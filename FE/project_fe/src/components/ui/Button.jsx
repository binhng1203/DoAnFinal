import React from "react";

const baseClasses =
  "inline-flex items-center justify-center rounded-lg text-sm font-medium transition focus:outline-none focus:ring-2 focus:ring-offset-2 disabled:opacity-60 disabled:cursor-not-allowed";

const variantClasses = {
  primary:
    "bg-primary text-white hover:bg-primaryDark focus:ring-primary focus:ring-offset-slate-50",
  outline:
    "border border-primary text-primary bg-white hover:bg-primary/5 focus:ring-primary focus:ring-offset-slate-50",
  ghost:
    "text-slate-700 hover:bg-slate-100 focus:ring-slate-300 focus:ring-offset-slate-50",
};

const sizeClasses = {
  sm: "px-3 py-1.5 text-xs",
  md: "px-4 py-2 text-sm",
  lg: "px-5 py-2.5 text-base",
};

export default function Button({
  children,
  variant = "primary",
  size = "md",
  fullWidth = false,
  className = "",
  ...rest
}) {
  const classes = [
    baseClasses,
    variantClasses[variant],
    sizeClasses[size],
    fullWidth ? "w-full" : "",
    className,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <button className={classes} {...rest}>
      {children}
    </button>
  );
}
