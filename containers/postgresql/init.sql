-- =========================
-- 扩展
-- =========================
CREATE EXTENSION IF NOT EXISTS vector;

-- =========================
-- 稠密向量表（pgvector）
-- =========================
CREATE TABLE pg_chunks (
    id TEXT PRIMARY KEY,
    document_id TEXT,
    kb_id TEXT,
    file_id TEXT,
    content TEXT,
    embedding vector(1536),  
    metadata JSONB,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 向量索引（IVFFLAT）
CREATE INDEX idx_pg_chunks_embedding
ON pg_chunks
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- metadata 索引（重要）
CREATE INDEX idx_pg_chunks_metadata
ON pg_chunks USING GIN (metadata);


-- =========================
-- 稀疏表（BM25）
-- =========================
CREATE TABLE pg_sparse_chunks (
    id TEXT PRIMARY KEY,
    document_id TEXT,
    kb_id TEXT,
    file_id TEXT,
    content TEXT,
    tokens TEXT,
    metadata JSONB,

    tsv tsvector GENERATED ALWAYS AS (
        to_tsvector('simple', tokens)
    ) STORED,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- BM25 索引
CREATE INDEX idx_pg_sparse_tsv
ON pg_sparse_chunks USING GIN (tsv);

-- metadata 索引（重要）
CREATE INDEX idx_pg_sparse_metadata
ON pg_sparse_chunks USING GIN (metadata);


-- =========================
-- 优化（关键）
-- =========================

-- 更新统计信息（必须）
ANALYZE pg_chunks;
ANALYZE pg_sparse_chunks;

-- ivfflat 查询精度（建议）
-- 注意：这个是 session 级参数，应用层也可以设置
SET ivfflat.probes = 10;