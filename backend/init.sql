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

-- 创建生成记录表
DROP TABLE IF EXISTS generation_records CASCADE;
CREATE TABLE generation_records (
    uuid UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    title VARCHAR(255),              -- 生成记录的标题
    status VARCHAR(20) NOT NULL CHECK (status IN ('chat', 'longtext')) DEFAULT 'chat',
    created_at TIMESTAMP DEFAULT NOW()
);
-- 索引优化
CREATE INDEX idx_records_user ON generation_records(user_id, created_at);
CREATE INDEX idx_records_uuid ON generation_records(uuid);

-- 创建聊天历史表
DROP TABLE IF EXISTS chat_history CASCADE;
CREATE TABLE chat_history (
    message_id BIGSERIAL PRIMARY KEY,
    record_uuid UUID NOT NULL REFERENCES generation_records(uuid) ON DELETE CASCADE,
    message_type VARCHAR(10) NOT NULL CHECK (message_type IN ('user', 'assistant')), -- 消息类型：用户输入或AI响应
    content TEXT NOT NULL,           -- 消息内容
    sequence_number INT NOT NULL,    -- 消息顺序号
    created_at TIMESTAMP DEFAULT NOW()
);
-- 索引优化
CREATE INDEX idx_chat_history_record ON chat_history(record_uuid, sequence_number);
CREATE INDEX idx_chat_history_type ON chat_history(record_uuid, message_type);

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

-- 关联表 (chat_history）
DROP TABLE IF EXISTS chat_history CASCADE;


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

-- Insert a sample user
INSERT INTO users (username, email, password_hash)
VALUES ('john_doe', 'john.doe@example.com', '$2b$12$KIXc5e2H80itp6S8iLZzJ.ZX1gY4f8Le6U5N2tkhNVUH0bmaFvL5G');

-- Insert a sample generation record
INSERT INTO generation_records (user_id, title, status)
VALUES ('123e4567-e89b-12d3-a456-426614174000', 'Sample Chat Record', 'chat');

-- Insert sample chat history
INSERT INTO chat_history (record_uuid, message_type, content, sequence_number)
VALUES
('9933bfba-c321-4c9a-95d3-c018a3c499cc', 'user', 'Hello, how are you?', 1),
('9933bfba-c321-4c9a-95d3-c018a3c499cc', 'assistant', 'I am an AI, I do not have feelings, but thank you for asking!', 2),
('9933bfba-c321-4c9a-95d3-c018a3c499cc', 'user', 'Can you help me with something?', 3),
('9933bfba-c321-4c9a-95d3-c018a3c499cc', 'assistant', 'Of course! What do you need help with?', 4);
