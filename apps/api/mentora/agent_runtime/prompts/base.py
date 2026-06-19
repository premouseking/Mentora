"""
Agent 提示词组装。

约定（借鉴 codex instructions + contextual fragments / lightest buildCompleteSystemPrompt）：
- **固定层**：identity / safety / tool_policy / evidence_policy / output_format 按 manifest 顺序拼接。
- **动态层**：course_scope / available_tools / learning_context 渲染为独立 contextual message。
- system instructions、动态上下文与对话 history 分离；history 由 ContextManager 维护。

@see docs/architecture/adr/0007-controlled-agent-tool-loop.md
@module mentora/agent_runtime/prompts/base
"""

from __future__ import annotations

from pathlib import Path

from .fragments import PromptContext, wrap_fragment

_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

# 固定章节顺序：安全守则置顶
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
    """渲染动态上下文片段，供 loop 作为独立 input message 注入。"""
    ctx = context or PromptContext()
    return "\n\n".join(ctx.render_dynamic_sections()).strip()


def build_instructions(
    *,
    context: PromptContext | None = None,
    dynamic_context: str = "",
    prompt_version: str = PROMPT_VERSION,
) -> str:
    """
    兼容旧入口：返回固定 instructions + 动态片段。

    新调用应优先使用 build_base_instructions() 与 build_contextual_fragment()。
    """
    instructions = build_base_instructions(prompt_version=prompt_version)
    ctx = context or PromptContext(dynamic_context=dynamic_context)
    fragment = build_contextual_fragment(context=ctx)
    if not fragment:
        return instructions
    return f"{instructions}\n\n{fragment}".strip()


def build_instructions_from_tools(
    *,
    tool_names: tuple[str, ...],
    dynamic_context: str = "",
    course_id: str | None = None,
    scope_revision_id: str | None = None,
    owner_id: str | None = None,
) -> str:
    """便捷入口：由工具名与任务上下文构建 instructions。"""
    return build_instructions(
        context=PromptContext(
            dynamic_context=dynamic_context,
            course_id=course_id,
            scope_revision_id=scope_revision_id,
            owner_id=owner_id,
            available_tool_names=tool_names,
        )
    )
