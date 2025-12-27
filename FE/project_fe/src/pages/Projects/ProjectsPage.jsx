// src/pages/Projects/ProjectsPage.jsx
import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { Pencil, Trash, User } from "lucide-react";

import Button from "../../components/ui/Button";
import ProjectCard from "../../components/projects/ProjectCard.jsx";
import projectService from "../../services/projectService";
import { formatDate } from "../../utils/formatDate";
import CreateProjectModal from "../../components/projects/CreateProjectModal";
import JoinProjectModal from "../../components/projects/JoinProjectModal";
import ConfirmModal from "../../components/common/ConfirmModal";

export default function ProjectsPage() {
  const navigate = useNavigate();

  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [viewMode, setViewMode] = useState("card");

  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [isJoinOpen, setIsJoinOpen] = useState(false);

  // ===== XÓA PROJECT (Popup) =====
  const [deleteId, setDeleteId] = useState(null);
  const [isConfirmOpen, setIsConfirmOpen] = useState(false);

  // ================== LOAD PROJECTS ==================
  useEffect(() => {
    async function fetchProjects() {
      try {
        setLoading(true);
        setError("");

        const data = await projectService.getProjects();
        console.log("Projects API response:", data);

        if (Array.isArray(data)) {
          const mapped = data.map((p) => ({
            ...p,
            role: p.creator_username || "Unknow Owner",
            status: p.status || "active",
          }));
          setProjects(mapped);
        } else {
          setProjects([]);
        }
      } catch (err) {
        console.error(err);
        setError("Không thể tải danh sách projects. Vui lòng thử lại.");
      } finally {
        setLoading(false);
      }
    }

    fetchProjects();
  }, []);

  // ================== HANDLERS ==================
  const handleCreateProject = async (payload) => {
    try {
      const data = await projectService.createProject(payload);
      const p = data.project;

      if (!p) throw new Error("Invalid project response");

      const newProject = {
        ...p,
        role: p.my_role || "Owner",
        status: p.status || "active",
      };

      setProjects((prev) => [...prev, newProject]);
      setIsCreateOpen(false);
    } catch (e) {
      console.error(e);
      alert("Tạo project thất bại!");
    }
  };

  // Callback này hiện tại chỉ log, nếu sau này bạn muốn reload list
  // sau khi join thành công thì có thể fetchProjects() ở đây.
  const handleJoinProject = (projectCode) => {
    console.log("Joined project with code:", projectCode);
    // TODO: nếu backend trả project mới hoặc thay đổi list,
    // có thể gọi lại API getProjects() ở đây.
  };

  const handleOpenDetail = (projectId) => {
    if (!projectId) return;
    navigate(`/projects/${projectId}`);
  };

  // mở popup xoá
  const requestDelete = (id) => {
    setDeleteId(id);
    setIsConfirmOpen(true);
  };

  // ====== XÁC NHẬN XOÁ: GỌI API DELETE ======
  const confirmDelete = async () => {
    // 1. Kiểm tra ID
    if (!deleteId) return;

    try {
      // 2. Gọi API qua Service (Tự động xử lý Token và Lỗi)
      await projectService.deleteProject(deleteId);

      // 3. Cập nhật State (Xoá dự án khỏi danh sách trên màn hình)
      setProjects((prev) => prev.filter((p) => p.project_id !== deleteId));

    } catch (err) {
      console.error("Delete project error:", err);
      // Ném lỗi ra để ConfirmModal bắt được và hiện giao diện lỗi (Permission Denied hoặc lỗi khác)
      throw err;
    }
  };

  const renderStatusText = (status) => {
    const s = status?.toLowerCase();
    if (s === "active") return "Active";
    if (s === "pending") return "Pending";
    if (s === "completed") return "Completed";
    return "Unknown";
  };

  // ================== RENDER ==================
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold text-slate-800">Projects</h1>

      {/* TOP BAR */}
      <div className="flex items-center justify-end gap-3 flex-wrap">
        <div className="w-full md:w-72">
          <input
            className="w-full rounded-full border border-slate-200 bg-white px-5 py-2.5 text-base outline-none focus:border-primary focus:ring-2 focus:ring-primary/10"
            placeholder="Search for..."
          />
        </div>

        <div className="flex items-center gap-1 rounded-full border border-slate-200 bg-white p-1.5 shadow-sm">
          <button
            onClick={() => setViewMode("card")}
            className={`px-3 py-1 rounded-full transition ${
              viewMode === "card"
                ? "bg-primary text-white"
                : "text-slate-600 hover:bg-slate-100"
            }`}
          >
            Card View
          </button>

          <button
            onClick={() => setViewMode("list")}
            className={`px-3 py-1 rounded-full transition ${
              viewMode === "list"
                ? "bg-primary text-white"
                : "text-slate-600 hover:bg-slate-100"
            }`}
          >
            List View
          </button>
        </div>

        <Button variant="primary" onClick={() => setIsCreateOpen(true)}>
          + New Project
        </Button>
        <Button variant="outline" onClick={() => setIsJoinOpen(true)}>
          + Join Project
        </Button>
      </div>

      {/* CONTENT */}
      {loading && (
        <p className="text-sm text-slate-500">Đang tải projects...</p>
      )}
      {error && <p className="text-sm text-red-500">{error}</p>}

      {/* ======================== CARD VIEW ======================== */}
      {!loading && !error && viewMode === "card" && (
        <>
          {projects.length === 0 ? (
            <p className="text-base text-slate-500">Không có project nào.</p>
          ) : (
            <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {projects.map((p) => (
                <div
                  key={p.project_id}
                  className="cursor-pointer"
                  onClick={() => handleOpenDetail(p.project_id)}
                >
                  <ProjectCard
                    name={p.name}
                    description={p.description}
                    role={p.role}
                    status={renderStatusText(p.status)}
                    createdAt={formatDate(p.created_at)}
                    onEdit={(e) => {
                      e.stopPropagation();
                      handleOpenDetail(p.project_id);
                    }}
                    onDelete={(e) => {
                      e.stopPropagation();
                      requestDelete(p.project_id);
                    }}
                  />
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {/* ======================== LIST VIEW ======================== */}
      {!loading && !error && viewMode === "list" && (
        <div className="mt-2 overflow-x-auto">
          <div className="min-w-full rounded-2xl bg-white border border-slate-200 shadow-sm">
            <table className="min-w-full text-base">
              <thead className="bg-slate-50 text-base font-semibold text-slate-500">
                <tr>
                  <th className="px-6 py-4 text-left">Project Name</th>
                  <th className="px-6 py-4 text-left">Owner</th>
                  <th className="px-6 py-4 text-left">Status</th>
                  <th className="px-6 py-4 text-left">Created Date</th>
                  <th className="px-6 py-4 text-left">Actions</th>
                </tr>
              </thead>

              <tbody className="divide-y divide-slate-100">
                {projects.length === 0 ? (
                  <tr>
                    <td
                      colSpan={5}
                      className="px-6 py-8 text-center text-slate-500 italic"
                    >
                      Không có dữ liệu
                    </td>
                  </tr>
                ) : (
                  projects.map((p) => (
                    <tr key={p.project_id} className="hover:bg-slate-50">
                      {/* Name */}
                      <td className="px-6 py-4">
                        <button
                          type="button"
                          onClick={() => handleOpenDetail(p.project_id)}
                        >
                          <div className="flex flex-col text-left">
                            <span className="text-lg font-medium text-slate-800">
                              {p.name}
                            </span>
                            {p.description && (
                              <span className="text-sm text-slate-500">
                                {p.description}
                              </span>
                            )}
                          </div>
                        </button>
                      </td>

                      {/* Owner */}
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-2">
                          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-slate-100 border border-slate-200 text-slate-500">
                            <User className="h-4 w-4" strokeWidth={2.5} />
                          </div>
                          <span className="text-slate-700 text-base">
                            {p.role}
                          </span>
                        </div>
                      </td>

                      {/* Status */}
                      <td className="px-6 py-4">
                        {renderStatusText(p.status)}
                      </td>

                      {/* Created At */}
                      <td className="px-6 py-4 text-slate-500">
                        {formatDate(p.created_at)}
                      </td>

                      {/* Actions */}
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-2">
                          <button
                            className="inline-flex h-8 w-8 items-center justify-center rounded-full border border-slate-200 hover:bg-slate-50"
                            onClick={() => handleOpenDetail(p.project_id)}
                          >
                            <Pencil
                              className="h-4 w-4"
                              stroke="#84828A"
                              strokeWidth={2}
                            />
                          </button>

                          <button
                            className="inline-flex h-8 w-8 items-center justify-center rounded-full border border-slate-200 hover:bg-slate-50"
                            onClick={() => requestDelete(p.project_id)}
                          >
                            <Trash
                              className="h-4 w-4"
                              stroke="#84828A"
                              strokeWidth={2}
                            />
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
      )}

      <p className="mt-4 text-sm text-slate-500">
        Showing {projects.length} projects
      </p>

      {/* MODALS */}
      <CreateProjectModal
        isOpen={isCreateOpen}
        onClose={() => setIsCreateOpen(false)}
        onCreate={handleCreateProject}
      />

      <JoinProjectModal
        isOpen={isJoinOpen}
        onClose={() => setIsJoinOpen(false)}
        onJoin={handleJoinProject}
      />

      {/* ===== Confirm Delete Popup ===== */}
      <ConfirmModal
        isOpen={isConfirmOpen}
        title="Notification"
        message="Are you sure you want to delete this project?"
        onCancel={() => {
          setIsConfirmOpen(false);
          setDeleteId(null);
        }}
        onConfirm={confirmDelete}
        successTitle="Deleted Successfully"
        successMessage="The project has been removed from the system."
      />
    </div>
  );
}
