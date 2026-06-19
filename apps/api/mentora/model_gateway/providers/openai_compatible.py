"""
OpenAI 兼容 Chat Completions 适配器。

约定：
- 覆盖一切暴露 OpenAI 兼容端点的厂商：OpenAI、DeepSeek、通义千问（DashScope 兼容模式）、
  Moonshot、智谱 GLM 等，仅靠 base_url + 模型名区分，无需逐厂商写 SDK。
- 使用标准库 urllib 发起 HTTP，避免引入额外依赖；后续如需流式/连接池可替换为
  httpx 或官方 SDK，替换范围仅限本文件。

约束：
- api_key 仅在请求头使用，不写日志、不进异常信息。
- 仅本文件可出现厂商协议字段（choices/usage/message 等）。

@module mentora/model_gateway/providers/openai_compatible
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Iterator

from ..contracts import TokenUsage, ToolCall, ToolSpec
from ..exceptions import ProviderError, ProviderTimeout
from .base import (
    LlmProvider,
    ProviderRequest,
    ProviderResponse,
    ProviderStreamChunk,
)

# 上游瞬时错误，允许网关重试 / Fallback。
_TRANSIENT_STATUS = {408, 409, 429, 500, 502, 503, 504}


class OpenAICompatibleProvider(LlmProvider):
    def __init__(
        self,
        *,
        name: str,
        api_key: str,
        base_url: str,
        organization: str | None = None,
    ) -> None:
        self.name = name
        self._api_key = api_key
        # 统一去掉结尾斜杠，拼接 /chat/completions。
        self._base_url = base_url.rstrip("/")
        self._organization = organization

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        http_request = self._build_http_request(request, stream=False)
        try:
            with urllib.request.urlopen(http_request, timeout=request.timeout_s) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            raise self._http_error(exc) from None
        except TimeoutError:
            raise ProviderTimeout(f"provider {self.name} 调用超时") from None
        except urllib.error.URLError as exc:
            raise ProviderError(
                f"provider {self.name} 网络错误: {exc.reason}", transient=True
            ) from None

        return self._parse(raw)

    def stream(self, request: ProviderRequest) -> Iterator[ProviderStreamChunk]:
        http_request = self._build_http_request(request, stream=True)
        try:
            resp = urllib.request.urlopen(http_request, timeout=request.timeout_s)
        except urllib.error.HTTPError as exc:
            raise self._http_error(exc) from None
        except TimeoutError:
            raise ProviderTimeout(f"provider {self.name} 调用超时") from None
        except urllib.error.URLError as exc:
            raise ProviderError(
                f"provider {self.name} 网络错误: {exc.reason}", transient=True
            ) from None

        # 一旦开始读取，连接中途断开按非可恢复处理（已对用户可见，不重头重试）。
        with resp:
            accumulator = _StreamAccumulator()
            try:
                for raw_line in resp:
                    chunk = self._parse_sse_line(
                        raw_line.decode("utf-8").strip(),
                        accumulator,
                    )
                    if chunk is not None:
                        yield chunk
            except (urllib.error.URLError, TimeoutError) as exc:
                raise ProviderError(
                    f"provider {self.name} 流中断: {exc}", transient=False
                ) from None

    def _build_http_request(
        self, request: ProviderRequest, *, stream: bool
    ) -> urllib.request.Request:
        if not self._api_key:
            raise ProviderError(
                f"provider {self.name} 未配置 api_key", transient=False
            )

        payload: dict[str, object] = {
            "model": request.model,
            "messages": request.messages,
            "max_tokens": request.max_output_tokens,
            "temperature": request.temperature,
        }
        if request.json_mode:
            payload["response_format"] = {"type": "json_object"}
        if request.tools:
            payload["tools"] = [self._tool_spec_to_dict(spec) for spec in request.tools]
            payload["tool_choice"] = request.tool_choice
        if stream:
            payload["stream"] = True
            # 要求上游在末片附带用量；不支持的兼容端点会忽略，按缺省处理。
            payload["stream_options"] = {"include_usage": True}

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }
        if self._organization:
            headers["OpenAI-Organization"] = self._organization

        return urllib.request.Request(
            url=f"{self._base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )

    @staticmethod
    def _tool_spec_to_dict(spec: ToolSpec) -> dict[str, object]:
        return {
            "type": "function",
            "function": {
                "name": spec.name,
                "description": spec.description,
                "parameters": spec.parameters,
            },
        }

    def _http_error(self, exc: urllib.error.HTTPError) -> ProviderError:
        # 不回显响应体，避免泄露上游返回的敏感片段。
        return ProviderError(
            f"provider {self.name} 返回 HTTP {exc.code}",
            transient=exc.code in _TRANSIENT_STATUS,
        )

    def _parse_sse_line(
        self, line: str, accumulator: _StreamAccumulator
    ) -> ProviderStreamChunk | None:
        if not line or not line.startswith("data:"):
            return None
        data = line[len("data:") :].strip()
        if data == "[DONE]":
            return None
        try:
            payload = json.loads(data)
        except json.JSONDecodeError:
            return None

        choices = payload.get("choices") or []
        delta_text = ""
        finish_reason = None
        if choices:
            choice = choices[0]
            delta = choice.get("delta") or {}
            delta_text = delta.get("content") or ""
            finish_reason = choice.get("finish_reason")
            accumulator.ingest_tool_call_deltas(delta.get("tool_calls"))

        usage = None
        usage_raw = payload.get("usage")
        if usage_raw:
            usage = TokenUsage(
                prompt_tokens=int(usage_raw.get("prompt_tokens", 0)),
                completion_tokens=int(usage_raw.get("completion_tokens", 0)),
                total_tokens=int(usage_raw.get("total_tokens", 0)),
            )

        tool_calls = None
        if finish_reason:
            tool_calls = accumulator.finalize_tool_calls() or None

        if (
            not delta_text
            and finish_reason is None
            and usage is None
            and tool_calls is None
        ):
            return None
        return ProviderStreamChunk(
            delta=delta_text,
            finish_reason=finish_reason,
            usage=usage,
            tool_calls=tool_calls,
        )

    def _parse(self, raw: str) -> ProviderResponse:
        try:
            data = json.loads(raw)
            choice = data["choices"][0]
            message = choice["message"]
            text = message.get("content") or ""
            finish_reason = choice.get("finish_reason") or "stop"
            tool_calls = self._parse_tool_calls(message.get("tool_calls"))
        except (json.JSONDecodeError, KeyError, IndexError, TypeError):
            raise ProviderError(
                f"provider {self.name} 返回结构非预期", transient=False
            ) from None

        usage_raw = data.get("usage") or {}
        usage = TokenUsage(
            prompt_tokens=int(usage_raw.get("prompt_tokens", 0)),
            completion_tokens=int(usage_raw.get("completion_tokens", 0)),
            total_tokens=int(usage_raw.get("total_tokens", 0)),
        )
        return ProviderResponse(
            text=text,
            model=data.get("model", ""),
            finish_reason=finish_reason,
            usage=usage,
            tool_calls=tool_calls,
        )

    @staticmethod
    def _parse_tool_calls(raw_calls: object) -> list[ToolCall]:
        if not isinstance(raw_calls, list):
            return []
        calls: list[ToolCall] = []
        for item in raw_calls:
            if not isinstance(item, dict):
                continue
            fn = item.get("function") or {}
            if not isinstance(fn, dict):
                continue
            call_id = item.get("id")
            name = fn.get("name")
            if not call_id or not name:
                continue
            arguments = fn.get("arguments")
            calls.append(
                ToolCall(
                    id=str(call_id),
                    name=str(name),
                    arguments=str(arguments) if arguments is not None else "{}",
                )
            )
        return calls


class _StreamAccumulator:
    """聚合 OpenAI 流式 tool_calls 分片。"""

    def __init__(self) -> None:
        self._calls: dict[int, dict[str, object]] = {}

    def ingest_tool_call_deltas(self, raw_calls: object) -> None:
        if not isinstance(raw_calls, list):
            return
        for item in raw_calls:
            if not isinstance(item, dict):
                continue
            index = item.get("index")
            if index is None:
                continue
            slot = self._calls.setdefault(
                int(index),
                {"id": "", "name": "", "arguments": ""},
            )
            if item.get("id"):
                slot["id"] = str(item["id"])
            fn = item.get("function") or {}
            if isinstance(fn, dict):
                if fn.get("name"):
                    slot["name"] = str(fn["name"])
                if fn.get("arguments"):
                    slot["arguments"] = str(slot["arguments"]) + str(fn["arguments"])

    def finalize_tool_calls(self) -> list[ToolCall]:
        if not self._calls:
            return []
        calls: list[ToolCall] = []
        for index in sorted(self._calls):
            slot = self._calls[index]
            call_id = str(slot.get("id") or "")
            name = str(slot.get("name") or "")
            if not call_id or not name:
                continue
            calls.append(
                ToolCall(
                    id=call_id,
                    name=name,
                    arguments=str(slot.get("arguments") or "{}"),
                )
            )
        return calls
