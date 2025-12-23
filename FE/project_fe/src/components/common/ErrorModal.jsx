// src/components/common/ErrorModal.jsx
import React from "react";
import { X, AlertTriangle } from "lucide-react";

export default function ErrorModal({
  isOpen,
  title = "Error",
  message = "Something went wrong. Please try again.",
  onClose,
}) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/30 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="w-[400px] rounded-2xl bg-white p-6 shadow-xl relative animate-in zoom-in-95 duration-200">
        {/* Close Button */}
        <button
          onClick={onClose}
          className="absolute right-4 top-4 text-slate-400 hover:text-slate-600 transition-colors"
        >
          <X className="h-5 w-5" />
        </button>

        <div className="flex flex-col items-center text-center pt-2 pb-2">
          {/* Icon Cảnh Báo (Màu đỏ) */}
          <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-rose-50 border border-rose-100">
            <AlertTriangle className="h-6 w-6 text-rose-500" />
          </div>

          <h2 className="text-lg font-bold text-slate-800 mb-1">
            {title}
          </h2>

          <p className="text-sm text-slate-600 mb-4 leading-relaxed">
            {message}
          </p>
        </div>

        <div className="w-full border-t border-slate-200 mb-4" />

        <div className="flex justify-center">
          <button
            className="px-6 py-2 rounded-lg text-sm font-medium text-white bg-rose-500 hover:bg-rose-600 transition-colors shadow-lg shadow-rose-200"
            onClick={onClose}
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}