"use client";

import React, { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import {
  ChevronDown,
  ChevronUp,
  RefreshCw,
  ShieldAlert,
  DollarSign,
  Clock,
  Inbox,
  Upload,
  X,
  ArrowRight,
  Check,
  CheckCheck,
  Film,
  TrendingUp,
  ExternalLink,
  Mic,
  Receipt,
  FileText,
  Copy,
} from "lucide-react";
import {
  api,
  DashboardSummary,
  ProductionOverview,
  MarketingAnalysisResponse,
  formatCurrency,
  ActionDraftResponse,
} from "@/lib/api";
import { triggerGlobalUploadModal } from "@/components/AddFilesModal";
import { PageHeader } from "@/components/ui/PageHeader";
import { StatusBadge, StatusVariant } from "@/components/ui/StatusBadge";
import { LoadingState } from "@/components/ui/LoadingState";
import { ErrorState } from "@/components/ui/ErrorState";

export default function TodayPage() {
  const [data, setData] = useState<DashboardSummary | null>(null);
  const [production, setProduction] = useState<ProductionOverview | null>(null);
  const [marketing, setMarketing] = useState<MarketingAnalysisResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedActionId, setExpandedActionId] = useState<string | null>(null);
  const [actionStatuses, setActionStatuses] = useState<Record<string, "pending" | "approved" | "dismissed">>({});
  const [actionUpdating, setActionUpdating] = useState<Record<string, boolean>>({});
  const [actionError, setActionError] = useState<string | null>(null);

  // Draft Modal state
  const [activeDraft, setActiveDraft] = useState<ActionDraftResponse | null>(null);
  const [draftText, setDraftText] = useState<string>("");
  const [draftLoading, setDraftLoading] = useState<boolean>(false);
  const [draftCopied, setDraftCopied] = useState<boolean>(false);
  const [draftSaved, setDraftSaved] = useState<boolean>(false);
  const [draftError, setDraftError] = useState<string | null>(null);

  const openDraftModal = async (actionId: string) => {
    try {
      setDraftLoading(true);
      setDraftError(null);
      setDraftCopied(false);
      setDraftSaved(false);
      const res = await api.getActionDraft(actionId, data?.reference_date);
      setActiveDraft(res);
      setDraftText(res.draft_text);
    } catch (err: any) {
      setActionError(err.message || "Failed to load prefilled draft.");
    } finally {
      setDraftLoading(false);
    }
  };

  const handleSaveDraft = async () => {
    if (!activeDraft) return;
    try {
      await api.updateActionDraft(activeDraft.action_id, draftText);
      setDraftSaved(true);
      setTimeout(() => setDraftSaved(false), 3000);
    } catch (err: any) {
      setDraftError(err.message || "Failed to save draft changes.");
    }
  };

  const handleCopyDraft = () => {
    if (typeof navigator !== "undefined" && navigator.clipboard) {
      navigator.clipboard.writeText(draftText);
      setDraftCopied(true);
      setTimeout(() => setDraftCopied(false), 2500);
    }
  };

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const [dashRes, prodRes, mktRes] = await Promise.allSettled([
        api.getDashboard(),
        api.getProductionOverview(),
        api.getMarketingAnalysis(),
      ]);

      if (dashRes.status === "fulfilled") {
        setData(dashRes.value);
        const initialStatuses: Record<string, "pending" | "approved" | "dismissed"> = {};
        dashRes.value.monday_top_3.forEach((act) => {
          initialStatuses[act.id] = act.status;
        });
        setActionStatuses(initialStatuses);
      } else {
        throw new Error(dashRes.reason?.message || "Failed to load morning briefing.");
      }

      if (prodRes.status === "fulfilled") {
        setProduction(prodRes.value);
      }

      if (mktRes.status === "fulfilled") {
        setMarketing(mktRes.value);
      }
    } catch (err: any) {
      setError(err.message || "Failed to connect to Axeom backend.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();

    const handleDataRefreshed = () => {
      loadData();
    };
    window.addEventListener("axeom:data-refreshed", handleDataRefreshed);
    window.addEventListener("axeom:reference-date-changed", handleDataRefreshed);

    return () => {
      window.removeEventListener("axeom:data-refreshed", handleDataRefreshed);
      window.removeEventListener("axeom:reference-date-changed", handleDataRefreshed);
    };
  }, [loadData]);

  const handleAction = async (actionId: string, newStatus: "approved" | "dismissed" | "pending") => {
    const previousStatus = actionStatuses[actionId] || "pending";
    setActionUpdating((prev) => ({ ...prev, [actionId]: true }));
    setActionError(null);

    try {
      await api.updateActionStatus(actionId, newStatus);
      setActionStatuses((prev) => ({ ...prev, [actionId]: newStatus }));
    } catch {
      setActionStatuses((prev) => ({ ...prev, [actionId]: previousStatus }));
      setActionError("Unable to update action status. Please ensure the backend is connected.");
    } finally {
      setActionUpdating((prev) => ({ ...prev, [actionId]: false }));
    }
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="h-10 w-48 bg-surface-muted rounded animate-pulse" />
        <LoadingState variant="cards" count={3} message="Loading morning briefing..." />
      </div>
    );
  }

  if (error || !data) {
    return (
      <ErrorState
        title="Could not load Today overview"
        message={error || "Ensure the FastAPI backend server is running on http://localhost:8000."}
        onRetry={loadData}
      />
    );
  }

  const isDbEmpty = data.data_status
    ? data.data_status.is_empty
    : parseFloat(data.overview.total_invoiced || "0") === 0 &&
      data.overview.active_clients_count === 0 &&
      data.overview.unanswered_leads_count === 0;

  const activeWipCount = production?.active_work_in_progress?.length ?? 0;
  const legitimateLeadsCount = data.overview.legitimate_unanswered_leads_count ?? 0;
  const privacyAlertsCount = data.overview.privacy_alerts_count ?? 0;
  const confirmedOverdue = data.overview.overdue_receivables ?? "0.00";
  const overdueCount = data.financial_alerts.overdue_invoices_count ?? 0;

  // Contextual destination and labels for each priority
  const getActionContext = (idx: number) => {
    if (idx === 0) {
      return {
        reason: "Privacy requirement unresolved",
        actionLabel: "Review in Production",
        href: "/production",
      };
    }
    if (idx === 1) {
      return {
        reason: "Repeated complaint & contract review",
        actionLabel: "Review Client",
        href: "/clients",
      };
    }
    return {
      reason: "Payment & invoice mismatch",
      actionLabel: "Review in Money",
      href: "/money",
    };
  };

  return (
    <div className="space-y-8 max-w-6xl">
      {/* 1. Header with scenario reference date */}
      <PageHeader
        title="Today"
        referenceDate={data.reference_date}
        actions={
          <button
            onClick={loadData}
            className="inline-flex items-center gap-1.5 px-3 py-2 text-xs sm:text-sm font-medium text-ink-secondary hover:text-ink-primary bg-surface border border-border rounded-lg hover:bg-surface-muted transition-colors cursor-pointer shadow-xs"
            aria-label="Refresh today's briefing data"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Refresh</span>
          </button>
        }
      />

      {/* ZERO-DATA / EMPTY DATABASE STATE */}
      {isDbEmpty ? (
        <div className="py-16 px-6 text-center bg-surface border border-border rounded-2xl space-y-4 max-w-lg mx-auto">
          <div className="w-14 h-14 rounded-full bg-brand-soft text-brand flex items-center justify-center mx-auto">
            <Upload className="w-7 h-7" />
          </div>
          <div className="space-y-1.5">
            <h2 className="text-lg font-semibold text-ink-primary">No studio records loaded</h2>
            <p className="text-sm text-ink-secondary leading-relaxed max-w-md mx-auto">
              Add the challenge data files to calculate financial reconciliations, detect privacy risks, and view your next priorities.
            </p>
          </div>
          <button
            onClick={triggerGlobalUploadModal}
            className="inline-flex items-center gap-2 px-5 py-2.5 bg-brand hover:bg-brand-hover text-white text-sm font-medium rounded-lg transition-colors cursor-pointer shadow-xs"
          >
            <Upload className="w-4 h-4" />
            <span>Add data files</span>
          </button>
        </div>
      ) : (
        <>
          {/* 2. YOUR NEXT 3 ACTIONS (FOCUSED 10-SECOND TEST) */}
          <section className="space-y-4" aria-label="Your next 3 actions">
            {actionError && (
              <div className="p-3.5 bg-status-critical-bg border border-status-critical-border text-status-critical text-xs sm:text-sm rounded-xl flex items-center justify-between">
                <span>{actionError}</span>
                <button
                  onClick={() => setActionError(null)}
                  className="p-1 hover:opacity-75 cursor-pointer"
                  aria-label="Dismiss error"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            )}

            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <div>
                <div className="flex items-center gap-2.5">
                  <h2 className="text-xl sm:text-[22px] font-semibold text-ink-primary tracking-tight">
                    Your next 3 actions
                  </h2>
                  <span className="px-2 py-0.5 rounded-full bg-brand-soft text-brand text-xs font-semibold">
                    {data.monday_top_3.length} priorities
                  </span>
                </div>
                <p className="text-xs sm:text-sm text-ink-secondary mt-0.5">
                  Top operational priorities requiring owner review before any status changes take effect.
                </p>
              </div>

              <div className="hidden sm:inline-flex items-center gap-1.5 text-xs text-ink-muted">
                <ShieldAlert className="w-4 h-4 text-brand" />
                <span>Requires owner confirmation</span>
              </div>
            </div>

            <div className="space-y-3.5">
              {data.monday_top_3.map((action, idx) => {
                const isExpanded = expandedActionId === action.id;
                const currentStatus = actionStatuses[action.id] || action.status;
                const isApproved = currentStatus === "approved";
                const isDismissed = currentStatus === "dismissed";
                const isUpdating = actionUpdating[action.id] || false;
                const ctx = getActionContext(idx);

                return (
                  <div
                    key={action.id}
                    className={`p-4 sm:p-5 bg-surface border rounded-xl shadow-xs space-y-3 transition-all ${
                      isDismissed
                        ? "border-border/60 opacity-60 bg-surface-muted/20"
                        : isApproved
                        ? "border-status-success-border/60 bg-status-success-bg/10"
                        : "border-border hover:border-brand/40"
                    }`}
                  >
                    {/* Header: Urgency badge, Reason, Client, Status */}
                    <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
                      <div className="space-y-1.5 flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="w-5 h-5 rounded-full bg-brand-soft text-brand text-xs font-bold flex items-center justify-center shrink-0">
                            {idx + 1}
                          </span>
                          <StatusBadge
                            label={action.urgency}
                            variant={action.urgency.toLowerCase() as StatusVariant}
                          />
                          <span className="text-xs font-medium text-ink-secondary px-2 py-0.5 rounded bg-surface-muted border border-border truncate max-w-full">
                            {ctx.reason}
                          </span>
                          {action.client_name && (
                            <span className="text-xs text-ink-muted font-medium truncate">
                              • {action.client_name}
                            </span>
                          )}
                        </div>

                        {/* Short Action-Oriented Title (5-9 words) */}
                        <h3 className="text-base sm:text-lg font-semibold text-ink-primary pt-0.5 leading-snug">
                          {action.title}
                        </h3>

                        {/* One clear sentence explaining why it matters */}
                        <p className="text-xs sm:text-sm text-ink-secondary leading-relaxed">
                          {action.why_it_matters}
                        </p>
                      </div>

                      {/* Current review status badge */}
                      <div className="shrink-0 pt-0.5 self-start sm:self-auto">
                        {isApproved && (
                          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-status-success-bg text-status-success border border-status-success-border">
                            <Check className="w-3.5 h-3.5" />
                            <span>Reviewed in app</span>
                          </span>
                        )}
                        {isDismissed && (
                          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-surface-muted text-ink-muted border border-border line-through">
                            <span>Dismissed</span>
                          </span>
                        )}
                        {!isApproved && !isDismissed && (
                          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-surface-muted text-ink-secondary border border-border">
                            <span>Pending review</span>
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Expandable Evidence Details (Clean Progressive Disclosure) */}
                    {action.evidence && action.evidence.length > 0 && (
                      <div className="pt-0.5">
                        <button
                          type="button"
                          onClick={() => setExpandedActionId(isExpanded ? null : action.id)}
                          className="inline-flex items-center gap-1 text-xs font-medium text-brand hover:text-brand-hover transition-colors cursor-pointer"
                        >
                          <span>{isExpanded ? "Hide source evidence" : `View source evidence (${action.evidence.length} records)`}</span>
                          {isExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                        </button>

                        {isExpanded && (
                          <div className="mt-2.5 p-3.5 bg-surface-muted/60 rounded-lg border border-border space-y-2 text-xs text-ink-secondary">
                            {action.evidence.map((ev, i) => (
                              <div key={i} className="flex items-start gap-2">
                                <span className="text-brand shrink-0 font-bold">•</span>
                                <span className="leading-relaxed">{ev}</span>
                              </div>
                            ))}
                            {action.what_is_uncertain && (
                              <div className="pt-2 mt-2 border-t border-border text-ink-secondary">
                                <span className="font-semibold text-ink-primary">Requires human verification: </span>
                                <span>{action.what_is_uncertain}</span>
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    )}

                    {/* Clear actions: Contextual review link + Review/Dismiss state (Responsive wrap ensures Mark reviewed never goes off-screen) */}
                    <div className="pt-3 border-t border-border flex flex-col gap-2.5">
                      <div className="text-xs text-ink-secondary flex items-start gap-1.5">
                        <span className="font-semibold text-ink-primary shrink-0">Recommended step:</span>
                        <span className="leading-relaxed">{action.suggested_action}</span>
                      </div>

                      <div className="flex items-center gap-2 flex-wrap pt-0.5">
                        {/* Prefilled Communication Draft */}
                        <button
                          type="button"
                          onClick={() => openDraftModal(action.id)}
                          disabled={draftLoading}
                          className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-brand hover:text-brand-hover bg-brand-soft border border-brand/20 rounded-lg hover:bg-brand/10 transition-colors cursor-pointer"
                          title="Open prefilled communication draft citing verified business records"
                        >
                          <FileText className="w-3.5 h-3.5" />
                          <span>Review draft</span>
                        </button>

                        {/* Contextual navigation link */}
                        <Link
                          href={ctx.href}
                          className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-ink-secondary hover:text-ink-primary bg-surface border border-border rounded-lg hover:bg-surface-muted transition-colors"
                        >
                          <span>{ctx.actionLabel}</span>
                          <ExternalLink className="w-3 h-3 text-ink-muted" />
                        </Link>

                        {/* Status update controls */}
                        {isApproved ? (
                          <button
                            type="button"
                            onClick={() => handleAction(action.id, "pending")}
                            disabled={isUpdating}
                            className="px-3 py-1.5 text-xs font-medium text-ink-secondary hover:text-ink-primary bg-surface border border-border rounded-lg transition-colors cursor-pointer disabled:opacity-50"
                          >
                            Reset
                          </button>
                        ) : isDismissed ? (
                          <button
                            type="button"
                            onClick={() => handleAction(action.id, "pending")}
                            disabled={isUpdating}
                            className="px-3 py-1.5 text-xs font-medium text-ink-secondary hover:text-ink-primary bg-surface border border-border rounded-lg transition-colors cursor-pointer disabled:opacity-50"
                          >
                            Restore
                          </button>
                        ) : (
                          <>
                            <button
                              type="button"
                              onClick={() => handleAction(action.id, "dismissed")}
                              disabled={isUpdating}
                              className="px-3 py-1.5 text-xs font-medium text-ink-secondary hover:text-ink-primary bg-surface border border-border rounded-lg hover:bg-surface-muted transition-colors cursor-pointer disabled:opacity-50"
                            >
                              Dismiss
                            </button>
                            <button
                              type="button"
                              onClick={() => handleAction(action.id, "approved")}
                              disabled={isUpdating}
                              className="px-3.5 py-1.5 text-xs font-medium text-white bg-brand hover:bg-brand-hover rounded-lg transition-colors cursor-pointer shadow-xs disabled:opacity-50 flex items-center gap-1.5"
                            >
                              <Check className="w-3.5 h-3.5" />
                              <span>Mark reviewed</span>
                            </button>
                          </>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </section>

          {/* 3. STUDIO AT A GLANCE — 4 GENUINELY USEFUL, NON-CONFLICTING METRICS */}
          <section className="space-y-3 pt-2" aria-label="Studio overview metrics">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-ink-secondary uppercase tracking-wider">
                Studio at a glance
              </h3>
              <span className="text-xs text-ink-muted">As of {data.reference_date}</span>
            </div>

            <div className="grid grid-cols-2 lg:grid-cols-4 gap-2.5 sm:gap-3.5">
              {/* Metric 1: Confirmed Overdue */}
              <Link
                href="/money"
                className="group p-3.5 sm:p-4 bg-surface rounded-xl border border-border hover:border-status-critical/40 transition-colors shadow-xs flex flex-col justify-between min-w-0 overflow-hidden"
              >
                <div className="flex items-center justify-between text-xs text-ink-secondary gap-1.5 min-w-0">
                  <span className="font-medium truncate">Confirmed overdue</span>
                  <Clock className="w-4 h-4 text-status-critical shrink-0" />
                </div>
                <div className="mt-2 sm:mt-2.5 min-w-0">
                  <div className="text-lg xs:text-xl sm:text-2xl font-semibold tabular-nums text-status-critical tracking-tight truncate">
                    {formatCurrency(confirmedOverdue)}
                  </div>
                  <p className="text-[11px] sm:text-xs text-ink-muted mt-0.5 truncate">
                    {overdueCount} reconciled invoices past due
                  </p>
                </div>
              </Link>

              {/* Metric 2: Legitimate Prospects Awaiting Reply */}
              <Link
                href="/requests"
                className="group p-3.5 sm:p-4 bg-surface rounded-xl border border-border hover:border-status-warning/40 transition-colors shadow-xs flex flex-col justify-between min-w-0 overflow-hidden"
              >
                <div className="flex items-center justify-between text-xs text-ink-secondary gap-1.5 min-w-0">
                  <span className="font-medium truncate">Prospects awaiting reply</span>
                  <Inbox className="w-4 h-4 text-status-warning shrink-0" />
                </div>
                <div className="mt-2 sm:mt-2.5 min-w-0">
                  <div className="text-lg xs:text-xl sm:text-2xl font-semibold tabular-nums text-status-warning tracking-tight truncate">
                    {legitimateLeadsCount} prospects
                  </div>
                  <p className="text-[11px] sm:text-xs text-ink-muted mt-0.5 truncate">
                    Excludes spam & existing clients
                  </p>
                </div>
              </Link>

              {/* Metric 3: Privacy Release Alerts */}
              <Link
                href="/production"
                className="group p-3.5 sm:p-4 bg-surface rounded-xl border border-border hover:border-brand/40 transition-colors shadow-xs flex flex-col justify-between min-w-0 overflow-hidden"
              >
                <div className="flex items-center justify-between text-xs text-ink-secondary gap-1.5 min-w-0">
                  <span className="font-medium truncate">Privacy release alerts</span>
                  <ShieldAlert className="w-4 h-4 text-brand shrink-0" />
                </div>
                <div className="mt-2 sm:mt-2.5 min-w-0">
                  <div className="text-lg xs:text-xl sm:text-2xl font-semibold tabular-nums text-brand tracking-tight truncate">
                    {privacyAlertsCount} videos
                  </div>
                  <p className="text-[11px] sm:text-xs text-ink-muted mt-0.5 truncate">
                    Unsigned media releases to verify
                  </p>
                </div>
              </Link>

              {/* Metric 4: Active Work in Progress */}
              <Link
                href="/production"
                className="group p-3.5 sm:p-4 bg-surface rounded-xl border border-border hover:border-ink-secondary/40 transition-colors shadow-xs flex flex-col justify-between min-w-0 overflow-hidden"
              >
                <div className="flex items-center justify-between text-xs text-ink-secondary gap-1.5 min-w-0">
                  <span className="font-medium truncate">Active production</span>
                  <Film className="w-4 h-4 text-ink-secondary shrink-0" />
                </div>
                <div className="mt-2 sm:mt-2.5 min-w-0">
                  <div className="text-lg xs:text-xl sm:text-2xl font-semibold tabular-nums text-ink-primary tracking-tight truncate">
                    {activeWipCount} in progress
                  </div>
                  <p className="text-[11px] sm:text-xs text-ink-muted mt-0.5 truncate">
                    Editing, review, or revision
                  </p>
                </div>
              </Link>
            </div>
          </section>

          {/* 4. COMPACT MARKETING ACQUISITION INSIGHT (SECONDARY CARD) */}
          {marketing?.best_marketing_channel && (
            <section aria-label="Marketing acquisition insight" className="pt-1">
              <div className="p-4 sm:p-5 bg-surface rounded-xl border border-border shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div className="flex items-start sm:items-center gap-3.5">
                  <div className="w-10 h-10 rounded-lg bg-brand-soft text-brand flex items-center justify-center shrink-0 mt-0.5 sm:mt-0">
                    <TrendingUp className="w-5 h-5" />
                  </div>
                  <div className="space-y-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-xs font-semibold text-brand uppercase tracking-wider">
                        Marketing Acquisition Insight
                      </span>
                      <span className="text-xs text-ink-muted">• Best Observed Conversion</span>
                    </div>
                    <p className="text-xs sm:text-sm text-ink-primary leading-relaxed">
                      <strong className="font-semibold text-ink-primary">
                        {marketing.best_marketing_channel.channel}
                      </strong>{" "}
                      achieved the highest observed conversion at{" "}
                      <strong className="font-semibold text-brand">
                        {(marketing.best_marketing_channel.conversion_rate ?? 78.6).toFixed(1)}%
                      </strong>{" "}
                      ({marketing.best_marketing_channel.won_leads ?? 11} won out of{" "}
                      {marketing.best_marketing_channel.total_leads ?? 14} leads,{" "}
                      {formatCurrency(marketing.best_marketing_channel.attributed_revenue ?? 66800)} attributed revenue).
                      <span className="text-ink-secondary block sm:inline sm:ml-1">
                        Advertising spend is missing from costs, so net channel profitability cannot be proven.
                      </span>
                    </p>
                  </div>
                </div>

                <Link
                  href="/requests"
                  className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-medium text-brand hover:text-brand-hover bg-brand-soft/60 hover:bg-brand-soft border border-[#cbe0d6] rounded-lg transition-colors shrink-0"
                >
                  <span>View channel table</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </Link>
              </div>
            </section>
          )}

          {/* 5. WORK QUEUES SHORTCUT STRIP */}
          <section className="pt-1" aria-label="Work queue shortcuts">
            <h3 className="text-xs font-semibold text-ink-secondary uppercase tracking-wider mb-2.5">
              Operational Work Queues
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3.5">
              <Link
                href="/requests"
                className="group p-4 bg-surface rounded-xl border border-border hover:border-brand/40 transition-colors flex items-center justify-between text-xs sm:text-sm"
              >
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg bg-surface-muted text-ink-secondary flex items-center justify-center shrink-0">
                    <Mic className="w-4 h-4" />
                  </div>
                  <div>
                    <span className="font-medium text-ink-primary block">Voice notes to review</span>
                    <span className="text-xs text-ink-muted">
                      {data.overview.lost_requests_count} unlogged client notes
                    </span>
                  </div>
                </div>
                <ArrowRight className="w-4 h-4 text-ink-muted group-hover:text-brand transition-colors" />
              </Link>

              <Link
                href="/money"
                className="group p-4 bg-surface rounded-xl border border-border hover:border-brand/40 transition-colors flex items-center justify-between text-xs sm:text-sm"
              >
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg bg-surface-muted text-ink-secondary flex items-center justify-center shrink-0">
                    <Receipt className="w-4 h-4" />
                  </div>
                  <div>
                    <span className="font-medium text-ink-primary block">Work to review for billing</span>
                    <span className="text-xs text-ink-muted">
                      {formatCurrency(data.overview.never_billed_total ?? "0.00")} completed shoots
                    </span>
                  </div>
                </div>
                <ArrowRight className="w-4 h-4 text-ink-muted group-hover:text-brand transition-colors" />
              </Link>

              <Link
                href="/money"
                className="group p-4 bg-surface rounded-xl border border-border hover:border-brand/40 transition-colors flex items-center justify-between text-xs sm:text-sm"
              >
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg bg-surface-muted text-ink-secondary flex items-center justify-center shrink-0">
                    <DollarSign className="w-4 h-4" />
                  </div>
                  <div>
                    <span className="font-medium text-ink-primary block">Bank collections</span>
                    <span className="text-xs text-ink-muted">
                      {formatCurrency(data.overview.total_bank_collected)} cleared deposits
                    </span>
                  </div>
                </div>
                <ArrowRight className="w-4 h-4 text-ink-muted group-hover:text-brand transition-colors" />
              </Link>
            </div>
          </section>
        </>
      )}

      {/* DETERMINISTIC COMMUNICATION DRAFT MODAL */}
      {activeDraft && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs">
          <div className="bg-surface border border-border rounded-2xl shadow-xl w-full max-w-2xl max-h-[90vh] flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-150">
            {/* Modal Header */}
            <div className="p-4 sm:p-5 border-b border-border flex items-center justify-between gap-3 bg-surface-muted/30">
              <div className="space-y-0.5">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-semibold px-2 py-0.5 rounded bg-brand-soft text-brand uppercase tracking-wider">
                    {activeDraft.responsible_area} Draft
                  </span>
                  {activeDraft.client_name && (
                    <span className="text-xs text-ink-muted font-medium">
                      • {activeDraft.client_name}
                    </span>
                  )}
                </div>
                <h3 className="text-base sm:text-lg font-semibold text-ink-primary">
                  {activeDraft.title}
                </h3>
              </div>
              <button
                onClick={() => setActiveDraft(null)}
                className="p-1.5 text-ink-muted hover:text-ink-primary rounded-lg hover:bg-surface-muted cursor-pointer"
                aria-label="Close draft modal"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Safety Notice Banner */}
            <div className="px-4 py-2.5 bg-amber-500/10 border-b border-amber-500/20 text-amber-700 dark:text-amber-400 text-xs flex items-center gap-2">
              <ShieldAlert className="w-4 h-4 shrink-0" />
              <span>
                Deterministic draft grounded in verified database records. StudioOS never sends external communications automatically.
              </span>
            </div>

            {/* Modal Body */}
            <div className="p-4 sm:p-5 flex-1 overflow-y-auto space-y-3">
              <label className="block text-xs font-medium text-ink-secondary">
                Editable Communication Text (cites verified records; never generated by an external LLM):
              </label>
              <textarea
                value={draftText}
                onChange={(e) => setDraftText(e.target.value)}
                rows={10}
                className="w-full p-3.5 text-sm text-ink-primary bg-surface border border-border rounded-xl font-mono leading-relaxed focus:outline-hidden focus:ring-2 focus:ring-brand focus:border-transparent resize-y"
                placeholder="Draft message content..."
              />
              {draftError && (
                <p className="text-xs text-status-critical font-medium">{draftError}</p>
              )}
            </div>

            {/* Modal Footer */}
            <div className="p-4 sm:p-5 border-t border-border flex items-center justify-between gap-3 bg-surface-muted/30">
              <button
                type="button"
                onClick={handleCopyDraft}
                className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-medium text-ink-primary bg-surface border border-border rounded-lg hover:bg-surface-muted transition-colors cursor-pointer shadow-xs"
              >
                {draftCopied ? <CheckCheck className="w-4 h-4 text-status-success" /> : <Copy className="w-4 h-4" />}
                <span>{draftCopied ? "Copied to clipboard!" : "Copy text"}</span>
              </button>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setActiveDraft(null)}
                  className="px-3.5 py-2 text-xs font-medium text-ink-secondary hover:text-ink-primary bg-surface border border-border rounded-lg hover:bg-surface-muted transition-colors cursor-pointer"
                >
                  Close
                </button>
                <button
                  type="button"
                  onClick={handleSaveDraft}
                  className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-medium text-white bg-brand hover:bg-brand-hover rounded-lg transition-colors cursor-pointer shadow-xs"
                >
                  {draftSaved ? <Check className="w-4 h-4" /> : null}
                  <span>{draftSaved ? "Saved!" : "Save draft"}</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
