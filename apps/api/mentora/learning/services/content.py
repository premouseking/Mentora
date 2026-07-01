"""
任务内容生成服务——调用 ContentAgent 为 LearningTask 生成 content_blocks。

约定：
- 懒生成：首次请求时检测 content_json 为空则生成
- 通过 gateway 调 ContentAgent 提示词 + 结构化输出
- 结果写入 task.content_json

@module mentora/learning/services/content
"""

import asyncio
import logging

from django.conf import settings

from mentora.courses.schemas import TaskContentOutput
from mentora.model_gateway.schemas import Message

logger = logging.getLogger(__name__)


def generate_task_content(task_id: str) -> bool:
    """为指定任务生成内容块，写入 task.content_json。

    返回 True 表示生成成功，False 表示跳过或失败。
    """
    from mentora.learning.models import LearningTask

    try:
        task = LearningTask.objects.select_related("unit__phase").get(id=task_id)
    except LearningTask.DoesNotExist:
        logger.warning("Task %s not found", task_id)
        return False

    # 已有内容则跳过
    content = task.content_json or {}
    if content.get("content_blocks"):
        return True

    # 检索相关证据
    evidence_context = _build_evidence_context(task.title)

    # 获取 gateway
    from mentora.agent_runtime.views import get_gateway, get_prompt_manager

    try:
        gateway = get_gateway()
        prompt_mgr = get_prompt_manager()
    except Exception as exc:
        logger.error("Gateway unavailable: %s", exc)
        return False

    if not settings.LLM_API_KEY:
        logger.warning("LLM_API_KEY not configured, skip content generation")
        return False

    try:
        system_text = prompt_mgr.render("content", {
            "task_title": task.title,
            "task_type": task.task_type,
            "phase_objective": (task.unit.phase.objective if task.unit and task.unit.phase else ""),
            "course_goal": "",
            "evidence_context": evidence_context,
        })

        messages = [
            Message(role="system", content=system_text),
            Message(role="user", content=f"请为任务「{task.title}」生成教学内容。"),
        ]

        resp = asyncio.run(
            gateway.chat(
                task_type="content",
                messages=messages,
                structured_output_schema=TaskContentOutput,
            )
        )
    except Exception:
        logger.exception("ContentAgent call failed for task %s", task_id)
        return False

    if resp.parsed_output is None:
        logger.warning("ContentAgent returned unparseable output for task %s", task_id)
        return False

    # 写入——兼容 dict 和 Pydantic 模型
    output = resp.parsed_output
    if isinstance(output, dict):
        blocks_raw = output.get("content_blocks", [])
        source_ids = output.get("source_evidence_ids", [])
    else:
        blocks_raw = [b.model_dump(exclude_none=True) for b in output.content_blocks]
        source_ids = output.source_evidence_ids

    existing_source_ids = content.get("source_evidence_ids") or []
    merged_source_ids = source_ids or existing_source_ids

    task.content_json = {
        "content_blocks": blocks_raw,
        "source_evidence_ids": merged_source_ids,
    }
    task.save(update_fields=["content_json"])

    logger.info("Content generated for task %s: %d blocks, %d sources",
                task_id, len(blocks_raw), len(source_ids))
    return True


def _build_evidence_context(query: str) -> str:
    """检索相关证据并格式化为提示词上下文。"""
    try:
        from mentora.retrieval.search import search
    except ImportError:
        return "（检索服务暂不可用）"

    try:
        results = search(query, top_k=5)
    except Exception as exc:
        logger.warning("Evidence retrieval failed: %s", exc)
        return "（检索失败）"

    if not results.results:
        return "（未找到相关资料）"

    lines = []
    for r in results.results:
        lines.append(
            f"[evidence_id: {r.evidence_id}] "
            f"来源: {r.source_title or '未知'}, "
            f"页码: {r.page_number or '—'}\n"
            f"内容: {r.content_preview or r.content or ''}"
        )
    return "\n\n".join(lines)
