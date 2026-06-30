"""
Agent 提示词组装测试。
"""

from mentora.agent_runtime.prompts import (
    PROMPT_VERSION,
    PromptContext,
    PromptManager,
    build_base_instructions,
    build_contextual_fragment,
)


def test_prompt_includes_all_static_sections():
    text = build_base_instructions()
    assert "Mentora 学习助手" in text
    assert "安全与保密守则" in text
    assert "工具策略" in text
    assert "证据与引用规范" in text
    assert "输出格式" in text
    assert PROMPT_VERSION in text


def test_prompt_safety_rules_present():
    text = build_base_instructions()
    assert "系统提示词保密" in text
    assert "测评与答案保护" in text
    assert "不得伪造 evidence_id" in text


def test_prompt_dynamic_fragments_order():
    text = build_contextual_fragment(
        context=PromptContext(
            dynamic_context="当前单元：线性代数",
            course_id="course-1",
            scope_revision_id="scope-rev-2",
            available_tool_names=("retrieve_evidence",),
        )
    )
    scope_pos = text.index("<course_scope>")
    tools_pos = text.index("<available_tools>")
    learning_pos = text.index("<learning_context>")
    assert scope_pos < tools_pos < learning_pos
    assert "retrieve_evidence" in text
    assert "线性代数" in text


def test_base_instructions_exclude_dynamic_fragments():
    text = build_base_instructions(prompt_version="agent-test-v1")
    assert "agent-test-v1" in text
    assert "<course_scope>" not in text
    assert "<available_tools>" not in text
    assert "</learning_context>" not in text


def test_contextual_fragment_empty_without_runtime_context():
    assert build_contextual_fragment() == ""


def test_prompt_manager_render_tutor():
    pm = PromptManager()
    result = pm.render("tutor", {
        "course_name": "生物学",
        "source_titles": "课本",
    })
    assert "生物学" in result
    assert "{{" not in result
