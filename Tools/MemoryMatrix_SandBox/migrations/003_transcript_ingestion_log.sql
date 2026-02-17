-- Migration 003: Transcript Ingestion Log
-- Tracks which transcripts have been ingested, when, and how

CREATE TABLE IF NOT EXISTS transcript_ingestion_log (
    conversation_uuid TEXT PRIMARY KEY,
    transcript_path TEXT NOT NULL,
    ingested_at TEXT DEFAULT CURRENT_TIMESTAMP,

    -- Trigger tracking
    trigger TEXT NOT NULL,             -- 'batch' | 'retrieval_miss' | 'manual'
    trigger_query TEXT,                -- For retrieval_miss: the query that triggered it

    -- Classification
    tier TEXT NOT NULL,                -- 'GOLD' | 'SILVER' | 'BRONZE'
    texture TEXT,                      -- JSON array of texture tags

    -- Extraction results
    extraction_status TEXT DEFAULT 'complete',  -- 'complete' | 'partial' | 'failed'
    nodes_created INTEGER DEFAULT 0,
    entities_found INTEGER DEFAULT 0,
    edges_created INTEGER DEFAULT 0,

    -- Review
    review_status TEXT DEFAULT 'pending',  -- 'pending' | 'approved' | 'rejected'

    -- Error tracking
    error_message TEXT
);

-- Index for querying by trigger type
CREATE INDEX IF NOT EXISTS idx_ingestion_trigger ON transcript_ingestion_log(trigger);

-- Index for querying by tier
CREATE INDEX IF NOT EXISTS idx_ingestion_tier ON transcript_ingestion_log(tier);

-- Index for finding failed extractions
CREATE INDEX IF NOT EXISTS idx_ingestion_status ON transcript_ingestion_log(extraction_status);
