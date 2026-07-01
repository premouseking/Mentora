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
from rest_framework.response import Response
from rest_framework.decorators import api_view
from drf_spectacular.utils import extend_schema

from mentora.courses.models import Course, CourseCreationSession, SessionStatus
from mentora.courses.services import archive_session, resolve_course
from mentora.courses.schemas import (
    ClarifierResponse,
    PlanResponse,
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
        try:
            course = Course.objects.select_related("session").get(id=session_id)
            return course.session
        except Course.DoesNotExist:
            raise ValueError(f"会话 {session_id} 不存在")


def _resolve_course_context(resource_id: str) -> tuple[Course | None, CourseCreationSession, str]:
    """解析 course_id 或 session_id，返回 (course|None, session, session_id)。"""
    resolved = resolve_course(resource_id)
    return resolved.course, resolved.session, resolved.session_id


_ARCHIVED_STATUSES = frozenset({SessionStatus.ARCHIVED, SessionStatus.STARTED})


def _ensure_session_writable(session: CourseCreationSession) -> Response | None:
    """archived/legacy started 会话禁止写入。"""
    if session.status in _ARCHIVED_STATUSES:
        return Response({"error": "建课会话已归档，不可修改"}, status=409)
    return None


def _purge_session(session: CourseCreationSession) -> None:
    """删除会话及关联的学习计划、Course 与资料绑定。"""
    from mentora.knowledge.models import CourseSource
    from mentora.learning.models import LearningPlan

    session_id = str(session.id)
    CourseSource.objects.filter(course_session_id=session_id).delete()
    LearningPlan.objects.filter(creation_session=session).delete()
    Course.objects.filter(session=session).delete()
    session.delete()


def _get_gateway_and_prompts():
    """延迟导入，获取单例 gateway 和 prompt_manager。"""
    from mentora.agent_runtime.views import get_gateway, get_prompt_manager

    return get_gateway(), get_prompt_manager()


def _gateway_unavailable_response(exc: Exception) -> Response:
    return Response({"error": str(exc)}, status=503)


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


def _build_source_context(source_version_ids: list[str], *, limit: int = 12) -> str:
    """Build a compact evidence summary for PlannerAgent."""
    if not source_version_ids:
        return "No uploaded course materials were selected."

    from mentora.knowledge.models import SourceVersion
    from mentora.retrieval.models import EvidenceUnit

    versions = {
        str(version.id): version
        for version in SourceVersion.objects.select_related("source").filter(
            id__in=source_version_ids,
        )
    }
    units = EvidenceUnit.objects.filter(
        source_version_id__in=source_version_ids,
    ).order_by("source_version_id", "page_number", "created_at")[:limit]

    lines = []
    for unit in units:
        version = versions.get(str(unit.source_version_id))
        title = (
            version.source.display_title
            if version is not None
            else str(unit.source_version_id)
        )
        content = " ".join((unit.content or "").split())[:260]
        lines.append(
            f"- evidence_id={unit.id}; source={title}; page={unit.page_number}; text={content}"
        )

    if lines:
        return "\n".join(lines)

    titles = [
        version.source.display_title or version.original_filename or str(version.id)
        for version in versions.values()
    ]
    return "Selected materials have no parsed evidence yet: " + ", ".join(titles)


# ── Session CRUD ──


@api_view(["GET", "POST"])
@extend_schema(summary="Session List Or Create")
def session_list_or_create(request):
    """
    GET  /api/courses/sessions/ → 列出所有建课会话
    POST /api/courses/sessions/ → 创建新会话
    """
    if request.method == "GET":
        from mentora.learning.services import get_active_plan, get_upcoming_tasks

        data: list[dict] = []

        for course in Course.objects.select_related("session").order_by("-session__updated_at"):
            s = course.session
            current_phase = None
            next_task = None
            plan = get_active_plan(str(course.id))
            if plan and plan.get("phases"):
                current_phase = plan["phases"][0].get("title")
            try:
                tasks = get_upcoming_tasks(str(course.id), limit=1)
                if tasks:
                    next_task = tasks[0].get("task_type")
            except Exception:
                next_task = None
            data.append({
                "course_id": str(course.id),
                "session_id": str(s.id),
                "id": str(course.id),
                "goal": s.goal,
                "title": s.title,
                "status": "active",
                "level": s.level,
                "pace": s.pace,
                "time_budget": s.time_budget,
                "school": s.school,
                "deadline": s.deadline.isoformat() if s.deadline else None,
                "current_phase": current_phase,
                "next_task": next_task,
                "created_at": s.created_at.isoformat(),
                "updated_at": s.updated_at.isoformat(),
                "last_studied_at": s.last_studied_at.isoformat() if s.last_studied_at else None,
            })

        confirmed_session_ids = Course.objects.values_list("session_id", flat=True)
        pending = CourseCreationSession.objects.filter(
            status=SessionStatus.COMPLETED,
        ).exclude(id__in=confirmed_session_ids).order_by("-updated_at")
        for s in pending:
            data.append({
                "course_id": None,
                "session_id": str(s.id),
                "id": str(s.id),
                "goal": s.goal,
                "title": s.title,
                "status": "completed",
                "level": s.level,
                "pace": s.pace,
                "time_budget": s.time_budget,
                "school": s.school,
                "deadline": s.deadline.isoformat() if s.deadline else None,
                "current_phase": None,
                "next_task": None,
                "created_at": s.created_at.isoformat(),
                "updated_at": s.updated_at.isoformat(),
                "last_studied_at": s.last_studied_at.isoformat() if s.last_studied_at else None,
            })
        return Response(data)

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

    blocked = _ensure_session_writable(session)
    if blocked is not None:
        return blocked

    try:
        body = _parse_json(request)
    except ValueError as exc:
        return Response({"error": str(exc)}, status=400)

    serializer = SessionUpdateSerializer(session, data=body, partial=True)
    if not serializer.is_valid():
        return Response({"error": serializer.errors}, status=400)

    serializer.save()
    return Response({"status": "ok"})


@extend_schema(
    summary="删除建课会话",
    responses={200: {"description": "删除成功"}, 404: {"description": "会话不存在"}},
)
@api_view(["DELETE"])
def session_delete(request, session_id):
    try:
        session = _get_session(session_id)
    except ValueError as exc:
        return Response({"error": str(exc)}, status=404)
    _purge_session(session)
    return Response({"status": "deleted"})


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

    blocked = _ensure_session_writable(session)
    if blocked is not None:
        return blocked

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
    try:
        gateway, prompt_mgr = _get_gateway_and_prompts()
    except RuntimeError as exc:
        return _gateway_unavailable_response(exc)

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
        # 提取追问历史为结构化补充画像
        supplement = {}
        for entry in session.inquiry_history:
            q = (entry.get("question") or "").strip()
            a = (entry.get("answer") or "").strip()
            if q and a:
                supplement[q] = a
        if supplement:
            session.profile_supplement = supplement
        session.save(update_fields=["status", "inquiry_history", "profile_supplement", "updated_at"])

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
        session = _get_session(session_id)
    except ValueError as exc:
        return Response({"error": str(exc)}, status=404)

    from mentora.learning.services import get_active_plan
    from mentora.topics.services import get_topic_tree

    resolved_session_id = str(session.id)
    plan = get_active_plan(resolved_session_id)
    if plan is None and resolved_session_id != str(session_id):
        plan = get_active_plan(str(session_id))
    if plan is None:
        revision_id = session.extra.get("plan_revision_id")
        if revision_id:
            from mentora.learning.services import activate_revision

            try:
                activate_revision(str(revision_id))
            except Exception:
                pass
            plan = get_active_plan(resolved_session_id)
    if plan is None:
        return Response({"error": "该课程尚未生成学习方案"}, status=404)

    plan["topics"] = get_topic_tree(str(session_id))
    return Response(plan)


@api_view(["GET"])
@extend_schema(summary="Course Active Plan")
def course_plan(request, course_id):
    """GET /api/courses/<course_id>/plan/ — 学习期活跃方案。"""
    from mentora.courses.services import resolve_course_required
    from mentora.learning.services import get_active_plan
    from mentora.topics.services import get_topic_tree

    try:
        course, _session = resolve_course_required(str(course_id))
    except ValueError as exc:
        return Response({"error": str(exc)}, status=404)

    plan = get_active_plan(str(course.id))
    if plan is None:
        return Response({"error": "该课程尚未生成学习方案"}, status=404)
    plan["topics"] = get_topic_tree(str(course.id))
    return Response(plan)


@api_view(["PATCH"])
@extend_schema(summary="Course Activity")
def course_activity(request, course_id):
    """PATCH /api/courses/<course_id>/activity/ — 更新最近学习时间。"""
    from django.utils.dateparse import parse_datetime

    from mentora.courses.services import resolve_course_required

    try:
        _course, session = resolve_course_required(str(course_id))
    except ValueError as exc:
        return Response({"error": str(exc)}, status=404)

    try:
        body = _parse_json(request)
    except ValueError as exc:
        return Response({"error": str(exc)}, status=400)

    raw = body.get("last_studied_at")
    if raw:
        parsed = parse_datetime(raw)
        if parsed is None:
            return Response({"error": "last_studied_at 格式无效"}, status=400)
        session.last_studied_at = parsed
        session.save(update_fields=["last_studied_at", "updated_at"])
    return Response({"status": "ok"})


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

    blocked = _ensure_session_writable(session)
    if blocked is not None:
        return blocked

    resolved_session_id = str(session.id)

    try:
        gateway, prompt_mgr = _get_gateway_and_prompts()
    except RuntimeError as exc:
        return _gateway_unavailable_response(exc)

    variables = {
        "school": session.school or "未填写",
        "goal": session.goal or "未填写",
        "level": session.level or "未选择",
        "pace": session.pace or "未选择",
        "inquiry_history": _format_history(session.inquiry_history),
    }
    system_text = prompt_mgr.render("planner", variables)
    source_version_ids = [str(item) for item in session.extra.get("source_version_ids", [])]
    source_context = _build_source_context(source_version_ids)
    system_text = f"{system_text}\n\nSelected source evidence for planning:\n{source_context}"

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
            course_session_id=resolved_session_id,
            plan_snapshot=snapshot,
            profile_revision_id="",
            knowledge_scope_revision_id="",
        )
        revision_id = revision["revision_id"]
        activate_revision(revision_id)

        # 自动构建主题树 + 证据关联（LLM 输出中的 topics）
        topics_data = plan_output.get("topics", [])
        if topics_data:
            from mentora.topics.models import Topic
            from mentora.topics.services import build_topic_tree, link_evidence

            build_topic_tree(resolved_session_id, [
                {"name": t["name"], "level": 0, "position": idx,
                 "estimated_minutes": 0}
                for idx, t in enumerate(topics_data)
            ])
            for t in topics_data:
                eids = t.get("evidence_ids", [])
                if eids:
                    topic = Topic.objects.filter(
                        legacy_course_key=resolved_session_id,
                        name=t["name"],
                    ).first()
                    if topic:
                        link_evidence(str(topic.id), eids)
    except Exception as exc:
        # 持久化失败不影响方案返回，前端可继续展示
        return Response({"error": f"方案持久化失败: {str(exc)}"}, status=500)

    session.status = SessionStatus.COMPLETED
    session.extra["plan_revision_id"] = revision_id
    session.save(update_fields=["title", "status", "extra", "updated_at"])

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
    resolved_session_id = str(session.id)

    if session.status not in (
        SessionStatus.COMPLETED,
        SessionStatus.STARTED,
        SessionStatus.ARCHIVED,
    ):
        return Response(
            {"error": "方案尚未生成，无法开始学习"},
            status=400,
        )

    from mentora.courses.models import CourseProfileRevision
    from mentora.courses.services import activate_course, confirm_course_from_session
    from mentora.learning.services import get_active_plan

    plan = get_active_plan(resolved_session_id)
    if plan is None and resolved_session_id != str(session_id):
        plan = get_active_plan(str(session_id))
    if plan is None:
        revision_id = session.extra.get("plan_revision_id")
        if revision_id:
            from mentora.learning.services import activate_revision

            try:
                activate_revision(str(revision_id))
            except Exception:
                pass
            plan = get_active_plan(resolved_session_id)
    if plan is None:
        return Response({"error": "未找到关联的学习计划"}, status=404)

    confirm_result = confirm_course_from_session(resolved_session_id)
    course_id = confirm_result["course_id"]

    course = Course.objects.get(id=course_id)
    profile = None
    if course.active_profile_revision_id:
        profile = CourseProfileRevision.objects.filter(
            id=course.active_profile_revision_id,
        ).first()

    if profile is None or profile.status != CourseProfileRevision.Status.ACTIVE:
        activate_course(course_id)
    revision_id = plan["revision_id"]

    archive_session(session)

    return JsonResponse({
        "status": "active",
        "revision_id": revision_id,
        "course_id": course_id,
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
        session = _get_session(session_id)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=404)

    if request.method == "GET":
        links = CourseSource.objects.filter(
            course_session_id=str(session.id),
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

    blocked = _ensure_session_writable(session)
    if blocked is not None:
        return JsonResponse({"error": "建课会话已归档，不可修改"}, status=409)

    # POST
    try:
        body = _parse_json(request)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    version_ids = body.get("source_version_ids", [])
    if not isinstance(version_ids, list):
        return JsonResponse({"error": "source_version_ids 必须是数组"}, status=400)

    # 幂等：先删后建
    CourseSource.objects.filter(course_session_id=str(session.id)).delete()

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
    return Response(result)


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
    from mentora.courses.models import CourseProfileRevision
    from mentora.courses.services import get_course_scope

    try:
        course, session, session_id = _resolve_course_context(str(course_id))
    except ValueError as exc:
        return Response({"error": str(exc)}, status=404)

    if course is None:
        return Response({
            "course_id": str(session.id),
            "goal": session.goal,
            "level": session.level,
            "pace": session.pace,
            "school": session.school,
            "status": session.status,
            "plan_revision_id": session.extra.get("plan_revision_id"),
            "source_version_ids": session.extra.get("source_version_ids", []),
            "created_at": session.created_at.isoformat(),
        })

    profile = None
    if course.active_profile_revision_id:
        try:
            profile = CourseProfileRevision.objects.get(id=course.active_profile_revision_id)
        except CourseProfileRevision.DoesNotExist:
            pass

    return Response({
        "course_id": str(course.id),
        "goal": profile.goal if profile else session.goal,
        "level": profile.level if profile else session.level,
        "pace": profile.pace if profile else session.pace,
        "school": profile.school if profile else session.school,
        "status": profile.status if profile else session.status,
        "plan_revision_id": str(profile.plan_revision_id) if profile and profile.plan_revision_id else session.extra.get("plan_revision_id"),
        "source_version_ids": get_course_scope(str(course.id)),
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


@extend_schema(
    summary="课程阶段列表",
    description="返回课程的学习阶段列表及计划调整影响范围。阶段状态按学习进度推导。",
    tags=["课程管理"],
    responses={
        200: {"description": "阶段列表 + 调整影响"},
        404: {"description": "课程不存在或无学习计划"},
    },
)
@api_view(["GET"])
def course_phases(request, course_id):
    """GET /api/courses/<course_id>/phases/"""
    from mentora.learning.models import LearningPlanRevision
    from mentora.learning.services import get_active_plan

    try:
        course, _session, _session_id = _resolve_course_context(str(course_id))
    except ValueError as exc:
        return Response({"error": str(exc)}, status=404)

    plan_resource = str(course.id) if course else str(course_id)
    plan_data = get_active_plan(plan_resource)
    if plan_data is None:
        return Response({"error": "该课程尚未生成学习计划"}, status=404)

    try:
        revision = LearningPlanRevision.objects.get(id=plan_data["revision_id"])
    except LearningPlanRevision.DoesNotExist:
        return Response({"phases": [], "adjustments": []})

    phases_qs = revision.phases.order_by("position")
    if not phases_qs.exists():
        # 尝试从 plan_snapshot_json 获取
        snapshot = revision.plan_snapshot_json or {}
        snapshot_phases = snapshot.get("phases", [])
        items = []
        for i, p in enumerate(snapshot_phases):
            units_count = len(p.get("units", []))
            items.append({
                "id": p.get("id", f"snapshot-phase-{i}"),
                "title": p.get("title", f"阶段 {i + 1}"),
                "position": i,
                "objective": p.get("objective", ""),
                "estimated_minutes": p.get("estimated_minutes", 0),
                "units_count": units_count,
                "completed_units": 0,
                "state": "completed" if i == 0 else ("active" if i == 1 else "upcoming"),
            })
        adjustments = snapshot.get("adjustments", [])
        return Response({"phases": items, "adjustments": adjustments})

    # 从 LearningPlanPhase 模型组装
    total_phases = phases_qs.count()
    items = []
    for phase in phases_qs:
        units_count = phase.units.count()
        # 阶段状态推导：position=0 已完成，最后一个有内容的为 active，其余 upcoming
        if phase.position == 0:
            state = "completed"
        elif phase.position == total_phases - 1:
            state = "active"
        else:
            state = "upcoming"

        items.append({
            "id": str(phase.id),
            "title": phase.title,
            "position": phase.position,
            "objective": phase.objective,
            "estimated_minutes": phase.estimated_minutes,
            "units_count": units_count,
            "completed_units": 0,
            "state": state,
        })

    # 调整影响从 validation_result_json 或 plan_snapshot_json 获取
    adjustments = (revision.validation_result_json or {}).get("adjustments", [])
    if not adjustments:
        adjustments = (revision.plan_snapshot_json or {}).get("adjustments", [])

    return Response({"phases": items, "adjustments": adjustments})


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
    try:
        gateway, prompt_mgr = _get_gateway_and_prompts()
    except RuntimeError as exc:
        return _gateway_unavailable_response(exc)

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


@extend_schema(
    summary="课程文件树",
    description="返回课程资料的文件树，按学习阶段分组。每个阶段为文件夹节点，内含该阶段关联的资料来源文件。",
    tags=["课程管理"],
    responses={
        200: {"description": "文件树"},
        404: {"description": "课程不存在"},
    },
)
@api_view(["GET"])
def course_files(request, course_id):
    """GET /api/courses/<course_id>/files/"""
    from mentora.knowledge.models import CourseSource
    from mentora.learning.models import LearningPlanRevision
    from mentora.learning.services import get_active_plan

    try:
        course, _session, session_id = _resolve_course_context(str(course_id))
    except ValueError as exc:
        return Response({"error": str(exc)}, status=404)

    plan_resource = str(course.id) if course else str(course_id)

    # 课程关联的资料来源
    source_links = CourseSource.objects.filter(
        course_session_id=session_id,
    ).select_related("source_version__source")

    source_map: dict[str, str] = {}
    for link in source_links:
        sv = link.source_version
        source_map[str(sv.id)] = sv.original_filename or sv.source.display_title or "未命名"

    tree: list[dict] = []
    plan_data = get_active_plan(plan_resource)
    if plan_data is not None:
        revision = LearningPlanRevision.objects.filter(id=plan_data["revision_id"]).first()
        if revision:
            phases_qs = revision.phases.order_by("position")
            for phase in phases_qs:
                children: list[dict] = []
                for unit in phase.units.all():
                    for tmpl in revision.task_templates.filter(unit=unit):
                        children.append({
                            "id": str(tmpl.id),
                            "name": f"{tmpl.get_task_type_display()} · {phase.title}",
                            "type": "file",
                            "extension": ".md" if tmpl.task_type == "lecture" else ".quiz",
                        })

                tree.append({
                    "id": str(phase.id),
                    "name": phase.title,
                    "type": "folder",
                    "children": children,
                })

    # 无阶段时，直接平铺所有 source 文件
    if not tree and source_links:
        flat_children: list[dict] = []
        for link in source_links:
            sv = link.source_version
            flat_children.append({
                "id": str(sv.id),
                "name": sv.original_filename or sv.source.display_title,
                "type": "file",
                "extension": f".{sv.source.file_type}" if hasattr(sv.source, "file_type") else ".pdf",
            })
        tree.append({
            "id": "all-sources",
            "name": "全部资料",
            "type": "folder",
            "children": flat_children,
        })

    return Response({"tree": tree})
