// src/components/projects/AddMemberModal.jsx
import React, { useEffect, useState } from "react";
import { X, CheckCircle2, AlertTriangle } from "lucide-react";

export default function AddMemberModal({ isOpen, onClose, onAdd }) {
  // --- STATE ---
  const [step, setStep] = useState("form"); // "form" | "success"
  const [username, setUsername] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [apiError, setApiError] = useState("");
  const [inputError, setInputError] = useState("");

  // Reset khi mở modal
  useEffect(() => {
    if (isOpen) {
      setStep("form");
      setUsername("");
      setIsLoading(false);
      setApiError("");
      setInputError("");
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setApiError("");
    setInputError("");

    if (!username.trim()) {
      setInputError("Username is required");
      return;
    }

    try {
      setIsLoading(true);

      // Gọi hàm từ cha (ProjectDetailPage)
      await onAdd(username.trim());

      // Thành công -> Chuyển màn hình tích xanh
      setStep("success");

    } catch (err) {
      console.error(err);
      const msg = err.response?.data?.message || err.message || "Failed to add member.";
      setApiError(msg);
    } finally {
      setIsLoading(false);
    }
  };

  const handleClose = () => {
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
      <div className="relative w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl transition-all">
        
        {/* ===================== STEP 1: FORM ===================== */}
        {step === "form" && (
          <>
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-xl font-semibold text-slate-900">
                Add Member
              </h2>
              <button
                onClick={handleClose}
                disabled={isLoading}
                className="text-slate-400 hover:text-slate-600"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <form onSubmit={handleSubmit} className="space-y-5">
              {/* API Error */}
              {apiError && (
                <div className="flex items-center gap-2 rounded-lg bg-red-50 p-3 text-sm text-red-600 border border-red-100">
                  <AlertTriangle className="h-4 w-4 shrink-0" />
                  <span>{apiError}</span>
                </div>
              )}

              <div>
                <label className="mb-1.5 block text-sm font-medium text-slate-700">
                  Username <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  placeholder="Enter username to add..."
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  disabled={isLoading}
                  className={`w-full rounded-lg border px-3 py-2.5 text-sm outline-none focus:ring-2 ${
                    inputError
                      ? "border-red-400 focus:ring-red-200"
                      : "border-slate-300 focus:border-[#6425FE] focus:ring-[#6425FE]/20"
                  }`}
                />
                {inputError && (
                  <p className="mt-1 text-xs text-red-500">{inputError}</p>
                )}
                
              </div>

              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={handleClose}
                  disabled={isLoading}
                  className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isLoading}
                  className="inline-flex items-center justify-center gap-2 rounded-lg bg-[#6425FE] px-5 py-2 text-sm font-semibold text-white hover:bg-[#5621d6] disabled:opacity-70"
                >
                  {isLoading && <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent"></span>}
                  Add Member
                </button>
              </div>
            </form>
          </>
        )}

        {/* ===================== STEP 2: SUCCESS ===================== */}
        {step === "success" && (
          <div className="flex flex-col items-center text-center py-6 animate-in fade-in zoom-in duration-200">
            <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-[#6425fe15]">
              <CheckCircle2 className="h-10 w-10 text-[#6425FE]" />
            </div>

            <h2 className="text-xl font-semibold text-[#6425FE] mb-2">
              Added Successfully!
            </h2>
            <p className="text-sm text-slate-600 mb-6">
              The user <b>{username}</b> has been added to the project.
            </p>

            <div className="w-full border-t border-slate-100 mb-6" />

            <button
              onClick={handleClose}
              className="rounded-full bg-[#6425FE] px-6 py-2 text-sm font-medium text-white hover:bg-[#5621d6]"
            >
              OK, Close
            </button>
          </div>
        )}
      </div>
    </div>
  );
}