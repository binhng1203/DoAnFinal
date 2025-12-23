// src/components/test-cases/ProactiveRunModal.jsx
import React, { useState, useEffect } from "react";
import { X, Play, GitCommit } from "lucide-react";

export default function ProactiveRunModal({ isOpen, onClose, onRun }) {
  const [headSha, setHeadSha] = useState("");
  const [baseSha, setBaseSha] = useState("");
  const [error, setError] = useState("");

  // Reset form khi mở
  useEffect(() => {
    if (isOpen) {
      setHeadSha("");
      setBaseSha("");
      setError("");
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!headSha.trim() || !baseSha.trim()) {
      setError("Please enter both Head SHA and Base SHA");
      return;
    }
    // Gửi dữ liệu ra ngoài cho cha xử lý
    onRun({ headSha: headSha.trim(), baseSha: baseSha.trim() });
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
      <div className="relative w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl animate-in fade-in zoom-in duration-200">
        
        {/* Header */}
        <div className="mb-5 flex items-center justify-between">
          <h2 className="text-xl font-semibold text-slate-800 flex items-center gap-2">
            <GitCommit className="h-5 w-5 text-[#6425FE]" />
            Proactive Run
          </h2>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600">
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          {error && <div className="p-3 bg-red-50 text-red-600 text-xs rounded-lg">{error}</div>}

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Head SHA</label>
            <input
              type="text"
              placeholder="e.g. 1054af4"
              value={headSha}
              onChange={(e) => setHeadSha(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm outline-none focus:border-[#6425FE] focus:ring-2 focus:ring-[#6425FE]/20"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Base SHA</label>
            <input
              type="text"
              placeholder="e.g. e23a456"
              value={baseSha}
              onChange={(e) => setBaseSha(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm outline-none focus:border-[#6425FE] focus:ring-2 focus:ring-[#6425FE]/20"
            />
          </div>

          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="inline-flex items-center gap-2 rounded-lg bg-[#6425FE] px-6 py-2 text-sm font-semibold text-white hover:bg-[#5621d6]"
            >
              <Play className="h-4 w-4 fill-current" />
              Run Now
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}