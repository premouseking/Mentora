"""
模型网关连通性自检命令。

用法：
    python manage.py llm_ping --prompt "用一句话介绍你自己"

@module mentora/model_gateway/management/commands/llm_ping
"""

from __future__ import annotations

import asyncio

from django.core.management.base import BaseCommand, CommandError
from pydantic import BaseModel

from mentora.agent_runtime.runtime import build_model_gateway, build_default_provider
from mentora.model_gateway.exceptions import ProviderError, StructuredOutputError
from mentora.model_gateway.schemas import Message


class _PingShape(BaseModel):
    message: str


class Command(BaseCommand):
    help = "调用模型网关验证 API key 链路是否打通"

    def add_arguments(self, parser) -> None:
        parser.add_argument("--prompt", default="用一句话证明你在线。")
        parser.add_argument("--structured", action="store_true")
        parser.add_argument("--stream", action="store_true")

    def handle(self, *args, **options) -> None:
        prompt = options["prompt"]
        structured = options["structured"]
        stream = options["stream"]

        if structured:
            prompt = (
                f"{prompt}\n请仅返回 JSON，形如 {{\"message\": \"...\"}}，不要其他内容。"
            )

        messages = [
            Message(role="system", content="你是连通性自检助手。"),
            Message(role="user", content=prompt),
        ]

        try:
            gateway = build_model_gateway(build_default_provider())
        except RuntimeError as exc:
            raise CommandError(str(exc)) from exc

        if stream:
            self._run_stream(gateway, messages)
            return

        try:
            response = asyncio.run(
                gateway.chat(
                    task_type="gateway_ping",
                    messages=messages,
                    structured_output_schema=_PingShape if structured else None,
                )
            )
        except (ProviderError, StructuredOutputError) as exc:
            raise CommandError(f"链路未打通: {exc}") from exc

        self.stdout.write(self.style.SUCCESS("链路打通 ✓"))
        self.stdout.write(f"model         : {response.model}")
        self.stdout.write(f"finish_reason : {response.finish_reason}")
        if response.usage:
            self.stdout.write(
                f"usage         : total={response.usage.total_tokens}"
            )
        if response.parsed_output is not None:
            self.stdout.write(f"structured    : {response.parsed_output}")
        else:
            self.stdout.write("")
            self.stdout.write(response.content or "")

    def _run_stream(self, gateway, messages) -> None:
        self.stdout.write(self.style.SUCCESS("流式打通 ✓（增量如下）"))
        self.stdout.write("")

        async def _consume():
            parts: list[str] = []
            async for chunk in gateway.chat_stream(
                task_type="gateway_ping",
                messages=messages,
            ):
                if chunk.content:
                    parts.append(chunk.content)
                    self.stdout.write(chunk.content, ending="")
                    self.stdout.flush()
            return "".join(parts)

        try:
            asyncio.run(_consume())
            self.stdout.write("")
        except ProviderError as exc:
            raise CommandError(f"流式链路未打通: {exc}") from exc
