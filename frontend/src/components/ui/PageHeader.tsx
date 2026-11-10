import React from "react";
import { Calendar } from "lucide-react";

interface PageHeaderProps {
  title: string;
  description?: string;
  referenceDate?: string;
  actions?: React.ReactNode;
}

export function PageHeader({ title, description, referenceDate, actions }: PageHeaderProps) {
  const handleOpenDateModal = () => {
    if (typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent("axeom:open-date-modal"));
    }
  };

  return (
    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 sm:gap-4 pb-4 sm:pb-5 border-b border-border min-w-0">
      <div className="space-y-1 min-w-0 flex-1">
        <div className="flex items-center gap-2 sm:gap-3 flex-wrap">
          <h1 className="text-xl sm:text-2xl lg:text-[26px] font-semibold text-ink-primary tracking-tight">
            {title}
          </h1>
          {referenceDate && (
            <button
              type="button"
              onClick={handleOpenDateModal}
              className="group inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-brand-soft text-brand border border-[#cbe0d6] hover:bg-brand-soft/80 hover:border-brand/40 transition-all cursor-pointer shadow-2xs shrink-0"
              title="Click to change scenario reference date"
            >
              <Calendar className="w-3 h-3 text-brand" />
              <span>
                <span className="hidden sm:inline">
                  {referenceDate === "2026-10-06"
                    ? "Challenge baseline: Oct 6, 2026"
                    : `As of ${referenceDate}`}
                </span>
                <span className="sm:hidden">
                  {referenceDate === "2026-10-06" ? "Oct 6, 2026" : referenceDate}
                </span>
              </span>
              <span className="text-[10px] text-brand/70 group-hover:text-brand font-semibold underline underline-offset-2 ml-0.5">
                Change
              </span>
            </button>
          )}
        </div>
        {description && (
          <p className="text-xs sm:text-sm text-ink-secondary leading-relaxed">
            {description}
          </p>
        )}
      </div>

      {actions && <div className="flex items-center gap-2 flex-wrap shrink-0">{actions}</div>}
    </div>
  );
}
