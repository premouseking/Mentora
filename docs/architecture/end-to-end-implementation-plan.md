# Mentora 端到端可落地实施方案

> 状态：主技术方案，供后续模块设计、ADR、排期和实现使用。  
> 更新日期：2026-06-11  
> 原则：从最终产品效果反推功能，并从功能拆解技术实现。

## 1. 项目最终要做成什么

Mentora 是一个“以课程为单位的 AI 学习工作台”，不是通用聊天机器人，也
不是单纯的文档知识库。

用户首先维护自己的长期资源库，再为每门课程选择当前允许使用的资料。用户为一门
课程提供：

- 学习目标，例如系统学习、快速入门、考试复习、专项补弱、完成作业或项目实践；
- 可用时间、当前基础和目标成果；有截止任务时再提供截止日期；
- 学习范围、教学大纲、老师重点、项目要求或个人兴趣方向；
- 从个人资源库选择的 PDF、Word、PPT、图片、音频、视频和网页资料；
- 用户主动选择的官方基础知识库和网络参考资料。

系统最终提供：

1. 一套与当前目标匹配、可以每天执行的学习计划；
2. 一张可操作的课程知识地图；
3. 每次学习所需的讲解、原文依据、例题和练习；
4. 对资料原文页码、区域、幻灯片页和视频时间点的精确引用；
5. 随时可用的课程问答与追问；
6. 基于多维证据的掌握度、薄弱点和复习安排；
7. 用户新增资料或改变目标后的局部影响分析和计划调整；
8. 有质量分级的网络视频、博客、论文和公开课程推荐。

用户前台应保持简单：进入课程后，主要操作始终是“继续学习”。复杂的解析、
检索、证据管理、冲突检测、评测和调度都在后台完成。

资源库与课程是两个不同生命周期：

- 资源属于用户或平台，可独立上传、整理、解析、更新和复用；
- 课程只通过版本化知识作用域引用资源，不拥有或复制原文件；
- 模型默认不能搜索用户全部资源，只能访问当前课程已激活作用域；
- 同一资料可供多门课程复用，解析、OCR、切块和 Embedding 按资料版本只执行一次。

## 2. 产品闭环

### 2.1 建立课程

```text
新建课程
  -> 输入一句初始诉求
  -> AI 提取已知信息和缺失信息
  -> 只询问影响方案的高价值问题
  -> 用户选择官方基础库
  -> 用户上传或稍后补充资料
  -> AI 填充课程配置草稿
  -> 用户检查、修改并点击“生成学习方案”
  -> 冻结已确认的 CourseProfileRevision
  -> 生成可编辑的 LearningPlanRevision 草稿
  -> 用户调整路径卡片并查看影响
  -> 用户点击“开始学习”
  -> 原子激活课程画像与学习路径
```

初始诉求可以很短，例如“七天速成计算机组成原理”。系统不能直接假设考试范围，
而应澄清：

- 考试日期和每天可投入时间；
- 是否有老师划定范围；
- 是否有教材、PPT、试卷或题库；
- 当前基础；
- 目标是通过、提分还是完整掌握。

澄清采用结构化问题卡，而不是无限自由聊天。每轮最多询问 1 至 3 个高信息增益
问题；能够生成可执行方案后立即停止追问。

#### 澄清结果如何总结和保存

模型不直接生成一段“用户需求总结”作为事实，也不能直接写入已确认画像。澄清的目标是
收集足够信息并填充课程配置面板，模型返回结构化候选：

```json
{
  "profile_candidates": [
    {
      "field_path": "purpose",
      "candidate_value": "exam_preparation",
      "extraction_confidence": 0.97,
      "source_refs": ["message:msg_1"],
      "ambiguity_reasons": []
    },
    {
      "field_path": "deadline",
      "candidate_value": "2026-06-25",
      "extraction_confidence": 0.99,
      "source_refs": ["message:msg_8"],
      "ambiguity_reasons": []
    },
    {
      "field_path": "scope_items[指令系统]",
      "candidate_value": {
        "scope_status": "included",
        "importance": "high"
      },
      "extraction_confidence": 0.93,
      "source_refs": ["source:sv_42#slide=18"],
      "ambiguity_reasons": ["尚未映射到标准 Topic"]
    }
  ],
  "unknown_fields": ["current_level"],
  "conflicting_fields": [],
  "next_questions": [
    {
      "field": "current_level",
      "question": "你目前对这门课大致掌握到什么程度？",
      "answer_type": "single_choice"
    }
  ],
  "ready_for_profile_review": false
}
```

服务端用 Pydantic JSON Schema 校验模型输出，再执行以下流程：

```text
用户消息或资料
  -> 模型生成 CourseProfileCandidate[]
  -> Schema 和字段权限校验
  -> 与当前草稿比较
  -> 生成新增、修改、冲突和未知项
  -> 填充可编辑 CourseProfileRevision 草稿
  -> 必要时继续结构化澄清
  -> 用户检查和修改配置面板
  -> 用户点击“生成学习方案”
  -> 冻结 confirmed CourseProfileRevision
  -> 触发 LearningPlanRevision 草稿生成
```

`extraction_confidence` 只属于确认前的模型候选，用于安排澄清顺序、风险抽样和评估提取
质量。它不是经过校准的真实概率，不在配置面板展示数值，也不能代替用户确认。用户
确认或修改后，正式画像字段不再保存该置信度。

候选字段至少带：

- `candidate_value`：模型建议填写的规范化值；
- `source_refs`：来自哪条消息、资料页或 PPT 页；
- `extraction_confidence`：仅供候选排序和模型评测；
- `ambiguity_reasons`：歧义、缺失上下文或待解析 Topic；
- `model_request_id`：生成候选的模型调用；
- `status`：待处理、接受、用户改写、拒绝或已被替代。

用户确认后的正式配置字段带：

- `value`：规范化后的值；
- `source_refs`：来自哪条用户消息、资料页、PPT 页或人工修改；
- `authority`：用户确认、用户修改、系统默认或诊断事实；
- `accepted_candidate_id`：可空，用于追溯采用了哪个模型候选；
- `updated_by`：用户或受控系统规则；模型只能写候选；
- `valid_from`、`valid_to`：适用时间；
- `revision_id`：所属配置版本。

数据库采用“版本快照 + 可查询明细”两层存储：

```text
course
  active_profile_revision_id
  active_learning_plan_revision_id
  onboarding_status        collecting_requirements | reviewing_profile
                           | generating_plan | reviewing_plan | active

course_profile_revision
  id
  course_id
  revision_number
  parent_revision_id
  profile_snapshot_json
  snapshot_schema_version
  snapshot_checksum
  change_summary
  created_by
  lock_version
  status                 draft | confirmed | active | superseded | abandoned
  confirmed_by
  confirmed_at
  created_at

course_profile_candidate
  id
  course_id
  clarification_run_id
  field_path
  candidate_value_json
  extraction_confidence
  source_refs_json
  ambiguity_reasons_json
  model_request_id
  status                 pending | accepted | edited | rejected | superseded

course_profile_field
  revision_id
  field_path
  value_json
  authority              user_confirmed | user_edited | system_default
                         | diagnostic_observed
  accepted_candidate_id
  updated_by
  source_refs_json

course_scope_item / course_focus_item / course_constraint
  revision_id
  normalized fields...

scope_candidate
  id
  revision_id
  raw_label
  raw_context
  proposed_scope_status
  source_refs_json
  resolution_status       unresolved | resolved | rejected
  resolved_topic_id
  resolved_at
```

规范化字段表和范围、重点、约束明细表是唯一可修改的课程配置事实源。
`profile_snapshot_json` 是从这些事实表生成的不可变派生快照，仅用于一次读取、
审计和传给计划器，禁止反向编辑。草稿允许通过 `lock_version` 编辑；用户点击
“生成学习方案”时重新生成快照、写入 Schema 版本和校验和，并冻结为 `confirmed`。
`confirmed` 版本不可修改，只能克隆为新草稿。后台一致性任务定期重建并比对校验和，
发现漂移时阻止该版本继续生成或启动计划。

考试范围、老师重点等列表项不能只保存名称。它们需要保存：

- 原始表述；
- 可空的规范化主题 ID；
- 包含、排除或未确定；
- 重要性；
- 题型或考查方式；
- 来源资料和定位；
- 用户确认状态。

课程刚创建或新资料刚上传时，主题目录可能尚未生成。此时范围信息先保存为
`ScopeCandidate`，保留原始表述和证据，不要求 `topic_id`。主题目录生成或更新后，
解析器再依据标题路径、关键词、别名和 Embedding 提出映射；高置信映射可进入
“待确认范围”，低置信映射继续保持未解析。只有完成映射并满足确认规则后，才生成
可供计划器使用的 `CourseScopeItem`。这样避免“先有 Topic 才能保存范围，而 Topic
又必须从范围和资料中生成”的循环依赖。

例如老师 PPT 中写“第五章不考”，模型只能提出一个带幻灯片引用的
`scope_status=excluded` 候选。用户确认后才成为有效课程配置。

是否继续追问由规则引擎决定，不由模型凭感觉决定。不同 `purpose` 定义不同的
最低可执行字段：

- 系统学习：范围或可发现资料、当前基础、每周可用时间；
- 考试复习：截止日期、考试范围来源、时间预算、当前基础；
- 专项补弱：目标主题或诊断结果、当前困难；
- 项目驱动：交付物、验收标准、截止日期或里程碑；
- 自由探索：兴趣方向即可，其余字段均可缺省。

字段满足最低集合且不存在阻塞冲突时，规则引擎设置
`ready_for_profile_review=true`。
模型只负责从未知字段中生成候选问题，并给出预期信息增益；服务端根据“是否会
改变范围、优先级、截止约束或资料选择”排序，选择最多三个问题。

#### 通用课程配置模型

课程配置不使用单一“考前速通模式”。学习意图拆成可组合维度：

```text
CourseProfile
  purpose
  target_outcomes[]
  target_depth
  pacing
  deadline
  time_budget
  current_level
  scope[]
  focus[]
  output_preferences[]
  assessment_preferences
  access_policy
  constraints[]
```

其中：

- `purpose`：系统学习、考试复习、补弱、作业支持、项目实践、证书备考、
  兴趣探索、教学备课等；
- `target_outcomes`：通过考试、达到分数、完成项目、能解决某类问题、建立完整
  知识体系等，可多选；
- `target_depth`：了解、理解、熟练应用、综合迁移；
- `pacing`：集中冲刺、固定节奏、自适应、无期限探索；
- `deadline`：可选。长期学习和兴趣探索不要求截止日期；
- `time_budget`：可以是每天、每周或某些固定时间段；
- `scope`：课程范围。可来自教学大纲、资料目录、用户选定主题或动态发现；
- `focus`：当前重点、薄弱点、项目目标或考试重点；
- `output_preferences`：讲解、练习、项目、阅读、视频、笔记或复习卡；
- `access_policy`：是否允许网络搜索、是否允许临时扩展作用域、引用质量门槛等访问
  规则；具体启用哪些资料不放入课程画像，而由课程知识作用域管理；
- `constraints`：语言、设备、无高数基础、只能周末学习等限制。

预设模式只负责填写默认值，不改变底层模型。例如：

| 预设 | 默认配置 |
| --- | --- |
| 系统学习 | 完整范围、理解到应用、自适应节奏、持续复习 |
| 考前复习 | 有截止日期、考试范围优先、诊断后补弱 |
| 快速入门 | 核心概念优先、了解到理解、较少评测 |
| 专项补弱 | 只聚焦薄弱主题和前置缺口 |
| 项目驱动 | 以交付物和实践任务组织学习 |
| 自由探索 | 无固定截止日期，按兴趣和前置关系推荐 |

用户可以从预设开始，也可以不选择预设，直接描述需求。预设不会形成六套不同
流程，所有场景共用 `CourseProfile -> LearningPlan` 管线。

#### 课程配置面板

澄清达到最低可执行条件后展示可编辑的“课程设置”面板，分为：

1. **学习目标**：目的、成果、深度、截止日期；
2. **时间与节奏**：每周时间、学习日、单次时长、冲刺或自适应；
3. **范围与重点**：纳入主题、排除主题、重点、薄弱点和来源；
4. **当前基础**：自评、诊断结果和已有能力；
5. **资料策略**：网络搜索、临时资料和引用质量等访问规则；具体资料在独立的
   “课程资料”页管理；
6. **学习方式**：讲解、题目、项目、视频和复习偏好；
7. **待确认事项**：未确认候选、信息缺失和资料冲突。

面板中的每项显示状态：

- 已确认；
- AI 根据对话推断；
- 从资料中提取；
- 用户已修改；
- 存在冲突；
- 信息缺失。

用户修改面板与回答澄清问题使用同一套 Draft Patch 语义。面板编辑只更新当前草稿并
递增 `lock_version`，避免每次点击产生无意义修订。用户点击“生成学习方案”后：

1. 服务端重新校验必填字段、冲突和资料选择；
2. 将当前画像草稿冻结为不可变 `confirmed` 修订；
3. 将课程推进到 `generating_plan`；
4. 以该画像修订、课程知识作用域、Topic 修订和学习快照为固定输入生成计划草稿。

这里的“确认画像”不等于开始学习。首次建课时，只有最终点击“开始学习”才同时激活
画像和路径。已有课程调整画像时，旧画像和旧计划继续服务，直到替代计划被最终确认。

### 2.2 用户资源库与课程知识作用域

```text
上传文件或添加链接到用户资源库
  -> 安全检查和文件识别
  -> 保存不可变原文件版本
  -> 选择解析策略
  -> 生成统一结构化文档
  -> 建立证据单元和检索索引
  -> 可供多门课程选择

创建或调整课程
  -> 从资源库和官方库选择资料
  -> 创建课程知识作用域草稿
  -> 对齐受影响课程主题
  -> 计算对当前计划的影响
  -> 必要时澄清冲突
  -> 用户确认后激活新作用域版本
```

上传到资源库不等于授权某门课程使用。新资料解析完成后，系统可以推荐可能相关的
课程，但必须由用户选择加入。新增资料也不自动覆盖旧资料，系统只判断它是：

- 新增覆盖；
- 旧内容的新版；
- 补充材料；
- 相互矛盾的观点；
- 重复或低价值资料。

涉及考试范围、关键结论或当前计划的高影响冲突，才打断用户澄清。

课程知识作用域中的每项资料绑定可设置：

- `role`：`primary`、`reference`、`exam_scope`、`exercise`；
- `selector_type + selector_json`：全文、章节、页码、幻灯片或时间范围；
- `version_policy`：固定当前版本，或发现新版本时提醒；
- `enabled`：是否参与后续检索和计划；
- `user_note`：用户对该资料用途的说明。

“发现新版本时提醒”只创建待处理建议，不能静默替换激活作用域中的资料版本。

### 2.3 学习

```text
点击继续学习
  -> 选择下一学习任务
  -> 加载必要资料和学习状态
  -> 返回学习包
  -> 阅读、提问、举例、练习
  -> 收集学习证据
  -> 更新掌握状态
  -> 安排下一任务和复习
```

“学习包”不是每次临时生成的一篇长文章，而是组合以下内容：

- 官方或用户资料中的原始内容；
- 平台维护的稳定基础讲解；
- 缓存的 AI 适配讲解；
- 当前用户需要的例子、提示和练习；
- 精确引用；
- 本节学习目标和完成条件。

### 2.4 评测与计划调整

```text
章节学习完成
  -> 快速回忆
  -> 基础题
  -> 解释题
  -> 迁移题
  -> 延迟复习
  -> 汇总 MasteryEvidence
  -> 更新掌握度和置信度
  -> 调整后续任务
```

不能把“看完”“点了完成”或“用户说会了”当作真正掌握。

## 3. 总体技术架构

第一版采用模块化单体，避免过早拆分微服务。

```text
Electron Main
  -> 本地文件、上传、认证、通知、窗口和更新
  -> Authenticated API / SSE Bridge
  -> Preload typed contextBridge
  -> React + TypeScript Renderer
  -> Django REST Framework
  -> 应用服务与领域模块
  -> PostgreSQL + pgvector
  -> Redis
  -> Celery Workers
  -> MinIO / S3 / COS
  -> 外部模型、搜索、解析和转写服务
```

桌面端完整设计见 `docs/architecture/desktop-client-architecture.md`。

### 3.1 Electron 客户端

- Windows 10/11 x64 首发；
- Electron 主进程作为薄桌面宿主，不内置 Django、数据库、队列或 AI Runtime；
- React 19 + TypeScript + Vite 作为 renderer；
- React Router；
- TanStack Query 管理服务端状态；
- Zustand 仅保存功能内临时交互状态；
- React Flow + ELK.js 展示知识地图；
- PDF.js 或 React PDF Viewer 展示 PDF；
- TipTap 仅在需要富文本笔记时引入；
- KaTeX 渲染公式；
- ECharts 展示掌握度与学习趋势。

进程边界：

- Main：窗口、令牌、API/SSE、文件、上传、通知和更新；
- Preload：通过 `contextBridge` 暴露有类型、白名单化的桌面能力；
- Renderer：只负责 UI，不允许 Node.js、任意文件访问和长期令牌；
- Cloud：继续拥有课程、资料、计划、评测和学习状态的唯一事实。

安全基线：

```text
nodeIntegration: false
contextIsolation: true
sandbox: true
webSecurity: true
```

### 3.2 后端

- Python 3.11+，生产环境建议统一为 3.12；
- Django 5 + Django REST Framework；
- PostgreSQL 16+；
- pgvector；
- Redis；
- Celery；
- Pydantic v2 定义模型输出和跨模块 DTO；
- django-storages 对接 MinIO、S3 或 COS；
- OpenTelemetry + Prometheus + Grafana；
- Sentry 收集应用异常。

当前早期骨架中的 `channels`、`channels-redis`、`daphne` 和 `langgraph` 属于
尚未确认方案时加入的占位依赖，不代表最终选型。恢复实现时应先移除；等实时
语音、多人协作或明确 Agent 图流程立项后再按 ADR 引入。

### 3.3 通信

- Renderer 只调用 preload 暴露的 typed Desktop API；
- 普通命令：Main Process 认证后转发 REST；
- 模型回答、解析进度、工作流进度：Main Process 桥接可恢复 SSE；
- 上传：Main Process 从临时 `file_token` 对应路径按流读取并直传预签名 URL；
- 登录：renderer 经 IPC 提交凭据，主进程调用 Django `/auth/login/` / `/auth/register/` 并保存 Refresh Token；
- 实时语音或多人协作确定立项后再增加 WebSocket。

API Bridge 只接受 Mentora 相对 API path，不能成为任意 URL 开放代理。大文件不能
编码为 base64 穿过 IPC。

## 4. 资料接入统一架构

所有输入先转成统一的 `ParsedBundle`，后续主题提取、检索、引用和学习逻辑不直接
依赖具体文件格式。

```text
LibraryItem
  -> Source
  -> SourceVersion
  -> ParseRun
  -> ParsedBundle
  -> ParsedElement
  -> EvidenceUnit
  -> RetrievalProjection
```

### 4.1 用户资源库

资源库是用户级资产，不依赖课程存在。核心能力包括：

- 文件夹、标签、搜索、排序和批量选择；
- 上传文件、添加网页或网络视频链接；
- 查看版本、解析状态、文件类型、页数或时长；
- 识别重复文件和可能的新版本；
- 查看哪些课程正在引用某个资料版本；
- 停用、逻辑删除和恢复资料。

`LibraryItem` 是用户整理资源时看到的逻辑条目，`Source` 表示原始资料身份，
`SourceVersion` 表示不可变内容版本。移动文件夹或修改标签不产生
`SourceVersion`；文件内容发生变化时必须创建新版本。

上传后立即执行安全检查、基础解析和全文索引，确保资料进入课程时可以快速使用。
高成本派生能力采用分层策略：

- 文本提取、结构识别和关键词索引按资料版本预处理；
- 默认 Embedding 可在解析完成后生成，超大资料可按配额延迟执行；
- OCR、视觉描述、视频 ASR 根据文件检测结果和用户需求触发；
- 课程 Topic 对齐、Claim 提取和冲突检查只有资料进入课程作用域后才执行；
- 所有可复用派生产物以 `source_version_id + processor_version` 为缓存键。

官方基础库也通过同一读取协议暴露 `SourceVersion`，但所有权和权限由平台管理。
用户只能把明确选择的官方资料加入课程作用域，不能靠课程名称自动绑定。

### 4.2 上传入口

支持：

- PDF；
- DOC、DOCX；
- PPT、PPTX；
- XLS、XLSX、CSV；
- TXT、Markdown、HTML、EPUB；
- PNG、JPEG、TIFF；
- MP3、WAV、M4A；
- MP4、MOV、MKV；
- 用户提供的网页和视频链接。

上传流程：

1. API 创建上传会话；
2. 返回对象存储预签名 URL；
3. Electron Main Process 从用户选择的 `file_token` 分片上传大文件；
4. 上传完成后提交 SHA-256、大小和客户端 MIME；
5. 服务端使用 libmagic 或 Apache Tika 再识别真实类型；
6. ClamAV 扫描；
7. 文件指纹去重；
8. 创建不可变 `SourceVersion`；
9. 投递解析任务。

原始文件不覆盖。普通上传默认创建独立资料；用户通过“为已有资料上传新版本”入口
明确创建下一版本。后续系统可以提出版本候选，但不能仅凭同名或相似度自动合并。

### 4.3 课程知识作用域

```text
Course
  -> active_knowledge_scope_revision_id
  -> CourseKnowledgeScopeRevision
       -> CourseScopeBinding[]
             -> SourceVersion
             -> selector_type + selector_json
             -> role
```

作用域版本状态为
`draft | analyzing | pending_confirmation | active | superseded | discarded`。
草稿可以反复添加、移除或调整资料；只有完成影响分析并由用户确认后才能激活。
完整的版本语义、并发控制和回滚规则见
`docs/architecture/scope-versioning-design.md`。

核心数据结构：

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
  activated_at

course_scope_binding
  id
  scope_revision_id
  binding_key
  source_version_id
  role                       primary | reference | exam_scope | exercise
  selector_type              whole_document | pdf_pages | section_ids | media_time_ranges
  selector_json
  priority
  version_policy             pinned | notify_on_new_version
  enabled
  user_note
  created_at

scope_impact_report
  id
  scope_revision_id
  base_active_revision_id
  binding_set_checksum
  course_profile_revision_id
  topic_revision_id
  affected_topic_ids
  added_evidence_count
  removed_evidence_count
  conflict_ids
  invalidated_artifact_ids
  plan_change_summary_json
  status
  analyzer_version
  created_at
```

`binding_key` 是同一资料绑定跨作用域修订的稳定标识。作用域草稿从当前 active
修订复制完整 Binding 集合，但只复制轻量元数据，不复制正文、证据或向量。同一作用域
版本内 `binding_key` 必须唯一；Binding 集合经规范化排序后计算校验和，用于幂等分析、
缓存和防止分析后草稿继续修改。

`replace_version` 只允许同一 Source 内的资料版本升级并保留 `binding_key`；改换为
另一份独立资料必须表示为 `remove + add`。M0 提供“上传新资料”和“为已有资料上传
新版本”两个明确入口，不依赖模型自动判断版本关系。

草稿编辑使用 `If-Match` 和 `lock_version` 乐观锁，版本不匹配返回 412。影响分析
冻结当前 Binding checksum；只有
`binding_set_checksum == analyzed_binding_checksum` 时才允许激活。同一课程通过
数据库部分唯一约束保证最多一个 active 修订，激活时锁定课程行并在同一事务内切换
旧、新修订状态和课程 active 指针。

每次学习计划、学习会话和模型调用必须固定：

```text
CourseProfileRevision
+ CourseKnowledgeScopeRevision
+ TopicRevision
+ TurnEvidenceSnapshot
```

历史回答继续引用原作用域和原资料版本。后续扩大或缩小作用域只影响新的调用和剩余
计划，不改写历史记录。

如果资源库中的某个 `Source` 出现新版本，系统查找使用旧版本且
`version_policy=notify_on_new_version` 的课程绑定，生成更新建议。用户接受后创建
新的作用域草稿并执行影响分析；`pinned` 绑定只显示已有新版本，不主动建议替换。

### 4.4 统一解析结果

```text
ParsedBundle
  document_metadata
  pages_or_slides[]
  elements[]
  hierarchy[]
  assets[]
  warnings[]
  quality_metrics
  parser_name
  parser_version
```

每个 `ParsedElement` 至少包含：

- 元素类型：标题、正文、列表、表格、公式、图片、代码、备注；
- 规范化文本；
- 原始文本；
- 页码、幻灯片页或时间区间；
- PDF 矩形坐标或 Office 形状位置；
- 标题路径；
- 阅读顺序；
- 置信度；
- 原始资源引用。

## 5. 各类资料的具体实现

### 5.1 PDF

PDF 分三条解析路径。

#### 快速路径

适用于文本层完整、布局简单的 PDF：

- PyMuPDF 提取文本块、字体、坐标、图片和书签；
- pdfplumber 辅助表格和几何检查；
- 根据字体、字号、位置和书签重建标题层级。

#### 高质量路径

适用于多栏、公式、复杂表格、论文和教材：

- 首选 MinerU；
- 输出 Markdown、JSON、公式、表格、图片和阅读顺序；
- 将 MinerU 结果转换成内部 `ParsedBundle`；
- 保留 MinerU 原始产物以便重新适配。

MinerU 官方当前支持 PDF、图片、DOCX、PPTX 和 XLSX，并面向复杂布局、公式和
表格解析：[MinerU](https://github.com/opendatalab/MinerU)。

#### OCR 路径

适用于扫描件或文本层质量差的页面：

- 页面渲染：PyMuPDF；
- 中文 OCR：PaddleOCR；
- 公式、表格密集页面优先 MinerU 或 PaddleOCR 文档解析流水线；
- OCR 后保留文字框坐标；
- 低置信页面标记为需要人工确认。

解析策略由预检决定，而不是让所有 PDF 都走昂贵 OCR：

- 有效文本页比例；
- 乱码比例；
- 每页字符密度；
- 字符语言分布；
- 页面图像覆盖率；
- 坐标可定位率；
- 公式和表格密度。

### 5.2 Word

DOCX 首选 Docling 或 python-docx：

- 读取标题样式、段落、列表、表格、图片、页眉页脚和批注；
- 读取 OOXML relationship，保存图片和链接；
- 按标题样式生成层级；
- 表格转成结构化网格和 Markdown；
- 嵌入图片进入图像解析队列。

旧 `.doc` 文件先用 LibreOffice headless 转为 DOCX，原文件和转换产物都保留。

Docling 提供统一文档模型，并支持 PDF、DOCX、PPTX、XLSX、HTML、音频等格式：
[Docling formats](https://docling-project.github.io/docling/usage/supported_formats/)。

### 5.3 PowerPoint

PPTX 使用 python-pptx 或 Docling：

- 每张幻灯片作为一级定位单元；
- 提取标题、文本框、表格、图片、图表和讲者备注；
- 根据坐标和占位符类型恢复阅读顺序；
- 图片型幻灯片进入 OCR；
- 讲者备注的权重高于普通隐藏文本；
- 连续幻灯片按标题和内容相似度组成章节。

旧 `.ppt` 使用 LibreOffice headless 转为 PPTX。

PPT 中经常出现“文字很少、知识在图里”的情况，因此必须保存幻灯片截图。对
图表、流程图和结构图按需调用视觉模型生成“可检索描述”，但描述必须标明为
模型派生内容，不能代替原图。

### 5.4 Excel 和 CSV

- XLSX 使用 openpyxl；
- XLS 使用 LibreOffice 转换；
- CSV 使用 Python csv 或 Polars；
- 保存工作表、表头、单元格范围、公式和合并关系；
- 大表不直接转成长文本；
- 先识别表语义，再按区域建立证据单元；
- 公式计算结果和原公式分别保存。

### 5.5 图片

- libmagic 识别真实格式；
- Pillow 读取元数据并规范化方向；
- PaddleOCR 提取文本与坐标；
- 图表、示意图和手写内容按需调用视觉模型；
- 图片描述与 OCR 文本分别保存；
- 用户可手动标注“这是考试重点”或框选区域。

### 5.6 网页

```text
URL
  -> URL 规范化和安全检查
  -> robots/访问策略检查
  -> 静态 HTTP 抓取
  -> 正文抽取
  -> JS 页面必要时浏览器渲染
  -> 保存抓取快照和时间
  -> 解析为 ParsedBundle
```

技术选择：

- httpx 请求；
- trafilatura 或 Readability 提取正文；
- Playwright 作为动态页面回退；
- Firecrawl 可作为托管回退，不成为唯一供应商；
- BeautifulSoup 做结构清理；
- 保存标题、作者、发布时间、抓取时间和 canonical URL。

网页内容具有时效性。回答引用网页时必须带抓取时间，后续重新抓取创建新版本。

### 5.7 用户上传视频

```text
视频
  -> ffprobe 获取编码、时长和轨道
  -> FFmpeg 提取音频
  -> 提取已有字幕
  -> 无字幕时执行 ASR
  -> 场景切分和关键帧抽取
  -> 关键帧 OCR / 视觉解析
  -> 合并字幕、语音、画面和时间轴
  -> 生成视频章节和 EvidenceUnit
```

技术选择：

- FFmpeg / ffprobe：转码、音轨、字幕和关键帧；
- PySceneDetect：场景变化检测；
- ASR 云端默认：支持时间戳的语音转写 API；
- 私有化或成本敏感模式：faster-whisper；
- 可选说话人区分：pyannote.audio；
- OCR：PaddleOCR；
- 视频播放器：Video.js 或原生 HTML5 video。

ASR 结果至少保存段落级时间戳。用户点击引用时跳转到对应视频时间。对教学视频，
每隔固定时间截帧是不够的，应结合场景变化、字幕变化和幻灯片差异抽取关键帧。

### 5.8 网络视频链接

优先级：

1. 使用平台官方 API 获取标题、作者、时长、字幕和嵌入地址；
2. 有公开字幕时只处理字幕和元数据；
3. 用户明确拥有处理权限时，才下载媒体进行转写；
4. yt-dlp 只作为受控适配器，不绕过访问限制或版权控制。

网络推荐默认只展示链接、来源、摘要、适用主题和推荐理由，不把未经授权的完整
视频复制到平台。

## 6. 从资料到课程知识模型

### 6.1 课程主题模型

系统不根据课程名称绑定固定模板。主题模型只能从当前课程知识作用域及用户明确输入
中产生：

- 用户选择的官方基础库；
- 用户资料中的目录、标题、考点和题目；
- 用户明确给出的考试范围和老师重点。

```text
Topic
  id
  canonical_name
  aliases[]
  description
  prerequisites[]
  importance
  exam_relevance
  source_coverage
```

生成流程：

1. 规则提取标题、目录、章节号和高频术语；
2. LLM 以 JSON Schema 提取候选主题、别名和前置关系；
3. 使用关键词、Embedding 和结构路径做候选合并；
4. 对低置信合并保留多个节点或请求用户确认；
5. 主题与资料证据建立多对多关系；
6. 用户可以重命名、合并、拆分和调整重点。

知识地图是“课程当前有效主题模型”，不是追求实体数量的通用知识图谱。

### 6.2 知识主张与冲突

只对可能影响学习的内容提取 `KnowledgeClaim`：

```text
KnowledgeClaim
  topic_id
  claim_type
  normalized_subject
  normalized_predicate
  normalized_value
  qualifiers
  evidence_unit_ids
  confidence
```

不对所有句子做全量两两比较。资源上传阶段不执行课程冲突比较；只有资料被加入某个
课程作用域草稿时，才针对该课程执行：

1. 找到受影响主题；
2. 检索同主题已有主张；
3. 规则比较数值、范围、否定和版本；
4. 只让模型判断少量高相似候选；
5. 生成冲突等级和解释；
6. P0/P1 才进入用户澄清。

### 6.3 作用域增量变更

扩大作用域、缩小作用域和更换资料版本统一走以下流程：

```text
编辑 CourseKnowledgeScopeRevision 草稿
  -> 计算 BindingDiff
  -> 定位新增、移除和变化资料覆盖的 Topic
  -> 只更新受影响 Topic 的证据覆盖和 Claim 候选
  -> 计算缓存、主题、计划和未完成任务影响
  -> 生成 ImpactReport
  -> 用户处理高影响冲突并确认
  -> 原子激活新作用域版本
  -> 异步重建受影响派生数据
```

BindingDiff 使用跨修订稳定的 `binding_key` 识别
`add | remove | replace_version | change_selector | change_role | change_priority |
enable | disable`。角色和优先级变化不重新解析资料；范围变化只处理范围对称差；
同一 Source 更换版本才执行内容差异和选择器迁移检查。

作用域回滚不能直接重新激活历史版本。系统以当前 active 修订为基础，克隆目标历史
修订的 Binding 集合形成新草稿，记录 `restored_from_revision_id`，重新校验权限、
资料状态、选择器和影响后再激活。

缩小作用域时，系统必须检查剩余资料能否支撑当前范围和已安排任务。失去依据的未来
任务标记为 `needs_replan`；历史回答只显示“原资料已停用或删除”，不伪造新引用。

## 7. 检索与引用

### 7.1 检索存储

第一版使用 PostgreSQL + pgvector，保证资料版本、权限和向量在同一事务边界内。

索引包括：

- GIN 全文索引；
- `pg_trgm` 名称和错别字检索；
- pgvector HNSW 向量索引；
- 普通 B-tree 版本、课程、状态和权限索引。

中文全文检索通过基准测试在以下方案中选择：

- jieba、HanLP 或 pkuseg 分词后生成 `tsvector`；
- 字符 N-gram；
- `pg_trgm`；
- 稀疏向量模型。

### 7.2 查询流程

```text
用户问题
  -> 意图分类和查询改写
  -> 固定当前 CourseKnowledgeScopeRevision
  -> 作用域 Binding/资料版本/权限过滤
  -> 关键词召回
  -> 向量召回
  -> RRF 融合
  -> 可选 cross-encoder 重排
  -> 多样性和来源覆盖控制
  -> 引用校验
  -> 构建 TurnEvidenceSnapshot
```

检索 API 不接受前端传入任意 `source_version_id` 绕过作用域。服务端先读取课程当前
激活作用域，再取其允许的 Binding；学习会话如需临时资料，必须创建显式的
`SessionScopeOverlay`，记录加入或排除项、原因和有效期，并且不能扩大到用户无权
访问的资源。

问题包含精确术语、公式、页码或老师原话时提高关键词权重；概念解释和自然语言
问题提高向量权重。排序策略由查询类型决定，不使用固定 alpha。

### 7.3 引用协议

模型接收带稳定 ID 的证据，返回结构化结果：

```json
{
  "answer_blocks": [
    {
      "text": "……",
      "citations": [
        {"evidence_unit_id": "ev_123", "claim": "……"}
      ]
    }
  ]
}
```

服务端校验引用 ID 是否属于本轮证据快照，前端再渲染页码、矩形、幻灯片页或
视频时间。禁止主要依靠正则解析模型自由生成的引用标签。

## 8. AI Tutor 与内容生成

### 8.1 模型职责

大模型负责：

- 澄清需求；
- 结构化提取；
- 解释、类比和例子；
- 查询改写；
- 根据学生状态动态生成练习题候选；
- 开放题评分辅助；
- 冲突候选判断；
- 学习快照生成。

大模型不负责：

- 成为课程事实源；
- 自行决定资料权限和版本；
- 直接写掌握度最终值；
- 绕过领域服务修改数据库；
- 对全课程内容无限制实时生成。

### 8.2 模型网关

业务模块声明任务：

```text
task_type
required_capabilities
quality_tier
latency_budget
cost_budget
context_size
structured_output_schema
```

`model_gateway` 决定具体提供方和模型，记录：

- `ModelRequest`；
- 每次物理调用的 `ModelAttempt`；
- Token、缓存和成本；
- Fallback 原因；
- 输出校验结果；
- 用户结算和内部成本。

### 8.3 降低生成成本

- 稳定知识采用官方内容和预生成基础讲解；
- 个性化只生成差异部分；
- 学习包缓存键至少包含 `topic_id`、课程配置版本、资料作用域版本、证据快照 ID、
  生成器版本和语言区域；
- AI 动态出题优先满足当前 Topic、误区、认知层级和掌握状态；精确匹配时才复用题库；
- 动态题采用答案优先生成、确定性过滤和批量独立验证；
- 相同主题解释复用基础版本；
- 只在用户打开主题时生成高成本内容；
- 小模型处理分类、提取和改写；
- 高质量模型处理复杂解释和开放题评分；
- Embedding 和解析按资料版本复用。

## 9. 学习计划与动态目标

### 9.1 计划输入

- 已冻结为 `confirmed` 的课程配置版本；
- 课程知识作用域版本；
- 学习目的和目标成果；
- 目标深度和节奏；
- 截止日期；
- 每日可用时间；
- 当前基础；
- 范围、重点和排除项；
- 学习方式与产出偏好；
- 主题重要性和考试权重；
- 主题前置关系；
- 资料覆盖；
- 掌握度和遗忘风险。

### 9.2 计划生成

计划生成不是让模型自由写一张日程表。先由确定性调度器计算：

1. 可用总时间；
2. 必学主题；
3. 前置拓扑；
4. 每主题预计时长；
5. 复习和测试预算；
6. 风险缓冲。

主题预计时长由可解释的 `DurationEstimator` 计算，输入包括目标深度、当前掌握度、
主题难度、资料长度、任务类型和历史学习速度。没有个人历史时使用课程级基线，并
同时输出估计区间而不是单点值。

当必学内容的保守时长超过可用预算时，计划器不得生成表面可执行的日程，而应进入
`infeasible` 状态，并给出可选择的降级方案：延长截止日期、增加时间预算、降低目标
深度、缩小范围或接受较低覆盖率。只有用户确认取舍后才激活计划。执行过程中如果
连续多次超时，系统按“保留前置和高优先级主题、减少低价值生成内容、压缩练习数量”
的规则降载，并再次展示影响。

模型只负责把调度结果转成用户易读的计划，并解释取舍。

生成结果先进入 `LearningPlanRevision` 草稿，不直接创建可执行任务：

```text
learning_plan
  id
  course_id
  active_revision_id

learning_plan_revision
  id
  learning_plan_id
  parent_revision_id
  profile_revision_id
  knowledge_scope_revision_id
  topic_revision_id
  learner_snapshot_id
  planner_policy_version
  plan_snapshot_json
  snapshot_checksum
  feasibility_status       feasible | constrained | infeasible
  validation_result_json
  lock_version
  status                   generating | draft | ready_to_start | active
                           | needs_replan | superseded | abandoned
  created_at

learning_plan_phase
  revision_id
  position
  title
  objective
  estimated_minutes

learning_plan_unit
  revision_id
  phase_id
  topic_id
  position
  target_depth
  estimated_minutes
  prerequisite_unit_ids
  priority

learning_plan_task_template
  revision_id
  unit_id
  task_type
  delivery_mode
  estimated_minutes
  required
  generation_policy_json
```

`LearningPlanRevision` 表达待用户检查和确认的学习路径结构，`LearningTask` 是启动后
按近期窗口物化的可执行实例。首期不提前生成整门课程所有个性化讲义、题目和学习任务。

### 9.3 学习路径编辑器

计划以可修改卡片展示，而不是一段不可编辑的 AI 文本：

```text
阶段卡 Phase
  -> 学习单元卡 Unit
       -> 任务卡 TaskTemplate
```

用户可以：

- 调整没有前置冲突的单元顺序；
- 将某个单元设为重点、快速回顾或暂时跳过；
- 修改单元时间预算和讲解、练习、项目、视频等任务组合；
- 拆分或合并单元；
- 选择“先诊断，达标后跳过”；
- 查看每张卡片的纳入原因、来源 Topic、预计时长和前置依赖。

计划编辑器必须区分两类修改：

1. **仅影响计划结构**：独立单元排序、任务呈现方式、预算内时间分配、可选任务启停。
   可以直接修改计划草稿，然后重新执行依赖、预算和覆盖校验。
2. **改变课程画像事实**：截止时间、总时间预算、学习范围、目标深度、目标成果和资料
   权威口径。必须返回课程配置面板创建新的画像草稿，不能在计划卡片中静默覆盖。

删除前置知识或压缩时间时，界面提供明确取舍：

- 保留原单元；
- 改成快速回顾；
- 先做诊断，达标后跳过；
- 接受覆盖率下降；
- 返回画像面板调整目标或时间。

每次编辑递增 `lock_version` 并重新计算：

- 前置依赖是否合法；
- 总时长是否超出预算；
- 必学范围和重点覆盖率；
- 复习与测试预算；
- 是否存在没有资料证据的任务；
- 相对自动生成草稿发生了哪些取舍。

通过校验后状态变为 `ready_to_start`。`infeasible` 计划不能进入该状态。

### 9.4 最终启动与原子激活

“开始学习”是整个建课流程的最终确认点。服务端在一个数据库事务中：

1. 锁定课程并检查当前活动版本没有发生并发变化；
2. 校验计划仍引用用户刚确认的画像、知识作用域和 Topic 修订；
3. 校验计划状态为 `ready_to_start`，校验结果和 checksum 未过期；
4. 将 `CourseProfileRevision` 和 `LearningPlanRevision` 同时置为 `active`；
5. 更新课程的两个 active 指针和 `onboarding_status=active`；
6. 写入 Outbox，异步物化近期任务、复习计划和第一个学习入口。

任何一步失败都不能只激活画像或只激活计划。用户在最终启动前离开，草稿继续保存，但
`GET /courses/{id}/next-task` 不得返回该草稿中的任务。

已有课程仅调整计划结构时，新计划继续引用当前 active 画像；“应用新路径”事务校验
该画像指针未变化后只切换计划指针。已有课程修改画像时，必须生成引用新 confirmed
画像的替代计划，并原子切换画像和计划两个指针。

计划版本化保存。任何课程配置或知识作用域变化都先计算影响范围。例如目标从
“长期系统学习”改成“七天完成核心内容”时：

- 创建新 `CourseProfileRevision`；
- 用户确认画像后生成新的 `LearningPlanRevision` 草稿；
- 保留已完成任务；
- 标记被跳过的低优先级内容；
- 重新计算复习间隔；
- 告知用户变化影响；
- 用户最终确认后原子切换活动画像和计划。

在替代计划确认之前，旧活动计划继续运行；若资料作用域变化已经使旧任务失据，则相关
任务进入 `blocked_by_scope_change`，不能为了保持可用而继续使用失效证据。

## 10. 掌握度与复习

### 10.1 学习证据

每条 `MasteryEvidence` 记录：

- 主题；
- 证据类型；
- `assessment_item_revision_id` 或其他原始证据 ID；
- 题目难度；
- 是否有提示；
- 正确率；
- 回答耗时；
- 用户置信度；
- 错误类型；
- 发生时间；
- 评分器和版本。

每个参与掌握度计算的 `AssessmentItemRevision` 必须保存：

- 题干、标准答案或评分量规；
- 对应主题与能力层级；
- 来源证据，或明确标记为模型生成；
- 生成器、提示词模板和模型版本；
- 生命周期、验证等级和统计校准状态；
- 质量等级与已知缺陷；
- 使用次数、区分度和异常作答统计。

规则题和 AI 新题只有完成对应用途要求的答案规划、独立验证、歧义检查与题型硬门禁后，
才能进入 `auto_checked`。开放题和未达到当前风险门槛的题目只能产生低权重证据，或
直接拒绝进入本次测验。统计校准不能替代内容验证。
题目存在歧义、答案冲突或评分器
异常时，相关掌握度证据可追溯撤销并重算，不能让低质量题目永久污染学生画像。

完整题库、AI 出题、审校、组卷和评分设计见
`docs/architecture/assessment-item-bank-design.md`。核心模型为：

```text
ItemBank
  -> AssessmentItem
       -> AssessmentItemRevision
            -> ItemProvenance
            -> ItemReviewRun

AssessmentBlueprint
  -> AssessmentFormRevision(mode=fixed|adaptive)

AssessmentAttempt
  -> AssessmentAttemptItem[]
       -> 固定 AssessmentItemRevision
       -> ItemResponse
            -> ScoringResult
                 -> MasteryEvidence
```

`fixed` 表单在 Attempt 创建时固定全部题位；`adaptive` 表单只固定蓝图、风险策略和
停止条件，再根据前序作答逐题追加 `AssessmentAttemptItem`。题位一旦返回给客户端就
不可替换，重连和幂等重试必须返回同一题目修订。

官方题、用户题、文档提取题和 AI 生成题使用同一题目协议。题目生命周期、验证等级和
统计校准状态分别记录：

```text
lifecycle_status     draft | reviewing | trial | published | quarantined
                     | retired | rejected
verification_level   unverified | auto_checked | human_verified
calibration_status   none | collecting | calibrated
```

题目用途采用风险分级准入：即时练习使用标准自动门禁，章节诊断使用加强门禁和多题聚合，
模拟考试在开考前使用高保证自动门禁完成预组卷，并优先混入人工验证或已有稳定统计的
锚定题。平台公开发布、认证或其他明确高风险用途才强制人工验证。题目新版本不会修改
已经固定或已返回的题位；发现坏题时隔离题目、保留作答并撤销相关掌握证据。

实时自适应生成以
`docs/architecture/adaptive-ai-question-generation-design.md` 为准：

```text
学生学习证据
  -> LearnerQuestionTarget
  -> AnswerPlan
  -> 动态题目候选
  -> 确定性检查
  -> 独立盲解
  -> 歧义攻击
  -> 题型硬验证
  -> 通过后进入当前测验
```

人工审核不进入普通实时出题链路。它只用于平台公共题库、模拟考试组卷抽样、异常题
处理、离线金标集和自动门禁抽样评估。验证不确定时拒绝、重生成或回退可靠题，不能
等待人工，也不能降低门槛。

证据类型包括：

- 无提示回忆；
- 选择、填空、计算和证明；
- 用户自我解释；
- 相似题与迁移题；
- 追问内容；
- 间隔复习；
- 实践任务。

### 10.2 计算模型

第一版采用可解释的证据加权模型：

- 每种证据有基础权重；
- 提示、猜测和过短耗时降低权重；
- 难题和迁移题提高信息量；
- 时间衰减计算遗忘风险；
- 输出掌握度和置信度两个值。

积累真实数据后再评估 BKT 或 IRT。不能在没有题目参数和行为数据时伪装成精确
概率模型。

FSRS 只负责“已学内容何时复习”的记忆调度，不负责判断学生是否掌握某个主题。
主题掌握度由上述证据模型计算，再把适合记忆复习的知识单元及评分结果送入 FSRS。
实现可参考或直接采用许可兼容的语言实现：[Open Spaced Repetition](https://open-spaced-repetition.github.io/)。

## 11. 网络资源推荐

### 11.1 搜索来源

- 通用网页搜索 API；
- YouTube Data API 或支持地区的正规视频搜索接口；
- Semantic Scholar、Crossref、OpenAlex、arXiv；
- 用户或管理员维护的可信站点白名单。

### 11.2 推荐流水线

```text
主题和学习目标
  -> 生成多组搜索查询
  -> 多提供方搜索
  -> URL 归一化和去重
  -> 抓取元数据和可公开摘要
  -> 质量与适配评分
  -> 安全检查
  -> 推荐卡片
```

评分因素：

- 与当前主题的相关度；
- 难度匹配；
- 来源可信度；
- 发布时间；
- 视频时长；
- 是否有字幕；
- 是否提供例题或可验证内容；
- 用户历史反馈。

推荐文案使用“可能有帮助”，不把网络内容自动当作课程事实。用户采纳后，该资源
才进入课程资料范围，并创建版本化抓取快照。

## 12. 桌面客户端信息架构

页面级产品流程、交互优先级、状态和首版实施顺序见
`docs/design/desktop-product-ux-design.md`。本节只保留与总体架构相关的信息边界。

### 12.1 全局页面

- 课程列表；
- 新建课程；
- 我的资源库；
- 全局任务与通知；
- 账户、模型额度和隐私设置。

### 12.2 课程工作台

顶部只展示：

- 当前目标；
- 当前阶段；
- 资料状态；
- 调整目标；
- 添加资料。

主体区域：

1. `继续学习`：推荐下一任务和当前阶段任务；
2. `学习`：当前学习包；
3. `提问`：课程问答；
4. `练习`：自测和错题；
5. `知识地图`：主题、前置关系、掌握度和下一步；
6. `课程资料`：当前作用域、资料角色、选定范围、待应用调整和冲突；
7. `进度`：掌握趋势、学习记录和复习安排。

学习方案以阶段为主结构。截止日期、预计周期和单个任务耗时只作为弱提示，不形成
强制每日任务量。用户可以连续完成多个任务，也可以在风险提示后提前进入下一阶段。

用户不需要先理解“知识库模式”“作用域版本”等技术概念。全局“我的资源库”负责
上传、整理和更新；课程中的“课程资料”负责从资源库选择资料，并设置主要资料、
参考资料、考试范围、练习资料或暂不使用。

课程资料调整采用“编辑 -> 查看影响 -> 确认应用”三步。多个连续勾选操作只形成一个
草稿，不逐次触发完整影响分析；用户点击“查看影响”或离开编辑态时再批量分析。

### 12.3 阅读与引用

- PDF：页码跳转和矩形高亮；
- PPT：跳转幻灯片并高亮对象；
- Word：跳转标题和段落；
- 视频：跳转时间点并显示字幕；
- 网页：显示抓取快照和原链接。

### 12.4 桌面外壳

- 单实例运行，第二实例聚焦已有窗口；
- 应用内登录/注册后回到课程工作台；
- 系统通知可定位解析任务、学习计划或复习任务；
- 外部链接默认用系统浏览器打开；
- 文件选择和下载位置使用系统对话框；
- 更新下载完成后显示“重启并安装”，不在退出时静默安装；
- 有进行中上传时关闭窗口需要明确确认。

## 13. 后端模块与核心数据

```text
identity
courses
sources
parsing
evidence
topics
retrieval
learning
assessment
recommendations
workflow_runtime
runtime_events
model_gateway
usage_ledger
artifact_store
```

核心数据表：

- `course`、`course_profile_candidate`、`course_profile_revision`、
  `course_profile_field`；
- `scope_candidate`、`course_scope_item`、`course_focus_item`、`course_constraint`；
- `library_item`、`library_folder`、`library_tag`、`source`、`source_version`；
- `course_knowledge_scope_revision`、`course_scope_binding`、`scope_impact_report`；
- `parse_run`、`parsed_element`、`source_asset`；
- `evidence_unit`、`retrieval_chunk`、`embedding_record`；
- `topic`、`topic_alias`、`topic_edge`、`topic_evidence`；
- `knowledge_claim`、`source_conflict`、`clarification_request`；
- `learning_plan`、`learning_plan_revision`、`learning_plan_phase`、
  `learning_plan_unit`、`learning_plan_task_template`、`learning_task`、
  `learning_session`；
- `learning_event`、`learner_fact`、`learning_snapshot`；
- `item_bank`、`item_bank_entry`、`course_item_bank_binding`；
- `assessment_item`、`assessment_item_revision`、`item_family`、`item_provenance`；
- `item_topic_binding`、`item_review_run`、`item_review_decision`、`item_issue`、
  `item_statistics`；
- `assessment_blueprint`、`assessment_form`、`assessment_form_revision`、
  `assessment_form_item`；
- `assessment_attempt`、`assessment_attempt_item`、`item_response`、
  `scoring_result`、`mastery_evidence`、`topic_mastery`；
- `adaptive_question_run`、`question_generation_attempt`、
  `question_validation_run`、`question_validation_policy_revision`；
- `review_schedule`；
- `workflow_run`、`task_run`、`runtime_event`、`outbox_event`；
- `model_request`、`model_attempt`、`usage_settlement`；
- `artifact`、`citation_snapshot`。

大字段和二进制文件进入对象存储，数据库只保存元数据、索引字段和内容引用。

## 14. 后台任务与工作流

队列划分：

```text
orchestrator    流程推进和澄清恢复
io              搜索、抓取、外部 API
parse-cpu       Office、网页和普通 PDF
parse-gpu       OCR、MinerU、视觉解析
media           FFmpeg、ASR、关键帧
embedding       Embedding 和索引
learning        计划、掌握度、复习
ops             对账、清理和失活恢复
```

每个长任务使用：

- 稳定幂等键；
- 数据库状态机；
- Worker 租约；
- 心跳；
- 阶段检查点；
- 最大重试次数；
- 可取消标记；
- 不可变输入版本；
- 处理器版本；
- 结果 Artifact。

状态迁移与 Outbox 在同一数据库事务提交。事件消费者可以重复执行，但必须幂等。

## 15. API 轮廓

```text
POST   /courses
GET    /courses/{id}/profile
POST   /courses/{id}/profile/drafts
PATCH  /profile/revisions/{revisionId}
GET    /courses/{id}/profile/revisions
POST   /courses/{id}/clarification-runs
POST   /clarification-runs/{id}/answers
POST   /profile/revisions/{revisionId}/confirm
GET    /courses/{id}/scope-candidates
POST   /courses/{id}/scope-candidates/{candidateId}/resolve
GET    /courses/{id}/workspace

GET    /library/items
POST   /library/folders
POST   /library/items/{id}/tags
POST   /uploads
POST   /uploads/{id}/complete
GET    /sources/{id}
GET    /sources/{id}/versions

GET    /courses/{id}/knowledge-scope
GET    /courses/{id}/knowledge-scope/revisions
POST   /courses/{id}/knowledge-scope/drafts
PATCH  /knowledge-scope/revisions/{revisionId}/bindings
POST   /knowledge-scope/revisions/{revisionId}/analyze
GET    /knowledge-scope/revisions/{revisionId}/impact
POST   /knowledge-scope/revisions/{revisionId}/activate
POST   /courses/{id}/knowledge-scope/restore
POST   /knowledge-scope/revisions/{revisionId}/discard

POST   /courses/{id}/learning-plan-runs
GET    /learning-plan-runs/{runId}
GET    /learning-plan-revisions/{revisionId}
PATCH  /learning-plan-revisions/{revisionId}
POST   /learning-plan-revisions/{revisionId}/validate
POST   /courses/{id}/start
POST   /courses/{id}/apply-learning-plan

POST   /courses/{id}/learning-sessions
GET    /learning-sessions/{id}
POST   /learning-sessions/{id}/messages
POST   /learning-sessions/{id}/complete

GET    /courses/{id}/next-task
GET    /courses/{id}/topics
GET    /courses/{id}/mastery

GET    /item-banks
POST   /courses/{id}/item-bank-bindings
DELETE /courses/{id}/item-bank-bindings/{bindingId}
POST   /courses/{id}/items/generation-runs
POST   /item-revisions/{revisionId}/review
POST   /item-revisions/{revisionId}/issues
POST   /courses/{id}/assessment-forms
POST   /assessment-forms/{formId}/attempts
POST   /assessment-attempts/{attemptId}/next-item
POST   /assessment-attempts/{attemptId}/responses
POST   /assessment-attempts/{attemptId}/submit
GET    /assessment-attempts/{attemptId}/results

POST   /courses/{id}/recommendations/search
POST   /courses/{id}/recommendations/{id}/adopt

GET    /workflow-runs/{id}
GET    /workflow-runs/{id}/events
POST   /workflow-runs/{id}/cancel
POST   /clarifications/{id}/answer
```

`POST /assessment-attempts/{attemptId}/next-item` 必须使用 `Idempotency-Key`。服务端以
`UNIQUE(attempt_id, position)` 先短事务占位，再在事务外执行生成与多模型验证；重复
请求返回已有题位或生成状态，不能创建两个“下一题”。

`POST /profile/revisions/{revisionId}/confirm` 只冻结画像并触发计划生成，不激活课程。
`POST /courses/{id}/start` 必须携带 `profile_revision_id`、
`learning_plan_revision_id` 和两个 checksum，并在同一事务中切换活动画像和计划。

## 16. 安全与版权

- 上传文件扩展名、MIME 和魔数三重校验；
- ClamAV 扫描；
- 文件大小、页数、时长和压缩包展开限制；
- Office 宏文件默认拒绝或隔离；
- PDF 和媒体解析在隔离 Worker 容器中运行；
- 对象存储私有 Bucket + 短期签名 URL；
- 所有检索先做用户和课程权限过滤；
- 网页抓取防 SSRF，禁止内网和云元数据地址；
- 模型日志脱敏；
- 资料生命周期区分四种操作：
  - 停用：不再参与检索和新计划，数据仍保留，可随时恢复；
  - 逻辑删除：对用户隐藏，进入可配置保留期，期间允许恢复；
  - 物理清理：保留期结束后删除原文件、解析结果、向量、缓存和非必要派生物；
  - 合规删除：立即进入不可恢复流程，同时对审计、日志和备份执行匿名化或到期清理；
- 删除任务以 `source_version_id` 建立派生数据清单并幂等执行；仍被引用的学习记录只
  保留必要的结构化事实和失效引用标记，不继续暴露原文；
- 网络视频只处理有权限的内容；
- 推荐内容保留来源链接和抓取时间；
- 官方知识库记录版权、授权范围和可使用场景。

## 17. 可观测性和质量评测

### 17.1 系统指标

- API 延迟和错误率；
- 队列积压；
- Worker 心跳；
- 解析耗时和失败率；
- SSE 断线和恢复率；
- 模型延迟、Token、成本和 Fallback；
- 对象存储和索引增长。

### 17.2 解析指标

- 文本覆盖率；
- 标题层级准确率；
- 阅读顺序准确率；
- OCR 字符错误率；
- 表格结构准确率；
- 公式识别率；
- 引用定位成功率；
- 视频字幕时间对齐误差。

### 17.3 检索和回答指标

- Recall@K；
- MRR、nDCG；
- 引用覆盖率；
- 引用是否支持答案；
- 无依据陈述率；
- 资料版本正确率；
- 不同资料范围下的隔离正确率。

### 17.4 学习指标

- 诊断后题目提升；
- 延迟复习保持率；
- 掌握度校准误差；
- 计划完成率；
- 用户修改计划的频率；
- 推荐资源采纳率；
- 相同错误重复率。

上线前建立固定评测集，Prompt、模型、Embedding、解析器或排序策略变更都需要
回归测试。

## 18. 部署路线

### 18.1 开发环境

Docker Compose：

- PostgreSQL + pgvector；
- Redis；
- MinIO；
- Django API；
- Celery worker；
- Celery beat；
- ClamAV；
- 可选 Tika；
- 可选本地 OCR/ASR Worker。

桌面开发：

- `apps/web` 暂作为 renderer，由 Vite 启动；
- `apps/desktop` 编译 Electron Main 和 Preload；
- Electron 开发态等待 Vite 和 API 健康检查后再创建窗口；
- 打包态加载本地 renderer 产物；
- 本地后端仍通过 Docker Compose 或独立 Python 进程启动，不嵌入 Electron。

### 18.2 生产初期

- Windows NSIS 安装包；
- Electron renderer 静态资源随安装包发布；
- `electron-updater` 使用对象存储/CDN generic feed；
- 安装包、blockmap 上传完成后最后发布 `latest.yml`；
- 正式外发前启用 Windows 代码签名；
- Django 使用 Gunicorn/Uvicorn；
- API 和 Worker 分开部署；
- PostgreSQL 托管实例；
- Redis 托管实例；
- COS/S3 对象存储；
- CPU、GPU Worker 分池；
- Nginx 或云网关支持 SSE；
- 数据库每日备份；
- Artifact 生命周期清理。

### 18.3 扩容顺序

1. 增加 Celery Worker；
2. 拆分 CPU、GPU 和媒体队列；
3. 增加只读数据库或缓存；
4. 独立检索服务；
5. 需要跨服务长流程时再评估 Temporal；
6. 只有 PostgreSQL 检索达到明确瓶颈时再引入 OpenSearch 或独立向量库。

## 19. 分阶段交付

### M0：文本 PDF 纵向样板

范围：

- 用户资源库；
- Windows Electron 桌面壳、单实例和安全 preload；
- 主进程 API/SSE Bridge；
- 应用内登录/注册（凭据经 IPC，Refresh Token 存 safeStorage）；
- 文本层完整的 PDF 上传和不可变版本；
- 课程创建并从资源库选择 PDF；
- 完整快照式 `CourseKnowledgeScopeRevision`；
- 单一草稿、`binding_key`、`lock_version` 和 Binding checksum；
- 原子激活和 active 部分唯一约束；
- 服务端强制作用域过滤和不可变 `TurnEvidenceSnapshot`；
- PyMuPDF 快速解析；
- PostgreSQL + pgvector 混合检索；
- 带引用问答；
- PDF 原文页码与坐标跳转；
- 任务进度；
- Electron unpacked 和 NSIS Smoke Test。

验收：

- 用户能上传一份真实文本 PDF，并从一门课程中选择它；
- renderer 无法直接访问 Node.js、令牌和任意本地路径；
- 大 PDF 由主进程流式上传，不能完整复制为 IPC base64；
- 解析结果可查看；
- 回答必须引用原文；
- 引用能够跳转；
- 解析失败可重试；
- 新资料不覆盖旧版本；
- 未绑定但属于同一用户的 PDF 不能被课程检索命中；
- 过期草稿编辑返回 412，基于旧 active 修订激活时返回 409；
- 历史回答能够定位当时的作用域修订、资料版本和证据单元。

### M1：扫描 PDF 与解析可靠性

范围：

- 扫描件检测；
- PaddleOCR；
- MinerU 高质量回退；
- 解析质量指标、失败重试和人工切换解析器；
- PDF 基准集与引用准确率评测。

### M2：Office 资料接入

范围：

- DOCX、PPTX；
- LibreOffice 旧格式转换；
- PPT 截图、备注和形状坐标；
- Word 标题、表格、图片和页码映射；
- Office 原文跳转。

### M3：课程主题与配置联动

范围：

- 主题候选生成、别名与前置关系；
- `ScopeCandidate -> CourseScopeItem` 解析；
- 澄清候选填充课程配置面板；
- 用户修改、确认并冻结 `CourseProfileRevision`；
- 完整课程知识作用域草稿、影响分析和激活；
- 用户选择官方基础库并设置辅助角色；
- 新资料的增量影响分析。

### 阶段二：计划与学习闭环

范围：

- 需求澄清；
- 双确认建课状态机；
- 可编辑的阶段、单元和任务路径卡片；
- 计划依赖、预算、覆盖与资料可用性校验；
- 最终启动时原子激活画像和计划；
- “继续学习”；
- 学习包；
- 章节练习；
- 官方题、用户题和 AI 候选题的统一题目版本；
- 基于学生掌握状态和误区的动态 AI 出题；
- 答案优先、独立盲解、歧义攻击和题型硬验证；
- AI 动态题受限权重使用和缺陷隔离；
- 固定卷预先固定题位、自适应卷逐题固定题位，以及确定性评分；
- 基础掌握度；
- 动态目标调整。

验收：

- 一句模糊诉求经过少量澄清后只填充画像草稿，不会自动启动课程；
- 用户确认画像后才能生成计划，计划确认前不能产生可执行学习任务；
- 用户能调整路径卡片，前置冲突和预算超限得到明确反馈；
- 修改截止日期、范围或目标深度会返回画像面板并使旧计划草稿过期；
- “开始学习”要么同时激活画像和计划，要么全部失败；
- 完成学习和练习后，下一任务发生合理变化；
- 发布题目新版本不会改变历史测验；
- AI 候选题未通过自动审校时不能进入章节自测；
- 学生连续正确、错误或使用提示后，下一题的难度或测量目标发生可解释变化；
- 验证服务不可用时稳定回退，不展示未验证题；
- 隔离坏题后相关掌握证据能够撤销并重算；
- 修改截止日期后只重算剩余计划。

### 阶段三：视频与多模态

范围：

- 上传音视频；
- 字幕、ASR 和时间引用；
- PPT 视频关键帧；
- 独立图片、图表和手写内容解析；
- 网络资源推荐。

验收：

- 视频问答可跳转对应时间；
- 关键幻灯片可检索；
- 网络推荐有来源和适用理由。

### 阶段四：高级评测和资料演进

范围：

- 迁移题和解释题；
- 用户试卷、作业和答案册提题；
- 人工题目审校工作台与题目统计；
- 开放题 Rubric 和模型辅助评分；
- 模拟考试蓝图、曝光控制和等价卷；
- QTI 3 导入导出适配；
- FSRS 复习；
- 知识主张冲突检测与用户澄清；
- 基于 Claim 和 Topic 的选择性重算；
- 知识地图；
- 离线评测与成本优化。

验收：

- 新资料只重算受影响主题；
- 高影响冲突要求用户确认；
- 复习任务随历史表现调整；
- 掌握度可展示证据来源。

## 20. 当前明确的技术决策

| 问题 | 当前决策 |
| --- | --- |
| 系统形态 | 模块化单体 |
| 客户端形态 | Electron 薄桌面客户端，Windows 首发 |
| 桌面构建 | electron-builder + NSIS |
| 桌面更新 | electron-updater + generic feed，用户确认安装 |
| 后端 | Django + DRF |
| 异步任务 | Celery + Redis |
| 主数据库 | PostgreSQL |
| 向量检索 | pgvector |
| 对象存储 | MinIO 开发，S3/COS 生产 |
| 资料组织 | 用户级资源库 + 不可变 SourceVersion |
| 课程资料 | 版本化 CourseKnowledgeScopeRevision |
| Renderer | React + TypeScript + Vite |
| 桌面安全 | contextIsolation + sandbox + typed preload |
| 实时输出 | Main Process 桥接可恢复 SSE |
| PDF | PyMuPDF 快速路径，MinerU 高质量路径，PaddleOCR OCR |
| Office | Docling/python-docx/python-pptx/openpyxl |
| 旧 Office | LibreOffice headless 转换 |
| 视频 | FFmpeg + ASR + 场景关键帧 |
| 网页 | httpx + trafilatura，Playwright 回退 |
| 混合检索 | 关键词 + 向量 + RRF + 可选重排 |
| 知识地图 | React Flow + ELK.js |
| 复习 | FSRS |
| 题库 | 统一 AssessmentItemRevision，来源和用途分级 |
| AI 出题 | 日常练习动态生成；答案优先 + 独立盲解 + 歧义攻击 + 硬验证 |
| 题目交换 | 后续 QTI 3 适配，首期内部使用 JSON/关系模型 |
| Agent | 受控工具循环，只用于开放推理 |
| 业务流程 | 显式持久状态机 |
| 工作流升级 | 达到跨服务长流程门槛后评估 Temporal |

## 21. 当前不做

- 不训练自有基础大模型；
- 不从第一版开始建设通用知识图谱；
- 不让 AI 自动覆盖用户资料；
- 不允许模型默认检索用户整个资源库；
- 不因资源出现新版本而静默替换课程作用域；
- 不把所有资料全文塞进 Prompt；
- 不对每次上传做全库两两比较；
- 不提前为整门课程生成全部个性化内容；
- 不把聊天记录当作掌握度；
- 不让未通过当前 `assessment_risk_profile` 自动门禁的 AI 题进入测验；
- 不让普通动态题等待人工逐题审批；
- 不用单模型同一上下文自我确认代替独立验证；
- 不让单道低可信题直接大幅改变掌握度；
- 不在第一版实现正式考试、IRT 或全量人工审题；
- 不默认下载和保存网络视频；
- 不在 renderer 开启 Node.js 或暴露任意 IPC；
- 不在客户端内置 Django、Celery、数据库、OCR 或本地模型运行时；
- 不在首期实现离线检索、离线 AI、托盘常驻和后台上传；
- 不复制 Lightest 的终端、SSH、Git、Computer Use 和远程 Agent 体系；
- 不在没有明确瓶颈时拆微服务或引入独立向量数据库。

## 22. 下一步工程工作

在正式恢复实现前，应依次完成：

1. 冻结桌面进程边界、课程配置版本、用户资源库与课程知识作用域、资料证据生命周期和
   测评证据 ADR；
2. 将 M0 拆成 Electron IPC、认证、上传、API/SSE、数据表和任务状态 ADR；
3. 冻结 Desktop API、`ParsedBundle`、`EvidenceUnit` 和结构化引用 Schema；
4. 先完成 Electron 安全壳、登录和流式上传 Spike；
5. 准备文本 PDF 解析基准集和课程问答检索金标集；
6. 实现 M0：桌面选择并上传文本 PDF -> 解析 -> 课程选择 -> 作用域过滤检索 ->
   引用问答 -> PDF 定位；
7. M0 达标后依次推进扫描 PDF、Office、主题配置联动；
8. 视频、完整计划和掌握度在前述基础设施稳定后进入后续阶段。
