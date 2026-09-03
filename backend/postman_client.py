"""
Thin client for the Postman API — fetches the collection and its linked
environment so the Analyst Agent has something to read.

Uses the user's own Postman API key (held only in session_store, passed
in per-call here, never module-level or hardcoded).
"""

import httpx

POSTMAN_API_BASE = "https://api.getpostman.com"


async def list_workspaces(api_key: str) -> list[dict]:
    """Returns every workspace the given API key can see, as [{id, name}].
    This is what powers the first dropdown in ConnectPostman.jsx — the
    user never types a workspace id, they pick a name from this list.
    """
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{POSTMAN_API_BASE}/workspaces",
            headers={"X-Api-Key": api_key},
        )
        resp.raise_for_status()
        return [{"id": w["id"], "name": w["name"]} for w in resp.json()["workspaces"]]


async def list_workspace_contents(workspace_id: str, api_key: str) -> dict:
    """Returns the collections and environments inside one workspace, as
    {"collections": [{id, name}], "environments": [{id, name}]} — powers
    the second and third dropdowns. Same principle: the frontend shows
    names, the actual collection_id/environment_id ride along invisibly
    and are what eventually get sent to /connect.

    NOTE: verify this response shape against current Postman API docs
    before wiring the frontend up for real — the workspace detail
    endpoint's exact field names have shifted between API versions in
    the past, and this is written from the general shape, not a fresh
    check of today's docs.
    """
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{POSTMAN_API_BASE}/workspaces/{workspace_id}",
            headers={"X-Api-Key": api_key},
        )
        resp.raise_for_status()
        workspace = resp.json()["workspace"]
        return {
            "collections": [{"id": c["id"], "name": c["name"]} for c in workspace.get("collections", [])],
            "environments": [{"id": e["id"], "name": e["name"]} for e in workspace.get("environments", [])],
        }


async def fetch_collection(collection_id: str, api_key: str) -> dict:
    """Fetches a collection by id. Returns the raw Postman collection JSON
    (same shape as a manual 'Export > Collection v2.1' would give you).
    """
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{POSTMAN_API_BASE}/collections/{collection_id}",
            headers={"X-Api-Key": api_key},
        )
        resp.raise_for_status()
        return resp.json()["collection"]


async def fetch_environment(environment_id: str, api_key: str) -> dict:
    """Fetches a linked environment by id. Returns {name: value} pairs.

    NOTE: this is the one place actual secret values (authToken,
    password, etc.) enter the system. Callers must pass these straight
    into session_store's SessionCredentials — never log this return
    value, never pass it to an LLM call, never write it to a response
    the frontend can see.
    """
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{POSTMAN_API_BASE}/environments/{environment_id}",
            headers={"X-Api-Key": api_key},
        )
        resp.raise_for_status()
        values = resp.json()["environment"]["values"]
        return {v["key"]: v["value"] for v in values if v.get("enabled", True)}


def variable_names_only(environment: dict) -> list[str]:
    """Strips values, returns just the variable names — this is what
    gets passed to the Analyst Agent (see list_environment_variable_names
    tool), never the raw environment dict.
    """
    return list(environment.keys())


# TODO: add a small heuristic here (or reuse one from api_proxy.py) to
# classify which variable names look credential-shaped (token, password,
# secret, apiKey, ...) so postman_client and api_proxy agree on the same
# redaction rules rather than each guessing separately.
