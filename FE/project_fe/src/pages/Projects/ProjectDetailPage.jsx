import React, { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  Clipboard,
  ChevronRight,
  Plus,
  Pencil,
  Trash,
  Filter,
  Search,
} from "lucide-react";
import CreateProjectModal from "../../components/projects/CreateProjectModal";
import { formatDate } from "../../utils/formatDate";
import projectService from "../../services/projectService";
import CreateTestSuiteModal from "../../components/test-suites/CreateTestSuiteModal";
import ConfirmModal from "../../components/common/ConfirmModal"; // chỉnh path nếu cần

export default function ProjectDetailPage() {
  const { id } = useParams(); // /projects/:id
  const navigate = useNavigate();

  const [project, setProject] = useState(null);
  const [loadingProject, setLoadingProject] = useState(false);
  const [errorProject, setErrorProject] = useState("");
  const [isEditOpen, setIsEditOpen] = useState(false);

  // ===== Test Suites =====
  const [testSuites, setTestSuites] = useState([]);
  const [loadingSuites, setLoadingSuites] = useState(false);
  const [errorSuites, setErrorSuites] = useState("");
  const [suiteSearch, setSuiteSearch] = useState("");
  const [suitePage, setSuitePage] = useState(1);
  const suitePageSize = 10;

  // expanded state cho tree test suite
  const [expandedSuites, setExpandedSuites] = useState({}); // { [suiteId]: boolean }

  // ===== Members =====
  const [members, setMembers] = useState([]);
  const [loadingMembers, setLoadingMembers] = useState(false);
  const [errorMembers, setErrorMembers] = useState("");
  const [memberSearch, setMemberSearch] = useState("");
  const [memberPage, setMemberPage] = useState(1);
  const memberPageSize = 10;

  const [activeTab, setActiveTab] = useState("general");
  const [copied, setCopied] = useState(false);

  // ===== Modal Create Test Suite =====
  const [editingSuite, setEditingSuite] = useState(null); // Lưu suite đang sửa
  const [isCreateSuiteOpen, setIsCreateSuiteOpen] = useState(false);
  const [parentSuiteId, setParentSuiteId] = useState(null);

  const openCreateSuiteModal = (suite) => {
    setParentSuiteId(suite); // null = root, còn lại = suite cha
    setIsCreateSuiteOpen(true);
  };


  const handleSuiteCreated = async (payload) => {
    try {
      // 1. GỌI API LƯU DB (Sử dụng service bạn cung cấp)
      // payload nhận từ Modal: { suite_id, name, parent_suite_id }
      const res = await projectService.createTestSuite(id, payload);

      // Dữ liệu thật sự từ DB trả về (đã có created_at, v.v...)
      const newSuite = res?.data || res;
      if (!newSuite) {
        throw new Error("Không nhận được dữ liệu từ API");
      }

      // 2. CẬP NHẬT GIAO DIỆN (Logic Root - Child cũ của bạn)
      setTestSuites((prev) => {
        const suiteToAdd = {
          ...newSuite,
          children: newSuite.children || [],
        };

        // Không có parent => suite root
        if (!suiteToAdd.parent_suite_id) {
          return [...prev, suiteToAdd];
        }

        // Có parent => tìm trong tree và chèn vào children
        const insertChild = (nodes) => {
          return nodes.map((node) => {
            // Nếu là suite cha
            if (node.suite_id === suiteToAdd.parent_suite_id) {
              const children = Array.isArray(node.children)
                ? [...node.children, suiteToAdd]
                : [suiteToAdd];

              return {
                ...node,
                children,
              };
            }

            // Nếu node này cũng có children thì đệ quy tiếp
            if (Array.isArray(node.children) && node.children.length > 0) {
              return {
                ...node,
                children: insertChild(node.children),
              };
            }

            // Không liên quan thì trả lại như cũ
            return node;
          });
        };

        const updated = insertChild(prev);

        // Nếu không tìm thấy parent (phòng hờ) thì thêm vào root
        // (Logic so sánh chuỗi cũ của bạn)
        const foundParent = JSON.stringify(updated) !== JSON.stringify(prev);
        return foundParent ? updated : [...prev, suiteToAdd];
      });

    } catch (error) {
      console.error("Create suite failed:", error);
      // Ném lỗi ra để Modal bắt được và hiện thông báo đỏ
      throw error;
    }
  };

  // ===== Modal Confirm Delete Suite =====
  const [isConfirmOpen, setIsConfirmOpen] = useState(false);
  const [suiteToDelete, setSuiteToDelete] = useState(null);

  // Xoá 1 suite (và toàn bộ subtree con của nó) khỏi tree
  const removeSuiteFromTree = (nodes, targetId) => {
    return (nodes || [])
      .filter((node) => node.suite_id !== targetId) // bỏ luôn node trùng ID
      .map((node) => ({
        ...node,
        children: node.children
          ? removeSuiteFromTree(node.children, targetId)
          : [],
      }));
  };

  const openDeleteSuiteConfirm = (suite) => {
    setSuiteToDelete(suite);
    setIsConfirmOpen(true);
  };

  const handleCancelDeleteSuite = () => {
    setIsConfirmOpen(false);
    setSuiteToDelete(null);
  };

  const handleConfirmDeleteSuite = async () => {
    // 1. Kiểm tra dữ liệu đầu vào
    if (!suiteToDelete) return;
    const suiteId = suiteToDelete.suite_id;

    try {
      // 2. Gọi API qua Service (Tự động xử lý Token)
      await projectService.deleteTestSuite(suiteId);

      // 3. Cập nhật State (Xoá suite khỏi cây thư mục trên giao diện)
      setTestSuites((prev) => removeSuiteFromTree(prev, suiteId));

    } catch (err) {
      console.error("Delete suite error:", err);
      // Ném lỗi ra để ConfirmModal bắt được và hiện giao diện lỗi (Permission Denied, 404, v.v...)
      throw err;
    }
  };

  // ✅ Hàm xử lý cập nhật Suite
  const handleUpdateSuite = async (payload) => {
    // payload: { suite_id, name, parent_suite_id }

    // 1. GỌI API (Bắt buộc phải có await)
    // Gọi PUT /api/v1/suites/{suite_id}
    await projectService.updateTestSuite(payload.suite_id, {
      name: payload.name,
      // parent_suite_id: payload.parent_suite_id // Gửi cái này nếu bạn muốn di chuyển thư mục
    });

    // 2. CẬP NHẬT GIAO DIỆN (Đệ quy tìm node và đổi tên)
    const updateTree = (nodes) => {
      return nodes.map((node) => {
        // Tìm thấy suite cần sửa
        if (node.suite_id === payload.suite_id) {
          return { ...node, name: payload.name };
        }
        // Nếu có con thì tìm tiếp bên trong
        if (node.children) {
          return { ...node, children: updateTree(node.children) };
        }
        return node;
      });
    };

    setTestSuites((prev) => updateTree(prev));

    // Lưu ý: Không cần alert hay đóng modal ở đây, modal con sẽ tự hiện Success
  };

  // ✅ Hàm mở modal Edit khi bấm nút Pencil
  const openEditSuiteModal = (suite) => {
    setEditingSuite(suite);     // Set dữ liệu cũ
    setIsCreateSuiteOpen(true); // Mở Modal
  };

  // ================== FETCH PROJECT DETAIL ==================
  useEffect(() => {
    async function fetchProject() {
      try {
        setLoadingProject(true);
        setErrorProject("");

        const data = await projectService.getProjectDetail(id);
        const mapped = {
          ...data,
          status: data.status || "active",
          project_code: data.project_code || data.project_id,
        };

        setProject(mapped);
      } catch (err) {
        console.error(err);
        setErrorProject("Không thể tải thông tin project. Vui lòng thử lại.");
      } finally {
        setLoadingProject(false);
      }
    }

    async function fetchTestSuites() {
      try {
        setLoadingSuites(true);
        setErrorSuites("");

        const data = await projectService.getTestSuites(id);
        setTestSuites(Array.isArray(data) ? data : []);
        setSuitePage(1);
      } catch (err) {
        console.error(err);
        setErrorSuites("Không thể tải danh sách test suite. Vui lòng thử lại.");
      } finally {
        setLoadingSuites(false);
      }
    }

    async function fetchMembers() {
      try {
        setLoadingMembers(true);
        setErrorMembers("");

        const data = await projectService.getProjectMembers(id);

        const mapped = Array.isArray(data)
          ? data.map((m) => ({
            ...m,
            name: m.user_id, // tạm dùng user_id làm Name hiển thị
            role: m.project_role, // map sang field role để UI dùng
          }))
          : [];

        setMembers(mapped);
      } catch (err) {
        console.error(err);
        setErrorMembers("Không thể tải danh sách member. Vui lòng thử lại.");
      } finally {
        setLoadingMembers(false);
      }
    }

    fetchProject();
    fetchTestSuites();
    fetchMembers();
  }, [id]);

  // ✅ Thêm hàm xử lý gọi API Update
  const handleUpdateProject = async (payload) => {
    // 1. Gọi API
    await projectService.updateProject(id, payload);

    // 2. Cập nhật giao diện ngay lập tức (Client State Update)
    setProject(prev => ({
      ...prev,
      name: payload.name,
      description: payload.description,
      repo_url: payload.repo_url
      // (Hoặc repo_url: payload.repo_url nếu tên field khớp nhau)
    }));

  };

  // ================== UI HELPERS ==================
  const handleCopyCode = async () => {
    const code = project?.project_code || project?.project_id || "";
    if (!code) return;
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch (err) {
      console.error("Copy failed:", err);
    }
  };

  const name = project?.name || "Project Detail";
  const projectCode =
    project?.project_code || project?.project_id || project?.code || "";
  const description = project?.description || "";
  const repoUrl = project?.repository_url || project?.repo_url || "";
  const ownerName = project?.creator_username || "Unknown Owner";
  const status = (project?.status || "unknown").toLowerCase();
  const createdAt = project?.created_at ? formatDate(project.created_at) : "--";
  const updatedAt = project?.updated_at ? formatDate(project.updated_at) : "--";

  const renderStatusBadge = () => {
    let cls = "bg-slate-100 text-slate-600";
    let text = "Unknown";

    if (status === "active") {
      cls = "bg-emerald-50 text-emerald-600";
      text = "Active";
    } else if (status === "pending") {
      cls = "bg-amber-50 text-amber-600";
      text = "Pending";
    } else if (status === "completed") {
      cls = "bg-slate-100 text-slate-600";
      text = "Completed";
    }

    return (
      <span
        className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-medium ${cls}`}
      >
        {text}
      </span>
    );
  };

  // ======= Test Suites helpers =======
  const filteredSuites = testSuites.filter((s) => {
    if (!suiteSearch) return true;
    const text = `${s.suite_id || ""} ${s.name || ""}`.toLowerCase();
    return text.includes(suiteSearch.toLowerCase());
  });

  const totalSuites = filteredSuites.length;
  const suiteTotalPages = Math.max(1, Math.ceil(totalSuites / suitePageSize));
  const pagedSuites = filteredSuites.slice(
    (suitePage - 1) * suitePageSize,
    suitePage * suitePageSize
  );

  // toggle expand/collapse 1 suite
  const handleToggleSuite = (suiteId) => {
    setExpandedSuites((prev) => ({
      ...prev,
      [suiteId]: !prev[suiteId],
    }));
  };

  // render tree suites (root + children)
  const renderSuiteRows = (suites, level = 0) => {
    return suites.map((suite) => {
      const suiteId = suite.suite_id || "";
      const suiteName = suite.name || "—";
      const isExpanded = !!expandedSuites[suiteId];
      const hasChildren =
        Array.isArray(suite.children) && suite.children.length > 0;

      // handler mở màn Test Case
      const handleOpenTestCases = () => {
        if (!suiteId) return;
        navigate(`/projects/${id}/suites/${suiteId}/test-cases`, {
          state: {
            suiteName: suiteName,
            projectName: name, // tên project trên tab General
          },
        });
      };

      return (
        <React.Fragment key={suiteId}>
          <tr>
            <td className="px-4 py-3 text-slate-500">
              {hasChildren ? (
                <button
                  type="button"
                  onClick={() => handleToggleSuite(suiteId)}
                  className="inline-flex h-6 w-6 items-center justify-center rounded-full hover:bg-slate-100"
                >
                  <ChevronRight
                    className={`h-4 w-4 transition-transform ${isExpanded ? "rotate-90" : ""
                      }`}
                    stroke="#84828A"
                    strokeWidth={2}
                  />
                </button>
              ) : null}
            </td>

            {/* ID: thụt lề + nhánh cho child */}
            <td className="px-4 py-3 text-slate-800">
              <div style={{ paddingLeft: level * 24 }}>
                {level > 0 && <span className="mr-2 text-slate-400"></span>}
                {suiteId}
              </div>
            </td>

            {/* Name: thụt lề giống ID + click để mở màn TestCase */}
            <td className="px-4 py-3 text-slate-800">
              <div
                style={{ paddingLeft: level * 24 }}
                className="cursor-pointer hover:text-primary"
                onClick={handleOpenTestCases}
              >
                {suiteName}
              </div>
            </td>

            <td className="px-4 py-3">
              <div className="flex items-center gap-2 text-slate-500">
                {/* Add Test Suite Child */}
                <button
                  type="button"
                  className="inline-flex h-8 w-8 items-center justify-center rounded-full border border-slate-200 bg-white hover:bg-slate-50"
                  onClick={() => openCreateSuiteModal(suiteId)}
                >
                  <Plus className="h-4 w-4" stroke="#84828A" strokeWidth={2} />
                </button>

                {/* Edit */}
                <button
                  type="button"
                  className="inline-flex h-8 w-8 items-center justify-center rounded-full border border-slate-200 bg-white hover:bg-slate-50"
                  onClick={() => openEditSuiteModal(suite)}
                >
                  <Pencil
                    className="h-4 w-4"
                    stroke="#84828A"
                    strokeWidth={2.5}
                  />
                </button>

                {/* Delete */}
                <button
                  type="button"
                  onClick={() => openDeleteSuiteConfirm(suite)}
                  className="inline-flex h-8 w-8 items-center justify-center rounded-full border border-slate-200 bg-white hover:bg-slate-50"
                >
                  <Trash
                    className="h-4 w-4"
                    stroke="#84828A"
                    strokeWidth={2.5}
                  />
                </button>
              </div>
            </td>
          </tr>

          {isExpanded &&
            hasChildren &&
            renderSuiteRows(suite.children, level + 1)}
        </React.Fragment>
      );
    });
  };

  // ======= Members helpers =======
  const filteredMembers = members.filter((m) => {
    if (!memberSearch) return true;
    const text = `${m.fullname || m.name || m.user_id || ""}`.toLowerCase();
    return text.includes(memberSearch.toLowerCase());
  });

  const totalMembers = filteredMembers.length;
  const memberTotalPages = Math.max(1, Math.ceil(totalMembers / memberPageSize));
  const pagedMembers = filteredMembers.slice(
    (memberPage - 1) * memberPageSize,
    memberPage * memberPageSize
  );

  // ================== RENDER ==================
  return (
    <>
      <div className="space-y-4">
        {/* HEADER */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl text-slate-500">
              <button
                type="button"
                onClick={() => navigate("/projects")}
                className="text-slate-500 hover:text-primary "
              >
                Projects
              </button>
              <span className="mx-1">›</span>
              <span className="text-primary font-medium">{name}</span>
            </h1>
          </div>

          <button
            type="button"
            onClick={() => setIsEditOpen(true)}
            className="rounded-full border border-slate-200 bg-white px-4 py-2 text-xs font-medium text-slate-700 hover:bg-slate-50"
          >
            Edit Project
          </button>
        </div>

        {loadingProject && (
          <p className="text-sm text-slate-500">Đang tải thông tin project...</p>
        )}
        {errorProject && (
          <p className="text-sm text-red-500">{errorProject}</p>
        )}

        {/* CARD CHÍNH */}
        <div className="rounded-2xl border border-slate-200 bg-white shadow-sm">
          {/* Tabs */}
          <div className="px-6 pt-4 border-b border-slate-100">
            <div className="flex gap-6 text-sm">
              <button
                className={`pb-3 border-b-2 ${activeTab === "general"
                  ? "border-primary text-primary font-semibold"
                  : "border-transparent text-slate-500 hover:text-slate-700"
                  }`}
                onClick={() => setActiveTab("general")}
              >
                General
              </button>

              <button
                className={`pb-3 border-b-2 ${activeTab === "testsuite"
                  ? "border-primary text-primary font-semibold"
                  : "border-transparent text-slate-500 hover:text-slate-700"
                  }`}
                onClick={() => setActiveTab("testsuite")}
              >
                Test Suite
              </button>

              <button
                className={`pb-3 border-b-2 ${activeTab === "member"
                  ? "border-primary text-primary font-semibold"
                  : "border-transparent text-slate-500 hover:text-slate-700"
                  }`}
                onClick={() => setActiveTab("member")}
              >
                Member
              </button>
            </div>
          </div>

          {/* Nội dung tab */}
          <div className="px-6 py-6">
            {/* ========== TAB GENERAL ========== */}
            {activeTab === "general" && (
              <div className="grid gap-8 md:grid-cols-[2fr,1fr]">
                {/* LEFT */}
                <div className="space-y-4">
                  {/* Project Name */}
                  <div>
                    <label className="mb-1 block text-xs font-medium text-slate-600">
                      Project Name
                    </label>
                    <input
                      readOnly
                      value={name || ""}
                      className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-800 outline-none"
                    />
                  </div>

                  {/* Project Code */}
                  <div>
                    <label className="mb-1 block text-xs font-medium text-slate-600">
                      Project Code
                    </label>

                    <div className="flex items-center gap-2">
                      <input
                        readOnly
                        value={projectCode}
                        className="flex-1 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-800 outline-none"
                      />

                      <button
                        type="button"
                        onClick={handleCopyCode}
                        className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 bg-white hover:bg-slate-50"
                      >
                        <Clipboard
                          className="h-4 w-4"
                          stroke="#84828A"
                          strokeWidth={2}
                        />
                      </button>
                    </div>

                    {copied && (
                      <p className="mt-1 text-xs text-emerald-500">Copied!</p>
                    )}
                  </div>

                  {/* Description */}
                  <div>
                    <label className="mb-1 block text-xs font-medium text-slate-600">
                      Description
                    </label>
                    <textarea
                      readOnly
                      rows={3}
                      value={description}
                      className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-800 outline-none"
                    />
                  </div>

                  {/* Repository URL */}
                  <div>
                    <label className="mb-1 block text-xs font-medium text-slate-600">
                      Repository URL
                    </label>

                    {repoUrl ? (
                      <a
                        href={repoUrl}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-2 text-sm text-primary hover:underline"
                      >
                        <span className="text-lg"></span>
                        <span className="truncate max-w-xs">{repoUrl}</span>
                      </a>
                    ) : (
                      <p className="text-sm text-slate-400">—</p>
                    )}
                  </div>
                </div>

                {/* RIGHT */}
                <div className="space-y-4 text-sm">
                  {/* Owner */}
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-xs font-medium text-slate-600">
                        Project Owner
                      </div>

                      <div className="mt-2 flex items-center gap-2">
                        <div className="h-8 w-8 rounded-full bg-slate-200" />
                        <span className="text-slate-800">{ownerName}</span>
                      </div>
                    </div>

                    <button className="text-xs font-medium text-primary hover:underline">
                      Change owner
                    </button>
                  </div>

                  {/* Status */}
                  <div>
                    <div className="text-xs font-medium text-slate-600">
                      Status
                    </div>
                    <div className="mt-2">{renderStatusBadge()}</div>
                  </div>

                  {/* Dates */}
                  <div className="space-y-2 text-xs text-slate-600">
                    <div>
                      <span className="font-medium">Created At:</span>{" "}
                      <span>{createdAt}</span>
                    </div>
                    <div>
                      <span className="font-medium">Updated At:</span>{" "}
                      <span>{updatedAt}</span>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* ========== TAB TEST SUITE ========== */}
            {activeTab === "testsuite" && (
              <div className="space-y-4">
                {/* Top bar: search + buttons */}
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="relative w-64">
                    <Search
                      className="pointer-events-none absolute left-3 top-2.5 h-4 w-4"
                      stroke="#84828A"
                      strokeWidth={2}
                    />

                    <input
                      className="w-full rounded-full border border-slate-200 bg-white pl-9 pr-3 py-2 text-sm outline-none focus:border-primary focus:ring-2 focus:ring-primary/10"
                      placeholder="Search suites..."
                      value={suiteSearch}
                      onChange={(e) => {
                        setSuiteSearch(e.target.value);
                        setSuitePage(1);
                      }}
                    />
                  </div>

                  <div className="flex items-center gap-2">
                    <button className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-4 py-2 text-xs font-medium text-slate-700 hover:bg-slate-50">
                      <Filter
                        className="h-4 w-4"
                        stroke="#84828A"
                        strokeWidth={2}
                      />
                      Filter
                    </button>

                    <button
                      className="inline-flex items-center gap-2 rounded-full bg-primary px-4 py-2 text-xs font-medium text-white hover:bg-primary/90"
                      onClick={() => openCreateSuiteModal(null)} // root, không có parent
                    >
                      + Create New Test Suite
                    </button>
                  </div>
                </div>

                {/* Test Suite Table */}
                <div className="rounded-2xl border border-slate-200 bg-white shadow-sm">
                  {loadingSuites && (
                    <p className="px-6 py-4 text-sm text-slate-500">
                      Đang tải danh sách test suite...
                    </p>
                  )}
                  {errorSuites && (
                    <p className="px-6 py-4 text-sm text-red-500">
                      {errorSuites}
                    </p>
                  )}

                  {!loadingSuites && (
                    <div className="overflow-x-auto">
                      <table className="min-w-full text-sm">
                        <thead className="bg-slate-50 text-xs font-semibold text-slate-500">
                          <tr>
                            <th className="px-4 py-3 text-left w-10"></th>
                            <th className="px-4 py-3 text-left w-32">
                              Test Suite ID
                            </th>
                            <th className="px-4 py-3 text-left">
                              Test Suite Name
                            </th>
                            <th className="px-4 py-3 text-left w-32">
                              Actions
                            </th>
                          </tr>
                        </thead>

                        <tbody className="divide-y divide-slate-100">
                          {pagedSuites.length === 0 ? (
                            <tr>
                              <td
                                colSpan={4}
                                className="px-6 py-6 text-center text-slate-500 italic"
                              >
                                Không có dữ liệu
                              </td>
                            </tr>
                          ) : (
                            renderSuiteRows(pagedSuites)
                          )}
                        </tbody>
                      </table>
                    </div>
                  )}

                  {/* Footer pagination */}
                  <div className="flex items-center justify-between px-6 py-3 border-t border-slate-100 text-xs text-slate-500">
                    <span>
                      Showing{" "}
                      {totalSuites === 0
                        ? "0"
                        : `${(suitePage - 1) * suitePageSize + 1}-${Math.min(
                          suitePage * suitePageSize,
                          totalSuites
                        )}`}{" "}
                      of {totalSuites} suites
                    </span>

                    <div className="flex items-center gap-1">
                      <button
                        disabled={suitePage === 1}
                        onClick={() =>
                          setSuitePage((p) => Math.max(1, p - 1))
                        }
                        className="h-7 w-7 rounded-full border border-slate-200 text-center disabled:opacity-40"
                      >
                        {"<"}
                      </button>

                      {[...Array(suiteTotalPages)].map((_, i) => (
                        <button
                          key={i}
                          onClick={() => setSuitePage(i + 1)}
                          className={`h-7 min-w-[1.75rem] rounded-full text-center text-xs ${suitePage === i + 1
                            ? "bg-primary text-white"
                            : "text-slate-600 hover:bg-slate-100"
                            }`}
                        >
                          {i + 1}
                        </button>
                      ))}

                      <button
                        disabled={suitePage === suiteTotalPages}
                        onClick={() =>
                          setSuitePage((p) =>
                            Math.min(suiteTotalPages, p + 1)
                          )
                        }
                        className="h-7 w-7 rounded-full border border-slate-200 text-center disabled:opacity-40"
                      >
                        {">"}
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* ========== TAB MEMBER ========== */}
            {activeTab === "member" && (
              <div className="space-y-4">
                {/* Top bar */}
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="relative w-64">
                    <Search
                      className="pointer-events-none absolute left-3 top-2.5 h-4 w-4"
                      stroke="#84828A"
                      strokeWidth={2}
                    />

                    <input
                      className="w-full rounded-full border border-slate-200 bg-white pl-9 pr-3 py-2 text-sm outline-none focus:border-primary focus:ring-2 focus:ring-primary/10"
                      placeholder="Search by name"
                      value={memberSearch}
                      onChange={(e) => {
                        setMemberSearch(e.target.value);
                        setMemberPage(1);
                      }}
                    />
                  </div>

                  <button className="inline-flex items-center gap-2 rounded-full bg-primary px-4 py-2 text-xs font-medium text-white hover:bg-primary/90">
                    <Plus
                      className="h-4 w-4"
                      stroke="#84828A"
                      strokeWidth={2}
                    />
                    Add Member
                  </button>
                </div>

                {/* Members Table */}
                <div className="rounded-2xl border border-slate-200 bg-white shadow-sm">
                  {loadingMembers && (
                    <p className="px-6 py-4 text-sm text-slate-500">
                      Đang tải danh sách member...
                    </p>
                  )}
                  {errorMembers && (
                    <p className="px-6 py-4 text-sm text-red-500">
                      {errorMembers}
                    </p>
                  )}

                  {!loadingMembers && (
                    <div className="overflow-x-auto">
                      <table className="min-w-full text-sm">
                        <thead className="bg-slate-50 text-xs font-semibold text-slate-500">
                          <tr>
                            <th className="px-4 py-3 text-left w-12">STT</th>
                            <th className="px-4 py-3 text-left">Name</th>
                            <th className="px-4 py-3 text-left w-32">Role</th>
                            <th className="px-4 py-3 text-left w-40">
                              Joined At
                            </th>

                            {/* Action column widened */}
                            <th className="px-4 py-3 text-left w-48">Action</th>
                          </tr>
                        </thead>

                        <tbody className="divide-y divide-slate-100">
                          {pagedMembers.length === 0 ? (
                            <tr>
                              <td
                                colSpan={5}
                                className="px-6 py-6 text-center text-slate-500 italic"
                              >
                                Không có dữ liệu
                              </td>
                            </tr>
                          ) : (
                            pagedMembers.map((m, idx) => {
                              const fullName =
                                m.fullname || m.name || m.user_id || "—";
                              const role = m.role || m.project_role || "—";
                              const joinedAt = m.joined_at
                                ? formatDate(m.joined_at)
                                : "--";
                              const isOwner =
                                role.toLowerCase().includes("admin") ||
                                m.is_owner === true;

                              return (
                                <tr key={m.user_id || m.id || idx}>
                                  <td className="px-4 py-3 text-xs text-slate-500">
                                    {(memberPage - 1) * memberPageSize +
                                      idx +
                                      1}
                                  </td>

                                  <td className="px-4 py-3">
                                    <div className="flex items-center gap-3">
                                      <div className="h-8 w-8 rounded-full bg-slate-200" />
                                      <span className="text-slate-800">
                                        {fullName}
                                      </span>
                                    </div>
                                  </td>

                                  <td className="px-4 py-3 text-slate-700">
                                    {role}
                                  </td>

                                  <td className="px-4 py-3 text-xs text-slate-500">
                                    {joinedAt}
                                  </td>

                                  {/* Action cell widened */}
                                  <td className="px-4 py-3 w-48">
                                    {isOwner ? (
                                      <button className="rounded-full bg-primary px-4 py-1.5 text-xs font-medium text-white hover:bg-primary/90">
                                        Change Owner
                                      </button>
                                    ) : (
                                      <button className="rounded-full bg-primary px-4 py-1.5 text-xs font-medium text-white hover:bg-primary/90">
                                        Remove
                                      </button>
                                    )}
                                  </td>
                                </tr>
                              );
                            })
                          )}
                        </tbody>
                      </table>
                    </div>
                  )}

                  {/* Footer */}
                  <div className="flex items-center justify-between px-6 py-3 border-t border-slate-100 text-xs text-slate-500">
                    <span>
                      Showing{" "}
                      {totalMembers === 0
                        ? "0"
                        : `${(memberPage - 1) * memberPageSize + 1}-${Math.min(
                          memberPage * memberPageSize,
                          totalMembers
                        )}`}{" "}
                      of {totalMembers} members
                    </span>

                    <div className="flex items-center gap-1">
                      <button
                        disabled={memberPage === 1}
                        onClick={() =>
                          setMemberPage((p) => Math.max(1, p - 1))
                        }
                        className="h-7 w-7 rounded-full border border-slate-200 text-center disabled:opacity-40"
                      >
                        {"<"}
                      </button>

                      {[...Array(memberTotalPages)].map((_, i) => (
                        <button
                          key={i}
                          onClick={() => setMemberPage(i + 1)}
                          className={`h-7 min-w-[1.75rem] rounded-full text-center text-xs ${memberPage === i + 1
                            ? "bg-primary text-white"
                            : "text-slate-600 hover:bg-slate-100"
                            }`}
                        >
                          {i + 1}
                        </button>
                      ))}

                      <button
                        disabled={memberPage === memberTotalPages}
                        onClick={() =>
                          setMemberPage((p) =>
                            Math.min(memberTotalPages, p + 1)
                          )
                        }
                        className="h-7 w-7 rounded-full border border-slate-200 text-center disabled:opacity-40"
                      >
                        {">"}
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Modal Create Test Suite */}
      <CreateTestSuiteModal
        isOpen={isCreateSuiteOpen}
        onClose={() => {
          setIsCreateSuiteOpen(false);
          setEditingSuite(null); // Reset dữ liệu edit khi đóng
        }}

        // Props cho Create
        onCreate={handleSuiteCreated}
        projectId={id}
        parentSuiteId={parentSuiteId}

        // ✅ Props cho Edit (Mới thêm)
        suiteData={editingSuite}
        onUpdate={handleUpdateSuite}
      />
      {/* Confirm Delete Test Suite */}
      <ConfirmModal
        isOpen={isConfirmOpen}
        onCancel={handleCancelDeleteSuite}
        onConfirm={async () => {
          await handleConfirmDeleteSuite();
        }}
        title="Delete Test Suite"
        message={
          suiteToDelete
            ? `Are you sure you want to delete test suite "${suiteToDelete.name}"?`
            : "Are you sure you want to delete this test suite?"
        }
        successTitle="Deleted Successfully"
        successMessage="The test suite and its children (if any) have been deleted."
        forbiddenTitle="Permission Denied"
        forbiddenMessage="You do not have permission to delete this test suite."
      />
      {/* ✅ Thêm Modal Edit vào đây */}
      <CreateProjectModal
        isOpen={isEditOpen}
        onClose={() => setIsEditOpen(false)}
        projectData={project}          // Truyền dữ liệu cũ vào để form tự điền
        onUpdate={handleUpdateProject} // Truyền hàm xử lý Update
      />
    </>
  );
}
