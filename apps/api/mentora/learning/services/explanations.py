"""
AI 讲解文档服务：归档、关键词匹配、CRUD。

约定：
- 文档存 LearningHistoryEvent，event_type=ai_explanation
- course_id 存 Course.id；查询时兼容 session_id
- 可变文档通过服务层更新 detail / metadata

@module mentora/learning/services/explanations
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from django.core.cache import cache
from django.db import transaction
from django.db.models import Q
from pydantic import BaseModel

from mentora.learning.models import LearningHistoryEvent
from mentora.learning.schemas import ExplanationSummaryOutput
from mentora.model_gateway.schemas import Message

PREVIEW_CACHE_PREFIX = "ai_explanation_preview:"
PREVIEW_TTL_SECONDS = 600

DOC_TYPES = {"解题思路", "知识点讲解", "错题分析", "公式推导"}


def _is_valid_uuid(value: str) -> bool:
    try:
        uuid.UUID(str(value))
        return True
    except (ValueError, AttributeError, TypeError):
        return False


def normalize_keywords(keywords: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for raw in keywords:
        word = raw.strip().lower()
        if not word or word in seen:
            continue
        seen.add(word)
        result.append(word)
    return result


def resolve_course_scope(resource_id: str) -> tuple[str, list[str]]:
    """解析课程上下文，返回存储用 canonical_id 与查询用 id 列表。"""
    from mentora.courses.services import resolve_course

    resolved = resolve_course(resource_id.strip())
    ids: set[str] = set()
    if resolved.course_id:
        ids.add(resolved.course_id)
        canonical = resolved.course_id
    else:
        canonical = resolved.session_id
    ids.add(resolved.session_id)
    return canonical, list(ids)


def _doc_queryset(course_ids: list[str]):
    return LearningHistoryEvent.objects.filter(
        course_id__in=course_ids,
        event_type=LearningHistoryEvent.EventType.AI_EXPLANATION,
    )


def _serialize_list_item(event: LearningHistoryEvent) -> dict:
    meta = event.metadata or {}
    keywords = meta.get("keywords") or []
    topic = keywords[0] if keywords else ""
    return {
        "id": str(event.id),
        "title": event.title,
        "topic": topic,
        "type": meta.get("doc_type") or "知识点讲解",
        "keywords": keywords,
        "created_at": event.created_at.isoformat(),
        "updated_at": (meta.get("updated_at") or event.updated_at.isoformat()),
    }


def _serialize_detail(event: LearningHistoryEvent) -> dict:
    meta = event.metadata or {}
    return {
        "id": str(event.id),
        "title": event.title,
        "detail": event.detail,
        "keywords": meta.get("keywords") or [],
        "doc_type": meta.get("doc_type") or "知识点讲解",
        "created_at": event.created_at.isoformat(),
        "updated_at": meta.get("updated_at") or event.updated_at.isoformat(),
        "append_count": meta.get("append_count") or 0,
    }


def list_explanation_docs(resource_id: str, *, limit: int = 50) -> list[dict]:
    _, course_ids = resolve_course_scope(resource_id)
    events = _doc_queryset(course_ids).order_by("-updated_at")[:limit]
    return [_serialize_list_item(e) for e in events]


def get_explanation_doc(doc_id: str, resource_id: str | None = None) -> dict | None:
    try:
        event = LearningHistoryEvent.objects.get(
            id=doc_id,
            event_type=LearningHistoryEvent.EventType.AI_EXPLANATION,
        )
    except LearningHistoryEvent.DoesNotExist:
        return None

    if resource_id:
        _, course_ids = resolve_course_scope(resource_id)
        if event.course_id not in course_ids:
            return None

    return _serialize_detail(event)


def match_doc_by_keywords(course_ids: list[str], keywords: list[str]) -> tuple[LearningHistoryEvent | None, int]:
    """按关键词重叠数匹配已有文档，返回 (文档, 重叠数)。"""
    normalized = normalize_keywords(keywords)
    if not normalized:
        return None, 0

    keyword_set = set(normalized)
    best: LearningHistoryEvent | None = None
    best_overlap = 0
    best_updated = ""

    for doc in _doc_queryset(course_ids):
        doc_keywords = set(normalize_keywords((doc.metadata or {}).get("keywords") or []))
        overlap = len(keyword_set & doc_keywords)
        if overlap <= 0:
            continue
        updated = (doc.metadata or {}).get("updated_at") or doc.updated_at.isoformat()
        if overlap > best_overlap or (overlap == best_overlap and updated > best_updated):
            best = doc
            best_overlap = overlap
            best_updated = updated

    return best, best_overlap


def _build_summary_prompt(
    *,
    user_message: str,
    assistant_message: str,
    citations: list[dict],
) -> list[Message]:
    citation_lines = []
    for c in citations[:8]:
        title = c.get("source_title") or ""
        preview = c.get("content_preview") or ""
        page = c.get("page_number")
        page_part = f" p.{page}" if page else ""
        if title or preview:
            citation_lines.append(f"- {title}{page_part}: {preview[:120]}")

    citations_block = "\n".join(citation_lines) if citation_lines else "（无引用）"

    system = (
        "你是学习笔记整理助手。根据一轮课程问答，输出结构化 JSON。\n"
        "要求：\n"
        "- keywords：3-8 个中文或英文关键词，小写，用于归档检索\n"
        "- summary_md：Markdown 总结，含要点列表；若有引用请在文末列出来源\n"
        "- suggested_title：若需新建文件，给简短标题（15 字内）\n"
        "- doc_type：从「解题思路」「知识点讲解」「错题分析」「公式推导」中选一项"
    )
    user = (
        f"用户问题：\n{user_message}\n\n"
        f"AI 回答：\n{assistant_message}\n\n"
        f"引用来源：\n{citations_block}"
    )
    return [
        Message(role="system", content=system),
        Message(role="user", content=user),
    ]


async def _call_summary_llm(
    user_message: str,
    assistant_message: str,
    citations: list[dict],
) -> ExplanationSummaryOutput:
    from mentora.agent_runtime.views import get_gateway

    gateway = get_gateway()
    resp = await gateway.chat(
        task_type="explanation_summarize",
        messages=_build_summary_prompt(
            user_message=user_message,
            assistant_message=assistant_message,
            citations=citations,
        ),
        structured_output_schema=ExplanationSummaryOutput,
    )
    if resp.parsed_output is None:
        raise ValueError("LLM 未返回有效摘要结构")
    raw = resp.parsed_output
    if isinstance(raw, BaseModel):
        return raw
    return ExplanationSummaryOutput.model_validate(raw)


def generate_preview(
    *,
    resource_id: str,
    user_message: str,
    assistant_message: str,
    citations: list[dict] | None = None,
) -> dict:
    """生成归档预览（调 LLM + 关键词匹配），结果缓存供 commit。"""
    import asyncio

    from django.conf import settings

    if not settings.LLM_API_KEY:
        raise RuntimeError("LLM_API_KEY 未配置")

    citations = citations or []
    canonical_id, course_ids = resolve_course_scope(resource_id)

    summary = asyncio.run(
        _call_summary_llm(user_message, assistant_message, citations),
    )
    keywords = normalize_keywords(summary.keywords)
    doc_type = summary.doc_type if summary.doc_type in DOC_TYPES else "知识点讲解"

    target_doc, overlap = match_doc_by_keywords(course_ids, keywords)
    action = "append" if target_doc else "create"

    preview_id = uuid.uuid4().hex
    payload = {
        "preview_id": preview_id,
        "canonical_course_id": canonical_id,
        "course_ids": course_ids,
        "action": action,
        "target_doc_id": str(target_doc.id) if target_doc else None,
        "target_title": target_doc.title if target_doc else summary.suggested_title.strip(),
        "keywords": keywords,
        "overlap_count": overlap,
        "summary_md": summary.summary_md.strip(),
        "doc_type": doc_type,
        "new_title": summary.suggested_title.strip() or "AI 讲解",
    }
    cache.set(f"{PREVIEW_CACHE_PREFIX}{preview_id}", payload, PREVIEW_TTL_SECONDS)
    return {
        "preview_id": preview_id,
        "action": action,
        "target_doc_id": payload["target_doc_id"],
        "target_title": payload["target_title"],
        "keywords": keywords,
        "overlap_count": overlap,
        "summary_md": payload["summary_md"],
        "doc_type": doc_type,
    }


def _append_block(summary_md: str) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return f"\n\n---\n\n### {now} 对话总结\n\n{summary_md}"


@transaction.atomic
def commit_preview(preview_id: str, resource_id: str) -> dict:
    """根据 preview_id 写入或追加讲解文档。"""
    cache_key = f"{PREVIEW_CACHE_PREFIX}{preview_id}"
    payload = cache.get(cache_key)
    if not payload:
        raise ValueError("预览已过期或不存在，请重新生成")

    _, course_ids = resolve_course_scope(resource_id)
    if not set(payload.get("course_ids") or []).intersection(course_ids):
        raise ValueError("课程上下文不匹配")

    canonical_id = payload["canonical_course_id"]
    summary_md = payload["summary_md"]
    keywords = normalize_keywords(payload.get("keywords") or [])
    doc_type = payload.get("doc_type") or "知识点讲解"
    now_iso = datetime.now(timezone.utc).isoformat()

    if payload["action"] == "append" and payload.get("target_doc_id"):
        doc = (
            LearningHistoryEvent.objects.select_for_update()
            .filter(
                id=payload["target_doc_id"],
                event_type=LearningHistoryEvent.EventType.AI_EXPLANATION,
                course_id__in=course_ids,
            )
            .first()
        )
        if doc is None:
            raise ValueError("目标讲解文件不存在")

        meta = dict(doc.metadata or {})
        merged_keywords = normalize_keywords((meta.get("keywords") or []) + keywords)
        meta["keywords"] = merged_keywords
        meta["doc_type"] = meta.get("doc_type") or doc_type
        meta["updated_at"] = now_iso
        meta["append_count"] = int(meta.get("append_count") or 0) + 1

        doc.detail = (doc.detail or "") + _append_block(summary_md)
        doc.metadata = meta
        doc.save(update_fields=["detail", "metadata", "updated_at"])
        cache.delete(cache_key)
        return {"doc_id": str(doc.id), "action": "append", "title": doc.title}

    title = (payload.get("new_title") or payload.get("target_title") or "AI 讲解").strip()[:512]
    doc = LearningHistoryEvent.objects.create(
        course_id=canonical_id,
        event_type=LearningHistoryEvent.EventType.AI_EXPLANATION,
        title=title,
        detail=summary_md,
        metadata={
            "keywords": keywords,
            "doc_type": doc_type,
            "updated_at": now_iso,
            "append_count": 1,
        },
    )
    cache.delete(cache_key)
    return {"doc_id": str(doc.id), "action": "create", "title": doc.title}


@transaction.atomic
def update_explanation_doc(
    doc_id: str,
    resource_id: str,
    *,
    title: str | None = None,
    detail: str | None = None,
    keywords: list[str] | None = None,
    doc_type: str | None = None,
) -> dict:
    _, course_ids = resolve_course_scope(resource_id)
    doc = (
        LearningHistoryEvent.objects.select_for_update()
        .filter(
            id=doc_id,
            event_type=LearningHistoryEvent.EventType.AI_EXPLANATION,
            course_id__in=course_ids,
        )
        .first()
    )
    if doc is None:
        raise ValueError("讲解文件不存在")

    meta = dict(doc.metadata or {})
    if title is not None:
        doc.title = title.strip()[:512]
    if detail is not None:
        doc.detail = detail
    if keywords is not None:
        meta["keywords"] = normalize_keywords(keywords)
    if doc_type is not None and doc_type in DOC_TYPES:
        meta["doc_type"] = doc_type
    meta["updated_at"] = datetime.now(timezone.utc).isoformat()
    doc.metadata = meta
    doc.save()
    return _serialize_detail(doc)


def delete_explanation_doc(doc_id: str, resource_id: str) -> None:
    _, course_ids = resolve_course_scope(resource_id)
    deleted, _ = LearningHistoryEvent.objects.filter(
        id=doc_id,
        event_type=LearningHistoryEvent.EventType.AI_EXPLANATION,
        course_id__in=course_ids,
    ).delete()
    if deleted == 0:
        raise ValueError("讲解文件不存在")
