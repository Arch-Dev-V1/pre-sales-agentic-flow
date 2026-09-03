"""
Resolves Postman-style {{variableName}} placeholders against an
environment dict, and separately against prior step responses for the
Sequencer/Verifier's data-threading (e.g. {{step1.response.person_id}}).

This file is fully implemented, not a stub — the substitution logic
itself is simple; the judgment calls (which value to thread where) live
in the agents, not here.
"""

import re
from typing import Any

_VAR_PATTERN = re.compile(r"\{\{([a-zA-Z0-9_.]+)\}\}")
_STEP_REF_PATTERN = re.compile(r"^step(\d+)\.response\.(.+)$")


def resolve_environment_variables(value: Any, environment: dict) -> Any:
    """Recursively resolves {{envVarName}} placeholders in a string, or
    within a dict/list structure, against a flat environment dict.
    Non-matching placeholders (e.g. step references) are left untouched
    for resolve_step_references to handle separately.
    """
    if isinstance(value, str):
        def _sub(match: re.Match) -> str:
            name = match.group(1)
            if name in environment:
                return str(environment[name])
            return match.group(0)  # leave unresolved if unknown
        return _VAR_PATTERN.sub(_sub, value)

    if isinstance(value, dict):
        return {k: resolve_environment_variables(v, environment) for k, v in value.items()}

    if isinstance(value, list):
        return [resolve_environment_variables(v, environment) for v in value]

    return value


def resolve_step_references(value: Any, prior_responses: dict[int, dict]) -> Any:
    """Resolves {{stepN.response.fieldPath}} references against the
    actual responses captured from earlier steps in this run.

    prior_responses is keyed by step_number -> that step's real JSON
    response, as captured by the Verifier Agent while executing the
    script (never assumed ahead of time).
    """
    if isinstance(value, str):
        match = _VAR_PATTERN.fullmatch(value)
        if match:
            step_ref = _STEP_REF_PATTERN.match(match.group(1))
            if step_ref:
                step_num = int(step_ref.group(1))
                field_path = step_ref.group(2).split(".")
                node = prior_responses.get(step_num, {})
                for key in field_path:
                    if isinstance(node, dict):
                        node = node.get(key)
                    else:
                        return value  # path didn't resolve, leave as-is
                return node
        return value

    if isinstance(value, dict):
        return {k: resolve_step_references(v, prior_responses) for k, v in value.items()}

    if isinstance(value, list):
        return [resolve_step_references(v, prior_responses) for v in value]

    return value
