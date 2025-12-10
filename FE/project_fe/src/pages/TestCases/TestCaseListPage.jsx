import React, { useEffect, useState } from "react";
import { Search, Pencil, Trash, Play } from "lucide-react";
import { formatDate } from "../../utils/formatDate";
import testCaseService from "../../services/testCaseService";
import { useParams, useLocation, useNavigate } from "react-router-dom";
import CreateTestCaseModal from "../../components/test-cases/CreateTestCaseModal";
import ConfirmModal from "../../components/common/ConfirmModal";

export default function TestCaseListPage() {
  const { projectId, suiteId } = useParams();
  const location = useLocation();
  const navigate = useNavigate();

  const suiteName = location.state?.suiteName || suiteId;
  const projectName = location.state?.projectName || "Project";

  const [testCases, setTestCases] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const pageSize = 10;

  const [runningId, setRunningId] = useState(null);

  const [isDeleteOpen, setIsDeleteOpen] = useState(false);
  const [caseToDelete, setCaseToDelete] = useState(null);

  const [editingTestCase, setEditingTestCase] = useState(null);

  // Hàm mở modal để TẠO
  const openCreateModal = () => {
    setEditingTestCase(null);
    setIsCreateOpen(true);
  };

  // Hàm mở modal để SỬA
  const openEditModal = (tc) => {
    setEditingTestCase(tc);
    setIsCreateOpen(true);
  };

  // Xử lý tạo mới (giữ logic cũ nhưng chuyển vào đây)
  const handleCreateTestCase = async (payload) => {
    // 1. Gọi API Create
    const res = await testCaseService.createTestCase(suiteId, payload);
    const newData = res.data || res;

    // 2. Cập nhật State (Thêm vào đầu danh sách)
    setTestCases(prev => [newData, ...prev]);
  };

  // Xử lý cập nhật (Mới)
  const handleUpdateTestCase = async (payload) => {
    if (!editingTestCase) return;
    const caseId = editingTestCase.case_id || editingTestCase.id;

    // 1. Gọi API Update
    await testCaseService.updateTestCase(caseId, payload);

    // 2. Cập nhật State (Tìm và sửa item trong mảng)
    setTestCases(prev => prev.map(tc => 
      (tc.case_id || tc.id) === caseId ? { ...tc, ...payload } : tc
    ));
  };

  // ============================================================
  // RUN TEST CASE
  // ============================================================
  const handleRunTestCase = async (testCaseId) => {
    try {
      console.log(">>> Gửi run_testcase với id =", testCaseId);
      if (!testCaseId) {
        console.error(
          "Không có testCaseId, dữ liệu tc.case_id / tc.id có thể đang bị thiếu"
        );
        alert("Không xác định được test case id");
        return;
      }

      setRunningId(testCaseId);

      const res = await testCaseService.runTestCase(testCaseId);
      console.log("Run testcase OK:", res);

      alert("Run test case thành công!");
    } catch (err) {
      console.error("Run testcase ERROR:", err);
      console.error("Response:", err.response?.status, err.response?.data);
      alert("Run test case thất bại. Vui lòng thử lại.");
    } finally {
      setRunningId(null);
    }
  };

  // ============================================================
  // FETCH TEST CASES (dùng lại cho cả load & sau khi tạo)
  // ============================================================
  const fetchTestCases = async () => {
    if (!suiteId) return;
    try {
      setLoading(true);
      setError("");

      const data = await testCaseService.getTestCases(suiteId);
      setTestCases(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error(err);
      setError("Không thể tải danh sách test case. Vui lòng thử lại.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTestCases();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [suiteId, projectId]);

  // ============================================================
  // CREATE TEST CASE (callback cho modal)
  // ============================================================
  const [isCreateOpen, setIsCreateOpen] = useState(false);

  // callback khi modal báo tạo thành công
  const handleTestCaseCreated = async () => {
    await fetchTestCases();
  };

  // ✅ CÁC HÀM XỬ LÝ XOÁ (MỚI)
  const openDeleteConfirm = (testCase) => {
    setCaseToDelete(testCase);
    setIsDeleteOpen(true);
  };

  const handleConfirmDelete = async () => {
    if (!caseToDelete) return;
    
    // Lấy ID chuẩn (check cả case_id lẫn id)
    const id = caseToDelete.case_id || caseToDelete.id;

    try {
      // 1. Gọi API
      await testCaseService.deleteTestCase(id);

      // 2. Cập nhật danh sách (Xoá item khỏi state client để đỡ phải fetch lại)
      setTestCases((prev) => prev.filter((item) => (item.case_id || item.id) !== id));

      // Không cần alert hay đóng modal ở đây, ConfirmModal tự lo
    } catch (err) {
      console.error("Delete failed:", err);
      // Ném lỗi ra để ConfirmModal bắt và hiện thông báo đỏ
      throw err; 
    }
  };

  // ============================================================
  // FILTER + PAGINATION
  // ============================================================
  const filteredCases = testCases.filter((tc) => {
    if (!search) return true;
    const text = `${tc.name || ""} ${
      tc.assignee_id || tc.created_by || ""
    }`.toLowerCase();
    return text.includes(search.toLowerCase());
  });

  const totalCases = filteredCases.length;
  const totalPages = Math.max(1, Math.ceil(totalCases / pageSize));

  const pagedCases = filteredCases.slice(
    (page - 1) * pageSize,
    page * pageSize
  );

  // ============================================================
  // RENDER
  // ============================================================
  return (
    <>
      <div className="space-y-4">
        {/* HEADER */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl text-slate-500 font-medium">
              <button
                type="button"
                onClick={() => navigate("/projects")}
                className="hover:text-primary cursor-pointer"
              >
                Projects
              </button>
              <span className="mx-1">›</span>

              <button
                type="button"
                onClick={() => navigate(`/projects/${projectId}`)}
                className="hover:text-primary cursor-pointer"
              >
                {projectName}
              </button>
              <span className="mx-1">›</span>

              <button
                type="button"
                onClick={() =>
                  navigate(`/projects/${projectId}`, {
                    state: { tab: "testsuite" },
                  })
                }
                className="hover:text-primary cursor-pointer"
              >
                Test Suites
              </button>
              <span className="mx-1">›</span>

              <span className="text-primary font-semibold">{suiteName}</span>
            </h1>
          </div>

          <button
            type="button"
            onClick={openCreateModal}
            className="rounded-full bg-primary px-4 py-2 text-xs font-medium text-white hover:bg-primary/90"
          >
            + Add Test Case
          </button>
        </div>

        {/* CARD */}
        <div className="rounded-2xl border border-slate-200 bg-white shadow-sm">
          {/* SEARCH BAR */}
          <div className="flex items-center justify-between gap-3 px-6 pt-4 pb-3 border-b border-slate-100">
            <div className="relative w-72">
              <Search
                className="pointer-events-none absolute left-3 top-2.5 h-4 w-4"
                stroke="#84828A"
              />
              <input
                className="w-full rounded-full border border-slate-200 bg-white pl-9 pr-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/20"
                placeholder="Search by title..."
                value={search}
                onChange={(e) => {
                  setSearch(e.target.value);
                  setPage(1);
                }}
              />
            </div>
          </div>

          {/* BODY */}
          <div className="px-6 pb-4">
            {loading && (
              <p className="py-4 text-sm text-slate-500">
                Đang tải danh sách test case...
              </p>
            )}
            {error && (
              <p className="py-4 text-sm text-red-500">{error}</p>
            )}

            {!loading && !error && (
              <div className="overflow-x-auto">
                <table className="min-w-full text-sm">
                  <thead className="bg-slate-50 text-xs font-semibold text-slate-500">
                    <tr>
                      <th className="px-4 py-3 text-left w-12">STT</th>
                      <th className="px-4 py-3 text-left">Title</th>
                      <th className="px-4 py-3 text-left w-28">Priority</th>
                      <th className="px-4 py-3 text-left w-28">Type</th>
                      <th className="px-4 py-3 text-left w-40">Author</th>
                      <th className="px-4 py-3 text-left w-32">Last Run</th>
                      <th className="px-4 py-3 text-left w-40">Action</th>
                    </tr>
                  </thead>

                  <tbody className="divide-y divide-slate-100">
                    {pagedCases.length === 0 ? (
                      <tr>
                        <td
                          colSpan={7}
                          className="px-6 py-6 text-center text-slate-500 italic"
                        >
                          Không có dữ liệu
                        </td>
                      </tr>
                    ) : (
                      pagedCases.map((tc, idx) => {
                        const testCaseId = tc.case_id || tc.id;
                        const stt = (page - 1) * pageSize + idx + 1;

                        const priorityColor =
                          tc.priority?.toLowerCase() === "high"
                            ? "bg-rose-50 text-rose-500"
                            : tc.priority?.toLowerCase() === "medium"
                            ? "bg-amber-50 text-amber-600"
                            : tc.priority?.toLowerCase() === "low"
                            ? "bg-emerald-50 text-emerald-600"
                            : "bg-slate-50 text-slate-500";

                        const statusColor =
                          tc.last_run_status === "passed"
                            ? "bg-emerald-50 text-emerald-600"
                            : tc.last_run_status === "failed"
                            ? "bg-rose-50 text-rose-500"
                            : "bg-slate-50 text-slate-500";

                        return (
                          <tr key={testCaseId}>
                            <td className="px-4 py-3 text-xs">{stt}</td>
                            <td className="px-4 py-3">
                              {tc.name || "—"}
                            </td>

                            {/* Priority */}
                            <td className="px-4 py-3">
                              <span
                                className={`px-3 py-1 rounded-full text-xs font-medium ${priorityColor}`}
                              >
                                {tc.priority || "—"}
                              </span>
                            </td>

                            {/* Type */}
                            <td className="px-4 py-3">
                              {Array.isArray(tc.steps) &&
                              tc.steps.length > 0
                                ? "Automated"
                                : "Manual"}
                            </td>

                            {/* Author */}
                            <td className="px-4 py-3">
                              <div className="flex items-center gap-2">
                                <div className="h-7 w-7 rounded-full bg-slate-200" />
                                <span>
                                  {tc.creator_username ||
                                    "—"}
                                </span>
                              </div>
                            </td>

                            {/* Status */}
                            <td className="px-4 py-3 text-xs">
                              {tc.last_run_status ? (
                                <div className="flex flex-col gap-1">
                                  <span
                                    className={`px-3 py-1 rounded-full text-xs font-medium ${statusColor}`}
                                  >
                                    {tc.last_run_status}
                                  </span>
                                  {tc.updated_at && (
                                    <span className="text-[11px] text-slate-400">
                                      {formatDate(tc.updated_at)}
                                    </span>
                                  )}
                                </div>
                              ) : (
                                "—"
                              )}
                            </td>

                            {/* Actions */}
                            <td className="px-4 py-3">
                              <div className="flex items-center gap-2 justify-end">
                                {/* Edit */}
                                <button
                                  className="h-8 w-8 flex items-center justify-center rounded-full border hover:bg-slate-50"
                                  onClick={() =>
                                    navigate(
                                      `/projects/${projectId}/suites/${suiteId}/test-cases/${testCaseId}`,
                                      {
                                        state: { projectName, suiteName },
                                      }
                                    )
                                  }
                                >
                                  <Pencil
                                    className="h-4 w-4"
                                    stroke="#84828A"
                                  />
                                </button>

                                {/* Delete */}
                                <button className="h-8 w-8 flex items-center justify-center rounded-full border hover:bg-slate-50"
                                onClick={() => openDeleteConfirm(tc)}
                                >
                                  <Trash
                                    className="h-4 w-4"
                                    stroke="#84828A"
                                  />
                                </button>

                                {/* Run */}
                                <button
                                  className="inline-flex items-center gap-1 rounded-full bg-primary px-4 py-1.5 text-xs font-medium text-white hover:bg-primary/90 disabled:opacity-50"
                                  onClick={() =>
                                    handleRunTestCase(testCaseId)
                                  }
                                  disabled={runningId === testCaseId}
                                >
                                  <Play
                                    className="h-3 w-3"
                                    stroke="#fff"
                                  />
                                  {runningId === testCaseId
                                    ? "Running..."
                                    : "Run"}
                                </button>
                              </div>
                            </td>
                          </tr>
                        );
                      })
                    )}
                  </tbody>
                </table>
              </div>
            )}

            {/* PAGINATION */}
            <div className="mt-3 flex items-center justify-between border-t pt-3 text-xs text-slate-500">
              <span>
                Showing{" "}
                {totalCases === 0
                  ? "0"
                  : `${(page - 1) * pageSize + 1}-${Math.min(
                      page * pageSize,
                      totalCases
                    )}`}{" "}
                of {totalCases} test cases
              </span>

              <div className="flex items-center gap-1">
                <button
                  disabled={page === 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  className="h-7 w-7 rounded-full border disabled:opacity-40"
                >
                  {"<"}
                </button>

                {[...Array(totalPages)].slice(0, 5).map((_, i) => (
                  <button
                    key={i}
                    onClick={() => setPage(i + 1)}
                    className={`h-7 min-w-[28px] rounded-full text-xs ${
                      page === i + 1
                        ? "bg-primary text-white"
                        : "hover:bg-slate-100"
                    }`}
                  >
                    {i + 1}
                  </button>
                ))}

                <button
                  disabled={page === totalPages}
                  onClick={() =>
                    setPage((p) => Math.min(totalPages, p + 1))
                  }
                  className="h-7 w-7 rounded-full border disabled:opacity-40"
                >
                  {">"}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* MODAL CREATE TEST CASE */}
      <CreateTestCaseModal
        isOpen={isCreateOpen}
        onClose={() => {
            setIsCreateOpen(false);
            setEditingTestCase(null);
        }}
        suiteId={suiteId}
        
        // Props xử lý
        onCreate={handleCreateTestCase}
        onUpdate={handleUpdateTestCase}
        testCaseData={editingTestCase}
      />

      {/* ✅ MODAL CONFIRM DELETE (Mới thêm) */}
      <ConfirmModal
        isOpen={isDeleteOpen}
        onCancel={() => setIsDeleteOpen(false)}
        onConfirm={handleConfirmDelete}
        title="Delete Test Case"
        message={
          caseToDelete
            ? `Are you sure you want to delete test case "${caseToDelete.name}"?`
            : "Are you sure you want to delete this test case?"
        }
        successTitle="Deleted Successfully"
        successMessage="The test case has been removed from the system."
        forbiddenTitle="Permission Denied"
        forbiddenMessage="You do not have permission to delete this test case."
      />
    </>
  );
}
