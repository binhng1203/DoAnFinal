// src/components/test-suites/CreateTestSuiteModal.jsx
import React, { useEffect, useState } from "react";
import { XMarkIcon } from "@heroicons/react/24/outline";
import { CheckCircle2, AlertTriangle } from "lucide-react";

export default function CreateTestSuiteModal({
  isOpen,
  onClose,
  onCreate,
  onUpdate,
  projectId,
  parentSuiteId,
  suiteData
}) {
  const isEditMode = !!suiteData;

  // --- STATE QUẢN LÝ ---
  const [step, setStep] = useState("form"); // Chỉ cần 'form' hoặc 'success'
  const [isLoading, setIsLoading] = useState(false);
  
  // Dữ liệu Form
  const [suiteId, setSuiteId] = useState("");
  const [suiteName, setSuiteName] = useState("");
  
  // Lỗi hiển thị
  const [fieldErrors, setFieldErrors] = useState({}); // Lỗi validate
  const [apiError, setApiError] = useState("");       // Lỗi từ backend

  // Reset khi mở modal
  useEffect(() => {
    if (isOpen) {
      setStep("form");
      setIsLoading(false);
      setApiError("");
      setFieldErrors({});

      if (isEditMode) {
        setSuiteId(suiteData.suite_id || "");
        setSuiteName(suiteData.name || "");
      } else {
        setSuiteId("");
        setSuiteName("");
      }
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setFieldErrors({});
    setApiError(""); // Reset lỗi API trước khi gọi

    // 1. Validate Client
    const newErrors = {};
    if (!suiteId.trim()) newErrors.suiteId = "Test Suite ID is required";
    if (!suiteName.trim()) newErrors.suiteName = "Test Suite name is required";
    if (Object.keys(newErrors).length > 0) {
      setFieldErrors(newErrors);
      return;
    }

    const payload = {
      suite_id: suiteId.trim(),
      name: suiteName.trim(),
      parent_suite_id: isEditMode ? suiteData.parent_suite_id : (parentSuiteId || null),
    };

    // 2. Gọi API (Try/Catch)
    try {
      setIsLoading(true);

      if (isEditMode && onUpdate) {
        await onUpdate(payload);
        setStep("success"); // ✅ Chỉ chuyển step khi THÀNH CÔNG
      } else if (onCreate) {
        await onCreate(payload);
        setStep("success"); // ✅ Chỉ chuyển step khi THÀNH CÔNG
      }

    } catch (err) {
      console.error(err);
      const msg = err.response?.data?.message || err.message || "An unexpected error occurred.";
      
      // ❌ KHÔNG chuyển step, chỉ hiện lỗi để user sửa
      setApiError(msg); 
    } finally {
      setIsLoading(false);
    }
  };

  // Helper styles
  const baseInput = "w-full rounded-xl border px-3 py-2.5 text-sm outline-none transition";
  const normalInput = baseInput + " border-slate-300 bg-white focus:border-primary focus:ring-2 focus:ring-primary/10";
  const errorInput = baseInput + " border-red-400 bg-red-50 focus:border-red-500 focus:ring-2 focus:ring-red-100";
  const readOnlyInput = baseInput + " border-slate-300 bg-slate-100 text-slate-500 cursor-not-allowed";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm">
      <div className="w-full max-w-lg rounded-3xl bg-white shadow-2xl transition-all">
        
        {/* ===================== FORM STEP ===================== */}
        {step === "form" && (
          <>
            <div className="flex items-center justify-between px-6 pt-6 pb-3">
              <h2 className="text-xl font-semibold text-primary">
                {isEditMode ? "Edit Test Suite" : "Create Test Suite"}
              </h2>
              <button onClick={onClose} disabled={isLoading} className="text-slate-400 hover:text-slate-600">
                <XMarkIcon className="h-5 w-5" />
              </button>
            </div>

            <form onSubmit={handleSubmit} className="px-6 pb-6 space-y-5">
              
              {/* 🔥 HIỂN THỊ LỖI API NGAY TẠI ĐÂY (Giống Project Modal) */}
              {apiError && (
                <div className="flex items-center gap-2 rounded-lg bg-red-50 p-3 text-sm text-red-600 border border-red-100">
                  <AlertTriangle className="h-4 w-4 shrink-0" />
                  <span>{apiError}</span>
                </div>
              )}

              {/* ID Field */}
              <div>
                <label className="mb-1.5 block text-sm font-medium text-slate-700">
                  Test Suite ID <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  placeholder="Enter ID..."
                  value={suiteId}
                  onChange={(e) => setSuiteId(e.target.value)}
                  readOnly={isEditMode}
                  disabled={isLoading || isEditMode}
                  className={isEditMode ? readOnlyInput : (fieldErrors.suiteId ? errorInput : normalInput)}
                />
                {fieldErrors.suiteId && <p className="mt-1 text-xs text-red-500">{fieldErrors.suiteId}</p>}
              </div>

              {/* Name Field */}
              <div>
                <label className="mb-1.5 block text-sm font-medium text-slate-700">
                  Test Suite Name <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  placeholder="Enter name..."
                  value={suiteName}
                  onChange={(e) => setSuiteName(e.target.value)}
                  disabled={isLoading}
                  className={fieldErrors.suiteName ? errorInput : normalInput}
                />
                {fieldErrors.suiteName && <p className="mt-1 text-xs text-red-500">{fieldErrors.suiteName}</p>}
              </div>

              <div className="mt-4 h-px w-full bg-slate-200" />

              <div className="mt-3 flex items-center justify-end gap-3">
                <button
                  type="button"
                  onClick={onClose}
                  disabled={isLoading}
                  className="rounded-full border border-slate-300 px-5 py-2 text-sm font-medium hover:bg-slate-50 disabled:opacity-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isLoading}
                  className="inline-flex items-center justify-center gap-2 rounded-full bg-primary px-6 py-2 text-sm font-semibold text-white hover:bg-primary/90 disabled:opacity-70"
                >
                  {isLoading && <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent"></span>}
                  {isEditMode ? "Save Changes" : "Create"}
                </button>
              </div>
            </form>
          </>
        )}

        {/* ===================== SUCCESS STEP ===================== */}
        {step === "success" && (
          <div className="px-6 py-8 flex flex-col items-center text-center animate-in fade-in zoom-in duration-200">
            <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-[#6425fe15]">
              <CheckCircle2 className="h-10 w-10 text-[#6425FE]" />
            </div>
            
            <h3 className="mb-1 text-lg font-semibold text-[#6425FE]">
              {isEditMode ? "Suite Updated!" : "Suite Created!"}
            </h3>
            <p className="text-sm text-slate-600 mb-6">
              The test suite has been successfully processed.
            </p>

            <div className="w-full border-t border-slate-200 mb-6" />

            <button
              onClick={onClose}
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