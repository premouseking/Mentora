# LH 分阶段开发计划

> 角色：资料与检索（与 WH 共同定义资料身份和不可变资料版本；负责解析、
> ParsedBundle、EvidenceUnit、检索投影、Embedding、召回、课程作用域过滤、
> 原文引用定位、解析与检索基准数据集。）
>
> 当前阶段：第一阶段（工程基线与资料处理链路），项目处于初期。
> 前端多处 UI 呈现和交互细节尚未敲定，以原型迭代方式推进。

## 推进策略

项目初期，前端页面作为产品方向探索的手段先行搭建（骨架 → 原型 → 真实集成）。
核心后端工作（解析、证据、检索）从 P1-LH-01 契约设计开始向外扩展。
两条线并行但节奏不同：前端原型验证产品假设，后端契约和 Worker 逐步建设。

## 优先级划分

| 级别 | 含义 | 判断标准 |
| --- | --- | --- |
| P0 | 阻塞阶段交付，必须本阶段完成 | 团队章程 Definition of Done |
| P1 | 驱动下一阶段进入，本阶段后半程启动 | 为 Stage 2 准备接口和数据 |
| P2 | 前端原型探索，验证产品方向 | 辅助 LBZ 确认 UI 方案，后续移交 |
| P3 | 远期能力，仅做技术调研 | 不阻塞当前阶段 |

---

## M1：前端产品骨架（P2，进行中）

项目初期需要可交互的界面来验证产品方向。LBZ 作为前端 DRI，LH 以支援方式参与
前端页面原型搭建，帮助加速产品决策。

| 任务 | 状态 | 说明 |
| --- | --- | --- |
| 课程列表、建课流程、课程工作台 | 已由 LBZ 完成 | 见 `apps/web/src/pages/` |
| AI 助手浮窗交互 | 原型完成 | 已被 AppShell 内置 AiChatPanel 取代 |
| 全局资源库页面 | 原型完成 | 含文件夹管理、拖拽移动、上传弹窗 |
| 学习记录页面 | 原型完成 | 时间线展示，12 种事件类型 |

**后续原则：**
- 新前端页面以可交互原型交付，优先走通主流程
- UI 细节（动画曲线、精确间距、空状态文案）由 LBZ 统一打磨
- 页面中涉及「资料上传」「解析进度」「证据引用」的部分需与 LH 的后端 Schema 对齐
- 前端页面逐渐移交 LBZ，LH 不再新建独立页面，除非涉及检索/证据的专用组件

---

## M2：ParsedBundle 与 EvidenceUnit 契约（P0，即将启动）

**对应：** P1-LH-01  
**评审人：** WH、LWJ  
**依赖：** 无

这是 LH 在 Stage 1 的核心交付，决定了后续解析、检索和引用的数据基础。

交付物：
- ParsedBundle Schema：SourceVersion + ParserVersion、页码与阅读顺序、元素类型与文本、
  PDF Bounding Box（可用时）、警告与提取质量字段、内容 Hash 与 Artifact 引用
- EvidenceUnit Schema：稳定的证据 ID、页码和坐标引用、内容片段、来源版本锁定
- JSON 往返序列化校验
- 非法元素校验规则

验收：
- 页码使用统一记录规则（从 1 开始或从原文件页码）
- 坐标明确原点和单位（PDF 点或像素）
- 非法元素无法通过 Schema 校验
- Schema 可被 WH（持久化）和 LWJ（模型输入）直接引用

**此任务不涉及任何前端页面。** 产出为 TypeScript / Python 类型定义和 JSON Schema。

---

## M3：文本 PDF 解析 Worker（P0，依赖 M2）

**对应：** P1-LH-02  
**评审人：** WH  
**依赖：** P1-WH-01（持久化模型）、P1-LH-01（契约）

交付物：
- PyMuPDF Parser Adapter（统一解析器接口的第一个实现）
- 3 个可安全提交到仓库的测试 PDF Fixture（正常文本、多栏、含表格）
- ParsedBundle Artifact 持久化（写入对象存储，数据库只存引用）
- 最小 EvidenceUnit 持久化（段落/语义块级别）
- 分类后的解析错误（加密 PDF、损坏 PDF、纯图片 PDF → 不同错误码）

验收：
- 普通文本 PDF 保留正确页码
- 重试不会生成重复 Evidence（ContentVersion + ParserVersion 组成幂等键）
- 纯图片 PDF 返回专门错误码，不静默当作成功
- 文档记录的安装和验证命令可重现

**前端配合：** 需要 LBZ 的处理进度 UI 展示解析阶段（`pending` → `running` → `completed`），
但事件定义和数据流由 WH 的 Runtime Event 和 SSE 统一管理，LH 只负责 Worker 内部逻辑。

---

## M4：解析基准数据集（P0，依赖 M3）

**对应：** P1-LH-03  
**评审人：** WH、LBZ、LWJ  
**依赖：** P1-LH-02

交付报告：
- Fixture 特征描述（页数、文本密度、图表比例、语言）
- 提取页数和文本数量
- 页码关联准确性（人工抽查至少 20 页）
- 警告和已知限制
- 处理耗时和内存峰值观察

验收：
- 一条文档化命令即可重跑
- 报告区分「产品暂不支持」与「解析器缺陷」
- 纯图片 PDF 明确延期，不能静默当作成功

---

## M5：Evidence 持久化与 pgvector 检索（P1，为 Stage 2 准备）

**对应：** 第二阶段 LH 交付  
**评审人：** WH、LWJ  
**依赖：** M2、M3、P1-WH-01

核心能力：
- EvidenceUnit 持久化模型与 Django ORM 映射
- pgvector 扩展配置和 Embedding 向量存储
- 全文检索（`pg_trgm` 或外部分词 `tsvector`）
- 混合召回管线（关键词 + 向量 → RRF 融合）
- 课程当前 `CourseKnowledgeScopeRevision` 过滤（必须通过作用域权限校验）
- 引用定位：从 Evidence ID 映射回页码和坐标

验收：
- 课程当前作用域外的资料不会进入召回结果（安全硬要求）
- 回答引用稳定的 Evidence ID 和页码
- 证据不足时明确拒答
- 基准问题可输出召回率和引用准确率

**前端配合：** 此阶段 LH 可能需要提供：
- 原文定位组件（PDF 页码跳转、Bounding Box 高亮）—— 可先出原型
- 检索调试面板（查看当前作用域、召回结果排序明细）—— 内部工具，非用户功能

---

## M6：协作与接口评审（持续）

**RACI 矩阵中 LH 参与评审的任务：**

| 评审对象 | 负责人 | 何时参与 |
| --- | --- | --- |
| REST 错误和 Runtime Event | WH | WH 起草后 |
| RetrievalRequest 和 EvidenceSnapshot | LH（自审） | 与 LWJ、WH 对齐 |
| 模型任务输入输出 Schema | LWJ | Schema 中涉及 Evidence ID 和引用格式时 |
| Desktop API 和 IPC Schema | WH | 涉及文件上传和路径安全时 |
| 上传 API 契约 | WH | 涉及 SHA-256 校验和文件类型检测时 |

**LH 作为消费者依赖的接口：**
- WH：Source、SourceVersion 持久化模型（P1-WH-01）
- WH：对象存储上传和 Artifact 引用（P1-WH-02）
- WH：Celery 任务调度和 Runtime Event（P1-WH-03）

---

## 不做事项（首个里程碑之前明确排除）

- 超出 PyMuPDF 的 OCR（扫描 PDF）、Office、音频、视频处理
- 独立 OpenSearch 或向量数据库（首版用 pgvector）
- 离线检索或离线 Embedding
- 全局知识图谱、自由编辑的主题模型
- 前端全局 AI 助手（已由 AppShell 内置 AiChatPanel 覆盖，LH 不再维护）
- 正式考试、认证考试的题目校准和人审流程

---

## 当前状态总结

| 模块 | 状态 | 下一步 |
| --- | --- | --- |
| 前端原型（资源库、学习记录） | 原型可用 | 移交 LBZ 打磨 UI 细节 |
| AI 助手浮窗 | 被 AppShell AiChatPanel 取代 | LH 不再维护 |
| P1-LH-01 契约 | 待启动 | 与 WH 对齐 Source/SourceVersion 模型后开始 |
| P1-LH-02 解析 Worker | 待 M2 完成 | 准备 3 个测试 PDF Fixture |
| P1-LH-03 解析基准 | 待 M3 完成 | 设计基准报告模板 |
| M5 检索管线 | 远期 | 调研 pgvector 配置和中文分词方案 |

---

## 近期行动（本周）

1. **与 WH 对齐 Source/SourceVersion 数据模型**——LH 的 ParsedBundle 和 EvidenceUnit
   依赖这些基础模型，需要在 P1-LH-01 开始前确认字段和版本语义。
2. **准备 3 个 PDF Fixture**——正常文本 PDF、多栏排版 PDF、含表格/公式 PDF，
   用于 P1-LH-02 开发和 P1-LH-03 基准测试。
3. **将已建的前端原型页面清单提交给 LBZ**——明确哪些页面是原型、哪些交互是占位、
   哪些需要 LBZ 重新对接真实 API。
4. **停止新建独立前端页面**——后续前端工作以协助 LBZ 的方式参与，不再独立开新页面。
