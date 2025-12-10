import React from "react";
import { Pencil, Trash } from "lucide-react";

export default function ProjectCard({
  name,
  description,
  role,
  status = "Active",
  createdAt,
  onEdit,
  onDelete,
}) {
  return (
    <div className="flex h-full flex-col justify-between rounded-2xl border border-slate-200 bg-white p-4 shadow-sm hover:shadow-md transition">
      
      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <h3 className="text-sm font-semibold text-slate-900 truncate">
            {name}
          </h3>

          {description && (
            <p className="mt-1 text-xs text-slate-500 line-clamp-2">
              {description}
            </p>
          )}
        </div>

        {/* Status Badge */}
        <span className="inline-flex items-center gap-1 text-xs font-medium text-emerald-600">
          <span className="h-2 w-2 rounded-full bg-emerald-500" />
          {status}
        </span>
      </div>

      {/* Footer */}
      <div className="mt-4 flex items-end justify-between gap-2">
        {/* Left info */}
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2">
            <div className="h-7 w-7 rounded-full bg-slate-200" />
            <span className="text-xs text-slate-700">{role}</span>
          </div>

          <p className="text-[11px] text-slate-500">Created {createdAt}</p>
        </div>

        {/* Action icons */}
        <div className="flex items-center gap-2">
          
          {/* Edit */}
          <button
            type="button"
            title="Edit project"
            onClick={onEdit}
            className="inline-flex h-7 w-7 items-center justify-center rounded-full border border-slate-200 hover:bg-slate-50"
          >
            <Pencil
              className="h-4 w-4"
              stroke="#84828A"
              strokeWidth={2}
            />
          </button>

          {/* Delete */}
          <button
            type="button"
            title="Delete project"
            onClick={onDelete}
            className="inline-flex h-7 w-7 items-center justify-center rounded-full border border-slate-200 hover:bg-slate-50"
          >
            <Trash
              className="h-4 w-4"
              stroke="#84828A"
              strokeWidth={2}
            />
          </button>

        </div>
      </div>
    </div>
  );
}
