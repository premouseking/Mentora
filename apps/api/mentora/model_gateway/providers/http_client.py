"""
自建异步 HTTP 客户端（仅使用 Python stdlib）。

约定：
- async_post_json() 用于非流式 JSON POST，内部 asyncio.to_thread + urllib
- async_post_sse() 用于 SSE 流式 POST，内部 asyncio.open_connection + SSL
- 不引入任何第三方 HTTP 库

约束：
- 错误通过 HttpError 异常传播
- 不在此处处理业务重试逻辑（由 Provider 层负责）
- SSL 仅服务端证书校验

@module mentora/model_gateway/providers/http_client
"""

import asyncio
import json
import ssl
import urllib.request
from urllib.error import URLError


class HttpError(Exception):
    """HTTP 请求错误。"""

    def __init__(self, status: str, body: str = ""):
        self.status = status
        self.body = body
        super().__init__(f"HTTP error: {status} | body: {body[:200]}")


async def async_post_json(
    url: str,
    payload: dict,
    headers: dict[str, str] | None = None,
    timeout: int = 30,
) -> dict:
    """非流式 JSON POST（asyncio.to_thread + urllib.request）。

    参数：
    - url: 请求 URL
    - payload: JSON 可序列化的请求体
    - headers: 额外 HTTP 头（Authorization 等）
    - timeout: 请求总超时（秒）

    返回：解析后的 JSON dict
    """
    headers = headers or {}
    body_bytes = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(url, data=body_bytes, method="POST")
    req.add_header("Content-Type", "application/json")
    for key, value in headers.items():
        req.add_header(key, value)

    def _do_request() -> dict:
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                resp_body = resp.read().decode("utf-8")
                return json.loads(resp_body)
        except URLError as e:
            raise HttpError(status=str(e.reason), body=str(e)) from e

    return await asyncio.to_thread(_do_request)


async def async_post_sse(
    url: str,
    payload: dict,
    headers: dict[str, str] | None = None,
    timeout: int = 120,
):
    """流式 SSE POST（asyncio.open_connection + 手动 HTTP/1.1）。

    参数：
    - url: 请求 URL
    - payload: JSON 可序列化的请求体
    - headers: 额外 HTTP 头（Authorization 等）
    - timeout: 连接和读取超时（秒）

    返回：AsyncGenerator[dict, None] — 逐块解析的 SSE JSON 数据
    """
    from urllib.parse import urlparse

    headers = headers or {}
    parsed = urlparse(url)
    host = parsed.hostname
    if host is None:
        raise ValueError(f"Invalid URL, no hostname: {url}")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    path = parsed.path or "/"
    if parsed.query:
        path += "?" + parsed.query

    ssl_ctx = ssl.create_default_context() if parsed.scheme == "https" else None

    reader, writer = await asyncio.wait_for(
        asyncio.open_connection(host, port, ssl=ssl_ctx),
        timeout=timeout,
    )

    try:
        body = json.dumps(payload)
        body_bytes = body.encode("utf-8")

        # 构造 HTTP/1.1 请求
        request_lines = [
            f"POST {path} HTTP/1.1",
            f"Host: {host}",
            "Content-Type: application/json",
            "Accept: text/event-stream",
            f"Content-Length: {len(body_bytes)}",
            "Connection: close",
        ]
        for key, value in headers.items():
            request_lines.append(f"{key}: {value}")
        request_lines.append("")  # 空行分隔 header 与 body
        request_lines.append("")

        request_str = "\r\n".join(request_lines) + body
        writer.write(request_str.encode("utf-8"))
        await writer.drain()

        # 读取状态行
        status_line = await asyncio.wait_for(reader.readline(), timeout=timeout)
        status_line = status_line.decode("utf-8").rstrip("\r\n")

        # 读取响应头
        resp_headers: dict[str, str] = {}
        while True:
            line = await asyncio.wait_for(reader.readline(), timeout=timeout)
            line_str = line.decode("utf-8").rstrip("\r\n")
            if not line_str:
                break
            if ":" in line_str:
                k, v = line_str.split(":", 1)
                resp_headers[k.strip().lower()] = v.strip()

        # 状态码检查
        if not status_line.startswith("HTTP/1.1 2"):
            error_body_parts: list[str] = []
            content_length = int(resp_headers.get("content-length", 0))
            if content_length:
                chunk = await reader.read(content_length)
                error_body_parts.append(chunk.decode("utf-8", errors="replace"))
            else:
                while True:
                    chunk = await reader.read(1024)
                    if not chunk:
                        break
                    error_body_parts.append(chunk.decode("utf-8", errors="replace"))
            raise HttpError(status=status_line, body="".join(error_body_parts))

        # 解析 SSE 流
        while True:
            line = await asyncio.wait_for(reader.readline(), timeout=timeout)
            if not line:
                break
            decoded = line.decode("utf-8").rstrip("\r\n")

            if decoded.startswith("data: "):
                data_str = decoded[6:]
                if data_str == "[DONE]":
                    break
                try:
                    yield json.loads(data_str)
                except json.JSONDecodeError:
                    continue
    finally:
        writer.close()
        await writer.wait_closed()
