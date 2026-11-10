"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  Calendar,
  Users,
  Inbox,
  Film,
  CircleDollarSign,
  Plus,
  RotateCw,
  Trash2,
  AlertTriangle,
  Loader2,
  X,
  Search,
  ArrowRight,
  Check,
} from "lucide-react";
import { AddFilesModal } from "./AddFilesModal";
import { api, notifyDataRefreshed, notifyReferenceDateChanged, ReferenceDateInfo } from "@/lib/api";

interface AppShellProps {
  children: React.ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  const pathname = usePathname();
  const router = useRouter();
  const [isAddFilesOpen, setIsAddFilesOpen] = useState(false);
  const [healthStatus, setHealthStatus] = useState<"checking" | "connected" | "disconnected">("checking");
  const [referenceDate, setReferenceDate] = useState<string>("Oct 6, 2026");
  const [refDateInfo, setRefDateInfo] = useState<ReferenceDateInfo | null>(null);
  const [isDateModalOpen, setIsDateModalOpen] = useState(false);
  const [selectedDateInput, setSelectedDateInput] = useState<string>("");
  const [isUpdatingDate, setIsUpdatingDate] = useState(false);
  const [dateError, setDateError] = useState<string | null>(null);

  // Delete all files state
  const [isConfirmDeleteOpen, setIsConfirmDeleteOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const handleDeleteAllFiles = async () => {
    try {
      setIsDeleting(true);
      setDeleteError(null);
      await api.resetDatabase();
      notifyDataRefreshed();
      setIsConfirmDeleteOpen(false);
      if (typeof window !== "undefined") {
        window.location.reload();
      }
    } catch (err: any) {
      setDeleteError(err.message || "Failed to delete files.");
    } finally {
      setIsDeleting(false);
    }
  };

  // Global Search Modal state
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<
    Array<{
      type: string;
      id: string;
      title: string;
      subtitle: string;
      source: string;
      href: string;
    }>
  >([]);
  const [isSearching, setIsSearching] = useState(false);
  const searchInputRef = useRef<HTMLInputElement>(null);

  const loadReferenceDateInfo = useCallback(async () => {
    try {
      const info = await api.getReferenceDate();
      setRefDateInfo(info);
      setReferenceDate(info.reference_date);
      setSelectedDateInput(info.reference_date);
    } catch {
      // fallback
    }
  }, []);

  const checkConnection = useCallback(() => {
    setHealthStatus("checking");
    api
      .getHealth()
      .then((res) => {
        setHealthStatus("connected");
        if (res.reference_date) {
          setReferenceDate(res.reference_date);
        }
      })
      .catch(() => {
        setHealthStatus("disconnected");
      });
    loadReferenceDateInfo();
  }, [loadReferenceDateInfo]);

  const handleApplyReferenceDate = async (targetDate: string) => {
    if (isUpdatingDate) return;
    setIsUpdatingDate(true);
    setDateError(null);
    try {
      const res = await api.setReferenceDate(targetDate);
      setReferenceDate(res.reference_date);
      await loadReferenceDateInfo();
      notifyReferenceDateChanged(res.reference_date);
      setIsDateModalOpen(false);
    } catch (err: any) {
      setDateError(err.message || "Failed to update calculation reference date.");
    } finally {
      setIsUpdatingDate(false);
    }
  };

  useEffect(() => {
    checkConnection();

    const handleOpenModal = () => setIsAddFilesOpen(true);
    const handleOpenDateModal = () => {
      setDateError(null);
      setIsDateModalOpen(true);
    };

    window.addEventListener("axeom:open-upload-modal", handleOpenModal);
    window.addEventListener("axeom:open-date-modal", handleOpenDateModal);

    return () => {
      window.removeEventListener("axeom:open-upload-modal", handleOpenModal);
      window.removeEventListener("axeom:open-date-modal", handleOpenDateModal);
    };
  }, [checkConnection]);

  // Keyboard shortcuts: Cmd/Ctrl+K for global search, Escape to close modals
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setIsSearchOpen((prev) => !prev);
      } else if (e.key === "Escape") {
        if (isSearchOpen) {
          setIsSearchOpen(false);
        } else if (isDateModalOpen && !isUpdatingDate) {
          setIsDateModalOpen(false);
          setDateError(null);
        }
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isSearchOpen, isDateModalOpen, isUpdatingDate]);

  useEffect(() => {
    if (isSearchOpen) {
      setTimeout(() => searchInputRef.current?.focus(), 50);
    } else {
      setSearchQuery("");
      setSearchResults([]);
    }
  }, [isSearchOpen]);

  useEffect(() => {
    const q = searchQuery.trim();
    if (q.length < 2) {
      setSearchResults([]);
      setIsSearching(false);
      return;
    }
    let cancelled = false;
    setIsSearching(true);
    const timer = setTimeout(() => {
      api
        .searchGlobal(q)
        .then((res) => {
          if (!cancelled) {
            setSearchResults(res.results || []);
          }
        })
        .catch(() => {
          if (!cancelled) {
            setSearchResults([]);
          }
        })
        .finally(() => {
          if (!cancelled) {
            setIsSearching(false);
          }
        });
    }, 150);

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [searchQuery]);

  const navItems = [
    { href: "/today", label: "Today", icon: Calendar },
    { href: "/clients", label: "Clients", icon: Users },
    { href: "/requests", label: "Requests", icon: Inbox },
    { href: "/production", label: "Production", icon: Film },
    { href: "/money", label: "Money", icon: CircleDollarSign },
  ];

  const isActive = (href: string) => {
    if (href === "/today" && (pathname === "/" || pathname === "/today")) return true;
    return pathname.startsWith(href);
  };

  return (
    <div className="min-h-screen flex flex-col lg:flex-row bg-canvas text-ink-primary antialiased selection:bg-brand-soft selection:text-brand overflow-x-hidden w-full">
      {/* DESKTOP EDITORIAL SIDEBAR (248px, deep charcoal-green #202B28, fixed full-height) */}
      <aside className="hidden lg:flex flex-col w-[248px] bg-sidebar-bg text-sidebar-text select-none shrink-0 fixed left-0 top-0 bottom-0 h-screen border-r border-[#2C3B37] z-30 overflow-y-auto no-scrollbar">
        {/* Workspace Brand Header */}
        <div className="px-6 py-5 border-b border-[#2C3B37] space-y-3">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-brand text-white flex items-center justify-center font-bold text-xs tracking-wider shadow-sm">
              AX
            </div>
            <div>
              <div className="flex items-center gap-1.5 leading-none">
                <span className="font-semibold text-sidebar-text text-sm tracking-tight">Axeom</span>
                <span className="text-sidebar-muted text-xs font-normal">StudioOS</span>
              </div>
              <button
                type="button"
                onClick={() => {
                  setDateError(null);
                  setIsDateModalOpen(true);
                }}
                className="group mt-1 flex items-center gap-1.5 px-2 py-0.5 rounded-md bg-white/6 hover:bg-white/12 border border-white/10 text-left transition-colors cursor-pointer text-xs"
                title="Click to change calculation reference date"
              >
                <Calendar className="w-3 h-3 text-brand shrink-0" />
                <span className="text-[11px] font-medium text-sidebar-text truncate">
                  As of {refDateInfo?.reference_date || referenceDate}
                </span>
                <span className="text-[9px] uppercase tracking-wider font-semibold px-1 py-0.2 rounded bg-brand/30 text-brand shrink-0">
                  {refDateInfo?.is_today
                    ? "Today"
                    : refDateInfo?.reference_date === "2026-10-06" || referenceDate === "2026-10-06"
                    ? "Baseline"
                    : "Custom"}
                </span>
              </button>
            </div>
          </div>

          {/* Global Search Trigger */}
          <button
            type="button"
            onClick={() => setIsSearchOpen(true)}
            className="w-full flex items-center justify-between px-3 py-2 rounded-lg bg-white/8 hover:bg-white/12 text-sidebar-muted hover:text-sidebar-text text-xs transition-colors cursor-pointer border border-white/10"
          >
            <span className="inline-flex items-center gap-2">
              <Search className="w-3.5 h-3.5" />
              <span>Search all records...</span>
            </span>
            <kbd className="text-[10px] px-1.5 py-0.5 rounded bg-black/25 text-sidebar-muted font-mono">⌘K</kbd>
          </button>
        </div>

        {/* Primary Navigation */}
        <nav className="flex-1 px-3 py-4 space-y-1" aria-label="Main navigation">
          {navItems.map((item) => {
            const Icon = item.icon;
            const active = isActive(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={`flex items-center gap-3.5 px-3.5 py-2.5 rounded-lg text-sm transition-colors ${
                  active
                    ? "bg-white/10 text-white font-medium border-l-2 border-brand pl-3"
                    : "text-sidebar-muted hover:text-sidebar-text hover:bg-white/5"
                }`}
              >
                <Icon className={`w-4 h-4 shrink-0 ${active ? "text-brand" : "text-sidebar-muted"}`} />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>

        {/* Workspace Footer Action: Add data files and Red Delete all files */}
        <div className="p-4 border-t border-[#2C3B37] space-y-2">
          <button
            onClick={() => setIsAddFilesOpen(true)}
            className="w-full flex items-center justify-center gap-2 px-3.5 py-2.5 bg-brand hover:bg-brand-hover text-white text-sm font-medium rounded-lg transition-colors cursor-pointer shadow-sm"
          >
            <Plus className="w-4 h-4" />
            <span>Add data files</span>
          </button>

          {/* Delete All Files (Red button) */}
          <button
            type="button"
            onClick={() => {
              setDeleteError(null);
              setIsConfirmDeleteOpen(true);
            }}
            className="w-full flex items-center justify-center gap-2 px-3 py-2 bg-red-900/30 hover:bg-red-900/60 text-red-300 hover:text-white border border-red-800/50 rounded-lg text-xs font-medium transition-colors cursor-pointer"
            title="Delete all files from database"
          >
            <Trash2 className="w-3.5 h-3.5" />
            <span>Delete all files</span>
          </button>

          {/* Connection status indicator (quiet) */}
          {healthStatus === "disconnected" && (
            <div className="pt-1 flex items-center justify-between text-xs text-status-critical px-1 bg-red-950/40 border border-red-900/60 rounded-md p-1.5">
              <div className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-status-critical shrink-0" />
                <span className="text-xs">Backend disconnected</span>
              </div>
              <button
                onClick={checkConnection}
                className="text-[11px] text-brand hover:underline flex items-center gap-1 cursor-pointer font-medium"
              >
                <RotateCw className="w-3 h-3" />
                <span>Retry</span>
              </button>
            </div>
          )}
        </div>
      </aside>

      {/* MOBILE / TABLET TOP BAR (Warm surface, AX brand, Scenario Date, Search, and Add files) */}
      <header className="lg:hidden flex items-center justify-between px-3 sm:px-4 py-2.5 bg-surface border-b border-border sticky top-0 z-30 shadow-xs gap-2 min-w-0">
        <div className="flex items-center gap-2 min-w-0 flex-1">
          <div className="w-7 h-7 rounded-lg bg-brand text-white flex items-center justify-center font-bold text-xs shrink-0 shadow-2xs">
            AX
          </div>
          <div className="min-w-0 flex-1">
            <span className="font-semibold text-sm text-ink-primary leading-tight truncate block">
              Axeom StudioOS
            </span>
            <button
              type="button"
              onClick={() => {
                setDateError(null);
                setIsDateModalOpen(true);
              }}
              className="flex items-center gap-1 text-[11px] text-ink-muted hover:text-ink-primary font-medium cursor-pointer -mt-0.5 min-w-0 max-w-full"
              title="Click to change scenario reference date"
            >
              <span className="truncate">As of {refDateInfo?.reference_date || referenceDate}</span>
              <span className="text-[9px] px-1 py-0.2 rounded bg-brand-soft text-brand font-semibold shrink-0">
                {refDateInfo?.reference_date === "2026-10-06" || referenceDate === "2026-10-06"
                  ? "Baseline"
                  : refDateInfo?.is_today
                  ? "Today"
                  : "Custom"}
              </span>
            </button>
          </div>
        </div>

        <div className="flex items-center gap-1 sm:gap-1.5 shrink-0">
          <button
            type="button"
            onClick={() => setIsSearchOpen(true)}
            className="p-1.5 sm:p-2 rounded-lg bg-surface-muted text-ink-secondary hover:text-ink-primary border border-border cursor-pointer transition-colors"
            aria-label="Search records"
            title="Search all records (Cmd+K)"
          >
            <Search className="w-4 h-4" />
          </button>

          <button
            type="button"
            onClick={() => {
              setDeleteError(null);
              setIsConfirmDeleteOpen(true);
            }}
            className="flex items-center gap-1 p-1.5 sm:px-2.5 sm:py-1.5 bg-status-critical-bg hover:bg-status-critical text-status-critical hover:text-white border border-status-critical-border text-xs font-medium rounded-lg cursor-pointer transition-colors shadow-2xs"
            title="Delete all files"
            aria-label="Delete all files"
          >
            <Trash2 className="w-4 h-4 sm:w-3.5 sm:h-3.5" />
            <span className="hidden sm:inline">Delete all</span>
          </button>

          <button
            onClick={() => setIsAddFilesOpen(true)}
            className="flex items-center gap-1 px-2.5 py-1.5 sm:px-3 sm:py-1.5 bg-brand hover:bg-brand-hover text-white text-xs font-medium rounded-lg cursor-pointer transition-colors shadow-xs"
            aria-label="Add files"
          >
            <Plus className="w-4 h-4 sm:w-3.5 sm:h-3.5" />
            <span>Add<span className="hidden sm:inline"> files</span></span>
          </button>
        </div>
      </header>

      {/* MAIN CONTENT AREA: Max 1440px, centered with generous padding and warm paper canvas, offset for fixed sidebar */}
      <div className="flex-1 flex flex-col min-w-0 lg:pl-[248px] w-full">
        <main className="flex-1 w-full max-w-[1440px] mx-auto px-4 sm:px-6 lg:px-10 py-6 sm:py-8 pb-28 lg:pb-12 min-w-0 overflow-x-hidden">
          {children}
        </main>
      </div>

      {/* MOBILE / TABLET FIXED BOTTOM NAVIGATION: 5 items, >=44px touch targets, safe-area insets */}
      <nav
        className="lg:hidden fixed bottom-0 left-0 right-0 bg-surface border-t border-border z-30 pb-[env(safe-area-inset-bottom)] shadow-lg"
        aria-label="Mobile navigation"
      >
        <div className="grid grid-cols-5 h-16">
          {navItems.map((item) => {
            const Icon = item.icon;
            const active = isActive(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={`flex flex-col items-center justify-center min-h-[44px] transition-colors ${
                  active ? "text-brand font-medium" : "text-ink-secondary hover:text-ink-primary"
                }`}
              >
                <Icon className={`w-5 h-5 ${active ? "text-brand" : "text-ink-secondary/80"}`} />
                <span className="text-[12px] mt-1">{item.label}</span>
              </Link>
            );
          })}
        </div>
      </nav>

      {/* SINGLE GLOBAL ADD FILES MODAL INSTANCE */}
      <AddFilesModal
        isOpen={isAddFilesOpen}
        onClose={() => setIsAddFilesOpen(false)}
      />

      {/* GLOBAL RECORD SEARCH MODAL */}
      {isSearchOpen && (
        <div
          className="fixed inset-0 z-50 flex items-start justify-center bg-black/45 backdrop-blur-xs p-4 pt-16 sm:pt-24 animate-in fade-in duration-150"
          role="dialog"
          aria-modal="true"
          aria-label="Global record search"
        >
          <div className="bg-surface rounded-2xl shadow-2xl w-full max-w-xl border border-border overflow-hidden flex flex-col max-h-[75vh]">
            <div className="flex items-center gap-3 px-4 py-3.5 border-b border-border">
              <Search className="w-4 h-4 text-brand shrink-0" />
              <input
                ref={searchInputRef}
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search clients, people, leads, invoices, payments, bookings, videos, messages..."
                className="flex-1 bg-transparent text-sm text-ink-primary placeholder:text-ink-muted focus:outline-none"
              />
              {isSearching && <Loader2 className="w-4 h-4 text-brand animate-spin shrink-0" />}
              <button
                type="button"
                onClick={() => setIsSearchOpen(false)}
                className="p-1 rounded-lg text-ink-secondary hover:text-ink-primary hover:bg-canvas transition-colors cursor-pointer"
                aria-label="Close search"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="p-3 overflow-y-auto flex-1 divide-y divide-border text-xs">
              {searchQuery.trim().length < 2 ? (
                <div className="py-8 text-center text-ink-muted">
                  Type at least 2 characters to search across all studio tables with source provenance.
                </div>
              ) : searchResults.length === 0 && !isSearching ? (
                <div className="py-8 text-center text-ink-muted">
                  No matching records found for &ldquo;{searchQuery}&rdquo;.
                </div>
              ) : (
                searchResults.map((item, idx) => (
                  <button
                    key={`${item.type}-${item.id}-${idx}`}
                    type="button"
                    onClick={() => {
                      setIsSearchOpen(false);
                      router.push(item.href);
                    }}
                    className="w-full text-left p-3 hover:bg-surface-muted/70 transition-colors flex items-center justify-between gap-3 cursor-pointer"
                  >
                    <div className="space-y-0.5 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="uppercase text-[10px] font-semibold px-1.5 py-0.5 rounded bg-brand-soft text-brand">
                          {item.type}
                        </span>
                        <span className="font-semibold text-ink-primary truncate">{item.title}</span>
                      </div>
                      <p className="text-ink-secondary truncate">{item.subtitle}</p>
                      <p className="text-[11px] text-ink-muted font-mono">Source: {item.source}</p>
                    </div>
                    <ArrowRight className="w-4 h-4 text-ink-muted shrink-0" />
                  </button>
                ))
              )}
            </div>
          </div>
        </div>
      )}

      {/* REFERENCE DATE SELECTOR MODAL */}
      {isDateModalOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 backdrop-blur-xs p-4 animate-in fade-in duration-150"
          role="dialog"
          aria-modal="true"
          aria-labelledby="ref-date-modal-title"
        >
          <div className="bg-surface rounded-2xl shadow-xl w-full max-w-lg border border-border overflow-hidden">
            <div className="flex items-center justify-between px-5 py-4 border-b border-border bg-canvas/40">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-full bg-brand-soft text-brand flex items-center justify-center shrink-0">
                  <Calendar className="w-4 h-4" />
                </div>
                <div>
                  <h2 id="ref-date-modal-title" className="text-base font-semibold text-ink-primary">
                    Calculation Reference Date
                  </h2>
                  <p className="text-xs text-ink-secondary">
                    Dynamic cutoff for overdue invoices, days late, and churn signals
                  </p>
                </div>
              </div>
              {!isUpdatingDate && (
                <button
                  onClick={() => {
                    setIsDateModalOpen(false);
                    setDateError(null);
                  }}
                  className="p-1 rounded-lg text-ink-secondary hover:text-ink-primary hover:bg-canvas transition-colors cursor-pointer"
                  aria-label="Close dialog"
                >
                  <X className="w-4 h-4" />
                </button>
              )}
            </div>

            <div className="p-5 space-y-4 text-sm text-ink-secondary leading-relaxed">
              {/* Option 1: Detected Today Date via Date API */}
              <div className="p-3.5 rounded-xl border border-border bg-canvas/60 space-y-2">
                <div className="flex items-start justify-between gap-3">
                  <div className="space-y-0.5">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-ink-primary">Today (Date API at your location)</span>
                      {refDateInfo?.is_today && (
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-status-success-bg text-status-success border border-status-success-border">
                          Active
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-ink-muted">
                      Source: {refDateInfo?.source || "timeapi.io (IP located Africa/Johannesburg)"}
                    </p>
                    <div className="text-base font-semibold text-ink-primary pt-1">
                      {refDateInfo?.location_date || "2026-11-09"}
                    </div>
                  </div>
                  <button
                    type="button"
                    disabled={isUpdatingDate || refDateInfo?.is_today}
                    onClick={() => handleApplyReferenceDate("today")}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-brand hover:bg-brand-hover text-white text-xs font-medium disabled:opacity-50 transition-colors cursor-pointer shrink-0 shadow-xs"
                  >
                    {refDateInfo?.is_today ? (
                      <>
                        <Check className="w-3.5 h-3.5" />
                        <span>Active</span>
                      </>
                    ) : (
                      <span>Use Today</span>
                    )}
                  </button>
                </div>
              </div>

              {/* Option 2: Challenge Baseline Date */}
              <div className="p-3.5 rounded-xl border border-border bg-canvas/60 space-y-2">
                <div className="flex items-start justify-between gap-3">
                  <div className="space-y-0.5">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-ink-primary">Pack 213 Baseline Date</span>
                      {refDateInfo?.reference_date === "2026-10-06" && (
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-status-success-bg text-status-success border border-status-success-border">
                          Active
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-ink-muted">
                      Original dataset baseline: 8 reconciled overdue invoices ($9,505.00)
                    </p>
                    <div className="text-base font-semibold text-ink-primary pt-1">
                      2026-10-06
                    </div>
                  </div>
                  <button
                    type="button"
                    disabled={isUpdatingDate || refDateInfo?.reference_date === "2026-10-06"}
                    onClick={() => handleApplyReferenceDate("2026-10-06")}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface hover:bg-canvas text-ink-primary border border-border text-xs font-medium disabled:opacity-50 transition-colors cursor-pointer shrink-0 shadow-2xs"
                  >
                    {refDateInfo?.reference_date === "2026-10-06" ? (
                      <>
                        <Check className="w-3.5 h-3.5 text-status-success" />
                        <span>Active</span>
                      </>
                    ) : (
                      <span>Use Baseline</span>
                    )}
                  </button>
                </div>
              </div>

              {/* Option 3: Custom Reference Date Picker */}
              <div className="p-3.5 rounded-xl border border-border bg-canvas/60 space-y-2.5">
                <label htmlFor="custom-ref-date-input" className="font-semibold text-ink-primary block text-xs">
                  Custom Reference Date:
                </label>
                <div className="flex items-center gap-2">
                  <input
                    id="custom-ref-date-input"
                    type="date"
                    value={selectedDateInput}
                    onChange={(e) => setSelectedDateInput(e.target.value)}
                    className="flex-1 px-3 py-1.5 rounded-lg bg-surface border border-border text-sm text-ink-primary focus:outline-none focus:ring-2 focus:ring-brand"
                  />
                  <button
                    type="button"
                    disabled={isUpdatingDate || !selectedDateInput}
                    onClick={() => handleApplyReferenceDate(selectedDateInput)}
                    className="inline-flex items-center gap-1.5 px-3.5 py-1.5 bg-ink-primary hover:bg-ink-primary/90 text-white text-xs font-semibold rounded-lg disabled:opacity-50 transition-colors cursor-pointer shadow-xs"
                  >
                    {isUpdatingDate ? (
                      <>
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        <span>Calculating...</span>
                      </>
                    ) : (
                      <span>Apply Date</span>
                    )}
                  </button>
                </div>
              </div>

              {dateError && (
                <div className="p-3 rounded-xl bg-status-critical-bg border border-status-critical-border text-status-critical text-xs flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 shrink-0" />
                  <span>{dateError}</span>
                </div>
              )}
            </div>

            <div className="px-5 py-3 bg-canvas border-t border-border flex items-center justify-between text-xs text-ink-muted">
              <span>All numbers across Money, Today, Clients update immediately.</span>
              <button
                type="button"
                disabled={isUpdatingDate}
                onClick={() => {
                  setIsDateModalOpen(false);
                  setDateError(null);
                }}
                className="px-3 py-1.5 text-ink-secondary hover:text-ink-primary font-medium cursor-pointer"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* CONFIRM DELETE ALL FILES MODAL */}
      {isConfirmDeleteOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/55 backdrop-blur-xs p-4 animate-in fade-in duration-150"
          role="dialog"
          aria-modal="true"
          aria-label="Confirm delete all files"
        >
          <div className="bg-surface rounded-2xl shadow-2xl w-full max-w-md border border-border overflow-hidden p-6 space-y-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-status-critical-bg text-status-critical flex items-center justify-center shrink-0">
                <Trash2 className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-base font-semibold text-ink-primary">Delete all studio files?</h3>
                <p className="text-xs text-ink-secondary">This action will clear all records from the database.</p>
              </div>
            </div>

            {deleteError && (
              <div className="p-3 bg-status-critical-bg border border-status-critical-border text-status-critical text-xs rounded-lg">
                {deleteError}
              </div>
            )}

            <p className="text-xs sm:text-sm text-ink-secondary leading-relaxed">
              Are you sure you want to delete all files? This will truncate all tables in the database (leads, bookings, invoices, payments, production videos, messages, etc.) and reset all imported data.
            </p>

            <div className="flex items-center justify-end gap-2.5 pt-2">
              <button
                type="button"
                onClick={() => setIsConfirmDeleteOpen(false)}
                disabled={isDeleting}
                className="px-4 py-2 text-xs font-medium text-ink-secondary hover:text-ink-primary bg-surface border border-border rounded-lg cursor-pointer hover:bg-surface-muted transition-colors disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleDeleteAllFiles}
                disabled={isDeleting}
                className="flex items-center gap-1.5 px-4 py-2 text-xs font-medium text-white bg-status-critical hover:bg-red-700 rounded-lg cursor-pointer transition-colors shadow-xs disabled:opacity-50"
              >
                {isDeleting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Trash2 className="w-3.5 h-3.5" />}
                <span>{isDeleting ? "Deleting..." : "Yes, delete all files"}</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
