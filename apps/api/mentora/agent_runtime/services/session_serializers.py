"""
课程 Agent 会话序列化辅助。

约定：
- 列表接口返回摘要，详情接口含完整消息
- citations / metadata 保持 JSON 原样输出

@module mentora/agent_runtime/services/session_serializers
"""

from __future__ import annotations

from mentora.agent_runtime.models import CourseAgentMessage, CourseAgentSession


def serialize_course_agent_message(message: CourseAgentMessage) -> dict:
    """单条消息序列化。"""
    return {
        "id": str(message.id),
        "role": message.role,
        "content": message.content,
        "citations": message.citations_json or [],
        "metadata": message.metadata_json or {},
        "created_at": message.created_at.isoformat() if message.created_at else None,
    }


def serialize_course_agent_session_summary(session: CourseAgentSession) -> dict:
    """会话列表项序列化。"""
    last_message = session.messages.order_by("-created_at").first()
    return {
        "id": str(session.id),
        "course_id": str(session.course_id),
        "course_session_id": str(session.course_session_id),
        "title": session.title or "新对话",
        "status": session.status,
        "message_count": session.messages.count(),
        "last_message_preview": (
            (last_message.content[:120] + "…")
            if last_message and len(last_message.content) > 120
            else (last_message.content if last_message else "")
        ),
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "updated_at": session.updated_at.isoformat() if session.updated_at else None,
    }


def serialize_course_agent_session_detail(session: CourseAgentSession) -> dict:
    """会话详情（含消息历史）。"""
    summary = serialize_course_agent_session_summary(session)
    summary["messages"] = [
        serialize_course_agent_message(msg)
        for msg in session.messages.order_by("created_at")
    ]
    return summary
