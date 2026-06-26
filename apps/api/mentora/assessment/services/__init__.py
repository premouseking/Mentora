"""
评估领域服务：题目创建、测验会话管理、作答记录与判分。

约束：
- 判分逻辑简单对比 correct_answer（选择题），后续扩展评分量规
- 不在此模块引入 Agent 层依赖

@module mentora/assessment/services
"""

from django.db import transaction
from django.utils import timezone

from mentora.assessment.models import (
    AssessmentAttempt,
    AssessmentItem,
    AssessmentItemRevision,
    AssessmentSession,
)


@transaction.atomic
def create_item(
    course_session_id: str,
    question_type: str,
    question_text: str,
    correct_answer: str,
    *,
    topic_id: str = "",
    difficulty: int = 3,
    options_json: list | None = None,
    explanation: str = "",
    source_evidence_ids: list | None = None,
    status: str = "draft",
    source_type: str = "user",
    created_by: str = "",
    model_request_id: str = "",
) -> dict:
    """创建题目 + 首版修订 + 溯源记录。"""
    item = AssessmentItem.objects.create(
        course_session_id=course_session_id,
        topic_id=topic_id or None,
        question_type=question_type,
        difficulty=difficulty,
    )

    from mentora.assessment.models import ItemProvenance
    ItemProvenance.objects.create(
        item=item,
        source_type=source_type,
        created_by=created_by,
        model_request_id=model_request_id,
    )

    revision = AssessmentItemRevision.objects.create(
        item=item,
        version_number=1,
        question_text=question_text,
        options_json=options_json,
        correct_answer=correct_answer,
        explanation=explanation,
        source_evidence_ids=source_evidence_ids or [],
        status=status,
    )
    item.current_revision_id = revision.id
    item.save(update_fields=["current_revision_id"])
    return {
        "item_id": str(item.id),
        "revision_id": str(revision.id),
        "version_number": 1,
        "question_type": item.question_type,
        "difficulty": item.difficulty,
        "status": revision.status,
    }


@transaction.atomic
def revise_item(item_id: str, **kwargs) -> dict:
    """克隆当前修订 → 新版本 → 更新 current_revision_id。"""
    item = AssessmentItem.objects.get(id=item_id)
    old = AssessmentItemRevision.objects.get(id=item.current_revision_id)

    new = AssessmentItemRevision.objects.create(
        item=item,
        parent_revision_id=old.id,
        version_number=old.version_number + 1,
        question_text=kwargs.get("question_text", old.question_text),
        options_json=kwargs.get("options_json", old.options_json),
        correct_answer=kwargs.get("correct_answer", old.correct_answer),
        explanation=kwargs.get("explanation", old.explanation),
        source_evidence_ids=kwargs.get("source_evidence_ids", old.source_evidence_ids),
        status=kwargs.get("status", AssessmentItemRevision.Status.PUBLISHED),
    )

    item.current_revision_id = new.id
    item.save(update_fields=["current_revision_id"])

    return {
        "item_id": str(item.id),
        "revision_id": str(new.id),
        "version_number": new.version_number,
        "previous_revision_id": str(old.id),
        "status": new.status,
    }


@transaction.atomic
def create_session(
    course_session_id: str,
    item_ids: list[str],
    *,
    unit_id: str = "",
) -> dict:
    """创建测验会话并关联题目。"""
    items = list(AssessmentItem.objects.filter(id__in=item_ids))
    if not items:
        raise ValueError("题目列表不能为空")

    session = AssessmentSession.objects.create(
        course_session_id=course_session_id,
        unit_id=unit_id or None,
        status=AssessmentSession.Status.CREATED,
        total_items=len(items),
    )

    for pos, item in enumerate(items):
        AssessmentAttempt.objects.create(
            session=session,
            item=item,
            position=pos,
        )

    return {
        "session_id": str(session.id),
        "item_count": len(items),
        "status": session.status,
    }


@transaction.atomic
def submit_attempt(
    session_id: str,
    item_id: str,
    user_answer: str,
    *,
    duration_seconds: int | None = None,
) -> dict:
    """记录单题作答并判分。"""
    attempt = AssessmentAttempt.objects.get(
        session_id=session_id,
        item_id=item_id,
    )

    revision = AssessmentItemRevision.objects.get(
        id=attempt.item.current_revision_id,
    )
    is_correct = user_answer.strip().lower() == revision.correct_answer.strip().lower()
    score = 1.0 if is_correct else 0.0

    attempt.user_answer = user_answer
    attempt.is_correct = is_correct
    attempt.score = score
    attempt.duration_seconds = duration_seconds
    attempt.save(update_fields=["user_answer", "is_correct", "score", "duration_seconds"])

    # 首次作答时将会话状态切换到进行中
    session = attempt.session
    if session.status == AssessmentSession.Status.CREATED:
        session.status = AssessmentSession.Status.IN_PROGRESS
        session.started_at = timezone.now()
        session.save(update_fields=["status", "started_at"])

    return {
        "attempt_id": str(attempt.id),
        "is_correct": is_correct,
        "score": score,
    }


@transaction.atomic
def complete_session(session_id: str) -> dict:
    """结束测验会话，汇总结果。"""
    session = AssessmentSession.objects.get(id=session_id)
    attempts = session.attempts.all()

    correct_count = sum(1 for a in attempts if a.is_correct)
    total = attempts.count()

    session.correct_count = correct_count
    session.score_pct = round(correct_count / max(total, 1) * 100)
    session.status = AssessmentSession.Status.COMPLETED
    session.completed_at = timezone.now()
    session.save(update_fields=["correct_count", "score_pct", "status", "completed_at"])

    return {
        "session_id": str(session.id),
        "total_items": total,
        "correct_count": correct_count,
        "score_pct": session.score_pct,
        "status": session.status,
    }


def get_session_result(session_id: str) -> dict | None:
    """获取测验会话完整结果（含每题作答详情）。"""
    try:
        session = AssessmentSession.objects.get(id=session_id)
    except AssessmentSession.DoesNotExist:
        return None

    attempts = session.attempts.select_related("item").order_by("position")
    items = []
    for a in attempts:
        rev = AssessmentItemRevision.objects.filter(
            id=a.item.current_revision_id,
        ).first()
        items.append({
            "attempt_id": str(a.id),
            "item_id": str(a.item.id),
            "question_text": rev.question_text if rev else "",
            "question_type": a.item.question_type,
            "correct_answer": rev.correct_answer if rev else "",
            "user_answer": a.user_answer,
            "is_correct": a.is_correct,
            "score": a.score,
            "duration_seconds": a.duration_seconds,
        })

    return {
        "session_id": str(session.id),
        "course_session_id": str(session.course_session_id),
        "unit_id": str(session.unit_id) if session.unit_id else None,
        "status": session.status,
        "total_items": session.total_items,
        "correct_count": session.correct_count,
        "score_pct": session.score_pct,
        "items": items,
    }


def flag_item(item_id: str, issue: str, *, student_note: str = "") -> dict:
    """学生对题目标记反馈。≥2 个未解决 flag 触发自动修正。"""
    from mentora.assessment.models import FlaggedItem

    FlaggedItem.objects.create(
        item_id=item_id,
        issue=issue,
        student_note=student_note,
    )

    unresolved = FlaggedItem.objects.filter(
        item_id=item_id, resolved=False,
    ).count()

    result = {"item_id": item_id, "unresolved_flags": unresolved}

    if unresolved >= 2:
        from mentora.assessment.models import AssessmentItem
        item = AssessmentItem.objects.get(id=item_id)
        old_rev = AssessmentItemRevision.objects.get(id=item.current_revision_id)

        new_rev_result = revise_item(item_id)
        new_rev = AssessmentItemRevision.objects.get(id=new_rev_result["revision_id"])

        val_result = validate_item(new_rev_result["revision_id"])
        result["auto_revised"] = True
        result["revision_id"] = new_rev_result["revision_id"]
        result["validation"] = val_result

        FlaggedItem.objects.filter(item_id=item_id, resolved=False).update(
            resolved=True,
            resolved_by_revision_id=new_rev.id,
        )

    return result


def get_latest_session_for_unit(unit_id: str) -> dict | None:
    """获取指定学习单元的最近一次完成测验结果，供 learning 模块调用。"""
    from mentora.assessment.models import AssessmentSession

    session = AssessmentSession.objects.filter(
        unit_id=unit_id,
        status=AssessmentSession.Status.COMPLETED,
    ).order_by("-completed_at").first()

    if session is None:
        return None

    return {
        "session_id": str(session.id),
        "score_pct": session.score_pct,
        "correct_count": session.correct_count,
        "total_items": session.total_items,
        "completed_at": session.completed_at.isoformat() if session.completed_at else None,
    }


def validate_item(revision_id: str) -> dict:
    """
    AI 自检：三要素校验。

    1. 选项互斥（无语义重叠）
    2. 答案唯一（单选题只有 1 个正确选项）
    3. 资料依据（答案能在 source_evidence_ids 中找到原文支撑）

    通过 → status=published；不通过 → 写入 validation_issues。
    """
    revision = AssessmentItemRevision.objects.select_related("item").get(id=revision_id)
    item = revision.item

    # 收集资料原文
    evidence_texts: list[str] = []
    if revision.source_evidence_ids:
        from mentora.retrieval.models import EvidenceUnit
        units = EvidenceUnit.objects.filter(
            id__in=revision.source_evidence_ids,
        )
        evidence_texts = [u.content for u in units]

    # 构建 LLM 校验请求
    options_str = ""
    if revision.options_json:
        options_str = "\n".join(
            f"{o.get('label', '')}: {o.get('text', '')}"
            for o in revision.options_json
        )

    prompt_parts = [
        f"题干：{revision.question_text}",
        f"题型：{item.get_question_type_display()}",
    ]
    if options_str:
        prompt_parts.append(f"选项：\n{options_str}")
    prompt_parts.append(f"答案：{revision.correct_answer}")
    if evidence_texts:
        prompt_parts.append(f"资料原文：\n{' '.join(evidence_texts[:3])}")

    check_rules = (
        "请逐项检查：\n"
        "1. 选项互斥——选择题选项中不存在语义重叠\n"
        "2. 答案唯一——单选题有且仅有一个正确选项\n"
        "3. 资料依据——正确答案能从资料原文中找到支撑\n\n"
        "如果资料原文为空，只检查第 1、2 项。"
    )

    try:
        from mentora.model_gateway.gateway import ModelGateway
        from mentora.agent_runtime.views import get_gateway
        from mentora.model_gateway.schemas import Message

        gateway = get_gateway()
        messages = [
            Message(role="system", content="你是题目质量审核员。" + check_rules),
            Message(role="user", content="\n\n".join(prompt_parts)),
        ]
        resp = gateway.chat_sync(
            task_type="assessor",
            messages=messages,
            structured_output_schema=None,
        )
        content = (resp.content or "").lower()
        valid = "通过" in content or "valid" in content or "yes" in content
    except Exception:
        # LLM 不可用时跳过校验，标记为手动确认
        return {
            "revision_id": revision_id,
            "valid": False,
            "issues": ["AI 自检不可用，需手动确认"],
        }

    issues = []
    if not valid:
        issues.append("AI 自检未通过，请人工审核题目内容")
        revision.status = AssessmentItemRevision.Status.DRAFT
        revision.validation_issues = issues
        revision.save(update_fields=["status", "validation_issues"])
    else:
        revision.status = AssessmentItemRevision.Status.PUBLISHED
        revision.validation_issues = []
        revision.save(update_fields=["status", "validation_issues"])

    return {
        "revision_id": revision_id,
        "valid": valid,
        "issues": issues,
        "status": revision.status,
    }


@transaction.atomic
def publish_item(item_id: str) -> dict:
    """手动发布题目的当前修订版本。"""
    item = AssessmentItem.objects.get(id=item_id)
    revision = AssessmentItemRevision.objects.get(id=item.current_revision_id)

    if revision.status == AssessmentItemRevision.Status.PUBLISHED:
        return {"item_id": item_id, "status": "published", "message": "已发布"}

    revision.status = AssessmentItemRevision.Status.PUBLISHED
    revision.validation_issues = []
    revision.save(update_fields=["status", "validation_issues"])
    return {"item_id": item_id, "revision_id": str(revision.id), "status": "published"}
