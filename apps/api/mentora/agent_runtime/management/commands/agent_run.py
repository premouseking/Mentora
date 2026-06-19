"""
Agent 运行时端到端自检命令。

用法：
    python manage.py agent_run --task "什么是梯度下降？"
    python manage.py agent_run --task "..." --stream

@module mentora/agent_runtime/management/commands/agent_run
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from mentora.agent_runtime.contracts import AgentConfig, AgentEventType
from mentora.agent_runtime.exceptions import AgentRuntimeError, MaxIterationsError
from mentora.agent_runtime.session import AgentSession
from mentora.agent_runtime.tools.builtin.search_evidence import SearchEvidenceTool
from mentora.agent_runtime.tools.base import ToolContext
from mentora.model_gateway.contracts import QualityTier
from mentora.model_gateway.exceptions import GatewayError


class Command(BaseCommand):
    help = "运行一次学习 Agent turn（多轮 tool-loop）"

    def add_arguments(self, parser) -> None:
        parser.add_argument("--task", required=True, help="用户学习任务或问题")
        parser.add_argument(
            "--tier",
            default="balanced",
            choices=[t.value for t in QualityTier],
        )
        parser.add_argument("--max-iterations", type=int, default=12)
        parser.add_argument("--owner-id", default="dev-user")
        parser.add_argument(
            "--dynamic-context",
            default="",
            help="注入到 system instructions 的动态上下文（非敏感）",
        )
        parser.add_argument(
            "--stream",
            action="store_true",
            help="流式输出模型增量（TOKEN_DELTA）",
        )

    def handle(self, *args, **options) -> None:
        config = AgentConfig(
            quality_tier=QualityTier(options["tier"]),
            max_iterations=options["max_iterations"],
        )
        session = AgentSession(
            config=config,
            tools=[SearchEvidenceTool()],
            tool_context=ToolContext(owner_id=options["owner_id"]),
            dynamic_context=options["dynamic_context"],
        )

        self.stdout.write(self.style.SUCCESS("Agent turn 开始"))
        self.stdout.write(f"task: {options['task']}")
        if options["stream"]:
            self.stdout.write("mode: stream")
        self.stdout.write("")

        try:
            if options["stream"]:
                self._run_stream(session, options["task"])
                return
            result = session.run(options["task"], emit=self._emit_event)
        except (GatewayError, AgentRuntimeError) as exc:
            raise CommandError(f"Agent turn 失败: {exc}") from exc

        self._print_result(result)

    def _run_stream(self, session: AgentSession, task: str) -> None:
        final_text = ""
        rounds = 0
        try:
            for event in session.run_stream(task):
                if event.type == AgentEventType.ROUND_START:
                    self.stdout.write(f"[round {event.round_index}] ---")
                elif event.type == AgentEventType.TOKEN_DELTA:
                    self.stdout.write(event.text, ending="")
                    self.stdout.flush()
                elif event.type == AgentEventType.TOOL_CALL_BEGIN:
                    self.stdout.write("")
                    self.stdout.write(
                        f"[round {event.round_index}] tool_begin: "
                        f"{event.tool_name} ({event.tool_call_id})"
                    )
                elif event.type == AgentEventType.TOOL_CALL_END:
                    suffix = " (error)" if event.error else ""
                    self.stdout.write(
                        f"[round {event.round_index}] tool_end: "
                        f"{event.tool_name}{suffix}"
                    )
                elif event.type == AgentEventType.TURN_END:
                    final_text = event.text
                    rounds = event.round_index
                elif event.type == AgentEventType.ERROR:
                    raise CommandError(f"Agent turn 失败: {event.error}")
        except (GatewayError, AgentRuntimeError, MaxIterationsError) as exc:
            raise CommandError(f"Agent turn 失败: {exc}") from exc

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Agent turn 完成 ✓"))
        self.stdout.write(f"rounds: {rounds}")
        self.stdout.write("")
        self.stdout.write(final_text)

    def _print_result(self, result) -> None:
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Agent turn 完成 ✓"))
        self.stdout.write(f"rounds       : {result.rounds}")
        self.stdout.write(f"finish_reason: {result.finish_reason}")
        self.stdout.write(
            "usage        : "
            f"prompt={result.usage.prompt_tokens} "
            f"completion={result.usage.completion_tokens} "
            f"total={result.usage.total_tokens}"
        )
        self.stdout.write("")
        self.stdout.write(result.text)

    def _emit_event(self, event) -> None:
        if event.type == AgentEventType.ROUND_START:
            self.stdout.write(f"[round {event.round_index}] ---")
        elif event.type == AgentEventType.TOOL_CALL_BEGIN:
            self.stdout.write(
                f"[round {event.round_index}] tool_begin: "
                f"{event.tool_name} ({event.tool_call_id})"
            )
        elif event.type == AgentEventType.TOOL_CALL_END:
            suffix = " (error)" if event.error else ""
            self.stdout.write(
                f"[round {event.round_index}] tool_end: {event.tool_name}{suffix}"
            )
