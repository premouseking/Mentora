"""Orchestrator 流式输出测试。"""

import asyncio
import json

from django.test import SimpleTestCase
from unittest.mock import MagicMock

from mentora.agent_runtime.agents.orchestrator import Orchestrator
from mentora.agent_runtime.schemas.context import ContextAllocation
from mentora.agent_runtime.schemas.output import AgentOutput
from mentora.agent_runtime.schemas.task import OrchestratorTask
from mentora.model_gateway.schemas import Message


class _MaxRoundsAgent:
    role = "tutor"
    system_prompt_ref = "tutor"

    async def run_stream(self, agent_input, emitter=None):
        if emitter:
            emitter.agent_response_stream(agent_input.task_id, "partial", is_final=False)
        return AgentOutput(
            agent_role="tutor",
            task_id=agent_input.task_id,
            final_message="",
            finish_reason="max_rounds",
        )


class OrchestratorStreamTests(SimpleTestCase):
    def test_emits_max_rounds_status_before_done(self):
        context_mgr = MagicMock()
        context_mgr.build_messages.return_value = (
            [Message(role="user", content="hello")],
            ContextAllocation(),
        )
        prompt_mgr = MagicMock()
        prompt_mgr.render.return_value = "system prompt"

        orchestrator = Orchestrator(
            agent_map={"tutor": _MaxRoundsAgent()},
            prompt_manager=prompt_mgr,
            context_manager=context_mgr,
        )
        task = OrchestratorTask(
            id="task-1",
            agent_role="tutor",
            user_message="hello",
        )

        async def collect_events():
            events = []
            async for chunk in orchestrator.run_stream(task):
                if chunk.startswith("data: "):
                    events.append(json.loads(chunk[6:].strip()))
            return events

        events = asyncio.run(collect_events())

        self.assertEqual(events[0], {"type": "chunk", "content": "partial"})
        self.assertEqual(events[-1], {"type": "done"})
        self.assertTrue(any(event.get("event") == "agent.max_rounds" for event in events))
