import React from "react";

export type StatusVariant =
  | "critical"
  | "warning"
  | "high"
  | "medium"
  | "low"
  | "success"
  | "approved"
  | "pending"
  | "dismissed"
  | "info"
  | "neutral"
  | "not assessed";

interface StatusBadgeProps {
  label: string;
  variant?: string;
  size?: "sm" | "md";
}

export function StatusBadge({ label, variant = "neutral", size = "sm" }: StatusBadgeProps) {
  const normalizedVariant = (variant || "neutral").toLowerCase() as StatusVariant;

  const styles: Record<StatusVariant, string> = {
    critical: "bg-status-critical-bg text-status-critical border-status-critical-border",
    warning: "bg-status-warning-bg text-status-warning border-status-warning-border",
    high: "bg-status-warning-bg text-status-warning border-status-warning-border",
    medium: "bg-status-info-bg text-status-info border-status-info-border",
    low: "bg-brand-soft text-brand border-[#F0D5C9]",
    success: "bg-status-success-bg text-status-success border-status-success-border",
    approved: "bg-status-success-bg text-status-success border-status-success-border",
    pending: "bg-surface-muted text-ink-secondary border-border",
    dismissed: "bg-surface-muted text-ink-muted border-border line-through opacity-75",
    info: "bg-status-info-bg text-status-info border-status-info-border",
    neutral: "bg-surface-muted text-ink-secondary border-border",
    "not assessed": "bg-surface-muted text-ink-muted border-border",
  };

  const sizeClasses = {
    sm: "px-2.5 py-0.5 text-xs font-medium",
    md: "px-3 py-1 text-[13px] font-medium",
  }[size];

  const currentStyle = styles[normalizedVariant] || styles.neutral;

  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border ${sizeClasses} ${currentStyle}`}>
      {label}
    </span>
  );
}
