"""
错题汇总服务：统计作答错误的题目，聚合频次与来源信息。

约定：
- 查询 AssessmentAttempt（is_correct=False），按 item 分组
- 关联 AssessmentItemRevision（题干/答案/解析）+ Topic（知识点名称）
- error_reason 预留入口，后续由 AI 分析填充

@module mentora/learning/services/mistakes
"""


from django.db.models import Count, Max

from mentora.assessment.models import (
    AssessmentAttempt,
    AssessmentItem,
    AssessmentItemRevision,
)
from mentora.courses.models import Course


def get_mistake_items(course_id: str, *, include_archived: bool = False) -> list[dict]:
    """统计指定课程中的错题，返回聚合后的错题列表。

    返回字段对齐前端 MistakeItem：
    - item_id, title, topic, difficulty, wrong_count, last_wrong
    - question, options, correct_answer, explanation
    - error_reason, knowledge_points, source_links
    """
    # 解析课程 → 获取 course_session_id
    try:
        course = Course.objects.only("session_id").get(id=course_id)
    except Course.DoesNotExist:
        return []

    session_id = str(course.session_id)

    archived_item_ids: set[str] = set()
    if not include_archived:
        from mentora.learning.models import MistakeArchive

        archived_item_ids = {
            str(row.item_id)
            for row in MistakeArchive.objects.filter(course_id=course_id).only("item_id")
        }

    # 该课程下所有错误的作答记录，按 item 分组
    wrong_attempts = (
        AssessmentAttempt.objects
        .filter(is_correct=False, session__course_session_id=session_id)
        .values("item_id")
        .annotate(wrong_count=Count("id"), last_wrong=Max("created_at"))
        .order_by("-last_wrong")
    )

    if not wrong_attempts:
        return []

    item_ids = [a["item_id"] for a in wrong_attempts]
    attempt_map = {a["item_id"]: a for a in wrong_attempts}

    # 题目基础信息
    items = AssessmentItem.objects.in_bulk(item_ids)

    # 题目内容修订（当前版本）
    revisions = {
        r.item_id: r
        for r in AssessmentItemRevision.objects.filter(
            item_id__in=item_ids,
            id__in=items.values_list("current_revision_id", flat=True),
        )
    }

    # 关联的知识主题
    topic_ids = [str(i.topic_id) for i in items.values() if i.topic_id]
    topic_map: dict[str, str] = {}
    if topic_ids:
        from mentora.topics.models import Topic
        for t in Topic.objects.filter(id__in=topic_ids).only("id", "name"):
            topic_map[str(t.id)] = t.name

    # 难度映射
    def _difficulty_label(level: int) -> str:
        if level <= 2:
            return "简单"
        if level <= 4:
            return "中等"
        return "困难"

    result = []
    for item_id, agg in attempt_map.items():
        if str(item_id) in archived_item_ids:
            continue
        item = items.get(item_id)
        if not item:
            continue

        revision = revisions.get(item_id)
        options = (revision.options_json if revision else None) or []
        explanation = revision.explanation if revision else ""
        question_text = revision.question_text if revision else ""
        correct_answer = revision.correct_answer if revision else ""

        # 获取知识点名称
        topic_name = topic_map.get(str(item.topic_id), "") if item.topic_id else ""

        # 来源链接：从 source_evidence_ids 获取
        source_links: list[dict] = []
        evidence_ids = revision.source_evidence_ids if revision else []
        if evidence_ids:
            from mentora.retrieval.models import EvidenceUnit
            sources = EvidenceUnit.objects.filter(id__in=evidence_ids).only(
                "id", "source_title", "page_number",
            )
            for src in sources:
                source_links.append({
                    "title": src.source_title or "",
                    "location": f"第 {src.page_number} 页" if src.page_number else "",
                    "excerpt": "",
                })

        result.append({
            "item_id": str(item_id),
            "title": question_text[:40] + "…" if len(question_text) > 40 else question_text,
            "topic": topic_name,
            "difficulty": _difficulty_label(item.difficulty),
            "wrong_count": agg["wrong_count"],
            "last_wrong": agg["last_wrong"].strftime("%Y-%m-%d") if agg["last_wrong"] else "",
            "question": question_text,
            "options": options,
            "correct_answer": correct_answer,
            "explanation": explanation,
            "error_reason": "",  # 预留：后续 AI 分析错因
            "knowledge_points": [topic_name] if topic_name else [],
            "source_links": source_links,
        })

    return result


def archive_mistake(course_id: str, item_id: str, *, owner) -> dict:
    """归档单道错题，后续默认列表不再展示。"""
    from mentora.learning.models import MistakeArchive

    record, _ = MistakeArchive.objects.get_or_create(
        course_id=course_id,
        item_id=item_id,
        owner=owner,
    )
    return {
        "course_id": course_id,
        "item_id": str(item_id),
        "archived_at": record.archived_at.isoformat(),
    }


def unarchive_mistake(course_id: str, item_id: str, *, owner) -> dict:
    from mentora.learning.models import MistakeArchive

    deleted, _ = MistakeArchive.objects.filter(
        course_id=course_id, item_id=item_id, owner=owner,
    ).delete()
    if not deleted:
        return {"course_id": course_id, "item_id": str(item_id), "status": "not_archived"}
    return {"course_id": course_id, "item_id": str(item_id), "status": "active"}


def get_explanations(course_id: str) -> list[dict]:
    """获取课程中已完成的讲解类学习记录。

    从 task_completed 事件中过滤 AI 讲解记录，返回前端 aiExplanations 数据。
    """
    from mentora.learning.models import LearningHistoryEvent

    events = LearningHistoryEvent.objects.filter(
        course_id=course_id,
        event_type="task_completed",
    ).order_by("-created_at")[:20]

    items = []
    for e in events:
        items.append({
            "id": str(e.id),
            "title": e.title,
            "topic": e.detail[:30] if e.detail else "",
            "type": e.result or "知识点讲解",
            "created_at": e.created_at.isoformat(),
        })

    return items
