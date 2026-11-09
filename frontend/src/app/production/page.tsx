"use client";

import React, { useEffect, useState, useMemo } from "react";
import {
  Search,
  RefreshCw,
  User,
  X,
  ShieldAlert,
  ChevronDown,
  ChevronUp,
  Layers,
} from "lucide-react";
import { api, ProductionOverview, ProductionVideoItem, formatCurrency, formatDate } from "@/lib/api";
import { PageHeader } from "@/components/ui/PageHeader";
import { StatusBadge, StatusVariant } from "@/components/ui/StatusBadge";
import { LoadingState } from "@/components/ui/LoadingState";
import { ErrorState } from "@/components/ui/ErrorState";
import { EmptyState } from "@/components/ui/EmptyState";

const PAGE_SIZE = 40;

export default function ProductionPage() {
  const [data, setData] = useState<ProductionOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedFilter, setSelectedFilter] = useState<string>("active_wip");
  const [searchQuery, setSearchQuery] = useState("");
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);
  const [selectedVideo, setSelectedVideo] = useState<ProductionVideoItem | null>(null);
  const [showWorkload, setShowWorkload] = useState(false);

  const loadProduction = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await api.getProductionOverview();
      setData(res);
    } catch (err: any) {
      setError(err.message || "Failed to load production pipeline.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadProduction();

    const handleDataRefreshed = () => {
      loadProduction();
    };
    window.addEventListener("axeom:data-refreshed", handleDataRefreshed);
    return () => {
      window.removeEventListener("axeom:data-refreshed", handleDataRefreshed);
    };
  }, []);

  const activeWork = useMemo(() => data?.active_work_in_progress || [], [data?.active_work_in_progress]);
  const allVideos = useMemo(() => data?.all_videos || activeWork, [data?.all_videos, activeWork]);
  const stages = data?.stage_breakdown || {};
  const editors = data?.editor_metrics || [];
  const costSummary = data?.cost_summary;

  const deliveredCount = stages["Delivered"] || 0;
  const inEditCount = stages["In edit"] || 0;
  const inReviewCount = stages["In review"] || 0;
  const inRevisionCount = stages["In revision"] || 0;
  const privacyVideos = useMemo(() => allVideos.filter((v) => v.has_privacy_alert), [allVideos]);
  const missingBookingCount =
    data?.missing_shoot_booking_count ?? allVideos.filter((v) => !v.shoot_booking).length;

  const totalAllVideos = allVideos.length || deliveredCount + inEditCount + inReviewCount + inRevisionCount;

  // Filter video dataset
  const baseVideos = useMemo(() => {
    switch (selectedFilter) {
      case "active_wip":
        return activeWork;
      case "needs_attention":
        return allVideos.filter((v) => v.has_privacy_alert || v.stage === "In revision");
      case "privacy_alerts":
        return privacyVideos;
      case "in_revision":
        return allVideos.filter((v) => v.stage === "In revision");
      case "in_review":
        return allVideos.filter((v) => v.stage === "In review");
      case "in_edit":
        return allVideos.filter((v) => v.stage === "In edit");
      case "delivered":
        return allVideos.filter((v) => v.stage === "Delivered");
      case "no_booking":
        return allVideos.filter((v) => !v.shoot_booking);
      case "all":
      default:
        return allVideos;
    }
  }, [selectedFilter, activeWork, allVideos, privacyVideos]);

  const filteredVideos = useMemo(() => {
    if (!searchQuery) return baseVideos;
    const q = searchQuery.toLowerCase().trim();
    return baseVideos.filter(
      (v) =>
        (v.title && v.title.toLowerCase().includes(q)) ||
        (v.client && v.client.toLowerCase().includes(q)) ||
        (v.client_name && v.client_name.toLowerCase().includes(q)) ||
        (v.editor && v.editor.toLowerCase().includes(q)) ||
        (v.video_id && v.video_id.toLowerCase().includes(q)) ||
        (v.notes_on_board && v.notes_on_board.toLowerCase().includes(q))
    );
  }, [baseVideos, searchQuery]);

  // Reset pagination on filter or search change
  useEffect(() => {
    setVisibleCount(PAGE_SIZE);
  }, [selectedFilter, searchQuery]);

  const displayedVideos = filteredVideos.slice(0, visibleCount);

  const getStageVariant = (stage?: string): StatusVariant => {
    if (!stage) return "neutral";
    const s = stage.toLowerCase();
    if (s.includes("revision")) return "critical";
    if (s.includes("review")) return "warning";
    if (s.includes("edit")) return "info";
    if (s.includes("delivered") || s.includes("complete")) return "success";
    return "neutral";
  };

  if (loading) {
    return <LoadingState message="Loading video production pipeline..." variant="table" />;
  }

  if (error || !data) {
    return (
      <ErrorState
        title="Could not load production pipeline"
        message={error || "Unable to reach the studio backend. Please check your network connection or try reloading."}
        onRetry={loadProduction}
      />
    );
  }

  return (
    <div className="space-y-6 max-w-6xl">
      {/* Header */}
      <PageHeader
        title="Production"
        description={`${totalAllVideos} tracked videos across editing, client review, revisions, and deliveries.`}
        actions={
          <button
            onClick={loadProduction}
            className="inline-flex items-center gap-1.5 px-3 py-2 text-xs sm:text-sm font-medium text-ink-secondary hover:text-ink-primary bg-surface border border-border rounded-lg hover:bg-surface-muted transition-colors cursor-pointer shadow-xs"
            aria-label="Refresh production data"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Refresh</span>
          </button>
        }
      />

      {/* 1. COMPACT "NEEDS ATTENTION" TOP SECTION (PRIVACY ALERTS & REVISIONS) */}
      <section className="space-y-3" aria-label="Production needs attention">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <h2 className="text-base sm:text-lg font-semibold text-ink-primary tracking-tight">
              Needs attention
            </h2>
            <span className="px-2 py-0.5 rounded-full bg-status-critical-bg text-status-critical text-xs font-semibold">
              {privacyVideos.length + inRevisionCount} items
            </span>
          </div>
          <span className="text-xs text-ink-muted">Requires human inspection</span>
        </div>

        {/* 6 PRIVACY & RELEASE ALERTS SPOTLIGHT */}
        {privacyVideos.length > 0 && (
          <div className="p-4 sm:p-5 bg-status-critical-bg/30 border border-status-critical-border rounded-xl space-y-3 shadow-xs">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-status-critical-bg text-status-critical flex items-center justify-center shrink-0">
                  <ShieldAlert className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="text-sm sm:text-base font-semibold text-ink-primary">
                    {privacyVideos.length} Unsigned-Release Privacy Alerts (1 Missing from Board)
                  </h3>
                  <p className="text-xs text-ink-secondary">
                    Patients/clients without signed media releases. Human visual confirmation of face blurring is required before publishing.
                  </p>
                </div>
              </div>

              <button
                type="button"
                onClick={() => setSelectedFilter("privacy_alerts")}
                className="inline-flex items-center gap-1 text-xs font-medium text-status-critical hover:underline cursor-pointer shrink-0"
              >
                <span>Filter to 6 privacy videos</span>
                <ChevronDown className="w-3.5 h-3.5" />
              </button>
            </div>

            {/* List of flagged privacy videos */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2.5 pt-1">
              {privacyVideos.map((pv) => (
                <div
                  key={pv.video_id}
                  onClick={() => setSelectedVideo(pv)}
                  className={`p-3 rounded-lg border text-xs transition-colors cursor-pointer ${
                    pv.privacy_board_missing
                      ? "bg-status-critical-bg border-status-critical text-status-critical font-medium"
                      : "bg-surface border-border hover:border-status-critical/60 text-ink-primary"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-mono font-bold">{pv.video_id}</span>
                    <span
                      className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ${
                        pv.privacy_board_missing
                          ? "bg-red-700 text-white"
                          : "bg-status-warning-bg text-status-warning border border-status-warning-border"
                      }`}
                    >
                      {pv.privacy_board_missing ? "BOARD NOTE MISSING!" : "Blur Note on Board"}
                    </span>
                  </div>
                  <div className="font-semibold text-sm mt-1 truncate">{pv.title}</div>
                  <div className="text-xs text-ink-secondary truncate">
                    {pv.client_name || pv.client} • {pv.stage}
                  </div>
                  {pv.privacy_board_missing && (
                    <p className="text-[11px] text-status-critical font-normal mt-1 leading-tight">
                      Client voice note requested face blur, but board note was left blank!
                    </p>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </section>

      {/* 2. SINGLE CLEAN STAGE SUMMARY (NO DUPLICATE CARDS + BAR) */}
      <section className="p-4 bg-surface border border-border rounded-xl shadow-xs space-y-3" aria-label="Pipeline overview">
        <div className="flex items-center justify-between text-xs font-semibold text-ink-secondary">
          <div className="flex items-center gap-2">
            <Layers className="w-4 h-4 text-brand" />
            <span>Active Pipeline & Delivery Summary</span>
          </div>
          <span className="text-ink-muted tabular-nums">
            {activeWork.length} active WIP • {deliveredCount} delivered
          </span>
        </div>

        {/* Distribution Progress Bar */}
        <div className="h-2.5 w-full bg-surface-muted rounded-full overflow-hidden flex">
          {deliveredCount > 0 && totalAllVideos > 0 && (
            <div
              style={{ width: `${(deliveredCount / totalAllVideos) * 100}%` }}
              className="bg-status-success h-full transition-all"
              title={`Delivered: ${deliveredCount}`}
            />
          )}
          {inEditCount > 0 && totalAllVideos > 0 && (
            <div
              style={{ width: `${(inEditCount / totalAllVideos) * 100}%` }}
              className="bg-brand h-full transition-all"
              title={`In edit: ${inEditCount}`}
            />
          )}
          {inReviewCount > 0 && totalAllVideos > 0 && (
            <div
              style={{ width: `${(inReviewCount / totalAllVideos) * 100}%` }}
              className="bg-status-warning h-full transition-all"
              title={`In review: ${inReviewCount}`}
            />
          )}
          {inRevisionCount > 0 && totalAllVideos > 0 && (
            <div
              style={{ width: `${(inRevisionCount / totalAllVideos) * 100}%` }}
              className="bg-status-critical h-full transition-all"
              title={`In revision: ${inRevisionCount}`}
            />
          )}
        </div>

        {/* Stage counts */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1 text-xs">
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-brand shrink-0" />
            <span className="text-ink-secondary">In edit:</span>
            <strong className="text-ink-primary tabular-nums">{inEditCount}</strong>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-status-warning shrink-0" />
            <span className="text-ink-secondary">In review:</span>
            <strong className="text-ink-primary tabular-nums">{inReviewCount}</strong>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-status-critical shrink-0" />
            <span className="text-ink-secondary">In revision:</span>
            <strong className="text-ink-primary tabular-nums">{inRevisionCount}</strong>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-status-success shrink-0" />
            <span className="text-ink-secondary">Delivered:</span>
            <strong className="text-ink-primary tabular-nums">{deliveredCount}</strong>
          </div>
        </div>
      </section>

      {/* 3. FILTER & SEARCH CONTROLS */}
      <div className="flex flex-col sm:flex-row gap-3 items-stretch sm:items-center justify-between">
        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 no-scrollbar -mx-4 px-4 sm:mx-0 sm:px-0 flex-nowrap sm:flex-wrap">
          {[
            ["active_wip", `Active WIP (${activeWork.length})`],
            ["needs_attention", `Needs attention (${privacyVideos.length + inRevisionCount})`],
            ["privacy_alerts", `Privacy alerts (${privacyVideos.length})`],
            ["in_revision", `In revision (${inRevisionCount})`],
            ["in_review", `In review (${inReviewCount})`],
            ["in_edit", `In edit (${inEditCount})`],
            ["delivered", `Delivered (${deliveredCount})`],
            ["no_booking", `No shoot booking (${missingBookingCount})`],
            ["all", `All videos (${allVideos.length})`],
          ].map(([key, label]) => (
            <button
              key={key}
              onClick={() => setSelectedFilter(key)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors cursor-pointer shrink-0 whitespace-nowrap ${
                selectedFilter === key
                  ? key === "privacy_alerts" || key === "needs_attention"
                    ? "bg-status-critical text-white shadow-xs"
                    : "bg-brand text-white shadow-xs"
                  : "bg-surface text-ink-secondary hover:text-ink-primary border border-border hover:bg-surface-muted"
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        <div className="relative max-w-xs w-full">
          <Search className="w-4 h-4 text-ink-muted absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search video, client, editor..."
            className="w-full pl-9 pr-8 py-1.5 bg-surface border border-border rounded-lg text-xs sm:text-sm text-ink-primary placeholder:text-ink-muted focus:outline-none focus:border-brand"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery("")}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-ink-muted hover:text-ink-primary p-0.5 cursor-pointer"
              aria-label="Clear search"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* 4. VIDEO LIST: NATURAL PAGE SCROLL (NO NESTED SCROLL BOX TRAP!) */}
      {displayedVideos.length === 0 ? (
        <EmptyState
          title={searchQuery ? "No matching videos found" : "No videos in this filter"}
          description={
            searchQuery
              ? `No videos match "${searchQuery}".`
              : "There are currently no video records matching this filter."
          }
          action={
            searchQuery ? (
              <button
                onClick={() => setSearchQuery("")}
                className="px-4 py-2 text-xs sm:text-sm font-medium text-brand hover:underline cursor-pointer"
              >
                Clear search filter
              </button>
            ) : undefined
          }
        />
      ) : (
        <>
          {/* DESKTOP TABLE */}
          <div className="hidden md:block bg-surface border border-border rounded-xl shadow-xs overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
              <thead className="bg-surface-muted/50 border-b border-border text-ink-secondary text-xs font-semibold uppercase tracking-wider">
                <tr>
                  <th className="py-3 px-4">Video ID</th>
                  <th className="py-3 px-4">Title</th>
                  <th className="py-3 px-4">Client</th>
                  <th className="py-3 px-4">Editor</th>
                  <th className="py-3 px-4 text-center">Stage</th>
                  <th className="py-3 px-4 text-center">Revs / Hrs</th>
                  <th className="py-3 px-4">Board Notes & Alerts</th>
                  <th className="py-3 px-3 text-right"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {displayedVideos.map((v) => {
                  const hasMultipleRevisions = (v.revisions || 0) >= 2;
                  const isPrivacyCritical = v.has_privacy_alert && v.privacy_board_missing;

                  return (
                    <tr
                      key={v.video_id}
                      onClick={() => setSelectedVideo(v)}
                      className={`hover:bg-surface-muted/40 transition-colors cursor-pointer ${
                        isPrivacyCritical
                          ? "bg-status-critical-bg/30"
                          : v.has_privacy_alert
                          ? "bg-status-warning-bg/15"
                          : hasMultipleRevisions
                          ? "bg-status-warning-bg/10"
                          : ""
                      }`}
                    >
                      <td className="py-3 px-4 font-mono text-xs font-semibold text-ink-secondary">
                        {v.video_id}
                      </td>
                      <td className="py-3 px-4 font-medium text-ink-primary">
                        <div>{v.title || "Untitled Project"}</div>
                        <div className="text-xs text-ink-muted">
                          {v.client_approved_on
                            ? `Approved: ${formatDate(v.client_approved_on)}`
                            : v.shoot_booking
                            ? `Shoot booking: ${v.shoot_booking}`
                            : "No shoot booking link"}
                        </div>
                      </td>
                      <td className="py-3 px-4 text-ink-secondary">
                        {v.client_name || v.client || "Unassigned"}
                      </td>
                      <td className="py-3 px-4 text-ink-primary">
                        {v.editor || <span className="text-ink-muted italic">Unassigned</span>}
                      </td>
                      <td className="py-3 px-4 text-center">
                        <StatusBadge label={v.stage || "Unknown"} variant={getStageVariant(v.stage)} />
                      </td>
                      <td className="py-3 px-4 text-center tabular-nums text-xs">
                        <span
                          className={`inline-block px-2 py-0.5 rounded-full font-medium ${
                            hasMultipleRevisions
                              ? "bg-status-warning-bg text-status-warning border border-status-warning-border"
                              : "text-ink-secondary"
                          }`}
                        >
                          {v.revisions ?? 0} rev • {v.editor_hours ?? 0}h
                        </span>
                      </td>
                      <td className="py-3 px-4 text-xs">
                        <div className="flex flex-wrap items-center gap-1.5">
                          {v.has_privacy_alert && (
                            <StatusBadge
                              label={
                                v.privacy_board_missing
                                  ? "PRIVACY NOTE MISSING!"
                                  : "Blur Face (Logged)"
                              }
                              variant={v.privacy_board_missing ? "critical" : "warning"}
                            />
                          )}
                          {v.has_unresolved_complaint && (
                            <StatusBadge label="Client Complaint" variant="critical" />
                          )}
                          {v.notes_on_board ? (
                            <span className="text-ink-secondary truncate max-w-xs block">
                              {v.notes_on_board}
                            </span>
                          ) : (
                            <span className="text-ink-muted italic">No board notes</span>
                          )}
                        </div>
                      </td>
                      <td className="py-3 px-3 text-right">
                        <span className="text-xs text-brand hover:underline font-medium">
                          Details
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            </div>
          </div>

          {/* MOBILE STACKED CARDS */}
          <div className="md:hidden space-y-3">
            {displayedVideos.map((v) => {
              const hasMultipleRevisions = (v.revisions || 0) >= 2;
              const isPrivacyCritical = v.has_privacy_alert && v.privacy_board_missing;

              return (
                <div
                  key={v.video_id}
                  onClick={() => setSelectedVideo(v)}
                  className={`p-4 bg-surface border rounded-xl shadow-xs space-y-2.5 cursor-pointer active:bg-surface-muted transition-colors ${
                    isPrivacyCritical
                      ? "border-status-critical bg-status-critical-bg/20"
                      : v.has_privacy_alert
                      ? "border-status-warning bg-status-warning-bg/10"
                      : "border-border"
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="space-y-0.5 min-w-0 flex-1">
                      <span className="font-mono text-xs text-ink-muted">{v.video_id}</span>
                      <h3 className="font-semibold text-sm text-ink-primary truncate">
                        {v.title || "Untitled Project"}
                      </h3>
                      <p className="text-xs text-ink-secondary truncate">
                        {v.client_name || v.client || "Unassigned"}
                      </p>
                    </div>
                    <StatusBadge label={v.stage || "Unknown"} variant={getStageVariant(v.stage)} />
                  </div>

                  {(v.has_privacy_alert || v.notes_on_board) && (
                    <div className="text-xs space-y-1">
                      {v.has_privacy_alert && (
                        <StatusBadge
                          label={
                            v.privacy_board_missing
                              ? "PRIVACY NOTE MISSING!"
                              : "Blur Face (Logged)"
                          }
                          variant={v.privacy_board_missing ? "critical" : "warning"}
                        />
                      )}
                      {v.notes_on_board && (
                        <p className="text-ink-secondary">{v.notes_on_board}</p>
                      )}
                    </div>
                  )}

                  <div className="flex items-center justify-between text-xs pt-2 border-t border-border/60 text-ink-secondary">
                    <span className="inline-flex items-center gap-1.5 font-medium text-ink-primary">
                      <User className="w-3.5 h-3.5 text-ink-muted" />
                      <span>{v.editor || "Unassigned"}</span>
                    </span>
                    <span
                      className={`font-medium ${
                        hasMultipleRevisions ? "text-status-warning font-semibold" : ""
                      }`}
                    >
                      {v.revisions ?? 0} rev • {v.editor_hours ?? 0}h
                    </span>
                  </div>
                </div>
              );
            })}
          </div>

          {/* NATURAL PAGINATION / "SHOW MORE" BUTTON */}
          {visibleCount < filteredVideos.length && (
            <div className="text-center pt-2">
              <button
                type="button"
                onClick={() => setVisibleCount((prev) => prev + PAGE_SIZE)}
                className="inline-flex items-center gap-2 px-5 py-2.5 bg-surface border border-border hover:bg-surface-muted text-ink-primary text-xs sm:text-sm font-medium rounded-lg transition-colors cursor-pointer shadow-xs"
              >
                <span>
                  Show more videos ({displayedVideos.length} of {filteredVideos.length})
                </span>
                <ChevronDown className="w-4 h-4" />
              </button>
            </div>
          )}
        </>
      )}

      {/* 5. COLLAPSIBLE TEAM WORKLOAD & DIRECT COSTS SECTION */}
      {editors.length > 0 && (
        <section className="pt-2 border-t border-border space-y-3" aria-label="Team workload">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-sm font-semibold text-ink-primary">
                Team workload & direct production costs
              </h2>
              <p className="text-xs text-ink-secondary">
                Direct labor and studio hourly rates from <code className="font-mono">team.csv</code> and <code className="font-mono">costs.csv</code> (excludes company overhead).
              </p>
            </div>
            <button
              type="button"
              onClick={() => setShowWorkload((prev) => !prev)}
              className="inline-flex items-center gap-1 text-xs font-medium text-brand hover:underline cursor-pointer"
            >
              <span>{showWorkload ? "Hide team details" : "View team details"}</span>
              {showWorkload ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
            </button>
          </div>

          {showWorkload && (
            <div className="space-y-3 animate-in fade-in duration-150">
              <div className="p-3 bg-surface-muted/60 rounded-lg border border-border text-xs text-ink-secondary leading-relaxed">
                Total direct editor labor:{" "}
                <strong className="text-ink-primary">{costSummary?.total_editor_hours ?? 0} hrs</strong> (
                {formatCurrency(costSummary?.total_editor_labor_cost ?? 0)}), plus{" "}
                <strong className="text-ink-primary">{costSummary?.completed_studio_hours ?? 0} completed studio hrs</strong> @ $
                {costSummary?.studio_hourly_rate ?? 0}/hr = {formatCurrency(costSummary?.completed_studio_cost ?? 0)}.
              </div>

              <div className="grid grid-cols-2 lg:grid-cols-4 gap-3.5">
                {editors.map((ed) => (
                  <div
                    key={ed.editor}
                    className="p-3.5 bg-surface border border-border rounded-xl shadow-xs space-y-2"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-sm text-ink-primary">{ed.editor}</span>
                      <span className="text-2xs font-medium px-2 py-0.5 rounded bg-surface-muted text-ink-secondary border border-border">
                        ${ed.hourly_rate ?? 0}/hr
                      </span>
                    </div>
                    <div className="space-y-1 text-xs text-ink-secondary pt-1">
                      <div className="flex justify-between">
                        <span>Videos:</span>
                        <strong className="text-ink-primary tabular-nums">{ed.total_videos}</strong>
                      </div>
                      <div className="flex justify-between">
                        <span>Hours:</span>
                        <strong className="text-ink-primary tabular-nums">{ed.total_hours ?? 0} hrs</strong>
                      </div>
                      <div className="flex justify-between">
                        <span>Revisions:</span>
                        <strong className="text-ink-primary tabular-nums">{ed.total_revisions}</strong>
                      </div>
                      {ed.labor_cost !== undefined && (
                        <div className="flex justify-between pt-1 border-t border-border">
                          <span>Labor cost:</span>
                          <strong className="text-ink-primary tabular-nums">{formatCurrency(ed.labor_cost)}</strong>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </section>
      )}

      {/* 6. VIDEO DETAIL MODAL (CLEAN ACCESSIBLE DISCLOSURE) */}
      {selectedVideo && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 backdrop-blur-xs p-4 animate-in fade-in duration-150"
          role="dialog"
          aria-modal="true"
          aria-labelledby="video-detail-title"
        >
          <div className="bg-surface rounded-2xl shadow-2xl w-full max-w-lg border border-border overflow-hidden flex flex-col max-h-[85vh]">
            {/* Modal Header */}
            <div className="flex items-center justify-between px-5 py-4 border-b border-border">
              <div className="flex items-center gap-2.5">
                <span className="font-mono text-xs font-bold text-ink-muted px-2 py-0.5 rounded bg-surface-muted">
                  {selectedVideo.video_id}
                </span>
                <StatusBadge
                  label={selectedVideo.stage || "Unknown"}
                  variant={getStageVariant(selectedVideo.stage)}
                />
              </div>
              <button
                type="button"
                onClick={() => setSelectedVideo(null)}
                className="p-1 rounded-lg text-ink-muted hover:text-ink-primary hover:bg-surface-muted cursor-pointer"
                aria-label="Close video details"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Content */}
            <div className="p-5 space-y-4 overflow-y-auto">
              <div>
                <h3 id="video-detail-title" className="text-lg font-semibold text-ink-primary">
                  {selectedVideo.title || "Untitled Project"}
                </h3>
                <p className="text-xs sm:text-sm text-ink-secondary mt-0.5">
                  Client: <strong className="text-ink-primary">{selectedVideo.client_name || selectedVideo.client || "Unassigned"}</strong>
                </p>
              </div>

              {/* Privacy Warning */}
              {selectedVideo.has_privacy_alert && (
                <div className="p-3.5 bg-status-critical-bg border border-status-critical-border rounded-xl text-xs space-y-1.5 text-status-critical">
                  <div className="flex items-center gap-1.5 font-semibold">
                    <ShieldAlert className="w-4 h-4" />
                    <span>Privacy Release Requirement Unresolved</span>
                  </div>
                  <p className="leading-relaxed">
                    {selectedVideo.privacy_board_missing
                      ? "CRITICAL: Client voice note requested face blur for this video, but the production board note was left blank. Visual verification required before posting!"
                      : "Patient/client in video did not sign a media release. Board has 'Blur client face' note, but visual verification of exported video is required."}
                  </p>
                </div>
              )}

              {/* Video Attributes Grid */}
              <div className="grid grid-cols-2 gap-3 text-xs bg-surface-muted/50 p-3.5 rounded-xl border border-border">
                <div>
                  <span className="text-ink-muted block">Editor:</span>
                  <span className="font-semibold text-ink-primary">{selectedVideo.editor || "Unassigned"}</span>
                </div>
                <div>
                  <span className="text-ink-muted block">Shoot Booking:</span>
                  <span className="font-semibold text-ink-primary">
                    {selectedVideo.shoot_booking || "No linked booking (Separate review)"}
                  </span>
                </div>
                <div>
                  <span className="text-ink-muted block">Revision count:</span>
                  <span className="font-semibold text-ink-primary">{selectedVideo.revisions ?? 0}</span>
                </div>
                <div>
                  <span className="text-ink-muted block">Editor hours logged:</span>
                  <span className="font-semibold text-ink-primary">{selectedVideo.editor_hours ?? 0} hrs</span>
                </div>
                {selectedVideo.client_approved_on && (
                  <div className="col-span-2">
                    <span className="text-ink-muted block">Client approved on:</span>
                    <span className="font-semibold text-ink-primary">{formatDate(selectedVideo.client_approved_on)}</span>
                  </div>
                )}
              </div>

              {/* Board Notes */}
              <div>
                <span className="text-xs font-semibold text-ink-primary block mb-1">Production Board Notes:</span>
                <p className="p-3 bg-surface-muted rounded-lg border border-border text-xs text-ink-secondary leading-relaxed">
                  {selectedVideo.notes_on_board || "No board notes recorded for this video."}
                </p>
              </div>
            </div>

            {/* Modal Footer */}
            <div className="px-5 py-3 border-t border-border flex justify-end bg-surface-muted/30">
              <button
                type="button"
                onClick={() => setSelectedVideo(null)}
                className="px-4 py-2 text-xs font-medium text-ink-secondary hover:text-ink-primary bg-surface border border-border rounded-lg cursor-pointer"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
