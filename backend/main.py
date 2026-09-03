"""
FastAPI entrypoint. Kept intentionally thin — the interesting logic
lives in orchestrator.py, session_store.py, and api_proxy.py; this file
just wires HTTP routes to them.
"""

# Load .env BEFORE importing orchestrator — orchestrator imports
# agent_runtime, which constructs the Anthropic client at MODULE IMPORT
# TIME (reading ANTHROPIC_API_KEY from the environment). If dotenv
# loads after that import, the key won't be set yet. Ordering matters
# here more than it usually would.
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import api_proxy
import postman_client
from postman_parser import extract_collection_variables, parse_collection
from session_store import SessionCredentials, create_session, end_session, get_session
from orchestrator import execute_endpoint, run_pipeline

app = FastAPI(title="DemoForge API")

# TODO: restrict this before anything beyond local dev / a hackathon
# demo — "*" or a wide-open localhost list is fine for that, not for
# anything handling real credentials in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ListWorkspacesRequest(BaseModel):
    postman_api_key: str


@app.post("/postman/workspaces")
async def get_workspaces(req: ListWorkspacesRequest):
    """Powers ConnectPostman.jsx's workspace dropdown. Stateless — the
    api_key is used for this one lookup and not stored anywhere; it only
    lands in session_store once the user actually completes /connect.
    """
    return {"workspaces": await postman_client.list_workspaces(req.postman_api_key)}


class WorkspaceContentsRequest(BaseModel):
    postman_api_key: str
    workspace_id: str


@app.post("/postman/workspace-contents")
async def get_workspace_contents(req: WorkspaceContentsRequest):
    """Powers ConnectPostman.jsx's collection and environment dropdowns,
    once a workspace is picked. Same statelessness note as above.
    """
    return await postman_client.list_workspace_contents(req.workspace_id, req.postman_api_key)


class ConnectRequest(BaseModel):
    postman_api_key: str
    collection_id: str
    environment_id: str | None = None  # optional — see extract_collection_variables for the fallback
    target_base_url: str  # any host; optionally restricted by config.HOST_ALLOWLIST
    target_username: str | None = None
    target_password: str | None = None


class ConnectResponse(BaseModel):
    session_id: str


@app.post("/connect", response_model=ConnectResponse)
async def connect(req: ConnectRequest) -> ConnectResponse:
    """Step 1: user provides their Postman API key + collection id, plus
    the target API's credentials. environment_id is optional — a
    collection without one still works, via collection-level variables
    (merged in at /generate-demo time, once the collection is fetched).
    Everything lands in session_store, never in a response body, log,
    or database.
    """
    environment = {}
    if req.environment_id:
        environment = await postman_client.fetch_environment(req.environment_id, req.postman_api_key)

    creds = SessionCredentials(
        postman_api_key=req.postman_api_key,
        target_base_url=req.target_base_url,
        target_username=req.target_username,
        target_password=req.target_password,
        other_secrets=environment,  # resolved values, kept server-side only
    )
    session_id = create_session(creds)
    return ConnectResponse(session_id=session_id)


class DemoConfig(BaseModel):
    """Answers to the fixed, predefined pre-generation questions — see
    ConfigureDemo.jsx. Deliberately a closed set of fields, not a
    freeform brief: this app does not accept open-ended layout/UI
    instructions anywhere, by design, not just by convention.
    """

    industry: str  # e.g. "Banking & Financial Services" — shapes vocabulary in narration
    emphasis: str  # e.g. "Fraud prevention & risk" — which angle the story leans into
    tone: str  # "Formal & enterprise" | "Modern & approachable"
    company_name: str | None = None  # optional, used to personalize narration text
    depth: str  # "Quick overview (3 steps)" | "Full walkthrough (all verified steps)"


class GenerateDemoRequest(BaseModel):
    session_id: str
    collection_id: str
    demo_config: DemoConfig


class RunStepRequest(BaseModel):
    """A live, on-demand re-run of one step from a finished demo.

    payload is whatever the presenter has in the request editor — it may
    be the payload recorded during verification, or one they've just
    edited to use the prospect's own values. prior_responses carries the
    demo's recorded raw_responses so that a step whose payload threads
    {{stepN.response.field}} from an earlier step still resolves when
    run on its own.
    """

    session_id: str
    collection_id: str
    endpoint_id: str
    payload: dict | None = None
    prior_responses: dict[int, dict] = {}


async def _load_collection_context(session, collection_id: str) -> tuple[dict, dict]:
    """Fetch the collection and build the merged variable-resolution dict.

    Collection-level variables are the fallback base; real environment
    values (session.other_secrets) win when both define the same name —
    this matches Postman's own variable-precedence rules, and is what
    makes a collection with no environment at all still work.
    """
    collection = await postman_client.fetch_collection(collection_id, session.postman_api_key)
    resolution_values = {
        **extract_collection_variables(collection),
        **session.other_secrets,
    }
    return collection, resolution_values


@app.post("/generate-demo")
async def generate_demo(req: GenerateDemoRequest):
    """Step 3 (after connect + configure): kicks off the
    Analyst -> Sequencer -> Verifier pipeline. demo_config is passed
    straight through to the Sequencer — see orchestrator.py's
    run_sequencer and sequencer_agent.md for how it's used. Nothing in
    demo_config ever reaches the Analyst or Verifier; they don't need it
    and shouldn't have it.

    TODO: for the live "agent trace" UI, swap this for a streaming
    response (Server-Sent Events or a websocket) so the frontend can
    show each agent's progress in real time, per the README's note on
    why that live feed matters for the demo itself.
    """
    session = get_session(req.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found or expired.")

    collection, resolution_values = await _load_collection_context(session, req.collection_id)

    # An exception escaping run_pipeline would return a bare 500, and
    # CORSMiddleware only annotates responses that complete normally —
    # so the browser sees a response with no Access-Control-Allow-Origin
    # and reports an opaque CORS failure, hiding the real cause (an
    # upstream API error, an exhausted credit balance, a bad key).
    # Re-raising as an HTTPException keeps the response on the normal
    # path, headers and all, so the detail actually reaches the UI.
    try:
        result = await run_pipeline(collection, list(resolution_values.keys()), resolution_values, req.demo_config.model_dump())
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"{type(e).__name__}: {e}") from e
    return result


@app.post("/run-step")
async def run_step(req: RunStepRequest):
    """Re-execute one endpoint live, on demand, from a finished demo —
    the "actually fire this in front of the prospect" path, optionally
    with a payload they've just edited.

    Routes through orchestrator.execute_endpoint, the same function the
    Verifier's call_target_api uses during generation, so the host
    allow-list, auth resolution and response redaction all apply
    identically. There is deliberately no separate path to the target
    API here — see api_proxy.py's module docstring.
    """
    session = get_session(req.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found or expired.")

    collection, resolution_values = await _load_collection_context(session, req.collection_id)

    endpoint = next(
        (e for e in parse_collection(collection) if e["id"] == req.endpoint_id), None
    )
    if endpoint is None:
        raise HTTPException(
            status_code=404, detail=f"No endpoint '{req.endpoint_id}' in this collection."
        )

    try:
        return await execute_endpoint(
            endpoint, req.payload, resolution_values, req.prior_responses
        )
    except api_proxy.HostNotAllowedError as e:
        # A hard guardrail, not a server fault — 403 says "refused",
        # which is the honest status, and keeps it out of the 502 bucket
        # used for genuine upstream failures below.
        raise HTTPException(status_code=403, detail=str(e)) from e
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"{type(e).__name__}: {e}") from e


@app.post("/end-session")
async def end_session_route(session_id: str):
    """Explicit cleanup — call this when a demo is done, don't rely only
    on the background sweep mentioned in session_store.py.
    """
    end_session(session_id)
    return {"status": "ended"}
