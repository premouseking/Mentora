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

from rest_framework.response import Response
from rest_framework.decorators import api_view
from drf_spectacular.utils import extend_schema

from mentora.courses.models import CourseCreationSession, SessionStatus
from mentora.courses.schemas import (
    ClarifierResponse,
    PlanResponse,
    ProfileCandidatesResponse,
)
from mentora.courses.serializers import (
    SessionCreateSerializer,
    SessionDetailSerializer,
    SessionUpdateSerializer,
)
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


@api_view(["GET", "POST"])
@extend_schema(summary="Session List Or Create")
def session_list_or_create(request):
    """
    GET  /api/courses/sessions/ → 列出所有建课会话
    POST /api/courses/sessions/ → 创建新会话
    """
    if request.method == "GET":
        sessions = CourseCreationSession.objects.all().order_by("-updated_at")
        data = []
        for s in sessions:
            data.append({
                "id": str(s.id),
                "goal": s.goal,
                "title": s.title,
                "status": s.status,
                "level": s.level,
                "pace": s.pace,
                "school": s.school,
                "created_at": s.created_at.isoformat(),
                "updated_at": s.updated_at.isoformat(),
            })
        return Response(data, safe=False)

    # POST
    try:
        body = _parse_json(request)
    except ValueError as exc:
        return Response({"error": str(exc)}, status=400)

    serializer = SessionCreateSerializer(data=body)
    if not serializer.is_valid():
        return Response({"error": serializer.errors}, status=400)

    session = serializer.save()
    return Response(
        {
            "id": str(session.id),
            "goal": session.goal,
            "title": session.title,
            "status": session.status,
        },
        status=201,
    )


@api_view(["GET"])
@extend_schema(summary="Session Detail")
def session_detail(request, session_id):
    """
    GET /api/courses/sessions/<uuid:id>/

    返回：{ "id", "goal", "level", "pace", "inquiry_history", "status", ... }
    """
    try:
        session = _get_session(session_id)
    except ValueError as exc:
        return Response({"error": str(exc)}, status=404)

    data = SessionDetailSerializer(session).data
    data["id"] = str(data["id"])
    return Response(data)


@api_view(["PATCH"])
@extend_schema(summary="Session Update")
def session_update(request, session_id):
    """
    PATCH /api/courses/sessions/<uuid:id>/

    请求体：{ "level"?, "pace"? }
    返回：{ "status": "ok" }
    """
    try:
        session = _get_session(session_id)
    except ValueError as exc:
        return Response({"error": str(exc)}, status=404)

    try:
        body = _parse_json(request)
    except ValueError as exc:
        return Response({"error": str(exc)}, status=400)

    serializer = SessionUpdateSerializer(session, data=body, partial=True)
    if not serializer.is_valid():
        return Response({"error": serializer.errors}, status=400)

    serializer.save()
    return Response({"status": "ok"})


# ── Inquiry 追问 ──


@api_view(["POST"])
@extend_schema(summary="Inquiry Next")
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
        return Response({"error": str(exc)}, status=404)

    try:
        body = _parse_json(request)
    except ValueError as exc:
        return Response({"error": str(exc)}, status=400)

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
        return Response(
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
        return Response(
            {"error": f"LLM 调用失败: {str(exc)}"},
            status=502,
        )

    # 结构化输出校验失败
    if resp.parsed_output is None:
        return Response(
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

    return Response(result)


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


@api_view(["GET", "POST"])
@extend_schema(summary="Plan Handler")
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
        return Response({"error": str(exc)}, status=404)

    from mentora.learning.services import get_active_plan

    plan = get_active_plan(session_id)
    if plan is None:
        return Response({"error": "该课程尚未生成学习方案"}, status=404)

    return Response(plan)


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
        return Response({"error": str(exc)}, status=404)

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
        return Response(
            {"error": f"LLM 调用失败: {str(exc)}"},
            status=502,
        )

    if resp.parsed_output is None:
        return Response(
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

    return Response({**plan_output, "revision_id": revision_id})


# ── 开始学习 ──


@api_view(["POST"])
@extend_schema(summary="Session Start")
def session_start(request, session_id):
    """
    POST /api/courses/sessions/<uuid:id>/start/

    激活 learning 模块中的 plan revision，将会话状态置为 STARTED。

    返回：{ "status": "started", "revision_id": "..." }
    """
    try:
        session = _get_session(session_id)
    except ValueError as exc:
        return Response({"error": str(exc)}, status=404)

    if session.status != SessionStatus.COMPLETED:
        return Response(
            {"error": "方案尚未生成，无法开始学习"},
            status=400,
        )

    from mentora.learning.services import activate_revision, get_active_plan

    plan = get_active_plan(session_id)
    if plan is None:
        return Response({"error": "未找到关联的学习计划"}, status=404)

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

    # 同步写入 session.extra，供 course_confirm 创建作用域时使用
    session = _get_session(session_id)
    session.extra["source_version_ids"] = version_ids
    session.save(update_fields=["extra", "updated_at"])

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


# ── Profile Candidates 画像候选项 ──


@api_view(["POST"])
@extend_schema(summary="Profile Candidates")
def profile_candidates(request, session_id):
    """
    POST /api/courses/sessions/<uuid:id>/candidates/

    基于追问历史生成 2-4 个差异化画像方案供学生选择。
    """
    try:
        session = _get_session(session_id)
    except ValueError as exc:
        return Response({"error": str(exc)}, status=404)

    gateway, prompt_mgr = _get_gateway_and_prompts()

    variables = {
        "school": session.school or "未填写",
        "goal": session.goal or "未填写",
        "level": session.level or "未选择",
        "pace": session.pace or "未选择",
        "time_budget": session.time_budget or "未选择",
        "deadline": session.deadline.isoformat() if session.deadline else "未设定",
        "inquiry_history": _format_history(session.inquiry_history),
    }
    system_text = prompt_mgr.render("clarifier", variables)

    messages = [
        Message(role="system", content=system_text),
        Message(
            role="user",
            content="请基于以上全部信息，生成 2-4 个差异化的学习画像方案候选。"
                    "每个方案应包含不同的目标/重点/节奏，并给出推荐理由。",
        ),
    ]

    try:
        resp = asyncio.run(
            gateway.chat(
                task_type="clarifier",
                messages=messages,
                structured_output_schema=ProfileCandidatesResponse,
            )
        )
    except Exception as exc:
        return Response({"error": f"LLM 调用失败: {str(exc)}"}, status=502)

    if resp.parsed_output is None:
        return Response(
            {"error": "LLM 返回格式异常", "raw_content": resp.content},
            status=502,
        )

    return Response(resp.parsed_output)


# ── Course list ──


@api_view(["GET"])
@extend_schema(summary="Course List")
def course_list(request):
    """
    GET /api/courses/

    返回课程列表（按创建时间倒序）。
    """
    from mentora.courses.models import Course, CourseProfileRevision

    courses = Course.objects.order_by("-created_at").values(
        "id", "active_profile_revision_id", "active_scope_revision_id", "created_at",
    )
    result = []
    for c in courses:
        goal = ""
        status = ""
        if c["active_profile_revision_id"]:
            profile = CourseProfileRevision.objects.filter(
                id=c["active_profile_revision_id"],
            ).values("goal", "status").first()
            if profile:
                goal = profile["goal"]
                status = profile["status"]
        result.append({
            "course_id": str(c["id"]),
            "goal": goal,
            "status": status,
            "created_at": c["created_at"].isoformat(),
        })
    return Response(result, safe=False)


# ── Apply Candidate → Auto Plan ──


@api_view(["POST"])
@extend_schema(summary="Apply Candidate")
def apply_candidate(request, session_id):
    """
    POST /api/courses/sessions/<uuid:id>/apply-candidate/

    请求体: {goal, level, pace}
    流程:
      1. 写入 session goal/level/pace
      2. 创建 Course + CourseProfileRevision(draft)
    返回: {course_id, profile_revision_id, goal, level, pace, status: "draft"}

    用户可继续 PATCH /api/courses/<id>/profile/ 编辑草稿，
    确认后 POST /api/courses/<id>/activate/ 触发 plan_generate 并激活。
    """
    try:
        session = _get_session(session_id)
    except ValueError as exc:
        return Response({"error": str(exc)}, status=404)

    try:
        body = _parse_json(request)
    except ValueError as exc:
        return Response({"error": str(exc)}, status=400)

    goal = body.get("goal", "").strip()
    level = body.get("level", "").strip()
    pace = body.get("pace", "").strip()

    if not goal:
        return Response({"error": "缺少 goal"}, status=400)

    # 更新 session
    session.goal = goal
    session.level = level
    session.pace = pace
    session.save(update_fields=["goal", "level", "pace", "updated_at"])

    # 创建 Course + draft ProfileRevision
    from mentora.courses.models import Course, CourseProfileRevision

    course, _ = Course.objects.get_or_create(session=session)

    # 旧 draft 标记 superseded
    CourseProfileRevision.objects.filter(
        course=course, status=CourseProfileRevision.Status.DRAFT,
    ).update(status=CourseProfileRevision.Status.SUPERSEDED)

    profile = CourseProfileRevision.objects.create(
        course=course,
        goal=goal,
        level=level,
        pace=pace,
        school=session.school or "",
        status=CourseProfileRevision.Status.DRAFT,
    )
    course.active_profile_revision_id = profile.id
    course.save(update_fields=["active_profile_revision_id"])

    session.status = SessionStatus.COMPLETED
    session.save(update_fields=["status", "updated_at"])

    return Response({
        "course_id": str(course.id),
        "profile_revision_id": str(profile.id),
        "goal": profile.goal,
        "level": profile.level,
        "pace": profile.pace,
        "school": profile.school,
        "status": profile.status,
    })


# ── Course 管理 ──


@api_view(["POST"])
@extend_schema(summary="Course Confirm")
def course_confirm(request):
    """
    POST /api/courses/confirm/

    请求体：{"session_id": "..."}
    返回：{course_id, profile_revision_id, scope_revision_id, source_version_ids}
    """
    try:
        body = _parse_json(request)
    except ValueError as exc:
        return Response({"error": str(exc)}, status=400)

    session_id = body.get("session_id", "")
    if not session_id:
        return Response({"error": "缺少 session_id"}, status=400)

    from mentora.courses.services import confirm_course_from_session

    try:
        result = confirm_course_from_session(session_id)
        return Response(result, status=201)
    except CourseCreationSession.DoesNotExist:
        return Response({"error": f"会话 {session_id} 不存在"}, status=404)
    except Exception as exc:
        return Response({"error": str(exc)}, status=500)


@api_view(["GET"])
@extend_schema(summary="Course Detail")
def course_detail(request, course_id):
    """
    GET /api/courses/<uuid:id>/

    返回课程详情：画像字段 + 当前作用域
    """
    from mentora.courses.models import Course, CourseProfileRevision
    from mentora.courses.services import get_course_scope

    try:
        course = Course.objects.get(id=course_id)
    except Course.DoesNotExist:
        return Response({"error": "课程不存在"}, status=404)

    profile = None
    if course.active_profile_revision_id:
        try:
            profile = CourseProfileRevision.objects.get(id=course.active_profile_revision_id)
        except CourseProfileRevision.DoesNotExist:
            pass

    return Response({
        "course_id": str(course.id),
        "goal": profile.goal if profile else "",
        "level": profile.level if profile else "",
        "pace": profile.pace if profile else "",
        "school": profile.school if profile else "",
        "status": profile.status if profile else "",
        "plan_revision_id": str(profile.plan_revision_id) if profile and profile.plan_revision_id else None,
        "source_version_ids": get_course_scope(course_id),
        "created_at": course.created_at.isoformat(),
    })


@api_view(["PATCH"])
@extend_schema(summary="Course Profile Revise")
def course_profile_revise(request, course_id):
    """
    PATCH /api/courses/<uuid:id>/profile/

    请求体：{"goal"?, "level"?, "pace"?, "school"?}
    返回：{profile_revision_id, status, goal, ...}
    """
    try:
        body = _parse_json(request)
    except ValueError as exc:
        return Response({"error": str(exc)}, status=400)

    from mentora.courses.services import revise_profile

    kwargs = {k: v for k, v in body.items()
              if k in ("goal", "level", "pace", "school", "topics_json", "plan_revision_id")}
    if not kwargs:
        return Response({"error": "无有效字段"}, status=400)

    try:
        result = revise_profile(course_id, **kwargs)
        return Response(result)
    except Course.DoesNotExist:
        return Response({"error": "课程不存在"}, status=404)
    except Exception as exc:
        return Response({"error": str(exc)}, status=500)


@api_view(["POST"])
@extend_schema(summary="Course Scope Extend")
def course_scope_extend(request, course_id):
    """
    POST /api/courses/<uuid:id>/scope/

    请求体：{"source_version_ids": [...], "role"?: "reference"}
    返回：{scope_revision_id, source_version_ids, superseded_revision_id}
    """
    try:
        body = _parse_json(request)
    except ValueError as exc:
        return Response({"error": str(exc)}, status=400)

    sv_ids = body.get("source_version_ids", [])
    if not sv_ids:
        return Response({"error": "缺少 source_version_ids"}, status=400)

    from mentora.courses.services import extend_scope

    role = body.get("role", "reference")
    try:
        result = extend_scope(course_id, sv_ids, role=role)
        return Response(result)
    except Course.DoesNotExist:
        return Response({"error": "课程不存在"}, status=404)
    except Exception as exc:
        return Response({"error": str(exc)}, status=500)


@api_view(["GET"])
@extend_schema(summary="Course Scope Suggest")
def course_scope_suggest(request, course_id):
    """
    GET /api/courses/<uuid:id>/scope-suggest/

    返回当前作用域和可加入的新资料列表。
    """
    from mentora.courses.services import suggest_scope_updates

    try:
        result = suggest_scope_updates(course_id)
        return Response(result)
    except Exception as exc:
        return Response({"error": str(exc)}, status=500)


@api_view(["POST"])
@extend_schema(summary="Course Activate")
def course_activate(request, course_id):
    """
    POST /api/courses/<uuid:id>/activate/

    流程: draft → confirmed → plan_generate → create_plan_revision → active
    """
    from mentora.courses.models import Course, CourseProfileRevision
    from mentora.courses.services import activate_course, get_course_scope

    try:
        course = Course.objects.get(id=course_id)
    except Course.DoesNotExist:
        return Response({"error": "课程不存在"}, status=404)

    try:
        profile = CourseProfileRevision.objects.get(
            id=course.active_profile_revision_id,
        )
    except CourseProfileRevision.DoesNotExist:
        return Response({"error": "无活动画像修订"}, status=400)

    if profile.status != CourseProfileRevision.Status.DRAFT:
        return Response({"error": f"画像状态为 {profile.status}，需为 draft"}, status=400)

    # 1. 调 PlannerAgent 生成计划
    session = course.session
    gateway, prompt_mgr = _get_gateway_and_prompts()

    variables = {
        "school": profile.school or "未填写",
        "goal": profile.goal,
        "level": profile.level or "未选择",
        "pace": profile.pace or "未选择",
        "time_budget": session.time_budget or "未选择",
        "deadline": session.deadline.isoformat() if session.deadline else "未设定",
        "inquiry_history": _format_history(session.inquiry_history),
    }
    system_text = prompt_mgr.render("planner", variables)

    messages = [
        Message(role="system", content=system_text),
        Message(role="user", content="请根据以上全部信息，生成一份阶段化学习方案。"),
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
        return Response({"error": f"LLM 调用失败: {str(exc)}"}, status=502)

    if resp.parsed_output is None:
        return Response({"error": "LLM 返回格式异常"}, status=502)

    plan_output = resp.parsed_output

    # 2. 持久化计划
    from mentora.learning.services import create_plan_revision

    plan_result = create_plan_revision(
        course_session_id=str(session.id),
        plan_snapshot={
            "total_budget_minutes": 80 * 60,
            "phases": plan_output.get("phases", []),
        },
        profile_revision_id=str(profile.id),
    )

    profile.plan_revision_id = plan_result["revision_id"]
    profile.save(update_fields=["plan_revision_id"])

    # 3. 确认 + 激活
    profile.status = CourseProfileRevision.Status.CONFIRMED
    profile.save(update_fields=["status"])

    try:
        result = activate_course(course_id)
    except Exception as exc:
        return Response({"error": str(exc)}, status=500)

    return Response({
        **result,
        "plan": {"phases": plan_output.get("phases", []), "revision_id": plan_result["revision_id"]},
    })
