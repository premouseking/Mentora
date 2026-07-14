"""资料库管理 API 回归测试。"""

from __future__ import annotations

import json
from types import SimpleNamespace

from django.test import RequestFactory
from rest_framework.test import force_authenticate

from mentora.knowledge import views
from mentora.knowledge.models import SourceStatus


class FakeSource:
    def __init__(self) -> None:
        self.status = SourceStatus.ACTIVE
        self.folder_id = None
        self.saved_fields: list[str] = []

    def save(self, update_fields: list[str]) -> None:
        self.saved_fields = update_fields


def test_archive_uses_source_status_enum(monkeypatch):
    source = FakeSource()
    monkeypatch.setattr(views.Source.objects, "get", lambda **kwargs: source)

    request = RequestFactory().patch("/")
    force_authenticate(request, user=SimpleNamespace(is_authenticated=True))
    response = views.source_archive(request, source_id="source-1")

    assert response.status_code == 200
    assert source.status == SourceStatus.ARCHIVED
    assert source.saved_fields == ["status"]


def test_move_rejects_unknown_folder(monkeypatch):
    source = FakeSource()
    monkeypatch.setattr(views.Source.objects, "get", lambda **kwargs: source)
    monkeypatch.setattr(
        views.LibraryFolder.objects,
        "filter",
        lambda **kwargs: SimpleNamespace(exists=lambda: False),
    )
    request = RequestFactory().patch(
        "/",
        data=json.dumps({"folderId": "00000000-0000-0000-0000-000000000001"}),
        content_type="application/json",
    )
    force_authenticate(request, user=SimpleNamespace(is_authenticated=True))

    response = views.source_move(request, source_id="source-1")

    assert response.status_code == 404
    assert source.folder_id is None
    assert source.saved_fields == []


def test_move_rejects_invalid_folder_id(monkeypatch):
    source = FakeSource()
    monkeypatch.setattr(views.Source.objects, "get", lambda **kwargs: source)
    request = RequestFactory().patch(
        "/",
        data=json.dumps({"folderId": "not-a-uuid"}),
        content_type="application/json",
    )
    force_authenticate(request, user=SimpleNamespace(is_authenticated=True))

    response = views.source_move(request, source_id="source-1")

    assert response.status_code == 400
    assert source.folder_id is None
    assert source.saved_fields == []


def test_list_sources_requires_authentication():
    response = views.list_sources(RequestFactory().get("/"))

    assert response.status_code == 401
