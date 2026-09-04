"""
Session-scoped, in-memory-only credential storage.

This file is the actual implementation of guardrail #1 and #2 from the
README: the frontend never sees credentials, and nothing here ever
touches disk, a database, or a log line. If you're extending this file,
the one rule that must never break is: nothing in this module writes to
anything other than the in-process dict below.

Restarting the backend process clears every session. That's intentional,
not a bug to fix later.
"""

import secrets
import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SessionCredentials:
    postman_api_key: str
    target_base_url: Optional[str] = None
    target_username: Optional[str] = None
    target_password: Optional[str] = None
    # Anything else resolved from the Postman environment that looks
    # credential-shaped goes here, keyed by variable name.
    other_secrets: dict = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


# In-memory only. No ORM, no file, no cache layer that could persist this
# to disk under the hood — keep it that way.
_SESSIONS: dict[str, SessionCredentials] = {}


def create_session(creds: SessionCredentials) -> str:
    """Stores credentials for a new session, returns an opaque session id.

    The session id is what the frontend holds and sends back on every
    request — it is never the credentials themselves.
    """
    session_id = secrets.token_urlsafe(32)
    _SESSIONS[session_id] = creds
    return session_id


def get_session(session_id: str) -> Optional[SessionCredentials]:
    return _SESSIONS.get(session_id)


def end_session(session_id: str) -> None:
    """Explicitly wipes a session's credentials. Call this when a demo
    is done, in addition to whatever natural expiry policy you add.
    """
    _SESSIONS.pop(session_id, None)


# TODO: add a background sweep that calls end_session() for anything
# older than e.g. 2 hours, so an abandoned browser tab doesn't leave
# credentials sitting in memory indefinitely.
