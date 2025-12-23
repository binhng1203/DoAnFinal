// src/components/test-cases/ProactiveDetailModal.jsx
import React, { useEffect, useState } from "react";
import { X, CheckCircle2, AlertTriangle, FileCode, Search, Target, Zap, Clock } from "lucide-react";
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

  if (!isOpen) return null;

  // Helper tính toán thống kê UI Changes
  const getChangeStats = (changes = []) => {
    return {
      added: changes.filter(c => c.change_type === 'added').length,
      modified: changes.filter(c => c.change_type === 'modified').length,
      deleted: changes.filter(c => c.change_type === 'deleted').length,
      total: changes.length
    };
  };

  // Helper render badge trạng thái
  const renderStatusBadge = (status) => {
    const s = (status || "").toUpperCase();
    if (s === "PASS") return <span className="bg-emerald-500 text-white text-xs font-bold px-3 py-1 rounded-full">PASS</span>;
    if (s === "FAIL") return <span className="bg-rose-500 text-white text-xs font-bold px-3 py-1 rounded-full">FAIL</span>;
    return <span className="bg-slate-400 text-white text-xs font-bold px-3 py-1 rounded-full">{s}</span>;
  };

  // Component con: Pipeline Timeline Item
  const TimelineItem = ({ label, icon: Icon, active }) => (
    <div className="flex flex-col items-center gap-2 relative z-10">
      <div className={`h-8 w-8 rounded-full flex items-center justify-center border-2 ${active ? 'border-emerald-500 bg-white text-emerald-500' : 'border-slate-200 bg-slate-50 text-slate-300'}`}>
        {active ? <CheckCircle2 className="h-5 w-5" /> : (Icon ? <Icon className="h-4 w-4" /> : <div className="h-2 w-2 rounded-full bg-slate-300" />)}
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
                    {/* Score Circle Badge */}
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
                                <span>...</span>
                            </div>
                        </div>
                         <div>
                            <span className="block text-slate-400 mb-1">PR Author</span>
                            <span className="font-medium text-slate-700">{detail.pr_info?.author || "—"}</span>
                        </div>
                        <div>
                            <span className="block text-slate-400 mb-1">Created At</span>
                            <span className="font-medium text-slate-700">{detail.timestamps?.start ? new Date(detail.timestamps.start).toLocaleString() : "—"}</span>
                        </div>
                    </div>

                    {/* 2. PIPELINE TIMELINE (Mock Visual based on Figma) */}
                    <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm">
                        <h3 className="text-sm font-bold text-slate-800 mb-4">Pipeline Timeline</h3>
                        <div className="relative flex justify-between items-center px-4">
                            {/* Connector Line */}
                            <div className="absolute top-[15px] left-8 right-8 h-0.5 bg-slate-100 z-0" />
                            
                            <TimelineItem label="Start" active={true} />
                            <TimelineItem label="Diff" active={true} />
                            <TimelineItem label="Scan" active={true} />
                            <TimelineItem label="Predict" active={true} />
                            <TimelineItem label="Execute" active={detail.status !== "SKIPPED"} />
                            <TimelineItem label="Score" active={detail.confidence?.score !== null} />
                        </div>
                    </div>

                    {/* 3. UI CHANGES & IMPACT ANALYSIS */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        
                        {/* LEFT: UI Changes Detected */}
                        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm">
                            <div className="flex items-center justify-between mb-4">
                                <h3 className="text-sm font-bold text-slate-800">UI Changes Detected</h3>
                                <span className="text-xs text-slate-400">Total: {getChangeStats(detail.ui_changes).total}</span>
                            </div>
                            
                            <div className="flex gap-3 mb-4">
                                <span className="px-2 py-1 bg-emerald-50 text-emerald-600 text-xs font-medium rounded-md border border-emerald-100">
                                    + Added: {getChangeStats(detail.ui_changes).added}
                                </span>
                                <span className="px-2 py-1 bg-blue-50 text-blue-600 text-xs font-medium rounded-md border border-blue-100">
                                    ~ Modified: {getChangeStats(detail.ui_changes).modified}
                                </span>
                                <span className="px-2 py-1 bg-rose-50 text-rose-600 text-xs font-medium rounded-md border border-rose-100">
                                    - Deleted: {getChangeStats(detail.ui_changes).deleted}
                                </span>
                            </div>

                            {/* List of changes (Preview) */}
                            <div className="max-h-40 overflow-y-auto space-y-2">
                                {detail.ui_changes?.map((change, idx) => (
                                    <div key={idx} className="text-xs p-2 bg-slate-50 rounded border border-slate-100 flex justify-between">
                                        <span className="font-mono text-slate-600 truncate max-w-[180px]">{change.attribute_value}</span>
                                        <span className="text-slate-400">{change.file_path}:{change.line_num}</span>
                                    </div>
                                ))}
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

                            {/* Match Details Preview (First 2) */}
                            <div className="space-y-2">
                                {detail.analysis_details?.match_details?.slice(0, 2).map((match, idx) => (
                                    <div key={idx} className="text-[10px] p-2 border border-slate-100 rounded bg-white">
                                        <div className="flex justify-between mb-1">
                                            <span className="text-slate-500 truncate max-w-[150px]">{match.locator.test_case}</span>
                                            <span className="font-bold text-emerald-600">{match.score}% Match</span>
                                        </div>
                                        <div className="flex gap-2">
                                            <span className="bg-rose-50 text-rose-600 px-1 rounded line-through">{match.deleted_attribute?.value}</span>
                                            <span>→</span>
                                            <span className="bg-emerald-50 text-emerald-600 px-1 rounded">{match.predicted_attribute?.value}</span>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>

                    {/* 4. FINAL DECISION / RATIONALE */}
                    <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm">
                        <h3 className="text-sm font-bold text-slate-800 mb-2">Final Decision</h3>
                        
                        {/* Progress Bar */}
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
                           {/* Logic render text based on status */}
                           {detail.status === "FAIL" 
                             ? "The test failed due to a high number of impacted locators and significant UI changes detected in critical components." 
                             : "The test passed as UI changes were minor and did not impact critical locators."}
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