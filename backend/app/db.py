import os
import re
import psycopg2
from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
from .config import settings

# Threaded connection pools keyed by schema
_pools = {}
_initialized_schemas = set()

SCHEMA_DDL = """
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS clients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    canonical_name VARCHAR(255) UNIQUE NOT NULL,
    aliases JSONB NOT NULL DEFAULT '[]'::jsonb,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS leads (
    lead_id VARCHAR(50) PRIMARY KEY,
    client_id UUID REFERENCES clients(id) ON DELETE SET NULL,
    created TIMESTAMPTZ NOT NULL,
    name VARCHAR(255),
    business VARCHAR(255),
    email VARCHAR(255),
    phone VARCHAR(50),
    source VARCHAR(100),
    first_reply DATE,
    status VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS bookings (
    booking_id VARCHAR(50) PRIMARY KEY,
    client_id UUID REFERENCES clients(id) ON DELETE SET NULL,
    date DATE NOT NULL,
    client_name VARCHAR(255),
    email VARCHAR(255),
    service VARCHAR(255),
    status VARCHAR(50),
    price NUMERIC(10, 2) NOT NULL
);

CREATE TABLE IF NOT EXISTS production_videos (
    video_id VARCHAR(50) PRIMARY KEY,
    client_id UUID REFERENCES clients(id) ON DELETE SET NULL,
    client VARCHAR(255),
    title VARCHAR(255) NOT NULL,
    editor VARCHAR(100),
    stage VARCHAR(50),
    notes_on_board TEXT,
    revisions INTEGER DEFAULT 0,
    editor_hours NUMERIC(6, 2) DEFAULT 0.00,
    client_approved_on DATE,
    shoot_booking VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS invoices (
    invoice_no VARCHAR(50) PRIMARY KEY,
    client_id UUID REFERENCES clients(id) ON DELETE SET NULL,
    bill_to VARCHAR(255),
    email VARCHAR(255),
    issued DATE NOT NULL,
    due DATE NOT NULL,
    amount NUMERIC(10, 2) NOT NULL,
    status VARCHAR(50) NOT NULL,
    memo TEXT
);

CREATE TABLE IF NOT EXISTS payments (
    payment_id VARCHAR(50) PRIMARY KEY,
    payment_date DATE NOT NULL,
    payer VARCHAR(255),
    payer_email VARCHAR(255),
    amount NUMERIC(10, 2) NOT NULL,
    method VARCHAR(50),
    reference VARCHAR(255),
    matched_invoice_no VARCHAR(50) REFERENCES invoices(invoice_no) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID REFERENCES clients(id) ON DELETE SET NULL,
    message_date TIMESTAMPTZ,
    channel VARCHAR(50),
    sender VARCHAR(255),
    message_text TEXT,
    original_line TEXT UNIQUE
);

CREATE TABLE IF NOT EXISTS team_members (
    name VARCHAR(100) PRIMARY KEY,
    role VARCHAR(100),
    joined DATE,
    pay NUMERIC(10, 2)
);

CREATE TABLE IF NOT EXISTS cost_rules (
    id SERIAL PRIMARY KEY,
    rule_name VARCHAR(100) NOT NULL,
    value NUMERIC(10, 2),
    unit VARCHAR(50),
    notes TEXT
);

CREATE TABLE IF NOT EXISTS message_classifications (
    id SERIAL PRIMARY KEY,
    message_id VARCHAR(64) NOT NULL,
    provider VARCHAR(64) NOT NULL DEFAULT 'google_gemini',
    model VARCHAR(64) NOT NULL,
    prompt_version VARCHAR(32) NOT NULL DEFAULT 'v1',
    content_hash VARCHAR(64) NOT NULL,
    primary_category VARCHAR(64) NOT NULL,
    secondary_categories JSONB NOT NULL DEFAULT '[]'::jsonb,
    is_spam_or_test BOOLEAN NOT NULL DEFAULT FALSE,
    spam_reason TEXT,
    sentiment VARCHAR(32) NOT NULL DEFAULT 'neutral',
    urgency VARCHAR(32) NOT NULL DEFAULT 'normal',
    needs_human_follow_up BOOLEAN NOT NULL DEFAULT FALSE,
    needs_reply BOOLEAN,
    requested_action TEXT,
    concise_summary TEXT,
    evidence_quotes JSONB NOT NULL DEFAULT '[]'::jsonb,
    mentioned_record_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    confidence NUMERIC(4,3) NOT NULL DEFAULT 0.0,
    classification_notes TEXT,
    status VARCHAR(32) NOT NULL DEFAULT 'classified_unreviewed',
    human_confirmed BOOLEAN NOT NULL DEFAULT FALSE,
    human_reviewer VARCHAR(64),
    human_notes TEXT,
    error_code VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (message_id, content_hash)
);

CREATE TABLE IF NOT EXISTS recommendation_states (
    fingerprint VARCHAR(128) PRIMARY KEY,
    action_type VARCHAR(64) NOT NULL,
    title TEXT NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    priority INTEGER DEFAULT 1,
    urgency VARCHAR(32) DEFAULT 'High',
    responsible_area VARCHAR(64) DEFAULT 'client',
    target_client VARCHAR(128),
    target_record VARCHAR(64),
    why_it_matters TEXT,
    suggested_action TEXT,
    what_is_uncertain TEXT,
    evidence JSONB DEFAULT '[]'::jsonb,
    draft_text TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS identity_review_actions (
    id SERIAL PRIMARY KEY,
    table_name VARCHAR(64) NOT NULL,
    record_id VARCHAR(64) NOT NULL,
    action VARCHAR(32) NOT NULL,
    suggested_client_id VARCHAR(64),
    assigned_client_id VARCHAR(64),
    reason TEXT,
    performed_by VARCHAR(64) DEFAULT 'Owner',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (table_name, record_id, action)
);
"""


def ensure_schema_initialized(target_schema: str):
    if target_schema in _initialized_schemas:
        return
    pool = _pools.get(target_schema)
    if not pool:
        return
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(f"CREATE SCHEMA IF NOT EXISTS {target_schema};")
            cur.execute(f"SET search_path TO {target_schema},public;")
            cur.execute(SCHEMA_DDL)
        conn.commit()
        _initialized_schemas.add(target_schema)
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


def get_active_schema() -> str:
    schema = os.getenv("DB_SCHEMA", settings.DB_SCHEMA) or "public"
    if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", schema):
        raise ValueError(f"Unsafe database schema identifier: {schema}")
    return schema


def get_pool(schema: str = None):
    target_schema = schema or get_active_schema()
    if target_schema not in _pools:
        params = {
            "dbname": settings.DB_NAME,
            "user": settings.DB_USER,
            "minconn": 1,
            "maxconn": 20,
        }
        # Neon / PgBouncer poolers do not allow search_path in startup parameters
        if target_schema != "public" and "pooler" not in (settings.DB_HOST or ""):
            params["options"] = f"-c search_path={target_schema},public"

        if settings.DB_HOST:
            params["host"] = settings.DB_HOST
            params["port"] = settings.DB_PORT
        if settings.DB_PASSWORD:
            params["password"] = settings.DB_PASSWORD
        if getattr(settings, "DB_SSLMODE", None):
            params["sslmode"] = settings.DB_SSLMODE

        _pools[target_schema] = ThreadedConnectionPool(**params)
        ensure_schema_initialized(target_schema)
    return _pools[target_schema]


@contextmanager
def get_db(schema: str = None):
    target_schema = schema or get_active_schema()
    pool = get_pool(target_schema)
    conn = pool.getconn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if target_schema != "public":
                cur.execute(f"SET search_path TO {target_schema},public;")
            yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)
