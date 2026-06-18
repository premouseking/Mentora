# Agent 运行时与模型网关架构设计

> 状态：Phase 2 已完成（流式 SSE 前后端联调验收通过）  
> 更新日期：2026-06-18  
> 原则：Agent 不拥有领域事实，只通过 Tool 调用领域服务；模型网关不判断业务，只负责路由与审计。

## 1. 概述

### 1.1 目标

构建 Mentora 后端 Agent 基础设施，使上层业务（问答、讲解、评估、推荐）通过统一的 Agent 协议与 LLM 交互，而非直接调用模型 SDK。

### 1.2 核心原则

1. **Agent 无状态**：每次 `run()` 接收完整上下文，返回结构化输出。Agent 代码不 import 领域模型（Course、Topic 等）。
2. **模型无关**：通过 `model_gateway` 统一路由，Provider 替换不影响 Agent 逻辑。
3. **工具隔离**：Agent 通过 `Tool.execute()` 间接调用领域服务，不直接写领域表。
4. **可审计**：每次模型调用、工具调用、Agent 运行均持久化记录。
5. **上下文预算**：硬性 Token 上限，优先级裁剪。

### 1.3 与现有架构的关系

```
                    ┌──────────────────────────┐
                    │      workflow_runtime     │
                    │   (显式持久状态机)         │
                    └──────────┬───────────────┘
                               │ OrchestratorTask
                               ▼
┌──────────────┐    ┌──────────────────────────┐    ┌──────────────┐
│ model_gateway│◄───│     agent_runtime        │───►│  领域服务     │
│              │    │                          │    │              │
│ • 路由       │    │ • Agent 调度             │    │ • retrieval  │
│ • Provider   │    │ • Tool 注册/执行          │    │ • learning   │
│ • 审计       │    │ • 提示词管理             │    │ • assessment │
│ • 结构化输出 │    │ • 上下文预算             │    │ • courses    │
└──────────────┘    └──────────────────────────┘    └──────────────┘
```

Agent Runtime 的定位：**业务逻辑与 LLM 之间的编排层**。workflow_runtime 通过 OrchestratorTask 驱动 Agent，Agent 通过 Tool 调用领域服务，通过 model_gateway 调用 LLM。

## 2. 模块架构

### 2.1 模块划分

```
apps/api/mentora/
├── model_gateway/          # [Phase 1 新建] 模型调用网关
│   ├── gateway.py          #   ModelGateway 主入口
│   ├── router.py           #   任务路由
│   ├── structured_output.py#   Pydantic 结构化输出校验
│   ├── models.py           #   ModelRequest, ModelAttempt
│   ├── schemas.py          #   ChatRequest, ChatResponse DTO
│   └── providers/
│       ├── base.py         #   BaseProvider 抽象
│       ├── fake.py         #   FakeProvider（测试）
│       └── openai.py       #   OpenAIProvider + 自建 HTTP 客户端
│
└── agent_runtime/          # [Phase 1 扩展] Agent 运行时
    ├── models.py           #   OrchestratorRun, SubAgentRun, ToolInvocation
    ├── services.py         #   RunManager
    ├── events.py           #   SSE 事件发射器
    ├── agents/
    │   ├── base.py         #   Agent 基类 + AgentInput/AgentOutput
    │   ├── orchestrator.py #   Orchestrator 调度器
    │   └── tutor.py        #   TutorAgent
    ├── tools/
    │   ├── base.py         #   ToolDefinition, Tool, ToolResult, ToolContext
    │   ├── registry.py     #   ToolRegistry
    │   └── knowledge_tools.py  #   retrieve_evidence 等
    ├── prompts/
    │   ├── manager.py      #   PromptManager
    │   ├── schema.py       #   PromptTemplate
    │   └── templates/
    │       └── tutor.yaml
    ├── context/
    │   ├── manager.py      #   ContextManager
    │   └── token_counter.py#   TokenCounter
    └── schemas/
        ├── task.py         #   OrchestratorTask, PipelineStep
        ├── output.py       #   AgentOutput, OrchestratorResult
        └── context.py      #   AgentContext, ToolContext
```

### 2.2 模块依赖

```
agent_runtime/agents  ──►  agent_runtime/tools  ──►  领域服务 (retrieval/learning/...)
        │                        │
        ▼                        ▼
agent_runtime/prompts    agent_runtime/context
        │                        │
        ▼                        ▼
   model_gateway ◄──────── agent_runtime/schemas
```

**原则**：
- `model_gateway` 不依赖 `agent_runtime` 或任何领域模块
- `agent_runtime/schemas` 不依赖 Django ORM，纯 Pydantic
- `agent_runtime/agents` 不 import 领域模型，通过 Tool 间接调用
- 模块间通过 Pydantic DTO 通信

### 2.3 Django 集成

`model_gateway` 需注册为 Django App：

```python
# model_gateway/apps.py
class ModelGatewayConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "mentora.model_gateway"
```

`settings.py` 追加：
```python
INSTALLED_APPS = [
    ...
    "mentora.model_gateway",   # [NEW]
    ...
]
```

## 3. Agent 体系

### 3.1 Agent 基类

```python
class Agent(ABC):
    """无状态 Agent 基类。

    约束：
    - 不持有领域模型引用
    - 不直接调用 LLM（通过 model_gateway）
    - run() 每次接收完整 AgentInput，返回 AgentOutput
    """

    role: str                           # 角色标识：tutor, planner, assessor, clarifier
    system_prompt_ref: str              # 提示词模板引用键，如 "tutor"
    tool_names: set[str] = field(default_factory=set)

    @abstractmethod
    async def run(self, input: AgentInput) -> AgentOutput: ...
```

### 3.2 AgentInput / AgentOutput

```python
class AgentInput(BaseModel):
    """单次 Agent 调用的完整输入。"""
    task_id: str                        # 关联的 OrchestratorRun ID
    user_message: str                   # 用户消息正文
    context: AgentContext               # 上下文（资料片段、历史消息等）
    tools: list[ToolDefinition]         # 本次可用的工具
    max_tool_rounds: int = 5            # 最大工具调用轮次

class AgentOutput(BaseModel):
    """Agent 运行的结构化输出。"""
    agent_role: str
    task_id: str
    final_message: str                  # 最终回复文本
    citations: list[Citation]           # 引用的证据
    tool_calls_made: list[ToolInvocationRecord]
    finish_reason: str                  # "completed" | "max_rounds" | "error"
    usage: TokenUsage
```

### 3.3 Agent 生命周期

```
AgentInput
  → ContextManager.build_messages() 组装消息列表
  → ModelGateway.chat(messages, tools) → LLM 响应
  → 检测 tool_calls:
      有 → ToolRegistry.execute(tool_name, args) → 结果回填 messages
            → 回到 ModelGateway.chat (下一轮)
      无 → 结构化输出校验 → AgentOutput
  → 最多 max_tool_rounds 轮
```

### 3.4 首批 Agent

| Agent | role | 用途 | 工具 |
|-------|------|------|------|
| TutorAgent | `tutor` | 基于资料的问答与讲解 | `retrieve_evidence` |

后续 Phase 扩展：
| PlannerAgent | `planner` | 学习计划生成 | `retrieve_evidence`, `query_topics` |
| AssessorAgent | `assessor` | 评估与题目生成 | `retrieve_evidence`, `generate_item` |
| ClarifierAgent | `clarifier` | 目标澄清与画像填充 | `query_profile_fields` |

## 4. Tool 机制

### 4.1 Tool 定义

```python
@dataclass
class ToolDefinition:
    """工具元数据，用于生成 Function Calling 的 tools 参数。"""
    name: str                           # 唯一标识，如 "retrieve_evidence"
    description: str                    # 人类可读描述，写入 system prompt
    parameters: dict                    # JSON Schema 格式
    agent_roles: set[str]               # 允许使用的 Agent 角色
    requires_confirmation: bool = False # 写操作需用户确认
    timeout_seconds: float = 30.0

class ToolResult(BaseModel):
    """工具执行结果。"""
    tool_name: str
    success: bool
    result: Any                         # 结构化结果
    error: str | None = None
    artifact_ref: str | None = None     # 结果过大时写入 Artifact
    duration_ms: float

class ToolContext(BaseModel):
    """工具执行的上下文，由 Orchestrator 注入。"""
    task_id: str
    agent_role: str
    run_id: str
```

### 4.2 ToolRegistry

```python
class ToolRegistry:
    """工具注册表。

    约定：
    - 按 Agent 角色过滤可用工具
    - 工具名称全局唯一
    - 注册时校验 parameters JSON Schema
    """

    def register(self, tool: Tool, definition: ToolDefinition) -> None: ...
    def get_for_agent(self, agent_role: str) -> list[ToolDefinition]: ...
    async def execute(self, name: str, args: dict, ctx: ToolContext) -> ToolResult: ...
```

### 4.3 首批工具

**retrieve_evidence**：
- 参数：`query` (string), `top_k` (int, default=5), `source_version_ids` (string[], optional)
- 执行：调用 `mentora.retrieval.search.search()`，返回证据片段 + 页码 + 坐标
- 归属于：`{"tutor", "planner", "assessor"}`
- 只读、无需确认

### 4.4 工具调用流程

```
Agent 推理 → LLM 返回 tool_calls
  → Orchestrator 解析 tool_calls
  → 校验权限（agent_role 是否在 ToolDefinition.agent_roles 中）
  → 如需确认 → 发射 tool.confirmation 事件 → 等待用户
  → ToolRegistry.execute(name, args, ctx)
  → ToolResult 序列化为 function role message
  → 回填到 messages 列表
  → 继续推理（下一轮）
```

### 4.5 大结果处理

工具结果 > 64KB 时：
1. 写入 `common.storage`（Artifact）
2. `ToolResult.artifact_ref` 指向对象存储键
3. 回填到 messages 的仅包含摘要文本 + `artifact_ref`

## 5. Orchestrator 调度器

### 5.1 调度模式

**单 Agent 模式**（Phase 1 默认）：
```
OrchestratorTask → 路由到单个 Agent → Agent.run() → AgentOutput
```

**Pipeline 模式**（Phase 2+）：
```
OrchestratorTask → Step 1 (ClarifierAgent) → Step 2 (PlannerAgent) → ... → OrchestratorResult
```

### 5.2 OrchestratorTask

```python
class OrchestratorTask(BaseModel):
    """来自 workflow_runtime 或 API 的编排任务。"""
    id: str
    mode: str                           # "single" | "pipeline"
    agent_role: str                     # 单 Agent 模式的目标 Agent
    user_message: str
    context_sources: list[str]          # 上下文资料版本 ID 列表
    history_messages: list[Message]     # 历史对话
    max_tool_rounds: int = 5
    pipeline_steps: list[PipelineStep] | None = None  # Pipeline 模式
    budget_config: BudgetConfig | None = None

class PipelineStep(BaseModel):
    """Pipeline 中的一个步骤。"""
    agent_role: str
    task_instruction: str
    input_from: str | None = None       # 从哪个步骤的输出取值
    output_key: str                     # 输出键名，供后续步骤引用
    max_tool_rounds: int = 5
```

### 5.3 执行流程

```
OrchestratorTask
  → 创建 OrchestratorRun (status=started)
  → 发射 agent.run.started 事件
  → ContextManager.build(task, history) 组装上下文
  → Agent.run(AgentInput)
    → [工具调用循环]
  → AgentOutput
  → 持久化 Run 记录 (status=completed)
  → 发射 agent.run.completed 事件
  → 返回 OrchestratorResult
```

## 6. 提示词管理

### 6.1 PromptTemplate

```python
@dataclass
class PromptTemplate:
    """JSON 提示词模板。"""
    name: str                           # 模板名称，如 "tutor"
    version: str                        # 语义版本，如 "1.0.0"
    system: str                         # 系统提示词正文（含 {{ var }} 变量）
    description: str = ""
    variables: list[str] = field(default_factory=list)
```

JSON 文件格式（`prompts/templates/tutor.json`）：
```json
{
  "name": "tutor",
  "version": "1.0.0",
  "description": "TutorAgent 系统提示词，基于资料回答学习问题",
  "variables": ["course_name", "source_titles"],
  "system": "你是 Mentora 学习助教，专门帮助学生基于学习资料回答问题。\n\n当前课程：{{ course_name }}\n可用资料：{{ source_titles }}\n\n规则：\n1. 只能基于提供的资料内容回答\n2. 每次引用必须标注来源页码\n3. 如果资料中找不到答案，诚实告知\n4. 用中文回答，保持简洁清晰"
}
```

> 注：Phase 1 实际使用 JSON 格式（环境无 PyYAML），支持 `{{ var }}` 和 `{{var}}` 两种占位符。

### 6.2 PromptManager

```python
class PromptManager:
    """提示词管理器。

    约定：
    - 初始化时加载所有 YAML 模板到内存缓存
    - 运行时只做变量渲染，不重新 IO
    - 模板版本号参与 PromptRevision 审计
    """

    def get(self, name: str) -> PromptTemplate: ...
    def render(self, name: str, variables: dict[str, str]) -> str: ...
    def list_templates(self) -> list[str]: ...
```

## 7. 上下文管理

### 7.1 上下文预算模型

```python
@dataclass
class BudgetConfig:
    """上下文窗口预算配置。"""
    max_tokens: int = 8000              # 硬上限
    system_reserved: int = 1500         # 系统提示词预留
    output_reserved: int = 1500         # 模型输出预留
    # 可用 = max_tokens - system_reserved - output_reserved

class BudgetPriority(Enum):
    """上下文裁剪优先级，P0 最高。"""
    P0_SYSTEM = 0      # 系统提示词
    P1_USER_QUERY = 1  # 当前用户消息
    P2_RECENT_MSGS = 2 # 最近 N 轮对话
    P3_EVIDENCE = 3    # 检索到的证据片段
    P4_OLDER_MSGS = 4  # 较早的对话历史

class ContextAllocation(BaseModel):
    """上下文分配结果。"""
    system_tokens: int
    user_query_tokens: int
    history_tokens: int
    evidence_tokens: int
    total_tokens: int
    within_budget: bool
```

### 7.2 ContextManager

```python
class ContextManager:
    """上下文管理器。

    约束：
    - 严格按照 BudgetPriority 裁剪
    - P4 最先被裁剪，P0 不可裁剪
    - 裁剪后消息列表保持时间顺序
    - 裁剪算法 O(n) 扫描，不引入外部依赖
    """

    def __init__(self, budget: BudgetConfig, counter: TokenCounter): ...

    def build_messages(
        self,
        system_prompt: str,
        user_message: str,
        history: list[Message],
        evidence_texts: list[str],
    ) -> tuple[list[Message], ContextAllocation]: ...

    def _truncate_evidence(
        self, texts: list[str], available: int
    ) -> tuple[list[str], int]: ...
```

### 7.3 TokenCounter

```python
class TokenCounter:
    """粗略 Token 计数器。

    约束：
    - 使用 len(text) // 4 近似估算
    - 不引入 tiktoken 依赖
    - 误差在 ±20% 内可接受，因为预算留有安全余量
    """

    def count(self, text: str) -> int:
        return max(1, len(text) // 4)

    def count_messages(self, messages: list[Message]) -> int:
        return sum(self.count(m.content or "") for m in messages)
```

## 8. 审计模型

### 8.1 agent_runtime 审计模型

```python
class OrchestratorRun(models.Model):
    """每次编排任务的运行记录。"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task_input = models.JSONField()             # OrchestratorTask 快照
    mode = models.CharField(max_length=16)      # single / pipeline
    status = models.CharField(max_length=16)    # started / running / completed / failed
    agent_role = models.CharField(max_length=32)
    context_allocation = models.JSONField(null=True)
    started_at = models.DateTimeField(null=True)
    completed_at = models.DateTimeField(null=True)
    total_duration_ms = models.IntegerField(null=True)
    total_tool_calls = models.IntegerField(default=0)
    error_code = models.CharField(max_length=64, blank=True, default="")
    error_message = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "agent_runtime_orchestrator_run"

class SubAgentRun(models.Model):
    """单个 Agent 的运行记录。"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    orchestrator_run = models.ForeignKey(
        OrchestratorRun, on_delete=models.CASCADE, related_name="sub_runs"
    )
    agent_role = models.CharField(max_length=32)
    agent_input = models.JSONField()            # AgentInput 快照
    agent_output = models.JSONField(null=True)  # AgentOutput 快照
    prompt_revision_id = models.CharField(max_length=64, blank=True, default="")
    status = models.CharField(max_length=16)
    duration_ms = models.IntegerField(null=True)
    tool_rounds = models.IntegerField(default=0)
    usage_json = models.JSONField(null=True)    # TokenUsage 快照
    started_at = models.DateTimeField(null=True)
    completed_at = models.DateTimeField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "agent_runtime_sub_agent_run"

class ToolInvocation(models.Model):
    """单次工具调用记录。"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sub_agent_run = models.ForeignKey(
        SubAgentRun, on_delete=models.CASCADE, related_name="tool_invocations"
    )
    tool_name = models.CharField(max_length=64)
    arguments = models.JSONField()
    result = models.JSONField(null=True)
    success = models.BooleanField(default=False)
    duration_ms = models.IntegerField(null=True)
    artifact_ref = models.CharField(max_length=512, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "agent_runtime_tool_invocation"

class PromptRevision(models.Model):
    """提示词版本记录，审计 Agent 运行时使用的是哪个版本。"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    template_name = models.CharField(max_length=64)
    version = models.CharField(max_length=16)
    content_sha256 = models.CharField(max_length=64)
    rendered_prompt = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "agent_runtime_prompt_revision"
        constraints = [
            models.UniqueConstraint(
                fields=["template_name", "version"],
                name="prompt_revision_name_version_unique",
            ),
        ]
```

### 8.2 model_gateway 审计模型

```python
class ModelRequest(models.Model):
    """每次网关调用的请求记录。"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task_type = models.CharField(max_length=32)  # tutor / planner / assessor
    provider_name = models.CharField(max_length=32)  # fake / openai
    messages_json = models.JSONField()            # 发送给模型的消息列表
    tools_json = models.JSONField(null=True)      # Function Calling 定义
    output_schema_name = models.CharField(max_length=64, blank=True, default="")
    structured_output = models.BooleanField(default=False)
    sub_agent_run_id = models.CharField(max_length=64, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "model_gateway_request"

class ModelAttempt(models.Model):
    """单次实际网络调用记录（含重试）。"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request = models.ForeignKey(
        ModelRequest, on_delete=models.CASCADE, related_name="attempts"
    )
    attempt_number = models.PositiveIntegerField(default=1)
    provider_name = models.CharField(max_length=32)
    model_name = models.CharField(max_length=64)
    response_json = models.JSONField(null=True)   # 原始响应 (tool_calls / content)
    usage_json = models.JSONField(null=True)      # {prompt_tokens, completion_tokens}
    latency_ms = models.IntegerField(null=True)
    success = models.BooleanField(default=False)
    error_code = models.CharField(max_length=64, blank=True, default="")
    error_message = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "model_gateway_attempt"
        indexes = [
            models.Index(fields=["request", "attempt_number"]),
        ]
```

## 9. model_gateway 设计

### 9.1 主入口

```python
class ModelGateway:
    """模型调用网关。

    约定：
    - 不直接暴露 Provider SDK 给领域模块
    - task_type 用于路由和审计，不影响请求内容
    - structured_output_schema 传入 Pydantic 模型类，框架负责校验
    """

    def __init__(self, router: TaskRouter, out_validator: StructuredOutputValidator): ...

    async def chat(
        self,
        task_type: str,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        structured_output_schema: type[BaseModel] | None = None,
    ) -> ChatResponse:
        """统一模型调用入口。

        流程：
        1. 创建 ModelRequest 审计记录
        2. 通过 TaskRouter 路由到 Provider
        3. Provider.chat() 返回原始响应
        4. 创建 ModelAttempt 审计记录
        5. 如有 structured_output_schema → 校验
        6. 返回 ChatResponse（含 tool_calls 或 text + parsed_output）
        """
```

### 9.2 Provider 抽象

```python
class BaseProvider(ABC):
    """模型提供方抽象基类。"""
    name: str
    default_model: str

    @abstractmethod
    async def chat(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
    ) -> ProviderResponse: ...
```

**FakeProvider**：返回预定义响应，供 Agent 逻辑测试。支持：
- 纯文本响应（`text_responses` 队列）
- 工具调用响应（`tool_call_scenarios` 列表，每个场景是一组 tool_calls）
- 错误模拟（`inject_error` 在指定轮次抛异常）

### 9.3 结构化输出

```python
class StructuredOutputValidator:
    """基于 Pydantic 的结构化输出校验器。"""

    def validate(
        self, text: str, schema: type[BaseModel]
    ) -> tuple[BaseModel | None, list[str]]:
        """尝试从文本中解析 JSON 并校验。

        - 成功：返回 (实例, [])
        - 失败：返回 (None, [错误列表])
        """
```

## 10. SSE 事件

### 10.1 事件类型

| 事件名 | 触发时机 | payload 关键字段 |
|--------|---------|-----------------|
| `agent.run.started` | Orchestrator 接受任务 | `task_id`, `agent_role`, `mode` |
| `agent.thinking` | Agent 开始新一轮模型调用 | `task_id`, `round_number` |
| `agent.tool.call` | 工具调用开始 | `task_id`, `tool_name`, `arguments` |
| `agent.tool.result` | 工具调用完成 | `task_id`, `tool_name`, `success`, `preview` |
| `agent.response` | 模型返回文本（非最终） | `task_id`, `text_chunk` |
| `agent.run.completed` | 运行完成 | `task_id`, `AgentOutput` 摘要 |
| `agent.run.error` | 运行失败 | `task_id`, `error_code`, `error_message` |

### 10.2 EventEmitter

```python
class EventEmitter:
    """SSE 事件发射器。

    约定：
    - 所有事件通过 Celery task 内的回调发射
    - 不持有连接状态（无状态发射）
    - 事件历史由 runtime_events 模块持久化
    """

    def emit(self, event_type: str, task_id: str, payload: dict) -> None: ...
```

## 11. Celery 集成

### 11.1 任务队列

```python
# agent_runtime/tasks.py

@shared_task(name="mentora.agent_runtime.tasks.run_agent")
def run_agent(task_json: str) -> dict:
    """Agent 运行 Celery 桥接。

    约定：
    - 输入为 OrchestratorTask 的 JSON 序列化
    - 输出为 OrchestratorResult 的 JSON 序列化
    - 内部实例化 Orchestrator 并执行
    """
    task = OrchestratorTask.model_validate_json(task_json)
    orchestrator = Orchestrator(...)
    result = asyncio.run(orchestrator.run(task))
    return result.model_dump(mode="json")
```

### 11.2 队列路由（已有）

```python
CELERY_TASK_ROUTES = {
    ...
    "mentora.agent_runtime.tasks.*": {"queue": "agent"},
}
```

## 12. 与现有模块的集成点

### 12.1 retrieval

```
agent_runtime/tools/knowledge_tools.py
  → mentora.retrieval.search.search(query, top_k)
  → SearchResultSet → ToolResult(result=search_results)
```

检索结果以 `SearchResult.to_dict()` 格式注入 Agent 上下文，包含 `evidence_id`, `content_preview`, `page_number`。

### 12.2 learning

```
agent_runtime/tools/learning_tools.py (Phase 2+)
  → mentora.learning.services.* → PlanRevision, Task
```

### 12.3 assessment

```
agent_runtime/tools/assessment_tools.py (Phase 2+)
  → mentora.assessment.services.* → AssessmentItem, Attempt
```

### 12.4 courses

```
agent_runtime/tools/course_tools.py (Phase 2+)
  → mentora.courses.* → CourseProfile, Scope
```

### 12.5 workflow_runtime

```
workflow_runtime 通过 OrchestratorTask 驱动 Agent
  → Celery task: run_agent(task_json)
  → Agent.output 回写 workflow 状态
```

### 12.6 common.storage

大结果 Artifact 写入：
```
ToolResult.result > 64KB
  → common.storage.ObjectStorageService.put_object(key, data)
  → ToolResult.artifact_ref = key
```

## 13. Phase 1 实施范围

### 13.1 文件清单

| 文件 | 行数估算 | 说明 |
|------|---------|------|
| `docs/architecture/agent-runtime-design.md` | ~400 | 本文档 |
| `model_gateway/__init__.py` | ~15 | 模块 docstring |
| `model_gateway/apps.py` | ~10 | AppConfig |
| `model_gateway/schemas.py` | ~80 | Message, ChatRequest, ChatResponse, ToolCall, ProviderResponse |
| `model_gateway/gateway.py` | ~80 | ModelGateway.chat() |
| `model_gateway/router.py` | ~40 | TaskRouter |
| `model_gateway/structured_output.py` | ~50 | StructuredOutputValidator |
| `model_gateway/models.py` | ~50 | ModelRequest, ModelAttempt |
| `model_gateway/providers/__init__.py` | ~5 | - |
| `model_gateway/providers/base.py` | ~30 | BaseProvider 抽象 |
| `model_gateway/providers/fake.py` | ~80 | FakeProvider |
| `agent_runtime/schemas/task.py` | ~60 | OrchestratorTask, PipelineStep, BudgetConfig |
| `agent_runtime/schemas/output.py` | ~60 | AgentOutput, OrchestratorResult, Citation, TokenUsage |
| `agent_runtime/schemas/context.py` | ~40 | AgentContext, ToolContext, ContextAllocation |
| `agent_runtime/schemas/__init__.py` | ~10 | 聚合导出 |
| `agent_runtime/prompts/schema.py` | ~25 | PromptTemplate |
| `agent_runtime/prompts/manager.py` | ~60 | PromptManager |
| `agent_runtime/prompts/templates/tutor.yaml` | ~20 | Tutor 提示词模板 |
| `agent_runtime/prompts/__init__.py` | ~5 | - |
| `agent_runtime/context/token_counter.py` | ~30 | TokenCounter |
| `agent_runtime/context/manager.py` | ~100 | ContextManager |
| `agent_runtime/context/__init__.py` | ~5 | - |
| `agent_runtime/tools/base.py` | ~70 | ToolDefinition, Tool, ToolResult, ToolContext |
| `agent_runtime/tools/registry.py` | ~60 | ToolRegistry |
| `agent_runtime/tools/knowledge_tools.py` | ~50 | RetrieveEvidenceTool |
| `agent_runtime/tools/__init__.py` | ~5 | - |
| `agent_runtime/agents/base.py` | ~60 | Agent 抽象基类 + AgentInput/AgentOutput |
| `agent_runtime/agents/orchestrator.py` | ~150 | Orchestrator 调度器 |
| `agent_runtime/agents/tutor.py` | ~60 | TutorAgent |
| `agent_runtime/agents/__init__.py` | ~5 | - |
| `agent_runtime/models.py` | ~100 | 审计模型 |
| `agent_runtime/services.py` | ~60 | RunManager |
| `agent_runtime/events.py` | ~50 | EventEmitter |
| `agent_runtime/tasks.py` | ~30 | run_agent Celery task（扩展） |
| `agent_runtime/__init__.py` | ~10 | 更新 docstring |
| **总计** | **~1600** | |

### 13.2 不在此 Phase

- AssessorAgent / CoachAgent（Phase 3）
- learning_tools / assessment_tools / course_tools（Phase 2-3）
- 工具结果流式回填（Phase 3）
- Usage Ledger 成本结算（Phase 3）

## 14. 四阶段实施路线

### Phase 1（已完成）：Core Skeleton

- [x] 架构设计文档
- [x] model_gateway 模块（BaseProvider + FakeProvider + 路由 + 审计）
- [x] agent_runtime Schema 层
- [x] agent_runtime 基础设施（PromptManager + ContextManager + TokenCounter + SSE）
- [x] Agent 核心（Agent 基类 + Tool 注册表 + KnowledgeTools + TutorAgent + Orchestrator）
- [x] 审计模型（OrchestratorRun, SubAgentRun, ToolInvocation, PromptRevision）
- [x] 端到端集成测试（FakeProvider 驱动的工具调用循环，25/25 通过）

### Phase 2（已完成）：Real Model + Pipeline

- [x] OpenAIProvider（兼容 Function Calling，非流式 + 流式双模式）
- [x] 自建异步 HTTP 客户端（stdlib asyncio + urllib，零依赖）
- [x] Pipeline 模式完整实现（step 事件 + 错误处理）
- [x] PlannerAgent + ClarifierAgent
- [x] SSE 流式输出（ModelGateway.chat_stream() + TutorAgent.run_stream()）
- [x] FakeProvider 流式模式

### Phase 3：Learning + Assessment Agents

- AssessorAgent + 题目生成 Tool
- 学习事件 → 掌握度汇总 Tool
- 评估结果回写 learning 模块

### Phase 4：Production

- Usage Ledger 成本结算
- 模型 Fallback + 重试策略
- 性能优化（Prompt 缓存、并行 Tool 调用）
- 监控与告警

## 附录 A：与 LangChain/LangGraph 的对比

Mentora 自建 Agent Runtime 而非使用 LangChain/LangGraph 的原因：

| 维度 | LangChain | Mentora Agent Runtime |
|------|-----------|----------------------|
| 学习成本 | 框架抽象层多，调试困难 | 直线代码，显式控制流 |
| 依赖 | 重，版本兼容问题频发 | 零外部 Agent 框架依赖 |
| 数据库集成 | 需自行对接 | Django ORM 原生 |
| 审计 | 需自行实现 | 内置审计模型 |
| 领域建模 | 通用 | 专为教学场景设计 |
| 上下文预算 | 无内置支持 | 内置优先级裁剪 |

## 附录 B：关键设计决策记录

| 决策 | 理由 | 日期 |
|------|------|------|
| Agent 无状态 | 避免 Agent 代码耦合数据库，便于测试 | 2026-06-17 |
| 粗 Token 计数 | 避免引入 tiktoken 依赖，误差在可接受范围 | 2026-06-17 |
| 自建 Agent 框架 | M0 不引入 LangGraph，保持依赖最小化 | 2026-06-17 |
| model_gateway 独立模块 | 与 agent_runtime 解耦，可独立测试和替换 Provider | 2026-06-17 |
| JSON 提示词模板 | 人可读、易 diff、无需 PyYAML 依赖 | 2026-06-17 |
| Pydantic 结构化输出校验 | 利用现有 Pydantic 生态，类型安全 | 2026-06-17 |
| 自建 HTTP 客户端（stdlib） | 环境无任何 HTTP 库，asyncio + urllib 完全可行 | 2026-06-17 |
| asyncio.open_connection 做 SSE | 避免 asyncio.to_thread 阻塞流式读取 | 2026-06-17 |
| chat_stream() 为可选方法 | 不破坏 FakeProvider 兼容性 | 2026-06-17 |

---

> @see docs/architecture/module-boundaries.md  
> @see docs/architecture/technical-solution.md  
> @see docs/architecture/end-to-end-implementation-plan.md
