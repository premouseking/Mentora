"""
评估领域服务：题目创建、测验会话管理、作答记录与判分。

约束：
- 判分逻辑简单对比 correct_answer（选择题），后续扩展评分量规
- 不在此模块引入 Agent 层依赖

@module mentora/assessment/services
"""

from django.db import transaction
from django.utils import timezone

from mentora.assessment.models import AssessmentAttempt, AssessmentItem, AssessmentSession


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
    status: str = AssessmentItem.Status.PUBLISHED,
) -> dict:
    """创建题目。"""
    item = AssessmentItem.objects.create(
        course_session_id=course_session_id,
        topic_id=topic_id or None,
        question_type=question_type,
        difficulty=difficulty,
        question_text=question_text,
        options_json=options_json,
        correct_answer=correct_answer,
        explanation=explanation,
        source_evidence_ids=source_evidence_ids or [],
        status=status,
    )
    return {
        "item_id": str(item.id),
        "question_type": item.question_type,
        "difficulty": item.difficulty,
        "status": item.status,
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

    item = attempt.item
    is_correct = user_answer.strip().lower() == item.correct_answer.strip().lower()
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
        items.append({
            "attempt_id": str(a.id),
            "item_id": str(a.item.id),
            "question_text": a.item.question_text,
            "question_type": a.item.question_type,
            "correct_answer": a.item.correct_answer,
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
