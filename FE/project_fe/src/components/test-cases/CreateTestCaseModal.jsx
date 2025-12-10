// src/components/test-cases/CreateTestCaseModal.jsx
import React, { useEffect, useState } from "react";
import { X, CheckCircle2, AlertTriangle } from "lucide-react";

export default function CreateTestCaseModal({
  isOpen,
  onClose,
  onCreate,       // Hàm xử lý tạo mới từ cha
  onUpdate,       // ✅ Hàm xử lý cập nhật từ cha
  testCaseData,   // ✅ Dữ liệu cũ (dùng cho Edit)
  suiteId,
}) {
  const isEditMode = !!testCaseData;

  // UI State
  const [step, setStep] = useState("form"); // "form" | "success"
  const [loading, setLoading] = useState(false);
  const [apiError, setApiError] = useState("");

  // Form Data
  const [name, setName] = useState("");
  const [priority, setPriority] = useState("medium"); // high/medium/low
  const [type, setType] = useState("manual");         // manual/auto
  const [description, setDescription] = useState("");
  const [tags, setTags] = useState([]);
  const [author, setAuthor] = useState(""); // Assignee

  // Reset & Fill Data
  useEffect(() => {
    if (isOpen) {
      setStep("form");
      setLoading(false);
      setApiError("");

      if (isEditMode) {
        // --- EDIT MODE ---
        setName(testCaseData.name || "");
        setPriority((testCaseData.priority || "medium").toLowerCase());
        
        // Map Type: "Automated" -> "auto", "Manual" -> "manual"
        const rawType = (testCaseData.type || "manual").toLowerCase();
        setType(rawType.includes("auto") ? "auto" : "manual");

        setDescription(testCaseData.description || "");
        setTags(Array.isArray(testCaseData.tags) ? testCaseData.tags : []);
        setAuthor(testCaseData.assignee_id || ""); // Map Assignee ID vào đây
      } else {
        // --- CREATE MODE ---
        setName("");
        setPriority("medium");
        setType("manual");
        setDescription("");
        setTags([]);
        setAuthor("");
      }
    }
  }, [isOpen]);

  if (!isOpen) return null;

  // Handle Logic
  const handleSubmit = async (e) => {
    e.preventDefault();
    setApiError("");

    if (!name.trim()) {
      setApiError("Name is required");
      return;
    }

    try {
      setLoading(true);

      // Map dữ liệu theo JSON bạn yêu cầu
      const priorityMap = { high: "High", medium: "Medium", low: "Low" };
      const typeMap = { manual: "Manual", auto: "Automated" };

      const payload = {
        name: name.trim(),
        priority: priorityMap[priority] || "Medium",
        type: typeMap[type] || "Manual",
        description: description.trim(),
        tags: tags,
        assignee_id: author.trim() || null, // Gửi assignee_id
        
        // Các trường bổ sung (Nếu Edit thì giữ nguyên hoặc hardcode theo yêu cầu)
        fullscreen_page_name: isEditMode ? testCaseData.fullscreen_page_name : "LoginPage",
        app_version: isEditMode ? testCaseData.app_version : "1.0.0",
      };

      // Gọi hàm từ Cha
      if (isEditMode && onUpdate) {
        await onUpdate(payload); // Gọi API PUT
      } else if (onCreate) {
        await onCreate(payload); // Gọi API POST
      }

      setStep("success"); // Chuyển màn hình thành công

    } catch (err) {
      console.error("Submit error:", err);
      const msg = err.response?.data?.message || err.message || "Something went wrong.";
      setApiError(msg);
    } finally {
      setLoading(false);
    }
  };

  // Helper tags
  const addTagOnEnter = (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      const val = e.target.value.trim();
      if (val && !tags.includes(val)) {
        setTags((prev) => [...prev, val]);
      }
      e.target.value = "";
    }
  };
  const removeTag = (tag) => setTags(prev => prev.filter(t => t !== tag));

  const baseRadio = "flex items-center gap-1.5 cursor-pointer text-sm select-none";
  const baseDot = "h-3 w-3 rounded-full border transition-colors";

  return (
    <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/30 backdrop-blur-sm">
      <div className="relative w-full max-w-3xl rounded-3xl bg-white p-6 shadow-2xl transition-all">
        <button type="button" onClick={onClose} className="absolute right-5 top-5 text-slate-400 hover:text-red-500">
          <X className="h-5 w-5" />
        </button>

        {/* ===================== FORM VIEW ===================== */}
        {step === "form" && (
          <>
            <h2 className="mb-4 text-2xl font-semibold text-[#6425FE]">
              {isEditMode ? "Edit Test Case" : "Create Test Case"}
            </h2>

            <form className="space-y-5" onSubmit={handleSubmit}>
              {apiError && (
                <div className="p-3 bg-red-50 text-red-600 text-sm rounded-lg border border-red-100">
                  {apiError}
                </div>
              )}

              {/* Name */}
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-800">Name *</label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm outline-none focus:border-[#6425FE] focus:ring-2 focus:ring-[#6425FE]/20"
                  disabled={loading}
                />
              </div>

              {/* Priority + Type */}
              <div className="grid gap-6 md:grid-cols-2">
                <div>
                  <div className="mb-1 text-sm font-medium text-slate-800">Priority *</div>
                  <div className="flex gap-6 text-sm">
                    {['high', 'medium', 'low'].map(p => (
                      <label key={p} className={baseRadio}>
                        <span className={`${baseDot} border-slate-400 ${priority === p ? (p==='high'?'bg-red-500': p==='medium'?'bg-blue-500':'bg-green-500') : 'bg-white'}`} />
                        <input type="radio" className="hidden" checked={priority === p} onChange={() => setPriority(p)} disabled={loading} />
                        <span className="capitalize">{p}</span>
                      </label>
                    ))}
                  </div>
                </div>

                <div>
                  <div className="mb-1 text-sm font-medium text-slate-800">Type</div>
                  <div className="flex gap-6 text-sm">
                    {['manual', 'auto'].map(t => (
                      <label key={t} className={baseRadio}>
                        <span className={`${baseDot} border-[#6425FE] ${type === t ? 'bg-[#6425FE]' : 'bg-white'}`} />
                        <input type="radio" className="hidden" checked={type === t} onChange={() => setType(t)} disabled={loading} />
                        <span className="capitalize">{t}</span>
                      </label>
                    ))}
                  </div>
                </div>
              </div>

              {/* Description */}
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-800">Description</label>
                <textarea
                  rows={4}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm outline-none focus:border-[#6425FE] focus:ring-2 focus:ring-[#6425FE]/20"
                  disabled={loading}
                />
              </div>

              {/* Tags */}
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-800">Tags</label>
                <div className="flex flex-wrap items-center gap-2">
                  {tags.map(tag => (
                    <span key={tag} className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-700">
                      {tag} <button type="button" onClick={() => removeTag(tag)}>×</button>
                    </span>
                  ))}
                  <input
                    type="text"
                    placeholder="Enter to add tag"
                    onKeyDown={addTagOnEnter}
                    className="mt-1 min-w-[100px] rounded-lg border border-slate-300 px-2 py-1.5 text-xs outline-none focus:border-[#6425FE]"
                    disabled={loading}
                  />
                </div>
              </div>

              {/* Assignee ID */}
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-800">Assignee ID</label>
                <input
                  type="text"
                  value={author}
                  onChange={(e) => setAuthor(e.target.value)}
                  placeholder="UUID (e.g. 19bbb186...)"
                  className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm outline-none focus:border-[#6425FE] focus:ring-2 focus:ring-[#6425FE]/20"
                  disabled={loading}
                />
              </div>

              {/* Footer */}
              <div className="mt-6 flex items-center justify-end gap-3 border-t border-slate-200 pt-4">
                <button type="button" onClick={onClose} disabled={loading} className="rounded-full border border-slate-300 px-5 py-2 text-sm font-medium hover:bg-slate-100">Cancel</button>
                <button type="submit" disabled={loading} className="rounded-full bg-[#6425FE] px-6 py-2 text-sm font-semibold text-white hover:bg-[#5621d6] flex items-center gap-2">
                  {loading && <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent"></span>}
                  {isEditMode ? "Save Changes" : "Create"}
                </button>
              </div>
            </form>
          </>
        )}

        {/* ===================== SUCCESS VIEW ===================== */}
        {step === "success" && (
          <div className="flex flex-col items-center text-center py-8 animate-in fade-in zoom-in duration-200">
            <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-[#6425fe15]">
              <CheckCircle2 className="h-10 w-10 text-[#6425FE]" />
            </div>
            <h2 className="text-xl font-semibold text-[#6425FE] mb-2">
              {isEditMode ? "Updated Successfully!" : "Created Successfully!"}
            </h2>
            <p className="text-sm text-slate-600 mb-6">
              The test case information has been saved.
            </p>
            <div className="w-full border-t border-slate-100 mb-6" />
            <button
              className="px-6 py-2 rounded-full text-sm font-medium text-white bg-[#6425FE] hover:bg-[#5621d6]"
              onClick={onClose}
            >
              OK, Close
            </button>
          </div>
        )}
      </div>
    </div>
  );
}