from django.http import JsonResponse
from django.urls import path

from mentora.assessment.views import (
    complete_quiz_session,
    generate_quiz_session,
    quiz_session_detail,
    submit_quiz_attempt,
)
from mentora.agent_runtime.views import chat_api, chat_stream
from mentora.courses.views import (
    course_activate,
    apply_candidate,
    course_confirm,
    course_detail,
    course_list,
    course_profile_revise,
    course_scope_extend,
    course_scope_suggest,
    inquiry_next,
    plan_generate,
    profile_candidates,
    session_create,
    session_detail,
    session_list_or_create,
    session_start,
    session_update,
)
from mentora.knowledge.views import list_sources, source_delete, source_detail, source_reparse, upload_complete, upload_create
from mentora.parsing.views import get_benchmark, preview_parse
from mentora.retrieval.views import locate_view, search_view


def health(_: object) -> JsonResponse:
    return JsonResponse({"status": "ok", "service": "mentora-api"})


urlpatterns = [
    path("api/health/", health, name="health"),
    # 聊天
    path("api/chat/", chat_api, name="chat"),
    path("api/chat/stream/", chat_stream, name="chat-stream"),
    path("api/assessment/sessions/generate/", generate_quiz_session, name="assessment-generate"),
    path("api/assessment/sessions/<uuid:session_id>/", quiz_session_detail, name="assessment-session-detail"),
    path("api/assessment/sessions/<uuid:session_id>/attempts/", submit_quiz_attempt, name="assessment-submit-attempt"),
    path("api/assessment/sessions/<uuid:session_id>/complete/", complete_quiz_session, name="assessment-complete"),
    # 建课会话
    path("api/courses/sessions/", session_list_or_create, name="session-list-create"),
    path("api/courses/sessions/<uuid:session_id>/", session_detail, name="session-detail"),
    path("api/courses/sessions/<uuid:session_id>/update/", session_update, name="session-update"),
    path("api/courses/sessions/<uuid:session_id>/inquiry/", inquiry_next, name="inquiry-next"),
    path("api/courses/sessions/<uuid:session_id>/plan/", plan_generate, name="plan-generate"),
    path("api/courses/sessions/<uuid:session_id>/candidates/", profile_candidates, name="profile-candidates"),
    path("api/courses/sessions/<uuid:session_id>/apply-candidate/", apply_candidate, name="apply-candidate"),
    # 课程管理
    path("api/courses/", course_list, name="course-list"),
    path("api/courses/confirm/", course_confirm, name="course-confirm"),
    path("api/courses/<uuid:course_id>/", course_detail, name="course-detail"),
    path("api/courses/<uuid:course_id>/profile/", course_profile_revise, name="course-profile-revise"),
    path("api/courses/<uuid:course_id>/scope/", course_scope_extend, name="course-scope-extend"),
    path("api/courses/<uuid:course_id>/scope-suggest/", course_scope_suggest, name="course-scope-suggest"),
    path("api/courses/<uuid:course_id>/activate/", course_activate, name="course-activate"),
    # 上传
    path("api/uploads/", upload_create, name="upload-create"),
    path("api/uploads/complete/", upload_complete, name="upload-complete"),
    path("api/library/sources/", list_sources, name="library-sources"),
    path("api/library/sources/<uuid:source_version_id>/", source_detail, name="library-source-detail"),
    path("api/library/sources/<uuid:source_id>/delete/", source_delete, name="library-source-delete"),
    path("api/library/sources/<uuid:source_id>/reparse/", source_reparse, name="library-source-reparse"),
    # 解析
    path("api/parsing/preview", preview_parse, name="parsing-preview"),
    path("api/parsing/benchmark", get_benchmark, name="parsing-benchmark"),
    path("api/retrieval/search", search_view, name="retrieval-search"),
    path("api/retrieval/evidence/<uuid:evidence_id>/location", locate_view, name="retrieval-locate"),
]
