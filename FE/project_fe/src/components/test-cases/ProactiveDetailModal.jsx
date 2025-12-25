// src/components/test-cases/ProactiveDetailModal.jsx
import React, { useEffect, useState, useMemo } from "react";
import { X, CheckCircle2, AlertTriangle } from "lucide-react";
import testCaseService from "../../services/testCaseService";

export default function ProactiveDetailModal({ isOpen, onClose, analysisId, testId }) {
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (isOpen && analysisId) {
      fetchDetail();
    } else {
      setDetail(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, analysisId]);

  const fetchDetail = async () => {
    try {
      setLoading(true);
      setError("");
      const res = await testCaseService.getProactiveReportDetail(analysisId, testId);
      setDetail(res.data);
    } catch (err) {
      console.error("Lỗi tải chi tiết proactive:", err);
      setError("Không thể tải chi tiết báo cáo.");
    } finally {
      setLoading(false);
    }
  };

  // ✅ FIX LỖI: Di chuyển useMemo lên TRƯỚC khi return null
  
  // 1. Helper tính toán thống kê
  const stats = useMemo(() => {
    if (!detail?.ui_changes) return { added: 0, modified: 0, deleted: 0, total: 0 };
    
    // API trả về object phân loại sẵn
    const { added = [], modified = [], deleted = [] } = detail.ui_changes;
    
    return {
      added: added.length,
      modified: modified.length,
      deleted: deleted.length,
      total: added.length + modified.length + deleted.length
    };
  }, [detail]);

  // 2. Helper gộp mảng để hiển thị danh sách
  const allChanges = useMemo(() => {
    if (!detail?.ui_changes) return [];
    const { added = [], modified = [], deleted = [] } = detail.ui_changes;

    return [
        ...added.map(c => ({ ...c, change_type: 'added' })),
        ...modified.map(c => ({ ...c, change_type: 'modified' })),
        ...deleted.map(c => ({ ...c, change_type: 'deleted' }))
    ];
  }, [detail]);

  // ✅ Sau khi khai báo hết Hooks mới được return
  if (!isOpen) return null;

  const renderStatusBadge = (status) => {
    const s = (status || "").toUpperCase();
    if (s === "PASS") return <span className="bg-emerald-500 text-white text-xs font-bold px-3 py-1 rounded-full">PASS</span>;
    if (s === "FAIL") return <span className="bg-rose-500 text-white text-xs font-bold px-3 py-1 rounded-full">FAIL</span>;
    return <span className="bg-slate-400 text-white text-xs font-bold px-3 py-1 rounded-full">{s}</span>;
  };

  const TimelineItem = ({ label, active }) => (
    <div className="flex flex-col items-center gap-2 relative z-10">
      <div className={`h-8 w-8 rounded-full flex items-center justify-center border-2 ${active ? 'border-emerald-500 bg-white text-emerald-500' : 'border-slate-200 bg-slate-50 text-slate-300'}`}>
        {active ? <CheckCircle2 className="h-5 w-5" /> : <div className="h-2 w-2 rounded-full bg-slate-300" />}
      </div>
      <span className={`text-[10px] font-medium uppercase ${active ? 'text-emerald-600' : 'text-slate-400'}`}>{label}</span>
    </div>
  );

  return (
    <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/40 backdrop-blur-sm p-4 overflow-y-auto">
      <div className="relative w-full max-w-4xl rounded-3xl bg-white shadow-2xl transition-all flex flex-col max-h-[90vh]">
        
        {/* HEADER */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100">
          <div className="flex items-center gap-4">
            <h2 className="text-xl font-bold text-[#6425FE]">Test Run Detail</h2>
            {!loading && detail && (
                <>
                    {renderStatusBadge(detail.status)}
                    <div className="flex items-center justify-center h-8 w-8 rounded-full border-2 border-rose-500 text-rose-500 text-xs font-bold">
                        {detail.confidence?.score || 0}
                    </div>
                </>
            )}
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-rose-500 transition-colors">
            <X className="h-6 w-6" />
          </button>
        </div>

        {/* BODY */}
        <div className="flex-1 overflow-y-auto p-6 bg-[#F8F9FC]">
            {loading && <p className="text-center text-slate-500 py-10">Đang tải dữ liệu...</p>}
            {error && <p className="text-center text-rose-500 py-10">{error}</p>}

            {!loading && detail && (
                <div className="space-y-6">
                    
                    {/* 1. INFO HEADER GRID */}
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs text-slate-500">
                        <div>
                            <span className="block text-slate-400 mb-1">Repo</span>
                            <span className="font-medium text-slate-700">{detail.pr_info?.repo_full_name || "—"}</span>
                        </div>
                        <div>
                            <span className="block text-slate-400 mb-1">Commit</span>
                            <div className="flex items-center gap-1 font-mono">
                                <span>{detail.pr_info?.head_sha?.substring(0,7) || "—"}</span>
                                <span>→</span>
                                <span>{detail.pr_info?.base_sha?.substring(0,7) || "base"}</span>
                            </div>
                        </div>
                         <div>
                            <span className="block text-slate-400 mb-1">PR Author</span>
                            <span className="font-medium text-slate-700">{detail.pr_info?.author || "—"}</span>
                        </div>
                        <div>
                            <span className="block text-slate-400 mb-1">Started At</span>
                            <span className="font-medium text-slate-700">{detail.timestamps?.start ? new Date(detail.timestamps.start).toLocaleString() : "—"}</span>
                        </div>
                    </div>

                    {/* 2. PIPELINE TIMELINE */}
                    <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm">
                        <h3 className="text-sm font-bold text-slate-800 mb-4">Pipeline Timeline</h3>
                        <div className="relative flex justify-between items-center px-4">
                            <div className="absolute top-[15px] left-8 right-8 h-0.5 bg-slate-100 z-0" />
                            <TimelineItem label="Start" active={!!detail.timestamps?.start} />
                            <TimelineItem label="Diff" active={!!detail.timestamps?.after_diff} />
                            <TimelineItem label="Scan" active={!!detail.timestamps?.after_scan} />
                            <TimelineItem label="Predict" active={!!detail.timestamps?.after_predict} />
                            <TimelineItem label="Execute" active={!!detail.timestamps?.after_execute} />
                            <TimelineItem label="Score" active={!!detail.timestamps?.after_score} />
                        </div>
                    </div>

                    {/* 3. UI CHANGES & IMPACT ANALYSIS */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        
                        {/* LEFT: UI Changes Detected */}
                        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm">
                            <div className="flex items-center justify-between mb-4">
                                <h3 className="text-sm font-bold text-slate-800">UI Changes Detected</h3>
                                <span className="text-xs text-slate-400">Total: {stats.total}</span>
                            </div>
                            
                            <div className="flex gap-3 mb-4">
                                <span className="px-2 py-1 bg-emerald-50 text-emerald-600 text-xs font-medium rounded-md border border-emerald-100">
                                    + Added: {stats.added}
                                </span>
                                <span className="px-2 py-1 bg-blue-50 text-blue-600 text-xs font-medium rounded-md border border-blue-100">
                                    ~ Modified: {stats.modified}
                                </span>
                                <span className="px-2 py-1 bg-rose-50 text-rose-600 text-xs font-medium rounded-md border border-rose-100">
                                    - Deleted: {stats.deleted}
                                </span>
                            </div>

                            {/* List of changes */}
                            <div className="max-h-60 overflow-y-auto space-y-2 pr-1 custom-scrollbar">
                                {allChanges.length > 0 ? allChanges.map((change, idx) => (
                                    <div key={idx} className="text-xs p-2 bg-slate-50 rounded border border-slate-100 flex flex-col gap-1">
                                        <div className="flex justify-between items-start">
                                            <span className={`font-mono font-semibold truncate max-w-[200px] ${
                                                change.change_type === 'added' ? 'text-emerald-600' : 
                                                change.change_type === 'deleted' ? 'text-rose-600 decoration-line-through' : 'text-blue-600'
                                            }`}>
                                                {change.attribute_value}
                                            </span>
                                            <span className={`text-[10px] uppercase font-bold px-1.5 py-0.5 rounded ${
                                                change.change_type === 'added' ? 'bg-emerald-100 text-emerald-600' :
                                                change.change_type === 'deleted' ? 'bg-rose-100 text-rose-600' : 'bg-blue-100 text-blue-600'
                                            }`}>
                                                {change.change_type}
                                            </span>
                                        </div>
                                        <div className="flex justify-between text-[10px] text-slate-400">
                                            <span className="truncate max-w-[200px]" title={change.file_path}>{change.file_path}</span>
                                            <span>Line: {change.line_num}</span>
                                        </div>
                                    </div>
                                )) : (
                                    <p className="text-xs text-slate-400 text-center py-4">No significant UI changes detected.</p>
                                )}
                            </div>
                        </div>

                        {/* RIGHT: Impact Analysis */}
                        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm space-y-4">
                            <h3 className="text-sm font-bold text-slate-800">Impact Analysis</h3>
                            
                            <div className="flex items-center justify-between p-3 bg-slate-50 rounded-xl">
                                <span className="text-xs text-slate-600">Predicted Failed Tests</span>
                                <span className="font-bold text-rose-500">{detail.analysis_details?.predicted_failed_tests?.length || 0}</span>
                            </div>

                            <div className="flex items-center justify-between p-3 bg-slate-50 rounded-xl">
                                <span className="text-xs text-slate-600">Matched Locators</span>
                                <span className="font-bold text-slate-800">{detail.analysis_details?.match_details?.length || 0}</span>
                            </div>

                            {/* Match Details Preview */}
                            <div className="space-y-2">
                                <h4 className="text-xs font-semibold text-slate-500 mt-2">Top Matches</h4>
                                {detail.analysis_details?.match_details?.slice(0, 3).map((match, idx) => (
                                    <div key={idx} className="text-[10px] p-2 border border-slate-100 rounded bg-white shadow-sm">
                                        <div className="flex justify-between mb-1">
                                            <span className="text-slate-500 truncate max-w-[150px]" title={match.locator?.test_case}>
                                                {match.locator?.test_case || "Unknown Test"}
                                            </span>
                                            <span className="font-bold text-emerald-600">{match.score}%</span>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>

                    {/* 4. FINAL DECISION / RATIONALE */}
                    <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm">
                        <h3 className="text-sm font-bold text-slate-800 mb-2">Final Decision</h3>
                        <div className="mb-4">
                            <div className="flex justify-between text-xs mb-1">
                                <span className="text-slate-400">Confidence Score</span>
                                <span className="font-bold text-slate-700">{detail.confidence?.score}/100</span>
                            </div>
                            <div className="h-2 w-full bg-slate-100 rounded-full overflow-hidden">
                                <div 
                                    className={`h-full rounded-full transition-all duration-500 ${detail.confidence?.score > 80 ? 'bg-emerald-500' : 'bg-rose-500'}`} 
                                    style={{ width: `${detail.confidence?.score}%` }}
                                />
                            </div>
                        </div>
                        <h4 className="text-xs font-bold text-slate-700 mb-1">Rationale</h4>
                        <p className="text-xs text-slate-500 leading-relaxed">
                           {detail.confidence?.rationale || "No rationale provided."}
                        </p>
                    </div>

                </div>
            )}
        </div>

        {/* FOOTER */}
        <div className="p-4 border-t border-slate-100 flex justify-end gap-3 bg-white">
             <button className="px-4 py-2 rounded-lg bg-[#6425FE] text-white text-xs font-semibold hover:bg-[#521bd1]">
                View Raw JSON
             </button>
             <button onClick={onClose} className="px-4 py-2 rounded-lg border border-slate-200 text-slate-600 text-xs font-medium hover:bg-slate-50">
                Close
             </button>
        </div>

      </div>
    </div>
  );
}