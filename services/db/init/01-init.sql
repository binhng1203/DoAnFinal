-- ====================================================================================
-- INIT DB FINAL - OPTIMIZED FOR PYTHON SELF-HEALING V1
-- ====================================================================================

-- ====================================================================================
-- PART 1: ROLES
-- ====================================================================================
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_user') THEN
    CREATE ROLE app_user LOGIN PASSWORD 'app_password';
  END IF;
END$$;

DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'healenium_user') THEN
    CREATE ROLE healenium_user LOGIN PASSWORD 'YDk2nmNs4s9aCP6K';
  END IF;
END$$;

GRANT CONNECT ON DATABASE final TO app_user;
GRANT CONNECT ON DATABASE final TO healenium_user;

-- ====================================================================================
-- PART 2: EXTENSIONS & PUBLIC SCHEMA
-- ====================================================================================
CREATE EXTENSION IF NOT EXISTS pgcrypto SCHEMA public;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp" SCHEMA public;

GRANT USAGE ON SCHEMA public TO app_user;
GRANT USAGE ON SCHEMA public TO healenium_user;

-- ====================================================================================
-- PART 3: HEALENIUM & ANALYTICS SCHEMAS
-- ====================================================================================
-- Schema cho Healenium Java Backend
CREATE SCHEMA IF NOT EXISTS healenium AUTHORIZATION healenium_user;
GRANT USAGE, CREATE ON SCHEMA healenium TO healenium_user;

-- Schema cho Python Persistence & Report
CREATE SCHEMA IF NOT EXISTS custom_analytics AUTHORIZATION app_user;
GRANT USAGE, CREATE ON SCHEMA custom_analytics TO app_user;
GRANT USAGE, CREATE ON SCHEMA custom_analytics TO healenium_user; -- Cấp quyền cho user healenium đọc/ghi báo cáo

-- Thiết lập search path mặc định
ALTER ROLE healenium_user SET search_path = custom_analytics, healenium, public;
ALTER ROLE app_user SET search_path = custom_analytics, public;

-- ====================================================================================
-- PART 4: KB TABLE (Layer 1)
-- ====================================================================================
-- 1. Xóa bảng cũ để áp dụng cấu trúc mới
DROP TABLE IF EXISTS public.healing_knowledge;

-- 2. Tạo bảng chuẩn hóa
CREATE TABLE public.healing_knowledge (
    id                BIGSERIAL PRIMARY KEY,
    project_id        VARCHAR(100) DEFAULT 'default_project', 
    
    -- [FINGERPRINT INFO]
    -- Hợp nhất fingerprint_json và fingerprint thành 1 cột duy nhất
    fingerprint       JSONB NOT NULL,                   
    fingerprint_hash  TEXT UNIQUE NOT NULL,             -- Dùng để so khớp nhanh và ON CONFLICT

    -- [LOCATOR INFO]
    old_locator_by    VARCHAR(50) NOT NULL,
    old_locator_value TEXT NOT NULL,
    new_locator_by    VARCHAR(50) NOT NULL,
    new_locator_value TEXT NOT NULL,

    -- [METRICS]
    success_count     INT NOT NULL DEFAULT 0,
    failure_count     INT NOT NULL DEFAULT 0,
    success_rate      NUMERIC(5,2) GENERATED ALWAYS AS (
        CASE WHEN (success_count + failure_count) = 0 THEN 0 
        ELSE (success_count::float / (success_count + failure_count)) * 100 
        END
    ) STORED, -- Tự động tính % thành công
    avg_repair_ms     BIGINT NOT NULL DEFAULT 0,

    -- [TIMESTAMPS]
    last_success_at   TIMESTAMPTZ,
    last_failure_at   TIMESTAMPTZ,
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at      TIMESTAMPTZ DEFAULT NOW(),

    -- [EXTRA INFO]
    last_engine       TEXT,                             -- 'PYTHON', 'LCS', 'HEALENIUM'
    last_score        NUMERIC(5,4),
    commit_info       JSONB,
    source_type       TEXT DEFAULT 'AUTO',
    manual_override   BOOLEAN DEFAULT FALSE,

    -- [CONSTRAINT]
    CONSTRAINT uq_kb_locators UNIQUE (fingerprint_hash)
);

-- Tạo Index để Suggestion Layer truy vấn cực nhanh
CREATE INDEX idx_kb_fp_hash ON public.healing_knowledge(fingerprint_hash);

-- ====================================================================================
-- PART 5: REPORTING TABLES (Layer 3 & 4)
-- ====================================================================================

-- 5.1 TEST RUN HISTORY
CREATE TABLE IF NOT EXISTS custom_analytics.test_run_history (
    id                  BIGSERIAL PRIMARY KEY,
    test_id             TEXT NOT NULL,
    run_id              TEXT UNIQUE,                            -- [UPDATE] Added run_id (uuid string)
    timestamp           TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    raw_result          TEXT,                            -- 'Pass' / 'Fail'
    heal_attempted      BOOLEAN NOT NULL DEFAULT FALSE,
    heal_success        BOOLEAN NOT NULL DEFAULT FALSE,
    final_result        TEXT NOT NULL DEFAULT 'Running',

    calculated_risk     NUMERIC(6,3),                    -- Fuzzy Logic Output

    total_duration_ms   BIGINT,
    total_heal_attempts INT NOT NULL DEFAULT 0,
    total_heal_success  INT NOT NULL DEFAULT 0,

    app_version         TEXT,
    build_version       TEXT,
    git_hash            TEXT,
    author              TEXT,
    metadata            JSONB,

    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
ALTER TABLE custom_analytics.test_run_history OWNER TO app_user;

-- 5.2 HEAL EVENT (Chi tiết mỗi lần heal)
CREATE TABLE IF NOT EXISTS custom_analytics.heal_event (
    id                 BIGSERIAL PRIMARY KEY,
    run_id             TEXT,                             -- [FIXED] Changed to TEXT to match UUID from Python
    test_id            TEXT NOT NULL,
    project_id         TEXT,                             -- [FIXED] Changed to TEXT

    page_url           TEXT,
    locator_old        TEXT NOT NULL,
    locator_new        TEXT,
    
    engine             TEXT NOT NULL,                    -- 'PYTHON', 'NATIVE'
    chosen_source      TEXT,                             -- 'kb_python', 'heuristic'
    
    confidence         NUMERIC(6,3),
    risk_score         NUMERIC(6,3),
    threshold          NUMERIC(6,3),
    
    ssim_score         NUMERIC(6,3),
    visual_status      TEXT,                             -- 'PASSED', 'SOFT_ACCEPT'

    status             TEXT NOT NULL,                    -- 'SUCCESS', 'FAILURE'
    error_message      TEXT,

    started_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    duration_ms        BIGINT,

    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
ALTER TABLE custom_analytics.heal_event OWNER TO app_user;

-- 5.3 LOCATOR INSTABILITY (Thống kê độ ổn định)
CREATE TABLE IF NOT EXISTS custom_analytics.locator_instability (
    id                 BIGSERIAL PRIMARY KEY,
    project_id         TEXT,                             -- [FIXED] Changed to TEXT
    locator_old        TEXT NOT NULL,

    total_failures     INT NOT NULL DEFAULT 0,
    total_success      INT NOT NULL DEFAULT 0,
    instability_rate   NUMERIC(5,2) NOT NULL DEFAULT 0.00, -- (Fail / Total)

    last_failed_at     TIMESTAMPTZ,
    last_success_at    TIMESTAMPTZ,
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_locator_instability UNIQUE (locator_old)
);
ALTER TABLE custom_analytics.locator_instability OWNER TO app_user;

-- 5.4 VISUAL VALIDATION EVENT (Validation Layer Logs)
CREATE TABLE IF NOT EXISTS custom_analytics.visual_validation_event (
    id                 SERIAL PRIMARY KEY,
    test_id            TEXT,
    run_id             TEXT,                             -- [FIXED] TEXT for UUID
    scope              TEXT,                             -- 'ELEMENT' | 'FULLSCREEN'
    target_name        TEXT,                             -- Element Name / Page Name
    
    page_url           TEXT,
    status             TEXT,                             -- PASSED / FAILED / NEW_BASELINE / SOFT_ACCEPT
    
    ssim_score         NUMERIC(5,4),
    extra_metrics      JSONB,                            -- {edge_diff: 0.01, matches: 100}
    
    baseline_path      TEXT,                             -- Path file ảnh gốc
    current_path       TEXT,                             -- Path file ảnh hiện tại
    diff_path          TEXT,                             -- Path file ảnh khác biệt
    
    created_at         TIMESTAMPTZ DEFAULT NOW()
);
ALTER TABLE custom_analytics.visual_validation_event OWNER TO app_user;

-- ====================================================================================
-- PART 6: PERMISSIONS
-- ====================================================================================
-- Cấp quyền cho healenium_user để Python Service có thể ghi vào
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA custom_analytics TO healenium_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA custom_analytics TO healenium_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO healenium_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO healenium_user;

-- Auto grant cho tương lai
ALTER DEFAULT PRIVILEGES IN SCHEMA custom_analytics GRANT ALL ON TABLES TO healenium_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA custom_analytics GRANT ALL ON SEQUENCES TO healenium_user;

-- Bước 1: SCHEMA PUBLIC
GRANT USAGE ON SCHEMA public TO app_user;
GRANT ALL ON ALL TABLES IN SCHEMA public TO app_user;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO app_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO app_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO app_user;

-- Bước 2: SCHEMA MANAGEMENT
GRANT USAGE ON SCHEMA management TO app_user;
GRANT ALL ON ALL TABLES IN SCHEMA management TO app_user;
GRANT ALL ON ALL SEQUENCES IN SCHEMA management TO app_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA management GRANT ALL ON TABLES TO app_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA management GRANT ALL ON SEQUENCES TO app_user;

-- Bước 3: Gán Owner (Nếu cần thiết tối đa quyền hạn)
ALTER SCHEMA management OWNER TO app_user;
ALTER SCHEMA public OWNER TO app_user;