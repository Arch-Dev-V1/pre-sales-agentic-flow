"""
Parses a raw Postman collection (v2.1 format) into a flat list of
endpoints, resolving Postman's auth-inheritance chain (request auth
overrides folder auth overrides collection-level auth) into a single
concrete auth block per endpoint.

This is the one place in the codebase that understands Postman's
specific nested JSON shape, so agents and tools work with a simple
flat structure instead of walking folders every time.
"""

import json


def extract_collection_variables(collection: dict) -> dict:
    """Returns {name: value} for variables defined directly on the
    collection itself (Postman's "Variables" tab on a collection, not an
    environment). Many self-contained public collections rely on this
    instead of shipping a separate environment — e.g. a hardcoded
    baseURL living here rather than in an environment file.

    This is the fallback source used when a workspace has no
    environment at all — see main.py's /generate-demo, which merges
    this with (and lets) the real environment override it, matching
    Postman's own variable-precedence rules (environment values win
    over collection values when both define the same name).
    """
    return {
        v["key"]: v.get("value", "")
        for v in collection.get("variable", [])
        if v.get("key") and not v.get("disabled")
    }


def parse_collection(collection: dict) -> list[dict]:
    """Returns a flat list of endpoints:

    [{
        "id": str,
        "name": str,
        "method": str,
        "url": str,                 # raw, {{var}} placeholders intact
        "headers": [{"key": str, "value": str}],
        "body": dict | str | None,  # parsed JSON if the body was raw JSON
        "auth": dict | None,        # resolved auth block, Postman's own shape
        "description": str,
    }, ...]

    NOTE: only "raw" (JSON) and "urlencoded" body modes are handled, per
    our earlier decision to scope this to plain JSON text + base64
    fields — "formdata"/file-upload bodies are intentionally skipped.
    """
    endpoints: list[dict] = []
    _walk_items(collection.get("item", []), collection.get("auth"), endpoints)
    return endpoints


def _walk_items(items: list, inherited_auth: dict | None, endpoints: list) -> None:
    for item in items:
        if "item" in item:
            # It's a folder, not a request — recurse. A folder's own
            # auth (if set) overrides what it inherited from its parent;
            # if it has none, keep passing the inherited one down.
            folder_auth = item.get("auth", inherited_auth)
            _walk_items(item["item"], folder_auth, endpoints)
            continue

        request = item.get("request", {})
        if isinstance(request, str):
            # Some minimal collection exports allow a bare URL string
            # with no method/headers/body — too little to build a real
            # call from, skip it.
            continue

        request_auth = request.get("auth", inherited_auth)
        endpoints.append({
            "id": item.get("id") or item.get("name"),
            "name": item.get("name", "Unnamed request"),
            "method": request.get("method", "GET"),
            "url": _extract_url(request.get("url")),
            "headers": [
                {"key": h.get("key"), "value": h.get("value")}
                for h in request.get("header", [])
                if not h.get("disabled")
            ],
            "body": _extract_body(request.get("body")),
            "auth": request_auth,
            "description": request.get("description", "") if isinstance(request.get("description"), str) else "",
        })


def _extract_url(url) -> str:
    if isinstance(url, str):
        return url
    if isinstance(url, dict):
        return url.get("raw", "")
    return ""


def _extract_body(body):
    if not body:
        return None

    mode = body.get("mode")
    if mode == "raw":
        raw = body.get("raw", "")
        try:
            return json.loads(raw)
        except (ValueError, TypeError):
            return raw  # not valid JSON, return as plain text

    if mode == "urlencoded":
        return {p["key"]: p.get("value") for p in body.get("urlencoded", []) if not p.get("disabled")}

    # "formdata" (file uploads) and "graphql" modes: out of scope, per
    # our earlier decision to only support plain JSON + base64 fields.
    return None
