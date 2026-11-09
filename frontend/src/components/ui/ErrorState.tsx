import React from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";

interface ErrorStateProps {
  title?: string;
  message?: string;
  onRetry?: () => void;
}

export function ErrorState({
  title = "Unable to load data",
  message = "A connection error occurred while communicating with the backend.",
  onRetry,
}: ErrorStateProps) {
  return (
    <div className="p-6 bg-surface border border-status-critical-border rounded-xl space-y-4 max-w-lg mx-auto my-8">
      <div className="flex items-start gap-3.5">
        <div className="w-9 h-9 rounded-full bg-status-critical-bg text-status-critical flex items-center justify-center shrink-0 mt-0.5">
          <AlertTriangle className="w-5 h-5" />
        </div>
        <div className="space-y-1">
          <h3 className="text-base font-semibold text-ink-primary">{title}</h3>
          <p className="text-sm text-ink-secondary leading-relaxed">{message}</p>
        </div>
      </div>

      {onRetry && (
        <div className="pt-2 flex justify-end">
          <button
            onClick={onRetry}
            className="inline-flex items-center gap-2 px-4 py-2 bg-brand hover:bg-brand-hover text-white text-xs sm:text-sm font-medium rounded-lg transition-colors cursor-pointer"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Try again</span>
          </button>
        </div>
      )}
    </div>
  );
}
