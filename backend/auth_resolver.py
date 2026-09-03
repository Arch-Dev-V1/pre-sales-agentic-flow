"""
Translates Postman's `auth` block (bearer/basic/apikey) into actual
HTTP headers, resolving any {{var}} placeholders against the
environment first.

This is what closes gap #4 from the conversation: a request whose auth
is stored as Postman's structured auth object — not a plain header
someone typed in — now actually authenticates when we call it for real.

OAuth2, Digest, and AWS Signature auth are deliberately unsupported —
they need multi-step token exchanges or request-signing that's real
scope, not a quick addition. If a target API needs one of these,
that's a genuine follow-up task, not a gap in this file.
"""

import base64

from variable_resolver import resolve_environment_variables


def build_auth_headers(auth: dict | None, environment: dict) -> dict:
    if not auth or auth.get("type") in (None, "noauth"):
        return {}

    auth_type = auth["type"]

    if auth_type == "bearer":
        token = resolve_environment_variables(_param(auth, "bearer", "token"), environment)
        return {"Authorization": f"Bearer {token}"} if token else {}

    if auth_type == "basic":
        username = resolve_environment_variables(_param(auth, "basic", "username"), environment) or ""
        password = resolve_environment_variables(_param(auth, "basic", "password"), environment) or ""
        encoded = base64.b64encode(f"{username}:{password}".encode()).decode()
        return {"Authorization": f"Basic {encoded}"}

    if auth_type == "apikey":
        key_name = _param(auth, "apikey", "key")
        key_value = resolve_environment_variables(_param(auth, "apikey", "value"), environment)
        location = _param(auth, "apikey", "in") or "header"
        if location == "header" and key_name:
            return {key_name: key_value}
        # TODO: "in": "query" needs to add a query param instead of a
        # header — api_proxy.call_api only accepts headers today, extend
        # its signature if a target API needs query-param auth.
        return {}

    # Don't silently send an unauthenticated request for an auth type we
    # don't handle — surface it clearly instead of a confusing 401 with
    # no explanation.
    raise NotImplementedError(f"Auth type '{auth_type}' is not yet supported.")


def _param(auth: dict, block_key: str, param_key: str):
    for entry in auth.get(block_key, []) or []:
        if entry.get("key") == param_key:
            return entry.get("value")
    return None
