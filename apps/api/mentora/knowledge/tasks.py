from celery import shared_task


@shared_task(name="mentora.knowledge.tasks.ingest_source")
def ingest_source(source_id: str) -> dict[str, str]:
    """Entry point for the incremental document ingestion pipeline."""
    return {"source_id": source_id, "status": "accepted"}

