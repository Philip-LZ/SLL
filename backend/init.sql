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

----------------------------- add test data---------------------------------

-- 插入新研究主题
INSERT INTO research (title, lnk, snippet) VALUES ('极昼极夜现象是怎么形成的', 'http://m.gaosan.com/gaokao/305845.html', '文/叶丹\n极昼与极夜的形成，是 由于地球在沿椭圆形轨道绕太阳公转时，还绕着自身的倾斜地轴旋转 而造成的。地轴与其垂线形成一个约23.5°的倾斜角，因而地球在公转时便出现6个月时间两极之中总有一极朝着太阳，全是白天，另一极背对全是黑夜。\n极昼极夜产生原理\n地球在沿椭圆形轨道绕太阳公转时，还绕着自身的倾斜地轴旋转。原来，地球在自转时，地轴与其垂线形成一个约23.5°的倾斜角，因而地球在公转时便出现有6个月时间两极之中总有一极朝着太阳，全是白天；另一个极背向太阳，全是黑夜。南、北极这种神奇的自然现象是其他大洲所没有的。\n极昼极夜范围及时间\n北极：极昼：每年3月21日——9月23日；极夜：每年9月23日——次年3月21日\n南极：极夜：每年3月21日——9月23日；极昼：每年9月23日——次年3月21日\n6月22日,北半球极昼范围最大,整个北极圈及其以内地区出现极昼现象；\n9月23日,全球昼夜平分,北极圈及其以内地区无极昼极夜现象（除极点）.所以从6月22日到9月23日,北半球极昼范围由整个北极圈及其以内地区缩小到北极点.\n9月23日至12月22日,此时北极点出现极夜,到了12月22日,北极圈出现极夜.南半球相反!');

SELECT ai.load_dataset('sgoel9/sam_altman_essays', 'default', table_name=>'blogs', batch_size=>50, max_batches=>1);
ALTER TABLE blogs ADD PRIMARY KEY (id);

SELECT ai.create_vectorizer(
    'public.research'::regclass,
    embedding=>ai.embedding_ollama('nomic-embed-text', 768),
    chunking=>ai.chunking_recursive_character_text_splitter('snippet'),
    formatting=>ai.formatting_python_template('Web title: $title URL: url web chunk: $chunk')
);