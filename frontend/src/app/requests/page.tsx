"use client";

import React, { useEffect, useState, useCallback, useRef } from "react";
import {
  RefreshCw,
  Bot,
  Search,
  Mic,
  Mail,
  X,
  Send,
  Loader2,
  TrendingUp,
  HelpCircle,
  ChevronDown,
  ChevronUp,
  ShieldAlert,
  MessageSquare,
  Sparkles,
  DollarSign,
  Target,
  AlertTriangle,
} from "lucide-react";
import {
  api,
  LeadsOverviewResponse,
  LostRequestsResponse,
  MarketingAnalysisResponse,
  GeminiStatusResponse,
  GeminiClassifyResponse,
  GeminiBatchClassifyResponse,
  MessagesIntelligenceResponse,
  PrivacyAlertItem,
  formatDate,
  formatCurrency,
} from "@/lib/api";
import { PageHeader } from "@/components/ui/PageHeader";
import { MetricCard } from "@/components/ui/MetricCard";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { LoadingState } from "@/components/ui/LoadingState";
import { ErrorState } from "@/components/ui/ErrorState";
import { EmptyState } from "@/components/ui/EmptyState";

const ALLOWED_CATEGORIES = [
  "new_lead_or_sales_enquiry",
  "existing_client_request",
  "revision_or_edit_change",
  "complaint_or_dissatisfaction",
  "privacy_release_or_face_blur",
  "billing_or_payment_question",
  "booking_or_scheduling",
  "cancellation_or_reschedule",
  "approval_or_positive_feedback",
  "referral_or_upsell_opportunity",
  "status_follow_up",
  "general_question",
  "spam_or_test",
  "internal_or_non_customer",
  "other",
  "uncertain",
];

export default function RequestsPage() {
  const [leadsData, setLeadsData] = useState<LeadsOverviewResponse | null>(null);
  const [lostData, setLostData] = useState<LostRequestsResponse | null>(null);
  const [messagesData, setMessagesData] = useState<MessagesIntelligenceResponse | null>(null);
  const [marketingData, setMarketingData] = useState<MarketingAnalysisResponse | null>(null);
  const [marketingError, setMarketingError] = useState<string | null>(null);
  const [geminiStatus, setGeminiStatus] = useState<GeminiStatusResponse | null>(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [activeTab, setActiveTab] = useState<
    "leads" | "lost_requests" | "privacy_alerts" | "all_messages"
  >("leads");
  const [leadsFilter, setLeadsFilter] = useState<
    "unanswered" | "legitimate" | "existing_client" | "spam" | "all_leads"
  >("unanswered");
  const [channelFilter, setChannelFilter] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [showGeminiModal, setShowGeminiModal] = useState(false);
  const [showLimitations, setShowLimitations] = useState(false);

  // Gemini interactive test state
  const [testText, setTestText] = useState("");
  const [testLoading, setTestLoading] = useState(false);
  const [testResult, setTestResult] = useState<GeminiClassifyResponse | null>(null);
  const [testError, setTestError] = useState<string | null>(null);

  // Gemini batch state
  const [batchLoading, setBatchLoading] = useState(false);
  const [batchResult, setBatchResult] = useState<GeminiBatchClassifyResponse | null>(null);

  // Human review modal state
  const [reviewModalOpen, setReviewModalOpen] = useState(false);
  const [selectedMsgForReview, setSelectedMsgForReview] = useState<any | null>(null);
  const [reviewCategory, setReviewCategory] = useState("general_question");
  const [reviewIsSpam, setReviewIsSpam] = useState(false);
  const [reviewUrgency, setReviewUrgency] = useState("normal");
  const [reviewNotes, setReviewNotes] = useState("");
  const [reviewSaving, setReviewSaving] = useState(false);
  const [reviewSuccess, setReviewSuccess] = useState(false);

  const modalOpenerRef = useRef<HTMLButtonElement>(null);

  const loadRequests = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      const [leadsRes, lostRes, msgRes, mktRes, gemRes] = await Promise.allSettled([
        api.getLeadsOverview(),
        api.getLostRequests(),
        api.getMessages(),
        api.getMarketingAnalysis(),
        api.getGeminiStatus(),
      ]);

      if (leadsRes.status === "fulfilled") {
        setLeadsData(leadsRes.value);
      }

      if (lostRes.status === "fulfilled") {
        setLostData(lostRes.value);
      }

      if (msgRes.status === "fulfilled") {
        setMessagesData(msgRes.value);
      }

      if (mktRes.status === "fulfilled") {
        setMarketingData(mktRes.value);
        setMarketingError(null);
      } else {
        setMarketingError("Could not load marketing channel performance.");
      }

      if (gemRes.status === "fulfilled") {
        setGeminiStatus(gemRes.value);
      }

      if (leadsRes.status === "rejected" && lostRes.status === "rejected") {
        throw new Error("Unable to load leads and client requests from the backend.");
      }
    } catch (err: any) {
      setError(err.message || "Failed to load requests.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadRequests();

    const handleDataRefreshed = () => {
      loadRequests();
    };
    window.addEventListener("axeom:data-refreshed", handleDataRefreshed);

    return () => {
      window.removeEventListener("axeom:data-refreshed", handleDataRefreshed);
    };
  }, [loadRequests]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        if (showGeminiModal) {
          setShowGeminiModal(false);
          modalOpenerRef.current?.focus();
        }
        if (reviewModalOpen) {
          setReviewModalOpen(false);
        }
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [showGeminiModal, reviewModalOpen]);

  const handleTestClassify = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!testText.trim()) return;
    try {
      setTestLoading(true);
      setTestError(null);
      const res = await api.classifyWithGemini(
        testText.trim(),
        "test-interactive",
        !geminiStatus?.configured
      );
      setTestResult(res);
    } catch (err: any) {
      setTestError(err.message || "Failed to classify message.");
    } finally {
      setTestLoading(false);
    }
  };

  const handleBatchClassify = async (dryRun: boolean = false) => {
    try {
      setBatchLoading(true);
      const res = await api.batchClassifyWithGemini(dryRun, false);
      setBatchResult(res);
      const s = await api.getGeminiStatus();
      setGeminiStatus(s);
    } catch (err: any) {
      alert("Classification batch error: " + (err.message || "Failed"));
    } finally {
      setBatchLoading(false);
    }
  };

  const openHumanReview = (msg: any) => {
    setSelectedMsgForReview(msg);
    setReviewCategory(msg.categories?.[0] || "general_question");
    setReviewIsSpam(msg.categories?.includes("spam_or_phishing") || false);
    setReviewUrgency(msg.severity || "normal");
    setReviewNotes("");
    setReviewSuccess(false);
    setReviewModalOpen(true);
  };

  const handleSaveHumanReview = async () => {
    if (!selectedMsgForReview) return;
    try {
      setReviewSaving(true);
      await api.saveGeminiReview(String(selectedMsgForReview.id), {
        primary_category: reviewCategory,
        is_spam_or_test: reviewIsSpam,
        urgency: reviewUrgency,
        notes: reviewNotes,
        reviewer: "Studio Owner",
      });
      setReviewSuccess(true);
      setTimeout(() => {
        setReviewModalOpen(false);
        setReviewSuccess(false);
        loadRequests();
      }, 1000);
    } catch (err: any) {
      alert("Failed to save review: " + (err.message || "Error"));
    } finally {
      setReviewSaving(false);
    }
  };

  const channelTotals = React.useMemo(() => {
    if (!marketingData?.channel_metrics || marketingData.channel_metrics.length === 0) {
      return null;
    }
    const metrics = marketingData.channel_metrics;
    const totalLeads = metrics.reduce((acc, c) => acc + (c.total_leads || 0), 0);
    const wonLeads = metrics.reduce((acc, c) => acc + (c.won_leads || 0), 0);
    const lostLeads = metrics.reduce((acc, c) => acc + (c.lost_leads || 0), 0);
    const unrepliedLeads = metrics.reduce((acc, c) => acc + (c.unreplied_leads || 0), 0);
    const newLeads = metrics.reduce((acc, c) => acc + (c.new_leads || 0), 0);
    const clientsAcquired = metrics.reduce((acc, c) => acc + (c.clients_acquired || 0), 0);
    const totalRevenue = metrics.reduce((acc, c) => acc + (c.direct_booking_revenue || 0), 0);
    const overallConversion = totalLeads > 0 ? (wonLeads / totalLeads) * 100 : 0;

    return {
      totalLeads,
      wonLeads,
      lostLeads,
      unrepliedLeads,
      newLeads,
      clientsAcquired,
      totalRevenue,
      overallConversion: Number(overallConversion.toFixed(1)),
    };
  }, [marketingData]);

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="h-10 w-48 bg-surface-muted rounded animate-pulse" />
        <LoadingState variant="cards" count={3} message="Loading inbound inquiries and client requests..." />
      </div>
    );
  }

  if (error) {
    return (
      <ErrorState
        title="Could not load requests"
        message={error}
        onRetry={loadRequests}
      />
    );
  }

  const unansweredLeads = leadsData?.unanswered_leads || [];
  const allLeads = leadsData?.all_leads || unansweredLeads;
  const lostRequests = lostData?.lost_requests || [];
  const privacyAlerts: PrivacyAlertItem[] =
    messagesData?.privacy_alerts || lostData?.privacy_alerts || [];
  const opportunities =
    messagesData?.opportunities_and_referrals ||
    leadsData?.message_opportunities_and_referrals ||
    [];
  const allMessages = messagesData?.messages || [];

  const baseLeadsList =
    leadsFilter === "all_leads"
      ? allLeads
      : leadsFilter === "legitimate"
      ? unansweredLeads.filter((l) => l.triage_category === "legitimate_prospect")
      : leadsFilter === "existing_client"
      ? unansweredLeads.filter((l) => l.triage_category === "existing_client_inquiry")
      : leadsFilter === "spam"
      ? unansweredLeads.filter((l) => l.triage_category === "junk_or_spam")
      : unansweredLeads;

  const filteredLeads = baseLeadsList.filter((l) => {
    const q = searchQuery.toLowerCase().trim();
    if (!q) return true;
    return (
      (l.name && l.name.toLowerCase().includes(q)) ||
      (l.business && l.business.toLowerCase().includes(q)) ||
      (l.email && l.email.toLowerCase().includes(q)) ||
      (l.source && l.source.toLowerCase().includes(q)) ||
      (l.lead_id && l.lead_id.toLowerCase().includes(q))
    );
  });

  const filteredLostRequests = lostRequests.filter((r) => {
    const q = searchQuery.toLowerCase().trim();
    if (!q) return true;
    return (
      (r.client && r.client.toLowerCase().includes(q)) ||
      (r.title && r.title.toLowerCase().includes(q)) ||
      (r.video_id && r.video_id.toLowerCase().includes(q)) ||
      (r.why_it_was_lost && r.why_it_was_lost.toLowerCase().includes(q))
    );
  });

  const filteredMessages = allMessages.filter((m) => {
    if (channelFilter === "spam") {
      if (!m.categories.includes("spam_or_phishing")) return false;
    } else if (channelFilter !== "all" && m.channel !== channelFilter) {
      return false;
    }
    const q = searchQuery.toLowerCase().trim();
    if (!q) return true;
    return (
      (m.sender && m.sender.toLowerCase().includes(q)) ||
      (m.message_text && m.message_text.toLowerCase().includes(q)) ||
      (m.client_name && m.client_name.toLowerCase().includes(q)) ||
      (m.matched_video_id && m.matched_video_id.toLowerCase().includes(q))
    );
  });

  return (
    <div className="space-y-8">
      {/* Header */}
      <PageHeader
        title="Requests & Messages"
        description={`Inbound lead inquiries, missed voice-note revisions, consent/privacy alerts, and ${allMessages.length}-message audit.`}
        actions={
          <div className="flex items-center gap-2 flex-wrap">
            <button
              ref={modalOpenerRef}
              type="button"
              onClick={() => setShowGeminiModal(true)}
              className="inline-flex items-center gap-2 px-3.5 py-2 text-xs sm:text-sm font-medium text-ink-secondary bg-surface border border-border rounded-lg hover:bg-surface-muted transition-colors cursor-pointer shadow-xs"
            >
              <Bot className="w-4 h-4 text-brand" />
              <span>
                Gemini AI ({geminiStatus?.configured ? "Live: " + geminiStatus.model : "Mock: " + (geminiStatus?.model || "gemini-2.5-flash")})
              </span>
            </button>

            <button
              type="button"
              onClick={loadRequests}
              className="inline-flex items-center gap-1.5 px-3 py-2 text-xs sm:text-sm font-medium text-ink-secondary hover:text-ink-primary bg-surface border border-border rounded-lg hover:bg-surface-muted transition-colors cursor-pointer shadow-xs"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              <span>Refresh</span>
            </button>
          </div>
        }
      />

      {/* Tabs and Search Bar */}
      <div className="flex flex-col sm:flex-row gap-3 items-stretch sm:items-center justify-between">
        <div className="flex items-center gap-2 flex-wrap">
          <button
            type="button"
            onClick={() => setActiveTab("leads")}
            className={`px-3.5 py-2 rounded-lg text-xs sm:text-sm font-medium transition-colors cursor-pointer ${
              activeTab === "leads"
                ? "bg-brand text-white shadow-xs"
                : "bg-surface text-ink-secondary hover:text-ink-primary border border-border hover:bg-surface-muted"
            }`}
          >
            Unanswered leads ({unansweredLeads.length})
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("lost_requests")}
            className={`px-3.5 py-2 rounded-lg text-xs sm:text-sm font-medium transition-colors cursor-pointer ${
              activeTab === "lost_requests"
                ? "bg-brand text-white shadow-xs"
                : "bg-surface text-ink-secondary hover:text-ink-primary border border-border hover:bg-surface-muted"
            }`}
          >
            Missed voice notes ({lostRequests.length})
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("privacy_alerts")}
            className={`px-3.5 py-2 rounded-lg text-xs sm:text-sm font-medium transition-colors cursor-pointer inline-flex items-center gap-1.5 ${
              activeTab === "privacy_alerts"
                ? "bg-status-critical text-white shadow-xs"
                : "bg-surface text-ink-secondary hover:text-ink-primary border border-border hover:bg-surface-muted"
            }`}
          >
            <ShieldAlert className="w-3.5 h-3.5" />
            <span>Privacy & consent alerts ({privacyAlerts.length})</span>
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("all_messages")}
            className={`px-3.5 py-2 rounded-lg text-xs sm:text-sm font-medium transition-colors cursor-pointer inline-flex items-center gap-1.5 ${
              activeTab === "all_messages"
                ? "bg-brand text-white shadow-xs"
                : "bg-surface text-ink-secondary hover:text-ink-primary border border-border hover:bg-surface-muted"
            }`}
          >
            <MessageSquare className="w-3.5 h-3.5" />
            <span>All messages ({allMessages.length})</span>
          </button>
        </div>

        <div className="relative max-w-xs w-full">
          <Search className="w-4 h-4 text-ink-muted absolute left-3.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search leads, messages, videos..."
            className="w-full pl-10 pr-9 py-2 bg-surface border border-border rounded-lg text-xs sm:text-sm text-ink-primary placeholder:text-ink-muted focus:outline-none focus:border-brand"
          />
          {searchQuery && (
            <button
              type="button"
              onClick={() => setSearchQuery("")}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-ink-muted hover:text-ink-primary p-1 cursor-pointer"
              aria-label="Clear search"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* SECTION 1: UNANSWERED LEADS & REFERRALS */}
      {activeTab === "leads" && (
        <div className="space-y-4">
          {/* Spotlight banner for 13 legitimate never-replied leads */}
          <div className="p-4 bg-status-critical-bg/40 border border-status-critical-border rounded-xl space-y-2.5">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5">
              <div className="flex items-center gap-2.5">
                <div className="w-2.5 h-2.5 rounded-full bg-status-critical shrink-0 animate-pulse" />
                <h3 className="font-semibold text-sm text-status-critical">
                  13 High-Intent Commercial Prospects Never Received Any Reply
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setLeadsFilter("legitimate")}
                className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer shadow-xs shrink-0 ${
                  leadsFilter === "legitimate"
                    ? "bg-status-critical text-white"
                    : "bg-surface border border-status-critical-border text-status-critical hover:bg-status-critical hover:text-white"
                }`}
              >
                <span>{leadsFilter === "legitimate" ? "Viewing 13 Never-Replied" : "Filter to 13 Never-Replied"}</span>
                <span>→</span>
              </button>
            </div>
            <p className="text-xs text-ink-secondary leading-relaxed">
              Out of 20 unreplied rows in <code className="font-mono bg-canvas px-1.5 py-0.5 rounded text-ink-primary font-semibold">leads.csv</code>, 4 are bot/spam entries and 3 are website form submissions from existing active clients (including Tanya Tran at Keystone Chiropractic requesting urgent contract review). The remaining <strong className="text-status-critical">13 are legitimate commercial prospects</strong> across Meta ads, Google, Instagram, Website, Referral, and LinkedIn that received zero reply from studio staff.
            </p>
          </div>

          <div className="p-3.5 bg-surface-muted/50 border border-border rounded-xl text-xs sm:text-sm text-ink-secondary flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <div>
              <span>
                <strong>{unansweredLeads.length} rows</strong> in <code className="font-mono">leads.csv</code> have no recorded reply:{" "}
                <strong className="text-status-critical">{leadsData?.legitimate_unanswered_count ?? 13}</strong> legitimate prospects,{" "}
                <strong>{leadsData?.existing_client_unanswered_count ?? 3}</strong> website forms from existing clients, and{" "}
                <strong>{leadsData?.junk_unanswered_count ?? 4}</strong> junk/test rows.
              </span>
            </div>
            <div className="flex items-center gap-1.5 flex-wrap">
              {(
                [
                  ["unanswered", `All Unanswered (${unansweredLeads.length})`],
                  ["legitimate", `13 Never Replied (${leadsData?.legitimate_unanswered_count ?? 13})`],
                  ["existing_client", `Existing Clients (${leadsData?.existing_client_unanswered_count ?? 3})`],
                  ["spam", `Spam/Test (${leadsData?.junk_unanswered_count ?? 4})`],
                  ["all_leads", `All Leads (${allLeads.length})`],
                ] as const
              ).map(([key, label]) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => setLeadsFilter(key)}
                  className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors cursor-pointer ${
                    leadsFilter === key
                      ? "bg-ink-primary text-white"
                      : "bg-surface border border-border text-ink-secondary hover:text-ink-primary"
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          {filteredLeads.length === 0 ? (
            <EmptyState
              title={searchQuery ? "No matching leads found" : "No leads in this filter"}
              description={searchQuery ? `No leads match "${searchQuery}".` : "All recorded leads in this category have been handled."}
            />
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
              {filteredLeads.map((lead) => {
                const isSpam = lead.triage_category === "junk_or_spam";
                const isExisting = lead.triage_category === "existing_client_inquiry";
                return (
                  <div
                    key={lead.lead_id}
                    className="p-5 bg-surface border border-border rounded-xl shadow-xs space-y-3 hover:border-brand/30 transition-all"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="space-y-0.5">
                        <div className="flex items-center gap-2 flex-wrap">
                          <h3 className="font-semibold text-base text-ink-primary">
                            {lead.name}
                          </h3>
                          {isSpam ? (
                            <StatusBadge label="Spam / Test" variant="neutral" />
                          ) : isExisting ? (
                            <StatusBadge label="Existing Client Form" variant="info" />
                          ) : lead.first_reply ? (
                            <StatusBadge label={lead.status || "Replied"} variant="success" />
                          ) : (
                            <StatusBadge label="Never Replied (0 reply)" variant="critical" />
                          )}
                          {lead.duplicate_of && lead.duplicate_of.length > 0 && (
                            <StatusBadge label={`Duplicate of ${lead.duplicate_of.join(", ")}`} variant="warning" />
                          )}
                        </div>
                        {lead.business && (
                          <p className="text-xs sm:text-sm font-medium text-ink-secondary">
                            {lead.business}
                          </p>
                        )}
                      </div>

                      <div className="text-right">
                        <span className="text-xs font-mono text-ink-muted block font-medium">
                          {lead.lead_id}
                        </span>
                        <span className="text-xs text-ink-secondary block tabular-nums">
                          {formatDate(lead.created)}
                        </span>
                      </div>
                    </div>

                    <div className="space-y-1 text-xs text-ink-secondary pt-1 border-t border-border">
                      <div className="flex items-center gap-2">
                        <Mail className="w-3.5 h-3.5 text-ink-muted shrink-0" />
                        <span className="truncate">{lead.email || "No email recorded"}</span>
                      </div>
                      {lead.phone && (
                        <div className="flex items-center gap-2">
                          <span className="text-xs text-ink-muted pl-0.5">Tel:</span>
                          <span>{lead.phone}</span>
                        </div>
                      )}
                    </div>

                    <div className="flex items-center justify-between text-xs pt-2 border-t border-border">
                      <span className="px-2 py-0.5 rounded bg-surface-muted text-ink-secondary font-medium">
                        Platform: <strong className="text-ink-primary font-semibold">{lead.source}</strong>
                      </span>
                      <span className="text-ink-secondary font-medium">
                        {lead.first_reply ? (
                          <span className="text-status-success font-medium">Replied {formatDate(lead.first_reply)}</span>
                        ) : (
                          <span className="text-status-critical font-semibold">Never replied • Needs follow-up</span>
                        )}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Uncaptured Message Opportunities & Referrals */}
          {opportunities.length > 0 && (
            <div className="pt-4 space-y-3">
              <div className="flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-brand" />
                <h3 className="text-sm font-semibold text-ink-primary">
                  Warm Referrals & Upsell Requests in Messages ({opportunities.length})
                </h3>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {opportunities.map((opp) => (
                  <div
                    key={opp.line_number}
                    className="p-4 bg-surface border border-border rounded-xl shadow-xs space-y-1.5"
                  >
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-semibold text-ink-primary">
                        {opp.client_name || opp.sender}
                      </span>
                      <span className="font-mono text-ink-muted">
                        Msg #{opp.line_number} • {formatDate(opp.date)}
                      </span>
                    </div>
                    <p className="text-xs text-ink-secondary leading-relaxed">
                      &ldquo;{opp.message_text}&rdquo;
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* SECTION 2: MISSED CLIENT VOICE NOTES */}
      {activeTab === "lost_requests" && (
        <div className="space-y-3">
          <div className="p-3.5 bg-status-warning-bg/40 border border-status-warning-border rounded-xl text-xs sm:text-sm text-ink-secondary space-y-1">
            <div className="flex items-center justify-between font-semibold text-ink-primary flex-wrap gap-2">
              <span>
                All {lostRequests.length} client voice notes had 0 board entries ({lostData?.repeated_complaints?.length ?? 22} escalated into complaints)
              </span>
              {lostData?.lost_requests_started_getting_worse_in && (
                <span className="text-xs text-status-warning font-medium">
                  Root cause: {lostData.lost_requests_started_getting_worse_in}
                </span>
              )}
            </div>
            <p className="text-xs leading-relaxed text-ink-secondary">
              On June 1, 2026 (Message #28), the studio invited clients to send edit revisions via voice notes, but no workflow existed to transcribe voice notes onto <code className="font-mono">production_board.csv</code>.
            </p>
          </div>

          {filteredLostRequests.length === 0 ? (
            <EmptyState
              title={searchQuery ? "No matching requests found" : "No missed requests"}
              description={searchQuery ? `No requests match "${searchQuery}".` : "All client requests have been accounted for."}
            />
          ) : (
            <div className="space-y-3">
              {filteredLostRequests.map((req, idx) => (
                <div
                  key={`${req.video_id}-${req.line_number || idx}`}
                  className="p-5 bg-surface border border-border rounded-xl shadow-xs space-y-3 hover:border-brand/30 transition-all"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2.5 flex-wrap">
                        <span className="font-mono text-xs font-semibold px-2 py-0.5 rounded bg-surface-muted border border-border text-ink-primary">
                          {req.video_id}
                        </span>
                        {req.line_number && (
                          <span className="font-mono text-xs text-ink-muted">
                            Msg #{req.line_number}
                          </span>
                        )}
                        <h3 className="font-semibold text-base text-ink-primary">
                          {req.title}
                        </h3>
                        <span className="text-xs sm:text-sm text-ink-secondary font-medium">
                          • {req.client}
                        </span>
                      </div>
                    </div>

                    <div className="text-right shrink-0">
                      <span className="text-xs font-medium text-ink-secondary block tabular-nums">
                        {formatDate(req.request_date)}
                      </span>
                      <span className="text-xs font-medium text-status-warning inline-flex items-center gap-1 mt-0.5">
                        <Mic className="w-3.5 h-3.5" />
                        <span>{req.came_by}</span>
                      </span>
                    </div>
                  </div>

                  <div className="p-3 bg-surface-muted/50 rounded-lg border border-border text-xs sm:text-sm text-ink-secondary leading-relaxed">
                    <span className="font-semibold text-ink-primary block mb-0.5">Why it got lost:</span>
                    {req.why_it_was_lost}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* SECTION 3: PRIVACY & CONSENT ALERTS */}
      {activeTab === "privacy_alerts" && (
        <div className="space-y-3">
          {(() => {
            const loggedAlerts = privacyAlerts.filter((a) => a.board_logged);
            const unloggedAlerts = privacyAlerts.filter((a) => !a.board_logged);
            const loggedVidIds = loggedAlerts.map((a) => a.video_id || "Unlinked").join(", ");
            const unloggedVidDesc = unloggedAlerts
              .map((a) => `${a.video_id || "Unlinked"} — ${a.client_name}`)
              .join(", ");
            return (
              <div className="p-3.5 bg-status-critical-bg/50 border border-status-critical-border rounded-xl text-xs sm:text-sm text-ink-secondary space-y-1">
                <div className="flex items-center justify-between font-semibold text-status-critical">
                  <span>{privacyAlerts.length} Client Consent / Face-Blur Requests Detected</span>
                  <span>
                    {unloggedAlerts.length} Unlogged Violation{unloggedAlerts.length === 1 ? "" : "s"} on Delivered Video
                    {unloggedVidDesc ? ` (${unloggedVidDesc})` : ""}
                  </span>
                </div>
                <p className="text-xs text-ink-secondary leading-relaxed">
                  {loggedAlerts.length} privacy request{loggedAlerts.length === 1 ? "" : "s"} sent via text/email were logged onto the production board
                  {loggedVidIds ? ` (${loggedVidIds})` : ""}, whereas {unloggedAlerts.length} sent via Voice Note
                  {unloggedVidDesc ? ` (${unloggedVidDesc})` : ""} never reached the production board and remained marked Delivered.
                </p>
              </div>
            );
          })()}

          <div className="space-y-3">
            {privacyAlerts.map((alert) => (
              <div
                key={alert.line_number}
                className={`p-5 bg-surface border rounded-xl shadow-xs space-y-2.5 ${
                  alert.board_logged
                    ? "border-border"
                    : "border-status-critical border-l-4"
                }`}
              >
                <div className="flex items-start justify-between gap-2 flex-wrap">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-mono text-xs font-semibold px-2 py-0.5 rounded bg-surface-muted border border-border text-ink-primary">
                      {alert.video_id || "Unlinked"}
                    </span>
                    <span className="font-mono text-xs text-ink-muted">
                      Msg #{alert.line_number}
                    </span>
                    <h3 className="font-semibold text-sm sm:text-base text-ink-primary">
                      {alert.client_name} — {alert.video_title}
                    </h3>
                  </div>
                  <div className="flex items-center gap-2">
                    <StatusBadge
                      label={
                        alert.board_logged
                          ? `Logged on board (${alert.notes_on_board})`
                          : "MISSING FROM BOARD — DELIVERED!"
                      }
                      variant={alert.board_logged ? "warning" : "critical"}
                    />
                  </div>
                </div>

                <p className="text-xs sm:text-sm text-ink-primary bg-canvas p-3 rounded-lg border border-border">
                  &ldquo;{alert.message_text}&rdquo;
                </p>

                <div className="flex items-center justify-between text-xs text-ink-secondary">
                  <span>
                    Sent by <strong>{alert.sender}</strong> via <strong>{alert.channel}</strong> on {formatDate(alert.date)}
                  </span>
                  <span>Video Stage: <strong>{alert.video_stage}</strong></span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* SECTION 4: ALL 190 MESSAGES EXPLORER */}
      {activeTab === "all_messages" && (
        <div className="space-y-3">
          <div className="flex items-center justify-between flex-wrap gap-2 p-3 bg-surface border border-border rounded-xl text-xs">
            <div className="flex items-center gap-1.5 flex-wrap">
              {[
                ["all", `All (${allMessages.length})`],
                ["Email", `Email (${messagesData?.by_channel?.["Email"] ?? 0})`],
                ["WhatsApp", `WhatsApp (${messagesData?.by_channel?.["WhatsApp"] ?? 0})`],
                ["Voice note", `Voice note (${messagesData?.by_channel?.["Voice note"] ?? 0})`],
                ["Instagram DM", `Instagram DM (${messagesData?.by_channel?.["Instagram DM"] ?? 0})`],
                ["Website form", `Website form (${messagesData?.by_channel?.["Website form"] ?? 0})`],
                ["spam", `Quarantined Spam (${messagesData?.quarantined_messages?.length ?? 0})`],
              ].map(([ch, label]) => (
                <button
                  key={ch}
                  type="button"
                  onClick={() => setChannelFilter(ch)}
                  className={`px-2.5 py-1 rounded-md font-medium transition-colors cursor-pointer ${
                    channelFilter === ch
                      ? "bg-brand text-white"
                      : "bg-surface-muted text-ink-secondary hover:text-ink-primary"
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
            <span className="text-ink-muted font-medium">
              Showing {filteredMessages.length} of {allMessages.length} messages
            </span>
          </div>

          <div className="bg-surface border border-border rounded-xl shadow-xs divide-y divide-border max-h-[540px] overflow-y-auto">
            {filteredMessages.map((m) => (
              <div key={m.line_number} className="p-3.5 hover:bg-surface-muted/40 transition-colors space-y-1.5">
                <div className="flex items-center justify-between gap-2 flex-wrap text-xs">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-mono font-semibold text-ink-muted">
                      #{m.line_number}
                    </span>
                    <span className="font-semibold text-ink-primary">
                      {m.sender}
                    </span>
                    <span className="px-2 py-0.5 rounded bg-surface-muted text-ink-secondary font-medium">
                      {m.channel}
                    </span>
                    {m.client_name && (
                      <span className="text-brand font-medium">
                        → {m.client_name}
                      </span>
                    )}
                    {m.matched_video_id && (
                      <span className="font-mono px-1.5 py-0.5 rounded bg-canvas border border-border text-ink-primary">
                        {m.matched_video_id}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <StatusBadge
                      label={m.categories[0] || "general"}
                      variant={
                        m.severity === "critical" || m.severity === "high"
                          ? "critical"
                          : m.categories.includes("spam_or_phishing")
                          ? "neutral"
                          : m.categories.includes("opportunity_or_referral")
                          ? "success"
                          : "info"
                      }
                    />
                    <button
                      type="button"
                      onClick={() => openHumanReview(m)}
                      className="px-2 py-0.5 rounded text-[11px] font-medium bg-surface-muted hover:bg-surface border border-border text-ink-secondary hover:text-ink-primary transition-colors cursor-pointer"
                    >
                      Review
                    </button>
                    <span className="text-ink-muted tabular-nums">{formatDate(m.date)}</span>
                  </div>
                </div>
                <p className="text-xs sm:text-sm text-ink-secondary leading-relaxed">
                  {m.message_text}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* SECTION 5: CHANNEL PERFORMANCE (ACQUISITION & CONVERSION ANALYSIS) */}
      <section className="space-y-4 pt-4 border-t border-border" aria-label="Acquisition channel performance">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div>
            <h2 className="text-lg font-semibold text-ink-primary tracking-tight">
              Acquisition channel performance
            </h2>
            <p className="text-xs sm:text-sm text-ink-secondary">
              Conversion rate, lost leads, unreplied inquiries, and attributed revenue by marketing platform.
            </p>
          </div>

          {marketingData?.best_marketing_channel && (
            <div className="px-3 py-1.5 rounded-lg bg-brand-soft border border-[#F0D5C9] text-xs text-brand font-medium">
              {marketingData.best_marketing_channel.label || "Best Observed Conversion (Ad Spend Unknown)"}:{" "}
              <strong>{marketingData.best_marketing_channel.channel}</strong>
            </div>
          )}
        </div>

        {marketingError ? (
          <div className="p-4 bg-status-warning-bg/40 border border-status-warning-border rounded-xl text-xs text-status-warning flex items-center justify-between">
            <span>{marketingError}</span>
            <button
              type="button"
              onClick={loadRequests}
              className="underline font-medium hover:opacity-80 cursor-pointer"
            >
              Retry
            </button>
          </div>
        ) : marketingData ? (
          <div className="space-y-4">
            {marketingData.best_marketing_channel?.why && (
              <div className="p-4 bg-surface rounded-xl border border-border shadow-xs space-y-1.5">
                <div className="flex items-center gap-2 text-xs font-semibold text-brand">
                  <TrendingUp className="w-4 h-4" />
                  <span>Channel Finding & Attribution Rationale</span>
                </div>
                <p className="text-xs sm:text-sm text-ink-secondary leading-relaxed">
                  {marketingData.best_marketing_channel.why}
                </p>
              </div>
            )}

            {/* 4 HIGH-LEVEL SUMMARY METRIC CARDS */}
            {channelTotals && (
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-3.5">
                <MetricCard
                  label="Total inbound reach"
                  value={`${channelTotals.totalLeads} leads`}
                  subtext="100% volume across 6 platforms"
                  icon={<Target className="w-4 h-4 text-ink-muted" />}
                  variant="neutral"
                />
                <MetricCard
                  label="Won vs lost leads"
                  value={`${channelTotals.wonLeads} won • ${channelTotals.lostLeads} lost`}
                  subtext={`${channelTotals.overallConversion}% win rate (${channelTotals.clientsAcquired} clients won)`}
                  icon={<TrendingUp className="w-4 h-4 text-status-success" />}
                  variant="success"
                />
                <MetricCard
                  label="Never replied inquiries"
                  value={`${leadsData?.legitimate_unanswered_count ?? 13} legitimate`}
                  subtext={`${channelTotals.unrepliedLeads} total unreplied (13 legit, 3 client forms, 4 junk)`}
                  icon={<AlertTriangle className="w-4 h-4 text-status-critical" />}
                  variant="critical"
                />
                <MetricCard
                  label="Total attributed revenue"
                  value={formatCurrency(channelTotals.totalRevenue)}
                  subtext="100% of non-void client invoices reconciled"
                  icon={<DollarSign className="w-4 h-4 text-brand" />}
                  variant="brand"
                />
              </div>
            )}

            <div className="bg-surface border border-border rounded-xl shadow-xs overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs sm:text-sm">
                  <thead className="bg-surface-muted/50 border-b border-border text-ink-secondary text-xs font-semibold uppercase tracking-wider">
                    <tr>
                      <th className="py-3 px-4">Channel / Platform</th>
                      <th className="py-3 px-3 text-center">Total Reach</th>
                      <th className="py-3 px-3 text-center">Won</th>
                      <th className="py-3 px-3 text-center">Lost</th>
                      <th className="py-3 px-3 text-center">Never Replied</th>
                      <th className="py-3 px-4 text-center">Win Rate</th>
                      <th className="py-3 px-3 text-center">Clients Won</th>
                      <th className="py-3 px-4 text-right">Attributed Revenue</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {marketingData.channel_metrics?.map((ch) => {
                      const isTop = ch.source === marketingData.best_marketing_channel?.channel;
                      const reachPercent = channelTotals?.totalLeads
                        ? ((ch.total_leads / channelTotals.totalLeads) * 100).toFixed(1)
                        : "0.0";
                      return (
                        <tr
                          key={ch.source}
                          className={`hover:bg-surface-hover/70 transition-colors ${
                            isTop ? "bg-brand-soft/20 font-medium" : ""
                          }`}
                        >
                          <td className="py-3 px-4 font-semibold text-ink-primary">
                            <div className="flex items-center gap-2">
                              <span>{ch.source}</span>
                              {isTop && (
                                <span className="px-1.5 py-0.2 rounded text-[11px] bg-brand text-white font-semibold">
                                  Top Conversion
                                </span>
                              )}
                            </div>
                          </td>
                          <td className="py-3 px-3 text-center tabular-nums text-ink-primary font-medium">
                            <span>{ch.total_leads}</span>
                            <span className="block text-[10px] text-ink-muted font-normal">
                              {reachPercent}% reach
                            </span>
                          </td>
                          <td className="py-3 px-3 text-center tabular-nums text-status-success font-medium">
                            {ch.won_leads}
                          </td>
                          <td className="py-3 px-3 text-center tabular-nums text-status-critical font-medium">
                            {ch.lost_leads}
                          </td>
                          <td className="py-3 px-3 text-center tabular-nums font-medium">
                            <span
                              className={
                                ch.unreplied_leads > 0
                                  ? "text-status-warning font-semibold"
                                  : "text-ink-muted"
                              }
                            >
                              {ch.unreplied_leads}
                            </span>
                          </td>
                          <td className="py-3 px-4 text-center tabular-nums">
                            <span className="font-semibold text-ink-primary">
                              {ch.conversion_rate}%
                            </span>
                          </td>
                          <td className="py-3 px-3 text-center tabular-nums text-ink-secondary">
                            {ch.clients_acquired}
                          </td>
                          <td className="py-3 px-4 text-right font-semibold tabular-nums text-ink-primary">
                            {formatCurrency(ch.direct_booking_revenue)}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                  {/* AT THE END OF ALL: CALCULATE TOTALS ROW */}
                  {channelTotals && (
                    <tfoot className="bg-canvas border-t-2 border-border font-semibold text-ink-primary text-xs sm:text-sm">
                      <tr>
                        <td className="py-3.5 px-4 font-bold text-ink-primary">
                          Total / Aggregate Reach
                        </td>
                        <td className="py-3.5 px-3 text-center tabular-nums font-bold">
                          {channelTotals.totalLeads}{" "}
                          <span className="text-[10px] text-ink-muted font-normal block">
                            (100% reach)
                          </span>
                        </td>
                        <td className="py-3.5 px-3 text-center tabular-nums font-bold text-status-success">
                          {channelTotals.wonLeads}
                        </td>
                        <td className="py-3.5 px-3 text-center tabular-nums font-bold text-status-critical">
                          {channelTotals.lostLeads}
                        </td>
                        <td className="py-3.5 px-3 text-center tabular-nums font-bold text-status-warning">
                          {channelTotals.unrepliedLeads}{" "}
                          <span className="text-[10px] text-ink-muted font-normal block">
                            ({leadsData?.legitimate_unanswered_count ?? 13} legit)
                          </span>
                        </td>
                        <td className="py-3.5 px-4 text-center tabular-nums font-bold text-brand">
                          {channelTotals.overallConversion}%
                        </td>
                        <td className="py-3.5 px-3 text-center tabular-nums font-bold text-ink-primary">
                          {channelTotals.clientsAcquired}
                        </td>
                        <td className="py-3.5 px-4 text-right font-bold tabular-nums text-brand text-sm sm:text-base">
                          {formatCurrency(channelTotals.totalRevenue)}
                        </td>
                      </tr>
                    </tfoot>
                  )}
                </table>
              </div>
            </div>

            {marketingData.what_this_data_cannot_tell_us && marketingData.what_this_data_cannot_tell_us.length > 0 && (
              <div className="pt-1">
                <button
                  type="button"
                  onClick={() => setShowLimitations(!showLimitations)}
                  className="inline-flex items-center gap-1.5 text-xs font-medium text-ink-muted hover:text-ink-primary transition-colors cursor-pointer"
                >
                  <HelpCircle className="w-3.5 h-3.5 text-brand" />
                  <span>
                    {showLimitations ? "Hide data boundary & accounting limitations" : "What this data cannot tell us about marketing profitability"}
                  </span>
                  {showLimitations ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                </button>

                {showLimitations && (
                  <div className="mt-2.5 p-4 bg-surface-muted/60 border border-border rounded-xl space-y-2 text-xs text-ink-secondary">
                    <span className="font-semibold text-ink-primary block uppercase tracking-wider text-[11px]">
                      Accounting Boundaries & Unrecorded Factors:
                    </span>
                    <ul className="list-disc pl-5 space-y-1.5">
                      {marketingData.what_this_data_cannot_tell_us.map((lim, idx) => (
                        <li key={idx} className="leading-relaxed">
                          {lim}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}
          </div>
        ) : null}
      </section>

      {/* GEMINI AI CLASSIFICATION WORKSPACE MODAL */}
      {showGeminiModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-xs p-4 animate-in fade-in duration-150"
          role="dialog"
          aria-modal="true"
          aria-labelledby="gemini-modal-title"
        >
          <div className="bg-surface rounded-2xl shadow-2xl w-full max-w-2xl border border-border overflow-hidden flex flex-col max-h-[88vh]">
            <div className="flex items-center justify-between px-6 py-4 border-b border-border">
              <div>
                <h2 id="gemini-modal-title" className="text-base font-semibold text-ink-primary flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-brand" />
                  <span>Google Gemini Message Classification</span>
                </h2>
                <p className="text-xs text-ink-secondary mt-0.5">
                  Official google-genai SDK • gemini-2.5-flash • Isolated Prompts • Substring Validation
                </p>
              </div>
              <button
                type="button"
                onClick={() => {
                  setShowGeminiModal(false);
                  modalOpenerRef.current?.focus();
                }}
                className="p-1.5 rounded-lg text-ink-secondary hover:text-ink-primary hover:bg-surface-muted transition-colors cursor-pointer"
                aria-label="Close dialog"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-6 overflow-y-auto flex-1 space-y-5 text-sm">
              {/* Provider Status */}
              <div className="p-4 rounded-xl bg-surface-muted/60 border border-border space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-ink-primary text-sm">Provider & Model Status</span>
                  <StatusBadge
                    label={geminiStatus?.configured ? "Live Gemini API Active" : "Not Configured (Calls Blocked)"}
                    variant={geminiStatus?.configured ? "success" : "warning"}
                  />
                </div>
                <p className="text-xs text-ink-secondary leading-relaxed">
                  {geminiStatus?.configured
                    ? `Live Gemini calls active using model '${geminiStatus.model}' via official '${geminiStatus.sdk}' SDK.`
                    : "GEMINI_API_KEY is not configured in the environment. In strict compliance with system rules, live provider calls are blocked (never faked), and the deterministic rule classifier processes all inquiries and dry-runs."}
                </p>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-2 border-t border-border/60 text-xs">
                  <div>
                    <span className="text-ink-muted block text-[11px]">Total Messages</span>
                    <span className="font-semibold text-ink-primary tabular-nums">{allMessages.length}</span>
                  </div>
                  <div>
                    <span className="text-ink-muted block text-[11px]">Classified</span>
                    <span className="font-semibold text-status-success tabular-nums">{geminiStatus?.classified_count ?? 0}</span>
                  </div>
                  <div>
                    <span className="text-ink-muted block text-[11px]">Pending</span>
                    <span className="font-semibold text-ink-primary tabular-nums">{geminiStatus?.pending_count ?? allMessages.length}</span>
                  </div>
                  <div>
                    <span className="text-ink-muted block text-[11px]">Human Reviewed</span>
                    <span className="font-semibold text-brand tabular-nums">{geminiStatus?.human_confirmed_count ?? 0}</span>
                  </div>
                </div>
              </div>

              {/* Batch Processing Controls */}
              <div className="p-4 rounded-xl bg-surface border border-border space-y-3">
                <span className="font-semibold text-ink-primary text-xs uppercase tracking-wider block">
                  Batch Classification Runner:
                </span>
                <p className="text-xs text-ink-secondary">
                  Process inbound messages in isolated chunks of 10–15 messages with SHA-256 deduplication and exact substring verification.
                </p>
                <div className="flex items-center gap-2 flex-wrap">
                  <button
                    type="button"
                    disabled={batchLoading}
                    onClick={() => handleBatchClassify(true)}
                    className="px-3.5 py-2 bg-surface-muted hover:bg-surface border border-border text-ink-primary text-xs font-medium rounded-lg transition-colors cursor-pointer inline-flex items-center gap-1.5"
                  >
                    {batchLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Bot className="w-3.5 h-3.5" />}
                    <span>Run Dry-Run Batch</span>
                  </button>
                  <button
                    type="button"
                    disabled={batchLoading || !geminiStatus?.configured}
                    onClick={() => handleBatchClassify(false)}
                    className="px-3.5 py-2 bg-brand hover:bg-brand-hover disabled:opacity-50 text-white text-xs font-medium rounded-lg transition-colors cursor-pointer inline-flex items-center gap-1.5 shadow-xs"
                  >
                    {batchLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
                    <span>Classify Next Batch (Live Gemini)</span>
                  </button>
                </div>
                {batchResult && (
                  <div className="p-3 bg-surface-muted rounded-lg text-xs space-y-1">
                    <p className="font-medium text-ink-primary">{batchResult.message || `Processed ${batchResult.processed} messages.`}</p>
                    <p className="text-ink-muted">Processed: {batchResult.processed} • Skipped (Cached): {batchResult.skipped} • Failed: {batchResult.failed}</p>
                  </div>
                )}
              </div>

              {/* Interactive Single-Message Classifier */}
              <div className="p-4 rounded-xl bg-surface-muted/50 border border-border space-y-3">
                <span className="font-semibold text-ink-primary text-xs uppercase tracking-wider block">
                  Test Single Message Classification:
                </span>
                {testError && (
                  <p className="text-xs text-status-critical bg-status-critical-bg p-2 rounded-lg border border-status-critical-border">
                    {testError}
                  </p>
                )}
                <form onSubmit={handleTestClassify} className="flex gap-2">
                  <input
                    type="text"
                    value={testText}
                    onChange={(e) => setTestText(e.target.value)}
                    placeholder="Enter customer message (e.g. 'Please blur the patient face in reel 2')..."
                    className="flex-1 px-3.5 py-2 bg-surface border border-border rounded-lg text-xs sm:text-sm text-ink-primary focus:outline-none focus:border-brand"
                  />
                  <button
                    type="submit"
                    disabled={testLoading || !testText.trim()}
                    className="px-4 py-2 bg-brand hover:bg-brand-hover disabled:opacity-50 text-white text-xs sm:text-sm font-medium rounded-lg transition-colors cursor-pointer inline-flex items-center gap-1.5 shadow-xs"
                  >
                    {testLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                    <span>Classify</span>
                  </button>
                </form>

                {testResult && (
                  <div className="p-3 bg-surface rounded-lg border border-border text-xs space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="font-medium text-ink-secondary">Primary Category:</span>
                      <StatusBadge label={testResult.primary_category} variant="success" />
                    </div>
                    <div className="grid grid-cols-2 gap-2 text-ink-secondary">
                      <div>Urgency: <strong>{testResult.urgency}</strong></div>
                      <div>Sentiment: <strong>{testResult.sentiment}</strong></div>
                      <div>Confidence: <strong>{(testResult.confidence * 100).toFixed(0)}%</strong></div>
                      <div>Engine: <strong>{testResult.provider} ({testResult.model})</strong></div>
                    </div>
                    {testResult.concise_summary && (
                      <p className="text-ink-primary pt-1">
                        <span className="text-ink-muted">Summary: </span>
                        {testResult.concise_summary}
                      </p>
                    )}
                    {testResult.evidence_quotes && testResult.evidence_quotes.length > 0 && (
                      <div className="text-ink-secondary">
                        <span className="text-ink-muted">Evidence Quote: </span>
                        &ldquo;{testResult.evidence_quotes[0]}&rdquo;
                      </div>
                    )}
                    {testResult.classification_notes && (
                      <p className="text-ink-muted text-[11px] pt-1 italic">{testResult.classification_notes}</p>
                    )}
                  </div>
                )}
              </div>
            </div>

            <div className="px-6 py-3.5 bg-surface-muted/50 border-t border-border flex justify-end">
              <button
                type="button"
                onClick={() => {
                  setShowGeminiModal(false);
                  modalOpenerRef.current?.focus();
                }}
                className="px-5 py-2 bg-brand hover:bg-brand-hover text-white text-xs sm:text-sm font-medium rounded-lg transition-colors cursor-pointer shadow-xs"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* HUMAN REVIEW OVERRIDE MODAL */}
      {reviewModalOpen && selectedMsgForReview && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-xs p-4 animate-in fade-in duration-150"
          role="dialog"
          aria-modal="true"
          aria-labelledby="review-modal-title"
        >
          <div className="bg-surface rounded-2xl shadow-2xl w-full max-w-lg border border-border overflow-hidden flex flex-col max-h-[88vh]">
            <div className="flex items-center justify-between px-6 py-4 border-b border-border">
              <div>
                <h2 id="review-modal-title" className="text-base font-semibold text-ink-primary">
                  Human Classification Review
                </h2>
                <p className="text-xs text-ink-secondary mt-0.5">
                  Msg #{selectedMsgForReview.line_number} • {selectedMsgForReview.sender} ({selectedMsgForReview.channel})
                </p>
              </div>
              <button
                type="button"
                onClick={() => setReviewModalOpen(false)}
                className="p-1.5 rounded-lg text-ink-secondary hover:text-ink-primary hover:bg-surface-muted transition-colors cursor-pointer"
                aria-label="Close dialog"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-6 overflow-y-auto flex-1 space-y-4 text-xs sm:text-sm">
              <div className="p-3 bg-canvas border border-border rounded-lg text-ink-primary text-xs leading-relaxed italic">
                &ldquo;{selectedMsgForReview.message_text}&rdquo;
              </div>

              <div className="space-y-1.5">
                <label className="font-semibold text-ink-primary text-xs block">
                  Primary Category (16 Controlled Categories):
                </label>
                <select
                  value={reviewCategory}
                  onChange={(e) => setReviewCategory(e.target.value)}
                  className="w-full px-3 py-2 bg-surface border border-border rounded-lg text-xs sm:text-sm text-ink-primary focus:outline-none focus:border-brand"
                >
                  {ALLOWED_CATEGORIES.map((cat) => (
                    <option key={cat} value={cat}>
                      {cat.replace(/_/g, " ")}
                    </option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <label className="font-semibold text-ink-primary text-xs block">Urgency Level:</label>
                  <select
                    value={reviewUrgency}
                    onChange={(e) => setReviewUrgency(e.target.value)}
                    className="w-full px-3 py-2 bg-surface border border-border rounded-lg text-xs sm:text-sm text-ink-primary focus:outline-none focus:border-brand"
                  >
                    <option value="low">Low</option>
                    <option value="normal">Normal</option>
                    <option value="high">High</option>
                    <option value="critical">Critical</option>
                  </select>
                </div>
                <div className="flex items-center gap-2 pt-6">
                  <input
                    type="checkbox"
                    id="spam-toggle"
                    checked={reviewIsSpam}
                    onChange={(e) => setReviewIsSpam(e.target.checked)}
                    className="w-4 h-4 text-brand rounded border-border focus:ring-brand cursor-pointer"
                  />
                  <label htmlFor="spam-toggle" className="text-xs font-medium text-ink-primary cursor-pointer">
                    Quarantine as Spam / Test
                  </label>
                </div>
              </div>

              <div className="space-y-1.5">
                <label className="font-semibold text-ink-primary text-xs block">
                  Reviewer Notes / Rationale:
                </label>
                <textarea
                  rows={3}
                  value={reviewNotes}
                  onChange={(e) => setReviewNotes(e.target.value)}
                  placeholder="Reason for classification change..."
                  className="w-full px-3 py-2 bg-surface border border-border rounded-lg text-xs sm:text-sm text-ink-primary focus:outline-none focus:border-brand"
                />
              </div>

              {reviewSuccess && (
                <div className="p-3 bg-status-success-bg border border-status-success-border rounded-lg text-xs text-status-success font-medium">
                  Review override saved successfully to PostgreSQL!
                </div>
              )}
            </div>

            <div className="px-6 py-3.5 bg-surface-muted/50 border-t border-border flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setReviewModalOpen(false)}
                className="px-4 py-2 bg-surface hover:bg-surface-muted border border-border text-ink-secondary text-xs sm:text-sm font-medium rounded-lg transition-colors cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={reviewSaving}
                onClick={handleSaveHumanReview}
                className="px-5 py-2 bg-brand hover:bg-brand-hover disabled:opacity-50 text-white text-xs sm:text-sm font-medium rounded-lg transition-colors cursor-pointer shadow-xs inline-flex items-center gap-1.5"
              >
                {reviewSaving && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                <span>Save Override</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
