// src/pages/TestCases/TestCaseDetailPage.jsx
import React, { useEffect, useState } from "react";
import { useParams, useLocation, useNavigate } from "react-router-dom";
import { Pencil, Trash, Play, MoreHorizontal, X, AlertTriangle, CheckCircle2, ChevronDown, Sparkles, RefreshCw, Wand2} from "lucide-react";
import { formatDate } from "../../utils/formatDate";
import testCaseService from "../../services/testCaseService";
import ConfirmModal from "../../components/common/ConfirmModal";
import CreateTestCaseModal from "../../components/test-cases/CreateTestCaseModal";
import ProactiveRunModal from "../../components/test-cases/ProactiveRunModal";
import RunDetailModal from "../../components/test-cases/RunDetailModal";
import ProactiveDetailModal from "../../components/test-cases/ProactiveDetailModal";
import SuccessModal from "../../components/common/SuccessModal";
import ErrorModal from "../../components/common/ErrorModal";

export default function TestCaseDetailPage() {
  const [isSuccessOpen, setIsSuccessOpen] = useState(false);
  const [successMessage, setSuccessMessage] = useState({ title: "", msg: "" });
  const [isErrorOpen, setIsErrorOpen] = useState(false);
  const [errorMessage, setErrorMessage] = useState({ title: "", msg: "" });
  const navigate = useNavigate();
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

  const [isRunDropdownOpen, setIsRunDropdownOpen] = useState(false);

  const [isProactiveOpen, setIsProactiveOpen] = useState(false);

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

  // ====== STATE CHO DETAIL MODAL ======
  const [isDetailModalOpen, setIsDetailModalOpen] = useState(false);
  const [selectedRunId, setSelectedRunId] = useState(null);
  const [selectedRunInfo, setSelectedRunInfo] = useState(null);

  // ====== HÀM MỞ MODAL CHI TIẾT ======
  const handleOpenRunDetail = (reportItem) => {
    setSelectedRunId(reportItem.run_id);
    setSelectedRunInfo({
        duration: formatDuration(reportItem.total_duration_ms),
        priority: testCase?.priority
    });
    setIsDetailModalOpen(true);
  };

  // ====== STATE CHO REPORT (MỚI) ======
  const [reports, setReports] = useState([]);
  const [reportLoading, setReportLoading] = useState(false);
  const [reportPage, setReportPage] = useState(1);
  const [reportPagination, setReportPagination] = useState({
    total_items: 0,
    total_pages: 1
  });

  // ====== HÀM TÍNH TOÁN THỐNG KÊ (SUMMARY) ======
  // Lưu ý: Vì API phân trang, nên thống kê này chỉ chính xác trên trang hiện tại 
  // hoặc bạn cần API trả về summary riêng. Ở đây mình tính tạm trên list tải về.
  const summary = React.useMemo(() => {
    let stats = {
      total: reportPagination.total_items, // Lấy tổng số bản ghi từ API
      pass: 0,
      fail: 0,
      healed_attempt: 0,
      healed_pass: 0,
      healed_fail: 0
    };

    reports.forEach(r => {
      // Đếm Pass/Fail Final
      if (r.final_result?.toLowerCase() === 'pass') stats.pass++;
      else stats.fail++;

      // Đếm Self-healing
      if (r.heal_attempted) {
        stats.healed_attempt++;
        if (r.heal_success) stats.healed_pass++;
        else stats.healed_fail++;
      }
    });
    return stats;
  }, [reports, reportPagination.total_items]);

  // ====== FETCH REPORT ======
  const fetchReports = async () => {
    if (!caseId) return;
    try {
      setReportLoading(true);
      // Gọi API Port 8006
      const res = await testCaseService.getTestCaseReports(caseId, reportPage, 10);
      
      // Dữ liệu trả về: { data: [...], pagination: {...} }
      const responseData = res.data; 
      
      setReports(responseData.data || []);
      setReportPagination(responseData.pagination || { total_items: 0, total_pages: 1 });

    } catch (err) {
      console.error("Lỗi tải reports:", err);
    } finally {
      setReportLoading(false);
    }
  };

  // Gọi fetchReports khi vào trang hoặc đổi trang
  useEffect(() => {
    fetchReports();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [caseId, reportPage]);

  // Helper: Format duration (ms -> seconds)
  const formatDuration = (ms) => {
    if (!ms) return "0s";
    return (ms / 1000).toFixed(2) + "s";
  };


  const [proactiveReports, setProactiveReports] = useState([]);
  const [proactiveLoading, setProactiveLoading] = useState(false);
  const [proactivePagination, setProactivePagination] = useState({
    total_items: 0,
    total_pages: 1
  });
  const [proactivePage, setProactivePage] = useState(1);
  // ====== FETCH PROACTIVE REPORTS ======
  const fetchProactiveReports = async () => {
    if (!caseId) return;
    try {
      setProactiveLoading(true);
      // Gọi API mới thêm trong service
      const res = await testCaseService.getProactiveReports(caseId, proactivePage, 10);
      
      const responseData = res.data; // { data: [], pagination: {} }
      setProactiveReports(responseData.data || []);
      setProactivePagination(responseData.pagination || { total_items: 0, total_pages: 1 });

    } catch (err) {
      console.error("Lỗi tải proactive reports:", err);
    } finally {
      setProactiveLoading(false);
    }
  };

  // Gọi fetch khi vào trang hoặc đổi trang
  useEffect(() => {
    fetchProactiveReports();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [caseId, proactivePage]);

  // Helper render thanh Score
  const renderScoreBar = (score) => {
    let color = "bg-slate-300";
    if (score >= 80) color = "bg-emerald-500";
    else if (score >= 50) color = "bg-amber-500";
    else if (score > 0) color = "bg-rose-500";

    return (
      <div className="flex items-center gap-2 w-24">
        <div className="h-1.5 w-full rounded-full bg-slate-100 overflow-hidden">
          <div className={`h-full ${color}`} style={{ width: `${score}%` }} />
        </div>
        <span className="text-[10px] font-bold text-slate-600 w-6 text-right">{score}</span>
      </div>
    );
  };

  // Helper render Status Badge
  const renderProactiveStatus = (status) => {
    const s = status.toUpperCase();
    let style = "bg-slate-100 text-slate-500";
    if (s === "PASS") style = "bg-emerald-500 text-white";
    if (s === "FAIL") style = "bg-rose-500 text-white";
    if (s === "WARNING") style = "bg-orange-400 text-white";
    if (s === "SKIPPED") style = "bg-slate-500 text-white";

    return (
      <span className={`px-3 py-0.5 rounded-full text-[10px] font-bold ${style}`}>
        {s}
      </span>
    );
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

      setSuccessMessage({
        title: "Execution Success",
        msg: "Self-healing done."
      });
      setIsSuccessOpen(true);
    } catch (err) {
      console.error("Run testcase (detail) ERROR:", err);
      console.error("Response:", err.response?.status, err.response?.data);
      setErrorMessage({
        title: "Execution Failed"
      });
      setIsErrorOpen(true);
    } finally {
      setRunning(false);
    }
  };

  // Mở Modal
  const handleRunProactive = () => {
    setIsRunDropdownOpen(false); // Đóng dropdown menu trước
    setIsProactiveOpen(true);    // Mở modal nhập SHA
  };

  // Hàm thực thi gọi API
  const handleConfirmProactive = async ({ headSha, baseSha }) => {
    try {
      const testCaseId = testCase?.case_id || testCase?.id || caseId;
      setRunning(true); // Bật loading ở nút Header

      const payload = {
        project_id: projectId,
        case_id: testCaseId,
        head_sha: headSha,
        base_sha: baseSha
      };

      await testCaseService.runProactiveTestCase(payload);
      setSuccessMessage({
        title: "Analysis Success",
        msg: "Proactive done."
      });
      setIsSuccessOpen(true);

    } catch (err) {
      console.error("Run Proactive ERROR:", err);
      setErrorMessage({
        title: "Analysis Failed"
      });
      setIsErrorOpen(true);
    } finally {
      setRunning(false); // Tắt loading
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

  // State cho Proactive Detail Modal
  const [isProactiveDetailOpen, setIsProactiveDetailOpen] = useState(false);
  const [selectedProactiveId, setSelectedProactiveId] = useState(null);
  const handleOpenProactiveDetail = (item) => {
    setSelectedProactiveId(item.id); // item.id chính là Mongo ID
    setIsProactiveDetailOpen(true);
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
          {/* BREADCRUMB NAVIGATION (Đã cập nhật style to hơn và click được) */}
          <h1 className="text-xl text-slate-500 font-medium flex items-center flex-wrap">
            <button
              type="button"
              onClick={() => navigate("/projects")}
              className="hover:text-primary cursor-pointer transition-colors"
            >
              Projects
            </button>
            <span className="mx-2 text-slate-400">›</span>

            <button
              type="button"
              onClick={() => navigate(`/projects/${projectId}`)}
              className="hover:text-primary cursor-pointer transition-colors"
            >
              {projectName}
            </button>
            <span className="mx-2 text-slate-400">›</span>

            <button
              type="button"
              onClick={() => navigate(`/projects/${projectId}`, {
                  state: { tab: "testsuite" },
                })
              }
              className="hover:text-primary cursor-pointer transition-colors"
            >
              Test Suites
            </button>
            <span className="mx-2 text-slate-400">›</span>

            <button
              type="button"
              onClick={() => navigate(`/projects/${projectId}/suites/${suiteId}/test-cases`, {
                  state: { projectName, suiteName } 
              })}
              className="hover:text-primary cursor-pointer transition-colors"
            >
              {suiteName}
            </button>
            <span className="mx-2 text-slate-400">›</span>

            <span className="text-primary font-semibold">{title}</span>
          </h1>
        </div>

        <div className="flex items-center gap-3">
          <button className="flex items-center rounded-full border border-slate-200 px-5 py-2.5 text-sm font-medium bg-white hover:bg-slate-50 shadow-sm transition-all"
          onClick={() => setIsEditInfoOpen(true)}
          >
            Edit
          </button>
          <div className="relative">
          {running ? (
            // Trạng thái Loading
            <button disabled className="inline-flex items-center gap-2 rounded-full bg-primary/70 px-5 py-2.5 text-sm font-medium text-white cursor-not-allowed">
               <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent"></span>
               Running...
            </button>
          ) : (
            // Trạng thái Dropdown Trigger
            <>
              <button
                onClick={() => setIsRunDropdownOpen(!isRunDropdownOpen)}
                className="inline-flex items-center gap-2 rounded-full bg-primary px-5 py-2.5 text-sm font-medium text-white hover:bg-primary/90 transition-all shadow-md shadow-indigo-100"
              >
                <Play className="h-4 w-4 fill-current" />
                Run Test Case
                <ChevronDown className={`h-4 w-4 transition-transform ${isRunDropdownOpen ? "rotate-180" : ""}`} />
              </button>

              {/* Menu Popup */}
              {isRunDropdownOpen && (
                <div className="absolute right-0 z-20 mt-2 w-60 origin-top-right rounded-2xl border border-slate-100 bg-white p-2 shadow-xl ring-1 ring-black ring-opacity-5 animate-in fade-in zoom-in duration-150">
                  
                  {/* Option 1: Self-healing */}
                  <button
                    onClick={() => {
                       handleRunTestCase(); // Gọi API cũ
                       setIsRunDropdownOpen(false);
                    }}
                    className="group flex w-full items-center gap-3 rounded-xl px-4 py-3 text-sm text-slate-700 hover:bg-slate-50 transition-colors"
                  >
                    <div className="flex h-9 w-9 items-center justify-center rounded-full bg-emerald-100 text-emerald-600 group-hover:bg-emerald-500 group-hover:text-white transition-colors">
                      <Wand2 className="h-5 w-5 fill-current" />
                    </div>
                    <span className="font-semibold text-slate-800">Self-healing</span>
                  </button>

                  {/* Option 2: Proactive */}
                  <button
                    onClick={handleRunProactive}
                    className="group flex w-full items-center gap-3 rounded-xl px-4 py-3 text-sm text-slate-700 hover:bg-slate-50 transition-colors"
                  >
                    <div className="flex h-9 w-9 items-center justify-center rounded-full bg-rose-100 text-rose-600 group-hover:bg-rose-500 group-hover:text-white transition-colors">
                      <Sparkles className="h-5 w-5 fill-current" />
                    </div>
                    <span className="font-semibold text-slate-800">Proactive</span>
                  </button>
                </div>
              )}
              
              {/* Overlay đóng khi click ra ngoài */}
              {isRunDropdownOpen && (
                <div 
                  className="fixed inset-0 z-10 cursor-default" 
                  onClick={() => setIsRunDropdownOpen(false)}
                />
              )}
            </>
          )}
       </div>
          <button className="h-10 w-10 flex items-center justify-center rounded-full border border-slate-200 bg-white hover:bg-slate-50 shadow-sm">
            <MoreHorizontal className="h-5 w-5" />
          </button>
        </div>
      </div>

      {/* GRID 2 COLUMNS: General + Side info */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,3fr)_minmax(300px,1.2fr)]">
        {/* MAIN COLUMN (General info) */}
        <div className="space-y-6">
          {/* CARD INFO */}
          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            {/* Name */}
            <h1 className="text-2xl font-bold text-slate-800 mb-5">
              {title}
            </h1>

            {/* Priority + Type + Tags */}
            <div className="flex flex-wrap items-center gap-2 mb-8">
              <span className={`px-3 py-1 rounded-full text-sm font-medium ${priorityColor}`}>
                Priority: {priority}
              </span>

              <span className="px-3 py-1 rounded-full border border-slate-200 bg-slate-50 text-sm font-medium text-slate-600">
                {type}
              </span>

              {tags.map((tag) => (
                <span key={tag} className="px-3 py-1 rounded-full border border-slate-200 bg-slate-50 text-xs font-medium text-slate-600">
                  #{tag}
                </span>
              ))}
            </div>

            {/* DESCRIPTION */}
            <div className="mb-8">
              <h3 className="mb-4 text-base font-bold uppercase tracking-wide text-slate-400">
                Description
              </h3>
              <p className="text-lg text-slate-700 leading-relaxed">
                {description}
              </p>
            </div>

            {/* META FIELDS */}
            <div className="border-t border-slate-100 pt-5 space-y-3 text-sm text-slate-700">
              <div className="flex justify-between">
                <span className="text-slate-500 font-medium">Assignee:</span>
                <span className="font-semibold text-slate-800">{author}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500 font-medium">Created:</span>
                <span>{createdAt}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500 font-medium">Updated:</span>
                <span>{updatedAt}</span>
              </div>
            </div>
          </div>
        </div>

        {/* SIDE COLUMN (Application + Run info) */}
        <div className="space-y-6">
          {/* Application Info */}
          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <h3 className="text-sm font-bold uppercase tracking-wide text-slate-400 mb-5">
              Application Info
            </h3>
            <div className="space-y-4 text-sm">
              <div className="flex justify-between items-center">
                <span className="text-slate-500 font-medium">App version</span>
                <span className="font-bold text-slate-800">{appVersion}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-slate-500 font-medium">Build version</span>
                <span className="font-bold text-slate-800">{buildVersion}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-slate-500 font-medium">Git hash</span>
                <span className="font-bold text-slate-800">{gitHash}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-slate-500 font-medium">Page Path</span>
                <span className="font-bold text-slate-800">{pagePath}</span>
              </div>
            </div>
          </div>

          {/* Run Info */}
          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <h3 className="text-sm font-bold uppercase tracking-wide text-slate-400 mb-5">
              Run Information
            </h3>
            <div className="space-y-4 text-sm">
              <div className="flex justify-between items-center">
                <span className="text-slate-500 font-medium">Last Run Status</span>
                <span className="font-bold text-slate-800">{lastRunStatus}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-slate-500 font-medium">Last Run At</span>
                <span className="font-bold text-slate-800">{lastRunAt}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* FULL WIDTH TEST STEPS */}
      <div className="rounded-2xl border border-slate-200 bg-white shadow-sm mt-2 p-0 w-full">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-5 border-b border-slate-200">
          <h2 className="text-xl font-bold text-slate-800">Test Steps</h2> 
          <button
            className="rounded-full bg-primary px-5 py-2 text-sm font-medium text-white hover:bg-primary/90 transition-all shadow-sm shadow-indigo-200"
            onClick={openCreateStepModal}
          >
            + Add Step
          </button>
        </div>

        {/* Table Test Steps */}
        <div className="overflow-x-auto">
          <table className="w-full text-base text-left">
            <thead className="bg-slate-50 text-xs font-bold uppercase tracking-wide text-slate-500 border-b border-slate-200"> 
              <tr>
                <th className="px-5 py-2.5 w-14">Step</th>
                <th className="px-5 py-2.5 w-36">Action</th>
                <th className="px-5 py-2.5 w-36">Locator Type</th>
                <th className="px-5 py-2.5 w-56">Locator Value</th>
                <th className="px-5 py-2.5 w-40">URL</th>
                <th className="px-5 py-2.5">Expected Result</th>
                <th className="px-5 py-2.5 text-right w-32">Actions</th>
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
                    <td className="px-5 py-2.5 text-slate-500">
                      {step.step_order ?? index + 1}
                    </td>
                    <td className="px-5 py-2.5">{step.action || "—"}</td>
                    <td className="px-5 py-2.5">{step.locator_type || "—"}</td>
                    <td className="px-5 py-2.5">{step.locator_value || "—"}</td>
                    <td className="px-5 py-2.5">{step.url || "—"}</td>
                    <td className="px-5 py-2.5">{step.expected || "—"}</td>
                    <td className="px-5 py-2.5 text-right">
                      <div className="flex justify-end gap-1">
                        <button className="h-8 w-8 flex items-center justify-center rounded-full border border-slate-200 hover:bg-slate-50 transition-colors"
                        onClick={() => openEditStepModal(step)}
                        >
                          <Pencil className="h-4 w-4 text-slate-600" />
                        </button>
                        <button className="h-8 w-8 flex items-center justify-center rounded-full border border-slate-200 hover:bg-rose-50 hover:border-rose-200 hover:text-rose-500 transition-colors"
                        onClick={() => openDeleteStepConfirm(step)}
                        >
                          <Trash className="h-4 w-4" />
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


      {/* ===================== TEST REPORTS SECTION (REAL DATA) ===================== */}
      <div className="rounded-2xl border border-slate-200 bg-white shadow-sm mt-4 p-6">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-bold text-slate-800">Test Reports - Self Healing</h2>
          <button 
            onClick={fetchReports} 
            disabled={reportLoading}
            className="flex items-center gap-1.5 text-xs text-primary hover:text-primary/80 hover:underline disabled:opacity-50 disabled:cursor-not-allowed transition-all"
            >
            <RefreshCw className={`h-4 w-4 ${reportLoading ? "animate-spin" : ""}`} />
            {reportLoading ? "Refreshing..." : "Refresh"}
          </button>
        </div>

        {/* 1. SUMMARY CARDS (Dùng biến summary đã tính ở trên) */}
        <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-5 mb-8">
          {/* Card Total Run */}
          <div className="rounded-xl border border-slate-100 bg-white p-5 shadow-sm flex flex-col items-center justify-center gap-1">
            <span className="text-sm font-medium text-slate-500">Total Run</span>
            <span className="text-3xl font-bold text-slate-800">{summary.total}</span>
          </div>
          
          {/* Card Pass */}
          <div className="rounded-xl border border-slate-100 bg-white p-5 shadow-sm flex flex-col items-center justify-center gap-1">
            <span className="text-sm font-medium text-slate-500">Pass</span>
            <span className="text-3xl font-bold text-emerald-500">{summary.pass}</span>
          </div>
          
          {/* Card Fail */}
          <div className="rounded-xl border border-slate-100 bg-white p-5 shadow-sm flex flex-col items-center justify-center gap-1">
            <span className="text-sm font-medium text-slate-500">Fail</span>
            <span className="text-3xl font-bold text-rose-500">{summary.fail}</span>
          </div>
          
          {/* Card Healed Attempt */}
          <div className="rounded-xl border border-slate-100 bg-white p-5 shadow-sm flex flex-col items-center justify-center gap-1">
            <span className="text-sm font-medium text-slate-500">Healed Attempt</span>
            <span className="text-3xl font-bold text-amber-500">{summary.healed_attempt}</span>
          </div>
          
          {/* Card Healed Pass */}
          <div className="rounded-xl border border-slate-100 bg-white p-5 shadow-sm flex flex-col items-center justify-center gap-1">
            <span className="text-sm font-medium text-slate-500">Healed Pass</span>
            <span className="text-3xl font-bold text-blue-500">{summary.healed_pass}</span>
          </div>
          
          {/* Card Healed Fail */}
          <div className="rounded-xl border border-slate-100 bg-white p-5 shadow-sm flex flex-col items-center justify-center gap-1">
            <span className="text-sm font-medium text-slate-500">Healed Fail</span>
            <span className="text-3xl font-bold text-orange-600">{summary.healed_fail}</span>
          </div>
        </div>

        {/* 2. EXECUTION HISTORY TABLE */}
        <h3 className="text-sm font-bold text-slate-800 mb-4">Execution History</h3>
        
        <div className="overflow-x-auto rounded-lg border border-slate-100">
          <table className="w-full text-base text-left"> 
            <thead className="bg-slate-50 text-xs font-bold uppercase tracking-wide text-slate-500 border-b border-slate-100"> 
              <tr>
                <th className="px-5 py-2.5">Run ID</th>
                <th className="px-5 py-2.5 text-center">Raw Result</th>
                <th className="px-5 py-2.5 text-center">Final Result</th>
                <th className="px-5 py-2.5 text-center">Self-healing</th>
                <th className="px-5 py-2.5">Duration</th>
                <th className="px-5 py-2.5">Timestamp</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-50">
              {reportLoading ? (
                 <tr><td colSpan={6} className="text-center py-4 text-slate-500">Đang tải dữ liệu...</td></tr>
              ) : reports.length === 0 ? (
                 <tr><td colSpan={6} className="text-center py-4 text-slate-500 italic">Chưa có lịch sử chạy nào.</td></tr>
              ) : (
                reports.map((item, idx) => {
                  // Logic hiển thị
                  const isPass = item.final_result?.toLowerCase() === "pass";
                  const finalColor = isPass
                    ? "bg-emerald-50 text-emerald-600 border border-emerald-100"
                    : "bg-rose-50 text-rose-500 border border-rose-100";
                  
                  // Logic suy luận Raw Result (Vì API không trả về Raw, ta suy luận từ Heal Attempt)
                  // Nếu có Heal Attempt -> Raw chắc chắn là Fail. Nếu ko -> Raw giống Final.
                  const rawResult = item.heal_attempted ? "FAIL" : item.final_result?.toUpperCase();
                  const rawColor = rawResult === "PASS"
                    ? "bg-emerald-50 text-emerald-600 border border-emerald-100" 
                    : "bg-rose-50 text-rose-500 border border-rose-100";

                  const rowBg = idx % 2 === 0 ? "bg-white" : "bg-slate-50/50";

                  return (
                    <tr key={item.run_id || idx} className={`${rowBg} hover:bg-slate-50 transition-colorscursor-pointer`} // Thêm cursor-pointer
                        onClick={() => handleOpenRunDetail(item)}>
                      <td className="px-5 py-2.5 font-medium text-blue-600">
                        #{item.run_id}
                      </td>
                      <td className="px-5 py-2.5 text-center">
                         <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${rawColor}`}>
                          {rawResult}
                        </span>
                      </td>
                      <td className="px-5 py-2.5 text-center">
                        <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${finalColor}`}>
                          {item.final_result}
                        </span>
                      </td>
                      <td className="px-5 py-2.5 text-center">
                         {item.heal_attempted ? (
                            item.heal_success ? (
                                <span className="text-blue-600 font-semibold flex items-center justify-center gap-1">
                                  Success
                                </span>
                            ) : (
                                <span className="text-orange-600 font-semibold flex items-center justify-center gap-1">
                                  Failed
                                </span>
                            )
                         ) : (
                            <span className="text-slate-400">—</span>
                         )}
                      </td>
                      <td className="px-5 py-2.5 text-slate-600">
                        {formatDuration(item.total_duration_ms)}
                      </td>
                      <td className="px-5 py-2.5 text-slate-500">
                        {formatDate(item.timestamp)}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* 3. PAGINATION (REAL) */}
        {reportPagination.total_pages > 1 && (
          <div className="mt-4 flex items-center justify-between text-xs text-slate-500">
             <span>
                Showing page {reportPage} of {reportPagination.total_pages} ({reportPagination.total_items} items)
             </span>
             <div className="flex items-center gap-1">
                <button 
                  disabled={reportPage === 1}
                  className="h-7 w-7 flex items-center justify-center rounded-md border border-slate-200 hover:bg-slate-50 disabled:opacity-50"
                  onClick={() => setReportPage(p => Math.max(1, p - 1))}
                >
                  &lt;
                </button>
                
                {/* Hiển thị số trang đơn giản */}
                {[...Array(reportPagination.total_pages)].slice(0, 5).map((_, i) => (
                   <button 
                     key={i}
                     onClick={() => setReportPage(i + 1)}
                     className={`h-7 w-7 flex items-center justify-center rounded-md ${
                        reportPage === i + 1 ? 'bg-[#6425FE] text-white' : 'hover:bg-slate-50 text-slate-600'
                     }`}
                   >
                     {i + 1}
                   </button>
                ))}

                <button 
                  disabled={reportPage === reportPagination.total_pages}
                  className="h-7 w-7 flex items-center justify-center rounded-md border border-slate-200 hover:bg-slate-50 disabled:opacity-50"
                  onClick={() => setReportPage(p => Math.min(reportPagination.total_pages, p + 1))}
                >
                  &gt;
                </button>
             </div>
          </div>
        )}
      </div>

      {/* ===================== TEST REPORTS - PROACTIVE FAULT (REAL DATA) ===================== */}
      <div className="rounded-2xl border border-slate-200 bg-white shadow-sm mt-4 p-6">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-bold text-slate-800">
            Test Reports - Proactive Fault
          </h2>
          <button 
            onClick={fetchProactiveReports} 
            disabled={proactiveLoading}
            className="flex items-center gap-1.5 text-xs text-primary hover:text-primary/80 hover:underline disabled:opacity-50 disabled:cursor-not-allowed transition-all"
            >
            <RefreshCw className={`h-4 w-4 ${proactiveLoading ? "animate-spin" : ""}`} />
            {reportLoading ? "Refreshing..." : "Refresh"}
          </button>
        </div>

        {/* TABLE PROACTIVE */}
        <div className="overflow-x-auto rounded-lg border border-slate-100">
          <table className="w-full text-base text-left">
            <thead className="bg-slate-50 text-xs font-bold uppercase tracking-wide text-slate-500 border-b border-slate-100">
              <tr>
                <th className="px-5 py-2.5">PR Info</th>
                <th className="px-5 py-2.5">Commit Message</th>
                <th className="px-5 py-2.5">Author</th>
                <th className="px-5 py-2.5">Score</th>
                <th className="px-5 py-2.5 text-center">Status</th>
                <th className="px-5 py-2.5">Timestamp</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-50">
              {proactiveLoading ? (
                 <tr><td colSpan={6} className="text-center py-6 text-slate-500">Đang tải dữ liệu...</td></tr>
              ) : proactiveReports.length === 0 ? (
                 <tr><td colSpan={6} className="text-center py-6 text-slate-500 italic">Chưa có báo cáo nào.</td></tr>
              ) : (
                proactiveReports.map((item, idx) => (
                  <tr key={item.id || idx} className="hover:bg-slate-50 transition-colors cursor-pointer"
                  onClick={() => handleOpenProactiveDetail(item)}>
                    
                    {/* Cột 1: PR Number (Fix null hiển thị —) */}
                    <td className="px-5 py-2.5">
                      <div className="flex items-center gap-2">
                         <span className="font-mono font-bold text-blue-600">
                            {item.pr_number ? `#${item.pr_number}` : "—"}
                         </span>
                      </div>
                    </td>

                    {/* Cột 2: Commit Message */}
                    <td className="px-5 py-2.5 max-w-[240px] truncate" title={item.commit_msg}>
                      <span className="text-slate-700 font-medium">
                        {item.commit_msg || "—"}
                      </span>
                    </td>

                    {/* Cột 3: Author */}
                    <td className="px-5 py-2.5">
                       <span className="px-2.5 py-1 bg-slate-100 rounded text-slate-600 font-medium text-sm">
                         {item.author || "Unknown"}
                       </span>
                    </td>

                    {/* Cột 4: Score */}
                    <td className="px-5 py-2.5">
                      {renderScoreBar(item.confidence_score)}
                    </td>

                    {/* Cột 5: Status */}
                    <td className="px-5 py-2.5 text-center">
                      {renderProactiveStatus(item.status)}
                    </td>

                    {/* Cột 6: Timestamp (JSON mới dùng started_at) */}
                    <td className="px-5 py-2.5 text-slate-500">
                      {formatDate(item.started_at)}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* PAGINATION (REAL) */}
        {proactivePagination.total_pages > 1 && (
          <div className="mt-4 flex items-center justify-between text-xs text-slate-500">
             <span>
                Showing page {proactivePage} of {proactivePagination.total_pages} ({proactivePagination.total_items} items)
             </span>
             <div className="flex items-center gap-1">
                <button 
                  disabled={proactivePage === 1}
                  className="h-7 w-7 flex items-center justify-center rounded-md border border-slate-200 hover:bg-slate-50 disabled:opacity-50"
                  onClick={() => setProactivePage(p => Math.max(1, p - 1))}
                >
                  &lt;
                </button>
                
                {[...Array(proactivePagination.total_pages)].slice(0, 5).map((_, i) => (
                   <button 
                     key={i}
                     onClick={() => setProactivePage(i + 1)}
                     className={`h-7 w-7 flex items-center justify-center rounded-md ${
                        proactivePage === i + 1 ? 'bg-[#6425FE] text-white' : 'hover:bg-slate-50 text-slate-600'
                     }`}
                   >
                     {i + 1}
                   </button>
                ))}

                <button 
                  disabled={proactivePage === proactivePagination.total_pages}
                  className="h-7 w-7 flex items-center justify-center rounded-md border border-slate-200 hover:bg-slate-50 disabled:opacity-50"
                  onClick={() => setProactivePage(p => Math.min(proactivePagination.total_pages, p + 1))}
                >
                  &gt;
                </button>
             </div>
          </div>
        )}
      </div>

      {/* POPUP ADD STEP */}
      <AddStepModal
        isOpen={isAddStepOpen}
        onClose={() => setIsAddStepOpen(false)}
        onSubmit={handleSaveStep}        // Gọi hàm save chung
        stepNumber={steps.length + 1}
        stepData={editingStep}           // Truyền dữ liệu cần sửa
/>
      {/* MODAL CONFIRM DELETE STEP  */}
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
        testCaseData={testCase} 
        onUpdate={handleUpdateInfo}
        suiteId={suiteId}
      />

      {/* MODAL PROACTIVE RUN */}
      <ProactiveRunModal
        isOpen={isProactiveOpen}
        onClose={() => setIsProactiveOpen(false)}
        onRun={handleConfirmProactive}
      />

      {/* REPORT MODAL  */}
        <RunDetailModal 
            isOpen={isDetailModalOpen}
            onClose={() => setIsDetailModalOpen(false)}
            runId={selectedRunId}
            runInfo={selectedRunInfo}
        />

        {/* MODAL PROACTIVE DETAIL */}
        <ProactiveDetailModal 
          isOpen={isProactiveDetailOpen}
          onClose={() => setIsProactiveDetailOpen(false)}
          analysisId={selectedProactiveId}
          testId={caseId} // Truyền caseId để làm tham số cho API
        />

        <SuccessModal
        isOpen={isSuccessOpen}
        onClose={() => setIsSuccessOpen(false)}
        title={successMessage.title}
        message={successMessage.msg}
      />

      <ErrorModal
        isOpen={isErrorOpen}
        onClose={() => setIsErrorOpen(false)}
        title={errorMessage.title}
        message={errorMessage.msg}
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
              {isEditMode ? `Edit Step` : `Add Step `}
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
                    <option value="CLASS NAME">Class Name</option>
                    <option value="TAG NAME">Tag Name</option>
                    <option value="LINK TEXT">Link Text</option>
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