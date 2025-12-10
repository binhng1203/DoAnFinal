import React from "react";
import { X, CheckCircle2 } from "lucide-react";

export default function SuccessModal({
  isOpen,
  title = "Request Sent",
  message = "Your request has been processed successfully.",
  onClose,
}) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/30 backdrop-blur-sm">
      <div className="w-[400px] rounded-2xl bg-white p-6 shadow-xl relative">
        {/* Close */}
        <button
          onClick={onClose}
          className="absolute right-4 top-4 text-slate-400 hover:text-red-500"
        >
          <X className="h-5 w-5" />
        </button>

        <div className="flex flex-col items-center text-center pt-2 pb-2">
          <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-[#6425fe15]">
            <CheckCircle2 className="h-7 w-7 text-[#6425FE]" />
          </div>

          <h2 className="text-lg font-semibold text-[#6425FE] mb-1">
            {title}
          </h2>

          <p className="text-sm text-slate-600 mb-4">
            {message}
          </p>
        </div>

        <div className="w-full border-t border-slate-200 mb-4" />

        <div className="flex justify-center">
          <button
            className="px-5 py-2 rounded-lg text-sm text-white bg-[#6425FE] hover:bg-[#5621d6]"
            onClick={onClose}
          >
            OK
          </button>
        </div>
      </div>
    </div>
  );
}
