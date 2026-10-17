CREATE TABLE weekly_earthquakes (
    event_id VARCHAR(64) PRIMARY KEY,
    magnitude DOUBLE PRECISION NOT NULL, place VARCHAR(512),
    event_time BIGINT NOT NULL, updated_time BIGINT,
    longitude DOUBLE PRECISION NOT NULL, latitude DOUBLE PRECISION NOT NULL,
    depth_km DOUBLE PRECISION NOT NULL, event_url TEXT, source_type VARCHAR(64)
);
