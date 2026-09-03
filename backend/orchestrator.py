"""
Runs the three-agent pipeline: Analyst -> Sequencer -> Verifier, with the
Verifier able to bounce a correction back to the Sequencer up to
MAX_CORRECTION_ROUNDS times per README/config.

This file wires together everything else in the backend: it parses the
collection once, runs each agent through agent_runtime's shared
tool-use loop, and gives each agent only the tools and data it's
supposed to have (see each function's docstring for exactly what's
passed to which agent, and why).
"""

import json
from pathlib import Path

from agent_runtime import run_agent_loop
import api_proxy
from auth_resolver import build_auth_headers
from config import FAST_MODEL, REASONING_MODEL, MAX_CORRECTION_ROUNDS
from postman_parser import parse_collection
from secret_detection import looks_like_secret_field
from tools.tool_definitions import ANALYST_TOOLS, SEQUENCER_TOOLS, VERIFIER_TOOLS
from variable_resolver import resolve_environment_variables, resolve_step_references

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def _load_prompt(filename: str) -> str:
    return (PROMPTS_DIR / filename).read_text()


ANALYST_PROMPT = _load_prompt("analyst_agent.md")
SEQUENCER_PROMPT = _load_prompt("sequencer_agent.md")
VERIFIER_PROMPT = _load_prompt("verifier_agent.md")


async def run_analyst(endpoints: list[dict], environment_var_names: list[str]) -> dict:
    """Analyst pass: cheap/fast model, broad scan across all endpoints.
    Read-only by construction — its tool_executor never calls the
    network or touches session credentials, it only reads from the
    already-parsed `endpoints` list held in this closure.
    """

    async def tool_executor(name: str, tool_input: dict) -> dict:
        if name == "get_collection_structure":
            return {
                "endpoints": [
                    {"id": e["id"], "name": e["name"], "method": e["method"], "url": e["url"]}
                    for e in endpoints
                ]
            }

        if name == "get_endpoint_details":
            endpoint = next((e for e in endpoints if e["id"] == tool_input["endpoint_id"]), None)
            if endpoint is None:
                return {"error": f"No endpoint with id '{tool_input['endpoint_id']}'"}
            return {
                **endpoint,
                "headers": [
                    {"key": h["key"], "value": "<redacted-credential>" if looks_like_secret_field(h["key"]) else h["value"]}
                    for h in endpoint["headers"]
                ],
            }

        if name == "list_environment_variable_names":
            return {"variable_names": environment_var_names}

        raise ValueError(f"Analyst has no tool named '{name}'")

    return await run_agent_loop(
        model=FAST_MODEL,
        system_prompt=ANALYST_PROMPT,
        tools=ANALYST_TOOLS,
        user_message="Analyze this collection and return your final JSON per your Output format.",
        tool_executor=tool_executor,
    )


async def run_sequencer(analyst_output: dict, demo_config: dict, correction: dict | None = None) -> dict:
    """Sequencer pass: best reasoning model, no tools at all (see
    SEQUENCER_TOOLS — deliberately empty). Everything it needs is
    passed directly in the user message rather than fetched via a tool
    call, since it isn't allowed to look anything up itself.
    """

    async def tool_executor(name: str, tool_input: dict) -> dict:
        raise ValueError("The Sequencer Agent has no tools available; it should never call one.")

    payload = {"analyst_output": analyst_output, "demo_config": demo_config}
    if correction is not None:
        payload["correction_from_verifier"] = correction

    return await run_agent_loop(
        model=REASONING_MODEL,
        system_prompt=SEQUENCER_PROMPT,
        tools=SEQUENCER_TOOLS,
        user_message=json.dumps(payload),
        tool_executor=tool_executor,
    )


async def run_presenter(
    sequencer_output: dict, captured_responses: dict[int, dict], demo_config: dict
) -> list[dict]:
    """Presentation pass: decide what each step's screen should show.

    Runs AFTER the Verifier, because it needs the real response bodies —
    the Analyst only ever reports request fields, so nothing earlier in
    the pipeline has seen a response shape. Asking the Sequencer to
    design screens before verification would be guesswork against a
    structure it has never seen.

    This is the Sequencer's own prompt in "presentation" mode rather
    than a fourth agent: it's pure synthesis over data another agent
    already gathered, which per the README stays inside an existing
    agent's job.

    Returns a list of screen specs, or [] on any failure — a demo that
    can't be prettified is still a working demo, and DemoRunner.jsx
    falls back to rendering the raw response.
    """

    async def tool_executor(name: str, tool_input: dict) -> dict:
        raise ValueError("The Sequencer has no tools available; it should never call one.")

    steps = [
        {
            "step_number": s["step_number"],
            "narration": s["narration"],
            # Keyed by step_number, same convention as raw_responses.
            "response_body": captured_responses.get(s["step_number"]),
        }
        for s in sequencer_output["steps"]
        if captured_responses.get(s["step_number"]) is not None
    ]
    if not steps:
        return []

    payload = {"mode": "presentation", "demo_config": demo_config, "steps": steps}

    try:
        result = await run_agent_loop(
            model=REASONING_MODEL,
            system_prompt=SEQUENCER_PROMPT,
            tools=SEQUENCER_TOOLS,
            user_message=json.dumps(payload),
            tool_executor=tool_executor,
        )
        screens = result.get("screens", [])
        return screens if isinstance(screens, list) else []
    except Exception:
        # Deliberately swallowed: presentation is an enhancement, and a
        # demo that renders raw JSON beats one that fails to generate.
        return []


async def execute_endpoint(
    endpoint: dict,
    body: dict | None,
    resolution_values: dict,
    captured_responses: dict[int, dict] | None = None,
) -> dict:
    """Resolve one endpoint's payload/URL/headers and make the single
    real call to the target API.

    Shared deliberately by two callers: the Verifier's call_target_api
    tool during generation, and main.py's /run-step for a live re-run in
    front of a prospect. Both therefore get identical variable
    resolution, identical auth-header construction, and — because this
    is the only thing that reaches api_proxy — the identical secret
    redaction and the identical host allow-list check (a no-op under the
    default empty allow-list). api_proxy.py's module docstring asks for
    exactly one path to the network; this is it.

    Resolution happens in two passes: {{stepN.response.field}} against
    what earlier steps actually returned, then any remaining {{envVar}}
    placeholders. Deterministic code does the substitution, not the
    model, so a hallucinated value can't reach a live call.
    """
    body = resolve_step_references(body, captured_responses or {})
    body = resolve_environment_variables(body, resolution_values)

    url = resolve_environment_variables(endpoint["url"], resolution_values)

    headers = {
        h["key"]: resolve_environment_variables(h["value"], resolution_values)
        for h in endpoint["headers"]
    }
    # Postman's structured auth block (bearer/basic/apikey) becomes real
    # headers here — without it, authenticated endpoints fail even when
    # everything else is correct.
    headers.update(build_auth_headers(endpoint["auth"], resolution_values))

    return await api_proxy.call_api(endpoint["method"], url, headers, body)


async def run_verifier(sequencer_output: dict, endpoints: list[dict], resolution_values: dict) -> dict:
    """Verifier pass: best reasoning model, the only agent with
    call_target_api. Returns {"judgment": ..., "raw_responses": ...} —
    see the docstring note further down for why those stay separate.

    resolution_values is the ALREADY-MERGED dict of collection-level
    variables with real environment values layered on top (environment
    wins on conflicts) — see main.py's /generate-demo for where that
    merge happens. This function doesn't know or care whether a given
    value came from an environment or from the collection itself; that
    distinction only matters at merge time, not at resolution time.
    """
    endpoints_by_id = {e["id"]: e for e in endpoints}
    step_number_by_endpoint = {s["endpoint_id"]: s["step_number"] for s in sequencer_output["steps"]}

    # Captured directly from each real tool execution, not from the
    # model's own summarized text — this is what becomes "raw_responses"
    # below, and what DemoRunner.jsx actually renders. See the README
    # and the earlier fix to this file for why that distinction matters.
    captured_responses: dict[int, dict] = {}

    async def tool_executor(name: str, tool_input: dict) -> dict:
        if name != "call_target_api":
            raise ValueError(f"Verifier has no tool named '{name}'")

        endpoint_id = tool_input["endpoint_id"]
        endpoint = endpoints_by_id.get(endpoint_id)
        if endpoint is None:
            return {"error": f"No endpoint with id '{endpoint_id}'"}

        try:
            result = await execute_endpoint(
                endpoint, tool_input["resolved_body"], resolution_values, captured_responses
            )
        except api_proxy.HostNotAllowedError as e:
            return {"error": str(e)}

        step_number = step_number_by_endpoint.get(endpoint_id)
        if step_number is not None:
            captured_responses[step_number] = result["body"]

        return result

    judgment = await run_agent_loop(
        model=REASONING_MODEL,
        system_prompt=VERIFIER_PROMPT,
        tools=VERIFIER_TOOLS,
        user_message=json.dumps({"demo_script": sequencer_output}),
        tool_executor=tool_executor,
    )

    return {"judgment": judgment, "raw_responses": captured_responses}


async def run_pipeline(
    collection: dict, environment_var_names: list[str], resolution_values: dict, demo_config: dict
) -> dict:
    """Top-level orchestration: Analyst -> Sequencer -> Verifier, with the
    correction loop between Sequencer and Verifier. The collection is
    parsed into a flat endpoint list once, here, and shared by both the
    Analyst (read-only) and the Verifier (the only one allowed to call
    call_target_api against those same endpoints) — see postman_parser.py.

    resolution_values is the merged collection-variables + environment
    dict built by main.py's /generate-demo — see run_verifier's
    docstring for why the merge happens there, not in this function.
    """
    endpoints = parse_collection(collection)

    analyst_output = await run_analyst(endpoints, environment_var_names)
    sequencer_output = await run_sequencer(analyst_output, demo_config)

    for round_num in range(MAX_CORRECTION_ROUNDS + 1):
        verifier_result = await run_verifier(sequencer_output, endpoints, resolution_values)
        verifier_judgment = verifier_result["judgment"]
        raw_responses = verifier_result["raw_responses"]

        if verifier_judgment["overall_status"] == "verified":
            # Only worth designing screens for a demo someone will show.
            screens = await run_presenter(sequencer_output, raw_responses, demo_config)
            return {
                "status": "verified",
                "demo_script": sequencer_output,
                "verification": verifier_judgment,
                "raw_responses": raw_responses,
                "screens": screens,
                "correction_rounds_used": round_num,
            }

        if verifier_judgment["overall_status"] == "blocked" or round_num == MAX_CORRECTION_ROUNDS:
            return {
                "status": "needs_human_review",
                "demo_script": sequencer_output,
                "verification": verifier_judgment,
                "raw_responses": raw_responses,
                "screens": [],
                "correction_rounds_used": round_num,
            }

        sequencer_output = await run_sequencer(
            analyst_output, demo_config, correction=verifier_judgment["correction_requests"]
        )
