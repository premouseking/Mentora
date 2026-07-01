"""学习模块 Pydantic Schema。"""

from pydantic import BaseModel, Field


class ExplanationSummaryOutput(BaseModel):
    """LLM 结构化输出：对话摘要归档。"""

    keywords: list[str] = Field(description="3-8 个关键词，小写")
    summary_md: str = Field(description="Markdown 格式的对话总结")
    suggested_title: str = Field(description="若新建文件时的标题")
    doc_type: str = Field(default="知识点讲解", description="讲解类型标签")
