// src/pages/TestCases/TestCaseDetailPage.jsx
import React, { useEffect, useState } from "react";
import { useParams, useLocation } from "react-router-dom";
import { Pencil, Trash, Play, MoreHorizontal, X , CheckCircle2, AlertTriangle} from "lucide-react";
import { formatDate } from "../../utils/formatDate";
import testCaseService from "../../services/testCaseService";
import ConfirmModal from "../../components/common/ConfirmModal";
import CreateTestCaseModal from "../../components/test-cases/CreateTestCaseModal";

export default function TestCaseDetailPage() {
  const { projectId, suiteId, caseId } = useParams();
  const location = useLocation();

  const suiteName = location.state?.suiteName || suiteId;
  const projectName = location.state?.projectName || "Project";

  const [testCase, setTestCase] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [running, setRunning] = useState(false); // trạng thái đang run

  const [isDeleteStepOpen, setIsDeleteStepOpen] = useState(false);
  const [stepToDelete, setStepToDelete] = useState(null);

  const [isEditInfoOpen, setIsEditInfoOpen] = useState(false);
  // ====== STATE POPUP ADD STEP ======
  const [isAddStepOpen, setIsAddStepOpen] = useState(false);
  const [editingStep, setEditingStep] = useState(null);

  // Hàm xử lý cập nhật thông tin (Sau khi Modal bấm Save)
  const handleUpdateInfo = async (payload) => {
    if (!testCase) return;
    const testCaseId = testCase.case_id || testCase.id || caseId;

    // 1. Gọi API Update (Service đã viết ở bài trước)
    await testCaseService.updateTestCase(testCaseId, payload);

    // 2. Cập nhật giao diện (Merge thông tin mới vào state hiện tại)
    setTestCase((prev) => ({
      ...prev,
      ...payload, // Ghi đè các trường mới (name, priority, etc.)
      tags: payload.tags, // Đảm bảo tags được cập nhật
      // Lưu ý: Nếu backend trả về object đầy đủ sau khi update thì tốt nhất là setTestCase(res.data)
    }));
  };

  // ====== RUN TEST CASE ======
  const handleRunTestCase = async () => {
    try {
      if (!testCase) return;

      const testCaseId = testCase.case_id || testCase.id || caseId;
      console.log(">>> Run test case detail với id =", testCaseId);

      if (!testCaseId) {
        alert("Không xác định được test case id");
        return;
      }

      setRunning(true);

      const res = await testCaseService.runTestCase(testCaseId);
      console.log("Run testcase (detail) OK:", res);

      alert("Run test case thành công!");
    } catch (err) {
      console.error("Run testcase (detail) ERROR:", err);
      console.error("Response:", err.response?.status, err.response?.data);
      alert("Run test case thất bại. Vui lòng thử lại.");
    } finally {
      setRunning(false);
    }
  };

  // ====== CREATE STEP ======
  const handleCreateStep = async (stepPayload) => {
    try {
      if (!testCase) return;

      const testCaseId = testCase.case_id || testCase.id || caseId;

      if (!testCaseId) {
        alert("Không xác định được test case id để tạo step");
        return;
      }

      // Gọi qua proxy giống các API khác (tránh CORS)
      const token = localStorage.getItem("access_token");
      const res = await fetch(`/api/v1/cases/${testCaseId}/steps`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(stepPayload),
      });

      const data = await res.json().catch(() => null);

      if (!res.ok) {
        const msg =
          data?.error ||
          data?.message ||
          "Tạo test step thất bại. Vui lòng thử lại.";
        alert(msg);
        return;
      }

      // Thêm step mới vào state để bảng tự cập nhật
      setTestCase((prev) => {
        const oldSteps = Array.isArray(prev?.steps) ? prev.steps : [];
        return {
          ...prev,
          steps: [...oldSteps, data],
        };
      });

      setIsAddStepOpen(false);
    } catch (err) {
      console.error("Create step error:", err);
      alert("Tạo test step thất bại. Vui lòng thử lại.");
    }
  };

  // Hàm mở modal để TẠO MỚI
  const openCreateStepModal = () => {
    setEditingStep(null); // Reset về null
    setIsAddStepOpen(true);
  };

  // Hàm mở modal để SỬA
  const openEditStepModal = (step) => {
    setEditingStep(step); // Lưu step cần sửa
    setIsAddStepOpen(true);
  };

  // Hàm xử lý chung: Nếu có editingStep thì là Update, không thì là Create
  const handleSaveStep = async (payload) => {
    if (!testCase) return;
    
    const testCaseId = testCase.case_id || testCase.id || caseId;

    // === TRƯỜNG HỢP 1: UPDATE (Sửa Step) ===
    if (editingStep) {
      const stepId = editingStep.step_id || editingStep.id || editingStep._id;
      
      // 1. Gọi API Update
      await testCaseService.updateTestStep(stepId, payload);

      // 2. Cập nhật State (Tìm và sửa item trong mảng)
      setTestCase((prev) => ({
        ...prev,
        steps: prev.steps.map((s) => 
          (s.step_id || s.id || s._id) === stepId 
            ? { ...s, ...payload } 
            : s
        ),
      }));
    } 
    
    // === TRƯỜNG HỢP 2: CREATE (Tạo Step mới)  ===
    else {
      // 1. Gọi API qua Service 
      const res = await testCaseService.createTestStep(testCaseId, payload);
      
      // Lấy data chuẩn (đề phòng axios interceptor trả về res hoặc res.data)
      const newData = res.data || res;

      if (!newData) {
        throw new Error("API không trả về dữ liệu.");
      }

      // 2. Cập nhật State (Thêm vào cuối danh sách)
      setTestCase((prev) => ({
        ...prev,
        steps: [...(prev.steps || []), newData],
      }));
    }
  };

  // ===== FETCH DETAIL =====
  useEffect(() => {
    async function fetchDetail() {
      try {
        setLoading(true);
        setError("");
        const data = await testCaseService.getTestCaseById(caseId);
        setTestCase(data || null);
      } catch (err) {
        console.error(err);
        setError("Không thể tải chi tiết test case. Vui lòng thử lại.");
        setTestCase(null);
      } finally {
        setLoading(false);
      }
    }

    if (caseId) {
      fetchDetail();
    }
  }, [caseId]);

  const openDeleteStepConfirm = (step) => {
    setStepToDelete(step);
    setIsDeleteStepOpen(true);
  };

  const handleConfirmDeleteStep = async () => {
    if (!stepToDelete) return;
    
    const stepId = stepToDelete.step_id;

    if (!stepId) {
      console.error("Lỗi: Không tìm thấy ID của step này", stepToDelete);
      throw new Error("Step ID is missing");
    }

    try {
      await testCaseService.deleteTestStep(stepId);

      setTestCase((prev) => ({
        ...prev,
        steps: prev.steps.filter((s) => {
            const sId = s.step_id;
            return String(sId) !== String(stepId);
        }),
      }));

    } catch (err) {
      console.error("Delete step failed:", err);
      throw err; 
    }
  };

  // ===== LOADING / ERROR =====
  if (loading) {
    return (
      <p className="text-sm text-slate-500">Đang tải chi tiết test case...</p>
    );
  }

  if (error) {
    return <p className="text-sm text-red-500">{error}</p>;
  }

  if (!testCase) {
    return (
      <p className="text-sm text-slate-500 italic">
        Không tìm thấy test case.
      </p>
    );
  }

  // ===== MAP DATA TỪ API =====
  const title = testCase.name || "—";
  const priority = testCase.priority || "—";

  const steps = Array.isArray(testCase.steps) ? testCase.steps : [];
  const type = steps.length > 0 ? "Automated" : "Manual";

  const description = testCase.description || "Không có mô tả.";
  const author = testCase.assigneer_username || "—";

  const createdAt = testCase.created_at
    ? formatDate(testCase.created_at)
    : "—";
  const updatedAt = testCase.updated_at
    ? formatDate(testCase.updated_at)
    : "—";

  const priorityColor =
    priority.toLowerCase() === "high"
      ? "bg-rose-50 text-rose-500 border border-rose-100"
      : priority.toLowerCase() === "medium"
      ? "bg-amber-50 text-amber-600 border border-amber-100"
      : priority.toLowerCase() === "low"
      ? "bg-emerald-50 text-emerald-600 border border-emerald-100"
      : "bg-slate-50 text-slate-500 border border-slate-100";

  // Run info
  const rawStatus = testCase.last_run_status;
  const lastRunStatus = rawStatus || "—";
  const statusLower = (rawStatus || "").toLowerCase();
  const statusCls =
    statusLower === "passed"
      ? "bg-emerald-50 text-emerald-600 border border-emerald-100"
      : statusLower === "failed"
      ? "bg-rose-50 text-rose-500 border border-rose-100"
      : "bg-slate-50 text-slate-500 border border-slate-100";

  const lastRunAt = testCase.last_run_at
    ? formatDate(testCase.last_run_at)
    : "—";

  // App info từ response
  const appVersion = testCase.app_version || "—";
  const buildVersion = testCase.build_version || "—";
  const gitHash = testCase.git_hash || "—";
  const pagePath = testCase.fullscreen_page_name || "—";

  const tags = Array.isArray(testCase.tags) ? testCase.tags : [];

  return (
    <div className="space-y-4">
      {/* HEADER */}
      <div className="flex items-center justify-between">
        <div>
          <div className="text-xs text-slate-500">
            Projects <span className="mx-1">›</span>
            <span className="text-slate-600">{projectName}</span>
            <span className="mx-1">›</span>
            <span className="text-slate-600">Test Suites</span>
            <span className="mx-1">›</span>
            <span className="text-slate-600">{suiteName}</span>
            <span className="mx-1">›</span>
            <span className="text-primary font-medium">{title}</span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button className="flex items-center rounded-full border border-slate-200 px-4 py-2 text-xs font-medium bg-white hover:bg-slate-50"
          onClick={() => setIsEditInfoOpen(true)}
          >
            Edit
          </button>
          <button
            className="inline-flex items-center gap-1 rounded-full bg-primary px-4 py-2 text-xs font-medium text-white hover:bg-primary/90 disabled:opacity-50"
            onClick={handleRunTestCase}
            disabled={running}
          >
            <Play className="h-3 w-3" />
            {running ? "Running..." : "Run Test Case"}
          </button>
          <button className="h-8 w-8 flex items-center justify-center rounded-full border border-slate-200 bg-white hover:bg-slate-50">
            <MoreHorizontal className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* GRID 2 COLUMNS: General + Side info */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,3fr)_minmax(260px,1.2fr)]">
        {/* MAIN COLUMN (General info) */}
        <div className="space-y-4">
          {/* CARD INFO */}
          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            {/* Name */}
            <h1 className="text-xl font-semibold text-slate-800 mb-4">
              {title}
            </h1>

            {/* Priority + Type + Tags */}
            <div className="flex flex-wrap items-center gap-3 mb-6">
              <span
                className={`px-3 py-0.5 rounded-full text-xs font-medium ${priorityColor}`}
              >
                Priority: {priority}
              </span>

              <span className="px-3 py-0.5 rounded-full border border-slate-200 bg-slate-50 text-xs font-medium text-slate-600">
                {type}
              </span>

              {tags.map((tag) => (
                <span
                  key={tag}
                  className="px-3 py-0.5 rounded-full border border-slate-200 bg-slate-50 text-[11px] font-medium text-slate-600"
                >
                  #{tag}
                </span>
              ))}
            </div>

            {/* DESCRIPTION */}
            <div className="mb-6">
              <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
                DESCRIPTION
              </h3>
              <p className="text-sm text-slate-700 leading-relaxed">
                {description}
              </p>
            </div>

            {/* META FIELDS */}
            <div className="border-t border-slate-100 pt-4 space-y-2 text-xs text-slate-700">
              <div className="flex justify-between">
                <span className="text-slate-400">Assignee:</span>
                <span className="font-medium">{author}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Created:</span>
                <span>{createdAt}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Updated:</span>
                <span>{updatedAt}</span>
              </div>
            </div>
          </div>
        </div>

        {/* SIDE COLUMN (Application + Run info) */}
        <div className="space-y-4">
          {/* Application Info */}
          <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Application Info
            </h3>
            <div className="mt-3 space-y-2 text-xs">
              <div className="flex justify-between">
                <span className="text-slate-400">App version</span>
                <span>{appVersion}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Build version</span>
                <span>{buildVersion}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Git hash</span>
                <span className="font-mono text-[11px]">{gitHash}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Page</span>
                <span className="text-[11px]">{pagePath}</span>
              </div>
            </div>
          </div>

          {/* Run Info */}
          <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Run Information
            </h3>
            <div className="mt-3 space-y-2 text-xs">
              <div className="flex justify-between">
                <span className="text-slate-400">Last Run Status</span>
                <span className={`px-3 py-0.5 rounded-full ${statusCls}`}>
                  {lastRunStatus}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Last Run At</span>
                <span>{lastRunAt}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* FULL WIDTH TEST STEPS */}
      <div className="rounded-2xl border border-slate-200 bg-white shadow-sm mt-2 p-0 w-full">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200">
          <h2 className="text-sm font-semibold text-slate-800">Test Steps</h2>
          <button
            className="rounded-full bg-slate-900 px-4 py-1.5 text-xs text-white hover:bg-slate-800"
            onClick={openCreateStepModal}
          >
            + Add Step
          </button>
        </div>

        {/* Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead className="bg-slate-50 text-[11px] font-semibold uppercase tracking-wide text-slate-500 border-b border-slate-200">
              <tr>
                <th className="px-4 py-3 text-left w-16">Step #</th>
                <th className="px-4 py-3 text-left">Action</th>
                <th className="px-4 py-3 text-left w-32">Locator Type</th>
                <th className="px-4 py-3 text-left w-44">Locator Value</th>
                <th className="px-4 py-3 text-left w-32">URL</th>
                <th className="px-4 py-3 text-left w-60">Expected Result</th>
                <th className="px-4 py-3 text-right w-24">Actions</th>
              </tr>
            </thead>

            <tbody className="divide-y divide-slate-100">
              {steps.length === 0 ? (
                <tr>
                  <td
                    colSpan={7}
                    className="px-6 py-6 text-center text-slate-500 italic"
                  >
                    Chưa có step nào
                  </td>
                </tr>
              ) : (
                steps.map((step, index) => (
                  <tr key={step.step_id || index}>
                    <td className="px-4 py-3 text-slate-500">
                      {step.step_order ?? index + 1}
                    </td>
                    <td className="px-4 py-3">{step.action || "—"}</td>
                    <td className="px-4 py-3">{step.locator_type || "—"}</td>
                    <td className="px-4 py-3">{step.locator_value || "—"}</td>
                    <td className="px-4 py-3">{step.url || "—"}</td>
                    <td className="px-4 py-3">{step.expected || "—"}</td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex justify-end gap-1">
                        <button className="h-7 w-7 flex items-center justify-center rounded-full border border-slate-200 hover:bg-slate-50"
                        onClick={() => openEditStepModal(step)}
                        >
                          <Pencil className="h-3.5 w-3.5" />
                        </button>
                        <button className="h-7 w-7 flex items-center justify-center rounded-full border border-slate-200 hover:bg-slate-50"
                        onClick={() => openDeleteStepConfirm(step)}
                        >
                          <Trash className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* POPUP ADD STEP */}
      <AddStepModal
        isOpen={isAddStepOpen}
        onClose={() => setIsAddStepOpen(false)}
        onSubmit={handleSaveStep}        // Gọi hàm save chung
        stepNumber={steps.length + 1}
        stepData={editingStep}           // Truyền dữ liệu cần sửa
/>
      {/* ✅ MODAL CONFIRM DELETE STEP (Mới thêm) */}
      <ConfirmModal
        isOpen={isDeleteStepOpen}
        onCancel={() => setIsDeleteStepOpen(false)}
        onConfirm={handleConfirmDeleteStep}
        title="Delete Test Step"
        message="Are you sure you want to delete this test step?"
        successTitle="Deleted Successfully"
        successMessage="The test step has been removed."
        forbiddenTitle="Permission Denied"
        forbiddenMessage="You do not have permission to delete this step."
      />

      <CreateTestCaseModal
        isOpen={isEditInfoOpen}
        onClose={() => setIsEditInfoOpen(false)}
        
        // Truyền dữ liệu hiện tại để form tự điền
        testCaseData={testCase} 
        
        // Hàm xử lý khi bấm Save
        onUpdate={handleUpdateInfo}
        
        // SuiteId (nếu cần validate, nhưng edit thì ko quan trọng lắm)
        suiteId={suiteId}
      />
    </div>
  );
}

/**
 * Modal Add Step
 */
function AddStepModal({ isOpen, onClose, onSubmit, stepData, stepNumber = 1 }) {
  const isEditMode = !!stepData;

  const [step, setStep] = useState("form"); // "form" | "success"
  const [loading, setLoading] = useState(false);
  const [apiError, setApiError] = useState("");

  const [action, setAction] = useState("");
  const [locatorType, setLocatorType] = useState("ID");
  const [locatorValue, setLocatorValue] = useState("");
  const [value, setValue] = useState("");
  const [url, setUrl] = useState("");
  const [expected, setExpected] = useState("");

  useEffect(() => {
    if (isOpen) {
      setStep("form");
      setLoading(false);
      setApiError("");

      if (isEditMode) {
        // --- EDIT MODE: Điền dữ liệu cũ ---
        setAction(stepData.action || "");
        setLocatorType(stepData.locator_type || "ID");
        setLocatorValue(stepData.locator_value || "");
        setValue(stepData.value || "");
        setUrl(stepData.url || "");
        setExpected(stepData.expected || "");
      } else {
        // --- CREATE MODE: Reset form ---
        setAction("");
        setLocatorType("ID");
        setLocatorValue("");
        setValue("");
        setUrl("");
        setExpected("");
      }
    }
  }, [isOpen, stepData, isEditMode]);

  if (!isOpen) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!action.trim()) {
      alert("Action is required");
      return;
    }
    if (!expected.trim()) {
      alert("Expected Result is required");
      return;
    }

    const payload = {
      action: action.trim(),
      locator_type: locatorType,
      locator_value: locatorValue.trim(),
      value: value.trim() || null,
      url: url.trim() || null,
      expected: expected.trim(),

      ...(isEditMode && { new_order: stepData.step_order }),
    };

    try {
      setLoading(true);
      
      // Gọi hàm từ cha (Cha chỉ cần update state, không cần alert)
      await onSubmit(payload);
      
      // Thành công -> Chuyển sang màn hình tích xanh
      setStep("success"); 

    } catch (err) {
      console.error(err);
      setApiError(err.message || "An error occurred.");
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    onClose();
  };

  return (
    <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/30 backdrop-blur-[2px]">
      <div className="relative w-full max-w-4xl rounded-3xl bg-white p-6 shadow-2xl transition-all">
        
        {/* ===================== STEP 1: FORM ===================== */}
        {step === "form" && (
          <>
            <button
              type="button"
              onClick={handleClose}
              disabled={loading}
              className="absolute right-5 top-5 text-slate-400 hover:text-red-500"
            >
              <X className="h-5 w-5" />
            </button>

            <h2 className="mb-4 text-2xl font-semibold text-[#6425FE]">
              {isEditMode ? `Edit Step #${stepData.step_order}` : `Add Step #${stepNumber}`}
            </h2>

            <form className="space-y-4" onSubmit={handleSubmit}>
              {apiError && (
                <div className="flex items-center gap-2 rounded-lg bg-red-50 p-3 text-sm text-red-600 border border-red-100">
                  <span className="font-bold">Error:</span> {apiError}
                </div>
              )}

              {/* Action */}
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-800">
                  Action <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  placeholder="Enter action (e.g. Click, Type Text)..."
                  value={action}
                  onChange={(e) => setAction(e.target.value)}
                  disabled={loading}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm outline-none focus:border-[#6425FE] focus:ring-2 focus:ring-[#6425FE]/20"
                />
              </div>

              {/* Locator Type + Value */}
              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <label className="mb-1 block text-sm font-medium text-slate-800">Locator Type</label>
                  <select
                    value={locatorType}
                    onChange={(e) => setLocatorType(e.target.value)}
                    disabled={loading}
                    className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm outline-none focus:border-[#6425FE] focus:ring-2 focus:ring-[#6425FE]/20"
                  >
                    <option value="ID">ID</option>
                    <option value="XPATH">XPath</option>
                    <option value="CSS">CSS Selector</option>
                    <option value="NAME">Name</option>
                    <option value="CLASS_NAME">Class Name</option>
                    <option value="TAG_NAME">Tag Name</option>
                    <option value="LINK_TEXT">Link Text</option>
                  </select>
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium text-slate-800">Locator Value</label>
                  <input
                    type="text"
                    value={locatorValue}
                    onChange={(e) => setLocatorValue(e.target.value)}
                    disabled={loading}
                    className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm outline-none focus:border-[#6425FE] focus:ring-2 focus:ring-[#6425FE]/20"
                  />
                </div>
              </div>

              {/* Value + URL */}
              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <label className="mb-1 block text-sm font-medium text-slate-800">Value</label>
                  <input
                    type="text"
                    value={value}
                    onChange={(e) => setValue(e.target.value)}
                    disabled={loading}
                    className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm outline-none focus:border-[#6425FE] focus:ring-2 focus:ring-[#6425FE]/20"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium text-slate-800">URL</label>
                  <input
                    type="text"
                    value={url}
                    onChange={(e) => setUrl(e.target.value)}
                    disabled={loading}
                    className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm outline-none focus:border-[#6425FE] focus:ring-2 focus:ring-[#6425FE]/20"
                  />
                </div>
              </div>

              {/* Expected */}
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-800">
                  Expected Result <span className="text-red-500">*</span>
                </label>
                <textarea
                  rows={3}
                  value={expected}
                  onChange={(e) => setExpected(e.target.value)}
                  disabled={loading}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm outline-none focus:border-[#6425FE] focus:ring-2 focus:ring-[#6425FE]/20"
                />
              </div>

              {/* Buttons */}
              <div className="mt-6 flex items-center justify-end gap-3 border-t border-slate-200 pt-4">
                <button
                  type="button"
                  onClick={handleClose}
                  disabled={loading}
                  className="rounded-full border border-slate-300 px-5 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100 disabled:opacity-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={loading}
                  className="rounded-full bg-[#6425FE] px-6 py-2 text-sm font-semibold text-white hover:bg-[#5621d6] disabled:opacity-70 flex items-center gap-2"
                >
                  {loading && <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent"></span>}
                  {isEditMode ? "Save Changes" : "Create"}
                </button>
              </div>
            </form>
          </>
        )}

        {/* ===================== STEP 2: SUCCESS ===================== */}
        {step === "success" && (
          <div className="flex flex-col items-center text-center py-8 animate-in fade-in zoom-in duration-200">
            {/* Icon Tích Xanh (CheckCircle2) */}
            <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-[#6425fe15]">
              <CheckCircle2 className="h-10 w-10 text-[#6425FE]" />
            </div>

            <h2 className="text-xl font-semibold text-[#6425FE] mb-2">
              {isEditMode ? "Updated Successfully!" : "Created Successfully!"}
            </h2>

            <p className="text-sm text-slate-600 mb-6">
              The test step has been saved to the system.
            </p>

            <div className="w-full border-t border-slate-100 mb-6" />

            <button
              className="px-6 py-2 rounded-full text-sm font-medium text-white bg-[#6425FE] hover:bg-[#5621d6] transition-colors"
              onClick={handleClose}
            >
              OK, Close
            </button>
          </div>
        )}

      </div>
    </div>
  );
}