"use client";

import React, { useState } from "react";
import {
  BarChart3,
  TrendingUp,
  DollarSign,
  Users,
} from "lucide-react";
import { formatCurrency } from "@/lib/api";

export interface ChannelMetric {
  source: string;
  total_leads: number;
  won_leads: number;
  lost_leads: number;
  unreplied_leads: number;
  new_leads: number;
  conversion_rate: number;
  clients_acquired: number;
  direct_booking_revenue: number;
}

interface AcquisitionChannelChartProps {
  metrics: ChannelMetric[];
  bestChannelName?: string;
}

export function AcquisitionChannelChart({
  metrics,
  bestChannelName,
}: AcquisitionChannelChartProps) {
  const [activeMetric, setActiveMetric] = useState<"leads" | "rate" | "revenue">("leads");

  if (!metrics || metrics.length === 0) return null;

  // Maximum values for proportional bar scaling
  const maxLeads = Math.max(...metrics.map((m) => m.total_leads), 1);
  const maxRate = Math.max(...metrics.map((m) => m.conversion_rate), 100);
  const maxRevenue = Math.max(...metrics.map((m) => m.direct_booking_revenue), 1);

  // Totals
  const totalLeads = metrics.reduce((acc, m) => acc + m.total_leads, 0);
  const totalWon = metrics.reduce((acc, m) => acc + m.won_leads, 0);
  const totalLost = metrics.reduce((acc, m) => acc + m.lost_leads, 0);
  const totalUnreplied = metrics.reduce((acc, m) => acc + m.unreplied_leads, 0);
  const totalRevenue = metrics.reduce((acc, m) => acc + m.direct_booking_revenue, 0);

  return (
    <div className="bg-surface border border-border rounded-xl shadow-xs overflow-hidden space-y-4 p-4 sm:p-5">
      {/* Header with Metric Selector Tabs */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-border">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-brand-soft text-brand flex items-center justify-center shrink-0">
            <BarChart3 className="w-4 h-4" />
          </div>
          <div>
            <h3 className="font-semibold text-sm sm:text-base text-ink-primary">
              Channel Performance Comparison Chart
            </h3>
            <p className="text-xs text-ink-secondary">
              Visual benchmark of all 6 acquisition platforms
            </p>
          </div>
        </div>

        {/* View Toggle Tabs (Responsive wrap/scroll) */}
        <div className="flex items-center gap-1 bg-surface-muted p-1 rounded-lg self-start sm:self-auto overflow-x-auto max-w-full">
          <button
            type="button"
            onClick={() => setActiveMetric("leads")}
            className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors cursor-pointer inline-flex items-center gap-1.5 whitespace-nowrap ${
              activeMetric === "leads"
                ? "bg-surface text-ink-primary font-semibold shadow-2xs"
                : "text-ink-secondary hover:text-ink-primary"
            }`}
          >
            <Users className="w-3.5 h-3.5" />
            <span>Leads (Won vs Lost)</span>
          </button>
          <button
            type="button"
            onClick={() => setActiveMetric("rate")}
            className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors cursor-pointer inline-flex items-center gap-1.5 whitespace-nowrap ${
              activeMetric === "rate"
                ? "bg-surface text-ink-primary font-semibold shadow-2xs"
                : "text-ink-secondary hover:text-ink-primary"
            }`}
          >
            <TrendingUp className="w-3.5 h-3.5" />
            <span>Win Rate %</span>
          </button>
          <button
            type="button"
            onClick={() => setActiveMetric("revenue")}
            className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors cursor-pointer inline-flex items-center gap-1.5 whitespace-nowrap ${
              activeMetric === "revenue"
                ? "bg-surface text-ink-primary font-semibold shadow-2xs"
                : "text-ink-secondary hover:text-ink-primary"
            }`}
          >
            <DollarSign className="w-3.5 h-3.5" />
            <span>Revenue Attributed</span>
          </button>
        </div>
      </div>

      {/* Legend */}
      {activeMetric === "leads" && (
        <div className="flex items-center gap-4 text-xs text-ink-secondary flex-wrap pt-1">
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-xs bg-status-success shrink-0" />
            <span>Won Leads ({totalWon})</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-xs bg-status-critical shrink-0" />
            <span>Lost Leads ({totalLost})</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-xs bg-status-warning shrink-0" />
            <span>Never Replied ({totalUnreplied})</span>
          </div>
        </div>
      )}

      {/* BARS CONTAINER (Responsive Horizontal Bars - optimal for all screen sizes) */}
      <div className="space-y-3.5 pt-1">
        {metrics.map((ch) => {
          const isTop = ch.source === bestChannelName;
          const wonPct = ch.total_leads > 0 ? (ch.won_leads / ch.total_leads) * 100 : 0;
          const lostPct = ch.total_leads > 0 ? (ch.lost_leads / ch.total_leads) * 100 : 0;
          const unrepliedPct = ch.total_leads > 0 ? (ch.unreplied_leads / ch.total_leads) * 100 : 0;
          const barWidthScale = (ch.total_leads / maxLeads) * 100;
          const rateWidthScale = Math.min(100, Math.max(0, (ch.conversion_rate / maxRate) * 100));
          const revWidthScale = maxRevenue > 0 ? (ch.direct_booking_revenue / maxRevenue) * 100 : 0;

          return (
            <div
              key={ch.source}
              className={`p-3 rounded-xl border transition-colors ${
                isTop
                  ? "bg-brand-soft/20 border-brand/30"
                  : "bg-surface-muted/30 border-border/80 hover:bg-surface-muted/50"
              }`}
            >
              {/* Channel Label & Top Badge */}
              <div className="flex items-center justify-between text-xs sm:text-sm font-semibold text-ink-primary mb-1.5 gap-2">
                <div className="flex items-center gap-2">
                  <span>{ch.source}</span>
                  {isTop && (
                    <span className="px-1.5 py-0.5 rounded text-[10px] bg-brand text-white font-bold uppercase tracking-wider">
                      Best Conversion ({ch.conversion_rate}%)
                    </span>
                  )}
                </div>

                {/* Right side value display depending on active tab */}
                <div className="text-right tabular-nums">
                  {activeMetric === "leads" && (
                    <span className="font-semibold text-ink-primary">
                      {ch.total_leads} leads{" "}
                      <span className="text-xs text-ink-muted font-normal">
                        ({ch.won_leads} won · {ch.lost_leads} lost)
                      </span>
                    </span>
                  )}
                  {activeMetric === "rate" && (
                    <span className="font-bold text-brand text-sm sm:text-base">
                      {ch.conversion_rate}%
                    </span>
                  )}
                  {activeMetric === "revenue" && (
                    <span className="font-bold text-brand text-sm sm:text-base">
                      {formatCurrency(ch.direct_booking_revenue)}
                    </span>
                  )}
                </div>
              </div>

              {/* Progress / Bar Chart Representation */}
              {activeMetric === "leads" && (
                <div className="space-y-1">
                  {/* Proportional Segmented Bar */}
                  <div className="h-4 w-full bg-surface-muted rounded-md overflow-hidden flex shadow-inner">
                    <div
                      style={{ width: `${barWidthScale}%` }}
                      className="h-full flex rounded-md overflow-hidden"
                    >
                      {ch.won_leads > 0 && (
                        <div
                          style={{ width: `${wonPct}%` }}
                          className="bg-status-success h-full transition-all duration-300"
                          title={`Won: ${ch.won_leads}`}
                        />
                      )}
                      {ch.lost_leads > 0 && (
                        <div
                          style={{ width: `${lostPct}%` }}
                          className="bg-status-critical h-full transition-all duration-300"
                          title={`Lost: ${ch.lost_leads}`}
                        />
                      )}
                      {ch.unreplied_leads > 0 && (
                        <div
                          style={{ width: `${unrepliedPct}%` }}
                          className="bg-status-warning h-full transition-all duration-300"
                          title={`Never Replied: ${ch.unreplied_leads}`}
                        />
                      )}
                    </div>
                  </div>
                  <div className="flex items-center justify-between text-[11px] text-ink-secondary">
                    <span>
                      {((ch.total_leads / (totalLeads || 1)) * 100).toFixed(1)}% of total reach
                    </span>
                    <span className="text-ink-muted">
                      {ch.unreplied_leads > 0 ? `${ch.unreplied_leads} unreplied` : "0 unreplied"}
                    </span>
                  </div>
                </div>
              )}

              {activeMetric === "rate" && (
                <div className="space-y-1">
                  <div className="h-3 w-full bg-surface-muted rounded-full overflow-hidden">
                    <div
                      style={{ width: `${rateWidthScale}%` }}
                      className={`h-full rounded-full transition-all duration-300 ${
                        isTop ? "bg-brand" : ch.conversion_rate >= 50 ? "bg-status-success" : "bg-ink-secondary"
                      }`}
                    />
                  </div>
                  <div className="flex items-center justify-between text-[11px] text-ink-secondary">
                    <span>
                      {ch.won_leads} won / {ch.total_leads} leads
                    </span>
                    <span className="text-ink-muted">
                      {ch.clients_acquired} client{ch.clients_acquired === 1 ? "" : "s"} acquired
                    </span>
                  </div>
                </div>
              )}

              {activeMetric === "revenue" && (
                <div className="space-y-1">
                  <div className="h-3 w-full bg-surface-muted rounded-full overflow-hidden">
                    <div
                      style={{ width: `${revWidthScale}%` }}
                      className={`h-full rounded-full transition-all duration-300 ${
                        isTop ? "bg-brand" : "bg-status-info"
                      }`}
                    />
                  </div>
                  <div className="flex items-center justify-between text-[11px] text-ink-secondary">
                    <span>
                      {totalRevenue > 0
                        ? `${((ch.direct_booking_revenue / totalRevenue) * 100).toFixed(1)}% of studio revenue`
                        : "0%"}
                    </span>
                    <span className="text-ink-muted">
                      {formatCurrency(ch.direct_booking_revenue / (ch.won_leads || 1))} / won lead avg
                    </span>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
