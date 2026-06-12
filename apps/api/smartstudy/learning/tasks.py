from celery import shared_task


@shared_task(name="smartstudy.learning.tasks.recalculate_plan")
def recalculate_plan(plan_id: str) -> dict[str, str]:
    """Entry point for localized learning-plan recalculation."""
    return {"plan_id": plan_id, "status": "accepted"}

