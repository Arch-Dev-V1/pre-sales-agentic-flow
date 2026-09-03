"""
The only module in the whole codebase that makes an HTTP call to the
target API. Every other piece of the system — frontend, Analyst,
Sequencer — goes through here indirectly or not at all.

Any host is callable by default: config.HOST_POLICY is "open", so the
URL a collection or environment resolves to is used as given, production
hostnames included. Setting DEMOFORGE_HOST_POLICY=allowlist switches on
the hostname allow-list, enforced here and here only — no code change
needed to flip between the two.

If you're tempted to add a second code path that calls the target API
directly from somewhere else, don't — route it through here, so that
response redaction (and the allow-list, when configured) can't be
bypassed.
"""

from urllib.parse import urlparse

import httpx

from config import HOST_ALLOWLIST, HOST_POLICY
from secret_detection import looks_like_secret_field


class HostNotAllowedError(Exception):
    """Raised when HOST_POLICY is not "open" and a resolved URL's host
    doesn't match config.HOST_ALLOWLIST. Never raised in the default
    "open" policy. When it is raised it's a hard stop, not a warning to
    log and continue past.
    """


def _host_matches(host: str, pattern: str) -> bool:
    """Match one hostname against one allow-list pattern.

    Matching is on the hostname alone and on label boundaries, so
    "sandbox.*" accepts sandbox.acme.com but not notsandbox.acme.com,
    and no path or query string can ever satisfy a pattern.
    """
    if pattern.startswith("*."):
        suffix = pattern[1:]  # ".example.com"
        return host == pattern[2:] or host.endswith(suffix)
    if pattern.endswith(".*"):
        prefix = pattern[:-2]  # "sandbox"
        return host == prefix or host.startswith(prefix + ".")
    return host == pattern


def _is_allowed_host(url: str) -> bool:
    if HOST_POLICY == "open":
        return True

    # Allow-list mode fails closed: an unparseable URL, or an empty or
    # misconfigured list, refuses rather than falling through to allow.
    host = (urlparse(url).hostname or "").lower()
    if not host:
        return False
    return any(_host_matches(host, pattern) for pattern in HOST_ALLOWLIST)


async def call_api(method: str, url: str, headers: dict, body: dict | None) -> dict:
    """Makes the real call.

    Under the default "open" policy every URL is permitted. Under
    "allowlist", the check runs on the hostname of the fully-resolved
    URL, after variable substitution — never on the unresolved
    {{baseURL}} template, which would trivially bypass it.
    """
    if not _is_allowed_host(url):
        raise HostNotAllowedError(
            f"Refusing to call '{url}': host is not in DEMOFORGE_HOST_ALLOWLIST "
            f"(policy '{HOST_POLICY}', patterns {HOST_ALLOWLIST or 'none'}). "
            f"Add a matching pattern, or set DEMOFORGE_HOST_POLICY=open to "
            f"allow any host."
        )

    async with httpx.AsyncClient() as client:
        resp = await client.request(method, url, headers=headers, json=body, timeout=15.0)
        return {
            "status_code": resp.status_code,
            "body": _redact_known_secret_fields(resp.json() if _looks_like_json(resp) else resp.text),
        }


def _looks_like_json(resp: httpx.Response) -> bool:
    return "application/json" in resp.headers.get("content-type", "")


def _redact_known_secret_fields(body):
    """Best-effort redaction of anything in a response that looks
    credential-shaped, before it's ever returned to an agent or the
    frontend. Deliberately conservative — false positives (redacting a
    field that wasn't actually sensitive) are the safe failure mode
    here, not the reverse. Uses the same heuristic as orchestrator.py's
    Analyst tool_executor — see secret_detection.py — so the two never
    drift out of sync with each other.
    """
    if isinstance(body, dict):
        return {
            k: ("<redacted>" if looks_like_secret_field(k) else _redact_known_secret_fields(v))
            for k, v in body.items()
        }
    if isinstance(body, list):
        return [_redact_known_secret_fields(v) for v in body]
    return body
