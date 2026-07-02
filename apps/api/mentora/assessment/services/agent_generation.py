"""
AssessorAgent 驱动的测验生成服务。

约定：
- HTTP 层默认走 fast path；mode=agent 时走本模块
- 工具执行后从 tool_calls_made 提取 session_id

@module mentora/assessment/services/agent_generation
"""

from __future__ import annotations

import logging
import time
import uuid

from mentora.agent_runtime.runtime import build_orchestrator
from mentora.agent_runtime.schemas.output import AgentOutput
from mentora.agent_runtime.schemas.task import OrchestratorTask
from mentora.assessment.services.quiz_generation import QuizGenerationError

logger = logging.getLogger(__name__)


def extract_generate_item_session_id(output: AgentOutput) -> str | None:
    """从 AssessorAgent 输出中提取 generate_item 返回的 session_id。"""
    for record in output.tool_calls_made:
        if record.tool_name != "generate_item" or not record.success:
            continue
        if record.result and record.result.get("session_id"):
            return str(record.result["session_id"])
    return None


def classify_agent_failure(output: AgentOutput | None) -> QuizGenerationError:
    if output is None:
        return QuizGenerationError("AssessorAgent 执行失败", code="agent_failed")

    generate_calls = [
        r for r in output.tool_calls_made if r.tool_name == "generate_item"
    ]
    if not generate_calls:
        return QuizGenerationError(
            "模型未调用 generate_item 工具创建测验",
            code="tool_not_called",
        )

    last = generate_calls[-1]
    if last.error and "格式" in last.error:
        return QuizGenerationError(last.error, code="invalid_format")
    if last.error and "质量评估" in last.error:
        return QuizGenerationError(last.error, code="validation_rejected")

    skipped = (last.result or {}).get("skipped") if last.result else None
    if skipped:
        return QuizGenerationError(
            "题目未通过质量评估，请减少题量或更换资料后重试",
            code="validation_rejected",
        )
    return QuizGenerationError(
        last.error or "AssessorAgent 未成功调用 generate_item 创建测验",
        code="agent_failed",
    )


def build_assessor_generation_message(
    *,
    course_session_id: str,
    count: int,
    difficulty: str,
    source_version_ids: list[str],
    source_evidence_ids: list[str],
    evidence_units,
    source_titles: dict[str, str],
    unit_title: str = "",
) -> str:
    evidence_lines = []
    for idx, unit in enumerate(evidence_units, 1):
        title = source_titles.get(unit.source_version_id, unit.source_version_id)
        content = unit.content.strip().replace("\n", " ")
        evidence_lines.append(
            f"{idx}. evidence_id={unit.id} source={title} page={unit.page_number}\n{content}"
        )

    allowed_ids = [str(unit.id) for unit in evidence_units]
    return (
        f"请为课程会话 {course_session_id} 生成 {count} 道单选题，难度：{difficulty}。\n"
        f"学习单元：{unit_title or '综合练习'}\n"
        "要求：\n"
        "1. 只基于下方证据出题，不得编造资料外知识\n"
        "2. 每题 4 个选项，正确答案只能是 A/B/C/D\n"
        "3. 每题必须填写 source_evidence_ids，且只能使用下列 evidence_id\n"
        "4. 生成完成后必须调用 generate_item 工具一次，传入全部题目\n"
        f"5. generate_item 参数 course_session_id={course_session_id}\n\n"
        f"允许的 evidence_id：{', '.join(allowed_ids) or '无'}\n"
        f"资料版本 ID：{', '.join(source_version_ids) or '无'}\n"
        f"指定证据 ID：{', '.join(source_evidence_ids) or '无'}\n\n"
        "课程资料证据：\n" + "\n\n".join(evidence_lines)
    )


async def run_assessor_quiz_generation(
    *,
    course_session_id: str,
    count: int,
    difficulty: str,
    source_version_ids: list[str],
    source_evidence_ids: list[str],
    evidence_units,
    source_titles: dict[str, str],
    unit_id: str = "",
    unit_title: str = "",
    max_tool_rounds: int = 4,
) -> str:
    """运行 AssessorAgent 生成测验，返回 session_id。"""
    started = time.perf_counter()
    orch, _, _ = build_orchestrator()
    allowed_evidence_ids = [str(unit.id) for unit in evidence_units]
    fallback_evidence_ids = allowed_evidence_ids[:3]

    user_message = build_assessor_generation_message(
        course_session_id=course_session_id,
        count=count,
        difficulty=difficulty,
        source_version_ids=source_version_ids,
        source_evidence_ids=source_evidence_ids,
        evidence_units=evidence_units,
        source_titles=source_titles,
        unit_title=unit_title,
    )

    task = OrchestratorTask(
        id=f"quiz-gen-{uuid.uuid4()}",
        mode="single",
        agent_role="assessor",
        user_message=user_message,
        context_sources=source_version_ids,
        max_tool_rounds=max_tool_rounds,
        tool_metadata={
            "allowed_evidence_ids": allowed_evidence_ids,
            "fallback_evidence_ids": fallback_evidence_ids,
            "unit_id": unit_id,
            "evidence_context": "\n".join(
                f"{unit.id}: {unit.content[:300]}" for unit in evidence_units
            ),
        },
    )

    result = await orch.run(task)
    elapsed_ms = (time.perf_counter() - started) * 1000
    tool_calls = result.final_output.tool_calls_made if result.final_output else []
    generate_calls = [r for r in tool_calls if r.tool_name == "generate_item"]
    logger.info(
        "assessor quiz generation status=%s tool_rounds=%s generate_attempts=%s ms=%.0f",
        result.status,
        len(tool_calls),
        len(generate_calls),
        elapsed_ms,
    )

    if result.status != "completed" or not result.final_output:
        raise QuizGenerationError(
            result.error_message or "AssessorAgent 执行失败",
            code="agent_failed",
        )

    session_id = extract_generate_item_session_id(result.final_output)
    if not session_id:
        raise classify_agent_failure(result.final_output)

    return session_id


def run_assessor_quiz_generation_sync(**kwargs) -> str:
    """同步入口，供 Django 视图调用。"""
    import asyncio

    return asyncio.run(run_assessor_quiz_generation(**kwargs))
