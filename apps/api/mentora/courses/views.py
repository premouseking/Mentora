"""
建课会话 HTTP 视图：Session CRUD + Inquiry 追问 + Plan 方案生成 + 开始学习。

约定：
- 视图函数风格（与 knowledge/views.py 一致），不使用 DRF ViewSet
- 所有端点 csrf_exempt，生产环境需配合 Token 认证
- inquiry 和 plan 端点调用 model_gateway + Pydantic schema 校验
- 复用 agent_runtime/views 中的单例 gateway / prompt_manager
- plan_generate 在生成方案后持久化到 learning 模块

@module mentora/courses/views
"""

import asyncio
import json
import uuid

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from mentora.courses.models import CourseCreationSession, SessionStatus
from mentora.courses.schemas import ClarifierResponse, PlanResponse
from mentora.courses.serializers import (
    SessionCreateSerializer,
    SessionDetailSerializer,
    SessionUpdateSerializer,
)
from mentora.knowledge.models import CourseSource
from mentora.knowledge.models import SourceVersion
from mentora.model_gateway.schemas import Message

# 追问最大轮次（防止无限循环）
MAX_INQUIRY_ROUNDS = 8


def _parse_json(request) -> dict:
    """安全解析请求 JSON body。"""
    if not request.body:
        return {}
    try:
        return json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ValueError("无效 JSON")


def _get_session(session_id: str) -> CourseCreationSession:
    """按 UUID 获取会话，不存在时抛 ValueError。"""
    try:
        return CourseCreationSession.objects.get(id=session_id)
    except CourseCreationSession.DoesNotExist:
        raise ValueError(f"会话 {session_id} 不存在")


def _get_gateway_and_prompts():
    """延迟导入，获取单例 gateway 和 prompt_manager。"""
    from mentora.agent_runtime.views import get_gateway, get_prompt_manager

    return get_gateway(), get_prompt_manager()


def _format_history(inquiry_history: list[dict]) -> str:
    """将追问历史格式化为可读文本，供 prompt 变量使用。"""
    if not inquiry_history:
        return "（尚无追问记录）"
    lines: list[str] = []
    for i, entry in enumerate(inquiry_history, 1):
        q = entry.get("question", "")
        a = entry.get("answer", "")
        lines.append(f"第{i}轮：问「{q}」答「{a}」")
    return "\n".join(lines)


# ── Session CRUD ──


@csrf_exempt
def session_list_or_create(request):
    """
    GET  /api/courses/sessions/ → 列出所有建课会话
    POST /api/courses/sessions/ → 创建新会话
    """
    if request.method == "GET":
        sessions = CourseCreationSession.objects.all().order_by("-updated_at")

        # 预加载进度摘要
        from mentora.learning.services import get_progress_summary

        progress_map: dict = {}
        for s in sessions:
            try:
                summary = get_progress_summary(str(s.id))
                if summary:
                    progress_map[str(s.id)] = summary
            except Exception:
                pass

        data = []
        for s in sessions:
            progress = progress_map.get(str(s.id))
            data.append({
                "id": str(s.id),
                "goal": s.goal,
                "title": s.title,
                "status": s.status,
                "level": s.level,
                "pace": s.pace,
                "time_budget": s.time_budget,
                "school": s.school,
                "deadline": s.deadline.isoformat() if s.deadline else None,
                "current_phase": progress["current_phase"] if progress else None,
                "next_task": progress["next_task"] if progress else None,
                "created_at": s.created_at.isoformat(),
                "updated_at": s.updated_at.isoformat(),
                "last_studied_at": s.last_studied_at.isoformat() if s.last_studied_at else None,
            })
        return JsonResponse(data, safe=False)

    # POST
    try:
        body = _parse_json(request)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    serializer = SessionCreateSerializer(data=body)
    if not serializer.is_valid():
        return JsonResponse({"error": serializer.errors}, status=400)

    session = serializer.save()
    return JsonResponse(
        {
            "id": str(session.id),
            "goal": session.goal,
            "title": session.title,
            "status": session.status,
        },
        status=201,
    )


@csrf_exempt
@require_http_methods(["GET"])
def session_detail(request, session_id):
    """
    GET /api/courses/sessions/<uuid:id>/

    返回：{ "id", "goal", "level", "pace", "inquiry_history", "status", ... }
    """
    try:
        session = _get_session(session_id)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=404)

    data = SessionDetailSerializer(session).data
    data["id"] = str(data["id"])
    return JsonResponse(data)


@csrf_exempt
@require_http_methods(["PATCH"])
def session_update(request, session_id):
    """
    PATCH /api/courses/sessions/<uuid:id>/

    请求体：{ "level"?, "pace"? }
    返回：{ "status": "ok" }
    """
    try:
        session = _get_session(session_id)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=404)

    try:
        body = _parse_json(request)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    serializer = SessionUpdateSerializer(session, data=body, partial=True)
    if not serializer.is_valid():
        return JsonResponse({"error": serializer.errors}, status=400)

    serializer.save()
    return JsonResponse({"status": "ok"})


# ── Inquiry 追问 ──


@csrf_exempt
@require_http_methods(["POST"])
def inquiry_next(request, session_id):
    """
    POST /api/courses/sessions/<uuid:id>/inquiry/

    请求体（可选）：{ "answer": "用户回答" }
    返回：
    - 继续追问: { "ready": false, "questions": [{ "text","type","options","guidance" }] }
    - 信息充足: { "ready": true, "summary": "总结文本" }

    约束：
    - 首次调用不传 answer，触发首个问题
    - 每次回答后追加到 inquiry_history，发给 LLM 判断是否继续
    - 追问超过 MAX_INQUIRY_ROUNDS 轮后强制 ready=true
    """
    try:
        session = _get_session(session_id)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=404)

    try:
        body = _parse_json(request)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    answer = body.get("answer", "").strip()

    # 有回答 → 更新上一轮 pending 的问题（最后一条 answer 为空的历史记录）
    if answer:
        if session.inquiry_history and session.inquiry_history[-1].get("answer", "") == "":
            session.inquiry_history[-1]["answer"] = answer
        else:
            # 异常情况：没有 pending 问题，仍然记录
            session.inquiry_history.append(
                {"question": "（用户直接输入）", "answer": answer}
            )
        session.save(update_fields=["inquiry_history", "updated_at"])

    # 超过最大轮次 → 强制终止
    if len(session.inquiry_history) >= MAX_INQUIRY_ROUNDS:
        session.status = SessionStatus.GENERATING_PLAN
        session.save(update_fields=["status", "updated_at"])
        return JsonResponse(
            {
                "ready": True,
                "summary": "已收集足够信息，可以生成学习方案。",
            }
        )

    # 构建消息并调用 LLM
    gateway, prompt_mgr = _get_gateway_and_prompts()

    variables = {
        "school": session.school or "未填写",
        "goal": session.goal or "未填写",
        "level": session.level or "未选择",
        "pace": session.pace or "未选择",
        "inquiry_history": _format_history(session.inquiry_history),
    }
    system_text = prompt_mgr.render("clarifier", variables)

    messages = [
        Message(role="system", content=system_text),
        Message(
            role="user",
            content=f"请根据以上信息，判断是否需要继续追问，并生成下一轮结构化问题。",
        ),
    ]

    try:
        resp = asyncio.run(
            gateway.chat(
                task_type="clarifier",
                messages=messages,
                structured_output_schema=ClarifierResponse,
            )
        )
    except Exception as exc:
        return JsonResponse(
            {"error": f"LLM 调用失败: {str(exc)}"},
            status=502,
        )

    # 结构化输出校验失败
    if resp.parsed_output is None:
        return JsonResponse(
            {
                "error": "LLM 返回格式异常，请重试",
                "raw_content": resp.content,
            },
            status=502,
        )

    result: dict = resp.parsed_output  # type: ignore[assignment]

    # LLM 返回新问题 → 追加 pending 条目到历史
    if not result.get("ready") and result.get("questions"):
        # 存第一条问题（当前前端一次只显示一道题）
        q = result["questions"][0]
        session.inquiry_history.append(
            {
                "question": q.get("text", ""),
                "answer": "",  # 待用户回答
            }
        )
        session.save(update_fields=["inquiry_history", "updated_at"])

    if result.get("ready"):
        session.status = SessionStatus.GENERATING_PLAN
        session.save(update_fields=["status", "updated_at"])

    return JsonResponse(result)


# ── Plan 方案生成 ──


def _plan_to_learning_snapshot(plan_output: dict) -> dict:
    """将 PlanResponse JSON 映射为 learning 模块的 plan_snapshot 格式。

    映射规则：
    - PlanPhase → LearningPlanPhase + 1 个 LearningPlanUnit
    - PlanPhase.tasks[] → LearningPlanTaskTemplate[]（默认 lecture/text 类型）
    - Phase.share 百分比 → 估算分钟数（share * 3）
    """
    phases: list[dict] = []
    for phase_data in plan_output.get("phases", []):
        phase_title = phase_data.get("name", "未命名阶段")
        phase_goal = phase_data.get("goal", "")
        share = phase_data.get("share", 25)
        estimated = share * 3  # 百分比 → 分钟估算

        tasks: list[dict] = []
        for task_text in phase_data.get("tasks", []):
            tasks.append({
                "task_type": "lecture",
                "delivery_mode": "text",
                "estimated_minutes": max(10, estimated // max(len(phase_data.get("tasks", [])), 1)),
                "required": True,
            })

        phases.append({
            "title": phase_title,
            "objective": phase_goal,
            "estimated_minutes": estimated,
            "position": len(phases),
            "units": [{
                "id": str(uuid.uuid4()),
                "title": phase_title,
                "position": 0,
                "target_depth": "basic",
                "estimated_minutes": estimated,
                "prerequisite_unit_ids": [],
                "tasks": tasks,
            }],
        })

    return {
        "total_budget_minutes": sum(p["estimated_minutes"] for p in phases),
        "phases": phases,
    }


@csrf_exempt
def plan_handler(request, session_id):
    """
    GET  /api/courses/sessions/<uuid:id>/plan/ → 返回当前生效的学习方案
    POST /api/courses/sessions/<uuid:id>/plan/ → 生成学习方案
    """
    if request.method == "GET":
        return _plan_detail(request, session_id)
    return _plan_generate(request, session_id)


def _plan_detail(request, session_id):
    """返回当前生效的学习方案（阶段、单元、任务）。"""
    try:
        _get_session(session_id)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=404)

    from mentora.learning.services import get_active_plan

    plan = get_active_plan(session_id)
    if plan is None:
        return JsonResponse({"error": "该课程尚未生成学习方案"}, status=404)

    return JsonResponse(plan)


@csrf_exempt
def _plan_generate(request, session_id):
    """
    POST /api/courses/sessions/<uuid:id>/plan/

    返回：{ "phases": [{ "name", "goal", "share", "tasks" }], "revision_id": "..." }

    约束：
    - 基于会话中全部已收集信息生成方案
    - 方案同步持久化到 learning 模块（status=draft）
    """
    try:
        session = _get_session(session_id)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=404)

    gateway, prompt_mgr = _get_gateway_and_prompts()

    variables = {
        "school": session.school or "未填写",
        "goal": session.goal or "未填写",
        "level": session.level or "未选择",
        "pace": session.pace or "未选择",
        "inquiry_history": _format_history(session.inquiry_history),
    }
    system_text = prompt_mgr.render("planner", variables)

    messages = [
        Message(role="system", content=system_text),
        Message(
            role="user",
            content="请根据以上全部信息，生成一份阶段化学习方案。",
        ),
    ]

    try:
        resp = asyncio.run(
            gateway.chat(
                task_type="planner",
                messages=messages,
                structured_output_schema=PlanResponse,
            )
        )
    except Exception as exc:
        return JsonResponse(
            {"error": f"LLM 调用失败: {str(exc)}"},
            status=502,
        )

    if resp.parsed_output is None:
        return JsonResponse(
            {
                "error": "LLM 返回格式异常，请重试",
                "raw_content": resp.content,
            },
            status=502,
        )

    # 持久化到 learning 模块
    plan_output: dict = resp.parsed_output  # type: ignore[assignment]

    # 存储 LLM 生成的标题
    course_title = plan_output.get("title", "").strip()
    if course_title:
        session.title = course_title

    revision_id = ""
    try:
        from mentora.learning.services import create_plan_revision, activate_revision

        snapshot = _plan_to_learning_snapshot(plan_output)
        revision = create_plan_revision(
            course_session_id=session_id,
            plan_snapshot=snapshot,
            profile_revision_id="",
            knowledge_scope_revision_id="",
        )
        revision_id = revision["revision_id"]
        # 立即激活，使工作区页面可以查到方案
        activate_revision(revision_id)
    except Exception:
        # 持久化失败不影响方案返回，前端可继续展示
        pass

    session.status = SessionStatus.COMPLETED
    session.save(update_fields=["title", "status", "updated_at"])

    return JsonResponse({**plan_output, "revision_id": revision_id})


# ── 开始学习 ──


@csrf_exempt
@require_http_methods(["POST"])
def session_start(request, session_id):
    """
    POST /api/courses/sessions/<uuid:id>/start/

    激活 learning 模块中的 plan revision，将会话状态置为 STARTED。

    返回：{ "status": "started", "revision_id": "..." }
    """
    try:
        session = _get_session(session_id)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=404)

    if session.status != SessionStatus.COMPLETED:
        return JsonResponse(
            {"error": "方案尚未生成，无法开始学习"},
            status=400,
        )

    from mentora.learning.services import activate_revision, get_active_plan

    plan = get_active_plan(session_id)
    if plan is None:
        return JsonResponse({"error": "未找到关联的学习计划"}, status=404)

    result = activate_revision(plan["revision_id"])

    session.status = SessionStatus.STARTED
    session.save(update_fields=["status", "updated_at"])

    return JsonResponse({
        "status": "started",
        "revision_id": result["revision_id"],
    })


# ── 课程资料关联 ──


@csrf_exempt
def course_sources_manage(request, session_id):
    """
    GET  /api/courses/sessions/<uuid:id>/sources/  → 查课程已关联资料
    POST /api/courses/sessions/<uuid:id>/sources/  → 批量设置关联

    POST body: { "source_version_ids": ["uuid1", "uuid2", ...] }
    注意：为幂等安全，先删后建，而非增量合并。
    """
    try:
        _get_session(session_id)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=404)

    if request.method == "GET":
        links = CourseSource.objects.filter(
            course_session_id=session_id,
        ).select_related("source_version__source")
        items = []
        for link in links:
            sv = link.source_version
            items.append({
                "sourceVersionId": str(sv.id),
                "sourceId": str(sv.source.id),
                "displayTitle": sv.source.display_title,
                "originalFilename": sv.original_filename,
                "processingStatus": sv.processing_status,
                "addedAt": link.added_at.isoformat(),
            })
        return JsonResponse({"items": items, "count": len(items)})

    # POST
    try:
        body = _parse_json(request)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    version_ids = body.get("source_version_ids", [])
    if not isinstance(version_ids, list):
        return JsonResponse({"error": "source_version_ids 必须是数组"}, status=400)

    # 幂等：先删后建
    CourseSource.objects.filter(course_session_id=session_id).delete()

    created = 0
    for vid in version_ids:
        try:
            sv = SourceVersion.objects.get(id=vid)
        except SourceVersion.DoesNotExist:
            continue
        CourseSource.objects.get_or_create(
            course_session_id=session_id,
            source_version=sv,
        )
        created += 1

    return JsonResponse({"status": "ok", "source_count": created})


# ── 删除课程 ──


@csrf_exempt
@require_http_methods(["DELETE"])
def session_delete(request, session_id):
    """
    DELETE /api/courses/sessions/<uuid:id>/

    删除建课会话及其课程资料关联。
    """
    try:
        session = _get_session(session_id)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=404)

    # 清理课程资料关联（非 FK，需手动删）
    CourseSource.objects.filter(course_session_id=session_id).delete()
    session.delete()

    return JsonResponse({"status": "deleted"})
