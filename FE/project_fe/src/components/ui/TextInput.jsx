import React from "react";

export default function TextInput({
  label,
  hint,
  error,
  className = "",
  inputClassName = "",
  ...rest
}) {
  return (
    <div className={`flex flex-col gap-1 ${className}`}>
      {label && (
        <label className="text-sm font-medium text-slate-700">
          {label}
        </label>
      )}

      <input
        className={[
          "w-full rounded-lg border px-3 py-2 text-sm outline-none transition",
          error
            ? "border-red-500 focus:ring-2 focus:ring-red-300"
            : "border-slate-300 focus:border-primary focus:ring-2 focus:ring-primary/20",
          "bg-white placeholder:text-slate-400",
          inputClassName,
        ]
          .filter(Boolean)
          .join(" ")}
        {...rest}
      />

      {hint && !error && (
        <p className="text-xs text-slate-500">{hint}</p>
      )}
      {error && (
        <p className="text-xs text-red-500">{error}</p>
      )}
    </div>
  );
}
