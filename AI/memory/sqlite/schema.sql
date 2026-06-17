CREATE TABLE IF NOT EXISTS project_context (
    project TEXT PRIMARY KEY,
    purpose TEXT,
    current_status TEXT,
    key_issues TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS decisions (
    decision_id TEXT PRIMARY KEY,
    project TEXT NOT NULL,
    title TEXT NOT NULL,
    context TEXT,
    decided_at TEXT
);

CREATE TABLE IF NOT EXISTS operational_notes (
    note_id TEXT PRIMARY KEY,
    project TEXT NOT NULL,
    topic TEXT NOT NULL,
    note TEXT NOT NULL,
    source TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS evaluation_runs (
    run_id TEXT PRIMARY KEY,
    project TEXT NOT NULL,
    profile TEXT NOT NULL,
    result TEXT NOT NULL,
    report_path TEXT,
    created_at TEXT
);