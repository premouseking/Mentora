"""Workflow Runtime URL 配置。"""

from django.urls import path

from mentora.workflow_runtime.views import workflow_detail, workflow_list, workflow_submit

urlpatterns = [
    path("workflows/", workflow_list, name="workflow-list"),
    path("workflows/submit/", workflow_submit, name="workflow-submit"),
    path("workflows/<uuid:workflow_id>/", workflow_detail, name="workflow-detail"),
]
