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


class PlanTaskItem(BaseModel):
    """学习任务。

    字段约定：
    - title：任务标题，前端直接展示
    - task_type：lecture / exercise / project / review
    - delivery_mode：text / interactive / video
    - estimated_minutes：建议时长
    - required：是否必修
    - source_evidence_ids：支撑该任务的 EvidenceUnit ID（资料范围约束时必填）
    """

    title: str = Field(description="任务标题")
    task_type: Literal["lecture", "exercise", "project", "review"] = Field(
        description="任务类型"
    )
    delivery_mode: Literal["text", "interactive", "video"] = Field(
        default="text",
        description="任务交付方式",
    )
    estimated_minutes: int = Field(default=30, ge=5, le=240, description="任务预估时长")
    required: bool = Field(default=True, description="是否必修")
    source_evidence_ids: list[str] = Field(
        default_factory=list,
        description="支撑该任务的 EvidenceUnit ID 列表",
    )


class PlanUnitItem(BaseModel):
    """学习单元/章节。"""

    title: str = Field(description="单元或章节标题")
    goal: str = Field(default="", description="本单元目标")
    target_depth: Literal["basic", "reinforce", "review", "skip"] = Field(
        default="basic",
        description="目标深度",
    )
    estimated_minutes: int = Field(default=60, ge=10, le=600, description="单元预估时长")
    source_evidence_ids: list[str] = Field(
        default_factory=list,
        description="支撑本单元的 EvidenceUnit ID 列表",
    )
    tasks: list[PlanTaskItem] = Field(description="单元下的细分任务")


class PlanPhase(BaseModel):
    """学习方案中的阶段卡。"""

    name: str = Field(description="阶段名称")
    goal: str = Field(description="阶段目标描述")
    share: int = Field(description="占比百分比", ge=5, le=50)
    units: list[PlanUnitItem] = Field(description="阶段下的细分章节/单元")


class TopicItem(BaseModel):
    """PlannerAgent 输出的主题-证据关联。"""

    name: str = Field(description="主题名称")
    evidence_ids: list[str] = Field(
        default_factory=list, description="支撑该主题的 EvidenceUnit ID 列表"
    )


class CoverageGapItem(BaseModel):
    """资料范围未能覆盖的学习目标片段。"""

    topic: str = Field(description="未能覆盖的主题或能力点")
    reason: str = Field(description="为何当前资料无法覆盖")
    suggested_action: str = Field(
        default="",
        description="建议用户采取的行动",
    )


class PlanResponse(BaseModel):
    """PlannerAgent 方案输出。

    title 字段由 LLM 根据用户目标生成简洁课程标题（≤15 字）。
    topics 由 LLM 根据资料内容自动标注主题-证据关联。
    coverage_gaps 仅在资料范围不足时列出缺口，不得把缺口生成为学习章节。
    """

    title: str = Field(description="课程标题，≤15字")
    phases: list[PlanPhase] = Field(description="学习阶段列表（4-5 个阶段）")
    topics: list[TopicItem] = Field(
        default_factory=list,
        description="主题与证据映射，LLM 自动标注",
    )
    coverage_gaps: list[CoverageGapItem] = Field(
        default_factory=list,
        description="资料范围未能覆盖的目标说明",
    )


class ContentBlockSchema(BaseModel):
    """ContentAgent 生成的单个内容块——字段按 type 区分。"""

    type: str = Field(description="heading / paragraph / citation / quiz / callout")
    id: str = Field(description="唯一标识，如 h-1 / p-1 / q-1")

    # heading
    label: str | None = Field(default=None, description="节标题文本")
    level: int | None = Field(default=None, description="标题级别 2 或 3")

    # paragraph
    text: str | None = Field(default=None, description="段落文本")
    modes: dict | None = Field(default=None, description="多模式 {simple, example, standard}")

    # citation
    evidence_id: str | None = Field(default=None, description="引用的 EvidenceUnit UUID")
    source_title: str | None = Field(default=None, description="资料名称")
    chapter: str | None = Field(default=None, description="章节")
    page_number: int | None = Field(default=None, description="页码")

    # quiz
    question: str | None = Field(default=None, description="题干")
    options: list[str] | None = Field(default=None, description="选项列表")
    correct_index: int | None = Field(default=None, description="正确选项索引 0-based")
    explanation: str | None = Field(default=None, description="答案解析")

    # callout
    variant: str | None = Field(default=None, description="tip / warning / info")
    # callout 复用 text 字段


class TaskContentOutput(BaseModel):
    """ContentAgent 生成的任务内容输出。"""

    content_blocks: list[ContentBlockSchema] = Field(description="按序渲染的内容块")
    source_evidence_ids: list[str] = Field(default_factory=list, description="引用的证据 ID 列表")
