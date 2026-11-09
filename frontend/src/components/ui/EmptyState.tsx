import React from "react";
import { FolderOpen } from "lucide-react";

interface EmptyStateProps {
  title: string;
  description?: string;
  action?: React.ReactNode;
  icon?: React.ReactNode;
}

export function EmptyState({
  title,
  description,
  action,
  icon,
}: EmptyStateProps) {
  return (
    <div className="py-16 px-6 text-center bg-surface border border-border rounded-xl space-y-4 max-w-md mx-auto my-6">
      <div className="w-12 h-12 rounded-full bg-brand-soft text-brand flex items-center justify-center mx-auto">
        {icon || <FolderOpen className="w-6 h-6" />}
      </div>

      <div className="space-y-1">
        <h3 className="text-base font-semibold text-ink-primary">{title}</h3>
        {description && (
          <p className="text-sm text-ink-secondary leading-relaxed max-w-sm mx-auto">
            {description}
          </p>
        )}
      </div>

      {action && <div className="pt-2">{action}</div>}
    </div>
  );
}
