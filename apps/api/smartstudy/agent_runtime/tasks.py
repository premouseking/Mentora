from celery import shared_task


@shared_task(name="smartstudy.agent_runtime.tasks.run_workflow")
def run_workflow(workflow_id: str) -> dict[str, str]:
    """Celery bridge for the explicit workflow state machine."""
    return {"workflow_id": workflow_id, "status": "accepted"}
