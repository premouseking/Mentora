"""
Workflow Runtime HTTP 视图：异步工作流提交、查询与列表。

约定：
- POST /api/workflows/ 提交异步工作流
- GET /api/workflows/<workflow_id>/ 查询单个工作流状态与结果
- GET /api/workflows/ 当前用户工作流列表

@module mentora/workflow_runtime/views
"""

import json

from drf_spectacular.utils import extend_schema
from rest_framework.decorators import api_view
from rest_framework.response import Response

from mentora.workflow_runtime.services import WorkflowRuntime
from mentora.workflow_runtime.tasks import run_workflow


@extend_schema(
    summary="提交异步工作流",
    description="创建一个新的异步工作流任务，返回 workflow_id 供后续查询。",
    tags=["Workflow"],
    request={
        "application/json": {
            "type": "object",
            "properties": {
                "workflow_type": {
                    "type": "string",
                    "enum": ["chat", "pipeline", "course_creation"],
                    "description": "工作流类型",
                },
                "input_json": {
                    "type": "object",
                    "description": "OrchestratorTask 序列化 JSON",
                },
                "owner_id": {
                    "type": "string",
                    "description": "发起用户 ID（可选）",
                },
            },
            "required": ["workflow_type", "input_json"],
        },
    },
    responses={
        201: {"description": "工作流已提交"},
        400: {"description": "参数无效"},
    },
)
@api_view(["POST"])
def workflow_submit(request):
    """POST /api/workflows/"""
    try:
        body = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return Response({"error": "无效 JSON"}, status=400)

    workflow_type = (body.get("workflow_type") or "").strip()
    if workflow_type not in ("chat", "pipeline", "course_creation"):
        return Response({"error": "workflow_type 必须是 chat / pipeline / course_creation"}, status=400)

    input_json = body.get("input_json")
    if not isinstance(input_json, dict):
        return Response({"error": "input_json 必须是对象"}, status=400)

    owner_id = (body.get("owner_id") or "").strip()

    runtime = WorkflowRuntime()
    wf = runtime.submit(
        workflow_type=workflow_type,
        input_json=input_json,
        owner_id=owner_id,
    )

    run_workflow.delay(str(wf.id))

    return Response(
        {"workflow_id": str(wf.id), "status": wf.status},
        status=201,
    )


@extend_schema(
    summary="查询工作流状态",
    description="按 ID 查询工作流的当前状态和结果。",
    tags=["Workflow"],
    responses={
        200: {"description": "工作流详情"},
        404: {"description": "工作流不存在"},
    },
)
@api_view(["GET"])
def workflow_detail(request, workflow_id):
    """GET /api/workflows/<workflow_id>/"""
    runtime = WorkflowRuntime()
    wf = runtime.get(workflow_id)
    if wf is None:
        return Response({"error": "工作流不存在"}, status=404)

    return Response({
        "id": str(wf.id),
        "workflow_type": wf.workflow_type,
        "status": wf.status,
        "current_step_index": wf.current_step_index,
        "input_json": wf.input_json,
        "output_json": wf.output_json,
        "owner_id": wf.owner_id,
        "error_code": wf.error_code,
        "error_message": wf.error_message,
        "started_at": wf.started_at.isoformat() if wf.started_at else None,
        "completed_at": wf.completed_at.isoformat() if wf.completed_at else None,
        "created_at": wf.created_at.isoformat() if wf.created_at else None,
    })


@extend_schema(
    summary="用户工作流列表",
    description="返回当前用户提交的工作流列表，按创建时间倒序。",
    tags=["Workflow"],
    parameters=[
        {
            "name": "owner_id",
            "in_": "query",
            "type": "string",
            "description": "用户 ID",
            "required": True,
        },
        {
            "name": "limit",
            "in_": "query",
            "type": "integer",
            "description": "返回条数上限，默认 20",
        },
    ],
    responses={
        200: {"description": "工作流列表"},
        400: {"description": "缺少 owner_id"},
    },
)
@api_view(["GET"])
def workflow_list(request):
    """GET /api/workflows/"""
    owner_id = (request.GET.get("owner_id") or "").strip()
    if not owner_id:
        return Response({"error": "owner_id 为必填参数"}, status=400)

    try:
        limit = max(1, min(100, int(request.GET.get("limit", 20))))
    except (ValueError, TypeError):
        limit = 20

    runtime = WorkflowRuntime()
    wfs = runtime.list_by_owner(owner_id, limit=limit)

    items = []
    for wf in wfs:
        items.append({
            "id": str(wf.id),
            "workflow_type": wf.workflow_type,
            "status": wf.status,
            "error_code": wf.error_code,
            "created_at": wf.created_at.isoformat() if wf.created_at else None,
        })

    # offset 固定为 0：该端点仅支持 limit 截断，暂不支持翻页
    return Response({"items": items, "total": len(items), "limit": limit, "offset": 0})
