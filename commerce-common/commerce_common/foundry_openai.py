# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0

"""An Anthropic-Messages-shaped client backed by an OpenAI-compatible Microsoft Foundry
deployment, so a deployment with no Anthropic model available can still run either role.

    from commerce_common.foundry_openai import AsyncFoundryOpenAI

    agent = ShoppingAgent(backend=..., client=AsyncFoundryOpenAI(
        resource="my-account", deployment="gpt-6-astra"))

This is the `client=` seam `docs/backends.md` and `docs/deployment.md` describe, filled in
for a non-Anthropic model. `AsyncAnthropicFoundry` is the right client whenever an
Anthropic deployment exists; reach for this one only when none does.

What it keeps and what it drops is the whole story, so it is stated once, here:

- Kept: tools, the eager tool-call stream (an OpenAI `arguments` delta becomes an
  `input_json_delta`, so presentation cards still render while they stream), tool results,
  forced tool choice, parallel tool calls, usage counts, and stop reasons. Every
  server-side guarantee — gates, provenance, caps, the rate engine — is untouched, because
  none of it runs in the model.
- Dropped: explicit cache breakpoints (`cache_control`) and adaptive thinking
  (`output_config.effort`), neither of which the OpenAI surface accepts. Breakpoints are
  stripped rather than emulated. An endpoint that caches prompts on its own still does so,
  and its cached prompt tokens are reported as `cache_read_input_tokens`, so a model-call
  log reads the same; what is lost is the control over where the prefix ends, not caching
  itself.

Foundry offers two OpenAI surfaces, and which one a deployment accepts is a property of
the deployment rather than a preference:

- `responses` (the default) is the only surface a reasoning model will carry function
  tools on. Every turn in both roles carries tools, so this is the surface most
  deployments need.
- `chat` is `/v1/chat/completions`, for a deployment that offers nothing else. A reasoning
  model refuses function tools there, so a reasoning deployment needs `reasoning_effort`
  set to whatever that endpoint still accepts, and some accept no value that works.

Set `FOUNDRY_SURFACE` to choose; a `FOUNDRY_BASE_URL` that names one of the two paths
selects it on its own. `reasoning_effort` is sent only when set, which leaves the
deployment's own default in place.

One cosmetic consequence: a model-call log line names the *configured* model, because that
string comes from the agent's config and this client substitutes the deployment when it
sends. The deployment actually called is named once, at startup, by the example host.

Credentials come from the Azure identity chain (`DefaultAzureCredential`): a managed
identity in Azure, and a developer login locally. No API key is read or stored.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import os
import time
import uuid
from collections.abc import AsyncIterator, Iterable
from contextlib import asynccontextmanager
from typing import Any

import httpx
from anthropic.types import (
    InputJSONDelta,
    Message,
    MessageDeltaUsage,
    RawContentBlockDeltaEvent,
    RawContentBlockStartEvent,
    RawContentBlockStopEvent,
    RawMessageDeltaEvent,
    RawMessageStartEvent,
    TextBlock,
    TextDelta,
    ToolUseBlock,
    Usage,
)
from anthropic.types.raw_message_delta_event import Delta

_SCOPE = "https://cognitiveservices.azure.com/.default"

# Anthropic reports why a turn ended; OpenAI reports how it stopped. The turn loop reads
# only `tool_use`, so the rest map to their nearest Anthropic name.
_STOP_REASONS = {
    "tool_calls": "tool_use",
    "stop": "end_turn",
    "length": "max_tokens",
    "content_filter": "refusal",
    "function_call": "tool_use",
}


def _text_of(content: Any) -> str:
    """The plain text of an Anthropic content value, which is either a string or a list
    of blocks. Non-text blocks carry no text and are skipped."""
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict) and block.get("type") == "text":
            parts.append(str(block.get("text", "")))
    return "".join(parts)


def _tools(tools: Iterable[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Anthropic tools as OpenAI functions. `cache_control` is a caching hint rather than
    part of the schema, so it is dropped with the rest of the caching surface."""
    converted: list[dict[str, Any]] = []
    for tool in tools or ():
        converted.append(
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": tool.get("input_schema") or {"type": "object", "properties": {}},
                },
            }
        )
    return converted


def _tool_choice(choice: Any) -> Any:
    """Anthropic's tool choice as OpenAI's. A forced tool is what grounding relies on, so
    it maps exactly; `any` becomes `required`."""
    if not isinstance(choice, dict):
        return "auto"
    kind = choice.get("type")
    if kind == "tool" and choice.get("name"):
        return {"type": "function", "function": {"name": choice["name"]}}
    if kind == "any":
        return "required"
    return "auto"


def _messages(system: Any, messages: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """The conversation as OpenAI messages. An Anthropic turn carries tool results as user
    content and tool calls as assistant content; OpenAI puts each in its own message, so one
    Anthropic message can become several."""
    out: list[dict[str, Any]] = []
    if (text := _text_of(system)).strip():
        out.append({"role": "system", "content": text})
    for message in messages:
        role = message.get("role")
        content = message.get("content")
        if role == "user":
            # Tool results come first: OpenAI requires them to directly answer the call.
            blocks = content if isinstance(content, list) else []
            for block in blocks:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    out.append(
                        {
                            "role": "tool",
                            "tool_call_id": block.get("tool_use_id", ""),
                            "content": _text_of(block.get("content")) or "",
                        }
                    )
            if (text := _text_of(content)).strip():
                out.append({"role": "user", "content": text})
            continue
        if role != "assistant":
            continue
        calls = [
            {
                "id": block.get("id", ""),
                "type": "function",
                "function": {
                    "name": block.get("name", ""),
                    "arguments": json.dumps(block.get("input") or {}),
                },
            }
            for block in (content if isinstance(content, list) else [])
            if isinstance(block, dict) and block.get("type") == "tool_use"
        ]
        entry: dict[str, Any] = {"role": "assistant", "content": _text_of(content)}
        if calls:
            entry["tool_calls"] = calls
        if entry["content"] or calls:
            out.append(entry)
    return out


def _usage(raw: Any) -> Usage:
    """OpenAI usage counts as Anthropic's. Cached prompt tokens, when the endpoint reports
    them, land on `cache_read_input_tokens` so a model-call log reads the same either way."""
    raw = raw if isinstance(raw, dict) else {}
    details = raw.get("prompt_tokens_details") or {}
    return Usage(
        input_tokens=int(raw.get("prompt_tokens", 0) or 0),
        output_tokens=int(raw.get("completion_tokens", 0) or 0),
        cache_read_input_tokens=int(details.get("cached_tokens", 0) or 0),
        cache_creation_input_tokens=0,
    )


def _responses_tools(tools: Iterable[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Anthropic tools as Responses function tools, which are flat where the chat
    surface nests them under `function`."""
    return [
        {
            "type": "function",
            "name": tool["name"],
            "description": tool.get("description", ""),
            "parameters": tool.get("input_schema") or {"type": "object", "properties": {}},
        }
        for tool in tools or ()
    ]


def _responses_tool_choice(choice: Any) -> Any:
    """Anthropic's tool choice as the Responses surface's. A forced tool is what grounding
    relies on, so it maps exactly."""
    if not isinstance(choice, dict):
        return "auto"
    kind = choice.get("type")
    if kind == "tool" and choice.get("name"):
        return {"type": "function", "name": choice["name"]}
    if kind == "any":
        return "required"
    return "auto"


def _responses_input(messages: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """The conversation as Responses input items. A tool call and its result are items in
    their own right here rather than roles, and they are matched by `call_id`."""
    out: list[dict[str, Any]] = []
    for message in messages:
        role = message.get("role")
        content = message.get("content")
        blocks = content if isinstance(content, list) else []
        if role == "user":
            for block in blocks:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    out.append(
                        {
                            "type": "function_call_output",
                            "call_id": block.get("tool_use_id", ""),
                            "output": _text_of(block.get("content")) or "",
                        }
                    )
            if (text := _text_of(content)).strip():
                out.append({"role": "user", "content": text})
            continue
        if role != "assistant":
            continue
        if (text := _text_of(content)).strip():
            out.append({"role": "assistant", "content": text})
        for block in blocks:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                out.append(
                    {
                        "type": "function_call",
                        "call_id": block.get("id", ""),
                        "name": block.get("name", ""),
                        "arguments": json.dumps(block.get("input") or {}),
                    }
                )
    return out


def _responses_usage(raw: Any) -> Usage:
    """Responses usage counts as Anthropic's. The names differ from the chat surface's."""
    raw = raw if isinstance(raw, dict) else {}
    details = raw.get("input_tokens_details") or {}
    return Usage(
        input_tokens=int(raw.get("input_tokens", 0) or 0),
        output_tokens=int(raw.get("output_tokens", 0) or 0),
        cache_read_input_tokens=int(details.get("cached_tokens", 0) or 0),
        cache_creation_input_tokens=0,
    )


class _Accumulating:
    """One streamed response, assembled as it arrives. The turn loop iterates the raw
    events and then asks for the final message, so both come from the same state."""

    def __init__(self, model: str) -> None:
        self._model = model
        self._blocks: list[dict[str, Any]] = []
        self._by_call: dict[int, int] = {}
        self._text_index: int | None = None
        self._usage = Usage(input_tokens=0, output_tokens=0)
        self._stop = "end_turn"

    def start_text(self) -> RawContentBlockStartEvent:
        self._text_index = len(self._blocks)
        self._blocks.append({"type": "text", "text": ""})
        return RawContentBlockStartEvent(
            type="content_block_start",
            index=self._text_index,
            content_block=TextBlock(type="text", text="", citations=None),
        )

    def text(self, piece: str) -> RawContentBlockDeltaEvent:
        assert self._text_index is not None
        self._blocks[self._text_index]["text"] += piece
        return RawContentBlockDeltaEvent(
            type="content_block_delta",
            index=self._text_index,
            delta=TextDelta(type="text_delta", text=piece),
        )

    @property
    def text_open(self) -> bool:
        return self._text_index is not None

    def start_tool(self, call_index: int, call_id: str, name: str) -> RawContentBlockStartEvent:
        index = len(self._blocks)
        self._by_call[call_index] = index
        self._blocks.append({"type": "tool_use", "id": call_id, "name": name, "buffer": ""})
        return RawContentBlockStartEvent(
            type="content_block_start",
            index=index,
            content_block=ToolUseBlock(type="tool_use", id=call_id, name=name, input={}),
        )

    def tool_arguments(self, call_index: int, piece: str) -> RawContentBlockDeltaEvent | None:
        index = self._by_call.get(call_index)
        if index is None:
            return None
        self._blocks[index]["buffer"] += piece
        return RawContentBlockDeltaEvent(
            type="content_block_delta",
            index=index,
            delta=InputJSONDelta(type="input_json_delta", partial_json=piece),
        )

    def record_usage(self, usage: Any) -> None:
        """Counts arrive in their own final chunk under `include_usage`, after the chunk
        that reported the finish reason."""
        if usage:
            self._usage = _usage(usage)

    def record_responses_usage(self, usage: Any) -> None:
        """The same counts from the Responses surface, which names them differently."""
        if usage:
            self._usage = _responses_usage(usage)

    def record_stop(self, reason: str | None) -> None:
        if reason:
            self._stop = _STOP_REASONS.get(reason, "end_turn")

    def settle_stop(self, truncated: bool) -> None:
        """The Responses surface reports no finish reason, so the turn's own shape names
        it: a tool call is what the turn loop dispatches on, and anything else ended."""
        if truncated:
            self._stop = "max_tokens"
        elif any(block["type"] == "tool_use" for block in self._blocks):
            self._stop = "tool_use"
        else:
            self._stop = "end_turn"

    def close_blocks(self) -> list[Any]:
        """Close every open block. OpenAI closes the whole choice at once, so the stops are
        synthesized here in block order; the turn loop dispatches a tool call on its stop,
        so these are emitted as soon as the finish reason lands rather than at end of stream."""
        return [
            RawContentBlockStopEvent(type="content_block_stop", index=index)
            for index in range(len(self._blocks))
        ]

    def delta_event(self) -> RawMessageDeltaEvent:
        """The closing `message_delta`, emitted once the stream is spent so it carries the
        final counts rather than the zeros known at finish time."""
        return RawMessageDeltaEvent(
            type="message_delta",
            delta=Delta(stop_reason=self._stop, stop_sequence=None),
            usage=MessageDeltaUsage(
                input_tokens=self._usage.input_tokens,
                output_tokens=self._usage.output_tokens,
                cache_read_input_tokens=self._usage.cache_read_input_tokens,
                cache_creation_input_tokens=self._usage.cache_creation_input_tokens,
            ),
        )

    def message(self) -> Message:
        content: list[Any] = []
        for block in self._blocks:
            if block["type"] == "text":
                if block["text"]:
                    content.append(TextBlock(type="text", text=block["text"], citations=None))
                continue
            try:
                parsed = json.loads(block["buffer"]) if block["buffer"].strip() else {}
            except json.JSONDecodeError:
                parsed = {}
            content.append(
                ToolUseBlock(
                    type="tool_use",
                    id=block["id"],
                    name=block["name"],
                    input=parsed if isinstance(parsed, dict) else {},
                )
            )
        return Message(
            id=f"msg_{uuid.uuid4().hex[:24]}",
            type="message",
            role="assistant",
            model=self._model,
            content=content,
            stop_reason=self._stop,
            stop_sequence=None,
            usage=self._usage,
        )


class _Stream:
    """The object `messages.stream()` yields: an async iterator of raw events, plus the
    final message once they are spent."""

    def __init__(self, response: httpx.Response, state: _Accumulating) -> None:
        self._response = response
        self._state = state

    def __aiter__(self) -> AsyncIterator[Any]:
        return self._events()

    async def _events(self) -> AsyncIterator[Any]:
        state = self._state
        yield RawMessageStartEvent(
            type="message_start",
            message=state.message(),
        )
        async for line in self._response.aiter_lines():
            if not line.startswith("data: "):
                continue
            payload = line[6:].strip()
            if payload == "[DONE]":
                break
            try:
                event = json.loads(payload)
            except json.JSONDecodeError:
                continue
            if usage := event.get("usage"):
                state.record_usage(usage)
            choices = event.get("choices") or []
            if not choices:
                continue
            choice = choices[0]
            delta = choice.get("delta") or {}
            if piece := delta.get("content"):
                if not state.text_open:
                    yield state.start_text()
                yield state.text(piece)
            for call in delta.get("tool_calls") or []:
                index = int(call.get("index", 0))
                function = call.get("function") or {}
                if call.get("id") and function.get("name"):
                    yield state.start_tool(index, call["id"], function["name"])
                if (arguments := function.get("arguments")) and (
                    frame := state.tool_arguments(index, arguments)
                ) is not None:
                    yield frame
            if reason := choice.get("finish_reason"):
                state.record_stop(reason)
                for closing in state.close_blocks():
                    yield closing
        yield state.delta_event()

    async def get_final_message(self) -> Message:
        return self._state.message()


class _ResponsesStream:
    """The same object over the Responses surface, whose events name items rather than
    choices. One `output_index` addresses one item, which is what `_Accumulating` already
    keys tool calls by, so the accumulated result is identical either way."""

    def __init__(self, response: httpx.Response, state: _Accumulating) -> None:
        self._response = response
        self._state = state

    def __aiter__(self) -> AsyncIterator[Any]:
        return self._events()

    async def _events(self) -> AsyncIterator[Any]:
        state = self._state
        yield RawMessageStartEvent(type="message_start", message=state.message())
        truncated = False
        async for line in self._response.aiter_lines():
            if not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if payload == "[DONE]":
                break
            try:
                event = json.loads(payload)
            except json.JSONDecodeError:
                continue
            kind = event.get("type")
            index = int(event.get("output_index", 0) or 0)
            if kind == "response.output_text.delta":
                if not state.text_open:
                    yield state.start_text()
                yield state.text(str(event.get("delta", "")))
            elif kind == "response.output_item.added":
                item = event.get("item") or {}
                if item.get("type") == "function_call":
                    yield state.start_tool(index, item.get("call_id", ""), item.get("name", ""))
            elif kind == "response.function_call_arguments.delta":
                if (frame := state.tool_arguments(index, str(event.get("delta", "")))) is not None:
                    yield frame
            elif kind in ("response.completed", "response.incomplete", "response.failed"):
                response = event.get("response") or {}
                state.record_responses_usage(response.get("usage"))
                reason = (response.get("incomplete_details") or {}).get("reason")
                truncated = reason == "max_output_tokens"
                if error := response.get("error"):
                    raise RuntimeError(f"Foundry response failed: {json.dumps(error)[:400]}")
            elif kind == "error":
                raise RuntimeError(f"Foundry response failed: {json.dumps(event)[:400]}")
        state.settle_stop(truncated)
        for closing in state.close_blocks():
            yield closing
        yield state.delta_event()

    async def get_final_message(self) -> Message:
        return self._state.message()


class _Messages:
    def __init__(self, client: AsyncFoundryOpenAI) -> None:
        self._client = client

    @asynccontextmanager
    async def stream(self, **request: Any) -> AsyncIterator[Any]:
        client = self._client
        responses = client.surface == "responses"
        body = (
            client.translate_responses(request, stream=True)
            if responses
            else client.translate(request, stream=True)
        )
        state = _Accumulating(str(request.get("model", "")))
        async with client.http.stream(
            "POST",
            client.url,
            json=body,
            headers=await client.headers(),
            timeout=client.timeout,
        ) as response:
            if response.status_code >= 400:
                raise _error(response.status_code, (await response.aread()).decode())
            yield _ResponsesStream(response, state) if responses else _Stream(response, state)

    async def create(self, **request: Any) -> Message:
        """One non-streamed call, for memory extraction and the analysis delegate."""
        client = self._client
        responses = client.surface == "responses"
        body = (
            client.translate_responses(request, stream=False)
            if responses
            else client.translate(request, stream=False)
        )
        response = await client.http.post(
            client.url,
            json=body,
            headers=await client.headers(),
            timeout=client.timeout,
        )
        if response.status_code >= 400:
            raise _error(response.status_code, response.text)
        payload = response.json()
        state = _Accumulating(str(request.get("model", "")))
        if responses:
            return _collect_responses(payload, state)
        choice = (payload.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        if text := message.get("content"):
            state.start_text()
            state.text(text)
        for index, call in enumerate(message.get("tool_calls") or []):
            function = call.get("function") or {}
            state.start_tool(index, call.get("id", ""), function.get("name", ""))
            state.tool_arguments(index, function.get("arguments") or "{}")
        state.record_stop(choice.get("finish_reason"))
        state.record_usage(payload.get("usage"))
        return state.message()


def _collect_responses(payload: dict[str, Any], state: _Accumulating) -> Message:
    """One non-streamed Responses body as the message the streamed path would have built."""
    for index, item in enumerate(payload.get("output") or []):
        kind = item.get("type")
        if kind == "message":
            for block in item.get("content") or []:
                if block.get("type") == "output_text" and (text := block.get("text")):
                    if not state.text_open:
                        state.start_text()
                    state.text(str(text))
        elif kind == "function_call":
            state.start_tool(index, item.get("call_id", ""), item.get("name", ""))
            state.tool_arguments(index, item.get("arguments") or "{}")
    state.record_responses_usage(payload.get("usage"))
    reason = (payload.get("incomplete_details") or {}).get("reason")
    state.settle_stop(reason == "max_output_tokens")
    return state.message()


def _error(status: int, body: str) -> Exception:
    """A Foundry failure as the error the host already handles. The example host turns an
    `anthropic.AuthenticationError` into a readable event, and a token that Foundry rejects
    is the same problem, so it is reported the same way."""
    import anthropic

    detail = body[:400]
    if status in (401, 403):
        return anthropic.AuthenticationError(
            message=(
                f"Microsoft Foundry rejected the Entra ID token ({status}). Confirm the "
                "identity holds 'Cognitive Services User' on the account. {detail}"
            ).format(detail=detail),
            response=httpx.Response(status, request=httpx.Request("POST", "https://foundry")),
            body=None,
        )
    return RuntimeError(f"Foundry request failed ({status}): {detail}")


def _surface(chosen: str | None, base_url: str | None) -> str:
    """Which of the two OpenAI surfaces to send to. An explicit choice wins; otherwise a
    base URL that names one selects it, because a caller who gave a full endpoint has
    already decided. Failing both, the surface a reasoning model can carry tools on."""
    named = (chosen or os.environ.get("FOUNDRY_SURFACE") or "").strip().lower()
    if named in ("responses", "chat"):
        return named
    if base_url and "chat/completions" in base_url:
        return "chat"
    return "responses"


class AsyncFoundryOpenAI:
    """An `AsyncAnthropic`-shaped client over an OpenAI-compatible Foundry deployment.

    `resource` is the Foundry account name, or pass `base_url` for a full endpoint.
    `surface` chooses between `/v1/responses` and `/v1/chat/completions`; the module
    docstring says why the default is the former. `reasoning_effort` is sent only when
    set, which leaves the deployment's own default in place.
    """

    def __init__(
        self,
        *,
        resource: str | None = None,
        base_url: str | None = None,
        deployment: str | None = None,
        credential: Any | None = None,
        timeout: float = 120.0,
        surface: str | None = None,
        reasoning_effort: str | None = None,
    ) -> None:
        resource = resource or os.environ.get("FOUNDRY_RESOURCE")
        base_url = base_url or os.environ.get("FOUNDRY_BASE_URL")
        self.surface = _surface(surface, base_url)
        path = "responses" if self.surface == "responses" else "chat/completions"
        self.url = base_url or f"https://{resource}.services.ai.azure.com/openai/v1/{path}"
        self.deployment = deployment or os.environ.get("FOUNDRY_DEPLOYMENT")
        self.timeout = timeout
        self.reasoning_effort = reasoning_effort or os.environ.get("FOUNDRY_REASONING_EFFORT")
        self.http = httpx.AsyncClient(timeout=timeout)
        self._credential = credential
        self._token: Any = None

    async def headers(self) -> dict[str, str]:
        """A bearer token from the Azure identity chain, cached until shortly before it
        expires. The synchronous credential is used off-thread on purpose: the async one
        pulls in `aiohttp`, and a cached token makes the hop rare."""
        token = self._token
        if token is None or token.expires_on - time.time() < 300:
            if self._credential is None:
                try:
                    from azure.identity import DefaultAzureCredential
                except ModuleNotFoundError as error:  # pragma: no cover - import guard
                    raise RuntimeError(
                        "AsyncFoundryOpenAI needs azure-identity for Entra ID auth: "
                        "pip install azure-identity"
                    ) from error

                self._credential = DefaultAzureCredential()
            getter = self._credential.get_token
            token = (
                await getter(_SCOPE)
                if inspect.iscoroutinefunction(getter)
                else await asyncio.to_thread(getter, _SCOPE)
            )
            self._token = token
        return {"Authorization": f"Bearer {token.token}"}

    def translate(self, request: dict[str, Any], *, stream: bool) -> dict[str, Any]:
        """One Anthropic request as an OpenAI one. `thinking`, `output_config`, and every
        `cache_control` are dropped here; see the module docstring."""
        body: dict[str, Any] = {
            "model": self.deployment or request.get("model"),
            "messages": _messages(request.get("system"), request.get("messages") or []),
            "max_completion_tokens": request.get("max_tokens", 4096),
            "stream": stream,
        }
        if tools := _tools(request.get("tools")):
            body["tools"] = tools
            body["tool_choice"] = _tool_choice(request.get("tool_choice"))
            body["parallel_tool_calls"] = True
        if self.reasoning_effort is not None:
            body["reasoning_effort"] = self.reasoning_effort
        if stream:
            body["stream_options"] = {"include_usage": True}
        return body

    def translate_responses(self, request: dict[str, Any], *, stream: bool) -> dict[str, Any]:
        """One Anthropic request as a Responses one. The system prompt becomes
        `instructions`; the same `thinking`, `output_config`, and `cache_control` are
        dropped as on the chat surface. Nothing is stored server-side: the turn loop holds
        the conversation and sends it whole, as it does for every other client."""
        body: dict[str, Any] = {
            "model": self.deployment or request.get("model"),
            "input": _responses_input(request.get("messages") or []),
            "max_output_tokens": request.get("max_tokens", 4096),
            "stream": stream,
            "store": False,
        }
        if (instructions := _text_of(request.get("system"))).strip():
            body["instructions"] = instructions
        if tools := _responses_tools(request.get("tools")):
            body["tools"] = tools
            body["tool_choice"] = _responses_tool_choice(request.get("tool_choice"))
            body["parallel_tool_calls"] = True
        if self.reasoning_effort is not None:
            body["reasoning"] = {"effort": self.reasoning_effort}
        return body

    @property
    def messages(self) -> _Messages:
        return _Messages(self)

    async def close(self) -> None:
        await self.http.aclose()
        closer = getattr(self._credential, "close", None)
        if closer is None:
            return
        if inspect.iscoroutinefunction(closer):
            await closer()
        else:
            await asyncio.to_thread(closer)
