-- Axeom Studio Database Schema
-- Designed for mobile-first Studio OS challenge

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 1. CLIENTS (Canonical identities)
CREATE TABLE IF NOT EXISTS clients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    canonical_name VARCHAR(255) UNIQUE NOT NULL,
    aliases JSONB NOT NULL DEFAULT '[]'::jsonb,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_clients_canonical_name ON clients(canonical_name);

-- 2. LEADS
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

CREATE INDEX IF NOT EXISTS idx_leads_client_id ON leads(client_id);
CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status);

-- 3. BOOKINGS
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

CREATE INDEX IF NOT EXISTS idx_bookings_client_id ON bookings(client_id);
CREATE INDEX IF NOT EXISTS idx_bookings_date ON bookings(date);

-- 4. PRODUCTION VIDEOS
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

CREATE INDEX IF NOT EXISTS idx_production_videos_client_id ON production_videos(client_id);
CREATE INDEX IF NOT EXISTS idx_production_videos_stage ON production_videos(stage);
CREATE INDEX IF NOT EXISTS idx_production_videos_editor ON production_videos(editor);

-- 5. INVOICES
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

CREATE INDEX IF NOT EXISTS idx_invoices_client_id ON invoices(client_id);
CREATE INDEX IF NOT EXISTS idx_invoices_status ON invoices(status);
CREATE INDEX IF NOT EXISTS idx_invoices_due ON invoices(due);

-- 6. PAYMENTS
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

CREATE INDEX IF NOT EXISTS idx_payments_matched_invoice_no ON payments(matched_invoice_no);
CREATE INDEX IF NOT EXISTS idx_payments_date ON payments(payment_date);

-- 7. MESSAGES
CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID REFERENCES clients(id) ON DELETE SET NULL,
    message_date TIMESTAMPTZ,
    channel VARCHAR(50),
    sender VARCHAR(255),
    message_text TEXT,
    original_line TEXT UNIQUE
);

CREATE INDEX IF NOT EXISTS idx_messages_client_id ON messages(client_id);
CREATE INDEX IF NOT EXISTS idx_messages_date ON messages(message_date);

-- 8. TEAM MEMBERS
CREATE TABLE IF NOT EXISTS team_members (
    name VARCHAR(100) PRIMARY KEY,
    role VARCHAR(100),
    joined DATE,
    pay NUMERIC(10, 2)
);

-- 9. COST RULES
CREATE TABLE IF NOT EXISTS cost_rules (
    id SERIAL PRIMARY KEY,
    rule_name VARCHAR(100) NOT NULL,
    value NUMERIC(10, 2),
    unit VARCHAR(50),
    notes TEXT
);

-- 10. MESSAGE CLASSIFICATIONS (Gemini structured outputs & human review)
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

CREATE INDEX IF NOT EXISTS idx_msg_class_msg_id ON message_classifications(message_id);
CREATE INDEX IF NOT EXISTS idx_msg_class_category ON message_classifications(primary_category);
CREATE INDEX IF NOT EXISTS idx_msg_class_status ON message_classifications(status);

-- 11. RECOMMENDATION STATES (PostgreSQL persistence & deterministic drafts)
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

CREATE INDEX IF NOT EXISTS idx_rec_states_status ON recommendation_states(status);

-- 12. IDENTITY REVIEW ACTIONS (Persistent review log for confirm, reject, assign)
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
