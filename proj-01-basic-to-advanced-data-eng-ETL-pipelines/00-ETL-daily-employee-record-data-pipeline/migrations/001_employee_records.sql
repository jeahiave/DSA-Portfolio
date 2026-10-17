CREATE TABLE employee_records (
    employee_id INTEGER PRIMARY KEY,
    full_name VARCHAR(255) NOT NULL,
    username VARCHAR(255), email VARCHAR(255), street VARCHAR(255), suite VARCHAR(255),
    city VARCHAR(255), zipcode VARCHAR(32), phone VARCHAR(64), website VARCHAR(255),
    company_name VARCHAR(255), address_geo_lat DOUBLE PRECISION, address_geo_lng DOUBLE PRECISION
);
