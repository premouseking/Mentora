"""
Pydantic 结构化输出校验器。

约定：
- 从 LLM 文本响应中提取 JSON 并校验
- 支持 JSON 代码块（```json ... ```）和裸 JSON

约束：
- 校验失败不抛异常，返回 (None, errors)
- 不支持流式校验（Phase 1 非流式）

@module mentora/model_gateway/structured_output
"""

import json
import re
from typing import Any

from pydantic import BaseModel, ValidationError


class StructuredOutputValidator:
    """基于 Pydantic 的结构化输出校验器。"""

    def validate(
        self, text: str, schema: type[BaseModel]
    ) -> tuple[BaseModel | None, list[str]]:
        """从文本中提取 JSON 并按 schema 校验。

        - 成功：返回 (instance, [])
        - 失败：返回 (None, [错误消息列表])
        """
        json_str = self._extract_json(text)
        if json_str is None:
            return None, ["无法从响应中提取有效 JSON"]

        try:
            data: dict[str, Any] = json.loads(json_str)
        except json.JSONDecodeError as e:
            return None, [f"JSON 解析错误: {e}"]

        try:
            instance = schema.model_validate(data)
            return instance, []
        except ValidationError as e:
            errors = [f"{err['loc']}: {err['msg']}" for err in e.errors()]
            return None, errors

    def _extract_json(self, text: str) -> str | None:
        """从文本中提取 JSON 字符串。

        优先级：
        1. ```json ... ``` 代码块
        2. 首个 { 到最后一个 } 的裸 JSON
        """
        # 尝试 JSON 代码块
        m = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
        if m:
            return m.group(1).strip()

        # 尝试裸 JSON（首个 { 到最后一个 }）
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return text[start : end + 1]

        return None
