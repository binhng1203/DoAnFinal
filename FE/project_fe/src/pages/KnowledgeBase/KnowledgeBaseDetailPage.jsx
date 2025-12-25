import React, { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import {
  ArrowDownIcon,
  InformationCircleIcon,
} from "@heroicons/react/24/outline";
import apiClient from "../../services/apiClient"; // chỉnh path nếu khác

export default function KnowledgeBaseDetailPage() {
  const { id } = useParams(); // locator id từ URL

  const [item, setItem] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [activeTab, setActiveTab] = useState("metrics"); // "metrics" | "system"

  const formatDateTime = (value) => {
    if (!value) return "—";
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return value;
    return d.toLocaleString();
  };

  useEffect(() => {
    async function fetchDetail() {
      try {
        setLoading(true);
        setError("");

        // 🔗 GỌI API THẬT
        // GET /api/v1/locators/{id}/history
        const data = await apiClient.get(`/api/v1/locators/${id}/history`);

        setItem(data || null);
      } catch (err) {
        console.error(err);
        setError("Không thể tải dữ liệu. Vui lòng thử lại.");
        setItem(null);
      } finally {
        setLoading(false);
      }
    }

    if (id) {
      fetchDetail();
    }
  }, [id]);

  // ====== MAP DỮ LIỆU TỪ API ======
  const oldLocator =
    item?.old_locator_value || "[Old Locator Value]";
  const newLocator = item?.new_locator_value || "";

  const oldBy = (item?.old_locator_by || "locator").toUpperCase();
  const newBy = (item?.new_locator_by || "locator").toUpperCase();

  const successRate =
    item?.success_rate != null ? item.success_rate : null;
  const totalSuccess =
    item?.success_count != null ? item.success_count : null;
  const totalFailure =
    item?.failure_count != null ? item.failure_count : null;
  const avgRepairTime =
    item?.avg_repair_ms != null ? item.avg_repair_ms : null;

  const lastUpdated = item?.last_updated
    ? formatDateTime(item.last_updated)
    : "—";

  const commitInfo = item?.commit_info || null;
  const appVersion = item?.app_version || commitInfo?.app_version || "—";
  const projectId = item?.project_id || "—";
  const sourceType = item?.source_type || "—";
  const locatorId = item?.id || id;

  // BE hiện chưa trả recent_healing_events -> để rỗng
  const recentEvents = item?.recent_healing_events || [];

  return (
    <div className="space-y-4">
      {/* BREADCRUMB + TITLE */}
      <div className="flex flex-col gap-1">
        <div className="text-xs text-slate-500">
          Healing Knowledge Base{" "}
          <span className="mx-1">›</span>
          <span className="text-primary font-medium">
            {oldLocator}
          </span>
        </div>
        <h1 className="text-2xl font-semibold text-slate-800">
          Locator Mapping
        </h1>
      </div>

      {/* THÔNG BÁO LOADING / ERROR */}
      {loading && (
        <p className="text-sm text-slate-500">
          Đang tải dữ liệu chi tiết...
        </p>
      )}
      {error && (
        <p className="text-sm text-red-500">
          {error}
        </p>
      )}

      {/* CARD CHÍNH */}
      <div className="rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="p-6 space-y-6">
          {/* LOCATOR MAPPING */}
          <section className="space-y-4">
            {/* Old locator */}
            <div className="space-y-1">
              <div className="text-xs font-semibold text-slate-500 uppercase tracking-wide">
                Old Locator
              </div>
              <div className="inline-flex items-center rounded-full border border-slate-200 px-3 py-1 text-xs text-slate-500 gap-1">
                <span className="text-[10px] font-semibold">
                  {oldBy}
                </span>
              </div>
              <textarea
                className="mt-1 w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-700 outline-none"
                rows={2}
                readOnly
                value={oldLocator || ""}
              />
            </div>

            {/* Arrow */}
            <div className="flex justify-center">
              <ArrowDownIcon className="h-5 w-5 text-slate-400" />
            </div>

            {/* New locator */}
            <div className="space-y-1">
              <div className="text-xs font-semibold text-slate-500 uppercase tracking-wide">
                New Locator
              </div>
              <div className="inline-flex items-center rounded-full border border-slate-200 px-3 py-1 text-xs text-slate-500 gap-1">
                <span className="text-[10px] font-semibold">
                  {newBy}
                </span>
              </div>
              <textarea
                className="mt-1 w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-700 outline-none"
                rows={2}
                readOnly
                value={newLocator || ""}
              />
            </div>
          </section>

          {/* RECENT HEALING EVENTS */}
          <section className="border-t border-slate-100 pt-4">
            <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">
              Recent Healing Events
            </h3>
            {recentEvents.length === 0 ? (
              <p className="text-xs text-slate-400">
                Không có dữ liệu.
              </p>
            ) : (
              <ul className="text-xs text-slate-600 space-y-1">
                {recentEvents.map((ev, idx) => (
                  <li key={idx} className="flex gap-2">
                    <span>{ev.timestamp}</span>
                    {ev.id && (
                      <button className="text-primary hover:underline">
                        {ev.id}
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </section>

          {/* TABS */}
          <section className="pt-4">
            <div className="flex gap-4 border-b border-slate-200 text-sm">
              <button
                className={`pb-2 border-b-2 ${
                  activeTab === "metrics"
                    ? "border-primary text-primary font-semibold"
                    : "border-transparent text-slate-500 hover:text-slate-700"
                }`}
                onClick={() => setActiveTab("metrics")}
              >
                Performance Metrics
              </button>
              <button
                className={`pb-2 border-b-2 ${
                  activeTab === "system"
                    ? "border-primary text-primary font-semibold"
                    : "border-transparent text-slate-500 hover:text-slate-700"
                }`}
                onClick={() => setActiveTab("system")}
              >
                System & Metadata
              </button>
            </div>

            {activeTab === "metrics" ? (
              <div className="mt-4 grid gap-4 md:grid-cols-4">
                {/* Total success */}
                <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                  <div className="flex items-center justify-between text-xs text-slate-500">
                    <span>Total Success Count</span>
                    <InformationCircleIcon className="h-4 w-4" />
                  </div>
                  <div className="mt-2 text-2xl font-semibold text-emerald-600">
                    {totalSuccess != null ? totalSuccess : "--"}
                  </div>
                </div>

                {/* Total failure */}
                <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                  <div className="flex items-center justify-between text-xs text-slate-500">
                    <span>Total Failure Count</span>
                    <InformationCircleIcon className="h-4 w-4" />
                  </div>
                  <div className="mt-2 text-2xl font-semibold text-red-500">
                    {totalFailure != null ? totalFailure : "--"}
                  </div>
                </div>

                {/* Avg repair time */}
                <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                  <div className="flex items-center justify-between text-xs text-slate-500">
                    <span>Average Repair Time (ms)</span>
                    <InformationCircleIcon className="h-4 w-4" />
                  </div>
                  <div className="mt-2 text-2xl font-semibold text-slate-900">
                    {avgRepairTime != null ? avgRepairTime : "--"}
                  </div>
                </div>

                {/* Success rate */}
                <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                  <div className="flex items-center justify-between text-xs text-slate-500">
                    <span>Success Rate (%)</span>
                    <InformationCircleIcon className="h-4 w-4" />
                  </div>
                  <div className="mt-2 text-2xl font-semibold text-emerald-600">
                    {successRate != null ? `${successRate}%` : "--"}
                  </div>
                </div>
              </div>
            ) : (
              <div className="mt-4 grid gap-4 md:grid-cols-2 text-xs text-slate-600">
                <div className="space-y-1">
                  <div className="font-semibold text-slate-700">
                    System & Metadata
                  </div>
                  <p>
                    <span className="font-medium">Locator ID:</span>{" "}
                    {locatorId || "--"}
                  </p>
                  <p>
                    <span className="font-medium">Source Type:</span>{" "}
                    {sourceType}
                  </p>
                  <p>
                    <span className="font-medium">App Version:</span>{" "}
                    {appVersion}
                  </p>
                  <p>
                    <span className="font-medium">Project ID:</span>{" "}
                    {projectId}
                  </p>
                  <p>
                    <span className="font-medium">Last Updated:</span>{" "}
                    {lastUpdated}
                  </p>
                </div>

                <div className="space-y-1">
                  <div className="font-semibold text-slate-700">
                    Commit Info
                  </div>
                  <p>
                    <span className="font-medium">Author:</span>{" "}
                    {commitInfo?.author || "--"}
                  </p>
                  <p>
                    <span className="font-medium">App Version:</span>{" "}
                    {commitInfo?.app_version || "--"}
                  </p>
                  <p>
                    <span className="font-medium">Build Version:</span>{" "}
                    {commitInfo?.build_version || "--"}
                  </p>
                  <p>
                    <span className="font-medium">Hash:</span>{" "}
                    {commitInfo?.hash || "--"}
                  </p>
                </div>
              </div>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
