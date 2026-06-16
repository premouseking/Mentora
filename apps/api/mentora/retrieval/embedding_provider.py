"""
Embedding Provider 抽象层。

约定：
- 统一接口 embed(texts) → list[list[float]]
- 通过 settings.EMBEDDING_PROVIDER 切换后端
- 批量请求由 Provider 内部管理（API 单次上限、重试等）

约束：
- 返回向量维度必须与 provider.dimensions 一致
- 空文本列表直接返回空列表

@module mentora/retrieval/embedding_provider
"""

from typing import Protocol


class EmbeddingProvider(Protocol):
    """Embedding 生成器接口。"""

    @property
    def dimensions(self) -> int:
        """返回向量维度。"""
        ...

    def embed(self, texts: list[str]) -> list[list[float]]:
        """批量生成 embedding，顺序与输入一致。"""
        ...


class DoubaoEmbeddingProvider:
    """
    豆包 Embedding（火山引擎）provider。

    MRL 支持降维：默认 2048d，可通过 dimensions 参数降为 1024/512。
    API 文档：https://www.volcengine.com/docs/84313/1254617
    """

    def __init__(
        self,
        api_key: str,
        model: str = "doubao-embedding",
        dimensions: int = 1024,
        base_url: str = "https://ark.cn-beijing.volces.com/api/v3",
        batch_size: int = 100,
        max_retries: int = 3,
    ):
        self._api_key = api_key
        self._model = model
        self._dimensions = dimensions
        self._base_url = base_url.rstrip("/")
        self._batch_size = batch_size
        self._max_retries = max_retries

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        all_embeddings: list[list[float]] = []
        for i in range(0, len(texts), self._batch_size):
            batch = texts[i:i + self._batch_size]
            all_embeddings.extend(self._embed_batch(batch))
        return all_embeddings

    def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        import json
        import time
        from urllib.error import URLError
        from urllib.request import Request, urlopen

        url = f"{self._base_url}/embeddings"
        payload = json.dumps({
            "model": self._model,
            "input": texts,
            "dimensions": self._dimensions,
        }).encode("utf-8")

        last_error: Exception | None = None
        for attempt in range(self._max_retries):
            try:
                req = Request(url, data=payload, method="POST")
                req.add_header("Content-Type", "application/json")
                req.add_header("Authorization", f"Bearer {self._api_key}")
                with urlopen(req, timeout=60) as resp:
                    body = json.loads(resp.read().decode("utf-8"))

                data = body.get("data", [])
                data.sort(key=lambda d: d.get("index", 0))
                embeddings = [d["embedding"] for d in data]

                if len(embeddings) != len(texts):
                    raise RuntimeError(
                        f"返回向量数 ({len(embeddings)}) 与输入数 ({len(texts)}) 不匹配"
                    )
                for emb in embeddings:
                    if len(emb) != self._dimensions:
                        raise RuntimeError(
                            f"返回维度 ({len(emb)}) 与预期 ({self._dimensions}) 不一致"
                        )

                return embeddings

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
            dimensions=getattr(settings, "EMBEDDING_DOUBAO_DIMENSIONS", 1024),
            base_url=getattr(
                settings,
                "EMBEDDING_DOUBAO_BASE_URL",
                "https://ark.cn-beijing.volces.com/api/v3",
            ),
        )

    raise ValueError(f"未知的 Embedding Provider: {provider_name}")
