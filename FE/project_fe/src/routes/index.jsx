// src/routes/index.jsx
import React from "react";
import { useRoutes, Navigate } from "react-router-dom";
import MainLayout from "../layouts/MainLayout";
import Dashboard from "../pages/Dashboard/Dashboard.jsx";
import ProjectsPage from "../pages/Projects/ProjectsPage.jsx";
import ProjectDetailPage from "../pages/Projects/ProjectDetailPage.jsx";
import LoginPage from "../pages/LoginPage/LoginPage.jsx";
import SignupPage from "../pages/SignupPage/SignupPage.jsx";
import KnowledgeBasePage from "../pages/KnowledgeBase/KnowledgeBasePage.jsx";
import KnowledgeBaseDetailPage from "../pages/KnowledgeBase/KnowledgeBaseDetailPage.jsx";
import TestCaseDetailPage from "../pages/TestCases/TestCaseDetailPage";
import TestCaseListPage from "../pages/TestCases/TestCaseListPage.jsx";

export default function AppRoutes() {
  const element = useRoutes([
    {
      path: "/login",
      element: <LoginPage />,
    },
    {
      path: "/signup",
      element: <SignupPage />,
    },
    {
      path: "/",
      element: <MainLayout />, // LAYOUT CHÍNH
      children: [
        { index: true, element: <Navigate to="/login" replace /> },
        { path: "dashboard", element: <Dashboard /> },
        { path: "projects", element: <ProjectsPage /> },
        { path: "projects/:id", element: <ProjectDetailPage /> },

        {
          path: "projects/:projectId/suites/:suiteId/test-cases",
          element: <TestCaseListPage />,
        },
        {
          path: "/projects/:projectId/suites/:suiteId/test-cases/:caseId",
          element: <TestCaseDetailPage />,
        },

        { path: "knowledge-base", element: <KnowledgeBasePage /> },
        { path: "knowledge-base/:id", element: <KnowledgeBaseDetailPage /> },
      ],
    },
  ]);

  return element;
}
