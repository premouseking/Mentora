# 建课流程后端实现 + 前后端联调

- 状态：Implemented
- 日期：2026-06-18
- 分支：`feat/P1-LBZ-04-course-creation`
- 关联：
  - `docs/design/specs/2026-06-18-course-creation-redesign.md`（前端设计）
  - `docs/architecture/end-to-end-implementation-plan.md` §2.1

> ⚠️ **首次启动前必须执行数据库迁移**，详见 [§2.2 数据库迁移](#22-%EF%B8%8F-数据库迁移必须执行见下文)。
> 跳过迁移会导致建课 API 全部返回 500 错误。

## 变更记录

| 日期 | 内容 |
|---|---|
| 2026-06-18 | 后端 API 实现 + 前后端联调完成 |
| 2026-06-18 | 新增 `school` 字段（迁移 0002），clarifier 改为每轮单问题 |
| 2026-06-18 | MentoraLoader 粒子动画（追问 + 方案），clarifier v2.1.0 禁复合问题 |

---

## 1. 架构概述

### 1.1 模块关系

```
前端 (React + Vite)
  │  courseApi.ts（fetch 封装）
  ▼
Django REST API (config/urls.py)
  │  courses/views.py（5 个端点）
  ├─► courses/models.py（CourseCreationSession 模型）
  ├─► courses/schemas.py（Pydantic 校验）
  ├─► courses/serializers.py（DRF 序列化）
  └─► agent_runtime/views.py（单例 Gateway + PromptManager）
       ├─► model_gateway（LLM 调用）
       └─► prompts/templates/clarifier.json / planner.json
```

### 1.2 核心设计决策

| 决策 | 理由 |
|---|---|
| 轻量 `CourseCreationSession`（单表 JSON）而非完整 Course 模型 | 避免死代码堆砌，建课会话只是临时状态 |
| 结构化 JSON 输出（非 Function Calling） | Prompt 约束输出格式 + Pydantic 校验，实现简单可控 |
| 追问最大 8 轮，**每轮只问 1 个问题**（clarifier v2.1.0 禁复合问题） | 防止 LLM 无限追问形成死循环；一次多个问题用户回答负担重 |
| `guidance` 字段 → AiMessageBubble | 引导文字与问答主体分离渲染 |
| 方案不持久化到数据库 | 暂不需要保存方案，仅返回给前端展示 |
| 跳过资料系统（步骤 3） | 资料系统未就绪，ClarifierAgent / PlannerAgent 暂不使用 retrieve_evidence 工具 |
| 复用 `agent_runtime/views.py` 单例 | Gateway 和 PromptManager 全局复用，避免重复初始化 |

---

## 2. 数据库模型

### 2.1 CourseCreationSession

**文件**：`apps/api/mentora/courses/models.py`

```python
class CourseCreationSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    status = models.CharField(max_length=32, choices=SessionStatus.choices)
    goal = models.TextField(blank=True, default="")        # 步骤1
    level = models.CharField(max_length=64)                 # 步骤2
    pace = models.CharField(max_length=64)                  # 步骤2
    school = models.CharField(max_length=128)               # 步骤2 学校
    inquiry_history = models.JSONField(default=list)        # 步骤4 追问记录
    extra = models.JSONField(default=dict)                  # 扩展
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

**表名**：`courses_session`

**索引**：`(status, created_at)` 联合索引

**SessionStatus 枚举**：
- `collecting` — 收集基础信息中（步骤 1-2）
- `inquiring` — AI 追问中（步骤 4）
- `generating_plan` — 生成方案中（步骤 5）
- `completed` — 已完成

### 2.2 ⚠️ 数据库迁移（**必须执行，见下文**）

> **注意**：本次变更引入新模型 `CourseCreationSession`，需要创建新数据库表 `courses_session`。
> 以下内容必须完整阅读后再操作，**跳过迁移将导致建课 API 全部 500**。

#### 迁移影响分析

| 项目 | 说明 |
|---|---|
| **操作类型** | **纯新增**一张表 `courses_session`（0001），后**新增一列** `school`（0002），不改动任何已有表 |
| **影响范围** | 仅影响 `mentora/courses` 模块的 API 端点（5 个新建课路由） |
| **迁移文件** | `0001_initial.py`（建表）+ `0002_add_school.py`（加列），均已提交 Git |
| **已有功能** | ☑ 不受影响 —— 聊天 API、上传、解析等已有功能与本次迁移无关 |
| **生产数据库** | 当前为本地 SQLite 开发环境（`db.sqlite3`），尚无生产数据库 |
| **团队影响** | 所有开发者拉取此分支后**必须执行 `migrate`**，否则建课页面前端请求全部 500 |
| **回滚方式** | 反向迁移 `python manage.py migrate courses zero`（仅删除 `courses_session` 表，不影响其他表） |

#### 操作步骤

```powershell
# 1. 进入后端目录
cd apps/api

# 2. 激活虚拟环境（如未激活）
D:\Apps\miniforge3\envs\mentora\Scripts\activate

# 3. 生成迁移文件（会在 mentora/courses/migrations/ 下生成 0001_initial.py）
python manage.py makemigrations courses

# 4. 查看将要执行的 SQL（确认无意外操作）
python manage.py sqlmigrate courses 0001

# 5. 执行迁移
python manage.py migrate

# 6. 验证迁移状态
python manage.py showmigrations courses
# 应显示：[X] 0001_initial  [X] 0002_add_school
```

#### 迁移文件管理

- 生成的迁移文件（`0001_initial.py`、`0002_add_school.py`）**必须提交到 Git**
- 提交后，其他开发者只需执行 `python manage.py migrate`，**不需要重新 `makemigrations`**
- 迁移文件属于代码仓库的一部分，与模型定义共同构成版本化 schema

#### 故障排查

| 症状 | 可能原因 | 处理 |
|---|---|---|
| `manage.py migrate` 报错 "no such table" | `makemigrations` 未生成迁移文件 | 先执行 `makemigrations courses` |
| 建课 API 返回 500 | 未执行 `migrate`，表不存在 | 执行 `migrate` |
| `makemigrations` 生成多余迁移 | 模型字段变更后未同步 | 检查 `models.py` 是否与预期一致 |
| 迁移文件冲突 | 多人同时修改同一模型 | 合并迁移依赖树（`migrate` 会自动处理顺序） |

#### 回滚方案

如需撤销本次迁移（例如模型定义有误需要重建）：

```powershell
# 回滚 courses 模块所有迁移（仅删除 courses_session 表）
python manage.py migrate courses zero

# 删除迁移文件
del mentora\courses\migrations\0001_initial.py
del mentora\courses\migrations\0002_add_school.py

# 修正 models.py 后重新生成
python manage.py makemigrations courses
python manage.py migrate
```

> **再次强调**：`migrate courses zero` 只删除 `courses_session` 表，**不会影响**聊天、上传、解析等其他模块的数据。

---

## 3. API 端点

**文件**：`apps/api/mentora/courses/views.py`  
**路由**：`apps/api/config/urls.py`

### 3.1 Session CRUD

| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/api/courses/sessions/` | 创建会话 `{ goal }` → `{ id, goal, status }` |
| `GET` | `/api/courses/sessions/<uuid>/` | 获取详情（含 inquiry_history） |
| `PATCH` | `/api/courses/sessions/<uuid>/update/` | 更新 `{ level?, pace?, school? }` → `{ status: "ok" }` |

### 3.2 Inquiry 追问

| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/api/courses/sessions/<uuid>/inquiry/` | LLM 追问循环 |

**请求体（可选）**：`{ "answer": "用户回答" }`

**首次调用**不传 `answer`，触发首个问题。后续每次传入回答，LLM 判断是否继续追问。

**返回**：
- 继续追问：`{ "ready": false, "questions": [{ "text", "type", "options", "guidance" }] }`
- 信息充足：`{ "ready": true, "summary": "总结文本" }`

**追问循环逻辑**：
1. 有回答 → 追加到 `inquiry_history` 最后一条 pending 条目
2. 超过 8 轮 → 强制 `ready=true` 终止
3. 调用 `ClarifierAgent` + `clarifier.json` 模板 → LLM 结构化 JSON 输出
4. LLM 返回新问题 → 追加 pending 条目到 `inquiry_history`（`answer: ""`）
5. `ready=true` → 状态切换为 `generating_plan`

### 3.3 Plan 方案生成

| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/api/courses/sessions/<uuid>/plan/` | LLM 生成学习方案 |

**返回**：`{ "phases": [{ "name", "goal", "share", "tasks" }] }`

调用 `PlannerAgent` + `planner.json` 模板，基于全部已收集信息（goal + level + pace + inquiry_history）生成 4-5 个学习阶段。方案**不持久化到数据库**，仅返回 JSON。

---

## 4. Pydantic Schema

**文件**：`apps/api/mentora/courses/schemas.py`

| Schema | 用途 | 关键字段 |
|---|---|---|
| `InquiryQuestion` | 单个追问问题卡 | text, type(single_choice\|multi_choice\|free_text), options[], guidance |
| `ClarifierResponse` | LLM 追问输出 | ready(bool), questions[], summary |
| `PlanPhase` | 方案阶段卡 | name, goal, share(10-50), tasks[] |
| `PlanResponse` | LLM 方案输出 | phases[] |

所有 Schema 用于 `ModelGateway.chat(structured_output_schema=...)` 校验 LLM 输出。

---

## 5. Prompt 模板

### 5.1 Clarifier v2.0.0

**文件**：`apps/api/mentora/agent_runtime/prompts/templates/clarifier.json`

**变量**：`goal`, `level`, `pace`, `inquiry_history`

**核心规则**：
- 优先追问高信息增益问题（考试日期、指定教材、主题范围、基础表现、每日时间）
- 避免低价值问题（"还有什么补充"、学习动机、过于细节）
- 首轮 2-3 个问题，后续 1-2 个，最多 5-6 轮
- `guidance` 字段引用已知信息 + 解释追问动机（1-3 句）
- 严格 JSON 输出，无 Markdown 代码块标记

### 5.2 Planner v2.0.0

**文件**：`apps/api/mentora/agent_runtime/prompts/templates/planner.json`

**变量**：同 clarifier

**核心规则**：
- 4-5 阶段：基础梳理 → 重点突破 → 综合应用 → 检验巩固
- 根据用户基础调整占比（新手基础梳理 30-35%，学过一遍重点突破 35-40%）
- 根据推进方式调整任务量
- 任务描述具体可执行（不说"学习第三章"，说"理解 Cache 的三种映射方式"）
- 严格 JSON 输出

---

## 6. 前端服务层

**文件**：`apps/web/src/services/courseApi.ts`

封装 4 个 API 调用：

| 函数 | 端点 | 超时 |
|---|---|---|
| `createCourseSession(goal, signal?)` | `POST /sessions/` | 60s |
| `updateCourseSession(id, {level?, pace?, school?}, signal?)` | `PATCH /sessions/:id/update/` | 60s |
| `inquiryNext(id, answer?, signal?)` | `POST /sessions/:id/inquiry/` | 30s |
| `generatePlan(id, signal?)` | `POST /sessions/:id/plan/` | 90s |

特性：
- `AbortController` 组合信号：组件卸载时自动取消请求
- 超时自动 Abort
- 统一 `ApiError` 异常类（含 status 码）
- 非 JSON 响应体安全 fallback

---

## 7. 前后端状态对应

| 步骤 | 前端页面 | 后端 API | 状态写入 |
|---|---|---|---|
| 1. 描述目标 | `DescribeGoalPage` | `createCourseSession` | goal |
| 2. 补充信息 | `AddInfoPage` | `updateCourseSession` | level, pace, school |
| 3. 资料上传 | `MaterialUploadPage` | ☐ TODO | — |
| 4. 信息追问 | `AiInquiryPage` | `inquiryNext` | inquiry_history[] |
| 5. 确认方案 | `ConfirmPlanPage` | `generatePlan` | phases（不持久化） |

---

## 8. 文件变更清单

### 后端新建

| 文件 | 说明 |
|---|---|
| `apps/api/mentora/courses/models.py` | CourseCreationSession 模型 |
| `apps/api/mentora/courses/schemas.py` | Pydantic Schema |
| `apps/api/mentora/courses/serializers.py` | DRF Serializer |
| `apps/api/mentora/courses/views.py` | 5 个 HTTP 视图 |
| `apps/api/mentora/courses/__init__.py` | 包描述 |
| `apps/api/mentora/courses/migrations/0001_initial.py` | 建表迁移 |
| `apps/api/mentora/courses/migrations/0002_add_school.py` | 加 school 列迁移 |

### 后端修改

| 文件 | 变更 |
|---|---|
| `apps/api/config/urls.py` | 新增 5 条路由 |
| `apps/api/mentora/agent_runtime/views.py` | 注册 clarifier/planner Agent + 暴露单例函数 |
| `apps/api/mentora/agent_runtime/prompts/templates/clarifier.json` | v2.1.0 结构化追问（禁复合问题、每轮单问） |
| `apps/api/mentora/agent_runtime/prompts/templates/planner.json` | v2.0.0 结构化方案模板（新增 school 变量） |

### 前端新建

| 文件 | 说明 |
|---|---|
| `apps/web/src/services/courseApi.ts` | API 服务层封装（含 school 字段） |
| `apps/web/src/components/MentoraLoader.tsx` | 知识粒子汇聚加载动画组件 |
| `apps/web/src/styles.css` | 新增粒子动画 CSS（mentora-*） |

### 前端修改

| 文件 | 变更 |
|---|---|
| `apps/web/src/components/CourseCreationContext.tsx` | 新增 sessionId 状态 |
| `apps/web/src/pages/SetupPages.tsx` | DescribeGoalPage 调用 createCourseSession；AddInfoPage 调用 updateCourseSession |
| `apps/web/src/pages/SetupContinuationPages.tsx` | AiInquiryPage 替换 mock 为 inquiry API（loading/ready/error/answering 四状态）；ConfirmPlanPage 替换 mockPhases 为 plan API；子组件增加 disabled prop |

---

## 9. 启动与联调

> ⚠️ **第一步：数据库迁移（必须）** — 完整步骤见 [§2.2](#22-%EF%B8%8F-数据库迁移必须执行见下文)，摘要如下：

```powershell
cd apps/api
python manage.py makemigrations courses
python manage.py migrate
```

```powershell
# 2. 启动后端
python manage.py runserver 127.0.0.1:8000

# 3. 新终端启动前端
cd apps/web
pnpm dev
```

> 注意：`apps/api/.env` 需配置 `LLM_API_KEY`、`LLM_API_BASE_URL`、`LLM_MODEL`。

---

## 10. 已知限制 / TODO

- **资料系统（步骤 3）**：前端 `MaterialUploadPage` 已就绪，但后端上传 + AI 解读接口未实现
- **方案持久化**：当前 plan 生成后不存储，刷新即丢失
- **会话 TTL 清理**：暂未实现过期会话自动清理
- **认证**：当前所有端点 `csrf_exempt`，生产环境需补充 Token 认证
- **错误恢复**：LLM 调用失败时前端仅显示错误，未做重试机制
