CREATE TABLE IF NOT EXISTS laundry_tasks (

    id SERIAL PRIMARY KEY,

    command TEXT,

    target VARCHAR(50),

    confidence REAL,

    saturation REAL,

    value REAL,

    classification VARCHAR(30),

    destination VARCHAR(30),

    status VARCHAR(30),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);