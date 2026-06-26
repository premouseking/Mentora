"""
评估模块 Pydantic Schema。

@module mentora/assessment/schemas
"""

from pydantic import BaseModel, Field


class ItemValidationResult(BaseModel):
    """AI 自检结果——三要素校验。"""

    valid: bool = Field(description="是否通过校验")
    issues: list[str] = Field(
        default_factory=list,
        description="未通过时的具体问题列表",
    )


class GeneratedQuizItem(BaseModel):
    """LLM 生成的单道题目。"""

    question_text: str = Field(description="题干")
    correct_answer: str = Field(description="正确选项标签 A/B/C/D")
    difficulty: int = Field(default=3, description="难度 1-5")
    options: list[dict] = Field(default_factory=list, description="选项列表")
    explanation: str = Field(default="", description="答案解析")
    source_evidence_ids: list[str] = Field(
        default_factory=list, description="出题依据的证据 ID"
    )


class GeneratedQuizPaper(BaseModel):
    """LLM 生成的完整测验卷。"""

    items: list[GeneratedQuizItem] = Field(description="题目列表")
