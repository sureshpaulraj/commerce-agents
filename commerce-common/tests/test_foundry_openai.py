# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0

"""The Foundry OpenAI adapter's translation both ways: an Anthropic request as an OpenAI
one, and an OpenAI stream as the raw events the turn accumulator reads. No network."""

from __future__ import annotations

import json
from typing import Any

import pytest

from commerce_common.foundry_openai import (
    AsyncFoundryOpenAI,
    _Accumulating,
    _messages,
    _tool_choice,
    _tools,
    _usage,
)
from commerce_common.turn import StreamedRound


def test_system_blocks_become_one_system_message() -> None:
    out = _messages([{"type": "text", "text": "Be brief.", "cache_control": {"type": "x"}}], [])
    assert out == [{"role": "system", "content": "Be brief."}]


def test_tool_result_precedes_user_text_in_the_same_turn() -> None:
    """OpenAI requires a tool message to answer its call directly, so the result is split
    out ahead of whatever text shared the Anthropic turn."""
    out = _messages(
        None,
        [
            {
                "role": "user",
                "content": [
                    {"type": "tool_result", "tool_use_id": "t1", "content": "12 rows"},
                    {"type": "text", "text": "and now?"},
                ],
            }
        ],
    )
    assert [m["role"] for m in out] == ["tool", "user"]
    assert out[0] == {"role": "tool", "tool_call_id": "t1", "content": "12 rows"}


def test_assistant_tool_use_becomes_tool_calls() -> None:
    out = _messages(
        None,
        [
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "here"},
                    {"type": "tool_use", "id": "t9", "name": "present_products", "input": {"a": 1}},
                ],
            }
        ],
    )
    assert out[0]["content"] == "here"
    call = out[0]["tool_calls"][0]
    assert call["id"] == "t9"
    assert call["function"]["name"] == "present_products"
    assert json.loads(call["function"]["arguments"]) == {"a": 1}


def test_empty_assistant_turn_is_dropped() -> None:
    assert _messages(None, [{"role": "assistant", "content": []}]) == []


def test_tools_carry_the_input_schema_as_parameters() -> None:
    schema = {"type": "object", "properties": {"q": {"type": "string"}}}
    out = _tools([{"name": "search", "description": "d", "input_schema": schema}])
    assert out[0]["function"] == {"name": "search", "description": "d", "parameters": schema}


@pytest.mark.parametrize(
    "given,expected",
    [
        ({"type": "auto"}, "auto"),
        ({"type": "any"}, "required"),
        (
            {"type": "tool", "name": "present_plan"},
            {"type": "function", "function": {"name": "present_plan"}},
        ),
    ],
)
def test_tool_choice_maps(given: dict[str, Any], expected: Any) -> None:
    assert _tool_choice(given) == expected


def test_cached_prompt_tokens_are_reported_as_cache_reads() -> None:
    usage = _usage(
        {
            "prompt_tokens": 100,
            "completion_tokens": 7,
            "prompt_tokens_details": {"cached_tokens": 80},
        }
    )
    assert (usage.input_tokens, usage.output_tokens, usage.cache_read_input_tokens) == (100, 7, 80)


def test_translate_drops_caching_and_thinking_and_forces_no_reasoning() -> None:
    client = AsyncFoundryOpenAI(resource="acct", deployment="gpt-6-astra")
    body = client.translate(
        {
            "model": "claude-sonnet-5",
            "max_tokens": 900,
            "system": [{"type": "text", "text": "S", "cache_control": {"type": "ephemeral"}}],
            "tools": [{"name": "t", "description": "", "input_schema": {"type": "object"}}],
            "tool_choice": {"type": "auto"},
            "messages": [{"role": "user", "content": "hi"}],
            "thinking": {"type": "adaptive"},
            "output_config": {"effort": "high"},
        },
        stream=True,
    )
    # The deployment is what Foundry addresses, not the configured model id.
    assert body["model"] == "gpt-6-astra"
    assert body["max_completion_tokens"] == 900
    assert body["reasoning_effort"] == "none"
    assert "thinking" not in body and "output_config" not in body
    assert "cache_control" not in json.dumps(body)


def _feed(events: list[Any]) -> StreamedRound:
    round_ = StreamedRound()
    for event in events:
        round_.feed(event)
    return round_


def test_streamed_tool_call_reaches_the_accumulator_intact() -> None:
    """The events this adapter synthesizes must drive the real turn accumulator: a tool
    call arriving in fragments has to come back out as parsed input."""
    state = _Accumulating("gpt-6-astra")
    events = [state.start_tool(0, "call_1", "present_application_plan")]
    for piece in ['{"acres"', ": 640,", ' "rows": []}']:
        events.append(state.tool_arguments(0, piece))
    state.record_stop("tool_calls")
    events.extend(state.close_blocks())

    round_ = _feed(events)
    message, tool_uses, unreadable = round_.salvaged()
    assert not unreadable
    assert len(tool_uses) == 1
    assert tool_uses[0].name == "present_application_plan"
    assert tool_uses[0].input == {"acres": 640, "rows": []}
    assert message is not None


def test_final_message_parses_tool_input_and_reports_stop_reason() -> None:
    state = _Accumulating("gpt-6-astra")
    state.start_tool(0, "c1", "present_products")
    state.tool_arguments(0, '{"product_ids": ["HA-1001"]}')
    state.record_stop("tool_calls")
    state.record_usage({"prompt_tokens": 10, "completion_tokens": 2})

    message = state.message()
    assert message.stop_reason == "tool_use"
    assert message.content[0].input == {"product_ids": ["HA-1001"]}
    # The accumulator dumps every block; a block it cannot dump breaks the turn.
    assert message.content[0].model_dump(exclude_none=True, exclude={"citations"})["name"] == (
        "present_products"
    )


def test_unparsable_tool_input_becomes_empty_rather_than_raising() -> None:
    state = _Accumulating("gpt-6-astra")
    state.start_tool(0, "c1", "present_products")
    state.tool_arguments(0, '{"product_ids": [')
    assert state.message().content[0].input == {}


def test_text_and_tool_blocks_keep_separate_indices() -> None:
    state = _Accumulating("gpt-6-astra")
    start_text = state.start_text()
    state.text("Here you go.")
    start_tool = state.start_tool(0, "c1", "present_products")
    assert start_text.index == 0
    assert start_tool.index == 1
    blocks = state.message().content
    assert [b.type for b in blocks] == ["text", "tool_use"]


def test_final_delta_carries_the_counts_that_arrived_after_the_finish_reason() -> None:
    """Under `include_usage` the counts land in a chunk after the one naming the finish
    reason, so the closing delta is emitted last."""
    state = _Accumulating("gpt-6-astra")
    state.record_stop("stop")
    state.record_usage({"prompt_tokens": 41, "completion_tokens": 9})
    delta = state.delta_event()
    assert delta.usage.input_tokens == 41
    assert delta.usage.output_tokens == 9
    assert delta.delta.stop_reason == "end_turn"
