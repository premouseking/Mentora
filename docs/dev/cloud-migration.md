# 云端迁移边界

本地开发与云端部署**同构**：只替换基础设施实现，不替换业务数据模型。

## 同构映射

| 本地 | 云端 |
| --- | --- |
| Docker PostgreSQL + pgvector | 托管 PostgreSQL |
| MinIO | COS / S3 |
| Redis | 托管 Redis |
| Celery worker | 云端 worker / 队列 |
| `.env` 环境变量 | 部署平台 Secret / ConfigMap |

## 数据库约束

- 业务表结构由 Django migrations 管理，禁止手工改表
- `SourceVersion.object_key` / `artifact_ref` 仅存对象存储逻辑键
- 禁止在数据库中保存本地绝对路径
- `pgvector`、`pg_trgm` 为正式依赖，不使用 SQLite 替代

## 对象存储约束

- 通过 `mentora.common.storage.ObjectStorageService` 读写
- MinIO 仅为 S3 兼容本地实现
- 迁移到 COS/S3 时：迁移对象文件 + 更新 `OBJECT_STORAGE_*` 环境变量

## 任务约束

- Celery 任务参数传 `source_version_id` 等稳定 ID
- Worker 从对象存储读取原文件，不从数据库路径字段读取

## 配置清单（云端需设置）

```text
POSTGRES_*
REDIS_URL
OBJECT_STORAGE_ENDPOINT
OBJECT_STORAGE_BUCKET
OBJECT_STORAGE_ACCESS_KEY
OBJECT_STORAGE_SECRET_KEY
OBJECT_STORAGE_REGION
OBJECT_STORAGE_BACKEND=s3
DJANGO_SECRET_KEY
DJANGO_DEBUG=false
```

## 上线前检查

运行 smoke 与管理命令验证：

```powershell
python manage.py smoke_upload_resource --fixture normal.pdf
python manage.py smoke_upload_resource --fixture normal.pdf --via-http
```

确认输出中 `objectKey` 为 `uploads/...` 格式，不含本地路径。
