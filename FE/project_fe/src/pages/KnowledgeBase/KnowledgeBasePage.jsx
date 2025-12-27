import React, { useEffect, useState } from "react";
import {
  MagnifyingGlassIcon,
  FunnelIcon,
  ChevronDownIcon,
  EyeIcon,
} from "@heroicons/react/24/outline";
import { useNavigate } from "react-router-dom";
import apiClient from "../../services/apiClient"; // 💡 dùng axios client chung

export default function KnowledgeBasePage() {
  const navigate = useNavigate();

  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // filters (UI, chờ ghép BE thêm)
  const [search, setSearch] = useState("");
  const [sourceType, setSourceType] = useState("All");
  const [successFilter, setSuccessFilter] = useState("All");
  const [lastUpdated, setLastUpdated] = useState("All");
  const [appVersion, setAppVersion] = useState("All");

  // paging (theo BE)
  const [page, setPage] = useState(1);
  const pageSize = 10;
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(1);

  // format datetime đơn giản
  const formatDateTime = (value) => {
    if (!value) return "—";
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return value;
    return d.toLocaleString();
  };

  // Locator dài -> rút gọn, hover thấy full
  const renderLocator = (by, value) => {
    if (!value) return <span className="text-slate-400">—</span>;

    const full = `${by || "locator"}: ${value}`;
    const maxLen = 60;
    const display =
      full.length > maxLen ? full.slice(0, maxLen - 3) + "..." : full;

    return (
      <span
        className="text-sm text-slate-600 max-w-xs truncate inline-block"
        title={full} // hover để xem full locator
      >
        {display}
      </span>
    );
  };

  useEffect(() => {
    async function fetchKnowledgeBase() {
      try {
        setLoading(true);
        setError("");

        // 📡 GỌI API THẬT
        const data = await apiClient.get("/api/v1/locators", {
          params: {
            page,
            limit: pageSize,
          },
        });

        // data = { current_page, items, pages, total }
        setRows(Array.isArray(data.items) ? data.items : []);
        setTotal(data.total ?? 0);
        setTotalPages(data.pages ?? 1);
      } catch (err) {
        console.error(err);
        setError("Không thể tải dữ liệu. Vui lòng thử lại.");
        setRows([]);
        setTotal(0);
        setTotalPages(1);
      } finally {
        setLoading(false);
      }
    }

    fetchKnowledgeBase();
  }, [page]);

  const handleClearFilters = () => {
    setSearch("");
    setSourceType("All");
    setSuccessFilter("All");
    setLastUpdated("All");
    setAppVersion("All");
  };

  // Filter tạm thời (search client-side trên page hiện tại)
  const filteredRows = rows.filter((r) => {
    const text = (
      `${r.project_id || ""} ` +
      `${r.old_locator_value || ""} ` +
      `${r.new_locator_value || ""}`
    ).toLowerCase();

    if (search && !text.includes(search.toLowerCase())) return false;

    // sourceType, successFilter, lastUpdated, appVersion: để sau ghép thêm field BE
    return true;
  });

  // hiển thị range theo page & số row sau filter
  const showingFrom = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const showingTo =
    total === 0
      ? 0
      : (page - 1) * pageSize + Math.min(filteredRows.length, pageSize);

  const renderSuccessCell = (value) => {
    if (value == null) return <span className="text-slate-400">—</span>;

    const percent =
      typeof value === "number"
        ? value
        : parseInt(String(value).replace("%", ""), 10) || 0;

    const barColor =
      percent >= 80
        ? "bg-emerald-500"
        : percent >= 50
        ? "bg-yellow-400"
        : "bg-red-500";

    return (
      <div className="flex items-center gap-3">
        <div className="h-2 w-20 rounded-full bg-slate-100">
          <div
            className={`h-full rounded-full ${barColor}`}
            style={{ width: `${Math.min(100, Math.max(0, percent))}%` }}
          />
        </div>
        <span className="text-sm font-medium text-slate-700">
          {percent}%
        </span>
      </div>
    );
  };

  return (
    <div className="space-y-4">
      {/* TITLE */}
      <h1 className="text-2xl font-semibold text-slate-800">
        Healing Knowledge Base
      </h1>

      {/* FILTER BAR */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-3">
          {/* Search */}
          <div className="relative w-64">
            <MagnifyingGlassIcon className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
            <input
              className="w-full rounded-full border border-slate-200 bg-white pl-9 pr-3 py-2 text-sm outline-none focus:border-primary focus:ring-2 focus:ring-primary/10"
              placeholder="Search by locator name, value, or..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>

          {/* Các filter khác: hiện mới UI, chưa ghép logic */}
          <button className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-50">
            <span>Source Type: {sourceType}</span>
            <ChevronDownIcon className="h-3 w-3" />
          </button>

          <button className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-50">
            <span>Success Rate: {successFilter}</span>
            <ChevronDownIcon className="h-3 w-3" />
          </button>

          <button className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-50">
            <span>Last Updated: {lastUpdated}</span>
            <ChevronDownIcon className="h-3 w-3" />
          </button>

          <button className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-50">
            <span>App Version: {appVersion}</span>
            <ChevronDownIcon className="h-3 w-3" />
          </button>
        </div>

        {/* Clear Filters */}
        <button
          onClick={handleClearFilters}
          className="inline-flex items-center gap-2 rounded-full bg-primary px-4 py-2 text-xs font-semibold text-white hover:bg-primary/90"
        >
          <FunnelIcon className="h-4 w-4" />
          Clear Filters
        </button>
      </div>

      {/* TABLE CARD */}
      <div className="rounded-2xl border border-slate-200 bg-white shadow-sm">
        {loading && (
          <p className="px-6 py-4 text-sm text-slate-500">
            Đang tải dữ liệu...
          </p>
        )}

        {error && (
          <p className="px-6 py-4 text-sm text-red-500">{error}</p>
        )}

        {/* TABLE */}
        {!loading && (
          <div className="overflow-x-auto">
            <table className="min-w-full text-base">
              <thead className="bg-slate-50 text-base font-semibold text-slate-500">
                <tr>
                  <th className="px-6 py-4 text-left w-12">STT</th>
                  <th className="px-6 py-4 text-left">Project ID</th>
                  <th className="px-6 py-4 text-left">Old Locator</th>
                  <th className="px-6 py-4 text-left">New Locator</th>
                  <th className="px-6 py-4 text-left">Success Rate</th>
                  <th className="px-6 py-4 text-left">Avg Repair Time</th>
                  <th className="px-6 py-4 text-left">Last Healing</th>
                  <th className="px-6 py-4 text-left w-20">Actions</th>
                </tr>
              </thead>

              <tbody className="divide-y divide-slate-100">
                {filteredRows.length === 0 ? (
                  <tr>
                    <td
                      colSpan={8}
                      className="px-6 py-8 text-center text-slate-500 italic"
                    >
                      Không có dữ liệu
                    </td>
                  </tr>
                ) : (
                  filteredRows.map((row, idx) => {
                    const detailId = row.id;

                    return (
                      <tr
                        key={detailId ?? idx}
                        className="hover:bg-slate-50"
                      >
                        <td className="px-6 py-4 text-sm text-slate-500">
                          {(page - 1) * pageSize + idx + 1}
                        </td>
                        <td className="px-6 py-4 text-slate-800">
                          {row.project_id ?? "—"}
                        </td>
                        <td className="px-6 py-4">
                          {renderLocator(
                            row.old_locator_by,
                            row.old_locator_value
                          )}
                        </td>
                        <td className="px-6 py-4">
                          {renderLocator(
                            row.new_locator_by,
                            row.new_locator_value
                          )}
                        </td>
                        <td className="px-6 py-4">
                          {renderSuccessCell(row.success_rate)}
                        </td>
                        <td className="px-6 py-4 text-slate-700">
                          {row.avg_repair_ms != null
                            ? `${row.avg_repair_ms} ms`
                            : "—"}
                        </td>
                        <td className="px-6 py-4 text-slate-500 text-xs">
                          {formatDateTime(row.last_updated)}
                        </td>
                        <td className="px-6 py-4">
                          <button
                            disabled={!detailId}
                            onClick={() =>
                              detailId &&
                              navigate(`/knowledge-base/${detailId}`)
                            }
                            className="inline-flex items-center justify-center rounded-full border border-slate-200 p-1.5 text-slate-500 hover:bg-slate-100 disabled:opacity-40 disabled:cursor-not-allowed"
                          >
                            <EyeIcon className="h-4 w-4" />
                          </button>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        )}

        {/* FOOTER: info + pagination */}
        <div className="flex items-center justify-between px-6 py-3 border-t border-slate-100 text-sm text-slate-500">
          <span>
            Showing {total === 0 ? "0" : `${showingFrom}-${showingTo}`} of{" "}
            {total} records
          </span>

          <div className="flex items-center gap-2">
            <button
              disabled={page === 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              className="h-7 w-7 rounded-full border border-slate-200 text-center disabled:opacity-40"
            >
              {"<"}
            </button>
            {[...Array(totalPages)].map((_, i) => (
              <button
                key={i}
                onClick={() => setPage(i + 1)}
                className={`h-7 min-w-[1.75rem] rounded-full text-center text-xs ${
                  page === i + 1
                    ? "bg-primary text-white"
                    : "text-slate-600 hover:bg-slate-100"
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
              className="h-7 w-7 rounded-full border border-slate-200 text-center disabled:opacity-40"
            >
              {">"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
