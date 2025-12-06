INSERT INTO core.roles (role_id, role_name, description) VALUES
(1, 'Admin', 'Quản trị viên hệ thống'),
(2, 'Test Manager', 'Quản lý kiểm thử'),
(3, 'Test Engineer', 'Kỹ sư kiểm thử');

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

INSERT INTO core.users (user_id, fullname, username, email, password_hash, is_active) VALUES
('1fc4746d-1ab4-4ab2-9c2c-d8833eae8877', 'Nguyen Van A', 'admin_a', 'admin@company.com', '$2b$12$r0fZG8GG3Y2pyxZ7NjTd0.ibHcF15HnnudT1dcex.DObcMsdx4aye', TRUE),
('1af275c6-1511-4190-8c16-49728c45bb08', 'Tran Thi B', 'manager_b', 'manager@company.com', '$2b$12$qZn4X7rL5.Tz/VSQnEn3Tuoh5N/NOqfzmnpg52MeB3TSrIXppElDy', TRUE),
('193a42cc-a90e-45a7-b7ac-e905f2c90ffa', 'Le Van C', 'tester_c', 'tester@company.com', '$2b$12$PO3DvOBekoGS3rJadZiPyO/hPR9oR7YyUAwXBD8HW550hhbUgWWQm', TRUE);

INSERT INTO core.user_roles (user_id, role_id) VALUES
('1fc4746d-1ab4-4ab2-9c2c-d8833eae8877', 1), 
('1af275c6-1511-4190-8c16-49728c45bb08', 2), 
('193a42cc-a90e-45a7-b7ac-e905f2c90ffa', 3); 
-- Project1
INSERT INTO management.projects (project_id, name, description, created_by_user_id) 
VALUES ('ECOM_WEB', 'E-Commerce Website', 'Trang bán hàng online', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11');

INSERT INTO management.project_members (project_id, user_id, project_role) VALUES
('ECOM_WEB', '1fc4746d-1ab4-4ab2-9c2c-d8833eae8877', 'Project Admin'),
('ECOM_WEB', '1af275c6-1511-4190-8c16-49728c45bb08', 'Member'),
('ECOM_WEB', '193a42cc-a90e-45a7-b7ac-e905f2c90ffa', 'Member');

INSERT INTO management.test_suites (suite_id, project_id, parent_suite_id, name) VALUES
('SUITE_EC_01', 'ECOM_WEB', NULL, 'Authentication Module'),
('SUITE_EC_02', 'ECOM_WEB', NULL, 'Checkout Module');

INSERT INTO management.test_cases (case_id, suite_id, name, priority, case_type, description, tags, assignee_id, created_by) 
VALUES (1, 'SUITE_EC_01', 'Verify Login UI', 'Low', 'manual', 'Check input fields', ARRAY['ui'], 'c0eebc99-9c0b-4ef8-bb6d-6bb9bd380c33', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11');

INSERT INTO management.test_cases (case_id, suite_id, name, priority, case_type, description, tags, assignee_id, fullscreen_page_name, created_by) 
VALUES (2, 'SUITE_EC_01', 'Login Success Flow', 'High', 'automated', 'Login with valid user', ARRAY['smoke'], 'b0eebc99-9c0b-4ef8-bb6d-6bb9bd380b22', 'LoginPage', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11');

INSERT INTO management.test_steps (case_id, step_order, action, locator_type, locator_value, value, expected, url) VALUES
(2, 1, 'open', NULL, NULL, NULL, 'Page loaded', 'https://ecom.demo/login'),
(2, 2, 'type', 'id', 'user_input', 'autodev@company.com', NULL, NULL),
(2, 3, 'type', 'id', 'pass_input', '123456', NULL, NULL),
(2, 4, 'click', 'css', 'button.btn-login', NULL, 'Redirect to Home', NULL);

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