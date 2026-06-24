# Agent 模块与领域服务开发记录

- 日期：2026-06-23
- 关联架构：`docs/architecture/agent-runtime-design.md`
- 关联计划：`docs/architecture/end-to-end-implementation-plan.md`

## Phase 3：Learning + Assessment Agents

### 3A：learning 模块 + 学习计划工具

#### 3A-1：ORM 模型

创建 5 表学习计划数据模型：

| 表 | 说明 |
|---|---|
| `learning_plan` | 1门课1个计划，关联 active_revision_id |
| `learning_plan_revision` | 版本化计划草稿，存储 plan_snapshot_json |
| `learning_plan_phase` | 学习阶段（如"基础篇"） |
| `learning_plan_unit` | 学习单元（如"存储系统"），含 prerequisite_unit_ids |
| `learning_plan_task_template` | 任务模板（lecture/exercise/project/review） |

文件：`mentora/learning/models.py`（新建）、`migrations/0001_initial.py`

#### 3A-2：领域服务

`mentora/learning/services/__init__.py`（新建）：

| 函数 | 说明 |
|---|---|
| `create_plan_revision()` | 全事务创建 Plan→Revision→Phase→Unit→TaskTemplate |
| `activate_revision()` | 原子切换 active_revision_id |
| `get_active_plan()` | 返回完整计划树（phases→units→tasks） |
| `get_progress()` | 查询 AssessmentSession 填真实完成状态 |

#### 3A-3/4：学习计划工具

| 工具 | 说明 |
|---|---|
| `CreateLearningPlanTool` | 从 placeholder 写实，调 `create_plan_revision()` |
| `GetLearningProgressTool` | 新建，返回课程进度摘要 |

`agent_runtime/tools/learning_tools.py` — 更新
`agent_runtime/runtime.py` — ToolDefinition + 注册

---

### 3B：assessment 模块 + AssessorAgent

#### 3B-1：ORM 模型

创建 3 表首期最小可用：

| 表 | 说明 |
|---|---|
| `assessment_item` | 题目定义（类型/难度/题干/选项/答案/解析/来源证据） |
| `assessment_session` | 测验会话（题目数/答对数/得分/开始-完成时间） |
| `assessment_attempt` | 单题作答（回答/对错/分数/耗时） |

Phase 4 扩展：ItemProvenance、Blueprint、MasteryEvidence。

文件：`mentora/assessment/models.py`（新建）、`migrations/0001_initial.py`

#### 3B-2：领域服务

`mentora/assessment/services/__init__.py`（新建）：

| 函数 | 说明 |
|---|---|
| `create_item()` | 创建题目 |
| `create_session()` | 创建测验会话 + 关联题目 |
| `submit_attempt()` | 记录作答 + 自动判分（对比 correct_answer） |
| `complete_session()` | 汇总 correct_count / score_pct |
| `get_session_result()` | 完整结果（每题答题详情） |

#### 3B-3：assessment 工具

| 工具 | 说明 |
|---|---|
| `GenerateItemTool` | 从 placeholder 写实，调 `create_item()` + `create_session()` |
| `SubmitAnswerTool` | 新建，记录作答并自动判分 |

`agent_runtime/tools/assessment_tools.py` — 更新

#### 3B-4：AssessorAgent

`agent_runtime/agents/assessor.py`（新建）— 评估与题目生成 Agent：
- role: assessor
- tools: generate_item, submit_answer, retrieve_evidence
- 提示词模板: `prompts/templates/assessor.json`

#### 3B-5：QueryCourseScopeTool 注册

补注册到 `runtime.py`。

---

### 3C：跨模块集成

#### 评估回写 learning

`learning/services/get_progress()` 查询 `AssessmentSession` 判断 unit 完成状态：
- `session.score_pct >= 60` → unit.completed=true
- `unit_score = session.score_pct`

---

### 工具与 Agent 最终矩阵

```
ToolRegistry (6 tools):
  query_course_scope      → courses
  retrieve_evidence       → knowledge
  create_learning_plan    → learning
  get_learning_progress   → learning
  generate_item           → assessment
  submit_answer           → assessment

Agent 矩阵 (4 agents):
  tutor      → query_course_scope, retrieve_evidence, get_learning_progress
  clarifier  → (纯文本交互)
  planner    → query_course_scope, retrieve_evidence, create_learning_plan, get_learning_progress
  assessor   → query_course_scope, retrieve_evidence, generate_item, submit_answer
```

### 文件清单

| 文件 | 说明 |
|---|---|
| `mentora/learning/models.py`（新建） | 5 ORM model |
| `mentora/learning/services/__init__.py`（新建） | 4 service 函数 |
| `mentora/assessment/models.py`（新建） | 3 ORM model |
| `mentora/assessment/services/__init__.py`（新建） | 5 service 函数 |
| `mentora/agent_runtime/agents/assessor.py`（新建） | AssessorAgent |
| `mentora/agent_runtime/prompts/templates/assessor.json`（新建） | assessor 提示词 |
| `mentora/agent_runtime/tools/learning_tools.py` | CreateLearningPlan + GetLearningProgress 写实 |
| `mentora/agent_runtime/tools/assessment_tools.py` | GenerateItem + SubmitAnswer 写实 |
| `mentora/agent_runtime/tools/course_tools.py`（新建） | QueryCourseScope |
| `mentora/agent_runtime/runtime.py` | 6 tool definitions + 4 agent 注册 |

---

## Phase 4：生产化

### 4A：Usage Ledger

`mentora/model_gateway/ledger.py`（新建）：

| 函数 | 说明 |
|---|---|
| `aggregate_usage(days, task_type, provider)` | 按维度汇总 Token 用量 + 费用 + 成功率 + 延迟 |
| `_estimate_cost()` | 7 个内置模型定价表 |

管理命令：`manage.py usage_report --days 30`

### 4B：Fallback 策略

| 文件 | 改动 |
|---|---|
| `model_gateway/router.py` | 新增 `mark_success()` / `mark_failure()` + `_is_healthy()` + cooldown 自动恢复 |
| `model_gateway/gateway.py` | 成功/失败后调 router 上报健康状态 |
| `model_gateway/exceptions.py` | 新增 `NoHealthyProviderError` |

阈值：连续失败 3 次 → 标记不健康 → 60s cooldown → 自动恢复。

### 4C：Prompt 缓存

`mentora/agent_runtime/prompts/manager.py` — `render()` 方法新增渲染结果缓存：
- 缓存 key = `{template_name}:{include_base}:{variables_kv}`
- tool 调用循环中同一模板 + 相同变量只渲染一次
- `reload()` 清空缓存
