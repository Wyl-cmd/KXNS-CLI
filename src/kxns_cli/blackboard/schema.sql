-- KXNS Hunter Blackboard schema (PostgreSQL + pgvector optional)

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS engagements (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    root_url TEXT NOT NULL,
    mode TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'running',
    config JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS targets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    engagement_id UUID NOT NULL REFERENCES engagements(id) ON DELETE CASCADE,
    parent_id UUID REFERENCES targets(id) ON DELETE SET NULL,
    value TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'url',
    depth INT NOT NULL DEFAULT 0,
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_targets_engagement ON targets(engagement_id);

CREATE TABLE IF NOT EXISTS findings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    engagement_id UUID NOT NULL REFERENCES engagements(id) ON DELETE CASCADE,
    target_id UUID REFERENCES targets(id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    severity TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'candidate',
    cwe TEXT,
    cvss REAL,
    description TEXT NOT NULL DEFAULT '',
    poc TEXT NOT NULL DEFAULT '',
    confidence REAL,
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_findings_engagement ON findings(engagement_id);
CREATE INDEX IF NOT EXISTS idx_findings_severity ON findings(severity, status);

CREATE TABLE IF NOT EXISTS artifacts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    engagement_id UUID NOT NULL REFERENCES engagements(id) ON DELETE CASCADE,
    finding_id UUID REFERENCES findings(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    path TEXT,
    content TEXT,
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS scan_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    engagement_id UUID NOT NULL REFERENCES engagements(id) ON DELETE CASCADE,
    target_id UUID REFERENCES targets(id) ON DELETE SET NULL,
    phase TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    prompt TEXT NOT NULL DEFAULT '',
    result_summary TEXT,
    error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_scan_jobs_engagement ON scan_jobs(engagement_id);

-- pgvector extension (optional; skip if unavailable)
DO $$
BEGIN
    CREATE EXTENSION IF NOT EXISTS vector;
EXCEPTION
    WHEN OTHERS THEN
        RAISE NOTICE 'pgvector extension not available, skipping';
END $$;

-- Only create finding_embeddings table if pgvector is available
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector') THEN
        CREATE TABLE IF NOT EXISTS finding_embeddings (
            finding_id UUID PRIMARY KEY REFERENCES findings(id) ON DELETE CASCADE,
            embedding vector(1536)
        );
    ELSE
        RAISE NOTICE 'pgvector extension not available, skipping finding_embeddings table';
    END IF;
END $$;
