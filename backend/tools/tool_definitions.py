"""
Tool schemas for the three DemoForge agents, in Anthropic tool-use
format (each dict is passed directly in the `tools` param of a
Messages API call).

IMPORTANT — this is where the guardrails actually get enforced, not
just described. Each agent is given only the tool subset it's allowed
to use:

    Analyst Agent   -> ANALYST_TOOLS      (read-only, no network calls)
    Sequencer Agent -> SEQUENCER_TOOLS    (no tools at all — pure reasoning
                                            over what the Analyst found)
    Verifier Agent  -> VERIFIER_TOOLS     (the only agent with call_target_api)

The actual enforcement of the host policy (see config.HOST_POLICY) and
of "never return secret values" happens in the Python implementations
of these tools (see ../postman_client.py and ../api_proxy.py), not just
in the schema below — a schema alone can't stop a bad call, the
function behind it has to.
"""

# ---------------------------------------------------------------------------
# Analyst Agent tools — read-only. Notice there is deliberately no
# "call_api" tool here at all; the Analyst physically cannot make a
# network call to the target API, by omission, not by instruction alone.
# ---------------------------------------------------------------------------

GET_COLLECTION_STRUCTURE = {
    "name": "get_collection_structure",
    "description": (
        "Returns the folder/request structure of the connected Postman "
        "collection: request names, methods, and endpoint paths. Does not "
        "include request bodies or environment values — use "
        "get_endpoint_details for that."
    ),
    "input_schema": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}

GET_ENDPOINT_DETAILS = {
    "name": "get_endpoint_details",
    "description": (
        "Returns the full detail for one request in the collection: method, "
        "URL (with {{variable}} placeholders unresolved), headers, and body "
        "fields including any example values already saved in the "
        "collection. Any field whose value looks like a credential "
        "(matched by variable name, e.g. containing 'token', 'password', "
        "'secret', 'apiKey') is returned as the literal string "
        "'<redacted-credential>' regardless of what it actually contains."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "endpoint_id": {
                "type": "string",
                "description": "The request id from get_collection_structure",
            }
        },
        "required": ["endpoint_id"],
    },
}

LIST_ENVIRONMENT_VARIABLE_NAMES = {
    "name": "list_environment_variable_names",
    "description": (
        "Returns the NAMES of variables defined in the linked Postman "
        "environment (e.g. 'baseURL', 'authToken') — never their values. "
        "Use this to know what an endpoint depends on, not what it "
        "resolves to."
    ),
    "input_schema": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}

ANALYST_TOOLS = [
    GET_COLLECTION_STRUCTURE,
    GET_ENDPOINT_DETAILS,
    LIST_ENVIRONMENT_VARIABLE_NAMES,
]


# ---------------------------------------------------------------------------
# Sequencer Agent tools — deliberately empty.
#
# The Sequencer's job is pure reasoning over the Analyst's already-gathered
# output (passed to it directly in the conversation, not fetched via a
# tool). It has no need to touch the collection, the environment, or the
# network, so it gets no tools at all. If a future version needs it to
# look something up, add tools here explicitly and reconsider whether it
# still deserves the name "Sequencer" or has quietly become something else.
# ---------------------------------------------------------------------------

SEQUENCER_TOOLS = []


# ---------------------------------------------------------------------------
# Verifier Agent tools — the only agent that can touch the network.
# ---------------------------------------------------------------------------

CALL_TARGET_API = {
    "name": "call_target_api",
    "description": (
        "Makes a real HTTP call to the connected target API, with all "
        "{{variable}} placeholders resolved server-side before the request "
        "is sent. You select a request by endpoint_id only — the URL comes "
        "from the collection and is never taken from you, so there is no "
        "way to direct this tool at a host the collection doesn't already "
        "define. Depending on how the deployment is configured, a host may "
        "be refused and return an error instead of a response; treat that "
        "as a hard stop for the step, not something to retry against a "
        "different URL. Response bodies are returned as-is; if a response "
        "contains a field matching a known credential shape, it is "
        "redacted before being returned to you."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "endpoint_id": {
                "type": "string",
                "description": "The request id to execute",
            },
            "resolved_body": {
                "type": "object",
                "description": (
                    "The request body with symbolic references "
                    "(e.g. {{step1.response.person_id}}) already resolved "
                    "to real values from earlier step responses in this run."
                ),
            },
        },
        "required": ["endpoint_id", "resolved_body"],
    },
}

VERIFIER_TOOLS = [CALL_TARGET_API]
