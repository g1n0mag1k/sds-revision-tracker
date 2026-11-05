"""SQLite storage (standard library) and activity events.

The activity history is application activity history / version tracking.
It is NOT tamper-proof or certified compliance logging.
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS materials (
    id INTEGER PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,              -- internal code (fictional in demos)
    product_name TEXT NOT NULL,
    supplier TEXT NOT NULL,
    product_identifier TEXT,                -- optional supplier product number/code
    cas_numbers TEXT NOT NULL DEFAULT '[]', -- JSON list; informational, not identity
    baseline_document_id INTEGER REFERENCES documents(id),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY,
    sha256 TEXT NOT NULL UNIQUE,            -- identical bytes stored once
    stored_path TEXT NOT NULL,              -- application-controlled path
    first_filename TEXT NOT NULL,
    byte_size INTEGER NOT NULL,
    page_count INTEGER,
    source_url TEXT,
    retrieved_on TEXT,
    text_status TEXT NOT NULL,              -- text | no_text | failed
    fields TEXT NOT NULL,                   -- JSON: raw/normalized/page/evidence/status
    sections TEXT NOT NULL,                 -- JSON: per-section text/pages/status
    warnings TEXT NOT NULL,                 -- JSON list
    material_id INTEGER REFERENCES materials(id), -- confirmed association only
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS receipts (
    id INTEGER PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id),
    original_filename TEXT NOT NULL,
    received_at TEXT NOT NULL,
    actor TEXT NOT NULL,
    match_status TEXT NOT NULL,             -- unconfirmed | confirmed | inherited | no_register_match
    material_id INTEGER REFERENCES materials(id),
    classification TEXT,                    -- NULL until classified
    classification_reason TEXT,
    baseline_document_id INTEGER REFERENCES documents(id), -- snapshot at classification
    comparison TEXT                         -- JSON snapshot at classification
);

CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY,
    receipt_id INTEGER NOT NULL UNIQUE REFERENCES receipts(id),
    status TEXT NOT NULL,                   -- pending | in_progress | completed
    reviewer_label TEXT,                    -- free text, not an authenticated identity
    comments TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS notification_drafts (
    id INTEGER PRIMARY KEY,
    receipt_id INTEGER NOT NULL UNIQUE REFERENCES receipts(id),
    recipient_label TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    generated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS activity_events (
    id INTEGER PRIMARY KEY,
    ts TEXT NOT NULL,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id INTEGER,
    previous_value TEXT,
    new_value TEXT,
    reason TEXT
);
"""

SYSTEM_ACTOR = "system"


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(data_dir: Path | None = None, check_same_thread: bool = True) -> sqlite3.Connection:
    path = config.db_path(data_dir)
    if not path.exists():
        raise FileNotFoundError(
            f"Database not found at {path}. Run: .venv/bin/python -m sdstracker init-db"
        )
    conn = sqlite3.connect(path, check_same_thread=check_same_thread)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(data_dir: Path | None = None) -> tuple[Path, bool]:
    """Create tables if missing. Never drops or resets existing data.

    Returns (db_path, created_new).
    """
    path = config.db_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    config.documents_dir(data_dir).mkdir(parents=True, exist_ok=True)
    created = not path.exists()
    conn = sqlite3.connect(path)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()
    return path, created


def _dump(value):
    if value is None or isinstance(value, str):
        return value
    return json.dumps(value, sort_keys=True, default=str)


def log_event(conn, actor, action, entity_type, entity_id=None,
              previous_value=None, new_value=None, reason=None):
    conn.execute(
        "INSERT INTO activity_events (ts, actor, action, entity_type, entity_id,"
        " previous_value, new_value, reason) VALUES (?,?,?,?,?,?,?,?)",
        (now(), actor or SYSTEM_ACTOR, action, entity_type, entity_id,
         _dump(previous_value), _dump(new_value), reason),
    )


def loads(text, default=None):
    if text is None:
        return default
    return json.loads(text)
