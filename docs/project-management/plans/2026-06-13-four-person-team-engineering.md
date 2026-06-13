# 四人团队工程化执行计划

**目标：** 让 Mentora 四人团队以明确职责、稳定评审机制和一个可执行的
阶段目标正式开始工程开发。

**架构方式：** 产品架构继续以 `docs/architecture/` 为准，
`docs/project-management/` 作为工程交付控制层。把第一阶段任务清单
转换为个人可领取任务，冻结最小共享契约，并通过“上传到处理结果”这一条
纵向链路完成集成。

**技术栈：** Markdown、GitHub Issues 和 Pull Requests、React/TypeScript、
Django/DRF、PostgreSQL、Redis、Celery、MinIO、PyMuPDF、Pydantic、
Vitest、pytest。

---

### 任务 1：确认四位成员的职责

**文件：**
- 修改：`docs/project-management/README.md`
- 修改：`docs/project-management/team-charter.md`

- [ ] **步骤 1：确认成员与职责映射**

确认以下职责分配：

```text
WH - 组长、后端与平台
LBZ - 产品与前端
LH - 资料与检索
LWJ - AI 学习与评测
```

- [ ] **步骤 2：确认职责**

WH 组织职责确认。每位成员阅读自己对应的“负责”“禁止”和
“每个功能必须交付”部分，并在项目启动会议记录中确认。

- [ ] **步骤 3：检查角色记录**

运行：

```powershell
Select-String -Path docs\project-management\README.md -Pattern 'WH|LBZ|LH|LWJ'
```

预期：四位成员均能匹配到角色记录。

- [ ] **步骤 4：提交角色分配**

```powershell
git add docs/project-management/README.md docs/project-management/team-charter.md
git commit -m "docs: assign Mentora team ownership"
```

### 任务 2：创建第一阶段工程任务

**文件：**
- 阅读：`docs/project-management/stage-01-backlog.md`
- 使用：`.github/ISSUE_TEMPLATE/engineering-task.yml`

- [ ] **步骤 1：为每个 Backlog ID 单独创建 Issue**

创建以下十一个 Issue，禁止合并为大任务：

```text
P1-LBZ-01 上传用户流程
P1-LBZ-02 处理状态与恢复
P1-WH-01 持久化处理状态
P1-WH-02 上传和处理 API
P1-WH-03 Celery 调度和 Runtime Event
P1-LH-01 ParsedBundle 和 EvidenceUnit 契约
P1-LH-02 文本 PDF 解析 Worker
P1-LH-03 解析基准
P1-LWJ-01 模型网关契约
P1-LWJ-02 结构化输出校验测试集
P1-TEAM-01 端到端验收
```

- [ ] **步骤 2：复制完整验收标准**

从 Backlog 中复制负责人、评审人、依赖、交付物、验收标准和测试要求，
不能只写概括性描述。

- [ ] **步骤 3：建立依赖链接**

每个 Issue 列出阻塞它的任务 ID。第一阶段集成 Issue 必须关联所有关键链路任务。

- [ ] **步骤 4：只把 Ready 任务加入当前阶段**

只有满足 `team-charter.md` 中 Definition of Ready 的 Issue 才能进入“可开始”状态。

### 任务 3：冻结第一阶段共享契约

**文件：**
- 新建：`docs/contracts/runtime-event-v1.md`
- 新建：`docs/contracts/source-processing-v1.md`
- 新建：`docs/contracts/model-gateway-v1.md`

- [ ] **步骤 1：定义 Runtime Event**

记录以下必填字段：

```text
event_id
stream_id
sequence
event_type
entity_id
status
progress
payload
occurred_at
```

明确 `sequence` 在单个 Stream 内单调递增，事件投递不能替代 REST 持久化状态。

- [ ] **步骤 2：定义资料处理契约**

记录：

```text
Source
SourceVersion
ProcessingRun
ParsedBundle
EvidenceUnit
```

必须包含 ID 所有权、不可变规则、状态值、页码规则、坐标规则、
ParserVersion 和幂等键。

- [ ] **步骤 3：定义模型网关契约**

记录与模型厂商无关的 Request、Attempt、StructuredOutput、Timeout、
Fallback、Usage 和审计字段。领域服务禁止直接导入模型厂商 SDK。

- [ ] **步骤 4：完成契约评审**

必须获得以下成员确认：

```text
runtime-event-v1：WH、LBZ、LH
source-processing-v1：WH、LH
model-gateway-v1：WH、LH、LWJ
```

- [ ] **步骤 5：提交契约**

```powershell
git add docs/contracts
git commit -m "docs: freeze phase one service contracts"
```

### 任务 4：建立干净 Checkout 的开发基线

**文件：**
- 修改：`README.md`
- 修改：`apps/api/README.md`
- 修改：`infra/docker/docker-compose.dev.yml`
- 修改：`.env.example`

- [ ] **步骤 1：记录环境要求**

记录支持的 Node.js、pnpm、Python、Docker、PostgreSQL、Redis 和 MinIO
版本与要求，不允许写入个人机器的绝对路径。

- [ ] **步骤 2：验证基础设施启动**

运行：

```powershell
corepack pnpm infra:up
docker compose -f infra/docker/docker-compose.dev.yml ps
```

预期：所有必需服务处于 healthy 或 running。

- [ ] **步骤 3：验证 Renderer**

运行：

```powershell
corepack pnpm typecheck:web
corepack pnpm test:web
corepack pnpm build:web
```

预期：所有命令退出码为 `0`。

- [ ] **步骤 4：验证 API**

在 `apps/api` 中运行：

```powershell
pytest
ruff check .
```

预期：所有命令退出码为 `0`。

- [ ] **步骤 5：记录环境阻塞**

任何缺少的依赖或无法复现的步骤，都必须建立由 WH 负责的阻塞 Issue，
解决前不继续相关功能开发。

### 任务 5：执行第一阶段集成验收

**文件：**
- 阅读：`docs/project-management/stage-01-backlog.md`
- 修改：第一阶段 Issue 中的验收证据

- [ ] **步骤 1：运行干净环境端到端流程**

执行 `P1-TEAM-01：端到端验收` 中的全部九个步骤。

- [ ] **步骤 2：记录技术证据**

附加：

- Renderer 运行中、成功和失败状态截图；
- API Request ID；
- ProcessingRun 状态历史；
- Parser Artifact 和 Evidence 数量；
- 重复 complete 请求结果；
- Worker 失败恢复结果。

- [ ] **步骤 3：运行仓库检查**

```powershell
corepack pnpm typecheck:web
corepack pnpm test:web
corepack pnpm build:web
Push-Location apps/api
pytest
ruff check .
Pop-Location
git diff --check
```

预期：所有命令退出码为 `0`。

- [ ] **步骤 4：验收或延长当前阶段**

只有九项端到端检查全部通过，第一阶段才能验收。未完成的可选工作进入后续
阶段任务清单；关键链路失败时继续停留在第一阶段。

- [ ] **步骤 5：更新路线图**

进入第二阶段之前，把实际风险、延期工作、基准结果和契约变更记录到
`docs/project-management/delivery-roadmap.md`。
