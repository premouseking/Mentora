# 课程知识作用域版本管理设计

> 状态：设计基线，待实现验证。  
> 适用范围：用户资源库、课程知识作用域、学习会话临时资料范围和单轮证据追溯。

## 1. 结论

SmartStudy 需要版本管理，但不采用 Git 式文件补丁链，也不对所有对象无差别版本化。

采用以下模型：

```text
资料身份版本
Source -> SourceVersion

课程选材版本
Course -> CourseKnowledgeScopeRevision -> CourseScopeBinding[]

会话临时调整版本
LearningSession -> SessionScopeOverlayRevision

单次调用事实快照
TurnEvidenceSnapshot
```

核心策略是“完整作用域快照 + 持久差异 + 不可变证据快照”：

- 每个课程作用域修订保存完整 Binding 集合，运行时不重放历史事件；
- `BindingDiff` 保存相对当前生效版本的变化，用于影响分析和用户确认；
- 历史修订不修改、不复活，回滚通过创建一个新的修订完成；
- 原文、解析结果和 Embedding 不随作用域修订复制，只保存稳定 ID；
- 只有变化涉及的资料版本、范围和 Topic 进入增量分析。

## 2. 为什么需要两类版本

### 2.1 `SourceVersion` 解决“资料内容是什么”

同一个逻辑资料可能存在教材修订版、教师更新后的 PPT、重新抓取的网页或修正后的
讲义。文件内容变化时创建新的不可变 `SourceVersion`。

以下操作不产生内容版本：

- 修改标题；
- 移动文件夹；
- 增删标签；
- 修改用户备注；
- 调整课程中的角色或优先级。

系统只能建议两个文件可能属于同一 `Source`，不能自动确认版本关系。用户需要选择：

- 作为旧资料的新版本；
- 作为独立资料；
- 作为重复文件丢弃；
- 暂不处理。

M0 提供两个明确入口：

- “上传新资料”：直接创建新的 `Source` 和第一个 `SourceVersion`；
- “为该资料上传新版本”：用户先选择已有 `Source`，再创建下一 `SourceVersion`。

普通上传后的智能版本候选属于后续能力。候选文件在用户确认版本关系前不能自动改写
已经被课程引用的 `source_id`。如果候选已经作为独立资料被使用，只能保留两个 Source
并建立 `supersedes` 或 `related` 关系；只有尚未被任何课程、回答或产物引用的临时
Source，才能通过受审计的合并操作归入已有 Source。

### 2.2 `CourseKnowledgeScopeRevision` 解决“课程允许使用什么”

课程作用域是一个业务配置版本。即使资料本身没有变化，以下操作也会产生新的作用域
修订：

- 添加或移除资料；
- 将资料从参考资料调整为考试范围；
- 改变允许使用的页码、章节或时间段；
- 将绑定从旧 `SourceVersion` 升级到新版本；
- 停用某个 Binding；
- 调整检索优先级。

这两个版本不能合并。`SourceVersion` 属于用户资源库，可能被多门课程复用；
`CourseKnowledgeScopeRevision` 属于单门课程，表达该课程在某一时刻的选材决定。

## 3. 不应版本化的对象

| 对象 | 处理方式 | 原因 |
| --- | --- | --- |
| 文件夹、标签、展示标题 | 原地更新并记录普通审计事件 | 不影响资料事实内容 |
| 上传和解析任务 | `Run/Attempt` 状态记录 | 属于执行记录，不是业务版本 |
| Embedding | 使用模型与处理器版本作为缓存键 | 属于可重建投影 |
| 资源列表排序、筛选条件 | 用户偏好 | 不影响课程知识边界 |
| 草稿中的每次点击 | 更新草稿并递增 `lock_version` | 不应制造大量无意义修订 |

草稿只有在用户请求影响分析时才冻结输入并形成可确认版本。用户连续增删资料时，前端
本地合并操作并批量提交，不逐次运行影响分析。

## 4. 数据模型

### 4.1 资料版本

```text
source
  id
  owner_id
  latest_version_id
  status
  created_at

source_version
  id
  source_id
  version_number
  previous_version_id
  content_sha256
  object_key
  media_type
  byte_size
  processing_status
  created_at

source_version_candidate
  id
  uploaded_source_version_id
  candidate_source_id
  similarity_features_json
  confidence
  status                     pending | accepted | rejected | duplicate
  decided_by
  decided_at

source_relation
  id
  from_source_id
  to_source_id
  relation_type              supersedes | supplements | related
  created_by
  created_at
```

`previous_version_id` 只表达同一 `Source` 内的版本顺序。不同资料之间的相关、引用或
补充关系由独立关系表表达，不能滥用版本链。

### 4.2 作用域修订

```text
course_knowledge_scope_revision
  id
  course_id
  revision_number
  parent_revision_id
  base_active_revision_id
  restored_from_revision_id
  status
  lock_version
  change_summary
  binding_set_checksum
  analyzed_binding_checksum
  analyzer_version
  created_by
  created_at
  analysis_started_at
  activated_at
  discarded_at

course_scope_binding
  id
  scope_revision_id
  binding_key
  source_version_id
  role
  selector_type
  selector_json
  priority
  version_policy
  enabled
  user_note
  created_at

scope_binding_change
  id
  scope_revision_id
  binding_key
  operation                  add | remove | replace_version | change_selector
                             | change_role | change_priority | enable | disable
  before_json
  after_json
  created_at

scope_impact_report
  id
  scope_revision_id
  base_active_revision_id
  binding_set_checksum
  course_profile_revision_id
  topic_revision_id
  analyzer_version
  affected_topic_ids
  conflict_ids
  invalidated_artifact_ids
  plan_change_summary_json
  status
  created_at
```

M0 尚未建立完整 Topic 修订时，`topic_revision_id` 允许为空；此时影响分析只计算资料、
页段和检索可用性变化。进入 Topic 阶段后，该字段必须存在并在激活时校验。

`binding_key` 是跨修订稳定的 UUID。复制作用域草稿时保留它，因此系统能识别“同一个
绑定更换了资料版本”，而不是误判为一次删除加一次新增。

约束：

- `course_id + revision_number` 唯一；
- `scope_revision_id + binding_key` 唯一；
- 同一课程最多一个 `active` 修订；
- M0 同一课程最多一个未完成草稿；
- `active`、`superseded` 和 `discarded` 修订不可修改；
- Binding 必须引用当前用户有权访问且未物理删除的 `SourceVersion`。

修订号在创建草稿时分配，允许因草稿废弃出现间断。课程行保存
`next_scope_revision_number`，创建草稿时锁定课程行并原子递增，避免并发执行
`MAX(revision_number) + 1`。

`replace_version` 只用于同一 `Source` 内升级 `SourceVersion`，并保留原
`binding_key`。将资料更换为另一个 Source 必须表示为 `remove + add`，避免错误继承
范围选择器和用户说明。

`binding_set_checksum` 使用字段白名单、稳定键顺序和规范化 JSON 计算，至少覆盖
`binding_key`、`source_version_id`、角色、选择器、优先级、版本策略和启用状态。
展示标题、文件夹和标签不进入校验和。

### 4.3 范围选择器

不同资料格式不能共用一个模糊的 `included_ranges_json`。采用带类型的选择器：

```text
selector_type = whole_document
selector_json = {}

selector_type = pdf_pages
selector_json = {"ranges": [{"from": 10, "to": 35}]}

selector_type = section_ids
selector_json = {"section_ids": ["sec_1", "sec_2"]}

selector_type = media_time_ranges
selector_json = {"ranges": [{"from_ms": 120000, "to_ms": 360000}]}
```

选择器必须经过 JSON Schema 校验并规范化后参与校验和计算。更换 `SourceVersion`
时旧选择器不一定仍然有效：

- `whole_document` 可以直接迁移；
- 页码或时间段只有在新版边界仍合法时才能迁移；
- 结构化章节需要建立新旧 `ParsedElement` 映射；
- 无法可靠映射时进入用户确认，不能静默扩大范围。

## 5. 状态机

```text
draft
  -> analyzing
       -> pending_confirmation
       -> draft                 分析失败或输入已失效

pending_confirmation
  -> active
  -> draft                      用户继续编辑
  -> discarded

active
  -> superseded                 新修订激活

draft/analyzing
  -> discarded
```

状态语义：

- `draft`：允许编辑，每次写入递增 `lock_version` 并清空旧分析有效标记；
- `analyzing`：冻结 Binding 输入，不接受编辑；
- `pending_confirmation`：影响报告与 `analyzed_binding_checksum` 匹配，可等待确认；
- `active`：课程运行时唯一读取的作用域；
- `superseded`：历史生效版本，只读保留；
- `discarded`：未生效草稿被放弃，不进入运行时。

如果用户在 `pending_confirmation` 状态继续编辑，系统将修订恢复为 `draft`，递增
`lock_version`，并把原影响报告标记为过期。

## 6. 增量变更与影响分析

### 6.1 编辑过程

```text
从当前 active 修订复制完整 Binding 集合
  -> 用户批量编辑草稿
  -> 规范化 Binding
  -> 计算 binding_set_checksum
  -> 与 base_active_revision_id 做集合差异
  -> 持久化 scope_binding_change
  -> 分析受影响对象
```

作用域快照复制的只是 Binding 元数据，不复制原文件、正文、证据或向量。

### 6.2 按变更类型选择分析范围

| 变更 | 必须执行 | 不需要执行 |
| --- | --- | --- |
| 添加资料 | 新资料 Topic/Claim 对齐、覆盖变化、冲突候选 | 重新解析其他资料 |
| 移除资料 | 剩余覆盖检查、未来任务与引用有效性检查 | 修改历史回答 |
| 同一 Source 更换版本 | 新旧版本内容差异、选择器迁移、受影响 Topic | 全课程两两比较 |
| 修改范围选择器 | 只处理范围对称差覆盖的 EvidenceUnit | 重新解析整份资料 |
| 修改角色或优先级 | 检索权重、计划来源策略 | OCR、解析和 Embedding |
| 修改标题、文件夹或标签 | 无课程影响分析 | 任何课程派生重建 |

高成本分析只在用户点击“查看影响”、尝试激活或系统检测到已冻结草稿需要恢复时执行。
草稿编辑本身只做权限、选择器和基础唯一性校验。

### 6.3 分析缓存

影响分析缓存键至少包含：

```text
base_active_revision_id
binding_set_checksum
analyzer_version
course_profile_revision_id
topic_revision_id
```

相同输入重复请求直接复用报告。任何 Binding 变化都会改变校验和，使旧报告自动失效。
分析任务使用 `scope_revision_id + binding_set_checksum + analyzer_version` 作为
幂等键，避免用户重复点击产生并发重复分析。

## 7. 并发控制

草稿编辑使用乐观锁：

```http
PATCH /knowledge-scope/revisions/{id}/bindings
If-Match: "<lock_version>"
Idempotency-Key: "<command-id>"
```

`If-Match` 不匹配返回 `412 Precondition Failed`，同时返回服务器当前草稿摘要。
前端让用户重新加载，不自动覆盖另一窗口中的修改。

激活使用 PostgreSQL 事务：

1. `SELECT ... FOR UPDATE` 锁定课程行；
2. 校验 `base_active_revision_id` 仍等于课程当前 active 修订；
3. 校验修订状态为 `pending_confirmation`；
4. 校验 `binding_set_checksum == analyzed_binding_checksum`；
5. 校验影响报告的 Binding checksum、课程配置版本、Topic 版本、权限、资料和必需
   索引仍有效；
6. 将原 active 修订标记为 `superseded`；
7. 将新修订标记为 `active`；
8. 更新课程的 `active_knowledge_scope_revision_id`；
9. 写入 Outbox 事件；
10. 提交事务。

如果基础 active 修订已变化，激活返回 `409`。用户需要从新 active 修订创建草稿并
重新应用自己的差异，不能强行覆盖。

课程首次激活时 `base_active_revision_id` 允许为空，但事务仍需锁定课程行，并校验
课程当前 active 指针也为空。

## 8. 激活前后的处理边界

激活前必须完成：

- 资料访问权限和有效状态校验；
- 范围选择器校验；
- 解析、EvidenceUnit 和首选检索投影达到可查询状态；
- BindingDiff 和影响报告生成；
- 高影响冲突完成用户确认。

激活后可以异步完成：

- 非关键缓存预热；
- 学习包重新生成；
- 推荐资源重排；
- 未开始学习任务的局部重建。

作用域激活事务必须同步标记受影响计划或任务为 `needs_replan`。在新计划准备完成前，
系统不能继续执行已失去资料依据的任务。

## 9. 新资料版本处理

上传新文件只进入用户资源库，不直接改变课程。

```text
通过“上传新版本”入口
  -> 用户明确选择已有 Source
  -> 创建下一 SourceVersion
  -> 查找采用 notify_on_new_version 的课程 Binding
  -> 为用户生成“可升级”建议
  -> 用户选择课程并创建作用域草稿
  -> 执行影响分析和激活流程
```

普通上传产生独立 Source。后续智能候选只负责建议和建立关系；除非临时 Source 从未
被课程或历史产物引用，否则不能把已经生效的 SourceVersion 静默移动到另一条版本链。

版本策略：

- `pinned`：继续使用当前版本，只展示新版存在；
- `notify_on_new_version`：生成升级建议，但不创建或激活作用域修订；
- 不提供“自动升级并激活”，避免考试范围和教师口径被静默改变。

## 10. 回滚

不能把课程指针直接改回历史修订。历史资料可能已经停用、权限变化、选择器失效，依赖
的课程配置和 Topic 版本也可能不同。

正确流程：

```text
选择历史修订 R5
  -> 以当前 active 修订 R9 为 base
  -> 克隆 R5 的 Binding 集合形成新草稿 R10
  -> restored_from_revision_id = R5
  -> 重新校验权限、资料状态和选择器
  -> 生成 R9 -> R10 的影响报告
  -> 用户确认后激活 R10
```

因此回滚本质上是一次受审计的新变更，而不是复活旧状态。

## 11. 会话临时作用域

课程 active 修订是默认边界。用户在单次学习会话中临时加入或排除资料时，使用：

```text
session_scope_overlay_revision
  id
  learning_session_id
  base_course_scope_revision_id
  revision_number
  parent_revision_id
  checksum
  created_at

session_scope_overlay_item
  overlay_revision_id
  operation                  include | exclude | change_priority
  source_version_id
  selector_type
  selector_json
  reason
```

Overlay 只能引用用户有权限的资料。模型调用固定课程修订和 Overlay 修订，并将最终
使用的证据写入 `TurnEvidenceSnapshot`。这样用户中途改变临时资料时，不会改变之前
回答的事实边界。

M0 不实现会话 Overlay；首版只支持课程 active 作用域。待课程级链路稳定后再增加。

## 12. API 语义

```text
POST /courses/{courseId}/knowledge-scope/drafts
  body: {base_active_revision_id}

PATCH /knowledge-scope/revisions/{revisionId}/bindings
  header: If-Match: lock_version
  body: {operations: [...]}

POST /knowledge-scope/revisions/{revisionId}/analyze
  body: {expected_lock_version, expected_binding_checksum}

GET /knowledge-scope/revisions/{revisionId}/impact

POST /knowledge-scope/revisions/{revisionId}/activate
  body: {
    expected_active_revision_id,
    expected_binding_checksum,
    impact_report_id
  }

POST /courses/{courseId}/knowledge-scope/restore
  body: {target_revision_id, expected_active_revision_id}

POST /knowledge-scope/revisions/{revisionId}/discard
```

API 不接受客户端直接指定“激活后搜索任意资料”。检索服务始终由 `course_id` 和
`learning_session_id` 在服务端解析允许集合。

## 13. 可行性审校

### 13.1 存储

可行。作用域修订复制的是几十到数百条 Binding 元数据，而不是正文和向量。即使示例中
一门课程有 200 个 Binding、保存 50 个历史修订，也只有约 10000 条轻量关联记录。
真正占用存储的是原文件、解析元素和 Embedding。

### 13.2 查询性能

可行。运行时直接查询当前完整快照，不需要重放增量事件。主要索引：

- `course_knowledge_scope_revision(course_id) WHERE status = 'active'` 部分唯一约束；
- `course_scope_binding(scope_revision_id, enabled)`；
- `course_scope_binding(source_version_id)`；
- `course_scope_binding(scope_revision_id, binding_key)`；
- `scope_binding_change(scope_revision_id, operation)`。

### 13.3 分析成本

可控，但必须满足：

- 上传阶段不做课程级冲突分析；
- 草稿每次点击不触发高成本分析；
- 只比较 BindingDiff 涉及的资料和范围；
- 解析和 Embedding 按 `SourceVersion + processor_version` 复用；
- 同输入影响报告按校验和缓存。

### 13.4 一致性

可行。PostgreSQL 行锁、唯一约束、乐观锁和事务 Outbox 足以支撑单体初期部署，不需要
引入分布式事务或事件溯源框架。后台 Reconciler 定期校验课程 active 指针、active
部分唯一约束、Binding checksum 和影响报告引用，发现不一致时阻止继续激活。

### 13.5 用户体验

用户界面不强调“Revision”术语，只展示：

- 当前使用的资料；
- 待应用的资料调整；
- 调整会影响哪些内容；
- 应用调整；
- 历史调整与恢复。

版本、校验和和状态机属于后台严格流程。

### 13.6 主要风险

| 风险 | 处理 |
| --- | --- |
| 系统误判两个文件是版本关系 | 只生成候选，由用户确认 |
| 新版页码或章节发生漂移 | 选择器迁移失败时要求用户重新确认 |
| 分析期间草稿继续变化 | 冻结输入并校验 Binding checksum |
| 两个窗口同时编辑或激活 | 草稿编辑返回 412；激活基线冲突返回 409 |
| 回滚指向已失效资料 | 回滚创建新草稿并重新校验 |
| 作用域激活但计划尚未更新 | 同事务标记 `needs_replan`，阻止执行失据任务 |
| 历史资料被用户删除 | 软删除并保留历史引用，物理清理由保留策略控制 |

只要某个 `SourceVersion` 仍被 active/superseded 作用域、回答证据快照或其他审计产物
引用，就禁止物理删除原文件和必要解析产物。用户删除只改变资源库可见性；真正清理由
引用检查和保留期任务执行。

## 14. 分阶段实施

### M0 必须实现

- 不可变 `SourceVersion`；
- 完整快照式 `CourseKnowledgeScopeRevision`；
- `binding_key`、`lock_version` 和 Binding checksum；
- 单一草稿、最小 BindingDiff；
- 原子激活和 active 唯一约束；
- 服务端强制作用域检索；
- `TurnEvidenceSnapshot`；
- 软删除和历史引用保留。

M0 的影响分析只检查权限、资料处理状态、选择器合法性和基础覆盖变化，不实现复杂
Claim 冲突判断。

### M1-M3 增加

- PDF、Office 和多媒体选择器；
- Topic 级增量覆盖分析；
- Claim 冲突候选；
- 新版本智能候选和章节映射；
- 恢复历史修订界面；
- 会话 `SessionScopeOverlayRevision`；
- 计划和学习资源的局部重建。

## 15. 验收不变量

实现必须满足：

1. 任何历史回答都能定位当时的课程作用域、资料版本和证据单元。
2. 未绑定资料即使属于同一用户，也不能被课程检索命中。
3. 草稿分析后发生任何修改，旧影响报告立即失效。
4. 过期草稿编辑返回 412；两个客户端不能基于同一个旧 active 修订同时成功激活
   不同版本。
5. 回滚产生新修订，不修改历史修订。
6. 新上传资料不会自动改变任何课程。
7. 资料逻辑删除不会破坏历史回答和引用。
8. 角色或优先级变化不会重复解析文件或重新生成无关 Embedding。
