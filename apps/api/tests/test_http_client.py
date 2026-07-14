from __future__ import annotations

import asyncio
import ssl

import pytest

from mentora.model_gateway.providers import http_client


class _FakeWriter:
    def __init__(self, close_error: BaseException | None = None):
        self.close_error = close_error
        self.closed = False
        self.written = b""

    def write(self, data: bytes) -> None:
        self.written += data

    async def drain(self) -> None:
        return None

    def close(self) -> None:
        self.closed = True

    async def wait_closed(self) -> None:
        if self.close_error:
            raise self.close_error


def _reader_from_lines(lines: list[bytes]) -> asyncio.StreamReader:
    reader = asyncio.StreamReader()
    for line in lines:
        reader.feed_data(line)
    reader.feed_eof()
    return reader


@pytest.mark.asyncio
async def test_async_post_sse_ignores_ssl_close_notify_during_cleanup(monkeypatch):
    reader = _reader_from_lines([
        b"HTTP/1.1 200 OK\r\n",
        b"content-type: text/event-stream\r\n",
        b"\r\n",
        b'data: {"choices":[{"delta":{"content":"hi"}}]}\r\n',
        b"data: [DONE]\r\n",
    ])
    writer = _FakeWriter(
        ssl.SSLError(
            1,
            "[SSL: APPLICATION_DATA_AFTER_CLOSE_NOTIFY] application data after close notify (_ssl.c:2788)",
        ),
    )

    async def fake_open_connection(*args, **kwargs):
        return reader, writer

    monkeypatch.setattr(http_client.asyncio, "open_connection", fake_open_connection)

    chunks = [
        chunk
        async for chunk in http_client.async_post_sse(
            "https://example.test/v1/chat/completions",
            {"stream": True},
            headers={"Authorization": "Bearer test"},
        )
    ]

    assert chunks == [{"choices": [{"delta": {"content": "hi"}}]}]
    assert writer.closed is True


@pytest.mark.asyncio
async def test_async_post_sse_propagates_other_ssl_cleanup_errors(monkeypatch):
    reader = _reader_from_lines([
        b"HTTP/1.1 200 OK\r\n",
        b"content-type: text/event-stream\r\n",
        b"\r\n",
        b"data: [DONE]\r\n",
    ])
    writer = _FakeWriter(ssl.SSLError(1, "certificate verify failed"))

    async def fake_open_connection(*args, **kwargs):
        return reader, writer

    monkeypatch.setattr(http_client.asyncio, "open_connection", fake_open_connection)

    with pytest.raises(ssl.SSLError, match="certificate verify failed"):
        async for _ in http_client.async_post_sse(
            "https://example.test/v1/chat/completions",
            {"stream": True},
        ):
            pass
