import React from "react";

export default function Card({ children, className = "" }) {
  return (
    <div
      className={[
        "bg-white rounded-2xl shadow-sm border border-slate-200 p-5",
        className,
      ]
        .filter(Boolean)
        .join(" ")}
    >
      {children}
    </div>
  );
}
