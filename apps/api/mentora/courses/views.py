"""
建课会话 HTTP 视图：Session CRUD + Inquiry 追问 + Plan 方案生成。

约定：
- 视图函数风格（与 knowledge/views.py 一致），不使用 DRF ViewSet
- 所有端点 csrf_exempt，生产环境需配合 Token 认证
- inquiry 和 plan 端点调用 model_gateway + Pydantic schema 校验
- 复用 agent_runtime/views 中的单例 gateway / prompt_manager

@module mentora/courses/views
"""

import asyncio
import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

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


@csrf_exempt
@require_http_methods(["POST"])
def session_create(request):
    """
    POST /api/courses/sessions/

    请求体：{ "goal": "学习目标文本" }
    返回：{ "id": "...", "goal": "...", "status": "..." }
    """
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


@csrf_exempt
@require_http_methods(["POST"])
def plan_generate(request, session_id):
    """
    POST /api/courses/sessions/<uuid:id>/plan/

    返回：{ "phases": [{ "name", "goal", "share", "tasks" }] }

    约束：
    - 基于会话中全部已收集信息生成方案
    - 方案不在数据库持久化
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

    session.status = SessionStatus.COMPLETED
    session.save(update_fields=["status", "updated_at"])

    return JsonResponse(resp.parsed_output)


# ── Profile Candidates 画像候选项 ──


@csrf_exempt
@require_http_methods(["POST"])
def profile_candidates(request, session_id):
    """
    POST /api/courses/sessions/<uuid:id>/candidates/

    基于追问历史生成 2-4 个差异化画像方案供学生选择。
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
        return JsonResponse({"error": f"LLM 调用失败: {str(exc)}"}, status=502)

    if resp.parsed_output is None:
        return JsonResponse(
            {"error": "LLM 返回格式异常", "raw_content": resp.content},
            status=502,
        )

    return JsonResponse(resp.parsed_output)


# ── Course 管理 ──


@csrf_exempt
@require_http_methods(["POST"])
def course_confirm(request):
    """
    POST /api/courses/confirm/

    请求体：{"session_id": "..."}
    返回：{course_id, profile_revision_id, scope_revision_id, source_version_ids}
    """
    try:
        body = _parse_json(request)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    session_id = body.get("session_id", "")
    if not session_id:
        return JsonResponse({"error": "缺少 session_id"}, status=400)

    from mentora.courses.services import confirm_course_from_session

    try:
        result = confirm_course_from_session(session_id)
        return JsonResponse(result, status=201)
    except CourseCreationSession.DoesNotExist:
        return JsonResponse({"error": f"会话 {session_id} 不存在"}, status=404)
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=500)


@csrf_exempt
@require_http_methods(["GET"])
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
        return JsonResponse({"error": "课程不存在"}, status=404)

    profile = None
    if course.active_profile_revision_id:
        try:
            profile = CourseProfileRevision.objects.get(id=course.active_profile_revision_id)
        except CourseProfileRevision.DoesNotExist:
            pass

    return JsonResponse({
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


@csrf_exempt
@require_http_methods(["PATCH"])
def course_profile_revise(request, course_id):
    """
    PATCH /api/courses/<uuid:id>/profile/

    请求体：{"goal"?, "level"?, "pace"?, "school"?}
    返回：{profile_revision_id, status, goal, ...}
    """
    try:
        body = _parse_json(request)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    from mentora.courses.services import revise_profile

    kwargs = {k: v for k, v in body.items()
              if k in ("goal", "level", "pace", "school", "topics_json", "plan_revision_id")}
    if not kwargs:
        return JsonResponse({"error": "无有效字段"}, status=400)

    try:
        result = revise_profile(course_id, **kwargs)
        return JsonResponse(result)
    except Course.DoesNotExist:
        return JsonResponse({"error": "课程不存在"}, status=404)
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def course_scope_extend(request, course_id):
    """
    POST /api/courses/<uuid:id>/scope/

    请求体：{"source_version_ids": [...], "role"?: "reference"}
    返回：{scope_revision_id, source_version_ids, superseded_revision_id}
    """
    try:
        body = _parse_json(request)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    sv_ids = body.get("source_version_ids", [])
    if not sv_ids:
        return JsonResponse({"error": "缺少 source_version_ids"}, status=400)

    from mentora.courses.services import extend_scope

    role = body.get("role", "reference")
    try:
        result = extend_scope(course_id, sv_ids, role=role)
        return JsonResponse(result)
    except Course.DoesNotExist:
        return JsonResponse({"error": "课程不存在"}, status=404)
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def course_activate(request, course_id):
    """
    POST /api/courses/<uuid:id>/activate/

    激活课程画像 + 联动激活 LearningPlan。
    """
    from mentora.courses.services import activate_course

    try:
        result = activate_course(course_id)
        return JsonResponse(result)
    except Course.DoesNotExist:
        return JsonResponse({"error": "课程不存在"}, status=404)
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=500)
