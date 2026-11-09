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
    <div className="p-5 bg-surface border border-border rounded-xl shadow-xs hover:border-[#cbd7cf] transition-all duration-150 flex flex-col justify-between h-full">
      <div className="flex items-start justify-between gap-2">
        <span className="text-xs sm:text-[13px] font-medium text-ink-secondary">
          {label}
        </span>
        {icon && <div className="text-ink-secondary/70">{icon}</div>}
        {!icon && href && <ArrowUpRight className="w-4 h-4 text-ink-muted group-hover:text-ink-primary transition-colors" />}
      </div>

      <div className="mt-3">
        <div className={`text-2xl sm:text-[28px] font-semibold tabular-nums tracking-tight ${valueColor}`}>
          {value}
        </div>
        {subtext && (
          <p className="text-xs text-ink-muted mt-1 leading-normal font-normal">
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
