"""
模型网关核心：路由 → 调用 → 重试/Fallback → 结构化校验 → 候选结果。

约定：
- 这是领域服务调用大模型的唯一入口；领域服务传入 ModelRequest，拿回 ModelResponse。
- 每次物理调用都记为一条 ModelAttempt，成功与失败都保留在 response.attempts 中，
  并同时记录 requested_model 与 actual_model。

约束：
- 结构化任务的输出在通过 Pydantic schema 校验前，绝不返回给领域服务。
- 透传给审计的字段不含密钥与私有资料正文。

@see docs/architecture/end-to-end-implementation-plan.md §8.2
@module mentora/model_gateway/gateway
"""

from __future__ import annotations

import json
import time
from collections.abc import Iterator

from pydantic import BaseModel, ValidationError

from .contracts import (
    AttemptStatus,
    ModelAttempt,
    ModelMessage,
    ModelRequest,
    ModelResponse,
    StreamEvent,
    StreamEventType,
    TokenUsage,
    ToolCall,
)
from .exceptions import GatewayError, ProviderError, StructuredOutputError
from .providers.base import ProviderRequest, ProviderResponse
from .registry import ProviderRegistry, RouteTarget


class ModelGateway:
    def __init__(self, registry: ProviderRegistry | None = None) -> None:
        self._registry = registry or ProviderRegistry()

    def complete(self, request: ModelRequest) -> ModelResponse:
        targets = self._registry.resolve_route(request.quality_tier)
        attempts: list[ModelAttempt] = []
        # requested_model 取主选候选，用于「请求模型 vs 实际模型」审计。
        requested_model = targets[0].model
        last_error: Exception | None = None

        for target in targets:
            outcome = self._try_target(request, target, attempts)
            if outcome is not None:
                provider_resp, structured = outcome
                return ModelResponse(
                    text=provider_resp.text,
                    requested_model=requested_model,
                    actual_model=provider_resp.model or target.model,
                    provider=target.provider,
                    finish_reason=provider_resp.finish_reason,
                    usage=provider_resp.usage,
                    attempts=attempts,
                    structured=structured,
                    tool_calls=list(provider_resp.tool_calls),
                )
            last_error = self._classify_last(attempts)

        # 全部候选耗尽：区分「结构化校验始终失败」与「provider 调用失败」。
        if attempts and attempts[-1].status == AttemptStatus.INVALID_OUTPUT:
            raise StructuredOutputError("所有候选输出均未通过结构化校验") from last_error
        raise ProviderError("所有候选调用均失败", transient=False) from last_error

    def stream(self, request: ModelRequest) -> Iterator[StreamEvent]:
        """
        流式调用，逐增量产出 DELTA，结束时产出携带完整 ModelResponse 的 DONE。

        约束（借鉴 lightest「输出对用户可见后不静默重试」）：
        - 仅在「尚未产出任何 DELTA」时允许切换到 Fallback 候选；
        - 一旦已产出增量，候选内/跨候选都不再重试，错误直接抛出。
        - 结构化任务在流结束后校验全文，校验失败抛 StructuredOutputError；
          此时增量可能已产出，但绝不返回未校验的 structured 给领域服务。
        """
        targets = self._registry.resolve_route(request.quality_tier)
        attempts: list[ModelAttempt] = []
        requested_model = targets[0].model
        emitted = False
        last_error: Exception | None = None

        for target in targets:
            if emitted:
                break
            provider = self._registry.get_provider(target.provider)
            provider_request = self._build_provider_request(request, target.model)
            started = time.perf_counter()
            buffer: list[str] = []
            finish_reason = "stop"
            usage = TokenUsage()
            tool_calls: list[ToolCall] = []

            try:
                for chunk in provider.stream(provider_request):
                    if chunk.delta:
                        buffer.append(chunk.delta)
                        emitted = True
                        yield StreamEvent(type=StreamEventType.DELTA, text=chunk.delta)
                    if chunk.finish_reason:
                        finish_reason = chunk.finish_reason
                    if chunk.usage:
                        usage = chunk.usage
                    if chunk.tool_calls:
                        tool_calls = list(chunk.tool_calls)
            except ProviderError as exc:
                attempts.append(
                    self._attempt(
                        target,
                        AttemptStatus.TIMEOUT
                        if "超时" in str(exc)
                        else AttemptStatus.PROVIDER_ERROR,
                        started,
                        error=str(exc),
                    )
                )
                last_error = exc
                if emitted:
                    raise
                continue  # 首片前失败：尝试 Fallback

            text = "".join(buffer)
            structured = None
            if request.structured_output_schema is not None:
                try:
                    structured = self._validate_structured(
                        text, request.structured_output_schema
                    )
                except StructuredOutputError as exc:
                    attempts.append(
                        self._attempt(
                            target, AttemptStatus.INVALID_OUTPUT, started, usage=usage,
                            error=str(exc),
                        )
                    )
                    raise

            attempts.append(
                self._attempt(target, AttemptStatus.SUCCEEDED, started, usage=usage)
            )
            yield StreamEvent(
                type=StreamEventType.DONE,
                response=ModelResponse(
                    text=text,
                    requested_model=requested_model,
                    actual_model=target.model,
                    provider=target.provider,
                    finish_reason=finish_reason,
                    usage=usage,
                    attempts=attempts,
                    structured=structured,
                    tool_calls=tool_calls,
                ),
            )
            return

        raise ProviderError("所有候选流式调用均失败", transient=False) from last_error

    def _try_target(
        self,
        request: ModelRequest,
        target: RouteTarget,
        attempts: list[ModelAttempt],
    ) -> tuple[ProviderResponse, BaseModel | None] | None:
        """在单个候选上重试。成功返回 (响应, 结构化实例)；用尽返回 None。"""
        provider = self._registry.get_provider(target.provider)
        provider_request = self._build_provider_request(request, target.model)

        for _ in range(self._registry.max_retries_per_attempt + 1):
            started = time.perf_counter()
            try:
                provider_resp = provider.generate(provider_request)
            except ProviderError as exc:
                attempts.append(
                    self._attempt(
                        target,
                        AttemptStatus.TIMEOUT
                        if "超时" in str(exc)
                        else AttemptStatus.PROVIDER_ERROR,
                        started,
                        error=str(exc),
                    )
                )
                if exc.transient:
                    continue  # 同 provider 重试
                return None  # 非瞬时错误：交给 Fallback 候选

            # 结构化校验
            if request.structured_output_schema is not None:
                try:
                    structured = self._validate_structured(
                        provider_resp.text, request.structured_output_schema
                    )
                except StructuredOutputError as exc:
                    attempts.append(
                        self._attempt(
                            target,
                            AttemptStatus.INVALID_OUTPUT,
                            started,
                            usage=provider_resp.usage,
                            error=str(exc),
                        )
                    )
                    continue  # 重新生成
                attempts.append(
                    self._attempt(
                        target, AttemptStatus.SUCCEEDED, started, usage=provider_resp.usage
                    )
                )
                return provider_resp, structured

            attempts.append(
                self._attempt(
                    target, AttemptStatus.SUCCEEDED, started, usage=provider_resp.usage
                )
            )
            return provider_resp, None

        return None

    def _build_provider_request(self, request: ModelRequest, model: str) -> ProviderRequest:
        return ProviderRequest(
            model=model,
            messages=[self._message_to_dict(m) for m in request.messages],
            max_output_tokens=request.max_output_tokens,
            temperature=request.temperature,
            json_mode=request.structured_output_schema is not None,
            tools=request.tools,
            tool_choice=request.tool_choice,
            timeout_s=self._registry.timeout_s,
            metadata=request.metadata,
        )

    @staticmethod
    def _message_to_dict(message: ModelMessage) -> dict[str, object]:
        payload: dict[str, object] = {
            "role": message.role.value,
            "content": message.content,
        }
        if message.tool_calls:
            payload["tool_calls"] = [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {"name": call.name, "arguments": call.arguments},
                }
                for call in message.tool_calls
            ]
        if message.tool_call_id:
            payload["tool_call_id"] = message.tool_call_id
        if message.name:
            payload["name"] = message.name
        return payload

    @staticmethod
    def _validate_structured(text: str, schema: type[BaseModel]) -> BaseModel:
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise StructuredOutputError(f"输出不是合法 JSON: {exc.msg}") from None
        try:
            return schema.model_validate(data)
        except ValidationError as exc:
            # 仅记录错误数量与字段，不回显模型原文，避免泄露隐藏答案。
            raise StructuredOutputError(
                f"结构化校验失败: {exc.error_count()} 处字段错误"
            ) from None

    @staticmethod
    def _attempt(
        target: RouteTarget,
        status: AttemptStatus,
        started: float,
        *,
        usage: TokenUsage | None = None,
        error: str | None = None,
    ) -> ModelAttempt:
        return ModelAttempt(
            provider=target.provider,
            model=target.model,
            status=status,
            latency_ms=int((time.perf_counter() - started) * 1000),
            usage=usage or TokenUsage(),
            error=error,
        )

    @staticmethod
    def _classify_last(attempts: list[ModelAttempt]) -> Exception:
        if attempts and attempts[-1].error:
            return GatewayError(attempts[-1].error)
        return GatewayError("候选失败")


_default_gateway: ModelGateway | None = None


def get_gateway() -> ModelGateway:
    """进程级单例。测试可直接构造 ModelGateway(registry=...) 绕过。"""
    global _default_gateway
    if _default_gateway is None:
        _default_gateway = ModelGateway()
    return _default_gateway
