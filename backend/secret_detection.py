"""
Shared heuristic for detecting credential-shaped field names. Used by
both api_proxy.py (redacting response bodies) and orchestrator.py
(redacting what the Analyst Agent sees) — one definition, not two that
can silently drift out of sync, per the TODO left in an earlier version
of api_proxy.py.
"""

SECRET_FIELD_HINTS = ("token", "password", "secret", "apikey", "api_key")


def looks_like_secret_field(key: str) -> bool:
    if not key:
        return False
    return any(hint in key.lower() for hint in SECRET_FIELD_HINTS)
