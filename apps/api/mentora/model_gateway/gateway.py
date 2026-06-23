"""Async model gateway with audit, retry/fallback, and strict structured output."""

from __future__ import annotations

import time
from collections.abc import AsyncGenerator

from asgiref.sync import sync_to_async
from pydantic import BaseModel

from mentora.model_gateway.exceptions import ProviderError, StructuredOutputError
from mentora.model_gateway.models import ModelAttempt, ModelRequest
from mentora.model_gateway.providers.base import BaseProvider
from mentora.model_gateway.router import TaskRouter
from mentora.model_gateway.schemas import ChatResponse, Message, ProviderResponse, TokenUsage
from mentora.model_gateway.structured_output import StructuredOutputValidator


class ModelGateway:
    """Single async entrypoint for model calls.

    This keeps the target branch's async/audit direction while preserving the
    main branch's stricter gateway contract:
    - every physical attempt can be audited;
    - candidates can retry and then fallback;
    - structured output failures are gateway errors, not silent empty payloads.
    """

    def __init__(
        self,
        router: TaskRouter,
        output_validator: StructuredOutputValidator | None = None,
        audit_enabled: bool = True,
        max_retries_per_attempt: int = 1,
    ) -> None:
        self._router = router
        self._validator = output_validator or StructuredOutputValidator()
        self._audit_enabled = audit_enabled
        self._max_retries_per_attempt = max(0, max_retries_per_attempt)

    async def chat(
        self,
        task_type: str,
        messages: list[Message],
        tools: list[dict] | None = None,
        structured_output_schema: type[BaseModel] | None = None,
    ) -> ChatResponse:
        schema_name = structured_output_schema.__name__ if structured_output_schema else ""
        candidates = self._router.resolve_candidates(task_type)
        req = await self._create_request_audit(
            task_type=task_type,
            provider_name=candidates[0].name,
            messages=messages,
            tools=tools,
            output_schema_name=schema_name,
            structured_output=structured_output_schema is not None,
        )

        last_error: Exception | None = None
        attempt_number = 0
        structured_error_seen = False

        for provider in candidates:
            for _ in range(self._max_retries_per_attempt + 1):
                attempt_number += 1
                started = time.perf_counter()
                try:
                    provider_resp = await provider.chat(messages=messages, tools=tools)
                    chat_resp = self._build_chat_response(provider, provider_resp)

                    if structured_output_schema is not None:
                        if not provider_resp.content:
                            raise StructuredOutputError("Model returned empty structured output")
                        instance, errors = self._validator.validate(
                            provider_resp.content,
                            structured_output_schema,
                        )
                        if instance is None:
                            structured_error_seen = True
                            raise StructuredOutputError(
                                "Structured output validation failed: "
                                + "; ".join(errors[:5])
                            )
                        chat_resp.parsed_output = instance.model_dump(mode="json")

                    await self._create_attempt_audit(
                        req=req,
                        attempt_number=attempt_number,
                        provider_name=provider.name,
                        model_name=chat_resp.model or provider.default_model,
                        response_json=self._response_json(provider_resp),
                        usage_json=(chat_resp.usage or TokenUsage()).model_dump(mode="json"),
                        latency_ms=self._elapsed_ms(started),
                        success=True,
                    )
                    return chat_resp
                except StructuredOutputError as exc:
                    structured_error_seen = True
                    last_error = exc
                    await self._create_attempt_audit(
                        req=req,
                        attempt_number=attempt_number,
                        provider_name=provider.name,
                        model_name=provider.default_model,
                        response_json=None,
                        usage_json=None,
                        latency_ms=self._elapsed_ms(started),
                        success=False,
                        error_code="invalid_structured_output",
                        error_message=str(exc),
                    )
                    continue
                except Exception as exc:  # noqa: BLE001 - provider boundary
                    last_error = exc
                    await self._create_attempt_audit(
                        req=req,
                        attempt_number=attempt_number,
                        provider_name=provider.name,
                        model_name=provider.default_model,
                        response_json=None,
                        usage_json=None,
                        latency_ms=self._elapsed_ms(started),
                        success=False,
                        error_code="provider_error",
                        error_message=type(exc).__name__,
                    )
                    continue

        if structured_error_seen:
            raise StructuredOutputError("All candidates failed structured output validation") from last_error
        raise ProviderError("All model candidates failed", transient=False) from last_error

    async def chat_stream(
        self,
        task_type: str,
        messages: list[Message],
        tools: list[dict] | None = None,
    ) -> AsyncGenerator[ChatResponse, None]:
        candidates = self._router.resolve_candidates(task_type)
        provider = candidates[0]
        req = await self._create_request_audit(
            task_type=task_type,
            provider_name=provider.name,
            messages=messages,
            tools=tools,
            output_schema_name="",
            structured_output=False,
        )

        accumulated: list[str] = []
        last_chunk: ChatResponse | None = None
        started = time.perf_counter()
        try:
            async for provider_resp in provider.chat_stream(messages=messages, tools=tools):
                if provider_resp.content:
                    accumulated.append(provider_resp.content)
                last_chunk = self._build_chat_response(provider, provider_resp)
                yield last_chunk
        except Exception as exc:  # noqa: BLE001 - provider boundary
            await self._create_attempt_audit(
                req=req,
                attempt_number=1,
                provider_name=provider.name,
                model_name=provider.default_model,
                response_json=None,
                usage_json=None,
                latency_ms=self._elapsed_ms(started),
                success=False,
                error_code="provider_stream_error",
                error_message=type(exc).__name__,
            )
            raise

        usage = (last_chunk.usage if last_chunk else None) or TokenUsage()
        await self._create_attempt_audit(
            req=req,
            attempt_number=1,
            provider_name=provider.name,
            model_name=(last_chunk.model if last_chunk else "") or provider.default_model,
            response_json={
                "content": "".join(accumulated),
                "tool_calls": (
                    [tc.model_dump(mode="json") for tc in last_chunk.tool_calls]
                    if last_chunk and last_chunk.tool_calls
                    else None
                ),
            },
            usage_json=usage.model_dump(mode="json"),
            latency_ms=self._elapsed_ms(started),
            success=True,
        )

    async def _create_request_audit(
        self,
        *,
        task_type: str,
        provider_name: str,
        messages: list[Message],
        tools: list[dict] | None,
        output_schema_name: str,
        structured_output: bool,
    ):
        if not self._audit_enabled:
            return None
        return await sync_to_async(ModelRequest.objects.create)(
            task_type=task_type,
            provider_name=provider_name,
            messages_json=[m.model_dump(mode="json") for m in messages],
            tools_json=tools,
            output_schema_name=output_schema_name,
            structured_output=structured_output,
        )

    async def _create_attempt_audit(
        self,
        *,
        req,
        attempt_number: int,
        provider_name: str,
        model_name: str,
        response_json: dict | None,
        usage_json: dict | None,
        latency_ms: int,
        success: bool,
        error_code: str = "",
        error_message: str = "",
    ):
        if not self._audit_enabled or req is None:
            return None
        return await sync_to_async(ModelAttempt.objects.create)(
            request=req,
            attempt_number=attempt_number,
            provider_name=provider_name,
            model_name=model_name,
            response_json=response_json,
            usage_json=usage_json,
            latency_ms=latency_ms,
            success=success,
            error_code=error_code,
            error_message=error_message,
        )

    @staticmethod
    def _build_chat_response(provider: BaseProvider, resp: ProviderResponse) -> ChatResponse:
        return ChatResponse(
            content=resp.content,
            tool_calls=resp.tool_calls,
            finish_reason=resp.finish_reason,
            usage=resp.usage or TokenUsage(),
            model=resp.model or provider.default_model,
        )

    @staticmethod
    def _response_json(resp: ProviderResponse) -> dict:
        return {
            "content": resp.content,
            "tool_calls": (
                [tc.model_dump(mode="json") for tc in resp.tool_calls]
                if resp.tool_calls
                else None
            ),
        }

    @staticmethod
    def _elapsed_ms(started: float) -> int:
        return int((time.perf_counter() - started) * 1000)
