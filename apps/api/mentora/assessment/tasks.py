"""Assessment Celery 任务。"""

from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="mentora.assessment.tasks.run_quiz_generation_job")
def run_quiz_generation_job(job_id: str) -> None:
    from mentora.assessment.models import QuizGenerationJob
    from mentora.assessment.services.quiz_generation import QuizGenerationRequest
    from mentora.assessment.services.quiz_generation_jobs import run_generation_job_sync
    from mentora.assessment.services.quiz_evidence import get_scoped_evidence, get_source_titles

    job = QuizGenerationJob.objects.get(id=job_id)
    payload = job.request_payload or {}
    source_version_ids = [str(v) for v in payload.get("source_version_ids") or []]
    source_evidence_ids = [str(v) for v in payload.get("source_evidence_ids") or []]
    evidence_units = get_scoped_evidence(
        source_version_ids,
        evidence_ids=source_evidence_ids or None,
    )
    source_titles = get_source_titles(source_version_ids)

    req = QuizGenerationRequest(
        course_session_id=str(payload.get("course_session_id") or ""),
        count=int(payload.get("count") or 5),
        difficulty=str(payload.get("difficulty") or "综合"),
        source_version_ids=source_version_ids,
        source_evidence_ids=source_evidence_ids,
        evidence_units=evidence_units,
        source_titles=source_titles,
        unit_id=str(payload.get("unit_id") or ""),
        unit_title=str(payload.get("unit_title") or ""),
        task_id=str(payload.get("task_id") or ""),
        mode=str(payload.get("mode") or "fast"),
    )
    run_generation_job_sync(job_id, req)
