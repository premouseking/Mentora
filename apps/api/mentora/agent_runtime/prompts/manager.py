"""Prompt template loader with layered base instructions."""

from __future__ import annotations

from pathlib import Path

from mentora.agent_runtime.prompts.base import build_base_instructions
from mentora.agent_runtime.prompts.schema import PromptTemplate


class PromptManager:
    """Load JSON task templates and render them under the base prompt policy."""

    def __init__(self, templates_dir: Path | str | None = None):
        self._cache: dict[str, PromptTemplate] = {}
        self._render_cache: dict[str, str] = {}
        if templates_dir is None:
            templates_dir = Path(__file__).resolve().parent / "templates"
        self._templates_dir = Path(templates_dir)
        self._load_all()

    def _load_all(self) -> None:
        if not self._templates_dir.is_dir():
            return
        for fpath in self._templates_dir.glob("*.json"):
            try:
                template = PromptTemplate.model_validate_json(
                    fpath.read_text(encoding="utf-8")
                )
                self._cache[template.name] = template
            except Exception:
                continue

    def get(self, name: str) -> PromptTemplate:
        if name not in self._cache:
            raise KeyError(f"Prompt template '{name}' not found")
        return self._cache[name]

    def render(
        self,
        name: str,
        variables: dict[str, str] | None = None,
        *,
        include_base: bool = True,
    ) -> str:
        variables = self._normalize_variables(variables or {})
        template = self.get(name)
        for required_name in template.required_variables:
            variables.setdefault(required_name, "")
        cache_key = self._make_cache_key(name, variables, include_base)
        if cache_key in self._render_cache:
            return self._render_cache[cache_key]

        rendered = template.system
        for key, value in variables.items():
            rendered = rendered.replace(f"{{{{ {key} }}}}", value)
            rendered = rendered.replace(f"{{{{{key}}}}}", value)
        rendered = rendered.strip()

        if not include_base:
            self._render_cache[cache_key] = rendered
            return rendered

        base = build_base_instructions()
        if not rendered:
            self._render_cache[cache_key] = base
            return base
        result = f'{base}\n\n<task_prompt name="{name}">\n{rendered}\n</task_prompt>'
        self._render_cache[cache_key] = result
        return result

    def _make_cache_key(
        self, name: str, variables: dict[str, str], include_base: bool
    ) -> str:
        var_str = ",".join(f"{k}={v}" for k, v in sorted(variables.items()))
        return f"{name}:{include_base}:{var_str}"

    def list_templates(self) -> list[str]:
        return list(self._cache.keys())

    def reload(self) -> None:
        self._cache.clear()
        self._render_cache.clear()
        self._load_all()

    @staticmethod
    def _normalize_variables(variables: dict[str, str]) -> dict[str, str]:
        normalized = dict(variables)
        course_name = normalized.get("course_name", "")
        source_titles = normalized.get("source_titles", "")
        normalized.setdefault("goal", course_name)
        normalized.setdefault("school", "")
        normalized.setdefault("level", "")
        normalized.setdefault("pace", "")
        normalized.setdefault("inquiry_history", source_titles)
        return normalized
