"""
课程 Agent 对话意图门控：决定是否暴露检索/进度工具。

约定：
- 寒暄、感谢、简短续聊不触发 retrieve_evidence
- 课程知识、资料解释、显式 @ 资料时才允许检索
- 进度/任务类问题优先使用 get_learning_progress，不默认全文检索

@module mentora/agent_runtime/services/course_intent
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum


class CourseChatIntent(StrEnum):
    SMALLTALK = "smalltalk"
    COURSE_QA = "course_qa"
    PROGRESS = "progress"
    READER_CONTEXT = "reader_context"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ToolAccess:
    chat_intent: CourseChatIntent
    allow_retrieval: bool
    allow_progress: bool
    reason: str


_SMALLTALK_EXACT = frozenset({
    "你好",
    "您好",
    "hello",
    "hi",
    "hey",
    "谢谢",
    "感谢",
    "多谢",
    "好的",
    "ok",
    "okay",
    "嗯",
    "嗯嗯",
    "哦",
    "啊",
    "继续",
    "在吗",
    "在不在",
})

_SMALLTALK_PREFIX = re.compile(
    r"^(你好|您好|hi|hello|hey|谢谢|感谢|好的|ok)[\s!！。?？~～]*$",
    re.IGNORECASE,
)

_COURSE_QA_PATTERN = re.compile(
    r"(什么是|是什么|什么叫|定义|解释|说明|总结|概括|归纳|为什么|为何|如何|怎么|怎样|"
    r"资料|课件|原文|这页|这段|本章|本节|页码|引用|根据|帮我看|帮我解释|"
    r"操作系统|概念|原理|公式|定理|例题|知识点|内容是什么)",
    re.IGNORECASE,
)

_PROGRESS_PATTERN = re.compile(
    r"(进度|下一步|接下来|学什么|任务安排|学习计划|当前任务|还有多少|完成度|"
    r"学到哪|安排|规划)",
    re.IGNORECASE,
)

_READER_CONTEXT_PATTERN = re.compile(
    r"(这页|这段|当前页|当前资料|打开的资料|阅读器|高亮|选中的|划线的|"
    r"这里说的|上面这段|这一页)",
    re.IGNORECASE,
)


def _normalize(message: str) -> str:
    text = (message or "").strip()
    if text.startswith("[课程上下文]"):
        parts = text.split("[/课程上下文]", 1)
        if len(parts) == 2:
            text = parts[1].strip()
    return re.sub(r"\s+", " ", text)


def _has_course_file_mentions(mentions: list | None) -> bool:
    if not isinstance(mentions, list):
        return False
    for item in mentions:
        if isinstance(item, dict) and str(item.get("type") or "") == "course_file":
            return True
    return False


def _is_smalltalk(message: str) -> bool:
    text = _normalize(message)
    lower = text.lower()
    if not text:
        return True
    if lower in _SMALLTALK_EXACT or text in _SMALLTALK_EXACT:
        return True
    if _SMALLTALK_PREFIX.match(text):
        return True
    if len(text) <= 4 and not _COURSE_QA_PATTERN.search(text):
        return True
    return False


def _matches_course_qa(message: str) -> bool:
    return bool(_COURSE_QA_PATTERN.search(_normalize(message)))


def _matches_progress(message: str) -> bool:
    return bool(_PROGRESS_PATTERN.search(_normalize(message)))


def _matches_reader_context(message: str) -> bool:
    return bool(_READER_CONTEXT_PATTERN.search(_normalize(message)))


def classify_course_chat_intent(
    message: str,
    *,
    mentions: list | None = None,
    current_source_version_id: str | None = None,
    current_task_id: str | None = None,
) -> ToolAccess:
    """根据用户消息与上下文判定工具可见性。"""
    if _has_course_file_mentions(mentions):
        return ToolAccess(
            chat_intent=CourseChatIntent.COURSE_QA,
            allow_retrieval=True,
            allow_progress=True,
            reason="用户显式 @ 课程资料",
        )

    if current_task_id and _matches_course_qa(message):
        return ToolAccess(
            chat_intent=CourseChatIntent.COURSE_QA,
            allow_retrieval=True,
            allow_progress=True,
            reason="当前任务相关的资料问题",
        )

    if _is_smalltalk(message):
        return ToolAccess(
            chat_intent=CourseChatIntent.SMALLTALK,
            allow_retrieval=False,
            allow_progress=True,
            reason="寒暄或简短会话输入，无需检索资料",
        )

    if _matches_progress(message) and not _matches_course_qa(message):
        return ToolAccess(
            chat_intent=CourseChatIntent.PROGRESS,
            allow_retrieval=False,
            allow_progress=True,
            reason="学习进度或任务安排问题",
        )

    if _matches_course_qa(message):
        return ToolAccess(
            chat_intent=CourseChatIntent.COURSE_QA,
            allow_retrieval=True,
            allow_progress=True,
            reason="课程知识或资料解释问题",
        )

    if current_source_version_id and _matches_reader_context(message):
        return ToolAccess(
            chat_intent=CourseChatIntent.READER_CONTEXT,
            allow_retrieval=True,
            allow_progress=True,
            reason="阅读器当前资料相关内容",
        )

    return ToolAccess(
        chat_intent=CourseChatIntent.UNKNOWN,
        allow_retrieval=False,
        allow_progress=True,
        reason="未识别为需要检索资料的场景",
    )
