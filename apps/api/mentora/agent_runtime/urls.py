"""Agent Runtime URL 配置。"""

from django.urls import path

from mentora.agent_runtime.views import chat_api, chat_stream, run_detail, run_list

urlpatterns = [
    path("chat/", chat_api, name="agent-chat"),
    path("chat/stream/", chat_stream, name="agent-chat-stream"),
    path("runs/", run_list, name="agent-run-list"),
    path("runs/<uuid:run_id>/", run_detail, name="agent-run-detail"),
]
