-- Mentora PostgreSQL 扩展初始化
-- 在 Docker 容器首次启动时自动执行（docker-compose 挂载到 /docker-entrypoint-initdb.d/）

-- pgvector: 向量存储和相似度检索
CREATE EXTENSION IF NOT EXISTS vector;

-- pg_trgm: 三元组模糊匹配（检索模糊层兜底、GIN 索引加速 LIKE/ILIKE）
CREATE EXTENSION IF NOT EXISTS pg_trgm;
