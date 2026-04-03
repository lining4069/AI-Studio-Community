CREATE EXTENSION IF NOT EXISTS vector;

-- 稠密表
CREATE TABLE pg_chunks (
    id TEXT PRIMARY KEY,
    document_id TEXT,
    kb_id TEXT,
    file_id TEXT,
    chunk_index INT,
    content TEXT,
    embedding vector(1024),
    metadata JSONB
);

CREATE INDEX idx_pg_chunks_embedding
ON pg_chunks
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- 稀疏表
CREATE TABLE pg_sparse_chunks (
    id TEXT PRIMARY KEY,
    document_id TEXT,
    kb_id TEXT,
    file_id TEXT,
    chunk_index INT,
    content TEXT,
    tokens TEXT,
    metadata JSONB,
    tsv tsvector GENERATED ALWAYS AS (
        to_tsvector('simple', tokens)
    ) STORED
);

CREATE INDEX idx_pg_sparse_tsv
ON pg_sparse_chunks USING GIN (tsv);