CREATE TABLE IF NOT EXISTS votes (
    id SERIAL PRIMARY KEY,
    number TEXT,
    brand TEXT,
    shade_name TEXT,
    finish TEXT,
    collection TEXT,
    winner_number TEXT,
    winner_brand TEXT,
    winner_shade_name TEXT,
    winner_finish TEXT,
    winner_collection TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
