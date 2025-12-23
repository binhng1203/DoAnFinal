import React, { useEffect, useState } from "react";
import { X, CheckCircle2, Trash, AlertTriangle } from "lucide-react";

export default function ConfirmModal({
  isOpen,
  title = "Notification",
  message = "Are you sure you want to delete this information?",
  onConfirm,
  onCancel,
  successTitle = "Deleted Successfully",
  successMessage = "The project has been removed from the system.",
  forbiddenTitle = "Permission Denied",
  forbiddenMessage = "You do not have permission to delete this project.",
}) {
  const [step, setStep] = useState("confirm"); // "confirm" | "success" | "forbidden"
  const [isLoading, setIsLoading] = useState(false);
  const [genericError, setGenericError] = useState("");

  useEffect(() => {
    if (isOpen) {
      setStep("confirm");
      setIsLoading(false);
      setGenericError("");
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleCancel = () => {
    setStep("confirm");
    setIsLoading(false);
    setGenericError("");
    onCancel && onCancel();
  };

  const handleConfirmClick = async () => {
    if (!onConfirm) return;

    try {
      setIsLoading(true);
      await onConfirm(); // nếu có lỗi sẽ throw

      // Nếu không throw => API 200 OK
      setStep("success");
    } catch (err) {
      console.error("Delete error:", err);
      const msg = err?.message || "";

      if (msg === "FORBIDDEN_NOT_MEMBER") {
        // 403: không phải member
        setGenericError("");          // hoặc set text riêng nếu muốn
        setStep("forbidden");
      } else if (msg === "MISSING_TOKEN") {
        setGenericError("You need to log in again.");
        setStep("forbidden");
      } else {
        // hiện message từ backend nếu có
        setGenericError(msg || "Something went wrong. Please try again.");
        setStep("forbidden");
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleCloseResult = () => {
    setStep("confirm");
    setGenericError("");
    onCancel && onCancel(); // Đóng modal & reset từ ngoài
  };

  return (
    <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/30 backdrop-blur-sm">
      <div className="w-[480px] rounded-2xl bg-white p-6 shadow-xl relative">
        {/* CLOSE BUTTON */}
        <button
          onClick={
            step === "confirm" ? handleCancel : handleCloseResult
          }
          className="absolute right-4 top-4 text-slate-400 hover:text-red-500"
        >
          <X className="h-5 w-5" />
        </button>

        {/* ===================== CONFIRM STEP ===================== */}
        {step === "confirm" && (
          <>
            <h2 className="text-xl font-semibold text-[#6425FE] mb-4 text-left">
              {title}
            </h2>

            {/* Trash Icon */}
            <div className="flex justify-center mb-4">
              <div className="flex h-14 w-14 items-center justify-center rounded-full bg-[#6425fe15]">
                <Trash className="h-8 w-8 text-[#6425FE]" />
              </div>
            </div>
            <p className="text-center text-slate-700 text-sm mb-2">
              {message}
            </p>

            {genericError && (
              <p className="text-center text-xs text-red-500 mb-2">
                {genericError}
              </p>
            )}

            <div className="w-full border-t border-slate-200 mb-6" />

            <div className="flex justify-end gap-3">
              <button
                className="px-5 py-2 rounded-lg text-sm border border-slate-300 text-slate-700 hover:bg-slate-100"
                onClick={handleCancel}
                disabled={isLoading}
              >
                Cancel
              </button>

              <button
                className="px-5 py-2 rounded-lg text-sm text-white bg-[#6425FE] hover:bg-[#5621d6] disabled:opacity-60 disabled:cursor-not-allowed"
                onClick={handleConfirmClick}
                disabled={isLoading}
              >
                {isLoading ? "Processing..." : "Confirm"}
              </button>
            </div>
          </>
        )}

        {/* ===================== SUCCESS STEP ===================== */}
        {step === "success" && (
          <>
            <div className="flex flex-col items-center text-center pt-4 pb-2">
              <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-[#6425fe15]">
                <CheckCircle2 className="h-7 w-7 text-[#6425FE]" />
              </div>

              <h2 className="text-lg font-semibold text-[#6425FE] mb-1">
                {successTitle}
              </h2>

              <p className="text-sm text-slate-600 mb-4">
                {successMessage}
              </p>
            </div>

            <div className="w-full border-t border-slate-200 mb-4" />

            <div className="flex justify-center">
              <button
                className="px-5 py-2 rounded-lg text-sm text-white bg-[#6425FE] hover:bg-[#5621d6]"
                onClick={handleCloseResult}
              >
                OK
              </button>
            </div>
          </>
        )}

        {/* ===================== FORBIDDEN / ERROR STEP ===================== */}
        {step === "forbidden" && (
          <>
            <div className="flex flex-col items-center text-center pt-4 pb-2">
              <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-red-50">
                <AlertTriangle className="h-7 w-7 text-red-500" />
              </div>

              <h2 className="text-lg font-semibold text-red-600 mb-1">
                {forbiddenTitle}
              </h2>

              <p className="text-sm text-slate-600 mb-1">
                {forbiddenMessage}
              </p>

              {genericError && (
                <p className="text-xs text-slate-500">
                  {genericError}
                </p>
              )}
            </div>

            <div className="w-full border-t border-slate-200 mb-4" />

            <div className="flex justify-center">
              <button
                className="px-5 py-2 rounded-lg text-sm text-white bg-[#6425FE] hover:bg-[#5621d6]"
                onClick={handleCloseResult}
              >
                OK
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
