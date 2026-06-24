from django.http import JsonResponse
from django.urls import path

from mentora.agent_runtime.views import chat_api, chat_stream
from mentora.courses.views import (
    course_activate,
    course_confirm,
    course_detail,
    course_profile_revise,
    course_scope_extend,
    inquiry_next,
    plan_generate,
    session_create,
    session_detail,
    session_update,
)
from mentora.knowledge.views import list_sources, upload_complete, upload_create
from mentora.parsing.views import get_benchmark, preview_parse
from mentora.retrieval.views import locate_view, search_view


def health(_: object) -> JsonResponse:
    return JsonResponse({"status": "ok", "service": "mentora-api"})


urlpatterns = [
    path("api/health/", health, name="health"),
    # 聊天
    path("api/chat/", chat_api, name="chat"),
    path("api/chat/stream/", chat_stream, name="chat-stream"),
    # 建课会话
    path("api/courses/sessions/", session_create, name="session-create"),
    path("api/courses/sessions/<uuid:session_id>/", session_detail, name="session-detail"),
    path("api/courses/sessions/<uuid:session_id>/update/", session_update, name="session-update"),
    path("api/courses/sessions/<uuid:session_id>/inquiry/", inquiry_next, name="inquiry-next"),
    path("api/courses/sessions/<uuid:session_id>/plan/", plan_generate, name="plan-generate"),
    # 课程管理
    path("api/courses/confirm/", course_confirm, name="course-confirm"),
    path("api/courses/<uuid:course_id>/", course_detail, name="course-detail"),
    path("api/courses/<uuid:course_id>/profile/", course_profile_revise, name="course-profile-revise"),
    path("api/courses/<uuid:course_id>/scope/", course_scope_extend, name="course-scope-extend"),
    path("api/courses/<uuid:course_id>/activate/", course_activate, name="course-activate"),
    # 上传
    path("api/uploads/", upload_create, name="upload-create"),
    path("api/uploads/complete/", upload_complete, name="upload-complete"),
    path("api/library/sources/", list_sources, name="library-sources"),
    # 解析
    path("api/parsing/preview", preview_parse, name="parsing-preview"),
    path("api/parsing/benchmark", get_benchmark, name="parsing-benchmark"),
    path("api/retrieval/search", search_view, name="retrieval-search"),
    path("api/retrieval/evidence/<uuid:evidence_id>/location", locate_view, name="retrieval-locate"),
]
