"""
Reranker：对 RRF 候选集进行语义精排。

约定：
- RRF 召回 top-N 候选（默认 30），Reranker 逐条打分后截取 top_k
- API 不可用时自动降级，返回原始顺序
- 参考：LightRead RerankService（Qwen3-Reranker-4B via SiliconFlow/CES）

@module mentora/retrieval/reranker
"""

from typing import Protocol


class RerankerProvider(Protocol):
    """Reranker 接口。"""

    def rerank(
        self, query: str, documents: list[str], top_k: int
    ) -> list[dict]:
        """
        对文档列表重排序。

        返回：[{"index": int, "score": float}, ...]，按 score 降序。
        """
        ...


class SiliconFlowReranker:
    """
    Qwen3-Reranker-4B via SiliconFlow API。

    API 文档：https://docs.siliconflow.cn/cn/api-reference/rerank/create-rerank
    """

    def __init__(
        self,
        api_key: str,
        model: str = "Qwen/Qwen3-Reranker-4B",
        base_url: str = "https://api.siliconflow.cn/v1/rerank",
        timeout: int = 30,
    ):
        self._api_key = api_key
        self._model = model
        self._base_url = base_url
        self._timeout = timeout

    def rerank(
        self, query: str, documents: list[str], top_k: int
    ) -> list[dict]:
        import json
        from urllib.request import Request, urlopen

        payload = json.dumps({
            "model": self._model,
            "query": query,
            "documents": documents,
        }).encode("utf-8")

        req = Request(self._base_url, data=payload, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", f"Bearer {self._api_key}")

        with urlopen(req, timeout=self._timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))

        results = body.get("results", [])
        return sorted(
            (
                {"index": r["index"], "score": r["relevance_score"]}
                for r in results
                if isinstance(r, dict) and "index" in r
            ),
            key=lambda x: x["score"],
            reverse=True,
        )[:top_k]


def get_reranker() -> RerankerProvider | None:
    """根据 Django settings 返回 Reranker 实例，未配置时返回 None。"""
    from django.conf import settings

    api_key = getattr(settings, "RERANKER_API_KEY", "")
    if not api_key:
        return None
    return SiliconFlowReranker(
        api_key=api_key,
        model=getattr(settings, "RERANKER_MODEL", "Qwen/Qwen3-Reranker-4B"),
    )
