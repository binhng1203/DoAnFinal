// src/services/projectService.js
import apiClient from "../services/apiClient";

const projectService = {
  // Lấy danh sách project
  async getProjects() {
    // GET http://localhost:8002/api/v1/projects
    return apiClient.get("/api/v1/projects");
  },

  // Tạo project
  async createProject(payload) {
    const body = {
      project_id: payload.code,
      name: payload.name,
      description: payload.description,
      repo_url: payload.repo_url,
    };
    // POST http://localhost:8002/api/v1/projects
    return apiClient.post("/api/v1/projects", body);
  },

  // Lấy chi tiết project
  async getProjectDetail(projectId) {
    // GET http://localhost:8002/api/v1/projects/{PROJECT_ID}
    return apiClient.get(`/api/v1/projects/${projectId}`);
  },

  // Cập nhật project
  async updateProject(projectId, payload) {
    const body = {
      name: payload.name,
      description: payload.description,
      repo_url: payload.repo_url,
    };
    // PUT: http://localhost:8002/api/v1/projects/{PROJECT_ID}
    return apiClient.put(`/api/v1/projects/${projectId}`, body);
  },

  // Xoá Project
  async deleteProject(projectId) {
    // DELETE /api/v1/projects/{projectId}
    return apiClient.delete(`/api/v1/projects/${projectId}`);
  },

  // Lấy Test Suite của project
  async getTestSuites(projectId) {
    // GET http://localhost:8002/api/v1/projects/{projectId}/suites
    return apiClient.get(`/api/v1/projects/${projectId}/suites`);
  },

  // Tạo Test Suite
  async createTestSuite(projectId, payload) {
    // POST http://localhost:8002/api/v1/projects/ProjectID/suites
    return apiClient.post(`/api/v1/projects/${projectId}/suites`, payload);
  },

  // Sửa Test Suite
  async updateTestSuite(suiteId, payload) {
    // PUT /api/v1/suites/{suiteId}
    return apiClient.put(`/api/v1/suites/${suiteId}`, payload);
  },

  // Xoá Test Suite
  async deleteTestSuite(suiteId) {
    // DELETE /api/v1/suites/{suiteId}
    return apiClient.delete(`/api/v1/suites/${suiteId}`);
  },

  // Lấy danh sách member của project
  async getProjectMembers(projectId) {
    // GET http://localhost:8002/api/v1/projects/{projectId}/members
    return apiClient.get(`/api/v1/projects/${projectId}/members`);
  },

  // Thêm thành viên vào project
  async addMember(projectId, payload) {
    // POST http://localhost:8002/api/v1/projects/{projectId}/members
    // payload: { username: "...", role: "Member" }
    return apiClient.post(`/api/v1/projects/${projectId}/members`, payload);
  },

  async removeMember(projectId, userId) {
    // DELETE http://localhost:8002/api/v1/projects/{projectId}/members/{userId}
    return apiClient.delete(`/api/v1/projects/${projectId}/members/${userId}`);
  },

  async joinProject(projectCode) {
    return Promise.resolve();
  },
};

export default projectService;
