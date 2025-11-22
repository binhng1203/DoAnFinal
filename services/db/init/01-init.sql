-- File: services/db/init/01-init.sql

-- 1. Tạo Role CHUNG cho hệ thống
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_user') THEN
    CREATE ROLE app_user LOGIN PASSWORD 'app_password';
  END IF;
END$$;

-- 2. Cấp quyền kết nối vào Database 'final'
GRANT CONNECT ON DATABASE final TO app_user;

-- 3. Tạo schema CORE và gán quyền chủ sở hữu cho app_user
CREATE SCHEMA IF NOT EXISTS core AUTHORIZATION app_user;

-- 4. Tạo schema MANAGEMENT và gán quyền chủ sở hữu cho app_user
CREATE SCHEMA IF NOT EXISTS management AUTHORIZATION app_user;

-- 5. Cài extension (Schema public thường cần quyền của postgres superuser hoặc owner DB)
-- Lưu ý: Lệnh này nên để docker chạy mặc định hoặc dùng user postgres chạy.
-- Trong file này vẫn chạy dưới quyền postgres (mặc định của init script) nên OK.
CREATE EXTENSION IF NOT EXISTS pgcrypto SCHEMA public;

-- 6. Cấp quyền cho app_user dùng schema public (để truy cập extension pgcrypto)
GRANT USAGE ON SCHEMA public TO app_user;