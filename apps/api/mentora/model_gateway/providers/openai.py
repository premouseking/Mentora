"""
OpenAIProvider：兼容 OpenAI Chat Completions API（含 Function Calling）。

约定：
- 支持非流式 chat() 和流式 chat_stream()
- 流式模式下 tool_calls 在最后一个 chunk 汇总返回
- 不记录完整 request/response body（避免日志泄露 prompts 和 API Key）

约束：
- API Key 通过构造函数注入
- 不处理重试（由 ModelGateway 层负责）
- 错误通过异常传播

@module mentora/model_gateway/providers/openai
"""

from typing import AsyncGenerator

from mentora.model_gateway.providers.base import BaseProvider
from mentora.model_gateway.providers.http_client import async_post_json, async_post_sse
from mentora.model_gateway.dsml_tool_calls import parse_dsml_tool_calls
from mentora.model_gateway.schemas import (
    FunctionCall,
    Message,
    ProviderResponse,
    TokenUsage,
    ToolCall,
)


class OpenAIProvider(BaseProvider):
    """OpenAI 兼容 Chat Completions API 提供方。

    使用方式：
    ```python
    provider = OpenAIProvider(api_key="sk-...", model="gpt-4o-mini")
    resp = await provider.chat(messages=[...])
    async for chunk in provider.chat_stream(messages=[...]):
        print(chunk.content)
    ```
    """

    name = "openai"
    default_model = "gpt-4o-mini"

    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        model: str | None = None,
        *,
        request_timeout: int = 60,
        stream_timeout: int = 120,
    ):
        """
        参数：
        - api_key: API Key
        - base_url: API 基础 URL（默认 https://api.openai.com/v1）
        - model: 覆盖 default_model
        - request_timeout: 非流式请求超时（秒）
        - stream_timeout: 流式请求超时（秒）
        """
        self._api_key = api_key
        self._base_url = (base_url or "https://api.openai.com/v1").rstrip("/")
        self._model = model or self.default_model
        self._request_timeout = request_timeout
        self._stream_timeout = stream_timeout

    # ── 非流式 ──

    async def chat(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
        model: str | None = None,
        *,
        timeout: int | None = None,
    ) -> ProviderResponse:
        """非流式聊天完成请求。"""
        url = f"{self._base_url}/chat/completions"
        resp_json = await async_post_json(
            url=url,
            payload=self._build_payload(messages, tools, model, stream=False),
            headers=self._build_headers(),
            timeout=timeout or self._request_timeout,
        )
        return self._parse_response(resp_json, model or self._model, tools=tools)

    # ── 流式 ──

    async def chat_stream(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
        model: str | None = None,
        *,
        timeout: int | None = None,
    ) -> AsyncGenerator[ProviderResponse, None]:
        """流式聊天完成请求（SSE）。"""
        url = f"{self._base_url}/chat/completions"
        tool_call_deltas: dict[int, dict] = {}  # index → 累计字段

        async for chunk_json in async_post_sse(
            url=url,
            payload=self._build_payload(messages, tools, model, stream=True),
            headers=self._build_headers(),
            timeout=timeout or self._stream_timeout,
        ):
            yield self._parse_stream_chunk(chunk_json, model or self._model, tool_call_deltas)

    # ── 内部方法 ──

    def _build_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
        }

    def _build_payload(
        self,
        messages: list[Message],
        tools: list[dict] | None,
        model: str | None,
        stream: bool,
    ) -> dict:
        payload: dict = {
            "model": model or self._model,
            "messages": [m.model_dump(mode="json") for m in messages],
            "stream": stream,
        }
        if tools:
            payload["tools"] = tools
        if stream:
            payload["stream_options"] = {"include_usage": True}
        return payload

    def _parse_response(
        self,
        resp: dict,
        model: str,
        *,
        tools: list[dict] | None = None,
    ) -> ProviderResponse:
        """解析非流式 OpenAI 响应。"""
        choice = resp.get("choices", [{}])[0]
        message = choice.get("message", {})
        finish_reason = choice.get("finish_reason", "stop")

        content = message.get("content")
        tool_calls: list[ToolCall] | None = None
        if message.get("tool_calls"):
            tool_calls = [
                ToolCall(
                    id=tc["id"],
                    type=tc.get("type", "function"),
                    function=FunctionCall(
                        name=tc["function"]["name"],
                        arguments=tc["function"]["arguments"],
                    ),
                )
                for tc in message["tool_calls"]
            ]

        usage = None
        if "usage" in resp:
            u = resp["usage"]
            usage = TokenUsage(
                prompt_tokens=u.get("prompt_tokens", 0),
                completion_tokens=u.get("completion_tokens", 0),
                total_tokens=u.get("total_tokens", 0),
            )

        return self._apply_dsml_fallback(
            ProviderResponse(
                content=content,
                tool_calls=tool_calls,
                finish_reason=finish_reason,
                usage=usage,
                model=resp.get("model", model),
            ),
            tools=tools,
        )

    def _apply_dsml_fallback(
        self,
        response: ProviderResponse,
        *,
        tools: list[dict] | None = None,
    ) -> ProviderResponse:
        allow_promotion = bool(tools)
        if response.tool_calls:
            cleaned, _ = parse_dsml_tool_calls(response.content, allow_promotion=False)
            if cleaned != response.content:
                return ProviderResponse(
                    content=cleaned,
                    tool_calls=response.tool_calls,
                    finish_reason=response.finish_reason,
                    usage=response.usage,
                    model=response.model,
                )
            return response

        cleaned, tool_calls = parse_dsml_tool_calls(
            response.content,
            allow_promotion=allow_promotion,
        )
        if not tool_calls:
            if cleaned != response.content:
                return ProviderResponse(
                    content=cleaned or "",
                    tool_calls=None,
                    finish_reason=response.finish_reason,
                    usage=response.usage,
                    model=response.model,
                )
            return response
        return ProviderResponse(
            content=cleaned,
            tool_calls=tool_calls,
            finish_reason="tool_calls",
            usage=response.usage,
            model=response.model,
        )

    def _parse_stream_chunk(
        self,
        chunk: dict,
        model: str,
        tool_call_deltas: dict[int, dict],
    ) -> ProviderResponse:
        """解析单个 SSE chunk。

        流式 tool_calls 采用 delta 增量模式，需跨 chunk 累计：
        - id 出现在第一个 chunk
        - function.name 出现在第一个 chunk
        - function.arguments 可能分散在多个 chunk
        - 当 finish_reason 出现时汇总为完整 tool_calls 列表
        """
        # 仅含 usage 的 chunk（stream_options 启用时）
        choices = chunk.get("choices")
        if not choices:
            usage_info = None
            if "usage" in chunk:
                u = chunk["usage"]
                usage_info = TokenUsage(
                    prompt_tokens=u.get("prompt_tokens", 0),
                    completion_tokens=u.get("completion_tokens", 0),
                    total_tokens=u.get("total_tokens", 0),
                )
            return ProviderResponse(
                content=None,
                finish_reason="stop",
                usage=usage_info,
                model=chunk.get("model", model),
            )

        choice = choices[0]
        delta = choice.get("delta", {})
        finish_reason = choice.get("finish_reason")

        content = delta.get("content")

        # 累计 tool_calls 增量
        if delta.get("tool_calls"):
            for tc_delta in delta["tool_calls"]:
                idx = tc_delta["index"]
                if idx not in tool_call_deltas:
                    tool_call_deltas[idx] = {
                        "id": "",
                        "type": "function",
                        "function_name": "",
                        "function_args": "",
                    }
                d = tool_call_deltas[idx]
                if "id" in tc_delta and tc_delta["id"]:
                    d["id"] = tc_delta["id"]
                func = tc_delta.get("function", {})
                if func.get("name"):
                    d["function_name"] += func["name"]
                if func.get("arguments"):
                    d["function_args"] += func["arguments"]

        # 仅当 finish_reason 出现且有 tool_calls 时汇总
        chunk_tool_calls: list[ToolCall] | None = None
        if finish_reason and tool_call_deltas:
            chunk_tool_calls = []
            for idx in sorted(tool_call_deltas.keys()):
                d = tool_call_deltas[idx]
                if d["id"]:
                    chunk_tool_calls.append(
                        ToolCall(
                            id=d["id"],
                            type="function",
                            function=FunctionCall(
                                name=d["function_name"],
                                arguments=d["function_args"],
                            ),
                        )
                    )

        return ProviderResponse(
            content=content,
            tool_calls=chunk_tool_calls,
            finish_reason="streaming" if content and not finish_reason else (finish_reason or "stop"),
            model=chunk.get("model", model),
        )
