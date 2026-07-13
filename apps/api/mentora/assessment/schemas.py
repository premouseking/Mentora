"""
评估模块 Pydantic Schema。

@module mentora/assessment/schemas
"""

from pydantic import AliasChoices, BaseModel, Field, field_validator, model_validator


class ItemValidationResult(BaseModel):
    """AI 自检结果——三要素校验。"""

    valid: bool = Field(description="是否通过校验")
    issues: list[str] = Field(
        default_factory=list,
        description="未通过时的具体问题列表",
    )


class GeneratedQuizItem(BaseModel):
    """LLM 生成的单道题目。"""

    question_text: str = Field(
        default="",
        validation_alias=AliasChoices("question_text", "question", "stem"),
        description="题干",
    )
    correct_answer: str = Field(
        default="A",
        validation_alias=AliasChoices("correct_answer", "answer"),
        description="正确选项标签 A/B/C/D",
    )
    difficulty: int = Field(default=3, description="难度 1-5")
    options: list[dict] = Field(
        default_factory=list,
        validation_alias=AliasChoices("options", "options_json", "choices"),
        description="选项列表",
    )
    explanation: str = Field(default="", description="答案解析")
    source_evidence_ids: list[str] = Field(
        default_factory=list, description="出题依据的证据 ID"
    )

    @field_validator("difficulty", mode="before")
    @classmethod
    def _coerce_difficulty(cls, value):
        try:
            return int(value)
        except (TypeError, ValueError):
            return 3

    @field_validator("source_evidence_ids", mode="before")
    @classmethod
    def _coerce_evidence_ids(cls, value):
        if isinstance(value, str):
            return [value] if value.strip() else []
        if isinstance(value, list):
            return [str(v) for v in value if str(v).strip()]
        return []


class GeneratedQuizPaper(BaseModel):
    """LLM 生成的完整测验卷。"""

    items: list[GeneratedQuizItem] = Field(default_factory=list, description="题目列表")

    @model_validator(mode="before")
    @classmethod
    def _normalize_root(cls, data):
        if isinstance(data, dict) and "items" not in data:
            if "questions" in data:
                return {**data, "items": data["questions"]}
            if "quiz_items" in data:
                return {**data, "items": data["quiz_items"]}
        if isinstance(data, list):
            return {"items": data}
        return data
