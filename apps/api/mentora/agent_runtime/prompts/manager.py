"""
提示词管理器：加载、缓存和渲染 JSON 格式提示词模板。

约定：
- 模板文件为 JSON 格式，存放在 prompts/templates/ 目录
- 初始化时加载所有模板到内存缓存
- 运行时只做变量渲染，不重新 IO

约束：
- 模板路径相对于 prompts/templates/
- 变量渲染使用简单的 {{ var }} 替换

@module mentora/agent_runtime/prompts/manager
"""

import json
from pathlib import Path

from mentora.agent_runtime.prompts.schema import PromptTemplate


class PromptManager:
    """提示词管理器。

    使用方式：
    ```python
    manager = PromptManager(templates_dir)
    system_prompt = manager.render("tutor", {"course_name": "数学分析"})
    ```
    """

    def __init__(self, templates_dir: Path | str | None = None):
        self._cache: dict[str, PromptTemplate] = {}
        if templates_dir is None:
            templates_dir = Path(__file__).resolve().parent / "templates"
        self._templates_dir = Path(templates_dir)
        self._load_all()

    def _load_all(self) -> None:
        """加载所有 JSON 模板到内存缓存。"""
        if not self._templates_dir.is_dir():
            return
        for fpath in self._templates_dir.glob("*.json"):
            try:
                template = PromptTemplate.model_validate_json(fpath.read_text(encoding="utf-8"))
                self._cache[template.name] = template
            except Exception:
                # 跳过无效模板文件
                continue

    def get(self, name: str) -> PromptTemplate:
        """按名称获取模板。

        Raises:
            KeyError: 模板不存在
        """
        if name not in self._cache:
            raise KeyError(f"Prompt template '{name}' not found")
        return self._cache[name]

    def render(self, name: str, variables: dict[str, str] | None = None) -> str:
        """获取模板并渲染变量。

        参数：
        - name: 模板名称
        - variables: 变量映射，如 {"course_name": "数学分析"}

        返回渲染后的系统提示词文本。

        Raises:
            KeyError: 模板不存在
        """
        template = self.get(name)
        result = template.system
        if variables:
            for key, value in variables.items():
                # 替换 {{ key }} 形式的占位符
                result = result.replace(f"{{{{ {key} }}}}", value)
                # 也尝试无空格形式 {{key}}
                result = result.replace(f"{{{{{key}}}}}", value)
        return result.strip()

    def list_templates(self) -> list[str]:
        """列出所有已加载的模板名称。"""
        return list(self._cache.keys())

    def reload(self) -> None:
        """重新加载所有模板（用于热更新）。"""
        self._cache.clear()
        self._load_all()
