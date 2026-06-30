"""
Agent 提示词组装。

约定：
- 固定层：identity / safety / tool_policy / evidence_policy / output_format
- 动态层：course_scope / available_tools / learning_context 渲染为独立 contextual message

@module mentora/agent_runtime/prompts/base
"""

from __future__ import annotations

from pathlib import Path

from .fragments import PromptContext, wrap_fragment

_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

_STATIC_SECTION_FILES: tuple[str, ...] = (
    "identity.md",
    "safety.md",
    "tool_policy.md",
    "evidence_policy.md",
    "output_format.md",
)

PROMPT_VERSION = "agent-base-v3"


def _load_section(filename: str) -> str:
    return (_TEMPLATES_DIR / filename).read_text(encoding="utf-8").strip()


def _build_static_sections() -> str:
    parts = [_load_section(name) for name in _STATIC_SECTION_FILES]
    return "\n\n".join(part for part in parts if part)


def build_base_instructions(*, prompt_version: str = PROMPT_VERSION) -> str:
    """组装固定 system instructions，不包含动态运行时上下文。"""
    header = wrap_fragment(
        "mentora_agent_instructions",
        f"prompt_version: {prompt_version}",
    )
    return f"{header}\n\n{_build_static_sections()}".strip()


def build_contextual_fragment(*, context: PromptContext | None = None) -> str:
    """渲染动态上下文片段。"""
    ctx = context or PromptContext()
    return "\n\n".join(ctx.render_dynamic_sections()).strip()
