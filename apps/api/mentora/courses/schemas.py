"""
建课流程 Pydantic Schema：ClarifierAgent 结构化追问输出、PlannerAgent 方案输出。

约定：
- 所有 Schema 用于校验 LLM 结构化 JSON 输出
- 与前端 Phase / Question 类型对齐，保持字段名一致
- schema 名称用于 ModelGateway 的 structured_output_schema_name 参数

约束：
- ClarifierResponse.ready 决定追问是否终止
- PlanPhase.share 为百分比整数（10-50）

@module mentora/courses/schemas
"""

from typing import Literal

from pydantic import BaseModel, Field


class InquiryQuestion(BaseModel):
    """追问中的单个问题卡。

    字段约定：
    - text：直接问句，展示在主区域 h2
    - type：single_choice / multi_choice / free_text
    - options：选择题选项（非选择题为空列表）
    - guidance：引导说明（1-3 句），展示在左侧 AiMessageBubble
    """

    text: str = Field(description="问题文本，直接问句")
    type: Literal["single_choice", "multi_choice", "free_text"] = Field(
        description="问题类型"
    )
    options: list[str] = Field(default_factory=list, description="选择题选项")
    guidance: str = Field(
        default="",
        description="引导说明：为什么问这个问题、基于什么已知信息推断",
    )


class ClarifierResponse(BaseModel):
    """ClarifierAgent 追问输出。

    字段约定：
    - ready=false：返回 questions（1-3 个下一轮问题）
    - ready=true：返回 summary，表示信息足够生成方案
    """

    ready: bool = Field(description="是否已有足够信息生成学习方案")
    questions: list[InquiryQuestion] = Field(
        default_factory=list,
        description="下一轮追问问题（ready=false 时有效）",
    )
    summary: str = Field(
        default="",
        description="信息收集总结（ready=true 时给出）",
    )


class PlanPhase(BaseModel):
    """学习方案中的阶段卡。

    字段约定：
    - name：阶段名称（如「基础梳理」）
    - goal：阶段目标描述
    - share：占全部内容的百分比（整数 10-50）
    - tasks：代表性任务列表（3-6 项）
    """

    name: str = Field(description="阶段名称")
    goal: str = Field(description="阶段目标描述")
    share: int = Field(description="占比百分比", ge=10, le=50)
    tasks: list[str] = Field(description="代表性任务列表")


class TopicItem(BaseModel):
    """PlannerAgent 输出的主题-证据关联。"""

    name: str = Field(description="主题名称")
    evidence_ids: list[str] = Field(
        default_factory=list, description="支撑该主题的 EvidenceUnit ID 列表"
    )


class PlanResponse(BaseModel):
    """PlannerAgent 方案输出。

    title 字段由 LLM 根据用户目标生成简洁课程标题（≤15 字）。
    topics 由 LLM 根据资料内容自动标注主题-证据关联。
    """

    title: str = Field(description="课程标题，≤15字")
    phases: list[PlanPhase] = Field(description="学习阶段列表（4-5 个阶段）")
    topics: list[TopicItem] = Field(
        default_factory=list,
        description="主题与证据映射，LLM 自动标注",
    )
