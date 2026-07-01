from django.http import JsonResponse
from django.urls import path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
)

from mentora.assessment.views import (
    complete_quiz_session,
    generate_quiz_session,
    quiz_session_detail,
    submit_quiz_attempt,
)
from django.urls import include
from mentora.users.views import change_password, login, logout, profile, refresh, register, update_profile
from mentora.learning.views import explanation_list, history_list, mistake_list
from mentora.courses.views import (
    course_activate,
    course_confirm,
    course_detail,
    course_files,
    course_list,
    course_phases,
    course_profile_revise,
    course_scope_extend,
    course_scope_suggest,
    inquiry_next,
    plan_handler,
    session_delete,
    session_detail,
    session_list_or_create,
    session_start,
    session_update,
)
from mentora.knowledge.views import course_sources, folder_create, folder_delete, folder_list, folder_rename, list_sources, list_tags, source_archive, source_delete, source_detail, source_move, source_reparse, source_unarchive, source_update_tags, upload_complete, upload_create
from mentora.parsing.views import get_benchmark, preview_parse
from mentora.topics.views import (
    topic_add_edge,
    topic_create_tree,
    topic_delete,
    topic_get_tree,
    topic_link_evidence,
    topic_update,
)
from mentora.retrieval.views import locate_view, search_view


def health(_: object) -> JsonResponse:
    return JsonResponse({"status": "ok", "service": "mentora-api"})


urlpatterns = [
    # Swagger / OpenAPI
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    # Auth
    path("api/auth/register/", register, name="auth-register"),
    path("api/auth/login/", login, name="auth-login"),
    path("api/auth/refresh/", refresh, name="auth-refresh"),
    path("api/auth/profile/", profile, name="auth-profile"),
    path("api/auth/profile/update/", update_profile, name="auth-profile-update"),
    path("api/auth/change-password/", change_password, name="auth-change-password"),
    path("api/auth/logout/", logout, name="auth-logout"),
    path("api/health/", health, name="health"),
    path("api/history/", history_list, name="history-list"),
    path("api/learning/mistakes/", mistake_list, name="learning-mistakes"),
    path("api/learning/explanations/", explanation_list, name="learning-explanations"),
    # Agent 聊天
    path("api/", include("mentora.agent_runtime.urls")),
    path("api/", include("mentora.model_gateway.urls")),
    # Workflow 异步任务
    path("api/", include("mentora.workflow_runtime.urls")),
    path("api/assessment/sessions/generate/", generate_quiz_session, name="assessment-generate"),
    path("api/assessment/sessions/<uuid:session_id>/", quiz_session_detail, name="assessment-session-detail"),
    path("api/assessment/sessions/<uuid:session_id>/attempts/", submit_quiz_attempt, name="assessment-submit-attempt"),
    path("api/assessment/sessions/<uuid:session_id>/complete/", complete_quiz_session, name="assessment-complete"),
    # 建课会话
    path("api/courses/sessions/", session_list_or_create, name="session-list-create"),
    path("api/courses/sessions/<uuid:session_id>/", session_detail, name="session-detail"),
    path("api/courses/sessions/<uuid:session_id>/update/", session_update, name="session-update"),
    path("api/courses/sessions/<uuid:session_id>/delete/", session_delete, name="session-delete"),
    path("api/courses/sessions/<uuid:session_id>/start/", session_start, name="session-start"),
    path("api/courses/sessions/<uuid:session_id>/inquiry/", inquiry_next, name="inquiry-next"),
    path("api/courses/sessions/<uuid:session_id>/plan/", plan_handler, name="plan-handler"),
    # 课程管理
    path("api/courses/", course_list, name="course-list"),
    path("api/courses/confirm/", course_confirm, name="course-confirm"),
    path("api/courses/<uuid:course_id>/", course_detail, name="course-detail"),
    path("api/courses/<uuid:course_id>/profile/", course_profile_revise, name="course-profile-revise"),
    path("api/courses/<uuid:course_id>/scope/", course_scope_extend, name="course-scope-extend"),
    path("api/courses/<uuid:course_id>/scope-suggest/", course_scope_suggest, name="course-scope-suggest"),
    path("api/courses/<uuid:course_id>/phases/", course_phases, name="course-phases"),
    path("api/courses/<uuid:course_id>/files/", course_files, name="course-files"),
    path("api/courses/<uuid:course_id>/activate/", course_activate, name="course-activate"),
    # 课程资料关联
    path("api/courses/sessions/<uuid:session_id>/sources/", course_sources, name="course-sources"),
    # 上传
    path("api/uploads/", upload_create, name="upload-create"),
    path("api/uploads/complete/", upload_complete, name="upload-complete"),
    path("api/library/sources/", list_sources, name="library-sources"),
    path("api/library/sources/<uuid:source_version_id>/", source_detail, name="library-source-detail"),
    path("api/library/sources/<uuid:source_id>/delete/", source_delete, name="library-source-delete"),
    path("api/library/sources/<uuid:source_id>/reparse/", source_reparse, name="library-source-reparse"),
    path("api/library/sources/<uuid:source_id>/tags/", source_update_tags, name="library-source-tags"),
    path("api/library/sources/<uuid:source_id>/archive/", source_archive, name="library-source-archive"),
    path("api/library/sources/<uuid:source_id>/unarchive/", source_unarchive, name="library-source-unarchive"),
    path("api/library/tags/", list_tags, name="library-tags"),
    path("api/library/sources/<uuid:source_id>/move/", source_move, name="library-source-move"),
    path("api/library/folders/", folder_list, name="library-folder-list"),
    path("api/library/folders/create/", folder_create, name="library-folder-create"),
    path("api/library/folders/<uuid:folder_id>/", folder_rename, name="library-folder-rename"),
    path("api/library/folders/<uuid:folder_id>/delete/", folder_delete, name="library-folder-delete"),
    # 知识主题
    path("api/courses/<uuid:course_id>/topics/", topic_get_tree, name="topic-get-tree"),
    path("api/courses/<uuid:course_id>/topics/create/", topic_create_tree, name="topic-create-tree"),
    path("api/topics/<uuid:topic_id>/", topic_update, name="topic-update"),
    path("api/topics/<uuid:topic_id>/delete/", topic_delete, name="topic-delete"),
    path("api/topics/<uuid:topic_id>/edges/", topic_add_edge, name="topic-add-edge"),
    path("api/topics/<uuid:topic_id>/evidence/", topic_link_evidence, name="topic-link-evidence"),
    # 解析
    path("api/parsing/preview", preview_parse, name="parsing-preview"),
    path("api/parsing/benchmark", get_benchmark, name="parsing-benchmark"),
    path("api/retrieval/search", search_view, name="retrieval-search"),
    path("api/retrieval/evidence/<uuid:evidence_id>/location", locate_view, name="retrieval-locate"),
]
