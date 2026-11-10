"use client";

import React, { useEffect, useState, useMemo } from "react";
import {
  RefreshCw,
  Clock,
  CheckCircle2,
  AlertTriangle,
  Receipt,
  Search,
  X,
  ChevronDown,
  Info,
} from "lucide-react";
import { api, FinanceReconciliation, formatCurrency, formatDate } from "@/lib/api";
import { PageHeader } from "@/components/ui/PageHeader";
import { MetricCard } from "@/components/ui/MetricCard";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { LoadingState } from "@/components/ui/LoadingState";
import { ErrorState } from "@/components/ui/ErrorState";
import { EmptyState } from "@/components/ui/EmptyState";

const PAGE_SIZE = 35;

export default function MoneyPage() {
  const [data, setData] = useState<FinanceReconciliation | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<
    "overdue" | "billing_errors" | "never_billed" | "we_owe" | "invoices_ledger" | "payments_ledger"
  >("overdue");
  const [overdueMode, setOverdueMode] = useState<"reconciled" | "source">("reconciled");
  const [searchQuery, setSearchQuery] = useState("");
  const [visibleLedgerCount, setVisibleLedgerCount] = useState(PAGE_SIZE);

  const loadFinance = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await api.getFinanceReconciliation();
      setData(res);
    } catch (err: any) {
      setError(err.message || "Failed to load financial reconciliation records.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadFinance();

    const handleDataRefreshed = () => {
      loadFinance();
    };
    window.addEventListener("axeom:data-refreshed", handleDataRefreshed);
    window.addEventListener("axeom:reference-date-changed", handleDataRefreshed);
    return () => {
      window.removeEventListener("axeom:data-refreshed", handleDataRefreshed);
      window.removeEventListener("axeom:reference-date-changed", handleDataRefreshed);
    };
  }, []);

  // Reset pagination on tab or search change
  useEffect(() => {
    setVisibleLedgerCount(PAGE_SIZE);
  }, [activeTab, searchQuery]);

  const reconciledOverdue = data?.overdue_invoices || [];
  const sourceOverdue = data?.source_overdue_invoices || reconciledOverdue;
  const displayedOverdue = overdueMode === "reconciled" ? reconciledOverdue : sourceOverdue;
  const displayedOverdueTotal =
    overdueMode === "reconciled"
      ? data?.overdue_total ?? "0.00"
      : data?.source_overdue_total ?? data?.overdue_total ?? "0.00";

  const billingErrors = data?.billing_tool_is_wrong || [];
  const neverBilled = data?.never_billed_items || [];
  const weOweItems = data?.we_owe || [];
  const invoicesLedger = data?.invoices_ledger || [];
  const paymentsLedger = data?.payments_ledger || [];

  const weOweTotal = useMemo(() => {
    return (data?.we_owe || []).reduce(
      (sum, item) => sum + (typeof item.amount === "number" ? item.amount : parseFloat(String(item.amount) || "0")),
      0
    );
  }, [data?.we_owe]);

  // Filtered invoices ledger
  const filteredInvoices = useMemo(() => {
    const list = data?.invoices_ledger || [];
    if (!searchQuery) return list;
    const q = searchQuery.toLowerCase().trim();
    return list.filter(
      (inv) =>
        inv.invoice_no.toLowerCase().includes(q) ||
        inv.client.toLowerCase().includes(q) ||
        (inv.memo && inv.memo.toLowerCase().includes(q)) ||
        inv.source_status.toLowerCase().includes(q) ||
        inv.reconciled_status.toLowerCase().includes(q)
    );
  }, [data?.invoices_ledger, searchQuery]);

  // Filtered payments ledger
  const filteredPayments = useMemo(() => {
    const list = data?.payments_ledger || [];
    if (!searchQuery) return list;
    const q = searchQuery.toLowerCase().trim();
    return list.filter(
      (pay) =>
        pay.payment_id.toLowerCase().includes(q) ||
        pay.payer.toLowerCase().includes(q) ||
        (pay.client && pay.client.toLowerCase().includes(q)) ||
        pay.method.toLowerCase().includes(q) ||
        pay.reference.toLowerCase().includes(q)
    );
  }, [data?.payments_ledger, searchQuery]);

  if (loading) {
    return <LoadingState message="Reconciling billing records with bank deposits..." variant="metrics" />;
  }

  if (error || !data) {
    return (
      <ErrorState
        title="Could not load financial records"
        message={error || "Unable to reach the studio backend. Please check your network connection or try reloading."}
        onRetry={loadFinance}
      />
    );
  }

  const refDate = data.reference_date || "2026-10-06";

  // Determine status label for invoices ledger
  const getReconciledDisplayStatus = (inv: (typeof invoicesLedger)[0]) => {
    if (inv.reconciled_status.includes("void")) return { label: "Void", variant: "neutral" as const };
    if (inv.reconciled_status.includes("paid") && !inv.reconciled_status.includes("unpaid")) {
      return { label: "Paid in full", variant: "success" as const };
    }
    if (inv.due === refDate) {
      return { label: "Due today", variant: "info" as const };
    }
    if (inv.due > refDate) {
      return { label: "Not yet due", variant: "neutral" as const };
    }
    return { label: "Confirmed overdue", variant: "critical" as const };
  };

  return (
    <div className="space-y-6 max-w-6xl">
      {/* Header with Scenario Date */}
      <PageHeader
        title="Money & Reconciliation"
        description="Reconciliation ledger separating customer receivables from studio liabilities against bank deposits."
        referenceDate={refDate}
        actions={
          <button
            onClick={loadFinance}
            className="inline-flex items-center gap-1.5 px-3 py-2 text-xs sm:text-sm font-medium text-ink-secondary hover:text-ink-primary bg-surface border border-border rounded-lg hover:bg-surface-muted transition-colors cursor-pointer shadow-xs"
            aria-label="Refresh financial records"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Refresh</span>
          </button>
        }
      />

      {/* 1. FOUR SUMMARY CARDS WITH CLEAR ACCOUNTING DEFINITIONS */}
      <section aria-label="Financial position summary">
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-2.5 sm:gap-3.5">
          {/* Card 1: Bank Collections */}
          <MetricCard
            label="Bank collections received"
            value={formatCurrency(data.total_collected_in_bank ?? 0)}
            subtext={
              paymentsLedger.length > 0
                ? `${paymentsLedger.length} verified bank receipts`
                : "No bank receipts recorded"
            }
            icon={<CheckCircle2 className="w-4 h-4 text-status-success" />}
            variant="success"
          />

          {/* Card 2: Confirmed Overdue as of Scenario Date */}
          <MetricCard
            label="Confirmed overdue"
            value={formatCurrency(data.overdue_total ?? 0)}
            subtext={
              reconciledOverdue.length > 0
                ? `${reconciledOverdue.length} reconciled invoices past due date (as of ${refDate})`
                : "No overdue invoices"
            }
            icon={<Clock className="w-4 h-4 text-status-critical" />}
            variant="critical"
          />

          {/* Card 3: Studio Liabilities / Customer Credits */}
          <MetricCard
            label="Customer credits to review"
            value={formatCurrency(weOweTotal || 0)}
            subtext={
              weOweItems.length > 0
                ? `${weOweItems.length} client credit items requiring owner action`
                : "No pending client credits or liabilities"
            }
            icon={<AlertTriangle className="w-4 h-4 text-status-warning" />}
            variant="warning"
          />

          {/* Card 4: Completed Work to Review for Billing */}
          <MetricCard
            label="Work to review for billing"
            value={formatCurrency(data.never_billed_total ?? 0)}
            subtext={
              neverBilled.length > 0
                ? `${neverBilled.length} completed shoots awaiting billing verification`
                : "All completed shoots have been billed"
            }
            icon={<Receipt className="w-4 h-4 text-brand" />}
            variant="neutral"
          />
        </div>
      </section>

      {/* 2. TABBED AUDIT QUEUES */}
      <div className="flex items-center gap-1.5 sm:gap-2 overflow-x-auto pb-2 border-b border-border no-scrollbar -mx-4 px-4 sm:mx-0 sm:px-0 flex-nowrap sm:flex-wrap">
        <button
          onClick={() => setActiveTab("overdue")}
          className={`px-3 py-1.5 rounded-lg text-xs sm:text-sm font-medium transition-colors cursor-pointer shrink-0 whitespace-nowrap ${
            activeTab === "overdue"
              ? "bg-brand text-white shadow-xs"
              : "bg-surface text-ink-secondary hover:text-ink-primary border border-border hover:bg-surface-muted"
          }`}
        >
          Overdue invoices ({reconciledOverdue.length})
        </button>
        <button
          onClick={() => setActiveTab("billing_errors")}
          className={`px-3 py-1.5 rounded-lg text-xs sm:text-sm font-medium transition-colors cursor-pointer shrink-0 whitespace-nowrap ${
            activeTab === "billing_errors"
              ? "bg-brand text-white shadow-xs"
              : "bg-surface text-ink-secondary hover:text-ink-primary border border-border hover:bg-surface-muted"
          }`}
        >
          Billing tool errors ({billingErrors.length})
        </button>
        <button
          onClick={() => setActiveTab("never_billed")}
          className={`px-3 py-1.5 rounded-lg text-xs sm:text-sm font-medium transition-colors cursor-pointer shrink-0 whitespace-nowrap ${
            activeTab === "never_billed"
              ? "bg-brand text-white shadow-xs"
              : "bg-surface text-ink-secondary hover:text-ink-primary border border-border hover:bg-surface-muted"
          }`}
        >
          Unbilled completed work ({neverBilled.length})
        </button>
        <button
          onClick={() => setActiveTab("we_owe")}
          className={`px-3 py-1.5 rounded-lg text-xs sm:text-sm font-medium transition-colors cursor-pointer shrink-0 whitespace-nowrap ${
            activeTab === "we_owe"
              ? "bg-brand text-white shadow-xs"
              : "bg-surface text-ink-secondary hover:text-ink-primary border border-border hover:bg-surface-muted"
          }`}
        >
          Client credits ({weOweItems.length})
        </button>
        <button
          onClick={() => setActiveTab("invoices_ledger")}
          className={`px-3 py-1.5 rounded-lg text-xs sm:text-sm font-medium transition-colors cursor-pointer shrink-0 whitespace-nowrap ${
            activeTab === "invoices_ledger"
              ? "bg-brand text-white shadow-xs"
              : "bg-surface text-ink-secondary hover:text-ink-primary border border-border hover:bg-surface-muted"
          }`}
        >
          All invoices ({invoicesLedger.length})
        </button>
        <button
          onClick={() => setActiveTab("payments_ledger")}
          className={`px-3 py-1.5 rounded-lg text-xs sm:text-sm font-medium transition-colors cursor-pointer shrink-0 whitespace-nowrap ${
            activeTab === "payments_ledger"
              ? "bg-brand text-white shadow-xs"
              : "bg-surface text-ink-secondary hover:text-ink-primary border border-border hover:bg-surface-muted"
          }`}
        >
          Bank payments ({paymentsLedger.length})
        </button>
      </div>

      {/* TAB 1: OVERDUE INVOICES */}
      {activeTab === "overdue" && (
        <section className="space-y-3.5" aria-label="Overdue invoices">
          {/* Cutoff explanation banner */}
          <div className="p-3.5 bg-surface border border-border rounded-xl flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
            <div className="space-y-0.5">
              <div className="flex items-center gap-1.5 font-medium text-ink-primary">
                <Info className="w-3.5 h-3.5 text-brand" />
                <span>Strict Scenario Date Cutoff: <code className="font-mono bg-surface-muted px-1.5 py-0.5 rounded text-ink-primary">due_date &lt; {refDate}</code></span>
              </div>
              <p className="text-ink-secondary">
                Invoices due on {refDate} are considered <strong>Due today</strong>. Invoices with due dates after {refDate} are <strong>Not yet due</strong>.
              </p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 w-full sm:w-auto shrink-0">
              <button
                type="button"
                onClick={() => setOverdueMode("reconciled")}
                className={`px-3 py-2 sm:py-1.5 rounded-lg text-xs font-medium transition-colors cursor-pointer text-center ${
                  overdueMode === "reconciled"
                    ? "bg-brand text-white shadow-xs"
                    : "bg-surface-muted text-ink-secondary hover:text-ink-primary"
                }`}
              >
                Reconciled overdue ({reconciledOverdue.length} = {formatCurrency(data.overdue_total)})
              </button>
              <button
                type="button"
                onClick={() => setOverdueMode("source")}
                className={`px-3 py-2 sm:py-1.5 rounded-lg text-xs font-medium transition-colors cursor-pointer text-center ${
                  overdueMode === "source"
                    ? "bg-brand text-white shadow-xs"
                    : "bg-surface-muted text-ink-secondary hover:text-ink-primary"
                }`}
              >
                Source status ({sourceOverdue.length} = {formatCurrency(data.source_overdue_total ?? data.overdue_total)})
              </button>
            </div>
          </div>

          {displayedOverdue.length === 0 ? (
            <EmptyState
              title={`No overdue invoices as of ${refDate}`}
              description="All issued invoices are currently settled or within their payment terms."
            />
          ) : (
            <>
              {/* Desktop Table */}
              <div className="hidden md:block bg-surface border border-border rounded-xl shadow-xs overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm">
                  <thead className="bg-surface-muted/50 border-b border-border text-ink-secondary text-xs font-semibold uppercase tracking-wider">
                    <tr>
                      <th className="py-3 px-4">Invoice #</th>
                      <th className="py-3 px-4">Client</th>
                      <th className="py-3 px-4">Due Date</th>
                      <th className="py-3 px-4 text-center">Days Late</th>
                      <th className="py-3 px-4">Reconciliation Status</th>
                      <th className="py-3 px-4 text-right">Amount Owed</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {displayedOverdue.map((inv) => (
                      <tr key={inv.invoice} className="hover:bg-surface-muted/40 transition-colors">
                        <td className="py-3 px-4 font-mono text-xs font-semibold text-ink-primary">
                          {inv.invoice}
                        </td>
                        <td className="py-3 px-4 font-medium text-ink-primary">
                          {inv.client}
                        </td>
                        <td className="py-3 px-4 text-ink-secondary tabular-nums">
                          {formatDate(inv.due_date)}
                        </td>
                        <td className="py-3 px-4 text-center">
                          <span className="inline-block px-2.5 py-0.5 rounded-full text-xs font-medium bg-status-critical-bg text-status-critical border border-status-critical-border">
                            {inv.days_late} days late
                          </span>
                        </td>
                        <td className="py-3 px-4 text-xs">
                          <StatusBadge
                            label={inv.reconciliation_status || "confirmed_unpaid"}
                            variant={
                              inv.reconciliation_status === "paid_in_bank_conflict" ||
                              inv.reconciliation_status === "candidate_batch_paid"
                                ? "success"
                                : inv.reconciliation_status === "candidate_partially_paid"
                                ? "warning"
                                : "critical"
                            }
                          />
                        </td>
                        <td className="py-3 px-4 text-right font-semibold text-ink-primary tabular-nums">
                          {formatCurrency(inv.amount_owed)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                  <tfoot className="bg-surface-muted/50 border-t border-border font-semibold text-ink-primary text-sm">
                    <tr>
                      <td colSpan={5} className="py-3 px-4 text-right">
                        {overdueMode === "reconciled" ? "Total Reconciled Overdue:" : "Total Source-Status Overdue:"}
                      </td>
                      <td className="py-3 px-4 text-right text-status-critical tabular-nums text-base">
                        {formatCurrency(displayedOverdueTotal)}
                      </td>
                    </tr>
                  </tfoot>
                </table>
                </div>
              </div>

              {/* Mobile Stacked Cards */}
              <div className="md:hidden space-y-3">
                {displayedOverdue.map((inv) => (
                  <div
                    key={inv.invoice}
                    className="p-4 bg-surface border border-border rounded-xl shadow-xs space-y-2 border-l-4 border-l-status-critical"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <span className="font-mono text-xs text-ink-muted">{inv.invoice}</span>
                        <h4 className="font-semibold text-sm text-ink-primary">{inv.client}</h4>
                      </div>
                      <span className="font-semibold text-base text-status-critical tabular-nums">
                        {formatCurrency(inv.amount_owed)}
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-xs pt-2 border-t border-border/60 text-ink-secondary">
                      <span>Due: {formatDate(inv.due_date)}</span>
                      <span className="px-2 py-0.5 rounded-full bg-status-critical-bg text-status-critical font-medium">
                        {inv.days_late} days late
                      </span>
                    </div>
                  </div>
                ))}
                <div className="p-3 bg-surface-muted border border-border rounded-xl flex items-center justify-between text-xs font-semibold">
                  <span className="text-ink-secondary">Total Overdue:</span>
                  <span className="text-status-critical text-sm tabular-nums">
                    {formatCurrency(displayedOverdueTotal)}
                  </span>
                </div>
              </div>
            </>
          )}
        </section>
      )}

      {/* TAB 2: BILLING TOOL ERRORS */}
      {activeTab === "billing_errors" && (
        <section className="space-y-3" aria-label="Billing tool errors">
          <p className="text-xs text-ink-secondary">
            Invoices where software billing status contradicts actual verified bank statements:
          </p>

          {billingErrors.length === 0 ? (
            <EmptyState
              title="No billing tool discrepancies found"
              description="All invoice statuses match bank transaction records."
            />
          ) : (
            <div className="grid grid-cols-1 gap-3">
              {billingErrors.map((item, idx) => (
                <div
                  key={idx}
                  className="p-4 bg-surface border border-border rounded-xl shadow-xs space-y-2.5"
                >
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                    <span className="font-mono text-sm font-semibold text-ink-primary">
                      {item.invoice}
                    </span>
                    <div className="flex items-center gap-2 text-xs flex-wrap">
                      <span className="px-2 py-0.5 rounded bg-surface-muted border border-border text-ink-secondary">
                        Billing tool says: <strong className="text-ink-primary">{item.tool_says}</strong>
                      </span>
                      <span className="text-ink-muted">→</span>
                      <span className="px-2 py-0.5 rounded bg-status-success-bg border border-status-success-border text-status-success font-semibold">
                        Bank evidence: {item.truth}
                      </span>
                    </div>
                  </div>

                  <div className="p-3 bg-surface-muted/60 rounded-lg border border-border text-xs text-ink-secondary leading-relaxed">
                    <span className="font-semibold text-ink-primary block mb-0.5">Audit Proof:</span>
                    {item.how_you_know}
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      )}

      {/* TAB 3: UNBILLED COMPLETED WORK */}
      {activeTab === "never_billed" && (
        <section className="space-y-3" aria-label="Unbilled work">
          <div className="p-3 bg-surface border border-border rounded-xl text-xs text-ink-secondary">
            Completed shoots without a candidate invoice. Note: <strong>{data.retainer_covered_bookings_count ?? 0}</strong> retainer shoots ($0 booking price) are covered under client monthly retainers and are not considered missing invoices.
          </div>

          {neverBilled.length === 0 ? (
            <EmptyState
              title="No unbilled completed shoots"
              description="All completed bookings have corresponding invoices."
            />
          ) : (
            <>
              {/* Desktop Table */}
              <div className="hidden md:block bg-surface border border-border rounded-xl shadow-xs overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm">
                  <thead className="bg-surface-muted/50 border-b border-border text-ink-secondary text-xs font-semibold uppercase tracking-wider">
                    <tr>
                      <th className="py-3 px-4">Booking Reference</th>
                      <th className="py-3 px-4">Client</th>
                      <th className="py-3 px-4">Audit Status</th>
                      <th className="py-3 px-4 text-right">Unbilled Amount</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {neverBilled.map((item, idx) => (
                      <tr key={idx} className="hover:bg-surface-muted/40 transition-colors">
                        <td className="py-3 px-4 font-mono text-xs font-semibold text-ink-primary">
                          {item.booking_id_or_month}
                        </td>
                        <td className="py-3 px-4 font-medium text-ink-primary">
                          <div>{item.client}</div>
                          {item.why && (
                            <div className="text-xs text-ink-secondary">{item.why}</div>
                          )}
                        </td>
                        <td className="py-3 px-4">
                          <StatusBadge
                            label={
                              item.confidence === "needs_billing_review"
                                ? "Needs Billing Review"
                                : "Confirmed Unbilled"
                            }
                            variant={
                              item.confidence === "needs_billing_review" ? "warning" : "critical"
                            }
                          />
                        </td>
                        <td className="py-3 px-4 text-right font-semibold text-ink-primary tabular-nums">
                          {formatCurrency(item.amount)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                  <tfoot className="bg-surface-muted/50 border-t border-border font-semibold text-ink-primary text-sm">
                    <tr>
                      <td colSpan={3} className="py-3 px-4 text-right">
                        Total Unbilled Revenue:
                      </td>
                      <td className="py-3 px-4 text-right text-brand tabular-nums text-base">
                        {formatCurrency(data.never_billed_total)}
                      </td>
                    </tr>
                  </tfoot>
                </table>
                </div>
              </div>

              {/* Mobile Stacked Cards */}
              <div className="md:hidden space-y-3">
                {neverBilled.map((item, idx) => (
                  <div
                    key={idx}
                    className="p-4 bg-surface border border-border rounded-xl shadow-xs space-y-2 border-l-4 border-l-brand"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <span className="font-mono text-xs text-ink-muted">
                          {item.booking_id_or_month}
                        </span>
                        <h4 className="font-semibold text-sm text-ink-primary">{item.client}</h4>
                      </div>
                      <span className="font-semibold text-base text-brand tabular-nums">
                        {formatCurrency(item.amount)}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </section>
      )}

      {/* TAB 4: CLIENT CREDITS (STUDIO OWES) */}
      {activeTab === "we_owe" && (
        <section className="space-y-3" aria-label="Client credits">
          {weOweItems.length === 0 ? (
            <EmptyState
              title="No client liabilities"
              description="The studio does not owe any refunds or customer credits."
            />
          ) : (
            <div className="space-y-3">
              {weOweItems.map((item, idx) => (
                <div
                  key={idx}
                  className="p-4 bg-surface border border-border rounded-xl shadow-xs space-y-2 border-l-4 border-l-status-warning"
                >
                  <div className="flex items-center justify-between">
                    <h3 className="font-semibold text-sm text-ink-primary">
                      {item.client}
                    </h3>
                    <span className="text-base font-semibold text-status-warning tabular-nums">
                      {formatCurrency(item.amount)}
                    </span>
                  </div>
                  <p className="text-xs text-ink-secondary leading-relaxed bg-surface-muted/60 p-2.5 rounded-lg border border-border">
                    {item.why}
                  </p>
                </div>
              ))}
            </div>
          )}
        </section>
      )}

      {/* TAB 5: ALL INVOICES LEDGER (NATURAL SCROLLING - NO NESTED TRAP!) */}
      {activeTab === "invoices_ledger" && (
        <section className="space-y-3" aria-label="Invoices ledger">
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <span className="text-xs text-ink-secondary">
              Showing {Math.min(visibleLedgerCount, filteredInvoices.length)} of {filteredInvoices.length} invoices
            </span>
            <div className="relative max-w-xs w-full">
              <Search className="w-4 h-4 text-ink-muted absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search invoice #, client, memo..."
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

          {/* Desktop Table */}
          <div className="hidden md:block bg-surface border border-border rounded-xl shadow-xs overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs sm:text-sm">
              <thead className="bg-surface-muted/50 border-b border-border text-ink-secondary text-xs font-semibold uppercase tracking-wider">
                <tr>
                  <th className="py-3 px-4">Invoice #</th>
                  <th className="py-3 px-4">Client</th>
                  <th className="py-3 px-4">Memo</th>
                  <th className="py-3 px-4">Due Date</th>
                  <th className="py-3 px-4">Billing Tool</th>
                  <th className="py-3 px-4">Reconciled Status</th>
                  <th className="py-3 px-4 text-right">Amount</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {filteredInvoices.slice(0, visibleLedgerCount).map((inv) => {
                  const stat = getReconciledDisplayStatus(inv);
                  return (
                    <tr key={inv.invoice_no} className="hover:bg-surface-muted/40 transition-colors">
                      <td className="py-2.5 px-4 font-mono font-semibold text-ink-primary">
                        {inv.invoice_no}
                      </td>
                      <td className="py-2.5 px-4 text-ink-primary">{inv.client}</td>
                      <td className="py-2.5 px-4 text-ink-secondary truncate max-w-xs">{inv.memo || "—"}</td>
                      <td className="py-2.5 px-4 tabular-nums text-ink-secondary">
                        {formatDate(inv.due)}
                      </td>
                      <td className="py-2.5 px-4">
                        <span className="px-2 py-0.5 rounded bg-surface-muted text-ink-secondary text-xs border border-border">
                          {inv.source_status}
                        </span>
                      </td>
                      <td className="py-2.5 px-4">
                        <StatusBadge label={stat.label} variant={stat.variant} />
                      </td>
                      <td className="py-2.5 px-4 text-right font-semibold tabular-nums text-ink-primary">
                        {formatCurrency(inv.amount)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            </div>
          </div>

          {/* Mobile Stacked Cards */}
          <div className="md:hidden space-y-3">
            {filteredInvoices.slice(0, visibleLedgerCount).map((inv) => {
              const stat = getReconciledDisplayStatus(inv);
              return (
                <div
                  key={inv.invoice_no}
                  className="p-4 bg-surface border border-border rounded-xl shadow-xs space-y-2"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <span className="font-mono text-xs text-ink-muted">{inv.invoice_no}</span>
                      <h4 className="font-semibold text-sm text-ink-primary">{inv.client}</h4>
                      {inv.memo && <p className="text-xs text-ink-secondary mt-0.5">{inv.memo}</p>}
                    </div>
                    <span className="font-semibold text-base text-ink-primary tabular-nums">
                      {formatCurrency(inv.amount)}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-xs pt-2 border-t border-border/60 text-ink-secondary">
                    <span>Due: {formatDate(inv.due)}</span>
                    <StatusBadge label={stat.label} variant={stat.variant} />
                  </div>
                </div>
              );
            })}
          </div>

          {visibleLedgerCount < filteredInvoices.length && (
            <div className="text-center pt-2">
              <button
                type="button"
                onClick={() => setVisibleLedgerCount((prev) => prev + PAGE_SIZE)}
                className="inline-flex items-center gap-1.5 px-4 py-2 bg-surface border border-border rounded-lg text-xs font-medium text-ink-primary hover:bg-surface-muted cursor-pointer shadow-xs"
              >
                <span>Show more invoices</span>
                <ChevronDown className="w-3.5 h-3.5" />
              </button>
            </div>
          )}
        </section>
      )}

      {/* TAB 6: ALL BANK PAYMENTS LEDGER (NATURAL SCROLLING) */}
      {activeTab === "payments_ledger" && (
        <section className="space-y-3" aria-label="Payments ledger">
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <span className="text-xs text-ink-secondary">
              Showing {Math.min(visibleLedgerCount, filteredPayments.length)} of {filteredPayments.length} payments
            </span>
            <div className="relative max-w-xs w-full">
              <Search className="w-4 h-4 text-ink-muted absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search payment ID, payer, ref..."
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

          {/* Desktop Table */}
          <div className="hidden md:block bg-surface border border-border rounded-xl shadow-xs overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs sm:text-sm">
              <thead className="bg-surface-muted/50 border-b border-border text-ink-secondary text-xs font-semibold uppercase tracking-wider">
                <tr>
                  <th className="py-3 px-4">Payment ID</th>
                  <th className="py-3 px-4">Date</th>
                  <th className="py-3 px-4">Payer / Client</th>
                  <th className="py-3 px-4">Method</th>
                  <th className="py-3 px-4">Reference</th>
                  <th className="py-3 px-4">Match Type</th>
                  <th className="py-3 px-4 text-right">Amount</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {filteredPayments.slice(0, visibleLedgerCount).map((pay) => (
                  <tr key={pay.payment_id} className="hover:bg-surface-muted/40 transition-colors">
                    <td className="py-2.5 px-4 font-mono font-semibold text-ink-primary">
                      {pay.payment_id}
                    </td>
                    <td className="py-2.5 px-4 tabular-nums text-ink-secondary">
                      {formatDate(pay.payment_date)}
                    </td>
                    <td className="py-2.5 px-4 text-ink-primary">
                      <div>{pay.payer}</div>
                      {pay.client && pay.client !== pay.payer && (
                        <span className="text-[11px] text-brand font-medium block">
                          → {pay.client}
                        </span>
                      )}
                    </td>
                    <td className="py-2.5 px-4 text-ink-secondary uppercase text-xs font-medium">
                      {pay.method}
                    </td>
                    <td className="py-2.5 px-4 text-xs text-ink-secondary">
                      <span className="font-mono text-ink-primary">{pay.reference || "—"}</span>
                      {pay.allocation_note && (
                        <span className="block italic text-ink-muted">{pay.allocation_note}</span>
                      )}
                    </td>
                    <td className="py-2.5 px-4">
                      <StatusBadge
                        label={pay.reference_type}
                        variant={pay.reference_type === "exact_invoice_id" ? "success" : "info"}
                      />
                    </td>
                    <td className="py-2.5 px-4 text-right font-semibold tabular-nums text-ink-primary">
                      {formatCurrency(pay.amount)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            </div>
          </div>

          {/* Mobile Stacked Cards */}
          <div className="md:hidden space-y-3">
            {filteredPayments.slice(0, visibleLedgerCount).map((pay) => (
              <div
                key={pay.payment_id}
                className="p-4 bg-surface border border-border rounded-xl shadow-xs space-y-2 border-l-4 border-l-status-success"
              >
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <span className="font-mono text-xs text-ink-muted">{pay.payment_id}</span>
                    <h4 className="font-semibold text-sm text-ink-primary">{pay.payer}</h4>
                    {pay.client && pay.client !== pay.payer && (
                      <span className="text-xs text-brand font-medium block mt-0.5">
                        → {pay.client}
                      </span>
                    )}
                  </div>
                  <span className="font-semibold text-base text-status-success tabular-nums">
                    {formatCurrency(pay.amount)}
                  </span>
                </div>
                <div className="flex items-center justify-between text-xs pt-2 border-t border-border/60 text-ink-secondary">
                  <span>{formatDate(pay.payment_date)} • {pay.method}</span>
                  <StatusBadge
                    label={pay.reference_type}
                    variant={pay.reference_type === "exact_invoice_id" ? "success" : "info"}
                  />
                </div>
              </div>
            ))}
          </div>

          {visibleLedgerCount < filteredPayments.length && (
            <div className="text-center pt-2">
              <button
                type="button"
                onClick={() => setVisibleLedgerCount((prev) => prev + PAGE_SIZE)}
                className="inline-flex items-center gap-1.5 px-4 py-2 bg-surface border border-border rounded-lg text-xs font-medium text-ink-primary hover:bg-surface-muted cursor-pointer shadow-xs"
              >
                <span>Show more payments</span>
                <ChevronDown className="w-3.5 h-3.5" />
              </button>
            </div>
          )}
        </section>
      )}

      {/* 3. SCOPE LIMITATION / EXCLUSIONS NOTE */}
      <div className="p-4 bg-surface border border-border rounded-xl text-xs text-ink-secondary space-y-1">
        <span className="font-semibold text-ink-primary block">
          Accounting Scope & Exclusions:
        </span>
        <p className="leading-relaxed">
          Facility overhead (studio lease, utilities, equipment depreciation) and owner draws are not recorded in <code className="font-mono text-ink-primary bg-surface-muted px-1.5 py-0.5 rounded">costs.csv</code>. Figures represent direct commercial client receivables and bank deposits only.
        </p>
      </div>
    </div>
  );
}
