# ADR-0006：ParsedBundle 与 EvidenceUnit 数据契约

- 状态：Proposed
- 日期：2026-06-13
- 关联设计：`docs/architecture/technical-solution.md` §5
- 关联阶段：`docs/project-management/stage-01-backlog.md` P1-LH-01

## 背景

系统需要统一表示解析产物和可引用证据，供检索（LH）、Tutor 回答（LWJ）和
原文定位（LBZ）消费。不同解析器（PyMuPDF、后续的 MinerU 等）必须产出
相同 Schema，上游消费者不感知解析器差异。

P1-LH-01 要求交付：页码和阅读顺序、元素类型和文本、PDF Bounding Box（可用时）、
警告和提取质量字段、内容 Hash 和 Artifact 引用。

## 决策

### 1. 解析产物使用 ParsedBundle 作为顶层容器

一个 ParsedBundle 对应一次完整的文件解析运行。字段包括：

- `source_version_id`：关联不可变资料版本
- `parser`（name + version）：参与幂等键，版本升级后可区分新旧产物
- `content_hash`：原始文件 SHA-256，用于重复检测和缓存键
- `pages`：按阅读顺序排列的 Page 列表
- `quality`：解析质量评估（供 OCR 决策参考）
- `artifact_ref`：对象存储键，数据库不存储 bundle 正文

### 2. 页面内元素使用 ParsedElement 枚举类型

类型包括 `paragraph`、`heading`、`table`、`formula`、`image`、`list_item`。
每个元素携带 text、可选 BoundingBox、heading_level（仅标题）、confidence。

### 3. 坐标使用 PDF 标准坐标系

原点为左下角，单位为点（pt, 1/72 英寸）。`x1 >= x0` 且 `y1 >= y0`。
不在 Schema 中引入像素或百分比坐标以避免歧义。

### 4. 页码使用物理序 + 原文件标注双字段

- `page_number`：从 1 开始递增
- `original_label`：保留原文件标注（如 "iii"、"A-1"），不参与计算

### 5. EvidenceUnit 通过索引引用 ParsedElement

EvidenceUnit 保存 `element_indices`（拍平后的 0-based 索引），不复制坐标。
消费者需要坐标时通过 ParsedBundle 回查。这样可以：
- 避免坐标数据在 Evidence 表中冗余
- 解析产物更新时 EvidenceUnit 自然失效
- 保持 EvidenceUnit 体积小、适合检索返回

### 6. EvidenceSnapshot 在每次模型调用时冻结

模型只能看见调用时刻批准的 Evidence ID 列表，后续资料变更不影响已生成回答。
快照记录 `scope_revision_id` 和 `evidence_ids`，支持历史回答回溯。

### 7. 首版用 Pydantic v2 实现

Pydantic v2 提供声明式校验（`@model_validator`、`Field(ge=, le=)`），
可直接生成 JSON Schema 供跨语言消费。后续如需 TypeScript 侧 Schema，
从 Pydantic 模型导出 JSON Schema 后通过工具生成。

## 影响范围

- **LH**：所有解析器 Adapter 必须产出 ParsedBundle
- **WH**：持久化时引用 `parsing.ParsedBundle` 和 `parsing.EvidenceUnit` 类型
- **LWJ**：Tutor 回答引用 `EvidenceUnit.id`，输入包含 `EvidenceSnapshot`
- **LBZ**：原文定位使用 `page_number` 和 `BoundingBox`

## 尚未完成 / 已知限制

- 不含 Embedding 向量字段（M5 补充）
- 不含多列阅读顺序推断规则（在 Parser Adapter 中实现）
- EvidenceUnit 的 element_indices 拍平规则需要在 Parser Adapter 中明确文档化
