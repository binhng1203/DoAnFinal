import React, { useEffect, useState } from "react";
import { CheckCircle2 } from "lucide-react";

export default function JoinProjectModal({ isOpen, onClose, onJoin }) {
  const [projectCode, setProjectCode] = useState("");
  const [error, setError] = useState("");
  const [step, setStep] = useState("form"); // "form" | "success"
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [successMessage, setSuccessMessage] = useState("");

  useEffect(() => {
    if (isOpen) {
      setProjectCode("");
      setError("");
      setStep("form");
      setIsSubmitting(false);
      setSuccessMessage("");
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();

    const code = projectCode.trim();

    if (!code) {
      setError("Project Code is required");
      return;
    }

    setError("");
    setIsSubmitting(true);

    try {
      const token = localStorage.getItem("access_token");

      const res = await fetch(`/api/v1/projects/${code}/join`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
      });

      const data = await res.json();
      console.log("JOIN RESPONSE:", data);

      if (!res.ok) {
        // Trường hợp không hợp lệ: project not found, v.v.
        const rawMsg = data.error || data.message || "Join project failed";
        const msgLower = rawMsg.toLowerCase();

        if (msgLower.includes("not found")) {
          setError("Project not found");
        } else {
          setError(rawMsg);
        }
        return;
      }

      // ====== res.ok: xử lý các trường hợp theo message backend ======
      const rawMsg = data.message || "";
      const msgLower = rawMsg.toLowerCase();

      if (msgLower.includes("already a member")) {
        // Đã là member
        setSuccessMessage("You are already a member of this project.");
      } else if (msgLower.includes("joined project successfully")) {
        // Join mới thành công
        setSuccessMessage("You are now a member of this project.");
      } else {
        // Fallback nếu sau này backend đổi message
        setSuccessMessage(rawMsg || "Your request to join the project was processed.");
      }

      // Callback cho parent nếu cần (ví dụ reload list)
      if (onJoin) {
        onJoin(code);
      }

      setStep("success");
    } catch (err) {
      console.error(err);
      setError("Failed to send join request. Please try again.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleClose = () => {
    onClose && onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* overlay */}
      <div
        className="absolute inset-0 bg-black/40"
        onClick={handleClose}
      />

      {/* modal */}
      <div className="relative z-10 w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl">
        {/* header */}
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-xl font-semibold text-primary">
            {step === "form" ? "Join Project" : "Request Result"}
          </h2>
          <button
            type="button"
            onClick={handleClose}
            className="inline-flex h-8 w-8 items-center justify-center rounded-full text-slate-400 hover:bg-slate-100 hover:text-slate-700"
          >
            ✕
          </button>
        </div>

        {step === "form" ? (
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Project Code input */}
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">
                Project Code<span className="text-red-500"> *</span>
              </label>
              <input
                type="text"
                className={`w-full rounded-lg border px-3 py-2 text-sm outline-none focus:ring-2 ${
                  error
                    ? "border-red-400 focus:ring-red-300"
                    : "border-slate-300 focus:border-primary focus:ring-primary/20"
                }`}
                placeholder="Enter project code..."
                value={projectCode}
                onChange={(e) => setProjectCode(e.target.value)}
              />
              {error && (
                <p className="mt-1 text-xs text-red-500">{error}</p>
              )}
            </div>

            {/* line giống design */}
            <div className="mt-4 border-t border-slate-200" />

            {/* footer buttons */}
            <div className="mt-4 flex justify-end gap-3">
              <button
                type="button"
                onClick={handleClose}
                className="rounded-full border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
                disabled={isSubmitting}
              >
                Cancel
              </button>
              <button
                type="submit"
                className="rounded-full bg-primary px-4 py-2 text-sm font-semibold text-white hover:bg-primary/90 disabled:opacity-60 disabled:cursor-not-allowed"
                disabled={isSubmitting}
              >
                {isSubmitting ? "Sending..." : "Request"}
              </button>
            </div>
          </form>
        ) : (
          // ========== SUCCESS VIEW (popup noti với tick) ==========
          <div className="pt-2">
            <div className="flex flex-col items-center text-center mb-4">
              <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-[#6425fe15]">
                <CheckCircle2 className="h-7 w-7 text-[#6425FE]" />
              </div>
              <h3 className="text-lg font-semibold text-[#6425FE] mb-1">
                Join Project
              </h3>
              <p className="text-sm text-slate-600">
                {successMessage}
              </p>
            </div>

            <div className="mt-4 border-t border-slate-200" />

            <div className="mt-4 flex justify-center">
              <button
                type="button"
                onClick={handleClose}
                className="rounded-full bg-[#6425FE] px-4 py-2 text-sm font-semibold text-white hover:bg-[#5621d6]"
              >
                OK
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
