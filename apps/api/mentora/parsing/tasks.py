"""
Celery 解析任务（兼容入口，实际编排已迁移至 knowledge.services.processing）。

@module mentora/parsing/tasks
"""

from celery import shared_task

from mentora.knowledge.services.processing import run_processing_for_version


class ParseTaskFailedError(Exception):
    """解析任务不可恢复的失败。"""


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    name="mentora.parsing.tasks.run_parsing",
)
def run_parsing(
    self,
    source_version_id: str,
    parser_version: str = "1.23.0",
) -> dict:
    """解析单个 SourceVersion 并持久化证据。"""
    try:
        run = run_processing_for_version(
            source_version_id,
            parser_version=parser_version,
            sync=True,
        )
        return {
            "source_version_id": source_version_id,
            "run_id": str(run.id),
            "status": run.status,
        }
    except Exception as exc:
        raise ParseTaskFailedError(str(exc)) from exc
