"""
ModelGateway 主入口：统一的模型调用接口。

约定：
- chat() 是唯一对外暴露的方法
- 内部完成：审计记录 → 路由 → 调用 → 校验 → 返回

约束：
- 不直接暴露 Provider SDK
- 所有调用都经过 TaskRouter 路由

@module mentora/model_gateway/gateway
"""

from typing import AsyncGenerator

from asgiref.sync import sync_to_async
from pydantic import BaseModel

from mentora.model_gateway.models import ModelAttempt, ModelRequest
from mentora.model_gateway.router import TaskRouter
from mentora.model_gateway.schemas import ChatResponse, Message, TokenUsage
from mentora.model_gateway.structured_output import StructuredOutputValidator


class ModelGateway:
    """模型调用网关。

    使用方式：
    ```python
    gateway = ModelGateway(router, validator)
    response = await gateway.chat(...)
    ```

    测试时禁用审计：
    ```python
    gateway = ModelGateway(router, audit_enabled=False)
    ```
    """

    def __init__(
        self,
        router: TaskRouter,
        output_validator: StructuredOutputValidator | None = None,
        audit_enabled: bool = True,
    ):
        self._router = router
        self._validator = output_validator or StructuredOutputValidator()
        self._audit_enabled = audit_enabled

    async def _create_request_audit(
        self,
        task_type: str,
        messages: list[Message],
        tools: list[dict] | None,
        output_schema_name: str,
        structured_output: bool,
    ):
        """创建 ModelRequest 审计记录（如果启用）。"""
        if not self._audit_enabled:
            return None
        return await sync_to_async(ModelRequest.objects.create)(
            task_type=task_type,
            provider_name=self._router.resolve(task_type).name,
            messages_json=[m.model_dump(mode="json") for m in messages],
            tools_json=tools,
            output_schema_name=output_schema_name,
            structured_output=structured_output,
        )

    async def _create_attempt_audit(
        self,
        req,
        provider_name: str,
        model_name: str,
        response_json: dict | None,
        usage_json: dict | None,
        success: bool,
        error_code: str = "",
        error_message: str = "",
    ):
        """创建 ModelAttempt 审计记录（如果启用）。"""
        if not self._audit_enabled:
            return None
        return await sync_to_async(ModelAttempt.objects.create)(
            request=req,
            attempt_number=1,
            provider_name=provider_name,
            model_name=model_name,
            response_json=response_json,
            usage_json=usage_json,
            latency_ms=0,
            success=success,
            error_code=error_code,
            error_message=error_message,
        )

    async def chat(
        self,
        task_type: str,
        messages: list[Message],
        tools: list[dict] | None = None,
        structured_output_schema: type[BaseModel] | None = None,
    ) -> ChatResponse:
        """统一模型调用入口。

        流程：
        1. 创建 ModelRequest 审计记录（如果启用）
        2. 通过 TaskRouter 解析 Provider
        3. Provider.chat() 返回原始响应
        4. 创建 ModelAttempt 审计记录（如果启用）
        5. 如有 structured_output_schema → 校验
        6. 返回 ChatResponse
        """
        schema_name = structured_output_schema.__name__ if structured_output_schema else ""

        # 1. 审计：创建请求记录
        req = await self._create_request_audit(
            task_type=task_type,
            messages=messages,
            tools=tools,
            output_schema_name=schema_name,
            structured_output=structured_output_schema is not None,
        )

        # 2. 路由
        provider = self._router.resolve(task_type)

        # 3. 调用
        try:
            provider_resp = await provider.chat(messages=messages, tools=tools)
            usage = provider_resp.usage or TokenUsage()
            model_name = provider_resp.model or provider.default_model

            response_json = {
                "content": provider_resp.content,
                "tool_calls": (
                    [tc.model_dump(mode="json") for tc in provider_resp.tool_calls]
                    if provider_resp.tool_calls
                    else None
                ),
            }
            usage_json = usage.model_dump(mode="json")

            # 4. 审计：创建调用记录
            await self._create_attempt_audit(
                req=req,
                provider_name=provider.name,
                model_name=model_name,
                response_json=response_json,
                usage_json=usage_json,
                success=True,
            )

            # 5. 结构化输出校验
            parsed_output: dict | None = None
            if structured_output_schema and provider_resp.content:
                instance, errors = self._validator.validate(
                    provider_resp.content, structured_output_schema
                )
                if instance is not None:
                    parsed_output = instance.model_dump(mode="json")

            # 6. 返回
            return ChatResponse(
                content=provider_resp.content,
                tool_calls=provider_resp.tool_calls,
                finish_reason=provider_resp.finish_reason,
                usage=usage,
                model=model_name,
                parsed_output=parsed_output,
            )

        except Exception:
            # 审计：记录失败的调用
            await self._create_attempt_audit(
                req=req,
                provider_name=provider.name,
                model_name=provider.default_model,
                response_json=None,
                usage_json=None,
                success=False,
                error_code="provider_error",
                error_message="Provider call failed",
            )
            raise

    async def chat_stream(
        self,
        task_type: str,
        messages: list[Message],
        tools: list[dict] | None = None,
    ) -> AsyncGenerator[ChatResponse, None]:
        """流式模型调用入口。

        流程：
        1. 创建 ModelRequest 审计记录（如果启用）
        2. 通过 TaskRouter 解析 Provider
        3. Provider.chat_stream() 逐 chunk 返回
        4. 每次 yield ChatResponse
        5. 流结束后创建 ModelAttempt 审计记录

        约束：
        - 结构化输出校验仅支持非流式模式（流式不走校验）
        """
        provider = self._router.resolve(task_type)

        # 1. 审计：创建请求记录
        if self._audit_enabled:
            req = await sync_to_async(ModelRequest.objects.create)(
                task_type=task_type,
                provider_name=provider.name,
                messages_json=[m.model_dump(mode="json") for m in messages],
                tools_json=tools,
                output_schema_name="",
                structured_output=False,
            )
        else:
            req = None

        # 2-4. 流式调用
        accumulated_content: list[str] = []
        last_chunk: ChatResponse | None = None
        try:
            async for provider_resp in provider.chat_stream(
                messages=messages, tools=tools
            ):
                if provider_resp.content:
                    accumulated_content.append(provider_resp.content)
                resp = ChatResponse(
                    content=provider_resp.content,
                    tool_calls=provider_resp.tool_calls,
                    finish_reason=provider_resp.finish_reason,
                    usage=provider_resp.usage,
                    model=provider_resp.model or provider.default_model,
                )
                last_chunk = resp
                yield resp
        except Exception:
            if self._audit_enabled and req is not None:
                await self._create_attempt_audit(
                    req=req,
                    provider_name=provider.name,
                    model_name=provider.default_model,
                    response_json=None,
                    usage_json=None,
                    success=False,
                    error_code="provider_error",
                    error_message="Provider stream call failed",
                )
            raise

        # 5. 审计：流结束后创建调用记录
        if self._audit_enabled and req is not None:
            usage = last_chunk.usage if last_chunk else TokenUsage()
            await self._create_attempt_audit(
                req=req,
                provider_name=provider.name,
                model_name=last_chunk.model if last_chunk else provider.default_model,
                response_json={
                    "content": "".join(accumulated_content),
                    "tool_calls": (
                        [tc.model_dump(mode="json") for tc in last_chunk.tool_calls]
                        if last_chunk and last_chunk.tool_calls
                        else None
                    ),
                },
                usage_json=usage.model_dump(mode="json"),
                success=True,
            )
