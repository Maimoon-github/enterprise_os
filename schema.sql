-- PostgreSQL with pgvector schema for Autonomous AI Agent Architecture (TSK-02)
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Semantic Brand Knowledge Graph and Snapshot Table
CREATE TABLE IF NOT EXISTS brand_state (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    brand_id VARCHAR(128) NOT NULL,
    version INT NOT NULL DEFAULT 1,
    profile_data JSONB NOT NULL,
    embedding vector(1536),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_brand_state_brand_id ON brand_state(brand_id);
CREATE INDEX IF NOT EXISTS idx_brand_state_embedding ON brand_state USING hnsw (embedding vector_cosine_ops);

-- Episodic Post-Mortems Table
CREATE TABLE IF NOT EXISTS episodic_post_mortems (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id VARCHAR(128) NOT NULL,
    phase VARCHAR(64) NOT NULL,
    outcome VARCHAR(64) NOT NULL,
    reflection TEXT NOT NULL,
    metrics JSONB DEFAULT '{}'::jsonb,
    embedding vector(1536),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_post_mortems_task_id ON episodic_post_mortems(task_id);
CREATE INDEX IF NOT EXISTS idx_post_mortems_embedding ON episodic_post_mortems USING hnsw (embedding vector_cosine_ops);
