"""
Config loading. Nothing here is a secret itself — actual credentials
(Postman API key, target API username/password) are supplied per-session
by the user at connect-time and live only in session_store.py, never here.
"""

import os

# The model used for cheap, broad work (Analyst's scan across many
# endpoints doesn't need deep reasoning per endpoint).
FAST_MODEL = os.environ.get("DEMOFORGE_FAST_MODEL", "claude-haiku-4-5-20251001")

# The model reserved for where correctness actually matters — the
# Verifier's job of judging whether a response is genuinely good, and the
# Sequencer's data-threading logic.
REASONING_MODEL = os.environ.get("DEMOFORGE_REASONING_MODEL", "claude-sonnet-5")

# Max correction rounds between Verifier and Sequencer before a step is
# flagged as a blocker needing human review, per the guardrail we agreed on.
MAX_CORRECTION_ROUNDS = 2

# --- Target host policy -----------------------------------------------
#
# Two phases, switched entirely by environment variable so that turning
# the restriction on later is a config change, not a code change.
#
# PHASE 1 — testing (the default, and what runs today):
#     DEMOFORGE_HOST_POLICY unset, or "open"
#   Every host a collection or environment resolves to is callable,
#   production hostnames included. This is deliberate: sample
#   collections point wherever they point, and the operator supplies
#   both the base URL and the credentials.
#
# PHASE 2 — restricted (later, once testing is done):
#     DEMOFORGE_HOST_POLICY=allowlist
#     DEMOFORGE_HOST_ALLOWLIST=sandbox.*,staging.*,*.test.internal
#   Only hosts matching a pattern are callable.
#
# Anything other than "open" is treated as allowlist mode, so a typo in
# this variable fails CLOSED (refuse everything) rather than silently
# leaving the target wide open.
HOST_POLICY = os.environ.get("DEMOFORGE_HOST_POLICY", "open").strip().lower()

# Patterns are matched against the URL's HOSTNAME only — never the whole
# URL string — so a path or query parameter can't be used to satisfy
# them. Three forms, all case-insensitive:
#     example.com      exact host
#     *.example.com    that host or any subdomain of it
#     sandbox.*        any host whose first label is "sandbox"
# Ignored entirely while HOST_POLICY is "open".
HOST_ALLOWLIST: list[str] = [
    pattern.strip().lower()
    for pattern in os.environ.get("DEMOFORGE_HOST_ALLOWLIST", "").split(",")
    if pattern.strip()
]

# Worth knowing in phase 1: the Verifier agent chooses which endpoints to
# call and with what payloads, so a production target means an agent may
# issue real POST/PUT/DELETE requests against real data. Read-only
# collections are the safe case.
