import React from "react";
import Link from "next/link";
import { ArrowUpRight } from "lucide-react";

interface MetricCardProps {
  label: string;
  value: string | number;
  subtext?: string;
  icon?: React.ReactNode;
  variant?: "neutral" | "brand" | "warning" | "critical" | "success";
  href?: string;
}

export function MetricCard({
  label,
  value,
  subtext,
  icon,
  variant = "neutral",
  href,
}: MetricCardProps) {
  const valueColor = {
    neutral: "text-ink-primary",
    brand: "text-brand",
    warning: "text-status-warning",
    critical: "text-status-critical",
    success: "text-status-success",
  }[variant];

  const content = (
    <div className="p-3 sm:p-4 lg:p-5 bg-surface border border-border rounded-xl shadow-xs hover:border-[#cbd7cf] transition-all duration-150 flex flex-col justify-between h-full min-w-0">
      <div className="flex items-start justify-between gap-1.5 min-w-0">
        <span className="text-xs sm:text-[13px] font-medium text-ink-secondary line-clamp-2 leading-snug">
          {label}
        </span>
        {icon && <div className="text-ink-secondary/70 shrink-0 mt-0.5">{icon}</div>}
        {!icon && href && <ArrowUpRight className="w-4 h-4 text-ink-muted group-hover:text-ink-primary transition-colors shrink-0" />}
      </div>

      <div className="mt-2 sm:mt-3 min-w-0">
        <div className={`text-base xs:text-lg sm:text-xl lg:text-[26px] font-semibold tabular-nums tracking-tight break-words leading-tight ${valueColor}`}>
          {value}
        </div>
        {subtext && (
          <p className="text-[11px] sm:text-xs text-ink-muted mt-1 leading-normal font-normal line-clamp-2">
            {subtext}
          </p>
        )}
      </div>
    </div>
  );

  if (href) {
    return (
      <Link href={href} className="group block h-full">
        {content}
      </Link>
    );
  }

  return content;
}
