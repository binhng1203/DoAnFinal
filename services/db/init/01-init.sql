-- ====================================================================================
-- INIT DB FINAL - FULLY COMPATIBLE WITH PersistenceService (self_healing_v1)
-- Target DB: final
-- Schemas:
--   - core, management   (web)
--   - healenium          (Healenium Java backend)
--   - custom_analytics   (Python persistence + report)
-- Tables created to match code:
--   1) public.healing_knowledge
--   2) custom_analytics.test_run_history
--   3) custom_analytics.heal_event
--   4) custom_analytics.locator_instability
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
-- PART 2: EXTENSIONS
-- ====================================================================================
CREATE EXTENSION IF NOT EXISTS pgcrypto SCHEMA public;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp" SCHEMA public;

GRANT USAGE ON SCHEMA public TO app_user;
GRANT USAGE ON SCHEMA public TO healenium_user;

-- ====================================================================================
-- PART 3: WEB SCHEMAS
-- ====================================================================================
CREATE SCHEMA IF NOT EXISTS core AUTHORIZATION app_user;
CREATE SCHEMA IF NOT EXISTS management AUTHORIZATION app_user;

-- ====================================================================================
-- PART 4: HEALENIUM SCHEMA (for Java backend)
-- ====================================================================================
CREATE SCHEMA IF NOT EXISTS healenium AUTHORIZATION healenium_user;
GRANT USAGE, CREATE ON SCHEMA healenium TO healenium_user;

-- Ensure backend always targets right schema
ALTER ROLE healenium_user SET search_path = custom_analytics, healenium, public;

-- ====================================================================================
-- PART 5: CUSTOM_ANALYTICS SCHEMA (Python Persistence)
-- ====================================================================================
CREATE SCHEMA IF NOT EXISTS custom_analytics AUTHORIZATION app_user;

-- ====================================================================================
-- PART 6: ENUMS (optional, kept for compatibility)
-- ====================================================================================
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname='heal_result') THEN
    CREATE TYPE heal_result AS ENUM ('SUCCESS','FAILURE');
  END IF;
END$$;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname='heal_engine') THEN
    CREATE TYPE heal_engine AS ENUM ('NATIVE','PYTHON','NONE');
  END IF;
END$$;

ALTER TYPE heal_result OWNER TO app_user;
ALTER TYPE heal_engine OWNER TO app_user;

-- ====================================================================================
-- PART 7: TABLES (MATCH PersistenceService)
-- ====================================================================================

-- ------------------------------------------------------------
-- 7.1) KB TABLE: public.healing_knowledge
-- Used by _upsert_kb()
-- Unique: (fingerprint, old_locator_value, new_locator_value)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.healing_knowledge (
  id                BIGSERIAL PRIMARY KEY,

  project_id        VARCHAR(8),                              -- optional (code passes None)
  fingerprint       JSONB NOT NULL,                      -- Json(fingerprint)

  old_locator_by    VARCHAR(50) NOT NULL,
  old_locator_value TEXT NOT NULL,
  new_locator_by    VARCHAR(50) NOT NULL,
  new_locator_value TEXT NOT NULL,

  success_count     INT NOT NULL DEFAULT 0 CHECK (success_count >= 0),
  failure_count     INT NOT NULL DEFAULT 0 CHECK (failure_count >= 0),
  avg_repair_ms     BIGINT NOT NULL DEFAULT 0 CHECK (avg_repair_ms >= 0),

  last_success_at   TIMESTAMPTZ,
  last_failure_at   TIMESTAMPTZ,

  commit_info       JSONB,
  source_type       TEXT NOT NULL DEFAULT 'AUTO',
  app_version       TEXT,

  last_updated      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  CONSTRAINT uq_kb UNIQUE (fingerprint, old_locator_value, new_locator_value)
);

ALTER TABLE public.healing_knowledge OWNER TO app_user;

CREATE INDEX IF NOT EXISTS idx_kb_old_locator ON public.healing_knowledge(old_locator_value);
CREATE INDEX IF NOT EXISTS idx_kb_app_version  ON public.healing_knowledge(app_version);



-- ------------------------------------------------------------
-- 7.2) TEST RUN HISTORY: custom_analytics.test_run_history
-- Used by save_raw_run_and_get_id() + update_*()
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS custom_analytics.test_run_history (
  id                   BIGSERIAL PRIMARY KEY,

  test_id              TEXT NOT NULL,
  timestamp            TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  raw_result           TEXT,
  heal_attempted       BOOLEAN NOT NULL DEFAULT FALSE,
  heal_success         BOOLEAN NOT NULL DEFAULT FALSE,
  final_result         TEXT NOT NULL DEFAULT 'Running',

  calculated_risk      NUMERIC(6,3),

  total_duration_ms    BIGINT,                           -- can be NULL until final update
  total_heal_attempts  INT NOT NULL DEFAULT 0,
  total_heal_success   INT NOT NULL DEFAULT 0,

  app_version          TEXT,

  -- optional extras for future/backward compatible
  build_version        TEXT,
  git_hash             TEXT,
  author               TEXT,
  metadata             JSONB,

  created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE custom_analytics.test_run_history OWNER TO app_user;

-- Idempotent add columns in case DB existed before
ALTER TABLE custom_analytics.test_run_history
  ADD COLUMN IF NOT EXISTS total_duration_ms BIGINT;

ALTER TABLE custom_analytics.test_run_history
  ADD COLUMN IF NOT EXISTS total_heal_attempts INT NOT NULL DEFAULT 0;

ALTER TABLE custom_analytics.test_run_history
  ADD COLUMN IF NOT EXISTS total_heal_success INT NOT NULL DEFAULT 0;

ALTER TABLE custom_analytics.test_run_history
  ADD COLUMN IF NOT EXISTS app_version TEXT;

ALTER TABLE custom_analytics.test_run_history
  ADD COLUMN IF NOT EXISTS build_version TEXT;

ALTER TABLE custom_analytics.test_run_history
  ADD COLUMN IF NOT EXISTS git_hash TEXT;

ALTER TABLE custom_analytics.test_run_history
  ADD COLUMN IF NOT EXISTS author TEXT;

ALTER TABLE custom_analytics.test_run_history
  ADD COLUMN IF NOT EXISTS metadata JSONB;



-- ------------------------------------------------------------
-- 7.3) HEAL EVENT: custom_analytics.heal_event
-- Used by _insert_heal_event()
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS custom_analytics.heal_event (
  id                 BIGSERIAL PRIMARY KEY,

  run_id             BIGINT,
  test_id            TEXT NOT NULL,
  project_id         BIGINT,                 -- code passes None currently

  page_url           TEXT,
  app_version        TEXT,

  engine             TEXT NOT NULL,          -- 'NATIVE'|'PYTHON'|'NONE'
  locator_old        TEXT NOT NULL,
  locator_new        TEXT,
  chosen_source      TEXT,

  confidence         NUMERIC(6,3),
  risk_score         NUMERIC(6,3),
  threshold          NUMERIC(6,3),

  ssim_score         NUMERIC(6,3),
  visual_status      TEXT,

  started_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  ended_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  native_overhead_ms BIGINT,
  python_overhead_ms BIGINT,

  basis              JSONB NOT NULL DEFAULT '{}'::jsonb, -- Json(basis_json)
  status             TEXT NOT NULL,                     -- SUCCESS/FAILURE
  reason             TEXT,

  created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  CONSTRAINT chk_engine  CHECK (engine IN ('NATIVE','PYTHON','NONE')),
  CONSTRAINT chk_status  CHECK (status IN ('SUCCESS','FAILURE'))
);

ALTER TABLE custom_analytics.heal_event OWNER TO app_user;

CREATE INDEX IF NOT EXISTS idx_heal_event_test_time
  ON custom_analytics.heal_event(test_id, started_at DESC);

CREATE INDEX IF NOT EXISTS idx_heal_event_run
  ON custom_analytics.heal_event(run_id);



-- ------------------------------------------------------------
-- 7.4) LOCATOR INSTABILITY: custom_analytics.locator_instability
-- Used by _update_locator_instability()
-- Unique: (project_id, locator_old)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS custom_analytics.locator_instability (
  id                BIGSERIAL PRIMARY KEY,

  project_id        BIGINT,           -- code passes None
  locator_old       TEXT NOT NULL,

  total_failures    INT NOT NULL DEFAULT 0,
  total_success     INT NOT NULL DEFAULT 0,

  instability_rate  NUMERIC(5,2) NOT NULL DEFAULT 0.00,

  last_failed_at    TIMESTAMPTZ,
  last_success_at   TIMESTAMPTZ,

  updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  CONSTRAINT uq_locator_instability UNIQUE (project_id, locator_old)
);

ALTER TABLE custom_analytics.locator_instability OWNER TO app_user;

CREATE INDEX IF NOT EXISTS idx_locator_instability_locator
  ON custom_analytics.locator_instability(locator_old);



-- ====================================================================================
-- PART 8: PERMISSIONS FOR healenium_user ON custom_analytics
-- (to avoid "permission denied for schema custom_analytics")
-- ====================================================================================

GRANT USAGE, CREATE ON SCHEMA custom_analytics TO healenium_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA custom_analytics TO healenium_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA custom_analytics TO healenium_user;

-- Auto grant to future tables/sequences
ALTER DEFAULT PRIVILEGES IN SCHEMA custom_analytics
GRANT ALL ON TABLES TO healenium_user;

ALTER DEFAULT PRIVILEGES IN SCHEMA custom_analytics
GRANT ALL ON SEQUENCES TO healenium_user;

-- ====================================================================================
-- DONE
-- ====================================================================================
CREATE TABLE IF NOT EXISTS custom_analytics.visual_validation_event (
    id              SERIAL PRIMARY KEY,
    test_id         TEXT,
    run_id          INTEGER,
    scope           TEXT,            -- 'ELEMENT' | 'FULLSCREEN'
    target_name     TEXT,            -- element_name hoặc page_name
    page_url        TEXT,
    status          TEXT,            -- PASSED / FAILED / NEW_BASELINE / SOFT_ACCEPT / ERROR
    ssim_score      NUMERIC(5,4),
    extra_metrics   JSONB,           -- fullscreen: edge_diff, matches...
    baseline_url    TEXT,            -- URL ảnh baseline trên cloud / static host
    current_url     TEXT,            -- URL ảnh hiện tại
    diff_url        TEXT,            -- URL ảnh diff (nếu có)
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

