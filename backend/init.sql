-- 创建数据库（如果不存在）
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'sll_chat') THEN
        CREATE DATABASE sll_chat;
    END IF;
END
$$;

-- 创建用户表
DROP TABLE IF EXISTS users CASCADE;
CREATE TABLE users (
    user_id BIGSERIAL PRIMARY KEY,
    username VARCHAR(64) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash CHAR(60) NOT NULL,  -- Bcrypt加密
    created_at TIMESTAMP DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE
);

-- 创建对话表
DROP TABLE IF EXISTS generation_records CASCADE;
CREATE TABLE generation_records (
    record_id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    generated_text TEXT NOT NULL,     -- 直接存储用户生成的长文本
    status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT NOW()
);
-- 索引优化
CREATE INDEX idx_records_user ON generation_records(user_id, created_at);
CREATE INDEX ON generation_records USING hnsw (embedding vector_cosine_ops);  -- 向量索引

-- 创建url信息表
DROP TABLE IF EXISTS research CASCADE;
CREATE TABLE research (
    research_id BIGSERIAL PRIMARY KEY,
    title VARCHAR(512) NOT NULL,  -- 外部资源的标题
    lnk VARCHAR(512) UNIQUE NOT NULL,  -- 外部资源的唯一URL
    snippet TEXT NOT NULL,                  -- 内容的简要描述
    created_at TIMESTAMP DEFAULT NOW()
);
-- 加速URL搜索
CREATE INDEX idx_research_url ON research USING GIN(lnk gin_trgm_ops);

-- 关联表 (generation_research）
DROP TABLE IF EXISTS generation_research CASCADE;
CREATE TABLE generation_research (
    generation_record_id BIGINT REFERENCES generation_records(record_id) ON DELETE CASCADE,
    research_id BIGINT REFERENCES research(research_id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (generation_record_id, research_id)  -- 联合主键
);

CREATE EXTENSION IF NOT EXISTS vector CASCADE;
CREATE EXTENSION IF NOT EXISTS vectorscale CASCADE;
CREATE EXTENSION IF NOT EXISTS ai CASCADE;

SELECT ai.create_vectorizer(
    'public.research'::regclass,
    embedding=>ai.embedding_ollama('nomic-embed-text', 768),
    chunking=>ai.chunking_recursive_character_text_splitter('snippet'),
    formatting=>ai.formatting_python_template('Web title: $title URL: $lnk web chunk: $chunk')
);

DROP FUNCTION similarity_search(text,integer);
CREATE OR REPLACE FUNCTION similarity_search(
    query_text TEXT,
    top_n INTEGER DEFAULT 5
)
RETURNS TABLE (
    title VARCHAR(512),
    lnk VARCHAR(512),
    snippet TEXT
) AS $$BEGIN
    RETURN QUERY
    SELECT re.title, re.lnk, re.snippet
    FROM research_embedding AS re
    ORDER BY embedding <=> ai.ollama_embed('nomic-embed-text', query_text)
    LIMIT
        top_n;
END;$$ LANGUAGE plpgsql;
