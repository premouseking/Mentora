"""刷题模式结构化输出 Schema。"""

from pydantic import BaseModel, Field


class GeneratedQuizOption(BaseModel):
    label: str = Field(description="选项标签，例如 A/B/C/D")
    text: str = Field(description="选项正文")


class GeneratedQuizItem(BaseModel):
    question_text: str = Field(description="题干")
    options: list[GeneratedQuizOption] = Field(description="单选题选项")
    correct_answer: str = Field(description="正确选项标签，例如 A")
    explanation: str = Field(description="答案解析")
    difficulty: int = Field(default=3, ge=1, le=5, description="难度 1-5")
    source_evidence_ids: list[str] = Field(default_factory=list, description="引用证据 ID")


class GeneratedQuizPaper(BaseModel):
    items: list[GeneratedQuizItem] = Field(description="生成的题目列表")
