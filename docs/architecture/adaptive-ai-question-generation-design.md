# 自适应 AI 出题与自动准确性门禁设计

> 状态：设计基线，待离线评测验证。  
> 适用范围：章节练习、即时诊断和个性化巩固。  
> 不适用范围：学校正式成绩、认证考试和无人复核的高风险评价。

## 1. 产品定位

日常学习中的题目主路径是：

```text
读取学生当前学习证据
  -> 决定下一题需要测量什么
  -> 从当前课程作用域选择事实依据
  -> AI 动态生成针对性题目
  -> 自动准确性门禁
  -> 通过后立即作答
  -> 用作答结果更新学习证据
  -> 决定下一题
```

官方题库不是日常个性化练习的唯一来源。它主要承担：

- 冷启动时的可靠题目；
- 自动生成连续失败时的回退；
- 诊断和模拟考试中的锚定题；
- 自动出题流水线的离线基准；
- 高复用、稳定内容的低成本供给。

已经存在且精确匹配当前测量目标的题可以复用，但系统不能为了复用题库而牺牲 Topic、
认知层级、误区和当前掌握状态的匹配度。

## 2. 人工审校的真实含义

人工审校不进入普通学生每次动态出题的同步路径。它只用于：

1. 平台公共题库发布；
2. 平台认证、公开排名等 `official_human` 高风险用途；
3. 用户投诉、自动验证冲突和异常统计；
4. 模拟考试预组卷、随机与风险分层抽样，评估自动门禁的误放率；
5. 建设离线金标集；
6. 调整生成策略、验证规则和模型路由。

人工审核的对象主要是“系统能力和高风险题目”，不是每一个人的每一道实时练习题。
实时链路遇到不确定题时直接拒绝、重试或回退，不等待人工处理。

### 2.1 风险配置

每个 `AssessmentFormRevision` 固定一个 `assessment_risk_profile`，它决定验证器数量、
硬门禁集合、最低软评分、可用题型、生成预算和证据权重：

| 风险配置 | 用途 | 自动验证要求 | 人工要求 |
| --- | --- | --- | --- |
| `practice_standard` | 即时练习 | 单独立盲解 + 标准硬门禁 | 无 |
| `diagnostic_strict` | 章节诊断 | 加强硬门禁 + 多题聚合 | 无，按风险抽样 |
| `mock_high_assurance` | 模拟考试 | 双独立盲解 + 整卷检查 + 开考前固定 | 组卷抽样，不逐题阻塞 |
| `official_human` | 公开发布、认证 | 高保证自动门禁 | 必须人工验证 |

风险配置只能提高，不能在同一 Attempt 进行中降低。模拟考试可使用同一生成流水线提前
产生题目，但不能在考试进行中临时展示尚未完成高保证验证的候选。

## 3. 总体架构

```text
AdaptiveQuestionController
  -> LearnerQuestionTarget
  -> EvidenceSelector
  -> AnswerPlanner
  -> QuestionGenerator
  -> DeterministicValidator
  -> IndependentSolver
  -> AmbiguityVerifier
  -> DomainVerifier
  -> QualityGate
  -> AssessmentItemRevision
  -> AssessmentAttemptItem
```

职责边界：

- `AdaptiveQuestionController`：根据学生状态决定测量目标和难度向量；
- `EvidenceSelector`：只从当前课程知识作用域选取证据；
- `AnswerPlanner`：先固定可验证答案和必要条件；
- `QuestionGenerator`：围绕答案和目标生成题干、选项、解析；
- Validator：独立校验事实、唯一答案、可作答性和评分可执行性；
- `QualityGate`：执行硬门禁和软评分，不负责生成；
- `assessment`：保存通过门禁的题目、表单、作答和评分；
- `learning`：消费 `MasteryEvidence`，不能直接相信生成模型的难度判断。

## 4. 学生状态到出题目标

### 4.1 `LearnerQuestionTarget`

```text
learner_question_target
  course_id
  topic_revision_id
  topic_id
  prerequisite_topic_ids
  current_mastery_band
  mastery_confidence
  target_misconception_id
  target_cognitive_level
  target_difficulty_vector
  item_type
  scaffold_policy
  novelty_policy
  excluded_item_family_ids
  source_event_ids
  policy_version
```

它表达“下一题为什么这样出”，而不是让模型自由猜测学生需要什么。

### 4.2 难度不是一个标签

```text
difficulty_vector
  cognitive_level            recall | understand | apply | analyze
  reasoning_steps            1..N
  prerequisite_count
  context_novelty            familiar | varied | transfer
  distractor_similarity      low | medium | high
  information_density
  scaffold_level             none | light | guided
  cross_topic_count
```

`predicted_difficulty` 是生成时的预测，`observed_difficulty` 来自后续真实作答统计。两者
必须分开，模型预测不能直接写成真实题目参数。

### 4.3 A0 自适应规则

首期采用可解释规则控制器，不上 IRT 或强化学习：

| 学生近期表现 | 下一题策略 |
| --- | --- |
| 当前 Topic 没有可靠证据 | 生成基础理解题和简单应用题，建立基线 |
| 错误且置信度高 | 针对最可能误区生成辨析题 |
| 错误且置信度低 | 降低一个维度或回到前置 Topic |
| 正确但耗时长 | 保持认知层级，换情境验证稳定性 |
| 正确但使用提示 | 保持难度，下一题减少提示 |
| 连续正确、无提示且耗时正常 | 一次只提高一个难度维度 |
| 同一 Item Family 已重复出现 | 强制更换题型、情境或测量方式 |
| 多次失败且原因不明确 | 停止继续加难，进入讲解或澄清 |

一次只改变一个主要难度维度，才能解释学生变化是由什么引起的。

## 5. 答案优先生成

不采用“一次调用自由生成题目、答案和解析”的方案。

```text
EvidenceUnit[]
  -> 提取可考查 Claim
  -> 固定 AnswerPlan
  -> 固定必要条件和允许知识范围
  -> 生成题干
  -> 生成干扰项或评分规则
  -> 生成解析和引用
```

`AnswerPlan`：

```text
answer_plan
  target_claim_ids
  claim_resolution_ids
  canonical_answer
  accepted_variants
  answer_authority_policy      course_primary | source_specific
                               | compare_sources
  required_reasoning_steps
  required_conditions
  forbidden_assumptions
  unit_spec
  tolerance_spec
  evidence_unit_ids
  source_conflict_ids
  planner_version
```

普通唯一答案题只能使用已经按当前课程口径解决的 Claim。若不同资料仍存在未解决冲突，
系统只能：

- 先触发课程配置澄清；
- 明确限定“根据某份教材/教师 PPT”后出题；
- 将学习目标改为比较不同口径；
- 或跳过该 Claim。

不能让生成模型自行选择它认为正确的资料口径。

优势：

- 答案可以在题干生成前单独校验；
- 题干只能使用已固定条件；
- 数值题可以先计算结果再表达问题；
- 干扰项可以围绕真实误区生成；
- 验证器能够重建答案，而不是相信生成器自报答案。

## 6. 自动准确性门禁

自动门禁由“硬门禁 + 软质量评分”组成。软评分不能抵消硬门禁失败。

### 6.1 硬门禁

任何一项失败都不得进入当前测验：

1. 结构化 Schema 合法；
2. 证据 ID 属于固定 `TurnEvidenceSnapshot`；
3. 题目只使用当前课程作用域允许的知识；
4. 普通唯一答案题不存在未解决的来源冲突或课程口径冲突；
5. 标准答案被来源证据和固定的 `answer_authority_policy` 支持；
6. 独立求解器得到兼容答案；
7. 单选或判断题不存在第二个合理答案；
8. 题干包含完成作答所需的全部条件；
9. 确定性评分器可以执行；
10. 题干、选项和解析没有答案泄露；
11. 没有命中高风险提示注入、版权复刻或危险内容规则。

### 6.2 确定性验证器

先执行低成本验证：

- JSON Schema；
- 选项 ID、唯一性和正确答案数量；
- Unicode、公式和媒体引用完整性；
- 数值答案、单位和容差；
- 引用权限；
- Claim 解决状态、课程口径和来源冲突状态；
- 精确重复和高相似候选召回；
- 题干与答案字符串泄露；
- 评分器 dry-run；
- 生成参数和题目字段一致性。

用户上传资料和网页内容一律作为不可信数据：进入模型前放入独立结构字段并标记来源，
禁止其文本改变系统指令或调用工具；检测到提示注入片段时隔离对应证据，不把“忽略前述
要求”等内容当作知识 Claim。

### 6.3 独立盲解

`IndependentSolver` 只接收：

```text
题干
选项
允许使用的证据
```

它不能看到生成器给出的标准答案、解析或干扰项理由。验证结果包括：

```text
derived_answer
reasoning_summary
used_evidence_ids
answerable
missing_conditions
alternative_answers
confidence
```

生成答案与盲解不一致、证据集合不同或验证器认为条件不足时，候选题失败。首期可以使用
同一基础模型的隔离调用，但不能在同一上下文中自我确认；高风险用途应使用不同模型或
硬验证器，降低相关错误。

### 6.4 歧义攻击

`AmbiguityVerifier` 的任务不是回答题目，而是主动寻找失败方式：

- 构造第二个合理答案；
- 找出缺失条件；
- 找出只在特定教材口径下成立的隐含前提；
- 检查否定词、范围词和量词歧义；
- 检查题干是否超出目标 Topic；
- 检查干扰项是否也能被证据支持；
- 检查解析是否循环论证或引用错误证据。

发现严重歧义直接拒绝，不把“模型多数意见”当作唯一答案证明。

### 6.5 领域硬验证器

| 题型 | 首选硬验证 |
| --- | --- |
| 判断题 | Claim 支持/反驳检查 + 独立盲解 |
| 单选题 | 逐选项证据判定 + 唯一答案检查 |
| 确定性短答案 | 规范化答案集合、别名和单位检查 |
| 数值题 | 表达式求值、容差、单位和边界条件 |
| 代码题（后续） | 隔离沙箱和隐藏测试 |
| 逻辑题（后续） | 规则或约束求解器 |

能用程序验证的内容不能只交给第二个大模型。

### 6.6 软质量评分

硬门禁通过后，再评估：

- 流畅性；
- 清晰度；
- 简洁性；
- Topic 相关性；
- 与来源一致性；
- 可回答性；
- 答案一致性；
- 目标认知层级匹配；
- 干扰项教学价值；
- 与近期题目的非重复性。

这些维度参考 QGEval 的多维评估思路，但 Mentora 的上线门禁必须通过自己的课程
金标集验证，不能直接假设 LLM 评委可靠。

## 7. 决策与降级

```text
all_hard_gates_pass && quality_score >= policy_threshold
  -> accept_for_current_assessment

repairable_failure && attempt_count < max_attempts
  -> regenerate_with_findings

validator_disagreement || uncertain
  -> reject_for_runtime

generation_budget_exhausted
  -> fallback
```

A0 建议每个题位最多生成两轮。失败后按顺序降级：

1. 使用精确匹配目标的已验证题；
2. 使用同 Topic、相邻难度的已验证题；
3. 使用参数模板生成并由硬验证器校验；
4. 减少本次题量并标记覆盖不足；
5. 返回讲解或等待稍后生成。

实时链路不等待人工审核，也不能因为题量不足降低硬门禁。

## 8. 运行数据模型

```text
adaptive_question_run
  id
  learner_id
  course_id
  assessment_attempt_id
  assessment_form_revision_id
  target_position
  request_idempotency_key
  assessment_risk_profile
  target_json
  course_scope_revision_id
  topic_revision_id
  learner_snapshot_id
  adaptive_policy_version
  generation_policy_version
  validation_policy_revision_id
  validation_budget_json
  status                       pending | generating | validating | accepted
                               | fallback | failed | cancelled
  created_at

question_generation_attempt
  id
  adaptive_question_run_id
  attempt_number
  evidence_snapshot_id
  answer_plan_json
  candidate_artifact_id
  generator_model_request_id
  status
  created_at

question_validation_run
  id
  generation_attempt_id
  assessment_risk_profile
  validation_policy_revision_id
  deterministic_result_json
  independent_solver_result_json
  ambiguity_result_json
  domain_verifier_result_json
  quality_scorecard_json
  decision
  accepted_item_revision_id
  created_at
```

只有通过门禁的候选才创建 `AssessmentItemRevision`。失败候选作为短期 Artifact 保留，
用于调试和离线评测，不污染正式题库。

`UNIQUE(assessment_attempt_id, target_position)` 保证同一题位只有一个运行实例。
`AssessmentAttemptItem.generation_run_id` 指回该运行，不在两张表之间建立双向必填外键。

### 8.1 验证策略修订

```text
question_validation_policy_revision
  id
  assessment_risk_profile
  domain_key
  item_type
  hard_gate_config_json
  minimum_quality_scores_json
  independent_solver_routes_json
  timeout_budget_json
  max_generation_attempts
  fallback_policy_json
  status                       draft | shadow | active | retired
  created_at
```

策略修订一旦激活不可修改。新策略先进入 `shadow`，完成离线回放和线上影子验证后再成为
`active`；进行中的 Attempt 继续使用表单修订已经固定的策略，不能自动漂移到最新版。

## 9. 实时序列

```text
上一题提交
  -> 写入 ItemResponse 和 ScoringResult
  -> 产生原始 MasteryEvidence
  -> AdaptiveQuestionController 以乐观锁更新 Attempt 控制状态
  -> 构建下一题 LearnerQuestionTarget
  -> 查询是否有精确匹配的已验证题
  -> 无精确匹配则动态生成和验证
  -> 固定题目修订并追加 AssessmentAttemptItem
  -> 返回下一题
```

自适应练习的 `AssessmentFormRevision` 固定蓝图和策略，实际题目逐题追加到
`AssessmentAttemptItem`。已经返回给用户的题目位置和版本不可修改。服务端使用
`attempt_id + next_position` 和 `Idempotency-Key`，避免断线重试产生两道不同的
“下一题”。

生成和多模型验证可能持续数秒，不能在整个过程持有数据库行锁。`next-item` 采用短事务
占位：

1. 锁定 Attempt，校验上一题已回答、停止条件未满足且没有可直接返回的下一题；
2. 创建 `reserved` 的 `AssessmentAttemptItem` 和唯一
   `AdaptiveQuestionRun(attempt_id, position)`，提交事务；
3. Worker 在事务外生成和验证，客户端轮询或通过 SSE 接收状态；
4. 通过门禁或完成可靠回退后，在短事务中写入固定题目修订并将题位改为 `ready`；
5. 返回题目时原子改为 `delivered`；相同幂等键始终返回同一题位；
6. 超时恢复任务只接管原 Run，不创建新的同位置题位。

接口语义：

- 已有 `ready/delivered` 题位返回 `200`；
- 正在生成返回 `202` 和 `run_id`；
- 上一题未回答或 Attempt 已结束返回 `409`；
- 生成预算耗尽且无可靠回退时返回覆盖不足结果，不留下永远 `generating` 的题位。

## 10. 延迟和成本

日常路径不能对每道题调用多个昂贵模型。A0 采用：

```text
规则控制器
  -> 一次答案规划与批量候选生成
  -> 确定性过滤
  -> 一次批量独立盲解/歧义验证
  -> 必要时单题重试
```

策略：

- 当前 Topic 学习接近完成时预生成少量不同难度候选；
- 学生实际表现偏离预测时再实时补题；
- 生成器使用结构化输出；
- 验证器批量处理已通过确定性过滤的候选；
- 数值和规则题优先使用硬验证器；
- 通过门禁的题允许在精确匹配其他学生目标时复用；
- 缓存键包含 Topic、课程作用域、难度向量、误区、题型和策略版本；
- 设置单次练习生成预算、重试上限和超时；
- 失败回退，不在用户等待路径无限重试。

AI 动态生成是产品主能力，但“动态”不等于每次都必须生成全新措辞。已经验证且精确匹配
当前测量目标的题可以复用，从而降低成本和提高稳定性。

## 11. 人工抽检与离线评测

### 11.1 金标集

按课程领域、题型和难度维度建立：

- 固定 SourceVersion 和 EvidenceUnit；
- 专家确认的 Claim 和答案；
- 可接受与不可接受题目；
- 多答案、缺条件、冲突资料、单位错误和超范围反例；
- 真实学生误区样例。

### 11.2 关键指标

```text
critical_false_accept_rate
answer_support_precision
independent_solver_agreement
ambiguity_escape_rate
scorer_execution_success_rate
topic_alignment_rate
difficulty_prediction_error
user_issue_rate
post_use_quarantine_rate
average_generation_cost
p95_question_ready_latency
fallback_rate
```

最重要的是误放率，而不是自动门禁总体通过率。宁可拒绝部分可用题，也不能稳定地把
错误答案交给学生。

指标必须按 `domain_key + item_type + assessment_risk_profile +
validation_policy_revision_id` 分层统计，不能用全平台平均值掩盖某一学科或题型的失败。
策略晋升不能只看点估计，应同时满足：

- 金标样本量达到该分层的最低要求；
- `critical_false_accept_rate` 的置信上界低于该风险配置阈值；
- 答案支持率、唯一答案检查和评分执行成功率分别达标；
- 新策略相对当前策略没有显著提高用户问题率、回退率或 P95 延迟；
- 所有硬门禁反例类别至少有一个回归样本。

### 11.3 上线方式

1. 离线金标回放；
2. Shadow 模式生成和验证，但不展示给学生；
3. 人工抽检自动通过与自动拒绝样本；
4. 小流量低风险练习；
5. 按题型和课程领域分别放量；
6. 持续抽样，验证器或模型升级后重新回放。

抽检采用随机样本加风险分层样本，重点覆盖新模型、新课程领域、低置信验证、用户投诉
和高复用题。人工结果用于评估门禁，不直接成为普通实时题的必经审批。

### 11.4 A0 建议发布门槛

以下是首期工程基线，不是永久产品承诺；获得真实数据后通过策略修订调整：

| 指标 | `practice_standard` 建议门槛 |
| --- | --- |
| 分层金标样本 | 每个启用的学科域与题型至少 300 个，包含系统性反例 |
| 关键错误误放率 | 95% 置信上界低于 1% |
| 答案证据支持精度 | 不低于 99% |
| 确定性评分执行成功率 | 100% |
| 提示注入与越权证据逃逸 | 安全回归集为 0 |
| 幂等与并发重复题位 | 压测和故障注入中为 0 |
| 实时生成 P95 | 8 秒内；超时走可靠回退，不降低门禁 |

`diagnostic_strict` 和 `mock_high_assurance` 必须使用更严格阈值或更多独立验证，但具体值
应在对应金标规模足够后冻结，不能用未经验证的任意百分比制造“精确感”。

## 12. 准确性边界

系统不能承诺 AI 题百分之百正确。可落地的承诺是：

- 每道展示题都固定来源证据；
- 答案先于题干规划并经过独立重建；
- 可程序验证的题使用硬验证；
- 严重歧义或验证不一致时题目不会展示；
- 单道动态题对掌握度的影响受限；
- 用户可以查看依据并报告问题；
- 发现问题后可以隔离题目、重评分和撤销掌握证据；
- 每次模型或验证策略升级都经过离线回放和抽样审计。

## 13. 工程实现拆分

### 13.1 服务组件

| 组件 | 技术与职责 |
| --- | --- |
| `assessment` 领域服务 | Django + DRF；表单、Attempt、题位、题目修订、作答和评分 |
| `AdaptiveQuestionController` | Python 纯领域服务；读取学习快照并生成可解释目标 |
| `GenerationWorker` | Celery `assessment-generation` 队列；答案规划和候选生成 |
| `ValidationWorker` | Celery `assessment-validation` 队列；盲解、歧义和领域验证 |
| 结构校验 | Pydantic/JSON Schema；所有模型输出先解析再进入领域对象 |
| 硬验证插件 | Python 插件接口；数值题可使用受限表达式求值或 SymPy，代码题后续接沙箱 |
| 持久化与并发 | PostgreSQL；唯一约束、短事务、乐观锁和 Outbox |
| 实时状态 | SSE；发布 `reserved/generating/validating/ready/failed` 事件 |
| 模型调用 | 统一 `model_gateway`；记录模型、提示模板、Token、延迟和策略修订 |
| 观测 | OpenTelemetry + Prometheus 指标；按学科、题型、风险配置和策略修订分层 |

生成器和验证器通过领域 DTO 交互，不能共享自由文本对话历史。Celery 任务只传主键和
版本号，不在消息体复制用户整份资料或隐藏答案。

### 13.2 测试体系

- Schema 合约测试：缺字段、越权引用、非法答案结构必须拒绝；
- 金标回放：正确题通过，错误答案、多答案、缺条件、冲突口径题被拒绝；
- 变异测试：主动翻转单位、删除条件、交换答案、加入第二正确选项，验证门禁能拦截；
- 变形测试：选项顺序变化、等价数值表达不应改变标准答案；
- 验证器隔离测试：盲解请求中不能出现生成器答案、解析和干扰项理由；
- 并发与故障注入：重复 `next-item`、Worker 超时、重试和进程退出不能产生重复题位；
- 安全回归：用户资料中的提示注入、越权证据 ID 和恶意公式不能逃逸；
- 统计回归：新模型或策略对关键误放率、回退率、延迟和成本的变化可比较。

## 14. A0 实施边界

A0 支持：

- 单选、判断、确定性短答案和数值题；
- 规则式 `AdaptiveQuestionController`；
- 多维难度向量；
- 答案优先生成；
- 当前课程证据快照；
- Schema、盲解、歧义和题型硬验证；
- 两轮以内重新生成；
- 已验证题和题量缩减回退；
- 动态题的低到中权重 `MasteryEvidence`；
- 题目问题报告和证据撤销；
- 离线金标、Shadow 和人工抽检。

A0 不支持：

- 无约束开放题；
- 正式考试；
- IRT、自适应测验最优化或强化学习策略；
- 依靠 LLM 自报难度作为真实参数；
- 每道动态题人工审批；
- 验证失败后仍把题展示给用户。

## 15. 验收不变量

1. 生成器不能访问课程作用域外资料。
2. 独立盲解看不到生成器标准答案和解析。
3. 任一硬门禁失败的候选不能进入当前测验。
4. 验证器不确定时采用拒绝或回退，不采用多数投票强行通过。
5. 难度一次只提升一个主要维度，并记录策略原因。
6. 模型预测难度与真实统计难度分开存储。
7. 相同 Attempt 和题位只能产生一个 `AssessmentAttemptItem`，相同幂等键返回同一题。
8. 动态题被隔离后，历史作答保留，相关掌握证据可以撤销。
9. 人工审核不阻塞普通学生实时练习。
10. 新模型或验证策略未通过离线回放前不能进入生产动态出题。
