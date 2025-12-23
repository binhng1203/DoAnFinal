import React, { useEffect, useState } from "react";
import {
  MagnifyingGlassIcon,
  FunnelIcon,
  ChevronDownIcon,
  EyeIcon,
} from "@heroicons/react/24/outline";
import { useNavigate } from "react-router-dom";
import apiClient from "../../services/apiClient";

export default function KnowledgeBasePage() {
  const navigate = useNavigate();

  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Filters
  const [search, setSearch] = useState("");
  const [sourceType, setSourceType] = useState("All");

  // Paging
  const [page, setPage] = useState(1);
  const pageSize = 10;
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(1);

  const formatDateTime = (value) => {
    if (!value) return "—";
    const d = new Date(value);
    return isNaN(d.getTime()) ? value : d.toLocaleString();
  };

  const renderLocator = (by, value) => {
    if (!value) return <span className="text-slate-400">—</span>;
    const full = `${by || "locator"}: ${value}`;
    const maxLen = 60;
    const display = full.length > maxLen ? full.slice(0, maxLen - 3) + "..." : full;
    return (
      <span className="text-xs text-slate-600 max-w-xs truncate inline-block" title={full}>
        {display}
      </span>
    );
  };

  // 📡 GỌI API VỚI SERVER-SIDE SEARCH & FILTER
  useEffect(() => {
    const fetchKnowledgeBase = async () => {
      try {
        setLoading(true);
        setError("");

        const response = await apiClient.get("/api/v1/locators", {
          params: {
            page,
            limit: pageSize,
            keyword: search || undefined, // Gửi keyword lên BE
            source_type: sourceType !== "All" ? sourceType : undefined,
          },
        });

        setRows(Array.isArray(response.items) ? response.items : []);
        setTotal(response.total ?? 0);
        setTotalPages(response.pages ?? 1);
      } catch (err) {
        console.error("API Error:", err);
        setError("Không thể tải dữ liệu từ máy chủ.");
      } finally {
        setLoading(false);
      }
    };

    // Áp dụng Debounce 500ms để giảm tải API khi gõ search
    const delayDebounceFn = setTimeout(() => {
      fetchKnowledgeBase();
    }, 500);

    return () => clearTimeout(delayDebounceFn);
  }, [page, search, sourceType]); // Chạy lại khi trang hoặc bộ lọc thay đổi

  const handleClearFilters = () => {
    setSearch("");
    setSourceType("All");
    setPage(1);
  };

  const renderSuccessCell = (value) => {
    const percent = parseFloat(value) || 0;
    const barColor = percent >= 80 ? "bg-emerald-500" : percent >= 50 ? "bg-yellow-400" : "bg-red-500";

    return (
      <div className="flex items-center gap-2">
        <div className="h-1.5 w-16 rounded-full bg-slate-100">
          <div
            className={`h-1.5 rounded-full ${barColor}`}
            style={{ width: `${Math.min(100, percent)}%` }}
          />
        </div>
        <span className="text-xs font-medium text-slate-700">{percent}%</span>
      </div>
    );
  };

  return (
    <div className="space-y-4 p-4">
      <h1 className="text-2xl font-semibold text-slate-800">Healing Knowledge Base</h1>

      {/* FILTER BAR */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-3">
          {/* Search Input */}
          <div className="relative w-64">
            <MagnifyingGlassIcon className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
            <input
              className="w-full rounded-full border border-slate-200 bg-white pl-9 pr-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/10"
              placeholder="Search project or locator..."
              value={search}
              onChange={(e) => { setSearch(e.target.value); setPage(1); }} // Reset về trang 1 khi search
            />
          </div>

          {/* Source Type Filter */}
          <select 
            className="rounded-full border border-slate-200 bg-white px-4 py-1.5 text-xs text-slate-600 outline-none"
            value={sourceType}
            onChange={(e) => { setSourceType(e.target.value); setPage(1); }}
          >
            <option value="All">Source Type: All</option>
            <option value="AUTO">AUTO</option>
            <option value="MANUAL">MANUAL</option>
          </select>
        </div>

        <button
          onClick={handleClearFilters}
          className="inline-flex items-center gap-2 rounded-full bg-primary px-4 py-2 text-xs font-semibold text-white hover:bg-primary/90"
        >
          <FunnelIcon className="h-4 w-4" />
          Clear Filters
        </button>
      </div>

      {/* TABLE CARD */}
      <div className="rounded-2xl border border-slate-200 bg-white shadow-sm overflow-hidden">
        {error && <p className="px-6 py-4 text-sm text-red-500">{error}</p>}

        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-50 text-xs font-semibold text-slate-500">
              <tr>
                <th className="px-4 py-3 text-left w-12">STT</th>
                <th className="px-4 py-3 text-left">Project ID</th>
                <th className="px-4 py-3 text-left">Old Locator</th>
                <th className="px-4 py-3 text-left">New Locator</th>
                <th className="px-4 py-3 text-left">Success Rate</th>
                <th className="px-4 py-3 text-left">Avg Repair</th>
                <th className="px-4 py-3 text-left">Last Healing</th>
                <th className="px-4 py-3 text-center w-20">Actions</th>
              </tr>
            </thead>

            <tbody className="divide-y divide-slate-100">
              {loading ? (
                <tr><td colSpan={8} className="px-6 py-10 text-center text-slate-400 italic">Đang tải dữ liệu...</td></tr>
              ) : rows.length === 0 ? (
                <tr><td colSpan={8} className="px-6 py-10 text-center text-slate-400 italic">Không có dữ liệu</td></tr>
              ) : (
                rows.map((row, idx) => (
                  <tr key={row.id || idx} className="hover:bg-slate-50 transition-colors">
                    <td className="px-4 py-3 text-xs text-slate-400">{(page - 1) * pageSize + idx + 1}</td>
                    <td className="px-4 py-3 font-medium text-slate-700">{row.project_id}</td>
                    <td className="px-4 py-3">{renderLocator(row.old_locator_by, row.old_locator_value)}</td>
                    <td className="px-4 py-3">{renderLocator(row.new_locator_by, row.new_locator_value)}</td>
                    <td className="px-4 py-3">{renderSuccessCell(row.success_rate)}</td>
                    <td className="px-4 py-3 text-slate-600">{row.avg_repair_ms ? `${row.avg_repair_ms}ms` : "—"}</td>
                    <td className="px-4 py-3 text-slate-500 text-xs">{formatDateTime(row.updated_at)}</td>
                    <td className="px-4 py-3 text-center">
                      <button
                        onClick={() => navigate(`/knowledge-base/${row.id}`)}
                        className="p-1.5 text-slate-400 hover:text-primary hover:bg-primary/5 rounded-full transition-colors"
                      >
                        <EyeIcon className="h-4 w-4" />
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* PAGINATION */}
        <div className="flex items-center justify-between px-6 py-3 border-t border-slate-100 text-xs text-slate-500">
          <span>Showing {total === 0 ? 0 : (page - 1) * pageSize + 1} to {Math.min(page * pageSize, total)} of {total} records</span>
          <div className="flex items-center gap-1">
            <button 
                disabled={page === 1} 
                onClick={() => setPage(p => p - 1)}
                className="h-7 w-7 rounded-full border border-slate-200 disabled:opacity-30"
            >{"<"}</button>
            <span className="px-2">Page {page} of {totalPages}</span>
            <button 
                disabled={page === totalPages} 
                onClick={() => setPage(p => p + 1)}
                className="h-7 w-7 rounded-full border border-slate-200 disabled:opacity-30"
            >{">"}</button>
          </div>
        </div>
      </div>
    </div>
  );
}