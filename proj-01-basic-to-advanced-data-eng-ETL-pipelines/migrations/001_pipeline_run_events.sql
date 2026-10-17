CREATE TABLE pipeline_run_events (
    run_id VARCHAR(36) PRIMARY KEY,
    job VARCHAR(255) NOT NULL,
    started_at TIMESTAMP NOT NULL,
    finished_at TIMESTAMP,
    status VARCHAR(16) NOT NULL,
    duration_seconds DOUBLE PRECISION,
    fetched_count BIGINT NOT NULL,
    filtered_count BIGINT NOT NULL,
    inserted_count BIGINT NOT NULL,
    updated_count BIGINT NOT NULL,
    skipped_count BIGINT NOT NULL,
    error_message TEXT
);
CREATE INDEX ix_pipeline_run_events_job_started
    ON pipeline_run_events (job, started_at);
