"""
出题后台任务与任务编排。

@module mentora/assessment/services/quiz_generation_jobs
"""

from __future__ import annotations

import logging
from typing import Any

from django.utils import timezone

from mentora.assessment.models import QuizGenerationJob
from mentora.assessment.services.quiz_generation import (
    QuizGenerationError,
    QuizGenerationRequest,
    build_generation_cache_key,
    run_quiz_generation_fast_sync,
)

logger = logging.getLogger(__name__)


def _job_to_dict(job: QuizGenerationJob) -> dict[str, Any]:
    return {
        "job_id": str(job.id),
        "status": job.status,
        "progress": job.progress,
        "progress_pct": job.progress_pct,
        "error": job.error_message or None,
        "error_code": job.error_code or None,
        "session_id": str(job.result_session_id) if job.result_session_id else None,
        "created_at": job.created_at.isoformat(),
        "updated_at": job.updated_at.isoformat(),
    }


def create_generation_job(req: QuizGenerationRequest) -> QuizGenerationJob:
    cache_key = build_generation_cache_key(req)
    return QuizGenerationJob.objects.create(
        status=QuizGenerationJob.Status.PENDING,
        progress="等待开始",
        progress_pct=0,
        generation_cache_key=cache_key,
        request_payload={
            "course_session_id": req.course_session_id,
            "count": req.count,
            "difficulty": req.difficulty,
            "source_version_ids": req.source_version_ids,
            "source_evidence_ids": req.source_evidence_ids,
            "unit_id": req.unit_id,
            "unit_title": req.unit_title,
            "task_id": req.task_id,
            "mode": req.mode,
        },
    )


def get_generation_job(job_id: str) -> dict[str, Any] | None:
    job = QuizGenerationJob.objects.filter(id=job_id).first()
    if job is None:
        return None
    return _job_to_dict(job)


def _update_job(job_id: str, **fields) -> None:
    fields["updated_at"] = timezone.now()
    QuizGenerationJob.objects.filter(id=job_id).update(**fields)


def run_generation_job_sync(job_id: str, req: QuizGenerationRequest) -> str:
    """同步执行出题任务（Celery worker 或 dev 回退）。"""
    _update_job(
        job_id,
        status=QuizGenerationJob.Status.RUNNING,
        progress="正在生成题目",
        progress_pct=20,
    )
    try:
        if req.mode == "agent":
            from mentora.assessment.services.agent_generation import run_assessor_quiz_generation_sync

            _update_job(job_id, progress="Agent 正在出题", progress_pct=40)
            session_id = run_assessor_quiz_generation_sync(
                course_session_id=req.course_session_id,
                count=req.count,
                difficulty=req.difficulty,
                source_version_ids=req.source_version_ids,
                source_evidence_ids=req.source_evidence_ids,
                evidence_units=req.evidence_units,
                source_titles=req.source_titles,
                unit_id=req.unit_id,
                unit_title=req.unit_title,
            )
        else:
            _update_job(job_id, progress="正在调用模型生成", progress_pct=40)
            session_id, _metrics = run_quiz_generation_fast_sync(req)

        _update_job(
            job_id,
            status=QuizGenerationJob.Status.SUCCEEDED,
            progress="生成完成",
            progress_pct=100,
            result_session_id=session_id,
            error_message="",
            error_code="",
        )
        return session_id
    except QuizGenerationError as exc:
        _update_job(
            job_id,
            status=QuizGenerationJob.Status.FAILED,
            progress="生成失败",
            progress_pct=100,
            error_message=str(exc),
            error_code=exc.code,
        )
        raise
    except Exception as exc:
        logger.exception("generation job failed job_id=%s", job_id)
        _update_job(
            job_id,
            status=QuizGenerationJob.Status.FAILED,
            progress="生成失败",
            progress_pct=100,
            error_message=str(exc),
            error_code="generation_failed",
        )
        raise


def enqueue_generation_job(job_id: str, req: QuizGenerationRequest) -> None:
    try:
        from mentora.assessment.tasks import run_quiz_generation_job

        run_quiz_generation_job.delay(str(job_id))
    except Exception:
        logger.warning("Celery 不可用，同步回退执行 job_id=%s", job_id)
        run_generation_job_sync(str(job_id), req)
