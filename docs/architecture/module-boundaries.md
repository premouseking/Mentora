# SmartStudy 模块边界

> 状态：与《端到端可落地实现方案》同步。正式实现前仍需用 ADR 冻结关键 Schema。

## 1. 领域模块

```text
courses
  课程、画像候选、课程配置版本、课程知识作用域、双确认状态与原子启动

sources
  用户资源库、文件夹与标签、原始资料、不可变资料版本、停用与删除生命周期

parsing
  解析任务、统一 ParsedBundle、元素坐标、解析质量

evidence
  EvidenceUnit、检索切块、引用快照和证据失效

topics
  主题、别名、前置关系、主题证据、范围候选解析

retrieval
  关键词/向量投影、混合召回、重排和权限过滤

learning
  学习计划修订、阶段/单元/任务模板、计划校验、任务、会话、学习事件和掌握度汇总

assessment
  官方/用户/AI 题目资产、题目版本、审校、组卷、作答、评分和原始掌握证据

recommendations
  网络资源发现、质量评估、推荐理由和采用记录
```

所有模块通过应用服务、DTO 和稳定 ID 通信。禁止跨模块直接修改数据模型。

## 2. 事实所有权

- `courses` 的规范化配置表是课程目标、范围、重点和节奏的唯一事实源；
- `CourseProfileCandidate` 只是模型填充面板的候选，不是课程事实；
- 模型提取置信度只属于候选；正式画像字段以用户确认、用户修改、系统默认或诊断事实
  表达权威来源；
- confirmed 画像不可修改，修改必须克隆为新草稿；
- `profile_snapshot_json` 只能由 `courses` 从规范化事实生成，不接受反向编辑；
- `ScopeCandidate` 可以没有 Topic，`CourseScopeItem` 必须关联已解析 Topic；
- `sources` 拥有用户资源库、原文件及版本关系，新增资料不得直接覆盖旧版本；
- `courses` 拥有 `CourseKnowledgeScopeRevision` 和 Binding，决定一门课程当前可访问
  哪些精确资料版本；`sources` 不能自行把资料加入课程；
- `sources` 只能提出“可能是新版本”的候选关系，是否归入同一 `Source` 由用户确认；
- `courses` 使用完整 Binding 快照运行，BindingDiff 只服务于影响分析和审计；
- 作用域草稿由 `lock_version` 控制并发，激活由 `courses` 在单一数据库事务内完成；
- 历史作用域不可重新激活，恢复历史配置必须创建新修订并重新校验；
- 上传资料不触发课程级 Topic、Claim 和冲突分析，只有加入作用域草稿后才触发；
- `parsing` 拥有解析过程和结构化结果，但不判断课程范围或资料优先级；
- `evidence` 拥有可引用证据及其有效性，`retrieval` 只保存派生索引；
- `topics` 拥有课程主题模型，但不能自行激活课程范围变更；
- `learning` 拥有 `LearningPlanRevision` 和路径卡片结构，但不能修改课程画像事实；
- 截止时间、总预算、范围、目标深度等变化必须由 `courses` 创建新画像修订；
- `courses` 负责最终启动事务，同时切换活动画像和活动计划；`learning` 不能单独激活
  一个与课程活动画像不匹配的计划；
- 未进入 `ready_to_start` 的计划不能物化可执行 `LearningTask`；
- `assessment` 产生带题目质量信息的原始证据，`learning` 负责汇总掌握度；
- `assessment` 拥有题目内容、答案、Rubric、验证状态和统计；`courses` 只选择题库
  或测验策略，不能直接修改题目；
- 课程选择官方题库只授权其用于组卷，不扩大 `CourseKnowledgeScopeRevision`，也不
  授权 Tutor 检索对应官方知识库全文；
- 固定卷预先固定精确 `AssessmentItemRevision`；自适应卷逐题固定
  `AssessmentAttemptItem`，题库更新不得改变已返回题位和历史测验；
- 模型只能创建 AI 候选题和辅助评分结果，不能直接发布官方题或写 `TopicMastery`；
- `assessment` 的实时 QualityGate 决定候选题能否进入测验；人工审核不阻塞普通
  动态练习；
- `learning` 提供学生状态和目标误区，`assessment` 将其转换为可审计的
  `LearnerQuestionTarget`，模型不能自行修改学生掌握度；
- 题目被隔离时由 `assessment` 撤销相关原始证据，`learning` 按事件重新汇总；
- FSRS 只由 `learning` 用于复习时间调度，不作为掌握度事实源；
- Agent 和工作流只能调用领域服务，不能绕过服务直接写领域表。

## 3. 基础设施模块

```text
workflow_runtime   显式持久状态机、检查点、租约、重试和取消
runtime_events     Outbox、持久事件和可恢复 SSE 投影
model_gateway      模型路由、结构化输出、Fallback 和调用记录
usage_ledger       Token、模型调用和内部成本结算
artifact_store     大型解析产物、快照和生成资源引用
```

边界约束：

- `workflow_runtime` 推进流程，不拥有课程、资料或学习事实；
- 状态迁移与 Outbox 必须在同一数据库事务提交；
- `runtime_events` 只投影已提交事件，不能替代领域状态；
- `model_gateway` 返回候选结果，字段授权和业务校验由领域服务执行；
- `artifact_store` 保存内容，不判断内容是否有效或应当参与计划；
- Agent checkpoint 只保存推理运行态，不能成为学生状态或课程状态的唯一来源。

## 4. 前端功能边界

前端按用户流程组织，不把每个小按钮拆成独立产品入口：

```text
src/features/
  courses/              课程入口与课程工作台
  course-profile/       澄清问题卡、画像草稿、字段依据和画像确认
  learning-plan/        阶段/单元/任务卡片、路径编辑、影响校验和最终启动
  library/              全局资源库、上传、整理、版本、停用和删除
  course-sources/       课程资料选择、角色、范围、影响分析和激活
  source-viewer/        PDF/Office/视频原文定位
  learning-session/     当前学习任务和学习包
  tutor/                提问、解释和证据引用
  assessment/           诊断、自测、作答反馈
  learning-map/         可执行主题地图
  recommendations/      网络资料推荐
  workflow-progress/    解析、生成和更新进度
```

约束：

- 服务端状态优先由 React Query 管理；
- 临时交互状态放在组件或功能级状态中；
- 不建立承载全部课程行为的全局 Zustand Store；
- 配置面板和澄清问题卡使用同一套 Patch API；
- 配置面板确认按钮是“生成学习方案”，只冻结画像并触发计划生成；
- 路径编辑器的“开始学习”才是最终启动入口；
- 路径卡片不能静默修改画像字段，相关操作必须跳转到画像草稿；
- 资源库操作不直接改变课程；课程资料修改先形成作用域草稿；
- 大流程页面可组合提问、测试等小流程，小流程不能反向控制整套课程状态机。

## 5. 后台队列边界

```text
orchestrator   流程推进、等待依赖、检查点和恢复
io             网页搜索、抓取、外部 API
parse-cpu      文本 PDF、Office、网页解析
parse-gpu      OCR、MinerU 和视觉解析
media          FFmpeg、ASR 和关键帧
embedding      Embedding 与检索投影
learning       计划重算、掌握度汇总和复习调度
ops            清理、对账和失活任务恢复
```

每个长任务必须：

- 使用稳定幂等键；
- 固定输入资料版本、处理器版本和配置版本；
- 支持取消、超时、有限重试和 Worker 丢失恢复；
- 对用户可见的任务上报阶段和进度；
- 只在阶段结果提交成功后更新检查点；
- 大结果写入 Artifact，任务状态只保存引用；
- 删除和重建派生数据时依据版本清单执行，不做无边界全库扫描。

## 6. 首期实现边界

M0 只实现：

```text
文本 PDF 上传到资源库
  -> 创建不可变 SourceVersion
  -> PyMuPDF 解析
  -> EvidenceUnit
  -> 课程选择并激活最小知识作用域
  -> PostgreSQL + pgvector 检索
  -> 结构化引用回答
  -> PDF 页码与坐标跳转
```

M0 不引入 Channels、WebSocket 或 LangGraph。进度与流式回答使用 SSE，流程使用
Celery 加显式持久状态机。扫描 PDF、Office、主题配置和学习闭环按主方案中的
M1、M2、M3 依次扩展。
