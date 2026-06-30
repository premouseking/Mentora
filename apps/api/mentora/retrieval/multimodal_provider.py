"""
多模态 Provider：图片描述 + 图文联合向量。

约定：
- image_to_text: LLM Vision 理解图片内容，生成文本描述
- multimodal_embed: 图文联合向量化（Text + Image → Vector）
- Provider 不可用时返回空，不阻断解析管线

参考: LightRead embedding_view.py (doubao-embedding-vision + multimodal embeddings)
@module mentora/retrieval/multimodal_provider
"""

import base64
import json
import time
from typing import Protocol
from urllib.request import Request, urlopen


class MultimodalProvider(Protocol):
    """多模态 Provider 接口。"""

    def image_to_text(self, image_bytes: bytes, prompt: str = "") -> str: ...

    def multimodal_embed(self, inputs: list[dict]) -> list[list[float]]: ...

    @property
    def is_available(self) -> bool: ...


class DoubaoMultimodalProvider:
    """
    豆包多模态 Provider。

    image_to_text:  Doubao Vision Pro → 图片描述文本
    multimodal_embed: doubao-embedding-vision → 图文联合向量
    """

    def __init__(
        self,
        api_key: str,
        vision_model: str = "doubao-1-5-vision-pro-32k",
        embed_model: str = "doubao-embedding-vision-250615",
        base_url: str = "https://ark.cn-beijing.volces.com/api/v3",
        timeout: int = 60,
    ):
        self._api_key = api_key
        self._vision_model = vision_model
        self._embed_model = embed_model
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    @property
    def is_available(self) -> bool:
        return bool(self._api_key)

    def image_to_text(self, image_bytes: bytes, prompt: str = "") -> str:
        """调用 Vision 模型，将图片转为文本描述。"""
        if not self._api_key:
            return ""

        encoded = base64.b64encode(image_bytes).decode("utf-8")
        user_prompt = prompt or "请用简洁的中文描述这张图片的内容，包括其中的文字、图表类型和关键信息。"

        payload = json.dumps({
            "model": self._vision_model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{encoded}"},
                        },
                        {
                            "type": "text",
                            "text": user_prompt,
                        },
                    ],
                },
            ],
            "max_tokens": 1000,
        }).encode("utf-8")

        req = Request(
            f"{self._base_url}/chat/completions",
            data=payload,
            method="POST",
        )
        req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", f"Bearer {self._api_key}")

        try:
            with urlopen(req, timeout=self._timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            return body["choices"][0]["message"]["content"].strip()
        except Exception:
            return ""

    def multimodal_embed(self, inputs: list[dict]) -> list[list[float]]:
        """
        图文联合向量化。

        inputs: [{"text": str | None, "image_url": str | None}, ...]
        """
        if not self._api_key or not inputs:
            return []

        payload = json.dumps({
            "model": self._embed_model,
            "input": inputs,
        }).encode("utf-8")

        req = Request(
            f"{self._base_url}/embeddings/multimodal",
            data=payload,
            method="POST",
        )
        req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", f"Bearer {self._api_key}")

        try:
            with urlopen(req, timeout=self._timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            data = body.get("data", [])
            data.sort(key=lambda d: d.get("index", 0))
            return [d["embedding"] for d in data]
        except Exception:
            return []


def get_multimodal_provider() -> MultimodalProvider | None:
    """返回当前配置的多模态 Provider，未配置时返回 None。"""
    from django.conf import settings

    api_key = getattr(settings, "MULTIMODAL_API_KEY", "")
    if not api_key:
        return None
    return DoubaoMultimodalProvider(
        api_key=api_key,
        vision_model=getattr(
            settings, "MULTIMODAL_VISION_MODEL", "doubao-1-5-vision-pro-32k"
        ),
        embed_model=getattr(
            settings, "MULTIMODAL_EMBED_MODEL", "doubao-embedding-vision-250615"
        ),
        base_url=getattr(
            settings, "MULTIMODAL_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3"
        ),
    )
