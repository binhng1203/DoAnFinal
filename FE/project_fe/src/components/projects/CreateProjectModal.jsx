import React, { useState, useEffect } from "react";
import { ClipboardIcon, CheckIcon } from "@heroicons/react/24/outline";
import { CheckCircle2, X, AlertTriangle } from "lucide-react";

function isValidUrl(url) {
  if (!url) return false;
  try {
    const u = new URL(url);
    return u.protocol === "http:" || u.protocol === "https:";
  } catch {
    return false;
  }
}

// Tạo project code 
function generateProjectCode() {
  const characters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
  let result = "";
  const length = 8;
  
  for (let i = 0; i < length; i++) {
    // Lấy ngẫu nhiên 1 ký tự trong chuỗi characters
    const randomIndex = Math.floor(Math.random() * characters.length);
    result += characters.charAt(randomIndex);
  }
  
  return result; 
}

export default function CreateProjectModal({ isOpen, onClose, onCreate, onUpdate, projectData }) {
  const isEditMode = !!projectData;

  const [step, setStep] = useState("form"); // "form" | "success"
  const [isLoading, setIsLoading] = useState(false);
  const [apiError, setApiError] = useState("");
  
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [description, setDescription] = useState("");
  const [repoUrl, setRepoUrl] = useState("");

  const [nameError, setNameError] = useState("");
  const [urlError, setUrlError] = useState("");

  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setStep("form");
      setIsLoading(false);
      setApiError("");
      
      setNameError("");
      setUrlError("");
      setCopied(false);

      if (isEditMode) {
        // --- CHẾ ĐỘ EDIT ---
        setName(projectData.name || "");
        setCode(projectData.project_code || projectData.code || "");
        setDescription(projectData.description || "");
        setRepoUrl(projectData.repo_url || projectData.repository_url || "");
      } else {
        // --- CHẾ ĐỘ CREATE ---
        setName("");
        setCode(generateProjectCode());
        setDescription("");
        setRepoUrl("");
      }
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleCopy = () => {
    navigator.clipboard.writeText(code);
    setCopied(true);

    setTimeout(() => setCopied(false), 1200);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    // 1. Validation (Giữ nguyên)
    let hasError = false;
    if (!name.trim()) {
      setNameError("Project name is required");
      hasError = true;
    } else {
      setNameError("");
    }

    if (repoUrl && !isValidUrl(repoUrl.trim())) {
      setUrlError("Please enter a valid URL");
      hasError = true;
    } else {
      setUrlError("");
    }

    if (hasError) return;

    // 2. Prepare Payload
    const payload = {
      name: name.trim(),
      code,
      description: description.trim(),
      repo_url: repoUrl.trim(),
    };

    // 3. Call API with Try/Catch (Giống ConfirmModal)
    try {
      setIsLoading(true);
      setApiError("");

      if (isEditMode && onUpdate) {
        await onUpdate(payload); // Chờ API trả về
        setStep("success");      // Chuyển sang màn hình thành công
      } else if (onCreate) {
        await onCreate(payload); // Chờ API trả về
        setStep("success");      // Chuyển sang màn hình thành công
      }
    } catch (err) {
      console.error("Submit error:", err);
      // Lấy message lỗi từ backend (giống ConfirmModal)
      const msg = err?.response?.data?.message || err?.message || "Something went wrong.";
      setApiError(msg);
    } finally {
      setIsLoading(false);
    }
  };

  const handleCloseSuccess = () => {
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
      {/* Modal Container */}
      <div className="relative z-10 w-full max-w-xl rounded-2xl bg-white p-6 shadow-2xl transition-all">
        
        {/* ===================== STEP 1: FORM NHẬP LIỆU ===================== */}
        {step === "form" && (
          <>
            {/* Header */}
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-xl font-semibold text-slate-900">
                {isEditMode ? "Edit Project" : "Add New Project"}
              </h2>
              <button
                type="button"
                onClick={onClose}
                disabled={isLoading}
                className="inline-flex h-8 w-8 items-center justify-center rounded-full text-slate-400 hover:bg-slate-100 hover:text-slate-700 disabled:opacity-50"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <form onSubmit={handleSubmit} className="space-y-5">
              
              {/* API Error Banner (Nếu có lỗi từ Backend) */}
              {apiError && (
                <div className="flex items-center gap-2 rounded-lg bg-red-50 p-3 text-sm text-red-600 border border-red-100">
                  <AlertTriangle className="h-4 w-4 shrink-0" />
                  <span>{apiError}</span>
                </div>
              )}

              {/* Project Name */}
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">
                  Project Name<span className="text-red-500"> *</span>
                </label>
                <input
                  type="text"
                  disabled={isLoading}
                  className={`w-full rounded-lg border px-3 py-2 text-sm outline-none focus:ring-2 ${
                    nameError
                      ? "border-red-400 focus:ring-red-300"
                      : "border-slate-300 focus:border-primary focus:ring-primary/20"
                  }`}
                  placeholder="Enter your project name..."
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                />
                {nameError && (
                  <p className="mt-1 text-xs text-red-500">{nameError}</p>
                )}
              </div>

              {/* Project Code */}
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">
                   Project Code
                </label>
                <div className="flex items-center gap-2">
                  <input
                    type="text"
                    value={code}
                    readOnly
                    disabled={isLoading}
                    placeholder="Enter project code..."
                    className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none bg-slate-100 text-slate-500 cursor-not-allowed"
                  />
                  <button
                    type="button"
                    onClick={handleCopy}
                    disabled={isLoading}
                    className="p-2 rounded-lg border border-slate-300 bg-white hover:bg-slate-50 transition"
                  >
                    {copied ? (
                      <CheckIcon className="w-5 h-5 text-green-600" />
                    ) : (
                      <ClipboardIcon className="w-5 h-5 text-slate-600" />
                    )}
                  </button>
                </div>
              </div>

              {/* Description */}
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">
                  Description
                </label>
                <textarea
                  rows={4}
                  disabled={isLoading}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
                  placeholder="Describe the project's scope..."
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                />
              </div>

              {/* Repository URL */}
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">
                  Repository URL
                </label>
                <div className="relative">
                  <input
                    type="text"
                    disabled={isLoading}
                    className={`w-full rounded-lg border pl-9 pr-3 py-2 text-sm outline-none focus:ring-2 ${
                      urlError
                        ? "border-red-400 focus:ring-red-300"
                        : "border-slate-300 focus:border-primary focus:ring-primary/20"
                    }`}
                    placeholder="https://github.com/your-org/your-repo"
                    value={repoUrl}
                    onChange={(e) => setRepoUrl(e.target.value)}
                  />
                  <span className="pointer-events-none absolute inset-y-0 left-3 flex items-center text-xs text-slate-400">
                    🔗
                  </span>
                </div>
                {urlError && (
                  <p className="mt-1 text-xs text-red-500">{urlError}</p>
                )}
              </div>

              {/* Footer Buttons */}
              <div className="mt-4 flex justify-end gap-3">
                <button
                  type="button"
                  onClick={onClose}
                  disabled={isLoading}
                  className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                >
                  Cancel
                </button>

                <button
                  type="submit"
                  disabled={isLoading}
                  className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white hover:bg-primary/90 disabled:opacity-70"
                >
                  {isLoading && (
                     <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent"></span>
                  )}
                  {isEditMode ? "Save Changes" : "Create"}
                </button>
              </div>
            </form>
          </>
        )}

        {/* ===================== STEP 2: SUCCESS VIEW  ===================== */}
        {step === "success" && (
          <div className="flex flex-col items-center text-center pt-4 pb-2 animate-in fade-in zoom-in duration-200">
            {/* Icon Tích Xanh */}
            <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-[#6425fe15]">
              <CheckCircle2 className="h-7 w-7 text-[#6425FE]" />
            </div>

            <h2 className="text-lg font-semibold text-[#6425FE] mb-1">
              {isEditMode ? "Updated Successfully" : "Created Successfully"}
            </h2>

            <p className="text-sm text-slate-600 mb-4">
              {isEditMode 
                ? "The project information has been updated."
                : "The new project has been created successfully."}
            </p>

            <div className="w-full border-t border-slate-200 mb-4" />

            <button
              className="px-5 py-2 rounded-lg text-sm text-white bg-[#6425FE] hover:bg-[#5621d6]"
              onClick={handleCloseSuccess}
            >
              OK
            </button>
          </div>
        )}

      </div>
    </div>
  );
}