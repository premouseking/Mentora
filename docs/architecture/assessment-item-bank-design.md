# 题库、AI 出题与评测证据设计

> 状态：设计基线，待实现验证。  
> 首期定位：章节自测和学习诊断，不承担学校正式成绩或高风险认证考试。

## 1. 结论

SmartStudy 使用统一题目资产模型承载：

- 平台官方题库；
- 用户手工创建的题目；
- 从用户上传试卷、作业、答案册中提取的题目；
- 大模型根据课程资料生成的题目；
- 后续接入的授权第三方题库。

不同来源不建立互相割裂的题目系统，而是共用：

```text
ItemBank
  -> AssessmentItem
       -> AssessmentItemRevision
            -> ItemProvenance
            -> ItemTopicBinding
            -> ItemReviewRun / ItemReviewDecision
            -> ItemStatistics

AssessmentBlueprint
  -> AssessmentFormRevision
       -> AssessmentFormItem（仅 fixed）
             -> 固定 AssessmentItemRevision

AssessmentAttempt
  -> AssessmentAttemptItem
       -> 固定 AssessmentItemRevision
       -> ItemResponse
            -> ScoringResult
                 -> MasteryEvidence
```

核心规则：

1. 题目、测验、作答、评分和掌握证据是不同对象。
2. 题目修改必须创建不可变 `AssessmentItemRevision`。
3. 固定卷在开始前锁定全部题目版本；自适应练习在每道题返回前锁定该题位，已返回
   题目永远不能替换。
4. AI 动态出题是日常个性化练习主路径，但生成结果必须先作为候选题通过自动门禁。
5. 题目质量状态和可使用场景分离，采用分级准入。
6. 坏题被隔离后，历史作答仍保留，但相关掌握证据可以撤销并重算。
7. 普通实时题不等待人工审核；使用答案优先生成、独立验证、硬验证器、低权重证据和
   多题聚合控制风险。

实时动态出题的完整设计见
`docs/architecture/adaptive-ai-question-generation-design.md`。

## 2. 可选方案与选择

### 方案 A：官方题和 AI 题分别建库

实现简单，但组卷、统计、评分和掌握度需要维护两套分支，用户上传题目又会形成第三套
流程。长期不可维护，不采用。

### 方案 B：统一题目模型，按来源、验证等级和校准状态控制用途

官方题、用户题和 AI 题共享题目版本、审校、组卷和作答协议。来源只决定初始信任、
审核要求、版权范围和可用场景。采用此方案。

### 方案 C：所有 AI 题必须人工审核

质量最容易解释，但成本与响应速度不可接受，也无法支撑大量个性化练习。不采用全量
人工审核，只对平台官方题、复用价值高的题和高风险用途进入人工队列。

## 3. 题库层级

### 3.1 平台官方题库

由平台编辑或获得授权后导入，具备：

- 明确版权、授权范围和来源；
- 人工审校记录；
- 稳定知识主题映射；
- 可跨课程复用；
- 题目版本和退役机制；
- 真实使用统计。

官方题库不是因为名称相似就自动绑定到课程。平台可以推荐，用户需要明确选择参考哪个
官方题库或题目集合，再由系统映射到课程 Topic。

### 3.2 用户私人题库

包括：

- 用户手工录入；
- 从个人上传资料中提取；
- 用户保存的错题；
- 为个人课程生成的 AI 题。

默认仅用户本人可见，不自动进入平台官方题库。用户点击“这题可用”只表示个人接受，
不等同于平台人工验证。

### 3.3 课程题目池

课程题目池不复制题目正文，只保存允许用于该课程的精确题目版本或题库选择规则：

```text
CourseAssessmentPolicyRevision
  -> selected_item_bank_ids
  -> allowed_origins
  -> minimum_verification_by_purpose
  -> calibration_policy
  -> topic_mapping_revision
```

课程可以混用官方题、用户题和 AI 题。一次测验最终固定为
`AssessmentFormRevision` 和 `AssessmentAttemptItem`，历史测验不受题库后续变化影响。

评测 A0 不实现独立的课程题目池版本。章节自测只从当前课程明确选择的官方题库、
用户手工题和当前作用域生成的 AI 题中选题。固定卷在表单中固定题目版本，自适应卷在
每个 `AssessmentAttemptItem` 返回前固定题目版本。
`CourseAssessmentPolicyRevision` 在需要多题库管理时再引入；资料自动提题属于 A1。

评测 A0 使用最小关联：

```text
course_item_bank_binding
  id
  course_id
  item_bank_id
  enabled
  created_by
  created_at
  disabled_at
```

官方题库由用户在课程设置中明确选择，系统只做推荐，不根据课程名称自动绑定。关联
停用只影响未来组卷；历史固定卷和自适应卷中已经返回的 `AssessmentAttemptItem`
不受影响。

## 4. 题目版本与数据模型

### 4.1 题目身份和版本

```text
assessment_item
  id
  owner_scope                 platform | user | organization
  owner_id
  current_revision_id
  lifecycle_status           active | retired
  created_at

assessment_item_revision
  id
  assessment_item_id
  revision_number
  previous_revision_id
  item_type
  content_json
  answer_spec_json
  rubric_json
  language
  content_checksum
  lifecycle_status
  verification_level
  calibration_status
  known_issue_flags
  created_by
  created_at

item_bank
  id
  owner_scope
  owner_id
  name
  visibility                  private | shared | platform
  license_policy
  created_at

item_bank_entry
  item_bank_id
  assessment_item_id
  version_policy             pinned | latest_ready
  pinned_revision_id
  status
```

题目正文、选项、媒体和交互定义放在 `content_json`；正确答案和评分规则必须存入独立
受限字段，不能在开始作答前下发到客户端。

`latest_ready` 只用于题库维护和未来选题。固定卷的 `AssessmentFormItem` 和自适应
练习的 `AssessmentAttemptItem` 都必须固定 `AssessmentItemRevision`，不能在用户
作答过程中跟随最新版。

题目修订的内容载荷不可变：题干、选项、答案、Rubric、Topic 映射依据和来源证据一旦
离开 `draft` 就不能原地修改。生命周期、验证等级、校准状态和缺陷标记属于治理状态，
可以按审校流程变化；修正题目内容必须创建下一修订。

### 4.2 题型边界

评测 A0 支持：

- 单选题；
- 判断题；
- 确定性短答案；
- 数值题，支持单位和误差范围。

后续增加：

- 多选题；
- 排序和匹配；
- 分步计算；
- 解释题、证明题和代码题；
- 实践任务和项目量规。

首期不优先做多选题，因为“漏选如何计分”和“是否存在多个合理答案”会显著提高生成
审校复杂度。

### 4.3 来源和证据

```text
item_provenance
  id
  item_revision_id
  origin_type                 official_authored | user_authored | document_extracted
                              | ai_generated | third_party_imported
  source_version_id
  evidence_snapshot_id
  generation_run_id
  external_reference
  license_policy
  created_at

item_topic_binding
  item_revision_id
  course_topic_revision_id
  topic_id
  cognitive_level             recall | understand | apply | analyze | evaluate | create
  skill_tags
  target_misconception_ids
  alignment_confidence
```

AI 生成题必须固定：

- `CourseKnowledgeScopeRevision`；
- `TopicRevision`；
- 用于出题的 EvidenceUnit 快照；
- 生成任务配置；
- 模型、Prompt 和结构化输出 Schema 版本。

题目后续仍然可以被使用，但新测验的 Eligibility 检查需要确认其来源证据仍符合课程
当前作用域。历史测验和作答不修改。

题目准入不能扩大课程知识作用域：

- AI 生成题和文档提取题使用的 `SourceVersion` 必须仍在当前
  `CourseKnowledgeScopeRevision` 内；
- 平台官方题必须来自用户明确选择的 `ItemBank`，并映射到当前课程允许的 Topic；
- 选择官方题库只授权该题库用于组卷，不授权 Tutor 检索对应官方知识库全文；
- 超出当前考试范围、排除项或 Topic 范围的题，即使属于已选题库也不能进入测验。

## 5. 质量状态、验证等级和校准状态

生命周期、内容验证和统计校准不能混成一个状态。

生命周期：

```text
draft -> reviewing -> trial -> published -> retired
                     \-> rejected
published/trial -> quarantined
```

验证等级：

```text
unverified
auto_checked
human_verified
```

校准状态：

```text
none
collecting
calibrated
```

状态含义：

- `draft`：作者或模型正在创建，不可作答；
- `reviewing`：正在执行自动或人工审校；
- `trial`：允许低风险练习和数据收集；
- `published`：满足某类正式用途的准入要求；
- `quarantined`：发现严重缺陷，立即停止进入新测验；
- `retired`：正常退出使用，但保留历史；
- `rejected`：未通过审校，不进入题库。

验证等级不保证题目永远正确，统计校准也不能替代内容审核。即使已人工验证，后续仍
可能因投诉、资料变化或异常统计被隔离。

## 6. 不同用途的准入矩阵

准入由 `assessment_risk_profile` 决定，不由“AI 题”“官方题”或测验名称直接决定：

| 风险配置 | 典型用途 | 允许题目 | 对掌握度影响 |
| --- | --- | --- | --- |
| `practice_standard` | 练习与即时反馈 | 通过标准自动准确性门禁的 `auto_checked` 动态题或已验证题 | 低到中，按质量折扣 |
| `diagnostic_strict` | 章节诊断 | 通过加强门禁，或 `human_verified` | 中，多题、多题型聚合 |
| `mock_high_assurance` | 模拟考试 | 开考前通过高保证自动门禁；优先混入 `human_verified` 或 `calibrated` 锚定题 | 中到高，但仍非学校正式成绩 |
| `official_human` | 平台公开发布、认证 | 必须 `human_verified`；首期不支持正式认证 | 按具体制度定义 |

高保证自动门禁至少增加第二独立求解器、整卷覆盖检查、跨题答案泄露检查和预组卷后的
人工抽样；它不等同于把每一道模拟题送入人工审批。风险配置必须固定在
`AssessmentFormRevision`，不能在作答中途降低。

限制：

- 单道 `trial` 或 AI 新题不能使主题掌握度发生大幅变化；
- 高影响计划调整至少需要多道不同题型、不同 Item Family 的一致证据；
- 使用提示、重复作答和看过解析后的结果降低证据权重；
- 同一题目的重复作答不视为独立证据；
- 题目质量权重与作答表现权重分别计算。

## 7. AI 出题流程

本节只描述题库资产侧接口。实时生成采用：

```text
学生状态 -> LearnerQuestionTarget -> AnswerPlan -> 题目候选
  -> 确定性检查 -> 独立盲解 -> 歧义攻击 -> 领域硬验证 -> QualityGate
```

人工审核不参与普通实时链路。候选验证失败时重生成或回退，不能等待人工。

### 7.1 生成输入

```text
GenerationRequest
  course_scope_revision_id
  topic_revision_id
  target_topic_ids
  target_misconception_id
  cognitive_level
  difficulty_vector
  item_type
  count
  learner_constraints
  evidence_snapshot_id
  generation_policy_version
```

生成模型接收受控证据，不允许自行搜索用户整个资源库。系统先固定 `AnswerPlan`，再
生成结构化题目草稿：

```json
{
  "stem": "题干",
  "options": [
    {"id": "A", "text": "选项 A"},
    {"id": "B", "text": "选项 B"}
  ],
  "answer_spec": {"correct_option_ids": ["B"]},
  "rationale": "答案依据",
  "difficulty_band": "basic",
  "cognitive_level": "understand",
  "citations": [{"evidence_unit_id": "ev_123"}],
  "distractor_rationales": {
    "A": "对应的典型误区"
  }
}
```

### 7.2 自动审校

自动审校分层执行，避免所有检查都交给另一次大模型调用。

第一层，确定性检查：

- JSON Schema 和题型字段完整性；
- 正确答案数量合法；
- 选项不重复、答案不直接泄露在题干中；
- 数值题答案、单位和容差可执行；
- 引用 ID 属于生成证据快照；
- 题干长度、语言、危险内容和媒体引用合法；
- 与已有题目做精确哈希和文本近重复检查。

第二层，证据一致性检查：

- 正确答案能被引用证据支持；
- 题干没有引入证据外的关键条件；
- 解析和答案一致；
- 题目映射到指定 Topic；
- 资料中存在多种口径时没有把争议结论包装成唯一答案。

第三层，题目质量检查：

- 是否自包含；
- 是否存在多个合理答案；
- 干扰项是否明显无效；
- 难度与目标是否大致一致；
- 是否考查目标能力而不是文字陷阱；
- 是否过度复制原资料或已有题目；
- 是否包含无障碍和展示问题。

候选还必须执行独立盲解和歧义攻击。盲解器看不到生成器提供的答案和解析；能使用
数值、单位、规则或代码验证器的题型优先使用硬验证。任一硬门禁失败直接拒绝，软质量
分数不能抵消硬失败。

### 7.3 审校结果

```text
ItemReviewRun
  -> Finding[]
  -> ReviewScorecard
  -> Decision

Decision:
  accept_for_current_assessment
  regenerate
  fallback
  reject
```

以下情况直接拒绝或重新生成：

- 引用不存在；
- 答案无法从证据支持；
- 存在多个明显正确答案；
- 题目与目标 Topic 不相关；
- 题干依赖未提供的图片、前文或上下文；
- 与受限原题高度近似且没有复用权利；
- 包含提示注入、答案泄露或不可执行评分规则。

以下情况离开实时链路并进入人工队列：

- 计划进入平台官方题库；
- 使用 `official_human` 风险配置；
- 开放题或复杂量规；
- 自动验证模型意见冲突；
- 用户投诉或异常作答统计超过阈值；
- 题目有较高跨课程复用价值。

## 8. 官方题、提取题和 AI 题的不同审校

| 来源 | 初始验证等级 | 必需检查 | 默认可见范围 |
| --- | --- | --- | --- |
| 平台原创/授权题 | `unverified` | 编辑复核、答案、版权、展示与无障碍 | 审核后平台 |
| 用户手工题 | `unverified` | Schema、评分可执行性 | 用户私人 |
| 文档提取题 | `unverified` | OCR/结构置信度、题干和答案键定位 | 用户私人 |
| AI 生成题 | `unverified` | 全部自动审校和证据一致性 | 当前用户/课程 |
| 第三方导入题 | `unverified` | 格式、许可、答案与映射 | 按合同 |

“来自官方试卷”不自动等于平台 `human_verified`。如果只是用户上传的扫描件，OCR 和
答案提取仍可能出错，只能视为私人来源题。

## 9. 题目统计和质量晋升

统计必须按 `AssessmentItemRevision` 计算，不能把不同版本混在一起。

记录：

- 首次无提示作答数量；
- 正确率和置信区间；
- 作答时长分布；
- 跳过率；
- 选项选择分布；
- 干扰项有效性；
- 题目与总测验表现的相关性；
- 投诉、答案争议和评分覆盖率；
- 不同课程、能力层级和语言环境下的表现。

统计样本需排除或单独标记：

- 看过答案后的重复作答；
- 获得提示的作答；
- 网络异常或超短异常耗时；
- 已知机器人或批量测试流量；
- 同一用户短时间内的重复提交。

达到最小样本、统计稳定性和无严重缺陷后，题目的 `calibration_status` 可以转为
`calibrated`。这不会自动提升 `verification_level`。阈值按题型和用途配置，首期不
硬编码一个通用数字。

在没有足够数据前只使用可解释的难度档位，不伪装成精确 IRT 参数。

## 10. 组卷

### 10.1 测验蓝图

```text
assessment_blueprint
  id
  purpose                     practice | diagnostic | mock
  course_id
  topic_distribution_json
  cognitive_distribution_json
  difficulty_distribution_json
  item_type_distribution_json
  quality_policy_json
  time_budget_seconds
  item_count
  exposure_policy_json
  version
```

章节自测示例：

```text
5 题
  2 道回忆/理解
  2 道应用
  1 道易错点诊断
  至少 2 个不同 Item Family
  不使用本次会话已经完整展示过的题
```

### 10.2 选题流程

```text
读取当前课程作用域和 Topic 修订
  -> 根据学生状态构建 LearnerQuestionTarget
  -> 查找是否存在精确匹配的已验证题
  -> 无精确匹配时动态生成和执行自动准确性门禁
  -> 过滤权限、来源证据、Topic 范围和重复 Item Family
  -> 固定 AssessmentFormRevision 的蓝图、风险配置和停止条件
  -> fixed 模式固定全部 AssessmentAttemptItem
  -> adaptive 模式逐题固定并追加 AssessmentAttemptItem
```

不能在用户作答到一半时替换题目。题目不足时宁可减少题量并告知覆盖不足，也不能塞入
未完成审校的候选题。

系统在当前 Topic 即将完成时按学生状态预生成少量候选。学生表现偏离预测时，逐题
实时补充新的 `LearnerQuestionTarget`。达到生成预算仍不足时回退可靠题或减少题量，
不降低自动门禁。

### 10.3 Item Family

同一道题改数字、换选项顺序或轻微改写仍属于同一 `ItemFamily`。组卷和掌握度聚合需要
避免把同族题当作多份独立证据。

评测 A0 只使用显式 `parent_item_id`、参数模板 ID 或同一生成请求给出的
`family_key`。语义近重复聚类和自动等价题识别属于 A1。

## 11. 作答和评分

### 11.1 不可变作答

```text
assessment_form
  id
  course_id
  purpose
  mode                         fixed | adaptive
  current_revision_id
  created_at

assessment_form_revision
  id
  assessment_form_id
  mode                         fixed | adaptive
  assessment_risk_profile
  validation_policy_revision_id
  blueprint_snapshot_json
  course_scope_revision_id
  topic_revision_id
  adaptive_policy_version
  generation_policy_version
  stop_conditions_json
  item_selection_checksum      fixed 模式必填
  created_at

assessment_form_item
  form_revision_id
  item_revision_id
  position
  points

assessment_attempt
  id
  form_revision_id
  learner_id
  status
  controller_state_json
  lock_version
  started_at
  submitted_at

assessment_attempt_item
  id
  attempt_id
  position
  status                       reserved | generating | ready | delivered
                               | answered | cancelled
  item_revision_id             ready 后必填
  learner_question_target_json
  generation_run_id
  request_idempotency_key
  created_at
  delivered_at

item_response
  id
  attempt_id
  attempt_item_id
  response_json
  hint_count
  confidence
  elapsed_ms
  submitted_at
```

`fixed` 模式在 Attempt 创建时从 `AssessmentFormItem` 复制并固定全部
`AssessmentAttemptItem`。`adaptive` 模式只固定蓝图和策略，随后根据上一题结果逐题
追加 `AssessmentAttemptItem`。同一题位创建后不可替换，重连必须返回相同题目。

数据库至少设置：

- `UNIQUE(attempt_id, position)`；
- `UNIQUE(attempt_id, request_idempotency_key)`；
- `ItemResponse.attempt_item_id` 外键，不能只靠 `item_revision_id` 猜测题位；
- 只有 `ready` 题位可以转为 `delivered`，只有 `delivered` 题位可以提交作答；
- 更新自适应控制状态时校验 `assessment_attempt.lock_version`。

原始作答不可覆盖。用户修改答案时新增响应事件或保留版本，最终提交指向生效响应。

### 11.2 评分

评测 A0 的单选、判断、确定性短答案和数值题使用确定性评分器。

```text
scoring_result
  id
  item_response_id
  item_revision_id
  scorer_type
  scorer_version
  score
  max_score
  error_type
  rationale_json
  status
  created_at
```

开放题后续采用：

```text
规则预检查
  -> 基于固定 Rubric 的模型评分
  -> 输出分项分数、引用和不确定性
  -> 高不确定或高影响结果进入复核
```

模型评分只能产生 `ScoringResult`，不能直接写 `TopicMastery`。

## 12. 掌握度证据

```text
MasteryEvidenceWeight
  = purpose_weight
  * item_quality_weight
  * response_condition_weight
  * independence_weight
  * recency_weight
```

至少记录：

- 题目修订和 Item Family；
- 测验用途；
- 题目验证等级和校准状态；
- 评分结果和评分器版本；
- 是否首次、无提示作答；
- 作答耗时和用户置信度；
- 题目认知层级和难度档；
- 证据状态：`active | retracted | superseded`。

保护规则：

- 单道题对主题掌握度增减设置上限；
- 同一 Item Family 的重复证据边际递减；
- 至少多个独立题目才能达到高置信掌握；
- AI `trial` 题只产生低权重证据；
- 题目被隔离或评分规则有误时，撤销相关证据并重算派生掌握度；
- 撤销不删除作答和评分历史。

## 13. 缺陷发现和隔离

缺陷入口：

- 用户报告“答案有误”“题目不清楚”“超出范围”；
- 自动统计发现多答案倾向、无效干扰项或异常时长；
- 资料版本变化导致引用证据失效；
- 人工巡检；
- 评分器版本回归。

处理流程：

```text
创建 ItemIssue
  -> 风险分级
  -> 高风险题立即 quarantined
  -> 停止进入新测验
  -> 评估历史 ScoringResult 和 MasteryEvidence
  -> 必要时批量 retract 并重算
  -> 修订题目形成新 AssessmentItemRevision
  -> 重新审校后发布
```

历史测验仍展示用户当时实际看到的题目版本，并注明后续发现的问题。

## 14. 成本控制

- 日常练习先构建个性化测量目标，精确匹配时复用已验证题，否则动态生成；
- 只为当前学生和当前 Topic 维护小型候选池；
- 生成和自动审校异步进行，按 `Topic + ScopeRevision + PolicyVersion` 缓存；
- 评测 A0 每批最多生成少量题目，确定性过滤后再批量执行一次独立语义验证；
- 确定性规则先过滤，减少验证模型调用；
- 近重复检查先用哈希和向量召回，再对少量候选判断；
- 人工审核不阻塞实时链路，只按官方发布价值、风险抽样和投诉排序；
- 题目统计和质量晋升使用批处理，不在提交作答的同步路径计算；
- 模拟考试可以提前动态生成，但必须在开考前完成高保证门禁和固定组卷，不能在考试
  进行中临时生成未验证题目。

## 15. 导入导出和 QTI

1EdTech QTI 3 将题目、测试、结果和元数据作为可交换对象，并支持丰富题型与无障碍
语义。SmartStudy 的内部模型保持领域友好的 JSON 和关系表，后续增加 QTI 适配层：

```text
QTI package
  -> import validator
  -> canonical AssessmentItemRevision

AssessmentItemRevision / AssessmentFormRevision
  -> QTI exporter
```

评测 A0 不直接以 QTI XML 作为数据库事实源，避免为了尚未使用的完整规范增加实现负担。

## 16. 用户入口和页面流程

普通学生只看到三个主要入口：

```text
课程工作台“继续学习”
  -> 学完当前主题
  -> 开始 3-5 题快速自测
  -> 逐题反馈与资料引用
  -> 查看薄弱点和下一步

课程工作台“测试”
  -> 选择当前章节 / 多章节诊断
  -> 系统按用途自动组卷

课程设置“题目来源”
  -> 选择官方题库
  -> 查看个人上传或 AI 生成题
```

题目页面提供“答案有误”“题目不清楚”“超出范围”报告入口。AI 生成题显示来源标记，
提交答案后展示依据和资料引用。普通学生不需要操作验证等级、校准状态和审校队列。

平台运营人员使用独立题库工作台处理：

- 官方题录入与版本；
- 人工审校队列；
- 版权和授权信息；
- 投诉、隔离和修订；
- 题目使用与质量统计。

## 17. API 轮廓

```text
GET    /item-banks
POST   /item-banks
GET    /item-banks/{bankId}/items

POST   /courses/{courseId}/items/generation-runs
GET    /item-generation-runs/{runId}
GET    /item-generation-runs/{runId}/candidates

POST   /item-revisions/{revisionId}/review
POST   /item-revisions/{revisionId}/review-decisions
POST   /item-revisions/{revisionId}/issues

POST   /courses/{courseId}/assessment-forms
GET    /assessment-forms/{formId}
POST   /assessment-forms/{formId}/attempts
POST   /assessment-attempts/{attemptId}/next-item
POST   /assessment-attempts/{attemptId}/responses
POST   /assessment-attempts/{attemptId}/submit
GET    /assessment-attempts/{attemptId}/results
```

服务端创建测验表单时自行执行题目 Eligibility 检查。客户端不能通过提交任意
`item_revision_id` 绕过题目状态、课程范围或质量准入限制。

创建表单、提交响应和提交整份测验均使用 `Idempotency-Key`。重复提交返回原结果，
不能创建重复 Attempt、评分和掌握证据。

## 18. 分阶段实施

### A0：确定性章节自测

对应主项目“阶段二：计划与学习闭环”，在课程 Topic 和资料作用域链路稳定后实施。

- 用户私人题库和最小平台题库；
- 单选、判断、确定性短答案和数值题；
- 不可变题目修订；
- 官方题手工录入；
- 根据当前证据快照生成 AI 候选题；
- 答案优先生成；
- Schema、引用、独立盲解、歧义攻击和题型硬验证；
- 规则式多维难度自适应；
- `auto_checked` AI 题仅用于练习和低到中权重诊断；
- 固定题目版本的章节自测；
- 确定性评分；
- 缺陷报告、隔离和证据撤销；
- 不进行 IRT 或自动统计晋升。

### A1：用户资料提题和审核工作台

- 从试卷、作业和答案册提取题目；
- OCR 与题干/答案定位校正；
- 人工审校队列；
- 语义近重复聚类和 Item Family 辅助识别；
- 题目使用统计和质量面板；
- 课程题库选择策略。

### A2：开放题与高级诊断

- 解释题、证明题和代码题；
- Rubric 版本；
- 模型评分与不确定性；
- 多评分器复核；
- 错误类型和误区诊断；
- 迁移题。

### A3：模拟考试和标准交换

- 模拟考试蓝图；
- 高保证自动验证、人工抽样和统计校准题池；
- 曝光控制和等价卷；
- QTI 3 导入导出；
- 题目参数与 IRT 可行性评估。

## 19. 可行性审校

### 19.1 技术可行性

可行。评测 A0 的题型都可以用结构化 JSON 和确定性评分完成；题目版本、表单版本、
作答和评分适合存入 PostgreSQL。动态题使用一次生成、确定性过滤和隔离验证调用；
验证超时或失败时回退，不在同步路径无限重试。

### 19.2 质量可行性

不能承诺 AI 自动生成题达到官方题质量。可行的承诺是：

- 每道展示的 AI 题有来源证据、答案规划和自动门禁记录；
- 未通过完整自动门禁的候选不会展示；
- 多题聚合且单题影响受限；
- 用户可以报告问题；
- 坏题可以隔离并撤销掌握证据。

### 19.3 运营可行性

普通个人练习不进入人工审核。人工只投入平台官方发布、模拟考试组卷抽样、自动门禁
抽样评测、异常统计、投诉和高复用题目。

### 19.4 数据可行性

首期没有足够样本估计可靠的区分度或 IRT 参数。因此先保存原始统计并使用粗粒度难度
档位；达到样本门槛后再离线评估，不提前把模型预测难度当作真实参数。

### 19.5 安全与版权

- 用户上传试卷提取出的题目默认私人使用；
- 进入平台官方题库前必须确认版权或授权；
- AI 题执行近重复检查，避免大段复刻受限原题；
- 正确答案、Rubric 和评分规则不提前下发客户端；
- 日志不记录未脱敏的学生开放回答和隐藏答案；
- 防止题目内容中的提示注入影响生成和审校模型。

## 20. 验收不变量

1. 每次测验都能定位精确题目修订、课程作用域和 Topic 修订。
2. 题目发布新版本不会改变已固定或已返回的题位。
3. 未完成审校的题不能进入不允许的测验用途。
4. AI 题不能绕过证据快照访问用户整个资源库。
5. 单道低可信题不能显著改变掌握度。
6. 题目被隔离后不再进入新测验，相关证据可以撤销并重算。
7. 历史作答、原评分和重评分记录均可追溯。
8. 客户端不能在作答前获得答案或 Rubric。
9. 模拟考试必须在开考前完成高保证门禁并固定全部题位，不能在考试进行中临时生成。
10. 用户私人题目未经授权不能进入平台共享题库。
11. 普通动态题不等待人工审核，验证不确定时必须拒绝或回退。
12. 独立盲解器不能看到生成器答案和解析。
