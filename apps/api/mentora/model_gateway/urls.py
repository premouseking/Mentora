from django.urls import path

from mentora.model_gateway.views import model_request_list, model_usage_summary

urlpatterns = [
    path("model-requests/", model_request_list, name="model-request-list"),
    path("model-usage/", model_usage_summary, name="model-usage-summary"),
]
