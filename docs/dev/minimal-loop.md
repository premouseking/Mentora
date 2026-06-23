# 最小业务闭环

当前阶段的最小闭环范围（M0），避免一次性铺开全部领域表。

## 数据链路

```text
上传 fixture PDF
  -> UploadSession（对象存储键）
  -> Source + SourceVersion（不可变版本）
  -> ProcessingRun（解析运行）
  -> ParsedBundle（对象存储 artifact_ref）
  -> EvidenceUnit ORM（检索事实源）
  -> GET /api/library/sources/ 可查询
```

## 已实现

| 环节 | 模型 / 端点 | 状态 |
| --- | --- | --- |
| 资料身份 | `Source` | 已实现 |
| 资料版本 | `SourceVersion` | 已实现 |
| 上传会话 | `UploadSession` | 已实现 |
| 处理运行 | `ProcessingRun` | 已实现 |
| 对象存储 | MinIO / filesystem / S3 | 已实现 |
| 解析入库 | `knowledge.services.processing` | 已实现 |
| 证据持久化 | `retrieval.EvidenceUnit` | 已实现 |
| 上传 API | `POST /api/uploads/`、`POST /api/uploads/complete/` | 已实现 |
| 资源库列表 | `GET /api/library/sources/` | 已实现 |
| 开发种子 | `python manage.py seed_dev` | 已实现 |
| 上传 smoke | `python manage.py smoke_upload_resource` | 已实现 |

## 暂未纳入（后续迭代）

| 环节 | 说明 |
| --- | --- |
| 课程知识作用域 | `CourseKnowledgeScopeRevision`、`CourseScopeBinding` |
| 学习计划 / 任务 | `learning` 领域模型 |
| 评估 / 掌握度 | `assessment` 领域模型 |
| 检索投影全量 | `ChunkProjection` 向量、全文检索投影写入 |
| Runtime Event / SSE | 处理进度推送 |
| 认证与用户 FK | `owner_id` 当前为字符串占位 |

## 临时兼容

- `retrieval.*.source_version_id` 仍为 `CharField`，存 SourceVersion UUID 字符串；后续迁移为 FK。
- `owner_id` 使用 `dev-user` 占位，待认证模块交付后关联用户表。

## 验证命令

```powershell
pnpm infra:up
pnpm api:migrate
pnpm api:seed
pnpm api:smoke:upload
```
