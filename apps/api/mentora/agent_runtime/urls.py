"""Agent Runtime URL 配置。"""

from django.urls import path

from mentora.agent_runtime.views import chat_api, chat_stream, pipeline_chat, pipeline_chat_stream, run_detail, run_list
from mentora.agent_runtime.course_agent_views import (
    course_agent_session_detail,
    course_agent_session_list,
    course_agent_stream,
)

urlpatterns = [
    path("chat/", chat_api, name="agent-chat"),
    path("chat/stream/", chat_stream, name="agent-chat-stream"),
    path("chat/pipeline/", pipeline_chat, name="agent-chat-pipeline"),
    path("chat/pipeline/stream/", pipeline_chat_stream, name="agent-chat-pipeline-stream"),
    path("runs/", run_list, name="agent-run-list"),
    path("runs/<uuid:run_id>/", run_detail, name="agent-run-detail"),
    path("courses/<uuid:course_id>/agent-sessions/", course_agent_session_list, name="course-agent-session-list"),
    path(
        "courses/<uuid:course_id>/agent-sessions/<uuid:session_id>/",
        course_agent_session_detail,
        name="course-agent-session-detail",
    ),
    path(
        "courses/<uuid:course_id>/agent-sessions/stream/",
        course_agent_stream,
        name="course-agent-stream",
    ),
]
