"""
知识库 Celery 任务。

@module mentora/knowledge/tasks
"""

from celery import shared_task

from mentora.knowledge.services.processing import run_processing_for_version


@shared_task(name="mentora.knowledge.tasks.ingest_source")
def ingest_source(source_id: str) -> dict[str, str]:
    """资料入库入口（按 Source 触发最新版本处理）。"""
    from mentora.knowledge.models import Source

    source = Source.objects.select_related("latest_version").get(id=source_id)
    if source.latest_version_id is None:
        return {"source_id": source_id, "status": "no_version"}

    run = run_processing_for_version(str(source.latest_version_id), sync=True)
    return {"source_id": source_id, "status": run.status}


@shared_task(name="mentora.knowledge.tasks.run_processing")
def run_processing(source_version_id: str, parser_version: str = "1.23.0") -> dict:
    """异步解析与证据入库。"""
    run = run_processing_for_version(source_version_id, parser_version=parser_version, sync=True)
    return {"run_id": str(run.id), "status": run.status}
