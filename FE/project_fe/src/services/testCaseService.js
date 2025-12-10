// src/services/testCaseService.js
import apiClient from "../services/apiClient";

const testCaseService = {
  // Lấy danh sách test case theo suite
  async getTestCases(suiteId) {
    return apiClient.get(`/api/v1/suites/${suiteId}/cases`);
  },

  // Lấy chi tiết 1 test case
  async getTestCaseById(caseId) {
    return apiClient.get(`/api/v1/cases/${caseId}`);
  },

  // Tạo test case mới
  async createTestCase(suiteId, body) {
    return apiClient.post(`/api/v1/suites/${suiteId}/cases`, body);
  },

  // Sửa Test Case
  async updateTestCase(caseId, payload) {
    // PUT /api/v1/cases/{caseId}
    return apiClient.put(`/api/v1/cases/${caseId}`, payload);
  },

  // Xoá test case
  async deleteTestCase(caseId) {
    // DELETE /api/v1/cases/{caseId}
    return apiClient.delete(`/api/v1/cases/${caseId}`);
  },

  // Run 1 test case
  async runTestCase(testCaseId) {
    return apiClient.post(
      "/run_testcase",
      { test_case_id: String(testCaseId) },
      { timeout: 600000 }   // 10 minutes
    );
  },

  // Tạo Test Step
  async createTestStep(caseId, payload) {
    // POST /api/v1/cases/{caseId}/steps
    return apiClient.post(`/api/v1/cases/${caseId}/steps`, payload);
  },
  // Sửa Test Step
  async updateTestStep(stepId, payload) {
    // PUT /api/v1/steps/{stepId}
    return apiClient.put(`/api/v1/steps/${stepId}`, payload);
  },

  // Xoá Test Step
  async deleteTestStep(stepId) {
    // DELETE /api/v1/steps/{stepId}
    return apiClient.delete(`/api/v1/steps/${stepId}`);
  },
};

export default testCaseService;