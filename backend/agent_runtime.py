"""
Generic "run Claude with tools until it produces final JSON" loop,
shared by all three agents in orchestrator.py. Each agent differs only
in its model, system prompt, tool list, and tool-dispatch function —
this file is the shared plumbing, not agent-specific logic. Keeping it
here (rather than duplicating the loop three times in orchestrator.py)
is what makes it obvious the three agents really do follow the same
shape, not three subtly different implementations.
"""

import json

import anthropic

# Reads ANTHROPIC_API_KEY from the environment automatically. main.py
# loads .env before importing anything that imports this module — see
# the comment at the top of main.py for why the ordering matters.
client = anthropic.AsyncAnthropic()


async def run_agent_loop(
    model: str,
    system_prompt: str,
    tools: list[dict],
    user_message: str,
    tool_executor,  # async callable: (tool_name: str, tool_input: dict) -> dict
    max_turns: int = 8,
) -> dict:
    """Runs the tool-use loop until Claude stops calling tools and
    returns final text, which is parsed as JSON per each agent prompt's
    documented Output format.

    tool_executor is always awaited, even for agents (like the Analyst)
    whose tools don't themselves need to await anything — this keeps
    one consistent interface rather than a sync/async split between
    agents, which is what actually matters here: the Verifier's
    call_target_api genuinely needs to await a real HTTP call, so the
    loop itself has to support that either way.
    """
    messages = [{"role": "user", "content": user_message}]

    for _ in range(max_turns):
        response = await client.messages.create(
            model=model,
            system=system_prompt,
            tools=tools,
            messages=messages,
            max_tokens=4096,
        )

        if response.stop_reason != "tool_use":
            return _parse_final_json(response)

        messages.append({"role": "assistant", "content": response.content})

        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                result = await tool_executor(block.name, block.input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result),
                })
        messages.append({"role": "user", "content": tool_results})

    raise RuntimeError(f"Agent exceeded {max_turns} tool-use turns without a final answer.")


def _parse_final_json(response) -> dict:
    text = "".join(block.text for block in response.content if block.type == "text")
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        # TODO: for anything beyond a hackathon demo, consider one
        # automatic retry that shows the model its own broken JSON and
        # asks it to fix it, rather than failing the whole run outright.
        raise ValueError(f"Agent did not return valid JSON: {e}\nRaw text: {text}")
