// src/routes/routes.js
const ROUTES = {
  LOGIN: "/login",
  SIGNUP: "/signup",
  DASHBOARD: "/dashboard",
  PROJECTS: "/projects",
  PROJECT_DETAIL: "/projects/:id",
  TEST_CASES: "/projects/:projectId/suites/:suiteId/test-cases",
  KNOWLEDGE_BASE: "/knowledge-base",
  KNOWLEDGE_BASE_DETAIL: "/knowledge-base/:id",
};

export default ROUTES;
