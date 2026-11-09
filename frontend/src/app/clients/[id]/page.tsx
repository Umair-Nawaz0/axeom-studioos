"use client";

import React, { useEffect, useState, useMemo, useCallback } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  ArrowLeft,
  Calendar,
  DollarSign,
  Film,
  Inbox,
  MessageSquare,
  CreditCard,
  ChevronDown,
  ChevronUp,
  AlertCircle,
} from "lucide-react";
import {
  api,
  ClientDetail,
  formatCurrency,
  formatDate,
} from "@/lib/api";
import { LoadingState } from "@/components/ui/LoadingState";
import { ErrorState } from "@/components/ui/ErrorState";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { EmptyState } from "@/components/ui/EmptyState";

interface TimelineEvent {
  id: string;
  dateStr: string;
  timestamp: number;
  hasValidDate: boolean;
  type: "lead" | "booking" | "invoice" | "payment" | "video" | "message";
  title: string;
  detail: string;
  sourceFile: string;
  rawDate: string;
}

export default function ClientDetailPage() {
  const params = useParams();
  const clientId = params?.id as string;

  const [detail, setDetail] = useState<ClientDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"activity" | "bookings" | "production" | "money" | "messages">("activity");
  const [expandedMessages, setExpandedMessages] = useState<Record<string, boolean>>({});

  const fetchDetail = useCallback(async () => {
    if (!clientId) return;
    try {
      setLoading(true);
      setError(null);
      const res = await api.getClientDetail(clientId);
      setDetail(res);
    } catch (err: any) {
      setError(err.message || "Failed to load client details.");
    } finally {
      setLoading(false);
    }
  }, [clientId]);

  useEffect(() => {
    fetchDetail();

    const handleDataRefreshed = () => {
      fetchDetail();
    };
    window.addEventListener("axeom:data-refreshed", handleDataRefreshed);
    window.addEventListener("axeom:reference-date-changed", handleDataRefreshed);

    return () => {
      window.removeEventListener("axeom:data-refreshed", handleDataRefreshed);
      window.removeEventListener("axeom:reference-date-changed", handleDataRefreshed);
    };
  }, [fetchDetail]);

  const toggleMessageExpand = (id: string) => {
    setExpandedMessages((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const parseTimestamp = (dStr: string | null | undefined): { ts: number; valid: boolean } => {
    if (!dStr) return { ts: 0, valid: false };
    const clean = dStr.split("T")[0].split(" ")[0];
    const parts = clean.split("-");
    if (parts.length === 3) {
      const y = parseInt(parts[0], 10);
      const m = parseInt(parts[1], 10) - 1;
      const d = parseInt(parts[2], 10);
      const dateObj = new Date(y, m, d);
      if (!isNaN(dateObj.getTime())) {
        return { ts: dateObj.getTime(), valid: true };
      }
    }
    return { ts: 0, valid: false };
  };

  // Build unified chronological activity timeline
  const timelineEvents: TimelineEvent[] = useMemo(() => {
    if (!detail) return [];
    const events: TimelineEvent[] = [];

    (detail.leads || []).forEach((l) => {
      const { ts, valid } = parseTimestamp(l.created);
      events.push({
        id: `lead-${l.lead_id || l.id}`,
        dateStr: formatDate(l.created),
        timestamp: ts,
        hasValidDate: valid,
        type: "lead",
        title: `Lead Inquiry (${l.source || "Website"})`,
        detail: `Contact: ${l.name || "Unknown"} • Status: ${l.status || "Open"}${l.email ? ` • ${l.email}` : ""}${l.phone ? ` • ${l.phone}` : ""}`,
        sourceFile: "leads.csv",
        rawDate: l.created || "",
      });
    });

    (detail.bookings || []).forEach((b) => {
      const { ts, valid } = parseTimestamp(b.date);
      events.push({
        id: `booking-${b.booking_id || b.id}`,
        dateStr: formatDate(b.date),
        timestamp: ts,
        hasValidDate: valid,
        type: "booking",
        title: `Booking: ${b.service}`,
        detail: `${formatCurrency(b.price)} • Status: ${b.status}`,
        sourceFile: "bookings.csv",
        rawDate: b.date || "",
      });
    });

    (detail.invoices || []).forEach((inv) => {
      const { ts, valid } = parseTimestamp(inv.issued);
      events.push({
        id: `inv-${inv.invoice_no || inv.id}`,
        dateStr: formatDate(inv.issued),
        timestamp: ts,
        hasValidDate: valid,
        type: "invoice",
        title: `Invoice ${inv.invoice_no}`,
        detail: `${formatCurrency(inv.amount)} • Status: ${inv.status} • Due: ${formatDate(inv.due)}${inv.memo ? ` (${inv.memo})` : ""}`,
        sourceFile: "invoices.csv",
        rawDate: inv.issued || "",
      });
    });

    (detail.payments || []).forEach((p) => {
      const { ts, valid } = parseTimestamp(p.payment_date);
      events.push({
        id: `pay-${p.payment_id || p.id}`,
        dateStr: formatDate(p.payment_date),
        timestamp: ts,
        hasValidDate: valid,
        type: "payment",
        title: `Linked Bank Deposit ${p.payment_id}`,
        detail: `${formatCurrency(p.amount)} received${p.payer_name ? ` from ${p.payer_name}` : ""}${p.reference ? ` • Ref: ${p.reference}` : ""}${p.matched_invoice_no ? ` • Matched: ${p.matched_invoice_no}` : ""}`,
        sourceFile: "payments.csv",
        rawDate: p.payment_date || "",
      });
    });

    (detail.production_videos || []).forEach((v) => {
      const dStr = v.approved_date || null;
      const { ts, valid } = parseTimestamp(dStr);
      events.push({
        id: `vid-${v.video_id || v.id}`,
        dateStr: dStr ? formatDate(dStr) : "Date not recorded",
        timestamp: ts,
        hasValidDate: valid,
        type: "video",
        title: `Video: ${v.title}`,
        detail: `Stage: ${v.stage} • Editor: ${v.editor || "Unassigned"} • Revisions: ${v.revisions} • Hours: ${v.editor_hours || 0}`,
        sourceFile: "production_board.csv",
        rawDate: dStr || "",
      });
    });

    (detail.messages || []).forEach((m) => {
      const dStr = m.message_date || m.timestamp || null;
      const { ts, valid } = parseTimestamp(dStr);
      events.push({
        id: `msg-${m.id}`,
        dateStr: formatDate(dStr),
        timestamp: ts,
        hasValidDate: valid,
        type: "message",
        title: `Message (${m.channel}): ${m.sender || "Client"}`,
        detail: m.message_text || m.original_line || "",
        sourceFile: "messages.txt",
        rawDate: dStr || "",
      });
    });

    events.sort((a, b) => {
      if (a.hasValidDate && b.hasValidDate) {
        return b.timestamp - a.timestamp;
      }
      if (a.hasValidDate && !b.hasValidDate) return -1;
      if (!a.hasValidDate && b.hasValidDate) return 1;
      return a.title.localeCompare(b.title);
    });

    return events;
  }, [detail]);

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="h-6 w-32 bg-surface-muted rounded animate-pulse" />
        <LoadingState variant="cards" count={3} message="Loading client 360 profile..." />
      </div>
    );
  }

  if (error || !detail) {
    return (
      <div className="space-y-4">
        <Link
          href="/clients"
          className="inline-flex items-center gap-1.5 text-sm text-ink-secondary hover:text-ink-primary font-medium transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back to clients directory</span>
        </Link>
        <ErrorState
          title="Client not found"
          message={error || "Could not retrieve records for this client ID."}
          onRetry={fetchDetail}
        />
      </div>
    );
  }

  const getEventIcon = (type: TimelineEvent["type"]) => {
    switch (type) {
      case "lead":
        return <Inbox className="w-4 h-4 text-status-info" />;
      case "booking":
        return <Calendar className="w-4 h-4 text-brand" />;
      case "invoice":
        return <DollarSign className="w-4 h-4 text-ink-primary" />;
      case "payment":
        return <CreditCard className="w-4 h-4 text-status-success" />;
      case "video":
        return <Film className="w-4 h-4 text-status-warning" />;
      case "message":
        return <MessageSquare className="w-4 h-4 text-ink-secondary" />;
    }
  };

  const bookingsCount = detail.bookings?.length || 0;
  const videosCount = detail.production_videos?.length || 0;
  const invoicesCount = detail.invoices?.length || 0;
  const paymentsCount = detail.payments?.length || 0;
  const messagesCount = detail.messages?.length || 0;

  return (
    <div className="space-y-6">
      {/* Breadcrumb back link */}
      <nav aria-label="Breadcrumb">
        <Link
          href="/clients"
          className="inline-flex items-center gap-1.5 text-xs sm:text-sm text-ink-secondary hover:text-ink-primary font-medium transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back to clients directory</span>
        </Link>
      </nav>

      {/* Client Overview Card */}
      <div className="p-6 bg-surface border border-border rounded-xl shadow-xs space-y-5">
        <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4 pb-4 border-b border-border">
          <div className="space-y-2">
            <div className="flex items-center gap-3 flex-wrap">
              <h1 className="text-2xl sm:text-3xl font-semibold text-ink-primary tracking-tight">
                {detail.canonical_name}
              </h1>
              <span className="px-2.5 py-0.5 rounded-full text-xs font-medium bg-brand-soft text-brand border border-[#F0D5C9]">
                {detail.entity_type === "payer" ? "Third-Party Payer (Not a Service Client)" : "Canonical Client"}
              </span>
              {detail.pays_for && detail.pays_for.length > 0 && (
                <span className="px-2.5 py-0.5 rounded-full text-xs font-medium bg-surface-muted text-ink-primary border border-border">
                  Pays for: {detail.pays_for.join(", ")}
                </span>
              )}
              {detail.billed_via_payer && (
                <span className="px-2.5 py-0.5 rounded-full text-xs font-medium bg-surface-muted text-ink-primary border border-border">
                  Invoices billed via: {detail.billed_via_payer}
                </span>
              )}
            </div>

            {detail.aliases && detail.aliases.length > 0 && (
              <div className="flex items-center gap-2 flex-wrap text-xs text-ink-secondary">
                <span className="font-medium text-ink-primary">Known aliases:</span>
                {detail.aliases.map((alias, idx) => (
                  <span
                    key={idx}
                    className="px-2 py-0.5 bg-surface-muted text-ink-secondary rounded border border-border"
                  >
                    {alias}
                  </span>
                ))}
              </div>
            )}

            {detail.notes && !detail.notes.trim().startsWith("{") && (
              <p className="text-xs text-ink-muted italic pt-0.5">{detail.notes}</p>
            )}

            {detail.alerts && detail.alerts.length > 0 && (
              <div className="pt-2 space-y-2">
                {detail.alerts.slice(0, 3).map((al, i) => (
                  <div
                    key={i}
                    className="p-2.5 rounded-lg bg-status-critical-bg border border-status-critical-border text-xs text-status-critical flex items-start gap-2"
                  >
                    <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                    <div>
                      <span className="font-semibold">{al.title}: </span>
                      <span>{al.detail}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* 5 Compact Summary Metrics */}
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
          <div className="p-3 bg-surface-muted/60 rounded-lg border border-border">
            <span className="text-xs font-medium text-ink-secondary block">Total invoiced</span>
            <div className="text-lg font-semibold text-ink-primary mt-1 tabular-nums">
              {formatCurrency(detail.financial_summary?.total_invoiced)}
            </div>
          </div>
          <div className="p-3 bg-surface-muted/60 rounded-lg border border-border">
            <span className="text-xs font-medium text-ink-secondary block">Bookings</span>
            <div className="text-lg font-semibold text-ink-primary mt-1 tabular-nums">
              {bookingsCount}
            </div>
          </div>
          <div className="p-3 bg-surface-muted/60 rounded-lg border border-border">
            <span className="text-xs font-medium text-ink-secondary block">Videos</span>
            <div className="text-lg font-semibold text-ink-primary mt-1 tabular-nums">
              {videosCount}
            </div>
          </div>
          <div className="p-3 bg-surface-muted/60 rounded-lg border border-border">
            <span className="text-xs font-medium text-ink-secondary block" title="Bank deposits explicitly matched to this client's invoices">
              Linked payments
            </span>
            <div className="text-lg font-semibold text-status-success mt-1 tabular-nums">
              {paymentsCount}
            </div>
          </div>
          <div className="p-3 bg-surface-muted/60 rounded-lg border border-border">
            <span className="text-xs font-medium text-ink-secondary block">Messages</span>
            <div className="text-lg font-semibold text-ink-primary mt-1 tabular-nums">
              {messagesCount}
            </div>
          </div>
        </div>
      </div>

      {/* Evidence-Based Client Health & Retention Status */}
      {detail.health_summary && (
        <div className="p-5 bg-surface border border-border rounded-xl shadow-xs space-y-4">
          <div className="flex items-center justify-between flex-wrap gap-2 pb-3 border-b border-border">
            <div className="flex items-center gap-3">
              <span className="font-semibold text-ink-primary text-base">Client Health & Retention Status</span>
              <StatusBadge
                label={
                  detail.health_summary.health_status === "paused"
                    ? "Paused / reactivation needed"
                    : detail.health_summary.health_status === "critical"
                    ? "Critical Risk"
                    : detail.health_summary.health_status === "at_risk"
                    ? "At Risk"
                    : detail.health_summary.health_status === "monitor"
                    ? "Monitor"
                    : detail.health_summary.health_status === "healthy"
                    ? "Healthy"
                    : "Insufficient Data"
                }
                variant={
                  detail.health_summary.health_status === "critical"
                    ? "critical"
                    : detail.health_summary.health_status === "at_risk"
                    ? "warning"
                    : detail.health_summary.health_status === "monitor"
                    ? "info"
                    : detail.health_summary.health_status === "healthy"
                    ? "success"
                    : "neutral"
                }
              />
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs text-ink-muted">Health Score:</span>
              <span
                className={`text-lg font-bold tabular-nums ${
                  detail.health_summary.health_score < 40
                    ? "text-status-critical"
                    : detail.health_summary.health_score < 70
                    ? "text-status-warning"
                    : "text-status-success"
                }`}
              >
                {detail.health_summary.health_score}/100
              </span>
            </div>
          </div>

          {/* Recommended Next Step */}
          {detail.health_summary.next_step && (
            <div className="p-3 bg-brand-soft/30 border border-[#F0D5C9] rounded-lg text-xs flex items-center justify-between flex-wrap gap-2">
              <span className="text-brand font-medium">Recommended Next Step:</span>
              <span className="text-ink-primary font-semibold">{detail.health_summary.next_step}</span>
            </div>
          )}

          {/* Contributing Factors */}
          {detail.health_summary.contributing_factors && detail.health_summary.contributing_factors.length > 0 && (
            <div className="space-y-2">
              <span className="text-xs font-semibold text-ink-secondary uppercase tracking-wider block">
                Evidence-Based Contributing Factors:
              </span>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
                {detail.health_summary.contributing_factors.map((cf: any, idx: number) => (
                  <div
                    key={idx}
                    className="p-3 bg-surface-muted/60 border border-border rounded-lg space-y-1"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-ink-primary capitalize">
                        {cf.factor.replace(/_/g, " ")}
                      </span>
                      <span className="font-mono text-xs font-semibold text-status-critical">
                        {cf.weight} pts
                      </span>
                    </div>
                    <p className="text-ink-secondary leading-relaxed">{cf.description}</p>
                    {cf.records && cf.records.length > 0 && (
                      <div className="flex items-center gap-1.5 flex-wrap pt-1 text-[11px] text-ink-muted">
                        <span>Supporting records:</span>
                        {cf.records.map((rec: string) => (
                          <span
                            key={rec}
                            className="font-mono px-1.5 py-0.2 rounded bg-surface border border-border text-ink-primary"
                          >
                            {rec}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Segmented Navigation Tabs */}
      <div className="border-b border-border flex items-center gap-1 sm:gap-2 overflow-x-auto pb-px">
        <button
          type="button"
          onClick={() => setActiveTab("activity")}
          className={`px-4 py-2.5 text-xs sm:text-sm font-medium border-b-2 transition-colors cursor-pointer whitespace-nowrap ${
            activeTab === "activity"
              ? "border-brand text-brand font-semibold"
              : "border-transparent text-ink-secondary hover:text-ink-primary hover:border-border"
          }`}
        >
          Activity timeline ({timelineEvents.length})
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("bookings")}
          className={`px-4 py-2.5 text-xs sm:text-sm font-medium border-b-2 transition-colors cursor-pointer whitespace-nowrap ${
            activeTab === "bookings"
              ? "border-brand text-brand font-semibold"
              : "border-transparent text-ink-secondary hover:text-ink-primary hover:border-border"
          }`}
        >
          Bookings ({bookingsCount})
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("production")}
          className={`px-4 py-2.5 text-xs sm:text-sm font-medium border-b-2 transition-colors cursor-pointer whitespace-nowrap ${
            activeTab === "production"
              ? "border-brand text-brand font-semibold"
              : "border-transparent text-ink-secondary hover:text-ink-primary hover:border-border"
          }`}
        >
          Production ({videosCount})
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("money")}
          className={`px-4 py-2.5 text-xs sm:text-sm font-medium border-b-2 transition-colors cursor-pointer whitespace-nowrap ${
            activeTab === "money"
              ? "border-brand text-brand font-semibold"
              : "border-transparent text-ink-secondary hover:text-ink-primary hover:border-border"
          }`}
        >
          Money ({invoicesCount} inv, {paymentsCount} pay)
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("messages")}
          className={`px-4 py-2.5 text-xs sm:text-sm font-medium border-b-2 transition-colors cursor-pointer whitespace-nowrap ${
            activeTab === "messages"
              ? "border-brand text-brand font-semibold"
              : "border-transparent text-ink-secondary hover:text-ink-primary hover:border-border"
          }`}
        >
          Messages ({messagesCount})
        </button>
      </div>

      {/* TAB CONTENT 1: ACTIVITY TIMELINE */}
      {activeTab === "activity" && (
        <div className="space-y-3">
          {timelineEvents.length === 0 ? (
            <EmptyState title="No activity recorded" description="No timeline events found for this client." />
          ) : (
            timelineEvents.map((evt) => {
              const isMsg = evt.type === "message";
              const isLong = evt.detail.length > 180;
              const isExpanded = expandedMessages[evt.id];

              return (
                <div
                  key={evt.id}
                  className="p-4 sm:p-5 bg-surface border border-border rounded-xl shadow-xs space-y-2 hover:border-border-subtle transition-all"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-center gap-2.5 flex-wrap">
                      <div className="w-7 h-7 rounded-lg bg-surface-muted flex items-center justify-center shrink-0">
                        {getEventIcon(evt.type)}
                      </div>
                      <h3 className="font-semibold text-sm sm:text-base text-ink-primary">
                        {evt.title}
                      </h3>
                    </div>

                    <div className="text-right shrink-0">
                      <span className="text-xs font-medium text-ink-secondary block tabular-nums">
                        {evt.dateStr}
                      </span>
                      <span className="text-xs text-ink-muted block">
                        {evt.sourceFile}
                      </span>
                    </div>
                  </div>

                  <div className="text-xs sm:text-sm text-ink-secondary leading-relaxed pl-9">
                    {isMsg && isLong && !isExpanded ? (
                      <div>
                        <p>{evt.detail.slice(0, 180)}...</p>
                        <button
                          type="button"
                          onClick={() => toggleMessageExpand(evt.id)}
                          className="text-xs text-brand hover:underline font-medium mt-1 inline-flex items-center gap-1 cursor-pointer"
                        >
                          <span>Show full message</span>
                          <ChevronDown className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    ) : isMsg && isLong && isExpanded ? (
                      <div>
                        <p className="whitespace-pre-wrap">{evt.detail}</p>
                        <button
                          type="button"
                          onClick={() => toggleMessageExpand(evt.id)}
                          className="text-xs text-brand hover:underline font-medium mt-1 inline-flex items-center gap-1 cursor-pointer"
                        >
                          <span>Collapse message</span>
                          <ChevronUp className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    ) : (
                      <p className="whitespace-pre-wrap">{evt.detail}</p>
                    )}
                  </div>
                </div>
              );
            })
          )}
        </div>
      )}

      {/* TAB CONTENT 2: BOOKINGS */}
      {activeTab === "bookings" && (
        <div className="space-y-3">
          {bookingsCount === 0 ? (
            <EmptyState title="No bookings recorded" description="This client has no session bookings in bookings.csv." />
          ) : (
            <div className="bg-surface border border-border rounded-xl shadow-xs overflow-hidden">
              <div className="divide-y divide-border">
                {detail.bookings.map((b) => (
                  <div key={b.booking_id || b.id} className="p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs sm:text-sm">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-ink-primary text-base">{b.service}</span>
                        <span className="text-xs text-ink-muted">({b.booking_id})</span>
                      </div>
                      <p className="text-xs text-ink-secondary mt-0.5">
                        Date: {formatDate(b.date)}{b.location ? ` • Location: ${b.location}` : ""}
                      </p>
                    </div>
                    <div className="flex items-center gap-4 shrink-0">
                      <span className="font-semibold text-ink-primary tabular-nums text-base">
                        {formatCurrency(b.price)}
                      </span>
                      <StatusBadge label={b.status} variant={b.status === "completed" ? "success" : "neutral"} />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* TAB CONTENT 3: PRODUCTION */}
      {activeTab === "production" && (
        <div className="space-y-3">
          {videosCount === 0 ? (
            <EmptyState title="No production videos" description="No videos found on the production board for this client." />
          ) : (
            <div className="bg-surface border border-border rounded-xl shadow-xs overflow-hidden">
              <div className="divide-y divide-border">
                {detail.production_videos.map((v) => (
                  <div key={v.video_id || v.id} className="p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs sm:text-sm">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-ink-primary text-base">{v.title}</span>
                        <span className="text-xs text-ink-muted font-mono">({v.video_id})</span>
                      </div>
                      <p className="text-xs text-ink-secondary mt-0.5">
                        Editor: {v.editor || "Unassigned"} • Revisions: {v.revisions} • Hours: {v.editor_hours || 0}
                        {v.approved_date ? ` • Approved: ${formatDate(v.approved_date)}` : ""}
                      </p>
                    </div>
                    <div className="shrink-0">
                      <StatusBadge
                        label={v.stage}
                        variant={v.stage === "Delivered" ? "success" : v.stage === "In revision" ? "warning" : "info"}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* TAB CONTENT 4: MONEY (INVOICES & LINKED PAYMENTS CLEARLY SEPARATED) */}
      {activeTab === "money" && (
        <div className="space-y-6">
          {/* Invoices Sub-Section */}
          <div className="space-y-3">
            <h3 className="text-sm font-semibold text-ink-primary uppercase tracking-wider">
              Invoices ({invoicesCount})
            </h3>
            {invoicesCount === 0 ? (
              <p className="text-xs text-ink-muted p-4 bg-surface rounded-xl border border-border">No invoices issued to this client.</p>
            ) : (
              <div className="bg-surface border border-border rounded-xl shadow-xs divide-y divide-border overflow-hidden">
                {detail.invoices.map((inv) => (
                  <div key={inv.invoice_no || inv.id} className="p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs sm:text-sm">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-ink-primary text-base">Invoice {inv.invoice_no}</span>
                        {inv.memo && <span className="text-xs text-ink-muted">({inv.memo})</span>}
                      </div>
                      <p className="text-xs text-ink-secondary mt-0.5">
                        Issued: {formatDate(inv.issued)} • Due: {formatDate(inv.due)}{inv.bill_to ? ` • Bill to: ${inv.bill_to}` : ""}
                      </p>
                    </div>
                    <div className="flex items-center gap-4 shrink-0">
                      <span className="font-semibold text-ink-primary tabular-nums text-base">
                        {formatCurrency(inv.amount)}
                      </span>
                      <StatusBadge
                        label={inv.status}
                        variant={inv.status === "paid" ? "success" : inv.status === "unpaid" ? "critical" : "neutral"}
                      />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Linked Payments Sub-Section */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-ink-primary uppercase tracking-wider">
                Linked Bank Deposits ({paymentsCount})
              </h3>
              <span className="text-xs text-ink-muted">
                Matched via invoice memo references
              </span>
            </div>

            {paymentsCount === 0 ? (
              <div className="p-4 bg-surface rounded-xl border border-border space-y-1">
                <p className="text-xs text-ink-secondary">No bank deposits explicitly linked to this client&apos;s invoice numbers.</p>
                <p className="text-xs text-ink-muted">Unmatched cash receipts are tracked in studio-wide bank reconciliation.</p>
              </div>
            ) : (
              <div className="bg-surface border border-border rounded-xl shadow-xs divide-y divide-border overflow-hidden">
                {detail.payments.map((p) => (
                  <div key={p.payment_id || p.id} className="p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs sm:text-sm">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-ink-primary text-base">Deposit {p.payment_id}</span>
                        {p.matched_invoice_no && (
                          <span className="px-2 py-0.5 rounded text-xs bg-status-success-bg text-status-success font-medium">
                            Matched {p.matched_invoice_no}
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-ink-secondary mt-0.5">
                        Date: {formatDate(p.payment_date)}{p.payer_name ? ` • Payer: ${p.payer_name}` : ""}{p.reference ? ` • Ref: ${p.reference}` : ""}
                      </p>
                    </div>
                    <span className="font-semibold text-status-success tabular-nums text-base shrink-0">
                      {formatCurrency(p.amount)}
                    </span>
                  </div>
                ))}
              </div>
            )}

            <div className="p-3 bg-surface-muted rounded-lg text-xs text-ink-muted flex items-start gap-2">
              <AlertCircle className="w-4 h-4 text-ink-muted shrink-0 mt-0.5" />
              <span>
                Note: Payments shown here represent cleared transactions in payments.csv matched directly to this client&apos;s invoices. Deposits without an invoice reference remain in studio-wide money reconciliation.
              </span>
            </div>
          </div>
        </div>
      )}

      {/* TAB CONTENT 5: MESSAGES */}
      {activeTab === "messages" && (
        <div className="space-y-3">
          {messagesCount === 0 ? (
            <EmptyState title="No messages recorded" description="No customer communications found for this client in messages.txt." />
          ) : (
            <div className="space-y-3">
              {detail.messages.map((m) => (
                <div key={m.id} className="p-4 bg-surface border border-border rounded-xl shadow-xs space-y-2">
                  <div className="flex items-center justify-between text-xs text-ink-muted">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-ink-primary">{m.sender || "Client"}</span>
                      <span className="px-2 py-0.5 rounded bg-surface-muted text-ink-secondary">{m.channel}</span>
                    </div>
                    <span className="tabular-nums">{formatDate(m.message_date || m.timestamp)}</span>
                  </div>
                  <p className="text-xs sm:text-sm text-ink-secondary leading-relaxed whitespace-pre-wrap">
                    {m.message_text || m.original_line}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
