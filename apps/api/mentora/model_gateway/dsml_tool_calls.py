"""
DeepSeek DSML 工具调用解析与流式文本过滤。

约定：
- 部分 DeepSeek 兼容端点把 tool call 以 DSML 标记写入 content，而非 delta.tool_calls
- 解析后转为标准 ToolCall；可见回复中剥离 DSML 块

约束：
- 支持全角/半角 pipe 及单/双 pipe 分隔符变体
- 流式过滤在 tag 未完整到达前缓冲，避免 DSML 泄露到前端

@module mentora/model_gateway/dsml_tool_calls
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field

from mentora.model_gateway.schemas import FunctionCall, ToolCall

_DSML_BAR = r"[|｜]+"
_DSML_PREFIX = rf"<{_DSML_BAR}DSML{_DSML_BAR}"
_DSML_SUFFIX = rf"</{_DSML_BAR}DSML{_DSML_BAR}"

_TOOL_BLOCK_KINDS = ("tool_calls", "tool_call", "function_calls", "tool_use_error")
_BAR_VARIANTS = ("|", "｜", "｜｜")

_INVOKE_RE = re.compile(
    rf"{_DSML_PREFIX}invoke\s+name=\"([^\"]+)\"\s*>(.*?){_DSML_SUFFIX}invoke>",
    re.DOTALL | re.IGNORECASE,
)
_PARAM_RE = re.compile(
    rf"{_DSML_PREFIX}parameter\s+name=\"([^\"]+)\"\s+string=\"(true|false)\"\s*>"
    rf"(.*?){_DSML_SUFFIX}parameter>",
    re.DOTALL | re.IGNORECASE,
)
_DSML_MARKER_RE = re.compile(rf"<{_DSML_BAR}DSML{_DSML_BAR}", re.IGNORECASE)


def _build_dsml_tokens(kind: str, *, closing: bool = False) -> list[str]:
    tokens: list[str] = []
    for bars in _BAR_VARIANTS:
        if closing:
            tokens.append(f"</{bars}DSML{bars}{kind}>")
        else:
            tokens.append(f"<{bars}DSML{bars}{kind}>")
    return tokens


def _dsml_open_tokens() -> list[str]:
    tokens: list[str] = []
    for kind in _TOOL_BLOCK_KINDS:
        tokens.extend(_build_dsml_tokens(kind, closing=False))
    return tokens


def _dsml_close_tokens() -> list[str]:
    tokens: list[str] = []
    for kind in _TOOL_BLOCK_KINDS:
        tokens.extend(_build_dsml_tokens(kind, closing=True))
    return tokens


_DSML_OPEN_TOKENS = _dsml_open_tokens()
_DSML_CLOSE_TOKENS = _dsml_close_tokens()
_MAX_OPEN_TOKEN_LEN = max(len(token) for token in _DSML_OPEN_TOKENS)
_MAX_CLOSE_TOKEN_LEN = max(len(token) for token in _DSML_CLOSE_TOKENS)


def contains_dsml_markup(text: str | None) -> bool:
    if not text:
        return False
    return bool(_DSML_MARKER_RE.search(text))


def _find_earliest_token(text: str, tokens: list[str]) -> tuple[int, str] | None:
    best: tuple[int, str] | None = None
    for token in tokens:
        index = text.find(token)
        if index != -1 and (best is None or index < best[0]):
            best = (index, token)
    return best


def _longest_open_prefix_suffix_length(text: str) -> int:
    max_length = min(len(text), _MAX_OPEN_TOKEN_LEN - 1)
    for length in range(max_length, 0, -1):
        suffix = text[-length:]
        if any(token.startswith(suffix) for token in _DSML_OPEN_TOKENS):
            return length
    return 0


def _coerce_param_value(raw: str, string_attr: str):
    if string_attr == "true":
        return raw
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def _generate_tool_call_id() -> str:
    return f"call_{uuid.uuid4().hex[:24]}"


def _strip_dsml_blocks(content: str) -> str:
    cleaned = content
    for token in _DSML_OPEN_TOKENS:
        while True:
            start = cleaned.find(token)
            if start == -1:
                break
            close = _find_earliest_token(cleaned[start + len(token) :], _DSML_CLOSE_TOKENS)
            if close is None:
                cleaned = cleaned[:start]
                break
            end = start + len(token) + close[0] + len(close[1])
            cleaned = cleaned[:start] + cleaned[end:]
    return cleaned.strip()


def parse_dsml_tool_calls(
    content: str | None,
    *,
    allow_promotion: bool = True,
) -> tuple[str | None, list[ToolCall]]:
    """从完整 content 解析 DSML 工具调用，并返回剥离 DSML 后的可见文本。"""
    if not content or not contains_dsml_markup(content):
        return content, []

    if not allow_promotion:
        cleaned = _strip_dsml_blocks(content)
        return cleaned, []

    tool_calls: list[ToolCall] = []
    for invoke_name, invoke_body in _INVOKE_RE.findall(content):
        params: dict[str, object] = {}
        for param_name, string_attr, param_value in _PARAM_RE.findall(invoke_body):
            params[param_name] = _coerce_param_value(param_value.strip(), string_attr)
        tool_calls.append(
            ToolCall(
                id=_generate_tool_call_id(),
                type="function",
                function=FunctionCall(
                    name=invoke_name,
                    arguments=json.dumps(params, ensure_ascii=False),
                ),
            )
        )

    if not tool_calls:
        cleaned = _strip_dsml_blocks(content)
        return (cleaned or None), []

    first_open = _find_earliest_token(content, _DSML_OPEN_TOKENS)
    if first_open is None:
        return None, tool_calls
    prefix = content[: first_open[0]].strip()
    return (prefix or None), tool_calls


@dataclass
class DsmlStreamFilter:
    """流式剥离 DeepSeek DSML 工具块，避免标记泄露到用户可见输出。"""

    _buffer: str = ""
    _inside_dsml: bool = False
    _pending_visible: list[str] = field(default_factory=list)

    def push(self, chunk: str) -> list[str]:
        if chunk:
            self._buffer += chunk
        return self._consume(final=False)

    def flush(self) -> list[str]:
        return self._consume(final=True)

    def _consume(self, *, final: bool) -> list[str]:
        output: list[str] = []

        def emit(text: str) -> None:
            if text:
                output.append(text)

        while self._buffer:
            if self._inside_dsml:
                close = _find_earliest_token(self._buffer, _DSML_CLOSE_TOKENS)
                if close:
                    self._buffer = self._buffer[close[0] + len(close[1]) :]
                    self._inside_dsml = False
                    continue
                keep = 0 if final else min(len(self._buffer), _MAX_CLOSE_TOKEN_LEN - 1)
                self._buffer = self._buffer[len(self._buffer) - keep :]
                if final:
                    self._inside_dsml = False
                break

            open_match = _find_earliest_token(self._buffer, _DSML_OPEN_TOKENS)
            if open_match:
                emit(self._buffer[: open_match[0]])
                self._buffer = self._buffer[open_match[0] + len(open_match[1]) :]
                self._inside_dsml = True
                continue

            if final:
                emit(self._buffer)
                self._buffer = ""
                break

            keep = _longest_open_prefix_suffix_length(self._buffer)
            emit_length = len(self._buffer) - keep
            if emit_length <= 0:
                break
            emit(self._buffer[:emit_length])
            self._buffer = self._buffer[emit_length:]
            break

        return output
