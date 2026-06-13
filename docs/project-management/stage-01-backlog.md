# 第一阶段任务清单：从上传到处理结果

**阶段目标：** 用户在 Renderer 中选择一个文本 PDF，通过规定的上传边界提交，
并持续观察可恢复的解析进度，直到成功或失败。

**进入条件：** 团队角色已经确认，开发环境和仓库访问权限可用。

**退出条件：** 本文共同任务中的九项端到端检查全部通过。

**演示流程：**

```text
打开应用
  -> 选择 PDF
  -> 上传
  -> 开始处理
  -> 进度更新
  -> 显示成功或失败结果
```

## 关键依赖顺序

```text
P1-WH-01 状态模型
  -> P1-WH-02 API 契约
  -> P1-LBZ-01 Renderer 集成
  -> P1-LH-02 解析 Worker
  -> P1-WH-03 运行时事件
  -> P1-LBZ-02 进度恢复
  -> P1-TEAM-01 端到端验收
```

## LBZ 的任务

### P1-LBZ-01：上传用户流程

**负责人：** LBZ  
**评审人：** WH、LH  
**依赖：** P1-WH-02

交付：

- 基于现有 `apps/web` 壳层实现上传路由或面板；
- 类型化的上传初始化和完成请求；
- 文件元信息预览；
- 校验、加载、进度、成功和失败状态；
- 正式实现不直接依赖仅浏览器可用的本地文件路径。

验收：

- 选择非 PDF 时显示可操作的校验提示；
- 双击提交只产生一个可见上传任务；
- 请求失败后不刷新应用即可重试；
- 界面读取服务端状态，不使用定时器伪造进度。

测试：

- 界面状态迁移组件测试；
- API Client 契约 Fixture；
- 使用小型文本 PDF 的 E2E。

### P1-LBZ-02：处理状态与恢复

**负责人：** LBZ  
**评审人：** WH  
**依赖：** P1-WH-03

交付：

- 当前处理状态的 React Query Resource；
- 带序列检查的 SSE 事件应用；
- SSE 不可用或回放过期时通过 REST 恢复；
- 最终成功和失败摘要。

验收：

- 重复事件不会让进度倒退；
- Renderer 刷新后能够恢复最终状态；
- SSE 失败时仍提供刷新或重试操作；
- 支持的桌面宽度下无横向溢出。

## WH 的任务

### P1-WH-01：持久化处理状态

**负责人：** WH  
**评审人：** LH  
**依赖：** 无

交付：

- 最小 `Source`、`SourceVersion` 和 `ProcessingRun` 模型；
- 数据迁移、Repository 和应用服务；
- `pending`、`running`、`completed`、`failed`、`cancelled` 状态；
- 幂等键和 Attempt 记录；
- 统一错误字段。

验收：

- SourceVersion 创建后不可变；
- 使用同一个幂等键重复创建时返回同一个操作；
- 非法状态迁移失败且不产生部分更新；
- 能够识别需要恢复的失活运行任务。

测试：

- 模型约束测试；
- 服务状态迁移测试；
- 重复命令测试；
- 失败 Attempt 持久化测试。

### P1-WH-02：上传和处理 API

**负责人：** WH  
**评审人：** LBZ、LH  
**依赖：** P1-WH-01

交付：

- 上传初始化；
- 带 SHA-256 校验的上传完成接口；
- ProcessingRun 查询；
- 未完成任务的取消接口；
- 统一 API 错误和 Request ID。

验收：

- complete 不能引用其他用户的上传；
- SHA-256 不一致时禁止解析；
- complete 接口具有幂等性；
- 响应只暴露 ID 和状态，不暴露本地路径或对象存储秘密。

### P1-WH-03：Celery 调度和 Runtime Event

**负责人：** WH  
**评审人：** LBZ、LH  
**依赖：** P1-WH-01、P1-LH-01

交付：

- 上传校验完成后调度解析任务；
- Worker 租约、超时、有限重试和终态失败；
- 单调递增的 Runtime Event 序号；
- SSE 接口和 REST 状态恢复。

验收：

- Worker 失败不会永久停留在 `running`；
- 重试继续处理原 ProcessingRun；
- 重复调度不能生成重复成功产物；
- 根据 Last-Event-ID 恢复，或明确要求客户端读取 REST。

## LH 的任务

### P1-LH-01：ParsedBundle 和 EvidenceUnit 契约

**负责人：** LH  
**评审人：** WH、LWJ  
**依赖：** 无

交付带版本的 Schema，至少包含：

- SourceVersion 和 ParserVersion；
- 页码和阅读顺序；
- 元素类型和文本；
- 可用时的 PDF Bounding Box；
- 警告和提取质量字段；
- 内容 Hash 和 Artifact 引用。

验收：

- Schema 可以完成 JSON 往返序列化；
- 页码使用一种明确记录的规则；
- 坐标明确原点和单位；
- 非法元素无法通过校验。

### P1-LH-02：文本 PDF 解析 Worker

**负责人：** LH  
**评审人：** WH  
**依赖：** P1-WH-01、P1-LH-01

交付：

- PyMuPDF Parser Adapter；
- 三个可安全提交到仓库的测试 Fixture；
- ParsedBundle Artifact 持久化；
- 最小 EvidenceUnit 持久化；
- 分类后的解析错误。

验收：

- 普通文本 PDF 保留正确页码；
- 重试不会生成重复 Evidence；
- 加密、损坏和纯图片 PDF 返回不同错误码；
- ContentVersion 和 ParserVersion 共同构成缓存及幂等键。

### P1-LH-03：解析基准

**负责人：** LH  
**评审人：** WH、LBZ、LWJ  
**依赖：** P1-LH-02

交付报告：

- Fixture 特征；
- 提取页数和文本数量；
- 页码关联准确性；
- 警告和已知限制；
- 处理耗时和内存峰值观察。

验收：

- 使用一条文档化命令即可重跑；
- 报告区分产品暂不支持与解析器缺陷；
- 纯图片 PDF 明确延期，不能静默当作成功。

## LWJ 的任务

### P1-LWJ-01：模型网关契约

**负责人：** LWJ  
**评审人：** WH、LH  
**依赖：** 无

交付：

- 与模型厂商无关的任务请求和响应类型；
- 超时、是否可重试和 Fallback 决策；
- ModelRequest、ModelAttempt、Usage 和 PromptVersion 审计字段；
- Pydantic 结构化输出校验；
- 测试用确定性 Fake Provider。

验收：

- 领域服务不直接导入模型厂商 SDK；
- 非法结构化输出在进入领域逻辑前被拒绝；
- 同时记录请求模型和实际模型；
- 失败 Attempt 仍可审计；
- Fake Provider 不需要外部凭证。

### P1-LWJ-02：结构化输出校验测试集

**负责人：** LWJ  
**评审人：** WH  
**依赖：** P1-LWJ-01

提供以下 Fixture：

- 合法输出；
- 缺少必填字段；
- 字段类型错误；
- 未知 Evidence ID；
- 输出过大；
- Provider 超时；
- Fallback 成功和全部失败。

验收：

- 每种情况都有确定的预期决策；
- 非法 Payload 不会进入领域回调；
- 日志不包含秘密或完整私有资料正文。

## 共同任务

### P1-TEAM-01：端到端验收

**负责人：** WH  
**参与人：** LBZ、LH、LWJ  
**依赖：** 所有关键链路任务

从干净本地环境执行：

1. 启动 PostgreSQL、Redis 和 MinIO；
2. 启动 Django 和 Celery；
3. 启动 Renderer；
4. 上传约定的 PDF Fixture；
5. 观察至少一个非终态进度；
6. 观察处理完成并确认 Evidence 已保存；
7. 重复 complete 请求，确认没有重复 Artifact；
8. 第二次运行时停止 Worker，确认有限恢复或明确终态失败；
9. 刷新 Renderer，确认能够恢复最终状态。

只有九项全部通过并完成演示，第一阶段才能验收。

## 第一阶段风险

| 风险 | 负责人 | 处理方式 |
| --- | --- | --- |
| Electron Host 尚未实现 | WH | 先使用窄范围 Renderer 上传适配器，同时明确未来 Preload 契约 |
| 对象存储拖慢本地环境 | WH | 提供确定的 Docker Compose 配置和健康检查 |
| PDF Fixture 提取结果不稳定 | LH | 固定 Fixture 和 ParserVersion |
| SSE 占用过多集成时间 | WH | REST 状态查询必须作为恢复路径 |
| AI 工作不在可见关键链路 | LWJ | 交付后续阶段需要的模型网关和 Fake Provider |

## 第一阶段完成清单

- [ ] 所有关键链路验收项通过。
- [ ] `pnpm typecheck:web`、`pnpm test:web` 和 `pnpm build:web` 通过。
- [ ] API 测试和 Ruff 检查通过。
- [ ] 数据迁移可以在空数据库中成功执行。
- [ ] 干净 Checkout 可以按照说明启动。
- [ ] 日志中没有秘密、Token、签名 URL 或私有资料正文。
- [ ] 已记录演示结果和未解决风险。
