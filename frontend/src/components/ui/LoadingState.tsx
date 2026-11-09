import React from "react";
import { Loader2 } from "lucide-react";

interface LoadingStateProps {
  message?: string;
  variant?: "spinner" | "cards" | "table" | "metrics";
  count?: number;
}

export function LoadingState({
  message = "Loading data...",
  variant = "cards",
  count = 3,
}: LoadingStateProps) {
  if (variant === "metrics") {
    return (
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 animate-pulse" aria-busy="true" aria-label={message}>
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="p-4 bg-surface rounded-xl border border-border space-y-3">
            <div className="h-3 w-20 bg-surface-muted rounded" />
            <div className="h-7 w-28 bg-surface-muted rounded" />
            <div className="h-2.5 w-32 bg-surface-muted rounded" />
          </div>
        ))}
      </div>
    );
  }

  if (variant === "table") {
    return (
      <div className="bg-surface rounded-xl border border-border divide-y divide-border animate-pulse overflow-hidden" aria-busy="true" aria-label={message}>
        <div className="p-4 bg-surface-muted/40 flex items-center justify-between">
          <div className="h-4 w-32 bg-surface-muted rounded" />
          <div className="h-4 w-24 bg-surface-muted rounded" />
        </div>
        {Array.from({ length: count }).map((_, i) => (
          <div key={i} className="p-4 flex items-center justify-between gap-4">
            <div className="space-y-2 flex-1">
              <div className="h-4 w-40 bg-surface-muted rounded" />
              <div className="h-3 w-56 bg-surface-muted rounded" />
            </div>
            <div className="h-5 w-20 bg-surface-muted rounded-full" />
          </div>
        ))}
      </div>
    );
  }

  if (variant === "cards") {
    return (
      <div className="space-y-4 animate-pulse" aria-busy="true" aria-label={message}>
        {Array.from({ length: count }).map((_, i) => (
          <div key={i} className="p-5 bg-surface rounded-xl border border-border space-y-3">
            <div className="flex items-center justify-between">
              <div className="h-4 w-48 bg-surface-muted rounded" />
              <div className="h-5 w-16 bg-surface-muted rounded-full" />
            </div>
            <div className="h-3.5 w-full max-w-md bg-surface-muted rounded" />
            <div className="h-3 w-3/4 bg-surface-muted rounded" />
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="py-20 text-center space-y-3">
      <div className="w-10 h-10 rounded-full bg-brand-soft text-brand flex items-center justify-center mx-auto">
        <Loader2 className="w-5 h-5 animate-spin" />
      </div>
      <p className="text-sm font-medium text-ink-secondary">{message}</p>
    </div>
  );
}
