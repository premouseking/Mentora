"""
提示词动态片段：带 XML 标记，便于 diff 注入与历史识别。

约定 ：
- 固定章节在 templates/ 中维护；运行时上下文以片段追加在末尾。
- 片段不得包含 Token、预签名 URL、私有资料正文或测评隐藏答案。

@module mentora/agent_runtime/prompts/fragments
"""

from __future__ import annotations

from dataclasses import dataclass


def wrap_fragment(tag: str, body: str) -> str:
    """用 XML 风格标记包裹动态片段。"""
    content = body.strip()
    if not content:
        return ""
    return f"<{tag}>\n{content}\n</{tag}>"


@dataclass(frozen=True)
class PromptContext:
    """运行时注入提示词的动态上下文（非敏感元数据）。"""

    dynamic_context: str = ""
    course_id: str | None = None
    scope_revision_id: str | None = None
    owner_id: str | None = None
    available_tool_names: tuple[str, ...] = ()

    def render_dynamic_sections(self) -> list[str]:
        """按固定顺序渲染动态片段。"""
        sections: list[str] = []

        scope_lines: list[str] = []
        if self.course_id:
            scope_lines.append(f"- course_id: {self.course_id}")
        if self.scope_revision_id:
            scope_lines.append(f"- scope_revision_id: {self.scope_revision_id}")
        if self.owner_id:
            scope_lines.append(f"- owner_id: {self.owner_id}")
        if scope_lines:
            sections.append(
                wrap_fragment("course_scope", "\n".join(scope_lines))
            )

        if self.available_tool_names:
            tool_lines = "\n".join(f"- {name}" for name in self.available_tool_names)
            sections.append(
                wrap_fragment(
                    "available_tools",
                    f"当前 turn 已启用的工具（仅供你规划调用，勿向用户罗列工具名）：\n{tool_lines}",
                )
            )

        if self.dynamic_context.strip():
            sections.append(
                wrap_fragment("learning_context", self.dynamic_context.strip())
            )

        return [section for section in sections if section]
