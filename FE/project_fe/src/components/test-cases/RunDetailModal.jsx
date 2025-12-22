import React, { useEffect, useState } from "react";
import { X, Copy, CheckCircle2, XCircle, AlertTriangle, Zap, Wand2 } from "lucide-react";
import testCaseService from "../../services/testCaseService";

export default function RunDetailModal({ isOpen, onClose, runId, runInfo }) {
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (isOpen && runId) {
      fetchDetail();
    } else {
      setDetail(null); // Reset khi đóng
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, runId]);

  const fetchDetail = async () => {
    try {
      setLoading(true);
      setError("");
      const res = await testCaseService.getTestRunDetail(runId);
      setDetail(res.data);
    } catch (err) {
      console.error(err);
      setError("Không thể tải chi tiết report.");
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  // --- Helper Render Status Badge ---
  const renderStatusBadge = (status) => {
    const s = (status || "").toLowerCase();
    if (s === "pass") return <span className="bg-emerald-500 text-white text-xs font-bold px-3 py-1 rounded-full">PASS</span>;
    if (s === "fail") return <span className="bg-rose-500 text-white text-xs font-bold px-3 py-1 rounded-full">FAIL</span>;
    return <span className="bg-slate-400 text-white text-xs font-bold px-3 py-1 rounded-full">{status}</span>;
  };

  // --- Helper Copy RunID ---
  const handleCopyId = () => {
    if (detail?.run_id) {
      navigator.clipboard.writeText(detail.run_id);
      // Có thể thêm toast notification ở đây
    }
  };

  // === HÀM XỬ LÝ URL ẢNH (FIX LỖI PORT 8000) ===
  const processImageUrl = (url) => {
    if (!url) return null;

    // Nếu URL là localhost:8000, ta đổi nó thành đường dẫn qua Proxy
    // Logic: http://localhost:8000/static/... -> /report-service/static/...
    // Khi đó Vite sẽ đẩy request sang http://localhost:8006/static/...
    if (url.includes("localhost:8000")) {
      return url.replace("http://localhost:8000", "/report-service");
    }

    return url;
  };

  return (
    <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/40 backdrop-blur-sm p-4 overflow-y-auto">
      <div className="relative w-full max-w-4xl rounded-3xl bg-white shadow-2xl transition-all flex flex-col max-h-[90vh]">
        
        {/* HEADER */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100">
          <div className="flex items-center gap-3">
            <h2 className="text-xl font-bold text-[#6425FE]">Test Detail</h2>
            {!loading && detail && renderStatusBadge(detail.final_result)}
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-rose-500 transition-colors">
            <X className="h-6 w-6" />
          </button>
        </div>

        {/* CONTENT SCROLLABLE */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6 bg-[#F8F9FC]">
          
          {loading && <p className="text-center text-slate-500 py-10">Đang tải dữ liệu...</p>}
          {error && <p className="text-center text-rose-500 py-10">{error}</p>}

          {!loading && detail && (
            <>
              {/* === SECTION 1: TOP CARDS === */}
              <div className="flex flex-wrap gap-4">
                {/* Run ID */}
                <div className="flex-1 min-w-[200px] rounded-xl border border-slate-200 bg-white p-3">
                  <span className="text-xs text-slate-400 font-medium uppercase">Run ID</span>
                  <div className="flex items-center justify-between mt-1">
                    <span className="text-sm font-mono text-slate-700 truncate max-w-[150px]" title={detail.run_id}>
                      {detail.run_id}
                    </span>
                    <button onClick={handleCopyId} className="text-slate-400 hover:text-[#6425FE]">
                      <Copy className="h-4 w-4" />
                    </button>
                  </div>
                </div>

                {/* Duration (Lấy từ props truyền vào vì API detail ko có) */}
                <div className="min-w-[120px] rounded-xl border border-slate-200 bg-white p-3">
                  <span className="text-xs text-slate-400 font-medium uppercase">Duration</span>
                  <div className="mt-1 text-base font-bold text-slate-800">
                    {runInfo?.duration || "N/A"}
                  </div>
                </div>

                {/* Priority (Đã sửa để lấy dynamic từ runInfo) */}
                <div className="min-w-[100px] rounded-xl border border-slate-200 bg-white p-3">
                  <span className="text-xs text-slate-400 font-medium uppercase">Priority</span>
                  <div className="mt-1">
                    {(() => {
                      const p = (runInfo?.priority || "medium").toLowerCase();
                      let style = "bg-amber-100 text-amber-600"; // Mặc định Medium
                      
                      if (p === "high") style = "bg-rose-100 text-rose-600";
                      else if (p === "low") style = "bg-emerald-100 text-emerald-600";

                      return (
                        <span className={`${style} text-[10px] font-bold px-2 py-0.5 rounded capitalize`}>
                          {runInfo?.priority || "Medium"}
                        </span>
                      );
                    })()}
                  </div>
                </div>

                {/* Healing Status */}
                <div className="min-w-[140px] rounded-xl border border-slate-200 bg-white p-3">
                  <span className="text-xs text-slate-400 font-medium uppercase">Healing</span>
                  <div className="mt-1 text-sm font-semibold flex items-center gap-1">
                    {detail.heal_attempted ? (
                      detail.heal_success ? (
                        <span className="text-emerald-600 flex items-center gap-1"><Wand2 className="h-3.5 w-3.5" /> Success</span>
                      ) : (
                        <span className="text-rose-600 flex items-center gap-1"><AlertTriangle className="h-3 w-3"/> Failed</span>
                      )
                    ) : (
                      <span className="text-slate-400">No Healing</span>
                    )}
                  </div>
                </div>
              </div>

              {/* === SECTION 2: BUILD INFORMATION === */}
              <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                <h3 className="text-sm font-bold text-slate-800 mb-4">Build Information</h3>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-y-4 gap-x-8 text-sm">
                  <div className="flex justify-between md:block">
                    <span className="text-slate-400 block mb-1">App Version:</span>
                    <span className="font-medium text-slate-700">{detail.app_version || "—"}</span>
                  </div>
                  <div className="flex justify-between md:block">
                    <span className="text-slate-400 block mb-1">Git Hash:</span>
                    <span className="font-mono text-[#6425FE] bg-[#6425FE]/10 px-2 py-0.5 rounded text-xs">
                       {detail.git_hash || "—"}
                    </span>
                  </div>
                  <div className="flex justify-between md:block">
                    <span className="text-slate-400 block mb-1">Timestamp:</span>
                    <span className="font-medium text-slate-700">
                        {new Date(detail.timestamp).toLocaleString()}
                    </span>
                  </div>
                </div>
              </div>

              {/* === SECTION 3: SELF-HEALING DETAILS === */}
              {detail.heal_attempted && (
                <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                  <h3 className="text-sm font-bold text-slate-800 mb-4 flex items-center gap-2">
                    <div className="flex h-6 w-6 items-center justify-center rounded-full bg-emerald-100 text-emerald-600">
                       <Wand2 className="h-3.5 w-3.5" />
                    </div>
                    Self-Healing Events
                  </h3>
                  
                  {detail.heal_events && detail.heal_events.length > 0 ? (
                    detail.heal_events.map((event, idx) => (
                      <div key={idx} className="mb-4 last:mb-0 p-4 bg-slate-50 rounded-xl border border-slate-100">
                         {/* Nếu API trả về old/new locator thì hiển thị ở đây. 
                             Tạm thời hiển thị raw data hoặc mock UI nếu JSON heal_events rỗng */}
                         <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div>
                                <span className="text-xs text-slate-400 uppercase">Old Locator</span>
                                <div className="mt-1 p-2 bg-rose-50 border border-rose-100 text-rose-700 text-xs font-mono rounded break-all">
                                   {event.locator_old || "—"}
                                </div>
                            </div>
                            <div>
                                <span className="text-xs text-slate-400 uppercase">New Locator</span>
                                <div className="mt-1 p-2 bg-emerald-50 border border-emerald-100 text-emerald-700 text-xs font-mono rounded break-all">
                                   {event.locator_new || "—"}
                                </div>
                            </div>
                         </div>
                         <div className="mt-3 flex gap-4 text-xs">
                            <span className="text-slate-500">Confidence: <b className="text-emerald-600">{event.confidence || "95%"}</b></span>
                            <span className="text-slate-500">Method: <b>{event.method || "AI_Heal"}</b></span>
                         </div>
                      </div>
                    ))
                  ) : (
                    <div className="p-4 bg-slate-50 rounded-xl text-center text-slate-500 text-sm italic">
                      Healing was attempted but no detailed events recorded.
                    </div>
                  )}
                </div>
              )}

              {/* === SECTION 4: VISUAL COMPARISON === */}
              {detail.visual_events && detail.visual_events.length > 0 && (
                <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                   <h3 className="text-sm font-bold text-slate-800 mb-4">Validation & Visual Comparison</h3>
                   
                   <div className="space-y-8">
                     {detail.visual_events.map((visual) => (
                        <div key={visual.id} className="border-b border-slate-100 last:border-0 pb-6 last:pb-0">
                            {/* Visual Header */}
                            <div className="flex items-center justify-between mb-3">
                                <span className="text-sm font-medium text-slate-700 truncate max-w-md" title={visual.target_name}>
                                    Target: <span className="text-[#6425FE]">{visual.target_name}</span>
                                </span>
                                <span className={`text-[10px] font-bold px-2 py-0.5 rounded border ${
                                    visual.status === 'NEW_BASELINE' ? 'bg-blue-50 text-blue-600 border-blue-100' : 
                                    visual.status === 'MATCH' ? 'bg-emerald-50 text-emerald-600 border-emerald-100' : 'bg-amber-50 text-amber-600 border-amber-100'
                                }`}>
                                    {visual.status}
                                </span>
                            </div>

                            {/* SSIM Score Bar */}
                            {visual.ssim_score && (
                                <div className="mb-4">
                                    <div className="flex justify-between text-xs mb-1">
                                        <span className="text-slate-400">SSIM Score</span>
                                        <span className="font-bold text-slate-700">{visual.ssim_score}</span>
                                    </div>
                                    <div className="h-1.5 w-full bg-slate-100 rounded-full overflow-hidden">
                                        <div 
                                            className="h-full bg-emerald-500 rounded-full transition-all duration-500" 
                                            style={{ width: `${parseFloat(visual.ssim_score) * 100}%` }}
                                        />
                                    </div>
                                </div>
                            )}

                            {/* Image Comparison Grid */}
                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <span className="block text-xs text-center text-slate-400 mb-2">Baseline Image</span>
                                    <div className="relative aspect-video bg-slate-100 rounded-lg overflow-hidden border border-slate-200 mb-2">
                                        {visual.baseline_url ? (
                                            <img 
                                              src={processImageUrl(visual.baseline_url)} 
                                              className="w-full h-full object-contain" 
                                            />
                                        ) : (
                                            <div className="flex items-center justify-center h-full text-xs text-slate-400">No Image</div>
                                        )}
                                    </div>
                                    {visual.baseline_url && (
                                        <div className="px-1">
                                            <a 
                                                href={processImageUrl(visual.baseline_url)} 
                                                target="_blank" 
                                                rel="noreferrer"
                                                className="text-[10px] text-blue-600 hover:text-blue-800 hover:underline break-all block leading-tight"
                                                title={visual.baseline_url} // Hover để xem full nếu bị cắt
                                            >
                                                {visual.baseline_url}
                                            </a>
                                        </div>
                                    )}
                                </div>
                                <div>
                                    <span className="block text-xs text-center text-slate-400 mb-2">Current Image</span>
                                    <div className="relative aspect-video bg-slate-100 rounded-lg overflow-hidden border border-slate-200 mb-2">
                                        {visual.current_url ? (
                                            <img 
                                              src={processImageUrl(visual.current_url)} 
                                              className="w-full h-full object-contain" 
                                            />
                                        ) : (
                                            <div className="flex items-center justify-center h-full text-xs text-slate-400">No Image</div>
                                        )}
                                    </div>
                                    {visual.current_url && (
                                        <div className="px-1">
                                            <a 
                                                href={processImageUrl(visual.current_url)} 
                                                target="_blank" 
                                                rel="noreferrer"
                                                className="text-[10px] text-blue-600 hover:text-blue-800 hover:underline break-all block leading-tight"
                                                title={visual.current_url}
                                            >
                                                {visual.current_url}
                                            </a>
                                        </div>
                                    )}
                                </div>
                            </div>
                        </div>
                     ))}
                   </div>
                </div>
              )}

            </>
          )}
        </div>
      </div>
    </div>
  );
}