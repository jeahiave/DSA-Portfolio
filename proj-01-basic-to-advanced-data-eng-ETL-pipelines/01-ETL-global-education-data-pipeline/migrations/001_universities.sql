CREATE TABLE universities (
    university_id TEXT PRIMARY KEY,
    name VARCHAR(512) NOT NULL,
    country VARCHAR(255) NOT NULL,
    alpha_two_code VARCHAR(2), state_province VARCHAR(255),
    web_pages TEXT NOT NULL, domains TEXT NOT NULL
);
