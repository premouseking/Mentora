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

from django.db import DatabaseError
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from rest_framework.response import Response
from rest_framework.decorators import api_view
from drf_spectacular.utils import extend_schema

from mentora.courses.models import CourseCreationSession, SessionStatus
from mentora.courses.scope_planning import (
    assess_scope_coverage,
    build_source_evidence_context,
    build_source_scope_summary,
    get_allowed_evidence_ids,
    get_scoped_evidence_for_planner,
    get_session_source_version_ids,
    get_source_titles,
    sanitize_plan_evidence_ids,
    validate_plan_evidence_ids,
)
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


def _get_session(session_id: str, owner) -> CourseCreationSession:
    """按 UUID 获取会话，不存在时抛 ValueError。"""
    try:
        return CourseCreationSession.objects.get(id=session_id, owner=owner)
    except CourseCreationSession.DoesNotExist:
        raise ValueError(f"会话 {session_id} 不存在")


def _get_gateway_and_prompts():
    """延迟导入，获取单例 gateway 和 prompt_manager。"""
    from mentora.agent_runtime.views import get_gateway, get_prompt_manager

    return get_gateway(), get_prompt_manager()


def _gateway_unavailable_response(exc: Exception) -> Response:
    return Response({"error": str(exc)}, status=503)


def _rebuild_profile_supplement(session: CourseCreationSession) -> None:
    """从 inquiry_history 重建 profile_supplement。"""
    supplement: dict[str, str] = {}
    for entry in session.inquiry_history or []:
        question = (entry.get("question") or "").strip()
        answer = (entry.get("answer") or "").strip()
        if question and answer:
            supplement[question] = answer
    session.profile_supplement = supplement


def _clear_session_scope_state(session: CourseCreationSession) -> None:
    """学习目标变化后丢弃旧追问、资料绑定与方案缓存，避免串课。"""
    from mentora.knowledge.models import CourseSource

    session.inquiry_history = []
    session.profile_supplement = {}
    session.status = SessionStatus.COLLECTING
    extra = dict(session.extra or {})
    extra.pop("source_version_ids", None)
    extra.pop("plan_revision_id", None)
    session.extra = extra
    CourseSource.objects.filter(course_session_id=str(session.id)).delete()


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


def _course_ids_by_session_id(session_ids: list[str], owner) -> dict[str, str]:
    """按 session_id 批量查 course_id；表未迁移时降级为空映射。"""
    if not session_ids:
        return {}
    try:
        from mentora.courses.models import Course

        return {
            str(course.session_id): str(course.id)
            for course in Course.objects.filter(session_id__in=session_ids, owner=owner).only("id", "session_id")
        }
    except DatabaseError:
        return {}


def _serialize_session_list_item(
    session: CourseCreationSession,
    course_by_session: dict[str, str],
) -> dict:
    return {
        "id": str(session.id),
        "course_id": course_by_session.get(str(session.id)),
        "goal": session.goal,
        "title": session.title,
        "status": session.status,
        "level": session.level,
        "pace": session.pace,
        "time_budget": session.time_budget,
        "school": session.school,
        "deadline": session.deadline.isoformat() if session.deadline else None,
        "current_phase": None,
        "next_task": None,
        "created_at": session.created_at.isoformat(),
        "updated_at": session.updated_at.isoformat(),
        "last_studied_at": session.last_studied_at.isoformat() if session.last_studied_at else None,
        "archived_at": session.archived_at.isoformat() if session.archived_at else None,
    }


# ── Session CRUD ──


@api_view(["GET", "POST"])
@extend_schema(summary="Session List Or Create")
def session_list_or_create(request):
    """
    GET  /api/courses/sessions/ → 列出所有建课会话
    POST /api/courses/sessions/ → 创建新会话
    """
    if request.method == "GET":
        try:
            limit = min(max(int(request.GET.get("limit", 100)), 1), 500)
            offset = max(int(request.GET.get("offset", 0)), 0)
            archived_param = request.GET.get("archived", "").strip().lower()
            qs = CourseCreationSession.objects.filter(owner=request.user).order_by("-updated_at")
            if archived_param in ("1", "true", "yes"):
                qs = qs.filter(archived_at__isnull=False)
            else:
                qs = qs.filter(archived_at__isnull=True)
            sessions = list(qs[offset: offset + limit])
            total = qs.count()
            course_by_session = _course_ids_by_session_id(
                [str(session.id) for session in sessions], request.user,
            )
            data = [
                _serialize_session_list_item(session, course_by_session)
                for session in sessions
            ]
            return Response({
                "items": data,
                "count": total,
                "limit": limit,
                "offset": offset,
            })
        except DatabaseError as exc:
            return Response(
                {"error": f"课程数据不可用，请确认数据库已启动并已执行 migrate：{exc}"},
                status=503,
            )

    # POST
    try:
        body = _parse_json(request)
    except ValueError as exc:
        return Response({"error": str(exc)}, status=400)

    serializer = SessionCreateSerializer(data=body)
    if not serializer.is_valid():
        return Response({"error": serializer.errors}, status=400)

    session = serializer.save(owner=request.user)
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
        session = _get_session(session_id, request.user)
    except ValueError as exc:
        return Response({"error": str(exc)}, status=404)

    data = SessionDetailSerializer(session).data
    data["id"] = str(data["id"])
    source_version_ids = get_session_source_version_ids(session)
    data["source_version_ids"] = source_version_ids
    if source_version_ids:
        titles = get_source_titles(source_version_ids)
        data["sources"] = [
            {
                "sourceVersionId": sid,
                "displayTitle": titles.get(sid, sid),
            }
            for sid in source_version_ids
        ]
    else:
        data["sources"] = []
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
        session = _get_session(session_id, request.user)
    except ValueError as exc:
        return Response({"error": str(exc)}, status=404)

    try:
        body = _parse_json(request)
    except ValueError as exc:
        return Response({"error": str(exc)}, status=400)

    old_goal = (session.goal or "").strip()

    serializer = SessionUpdateSerializer(session, data=body, partial=True)
    if not serializer.is_valid():
        return Response({"error": serializer.errors}, status=400)

    serializer.save()
    new_goal = (session.goal or "").strip()
    if old_goal and new_goal and old_goal != new_goal:
        _clear_session_scope_state(session)
        session.save(
            update_fields=[
                "inquiry_history",
                "profile_supplement",
                "status",
                "extra",
                "updated_at",
            ]
        )
    if "inquiry_history" in body:
        _rebuild_profile_supplement(session)
        session.save(update_fields=["profile_supplement", "updated_at"])
    return Response({"status": "ok"})


@extend_schema(
    summary="删除建课会话",
    responses={200: {"description": "删除成功"}, 404: {"description": "会话不存在"}},
)
@api_view(["DELETE"])
def session_delete(request, session_id):
    try:
        session = _get_session(session_id, request.user)
    except ValueError as exc:
        return Response({"error": str(exc)}, status=404)
    session.delete()
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
        session = _get_session(session_id, request.user)
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
        detail = str(exc)
        if isinstance(exc, TimeoutError) or "Timeout" in type(exc).__name__:
            detail = "模型响应超时，请稍后重试"
        return Response(
            {"error": f"LLM 调用失败: {detail}"},
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
        _rebuild_profile_supplement(session)
        session.save(update_fields=["status", "inquiry_history", "profile_supplement", "updated_at"])

    return Response(result)


# ── Plan 方案生成 ──


def _plan_to_learning_snapshot(plan_output: dict) -> dict:
    """将 PlanResponse JSON 映射为 learning 模块的 plan_snapshot 格式。

    映射规则：
    - PlanPhase → LearningPlanPhase
    - PlanUnit → LearningPlanUnit
    - PlanTask → LearningPlanTaskTemplate
    - 若收到旧版 phases.tasks[] 字符串列表，则向后兼容为单 unit 结构
    """
    phases: list[dict] = []
    for phase_data in plan_output.get("phases", []):
        phase_title = phase_data.get("name", "未命名阶段")
        phase_goal = phase_data.get("goal", "")
        share = phase_data.get("share", 25)
        units_input = phase_data.get("units") or []
        if not units_input and phase_data.get("tasks"):
            legacy_tasks = phase_data.get("tasks", [])
            estimated = max(30, share * 12)
            units_input = [{
                "title": phase_title,
                "goal": phase_goal,
                "target_depth": "basic",
                "estimated_minutes": estimated,
                "tasks": [
                    {
                        "title": str(task_text).strip(),
                        "task_type": "lecture",
                        "delivery_mode": "text",
                        "estimated_minutes": max(10, estimated // max(len(legacy_tasks), 1)),
                        "required": True,
                    }
                    for task_text in legacy_tasks
                ],
            }]

        units: list[dict] = []
        phase_estimated = 0
        for unit_index, unit_data in enumerate(units_input):
            tasks: list[dict] = []
            unit_estimated = int(unit_data.get("estimated_minutes") or 0)
            raw_tasks = unit_data.get("tasks", [])
            for task_data in raw_tasks:
                if isinstance(task_data, str):
                    title = task_data.strip()
                    normalized = {
                        "title": title,
                        "task_type": "lecture",
                        "delivery_mode": "text",
                        "estimated_minutes": 30,
                        "required": True,
                    }
                else:
                    title = str(task_data.get("title", "")).strip()
                    normalized = {
                        "title": title,
                        "task_type": task_data.get("task_type", "lecture"),
                        "delivery_mode": task_data.get("delivery_mode", "text"),
                        "estimated_minutes": int(task_data.get("estimated_minutes") or 30),
                        "required": bool(task_data.get("required", True)),
                    }
                    evidence_ids = task_data.get("source_evidence_ids") or []
                    if evidence_ids:
                        normalized["source_evidence_ids"] = [
                            str(eid).strip() for eid in evidence_ids if str(eid).strip()
                        ]
                tasks.append(normalized)

            if unit_estimated <= 0:
                unit_estimated = sum(t["estimated_minutes"] for t in tasks)
            if unit_estimated <= 0:
                unit_estimated = max(30, share * 12)

            phase_estimated += unit_estimated
            unit_payload = {
                "id": str(uuid.uuid4()),
                "title": unit_data.get("title", f"{phase_title}-{unit_index + 1}"),
                "position": unit_index,
                "target_depth": unit_data.get("target_depth", "basic"),
                "estimated_minutes": unit_estimated,
                "prerequisite_unit_ids": unit_data.get("prerequisite_unit_ids", []),
                "priority": unit_data.get("priority", 0),
                "tasks": tasks,
            }
            unit_evidence_ids = unit_data.get("source_evidence_ids") or []
            if unit_evidence_ids:
                unit_payload["source_evidence_ids"] = [
                    str(eid).strip() for eid in unit_evidence_ids if str(eid).strip()
                ]
            units.append(unit_payload)

        phases.append({
            "title": phase_title,
            "objective": phase_goal,
            "estimated_minutes": phase_estimated or max(30, share * 12),
            "position": len(phases),
            "units": units,
        })

    snapshot = {
        "total_budget_minutes": sum(p["estimated_minutes"] for p in phases),
        "phases": phases,
    }
    metadata = plan_output.get("metadata") or {}
    if metadata:
        snapshot["metadata"] = metadata
    return snapshot


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
        _get_session(session_id, request.user)
    except ValueError as exc:
        return Response({"error": str(exc)}, status=404)

    from mentora.learning.services import get_active_plan
    from mentora.topics.services import get_topic_tree

    plan = get_active_plan(session_id)
    if plan is None:
        return Response({"error": "该课程尚未生成学习方案"}, status=404)

    plan["topics"] = get_topic_tree(session_id)
    return Response(plan)


def _plan_generate(request, session_id):
    """
    POST /api/courses/sessions/<uuid:id>/plan/

    返回：{ "phases": [{ "name", "goal", "share", "tasks" }], "revision_id": "..." }

    约束：
    - 基于会话中全部已收集信息生成方案
    - 若用户选择了参考资料，则严格受资料白名单约束
    - 方案同步持久化到 learning 模块（status=draft）
    """
    try:
        session = _get_session(session_id, request.user)
    except ValueError as exc:
        return Response({"error": str(exc)}, status=404)

    try:
        body = _parse_json(request)
    except ValueError as exc:
        return Response({"error": str(exc)}, status=400)

    allow_partial_plan = bool(body.get("allow_partial_plan"))

    source_version_ids = get_session_source_version_ids(session)
    scope_constrained = len(source_version_ids) > 0
    source_titles = get_source_titles(source_version_ids) if scope_constrained else {}
    evidence_units = get_scoped_evidence_for_planner(source_version_ids) if scope_constrained else []
    allowed_evidence_ids = get_allowed_evidence_ids(source_version_ids) if scope_constrained else set()

    if scope_constrained:
        sufficient, coverage_gaps = assess_scope_coverage(
            session.goal or "",
            evidence_units,
            source_version_ids,
        )
        if not sufficient and not allow_partial_plan:
            return Response(
                {
                    "error": "所选资料不足以覆盖当前学习目标，请补充资料或确认按现有资料部分生成。",
                    "code": "insufficient_scope",
                    "coverage_gaps": coverage_gaps,
                },
                status=409,
            )

    try:
        gateway, prompt_mgr = _get_gateway_and_prompts()
    except RuntimeError as exc:
        return _gateway_unavailable_response(exc)

    import json as _json
    variables = {
        "school": session.school or "未填写",
        "goal": session.goal or "未填写",
        "level": session.level or "未选择",
        "pace": session.pace or "未选择",
        "inquiry_history": _format_history(session.inquiry_history),
        "profile_supplement": _json.dumps(session.profile_supplement, ensure_ascii=False) if session.profile_supplement else "（无补充信息）",
        "source_scope_summary": build_source_scope_summary(source_version_ids, source_titles),
        "source_evidence_context": build_source_evidence_context(evidence_units, source_titles),
        "allow_partial_plan": "true" if allow_partial_plan else "false",
    }
    system_text = prompt_mgr.render("planner", variables)

    user_instruction = "请根据以上全部信息，生成一份阶段化学习方案。"
    if scope_constrained:
        user_instruction += " 必须严格基于资料证据白名单组织章节与任务，不得生成资料外内容。"

    messages = [
        Message(role="system", content=system_text),
        Message(role="user", content=user_instruction),
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
        detail = str(exc)
        if isinstance(exc, TimeoutError) or "Timeout" in type(exc).__name__:
            detail = "模型响应超时，请稍后重试（学习方案生成通常需要 1-3 分钟）"
        return Response(
            {"error": f"LLM 调用失败: {detail}"},
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

    plan_output: dict = resp.parsed_output  # type: ignore[assignment]
    sanitized_evidence_ids: list[str] = []

    if scope_constrained:
        invalid_ids = validate_plan_evidence_ids(plan_output, allowed_evidence_ids)
        if invalid_ids:
            sanitized_evidence_ids = sanitize_plan_evidence_ids(plan_output, allowed_evidence_ids)
            still_invalid = validate_plan_evidence_ids(plan_output, allowed_evidence_ids)
            if still_invalid:
                return Response(
                    {
                        "error": "生成方案引用了资料范围外的证据，请重试。",
                        "code": "invalid_scope_evidence",
                        "invalid_evidence_ids": still_invalid,
                    },
                    status=502,
                )

    # 存储 LLM 生成的标题
    course_title = plan_output.get("title", "").strip()
    if course_title:
        session.title = course_title

    revision_id = ""
    try:
        from mentora.learning.services import create_plan_revision, activate_revision

        plan_output["metadata"] = {
            "source_version_ids": source_version_ids,
            "scope_constrained": scope_constrained,
            "allow_partial_plan": allow_partial_plan,
            "coverage_gaps": plan_output.get("coverage_gaps") or [],
            **({"sanitized_evidence_ids": sanitized_evidence_ids} if sanitized_evidence_ids else {}),
        }
        snapshot = _plan_to_learning_snapshot(plan_output)
        revision = create_plan_revision(
            course_session_id=session_id,
            plan_snapshot=snapshot,
            profile_revision_id="",
            knowledge_scope_revision_id="",
        )
        revision_id = revision["revision_id"]
        session.extra = {
            **(session.extra or {}),
            "plan_revision_id": revision_id,
            "source_version_ids": source_version_ids,
        }
        activate_revision(revision_id)

        # 自动构建主题树 + 证据关联（LLM 输出中的 topics）
        topics_data = plan_output.get("topics", [])
        if topics_data:
            from mentora.topics.models import Topic
            from mentora.topics.services import build_topic_tree, link_evidence

            build_topic_tree(session_id, [
                {"name": t["name"], "level": 0, "position": idx,
                 "estimated_minutes": 0}
                for idx, t in enumerate(topics_data)
            ])
            for t in topics_data:
                eids = t.get("evidence_ids", [])
                if eids:
                    topic = Topic.objects.filter(
                        course_id=session_id, name=t["name"]
                    ).first()
                    if topic:
                        link_evidence(str(topic.id), eids)
    except Exception as e:
        import logging
        logging.getLogger(__name__).exception("Plan persist failed for session %s: %s", session_id, e)

    session.status = SessionStatus.COMPLETED
    session.save(update_fields=["title", "status", "extra", "updated_at"])

    return Response({**plan_output, "revision_id": revision_id})


# ── 开始学习 ──


@api_view(["POST"])
@extend_schema(summary="Session Start")
def session_start(request, session_id):
    """
    POST /api/courses/sessions/<uuid:id>/start/

    1. 确认课程（如未 confirm 则先创建 Course 记录）
    2. 激活 learning 模块中的 plan revision
    3. 会话状态置为 STARTED

    返回：{ "status": "started", "revision_id": "...", "course_id": "..." }
    """
    try:
        session = _get_session(session_id, request.user)
    except ValueError as exc:
        return Response({"error": str(exc)}, status=404)

    if session.status != SessionStatus.COMPLETED:
        return Response(
            {"error": "方案尚未生成，无法开始学习"},
            status=400,
        )

    # 1. 确认课程——如 Course 不存在则创建（幂等）
    from mentora.courses.models import Course
    from mentora.courses.services import confirm_course_from_session

    course = Course.objects.filter(session=session).first()
    if course is None:
        try:
            result = confirm_course_from_session(session_id, owner=request.user)
            course = Course.objects.get(session=session)
        except Exception as exc:
            return Response({"error": f"课程确认失败: {exc}"}, status=500)
    course_id = str(course.id)

    # 2. 激活计划
    from mentora.learning.services import activate_revision, get_active_plan

    plan = get_active_plan(session_id)
    if plan is None:
        return Response({"error": "未找到关联的学习计划"}, status=404)

    result = activate_revision(plan["revision_id"])

    session.status = SessionStatus.STARTED
    session.save(update_fields=["status", "updated_at"])

    # 写入学习历史
    from mentora.learning.services import write_history_event

    write_history_event(
        course_id=course_id,
        course_title=session.title or session.goal,
        event_type="course_started",
        title="开始学习课程",
        detail=session.goal or "",
        result="started",
        task_id=str(session.id),
    )

    return JsonResponse({
        "status": "started",
        "revision_id": result["active_revision_id"],
        "course_id": course_id,
        "session_id": str(session.id),
    })


# ── 课程资料关联 ──


@api_view(["POST"])
@extend_schema(summary="Preview source coverage for session")
def session_source_coverage_preview(request, session_id):
    """
    POST /api/courses/sessions/<uuid:id>/sources/coverage-preview/

    请求体：{ "source_version_ids": ["uuid1", ...] }（可选，默认读 session 已绑定资料）
    返回：{ "sufficient", "gaps", "sources" }
    """
    try:
        session = _get_session(session_id, request.user)
    except ValueError as exc:
        return Response({"error": str(exc)}, status=404)

    try:
        body = _parse_json(request)
    except ValueError as exc:
        return Response({"error": str(exc)}, status=400)

    version_ids = body.get("source_version_ids")
    if version_ids is None:
        version_ids = get_session_source_version_ids(session)
    if not isinstance(version_ids, list):
        return Response({"error": "source_version_ids 必须是数组"}, status=400)

    version_ids = [str(item).strip() for item in version_ids if str(item).strip()]
    if not version_ids:
        return Response({"error": "请至少选择 1 份已解析资料"}, status=400)

    source_titles = get_source_titles(version_ids)
    evidence_units = get_scoped_evidence_for_planner(version_ids)
    sufficient, gaps = assess_scope_coverage(
        session.goal,
        evidence_units,
        version_ids,
    )
    return Response({
        "sufficient": sufficient,
        "gaps": gaps,
        "sources": [
            {
                "sourceVersionId": sid,
                "displayTitle": source_titles.get(sid, sid),
            }
            for sid in version_ids
        ],
    })


@api_view(["GET", "POST"])
def course_sources_manage(request, session_id):
    """
    GET  /api/courses/sessions/<uuid:id>/sources/  → 查课程已关联资料
    POST /api/courses/sessions/<uuid:id>/sources/  → 批量设置关联

    POST body: { "source_version_ids": ["uuid1", "uuid2", ...] }
    注意：为幂等安全，先删后建，而非增量合并。
    """
    from mentora.knowledge.models import CourseSource, Source, SourceStatus, SourceVersion

    try:
        _get_session(session_id, request.user)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=404)

    if request.method == "GET":
        include_archived = request.GET.get("includeArchived", "").lower() in ("1", "true", "yes")
        links = CourseSource.objects.filter(
            course_session_id=session_id,
            source_version__source__owner=request.user,
        ).select_related("source_version__source")
        if not include_archived:
            links = links.filter(archived_at__isnull=True)
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
                "archivedAt": link.archived_at.isoformat() if link.archived_at else None,
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

    owned_versions = list(SourceVersion.objects.select_related("source").filter(
        id__in=version_ids,
        source__owner=request.user,
        source__status=SourceStatus.ACTIVE,
    ))
    if len(owned_versions) != len(set(version_ids)):
        return JsonResponse({"error": "资料不存在或无权访问"}, status=404)

    # 完整验证后再替换，避免失败时丢失原关联。
    CourseSource.objects.filter(course_session_id=session_id).delete()

    created = 0
    for sv in owned_versions:
        CourseSource.objects.get_or_create(
            course_session_id=session_id,
            source_version=sv,
        )
        created += 1

    # 同步写入 session.extra，供 course_confirm 创建作用域时使用
    session = _get_session(session_id, request.user)
    persisted_ids = [str(sv.id) for sv in owned_versions]
    session.extra = {**(session.extra or {}), "source_version_ids": persisted_ids}
    session.save(update_fields=["extra", "updated_at"])

    return JsonResponse({"status": "ok", "source_count": created})


@api_view(["PATCH"])
def course_source_archive(request, session_id, source_version_id):
    """PATCH /api/courses/sessions/<id>/sources/<source_version_id>/archive/"""
    from django.utils import timezone

    from mentora.knowledge.models import CourseSource

    try:
        _get_session(session_id, request.user)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=404)

    updated = CourseSource.objects.filter(
        course_session_id=session_id,
        source_version_id=source_version_id,
    ).update(archived_at=timezone.now())
    if not updated:
        return JsonResponse({"error": "课程资料关联不存在"}, status=404)
    return JsonResponse({"status": "archived"})


@api_view(["PATCH"])
def course_source_unarchive(request, session_id, source_version_id):
    """PATCH /api/courses/sessions/<id>/sources/<source_version_id>/unarchive/"""
    from mentora.knowledge.models import CourseSource

    try:
        _get_session(session_id, request.user)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=404)

    updated = CourseSource.objects.filter(
        course_session_id=session_id,
        source_version_id=source_version_id,
    ).update(archived_at=None)
    if not updated:
        return JsonResponse({"error": "课程资料关联不存在"}, status=404)
    return JsonResponse({"status": "active"})


@api_view(["PATCH"])
def session_archive(request, session_id):
    """PATCH /api/courses/sessions/<id>/archive/ — 软归档，保留数据。"""
    from django.utils import timezone

    try:
        session = _get_session(session_id, request.user)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=404)

    session.archived_at = timezone.now()
    session.save(update_fields=["archived_at", "updated_at"])
    return JsonResponse({"status": "archived", "archived_at": session.archived_at.isoformat()})


@api_view(["PATCH"])
def session_unarchive(request, session_id):
    """PATCH /api/courses/sessions/<id>/unarchive/"""
    try:
        session = _get_session(session_id, request.user)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=404)

    session.archived_at = None
    session.save(update_fields=["archived_at", "updated_at"])
    return JsonResponse({"status": "active"})


# ── 删除课程 ──


@api_view(["DELETE"])
def session_delete(request, session_id):
    """
    DELETE /api/courses/sessions/<uuid:id>/

    删除建课会话及其课程资料关联。
    """
    try:
        session = _get_session(session_id, request.user)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=404)

    from mentora.knowledge.models import CourseSource

    # 清理课程资料关联（非 FK，需手动删）
    CourseSource.objects.filter(course_session_id=session_id).delete()
    session.delete()

    return JsonResponse({"status": "deleted"})


# ── Course list ──


@api_view(["GET"])
@extend_schema(summary="Course List")
def course_list(request):
    """
    GET /api/courses/

    返回课程列表（按创建时间倒序）。
    """
    from mentora.courses.models import Course, CourseProfileRevision
    courses = Course.objects.filter(owner=request.user).order_by("-created_at").values(
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
        _get_session(session_id, request.user)
        result = confirm_course_from_session(session_id, owner=request.user)
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
        course = Course.objects.get(id=course_id, owner=request.user)
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
        "session_id": str(course.session_id),
        "goal": profile.goal if profile else "",
        "level": profile.level if profile else "",
        "pace": profile.pace if profile else "",
        "school": profile.school if profile else "",
        "status": profile.status if profile else "",
        "plan_revision_id": str(profile.plan_revision_id) if profile and profile.plan_revision_id else None,
        "source_version_ids": get_course_scope(course_id, owner=request.user),
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
        result = revise_profile(course_id, owner=request.user, **kwargs)
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
        result = extend_scope(course_id, sv_ids, role=role, owner=request.user)
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
        result = suggest_scope_updates(course_id, owner=request.user)
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
    from mentora.courses.models import Course
    from mentora.learning.models import LearningPlan, LearningPlanRevision

    # 统一路径 A：先有 Course 记录
    try:
        course = Course.objects.get(id=course_id, owner=request.user)
    except Course.DoesNotExist:
        return Response({"error": "课程不存在"}, status=404)
    session_id = str(course.session.id)

    try:
        plan = LearningPlan.objects.get(course_session_id=session_id)
    except LearningPlan.DoesNotExist:
        return Response({"error": "该课程尚未生成学习计划"}, status=404)

    if not plan.active_revision_id:
        return Response({"phases": [], "adjustments": []})

    try:
        revision = LearningPlanRevision.objects.get(id=plan.active_revision_id)
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
                "state": "completed" if i == 0 else ("active" if i == len(snapshot_phases) - 1 else "upcoming"),
            })
        adjustments = snapshot.get("adjustments", [])
        return Response({"phases": items, "adjustments": adjustments})

    # 从 LearningPlanPhase 模型组装
    from mentora.learning.models import LearningTask

    # 统计各 phase 的任务完成情况
    phase_task_stats = {}
    tasks = LearningTask.objects.filter(
        revision=revision,
    ).values("unit__phase_id", "status", "required")
    for t in tasks:
        pid = str(t["unit__phase_id"])
        if pid not in phase_task_stats:
            phase_task_stats[pid] = {"total_required": 0, "completed_required": 0}
        if t["required"]:
            phase_task_stats[pid]["total_required"] += 1
            if t["status"] == LearningTask.Status.COMPLETED:
                phase_task_stats[pid]["completed_required"] += 1

    items = []
    for phase in phases_qs:
        pid = str(phase.id)
        stats = phase_task_stats.get(pid, {"total_required": 0, "completed_required": 0})
        units_count = phase.units.count()

        if stats["total_required"] == 0:
            state = "upcoming"
        elif stats["completed_required"] >= stats["total_required"]:
            state = "completed"
        elif stats["completed_required"] > 0:
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
            "completed_units": stats["completed_required"],
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
        course = Course.objects.get(id=course_id, owner=request.user)
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
        detail = str(exc)
        if isinstance(exc, TimeoutError) or "Timeout" in type(exc).__name__:
            detail = "模型响应超时，请稍后重试（学习方案生成通常需要 1-3 分钟）"
        return Response({"error": f"LLM 调用失败: {detail}"}, status=502)

    if resp.parsed_output is None:
        return Response({"error": "LLM 返回格式异常"}, status=502)

    plan_output = resp.parsed_output

    # 2. 持久化计划
    from mentora.learning.services import create_plan_revision

    plan_result = create_plan_revision(
        course_session_id=str(session.id),
        plan_snapshot=_plan_to_learning_snapshot(plan_output),
        profile_revision_id=str(profile.id),
    )

    profile.plan_revision_id = plan_result["revision_id"]
    profile.save(update_fields=["plan_revision_id"])

    # 3. 确认 + 激活
    profile.status = CourseProfileRevision.Status.CONFIRMED
    profile.save(update_fields=["status"])

    try:
        result = activate_course(course_id, owner=request.user)
    except Exception as exc:
        return Response({"error": str(exc)}, status=500)

    # 写入学习历史
    from mentora.learning.services import write_history_event

    write_history_event(
        course_id=course_id,
        course_title=session.title or session.goal,
        event_type="plan_adjusted",
        title="学习计划已激活",
        detail=f"阶段数: {len(plan_output.get('phases', []))}",
        result="activated",
        task_id=str(session.id),
    )

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
    from mentora.courses.models import Course
    from mentora.knowledge.models import CourseSource

    try:
        course = Course.objects.get(id=course_id, owner=request.user)
    except Course.DoesNotExist:
        return Response({"error": "课程不存在"}, status=404)
    session_id = str(course.session.id)

    # 课程关联的资料来源
    source_links = CourseSource.objects.filter(
        course_session_id=session_id,
        archived_at__isnull=True,
    ).select_related("source_version__source")

    source_map: dict[str, str] = {}
    for link in source_links:
        sv = link.source_version
        source_map[str(sv.id)] = sv.original_filename or sv.source.display_title or "未命名"

    # 学习计划阶段 → 文件夹结构
    from mentora.learning.models import LearningPlan, LearningPlanRevision

    tree: list[dict] = []
    try:
        plan = LearningPlan.objects.get(course_session_id=session_id)
        if plan.active_revision_id:
            revision = LearningPlanRevision.objects.filter(
                id=plan.active_revision_id,
            ).first()
            if revision:
                phases_qs = revision.phases.order_by("position")
                for phase in phases_qs:
                    children: list[dict] = []
                    for unit in phase.units.all():
                        for task in unit.tasks.all():
                            for mat in task.materials:
                                name = source_map.get(mat.get("id", ""), mat.get("title", "资料"))
                                children.append({
                                    "id": mat.get("id", ""),
                                    "name": name,
                                    "type": "file",
                                    "extension": ".md" if task.task_type == "lecture" else ".quiz",
                                })

                    tree.append({
                        "id": str(phase.id),
                        "name": phase.title,
                        "type": "folder",
                        "children": children,
                    })
    except LearningPlan.DoesNotExist:
        pass

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
