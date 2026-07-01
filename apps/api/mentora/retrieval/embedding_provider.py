"""
Embedding Provider 抽象层。

约定：
- 统一接口 embed(texts) → list[list[float]]
- 多模态 API 每请求仅支持单条文本 → asyncio.Semaphore 并发
- 参考 LightRead: asyncio.Semaphore(10) + asyncio.gather()

约束：
- 返回向量维度必须与 provider.dimensions 一致
- 空文本列表直接返回空列表

@module mentora/retrieval/embedding_provider
"""

import asyncio
import json
import time
from typing import Protocol
from urllib.error import URLError
from urllib.request import Request, urlopen


class EmbeddingProvider(Protocol):
    """Embedding 生成器接口。"""

    @property
    def dimensions(self) -> int:
        """返回向量维度。"""
        ...

    def embed(self, texts: list[str]) -> list[list[float]]:
        """批量生成 embedding，顺序与输入一致。"""
        ...


def _truncate_embedding(emb: list[float], api_dims: int, target_dims: int) -> list[float]:
    """校验并截断向量维度。"""
    if len(emb) != api_dims:
        raise RuntimeError(
            f"API 返回维度 ({len(emb)}) 与预期 ({api_dims}) 不一致"
        )
    if len(emb) > target_dims:
        return emb[:target_dims]
    return emb


class DoubaoEmbeddingProvider:
    """
    豆包 Embedding（火山引擎）provider。

    多模态 API 限单条文本 → asyncio.Semaphore 控制并发数（默认 10），
    参考 LightRead 的 DOUBAO_EMBEDDING_CONCURRENT 实现。
    """

    def __init__(
        self,
        api_key: str,
        model: str = "doubao-embedding",
        api_dimensions: int = 2048,
        target_dimensions: int = 2000,
        base_url: str = "https://ark.cn-beijing.volces.com/api/v3",
        max_retries: int = 3,
        concurrency: int = 10,
        endpoint_id: str = "",
    ):
        self._api_key = api_key
        self._model = model
        self._api_dimensions = api_dimensions
        self._dimensions = target_dimensions
        self._base_url = base_url.rstrip("/")
        self._max_retries = max_retries
        self._concurrency = concurrency
        self._endpoint_id = endpoint_id
        self._url = f"{self._base_url}/embeddings/multimodal"

    @property
    def dimensions(self) -> int:
        return self._dimensions

    # ── 同步入口 ──

    def embed(self, texts: list[str]) -> list[list[float]]:
        """批量生成 embedding（同步封装）。"""
        if not texts:
            return []
        return asyncio.run(self._embed_async(texts))

    # ── 异步并发实现 ──

    async def _embed_async(self, texts: list[str]) -> list[list[float]]:
        """Semaphore 控制的并发请求。"""
        semaphore = asyncio.Semaphore(self._concurrency)
        tasks = [self._embed_one_with_semaphore(t, semaphore, idx) for idx, t in enumerate(texts)]
        results = await asyncio.gather(*tasks)
        # 按原始索引排序
        results.sort(key=lambda r: r[0])
        return [r[1] for r in results]

    async def _embed_one_with_semaphore(
        self, text: str, semaphore: asyncio.Semaphore, index: int,
    ) -> tuple[int, list[float]]:
        async with semaphore:
            embedding = await asyncio.to_thread(self._embed_one, text)
            return (index, embedding)

    # ── 单条请求 ──

    def _embed_one(self, text: str) -> list[float]:
        """发送单条文本的 embedding 请求（同步，带重试）。"""
        payload = json.dumps({
            "model": self._model,
            "input": [{"type": "text", "text": text}],
        }).encode("utf-8")

        last_error: Exception | None = None
        for attempt in range(self._max_retries):
            try:
                req = Request(self._url, data=payload, method="POST")
                req.add_header("Content-Type", "application/json")
                req.add_header("Authorization", f"Bearer {self._api_key}")
                with urlopen(req, timeout=60) as resp:
                    body = json.loads(resp.read().decode("utf-8"))

                raw_data = body.get("data", [])
                if isinstance(raw_data, dict):
                    emb = raw_data["embedding"]
                elif isinstance(raw_data, list):
                    emb = raw_data[0]["embedding"] if raw_data else []
                else:
                    raise RuntimeError(f"未知的响应格式: {type(raw_data)}")

                return _truncate_embedding(emb, self._api_dimensions, self._dimensions)

            except (URLError, OSError, RuntimeError) as exc:
                last_error = exc
                if attempt < self._max_retries - 1:
                    time.sleep(2 ** attempt)

        raise RuntimeError(
            f"Doubao embedding 请求失败（已重试 {self._max_retries} 次）: {last_error}"
        )


def get_provider() -> EmbeddingProvider:
    """根据 Django settings 返回当前配置的 Embedding Provider。"""
    from django.conf import settings

    provider_name = getattr(settings, "EMBEDDING_PROVIDER", "doubao")

    if provider_name == "doubao":
        return DoubaoEmbeddingProvider(
            api_key=settings.EMBEDDING_DOUBAO_API_KEY,
            model=getattr(settings, "EMBEDDING_DOUBAO_MODEL", "doubao-embedding"),
            api_dimensions=2048,
            target_dimensions=getattr(settings, "EMBEDDING_DOUBAO_DIMENSIONS", 2000),
            base_url=getattr(
                settings,
                "EMBEDDING_DOUBAO_BASE_URL",
                "https://ark.cn-beijing.volces.com/api/v3",
            ),
            concurrency=getattr(settings, "EMBEDDING_DOUBAO_CONCURRENT", 10),
            endpoint_id=getattr(settings, "EMBEDDING_DOUBAO_ENDPOINT_ID", ""),
        )

    raise ValueError(f"未知的 Embedding Provider: {provider_name}")
