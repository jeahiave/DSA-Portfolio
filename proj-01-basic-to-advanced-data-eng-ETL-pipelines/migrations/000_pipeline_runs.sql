CREATE TABLE pipeline_runs (
    job VARCHAR(255) PRIMARY KEY,
    last_success TIMESTAMP NOT NULL,
    row_count BIGINT NOT NULL
);
