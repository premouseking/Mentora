"""
模型网关连通性自检命令。

约定：
- 用于「配置好 API key 后，一条命令验证链路是否打通」。
- --structured 走结构化校验路径，验证 JSON 模式与 Pydantic 校验。

用法：
    python manage.py llm_ping --prompt "用一句话介绍你自己"
    python manage.py llm_ping --tier premium --structured

@module mentora/model_gateway/management/commands/llm_ping
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from pydantic import BaseModel

from mentora.model_gateway.contracts import (
    ModelMessage,
    ModelRequest,
    QualityTier,
    Role,
    StreamEventType,
)
from mentora.model_gateway.exceptions import GatewayError
from mentora.model_gateway.gateway import get_gateway


class _PingShape(BaseModel):
    """--structured 模式下要求模型返回的最小 JSON 形态。"""

    message: str


class Command(BaseCommand):
    help = "调用模型网关验证 API key 链路是否打通"

    def add_arguments(self, parser) -> None:
        parser.add_argument("--prompt", default="用一句话证明你在线。")
        parser.add_argument(
            "--tier",
            default="balanced",
            choices=[t.value for t in QualityTier],
        )
        parser.add_argument("--structured", action="store_true")
        parser.add_argument("--stream", action="store_true")

    def handle(self, *args, **options) -> None:
        tier = QualityTier(options["tier"])
        prompt = options["prompt"]
        structured = options["structured"]
        stream = options["stream"]

        if structured:
            prompt = (
                f"{prompt}\n请仅返回 JSON，形如 {{\"message\": \"...\"}}，不要其他内容。"
            )

        request = ModelRequest(
            task_type="gateway_ping",
            quality_tier=tier,
            messages=[
                ModelMessage(role=Role.SYSTEM, content="你是连通性自检助手。"),
                ModelMessage(role=Role.USER, content=prompt),
            ],
            structured_output_schema=_PingShape if structured else None,
            max_output_tokens=256,
        )

        gateway = get_gateway()

        if stream:
            self._run_stream(gateway, request)
            return

        try:
            response = get_gateway().complete(request)
        except GatewayError as exc:
            raise CommandError(f"链路未打通: {exc}") from exc

        self.stdout.write(self.style.SUCCESS("链路打通 ✓"))
        self.stdout.write(f"provider      : {response.provider}")
        self.stdout.write(f"requested_model: {response.requested_model}")
        self.stdout.write(f"actual_model  : {response.actual_model}")
        self.stdout.write(f"finish_reason : {response.finish_reason}")
        self.stdout.write(
            "usage         : "
            f"prompt={response.usage.prompt_tokens} "
            f"completion={response.usage.completion_tokens} "
            f"total={response.usage.total_tokens}"
        )
        self.stdout.write(f"attempts      : {len(response.attempts)}")
        for i, attempt in enumerate(response.attempts, 1):
            line = f"  #{i} {attempt.provider}/{attempt.model} -> {attempt.status.value} ({attempt.latency_ms}ms)"
            if attempt.error:
                line += f" error={attempt.error}"
            self.stdout.write(line)

        if response.structured is not None:
            self.stdout.write(f"structured    : {response.structured.model_dump_json()}")
        else:
            self.stdout.write("")
            self.stdout.write(response.text)

    def _run_stream(self, gateway, request) -> None:
        self.stdout.write(self.style.SUCCESS("流式打通 ✓（增量如下）"))
        self.stdout.write("")
        try:
            for event in gateway.stream(request):
                if event.type == StreamEventType.DELTA:
                    # 增量实时输出，不换行。
                    self.stdout.write(event.text, ending="")
                    self.stdout.flush()
                elif event.type == StreamEventType.DONE and event.response is not None:
                    resp = event.response
                    self.stdout.write("")
                    self.stdout.write("")
                    self.stdout.write(
                        f"actual_model: {resp.actual_model}  "
                        f"finish: {resp.finish_reason}  "
                        f"total_tokens: {resp.usage.total_tokens}  "
                        f"attempts: {len(resp.attempts)}"
                    )
                    if resp.structured is not None:
                        self.stdout.write(
                            f"structured: {resp.structured.model_dump_json()}"
                        )
        except GatewayError as exc:
            raise CommandError(f"流式链路未打通: {exc}") from exc
