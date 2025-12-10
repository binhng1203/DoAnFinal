INSERT INTO core.roles  (role_id, role_name, description) VALUES
(1, 'Admin', 'Quản trị viên hệ thống'),
(2, 'Test Manager', 'Quản lý kiểm thử'),
(3, 'Test Engineer', 'Kỹ sư kiểm thử');

INSERT INTO core.users (user_id, fullname, username, email, password_hash, is_active) VALUES
('56a0a5ec-09dc-4b59-9ccf-b581af82c3d0', 'Tester Admin', 'admin', 'TesterAdmin@email.com', '$2b$12$P5R60NnOJthXM0.OOFTNx.aYVpVQ1/DMESZbT26LQg.MGUkFv9Zcm', TRUE),
('41a2dce5-d109-4571-9fd7-dc0eaf282e54', 'Bùi Thị Xuyến', 'xuyenbt', 'XuyenBT@gmail.com', '$2b$12$21isCyG4I7YPFo1vxCjsAOi42mLdjrlUxYmIDnDGbz/BkvSDaddk2', TRUE),
('43ed7e0d-434b-4538-8a43-850a543b4072', 'Nguyễn Thái Bình', 'binhnt', 'BinhNT@gmail.com', '$2b$12$j1uBzg8ceAhBEEOwm6qaEuWreJfdqfInbJKXHm3m/1I2ddYoSG4ce', TRUE);


INSERT INTO core.permissions (permission_id, permission_key, description) VALUES
(1, 'user:read_profile', 'Xem thông tin cá nhân'),
(2, 'user:update_profile', 'Cập nhật hồ sơ'),
(3, 'admin:manage_users', 'Quản lý người dùng hệ thống'),
(4, 'project:view', 'Xem danh sách dự án'),
(5, 'project:create', 'Tạo dự án mới'),
(6, 'project:update', 'Cập nhật dự án'),
(7, 'project:delete', 'Xóa dự án'),
(8, 'test:view', 'Xem test cases/suites'),
(9, 'test:manage', 'Tạo/Sửa/Xóa test cases/suites'),
(10, 'test:execute', 'Kích hoạt chạy test (Manual/Auto)'),
(11, 'report:view', 'Xem báo cáo kết quả'),
(12, 'healing:view', 'Xem lịch sử self-healing');

INSERT INTO core.role_permissions (role_id, permission_id) VALUES
(1, 1), (1, 2), (1, 3), (1, 4), (1, 5), (1, 6), (1, 7), (1, 8), (1, 9), (1, 10), (1, 11), (1, 12),
(2, 1), (2, 2), (2, 4), (2, 5), (2, 6), (2, 8), (2, 11),
(3, 1), (3, 2),(3, 4), (3, 8), (3, 9),(3, 10), (3, 11), (3, 12); 

-- Project1
INSERT INTO management.projects (project_id, name, description, created_by_user_id) 
VALUES 
('ECOM_WEB', 'E-Commerce Website', 'Trang bán hàng online', '41a2dce5-d109-4571-9fd7-dc0eaf282e54'),
('CRM_APP1', 'CRM Application', 'Hệ thống quản lý khách hàng', '41a2dce5-d109-4571-9fd7-dc0eaf282e54'),
('HRM_SYS1', 'HR Management System', 'Quản lý nhân sự và chấm công', '41a2dce5-d109-4571-9fd7-dc0eaf282e54'),
('EDU_PORT', 'Education Portal', 'Nền tảng học trực tuyến cho sinh viên', '43ed7e0d-434b-4538-8a43-850a543b4072'),
('INV_MGMT', 'Inventory Management', 'Hệ thống quản lý kho hàng', '43ed7e0d-434b-4538-8a43-850a543b4072'),
('FINTRACK', 'Finance Tracker', 'Ứng dụng theo dõi chi tiêu và tài chính cá nhân', '41a2dce5-d109-4571-9fd7-dc0eaf282e54');

INSERT INTO management.project_members (project_id, user_id, project_role) VALUES
('ECOM_WEB', '41a2dce5-d109-4571-9fd7-dc0eaf282e54', 'Project Admin'),
('ECOM_WEB', '43ed7e0d-434b-4538-8a43-850a543b4072', 'Member'),
('ECOM_WEB', '56a0a5ec-09dc-4b59-9ccf-b581af82c3d0', 'Member'),
('CRM_APP1', '41a2dce5-d109-4571-9fd7-dc0eaf282e54', 'Project Admin'),
('HRM_SYS1', '41a2dce5-d109-4571-9fd7-dc0eaf282e54', 'Project Admin'),
('EDU_PORT', '41a2dce5-d109-4571-9fd7-dc0eaf282e54', 'Project Admin'),
('INV_MGMT', '41a2dce5-d109-4571-9fd7-dc0eaf282e54', 'Project Admin'),
('FINTRACK', '41a2dce5-d109-4571-9fd7-dc0eaf282e54', 'Project Admin');


INSERT INTO management.test_suites (suite_id, project_id, parent_suite_id, name) VALUES
('SUITE_EC_01', 'ECOM_WEB', NULL, 'Authentication Module'),
('SUITE_EC_11', 'ECOM_WEB', 'SUITE_EC_01', 'Login Successfully'),
('SUITE_EC_12', 'ECOM_WEB', 'SUITE_EC_01', 'Register Successfully'),
('SUITE_EC_02', 'ECOM_WEB', NULL, 'Checkout Module');

INSERT INTO management.test_cases (case_id, suite_id, name, priority, case_type, description, tags, assignee_id, fullscreen_page_name, created_by) 
VALUES (1, 'SUITE_EC_11', 'Login Success Flow', 'High', 'automated', 'Login with valid user', '["smoke"]'::jsonb, '43ed7e0d-434b-4538-8a43-850a543b4072', 'LoginPage', '43ed7e0d-434b-4538-8a43-850a543b4072');
VALUES (2, 'SUITE_EC_11', 'Login Success Flow', 'High', 'automated', 'Register with valid user', '["smoke"]'::jsonb, '43ed7e0d-434b-4538-8a43-850a543b4072', 'RegisterPage', '43ed7e0d-434b-4538-8a43-850a543b4072');

UPDATE management.test_cases
SET is_active = TRUE
WHERE case_id = 1;

update management.test_steps ts 
set action = 'open_url'
where ts.step_id = 1;

-- 1. Cấp quyền trên schema PUBLIC (Để ghi log healing)
GRANT USAGE ON SCHEMA public TO app_user;
GRANT ALL ON ALL TABLES IN SCHEMA public TO app_user;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_user;

-- 2. Cấp quyền trên schema MANAGEMENT (Để đọc test cases - Fix lỗi trong ảnh)
GRANT USAGE ON SCHEMA management TO app_user;
GRANT ALL ON ALL TABLES IN SCHEMA management TO app_user;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA management TO app_user;

-- 3. Đảm bảo quyền sở hữu (Chắc ăn nhất)
ALTER SCHEMA management OWNER TO app_user;

INSERT INTO management.test_steps (case_id, step_order, action, locator_type, locator_value, value, expected, url) VALUES
(1, 1, 'open', NULL, NULL, NULL, 'Page loaded', 'https://ecom.demo/login'),
(1, 2, 'type', 'id', 'user_input', 'autodev@company.com', NULL, NULL),
(1, 3, 'type', 'id', 'pass_input', '123456', NULL, NULL),
(1, 4, 'click', 'css', 'button.btn-login', NULL, 'Redirect to Home', NULL);

UPDATE management.test_steps
SET 
    action = CASE step_order
                WHEN 1 THEN 'open_url'
                WHEN 2 THEN 'click'
                WHEN 3 THEN 'click'   -- ❗ đổi từ 'type' -> 'click'
                WHEN 4 THEN 'click'
             END,
             
    locator_type = CASE step_order
                WHEN 1 THEN NULL
                WHEN 2 THEN 'id'
                WHEN 3 THEN 'xpath'   -- ❗ click trực tiếp option
                WHEN 4 THEN 'id'
             END,

    locator_value = CASE step_order
                WHEN 1 THEN NULL
                WHEN 2 THEN 'ctl00_mainContent_DropDownListCurrency'
                WHEN 3 THEN '//select[@id="ctl00_mainContent_DropDownListCurrency"]/option[@value="USD"]'
                WHEN 4 THEN 'ctl00_mainContent_chk_friendsandfamily'
             END,

    value = NULL,  -- giờ không dùng 'type' nữa nên tất cả đều NULL

    expected = CASE step_order
                WHEN 1 THEN 'Page loaded'
                WHEN 4 THEN 'Checkbox checked'
                ELSE NULL
            END,

    url = CASE step_order
                WHEN 1 THEN 'https://rahulshettyacademy.com/dropdownsPractise/'
                ELSE NULL
          END
WHERE case_id = 1
  AND step_order IN (1, 2, 3, 4);

-- Project2
INSERT INTO management.projects (project_id, name, description, created_by_user_id) 
VALUES ('BANK_APP', 'Mobile Banking App', 'App ngân hàng iOS/Android', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11');

INSERT INTO management.project_members (project_id, user_id, project_role) VALUES
('BANK_APP', '1fc4746d-1ab4-4ab2-9c2c-d8833eae8877', 'Project Admin'),
('BANK_APP', '1af275c6-1511-4190-8c16-49728c45bb08', 'Member');

INSERT INTO management.test_suites (suite_id, project_id, parent_suite_id, name) VALUES
('SUITE_BK_01', 'BANK_APP', NULL, 'Money Transfer Feature');

INSERT INTO management.test_cases (case_id, suite_id, name, priority, case_type, description, tags, assignee_id, fullscreen_page_name, created_by) 
VALUES (3, 'SUITE_BK_01', 'Transfer 24/7 Success', 'Critical', 'automated', 'Chuyển tiền liên ngân hàng', ARRAY['core', 'api'], 'b0eebc99-9c0b-4ef8-bb6d-6bb9bd380b22', 'TransferPage', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11');

INSERT INTO management.test_steps (case_id, step_order, action, locator_type, locator_value, value, expected) VALUES
(3, 1, 'type', 'xpath', '//input[@name="account_no"]', '1900123456', NULL),
(3, 2, 'type', 'xpath', '//input[@name="amount"]', '500000', NULL),
(3, 3, 'click', 'id', 'btn-confirm', NULL, 'OTP Screen appears');

-- Project3
INSERT INTO management.projects (project_id, name, description, created_by_user_id) 
VALUES ('HRM_TOOL', 'Internal HRM', 'Hệ thống chấm công nội bộ', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11');

INSERT INTO management.project_members (project_id, user_id, project_role) VALUES
('HRM_TOOL', '1fc4746d-1ab4-4ab2-9c2c-d8833eae8877', 'Project Admin'),
('HRM_TOOL', '193a42cc-a90e-45a7-b7ac-e905f2c90ffa', 'Member');

INSERT INTO management.test_suites (suite_id, project_id, parent_suite_id, name) VALUES
('SUITE_HR_01', 'HRM_TOOL', NULL, 'Employee Onboarding');

INSERT INTO management.test_cases (case_id, suite_id, name, priority, case_type, description, tags, assignee_id, created_by) 
VALUES (4, 'SUITE_HR_01', 'Create New Employee', 'Medium', 'manual', 'Nhập thông tin nhân viên mới', ARRAY['admin'], 'c0eebc99-9c0b-4ef8-bb6d-6bb9bd380c33', 'c0eebc99-9c0b-4ef8-bb6d-6bb9bd380c33');

INSERT INTO management.test_steps (case_id, step_order, action, locator_value, value, expected) VALUES
(4, 1, 'instruction', NULL, 'Login as Admin -> Go to Employee Menu -> Click Add New', 'Form Add New Employee opens');


-- Cập nhật bộ đếm tự động của PostgreSQL
SELECT setval('management.test_cases_case_id_seq', (SELECT MAX(case_id) FROM management.test_cases));
SELECT setval('management.test_steps_step_id_seq', (SELECT MAX(step_id) FROM management.test_steps));