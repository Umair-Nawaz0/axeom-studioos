"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import {
  Upload,
  X,
  CheckCircle2,
  AlertTriangle,
  FileText,
  Loader2,
  Trash2,
  Plus,
  AlertCircle,
  History,
  Database,
} from "lucide-react";
import { api, UploadResult, notifyDataRefreshed } from "@/lib/api";

interface AddFilesModalProps {
  isOpen: boolean;
  onClose: () => void;
  onImportComplete?: () => void;
}

// Global helper to open the upload modal from any page
export function triggerGlobalUploadModal() {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent("axeom:open-upload-modal"));
  }
}

export function AddFilesModal({ isOpen, onClose, onImportComplete }: AddFilesModalProps) {
  const [stage, setStage] = useState<"select" | "preview" | "importing" | "result">("select");
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [previewResults, setPreviewResults] = useState<UploadResult[]>([]);
  const [isPreviewLoading, setIsPreviewLoading] = useState(false);
  const [results, setResults] = useState<UploadResult[]>([]);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [confirmingReset, setConfirmingReset] = useState(false);
  const [isResetting, setIsResetting] = useState(false);
  const [resetSuccessMsg, setResetSuccessMsg] = useState<string | null>(null);
  const [historyData, setHistoryData] = useState<{
    events: Array<{
      timestamp: string;
      filename: string;
      file_type: string;
      rows_processed: number;
      rows_inserted: number;
      rows_updated: number;
      rows_skipped: number;
      rejected_count: number;
      warnings_count: number;
      message: string;
    }>;
    current_table_counts: Record<string, number>;
  } | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const modalRef = useRef<HTMLDivElement>(null);

  const loadUploadHistory = useCallback(() => {
    api
      .getUploadHistory()
      .then((res) => setHistoryData(res))
      .catch(() => {
        // non-blocking
      });
  }, []);

  useEffect(() => {
    if (isOpen) {
      loadUploadHistory();
    }
  }, [isOpen, loadUploadHistory]);

  // Run dry-run import preview whenever selectedFiles changes in preview stage
  useEffect(() => {
    if (stage !== "preview" || selectedFiles.length === 0) {
      setPreviewResults([]);
      return;
    }
    let cancelled = false;
    setIsPreviewLoading(true);
    api
      .previewFiles(selectedFiles)
      .then((res) => {
        if (!cancelled) {
          setPreviewResults(res);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setPreviewResults([]);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setIsPreviewLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [stage, selectedFiles]);

  const handleResetDatabase = async () => {
    setIsResetting(true);
    setErrorMsg(null);
    try {
      const res = await api.resetDatabase();
      setResetSuccessMsg(res.message || "All files deleted from database.");
      setConfirmingReset(false);
      loadUploadHistory();
      notifyDataRefreshed();
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to reset database.");
    } finally {
      setIsResetting(false);
    }
  };

  const handleModalClose = useCallback(() => {
    if (stage === "importing" || isResetting) return; // Prevent unsafe dismissal during upload
    const shouldRefresh = stage === "result";
    setSelectedFiles([]);
    setPreviewResults([]);
    setResults([]);
    setErrorMsg(null);
    setConfirmingReset(false);
    setResetSuccessMsg(null);
    setStage("select");
    onClose();
    if (shouldRefresh) {
      if (onImportComplete) {
        onImportComplete();
      } else {
        notifyDataRefreshed();
      }
    }
  }, [stage, isResetting, onClose, onImportComplete]);

  // Keyboard accessibility: Escape to close when safe
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen && stage !== "importing") {
        handleModalClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, stage, handleModalClose]);

  if (!isOpen) return null;

  const addFiles = (newFiles: FileList | File[]) => {
    const arr = Array.from(newFiles);
    const valid = arr.filter((f) => {
      const ext = f.name.toLowerCase();
      return ext.endsWith(".csv") || ext.endsWith(".txt");
    });

    if (valid.length === 0) {
      setErrorMsg("Please select valid challenge data files (.csv or .txt).");
      return;
    }

    setSelectedFiles((prev) => {
      const existingNames = new Set(prev.map((f) => f.name));
      const filtered = valid.filter((f) => !existingNames.has(f.name));
      return [...prev, ...filtered];
    });
    setStage("preview");
    setErrorMsg(null);
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      addFiles(e.target.files);
    }
    e.target.value = "";
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    if (stage === "importing") return;
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      addFiles(e.dataTransfer.files);
    }
  };

  const removeFile = (index: number) => {
    if (stage === "importing") return;
    setSelectedFiles((prev) => {
      const next = prev.filter((_, i) => i !== index);
      if (next.length === 0) {
        setStage("select");
      }
      return next;
    });
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const handleUploadCommit = async () => {
    if (selectedFiles.length === 0 || stage === "importing") return;
    setStage("importing");
    setErrorMsg(null);

    try {
      const res = await api.uploadFiles(selectedFiles);
      setResults(res);
      setStage("result");
      loadUploadHistory();
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to upload files. Please try again.");
      setStage("preview");
    }
  };

  // Determine result summary: complete success vs partial vs failure
  const hasErrors = results.some((r) => r.errors && r.errors.length > 0);
  const totalInserted = results.reduce((acc, r) => acc + (r.rows_inserted || 0), 0);
  const totalUpdated = results.reduce((acc, r) => acc + (r.rows_updated || 0), 0);
  const totalSkipped = results.reduce((acc, r) => acc + (r.rows_skipped || 0), 0);
  const allFailed = results.length > 0 && totalInserted === 0 && totalUpdated === 0 && totalSkipped === 0 && hasErrors;

  const previewByFilename = new Map<string, UploadResult>();
  for (const pr of previewResults) {
    previewByFilename.set(pr.filename, pr);
  }

  const totalCurrentRows = historyData?.current_table_counts
    ? Object.entries(historyData.current_table_counts)
        .filter(([k]) => k !== "clients")
        .reduce((acc, [, v]) => acc + v, 0)
    : 0;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4 animate-in fade-in duration-150"
      role="dialog"
      aria-modal="true"
      aria-labelledby="upload-modal-title"
    >
      <div
        ref={modalRef}
        className="bg-surface rounded-2xl shadow-xl w-full max-w-2xl border border-border overflow-hidden flex flex-col max-h-[88vh]"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border">
          <div>
            <h2 id="upload-modal-title" className="text-base font-semibold text-ink-primary">
              {stage === "result"
                ? "Import Results"
                : stage === "preview"
                ? "Import Preview Before Commit"
                : "Add Data Files & Import History"}
            </h2>
            <p className="text-xs text-ink-secondary mt-0.5">
              {stage === "result"
                ? "Review the records ingested into StudioOS"
                : stage === "preview"
                ? "Dry-run validation showing new, updated, unchanged, and invalid rows before committing"
                : "Upload new or updated CSV / TXT challenge files in any order"}
            </p>
          </div>

          {stage !== "importing" && (
            <button
              onClick={handleModalClose}
              className="p-1.5 rounded-lg text-ink-secondary hover:text-ink-primary hover:bg-canvas transition-colors cursor-pointer"
              aria-label="Close dialog"
            >
              <X className="w-5 h-5" />
            </button>
          )}
        </div>

        {/* Body Content */}
        <div className="p-6 overflow-y-auto flex-1 space-y-4 text-sm">
          {errorMsg && (
            <div className="p-3.5 rounded-xl bg-status-critical-bg border border-status-critical-border text-status-critical flex items-start gap-2.5 text-xs">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <div className="space-y-0.5">
                <p className="font-semibold">Action could not be completed</p>
                <p>{errorMsg}</p>
              </div>
            </div>
          )}

          {resetSuccessMsg && stage === "select" && (
            <div className="p-3.5 rounded-xl bg-status-success-bg border border-status-success-border text-status-success flex items-start gap-2.5 text-xs">
              <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5" />
              <div className="space-y-0.5">
                <p className="font-semibold">Database cleared</p>
                <p>{resetSuccessMsg}</p>
              </div>
            </div>
          )}

          {/* STAGE 1: FILE SELECTION + CURRENT IMPORT STATUS & HISTORY */}
          {stage === "select" && (
            <div className="space-y-4">
              <div
                onDragOver={(e) => e.preventDefault()}
                onDrop={handleDrop}
                className="border-2 border-dashed border-border hover:border-brand/60 rounded-xl p-7 text-center transition-colors bg-canvas/60"
              >
                <div className="w-11 h-11 rounded-full bg-brand-soft text-brand flex items-center justify-center mx-auto mb-2.5">
                  <Upload className="w-5 h-5" />
                </div>
                <h3 className="font-semibold text-ink-primary text-sm mb-1">
                  Drag and drop your files here
                </h3>
                <p className="text-xs text-ink-secondary mb-3.5 max-w-xs mx-auto">
                  Supports .csv and .txt files. Select all 8 data files together or upload incrementally.
                </p>

                <label className="inline-flex items-center gap-2 px-4 py-2 bg-brand hover:bg-brand-hover text-white text-sm font-medium rounded-lg cursor-pointer transition-colors shadow-xs">
                  <span>Browse files</span>
                  <input
                    ref={fileInputRef}
                    type="file"
                    multiple
                    accept=".csv,.txt"
                    onChange={handleFileChange}
                    className="hidden"
                  />
                </label>
              </div>

              {/* CURRENT DATABASE STATUS & IMPORT HISTORY */}
              {historyData && (
                <div className="p-4 rounded-xl bg-canvas border border-border space-y-3 text-xs">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-ink-primary inline-flex items-center gap-1.5">
                      <Database className="w-3.5 h-3.5 text-brand" />
                      <span>Current Database State ({totalCurrentRows.toLocaleString()} source rows loaded)</span>
                    </span>
                    <span className="text-ink-muted">
                      {historyData.current_table_counts.clients ?? 0} reconciled entities
                    </span>
                  </div>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-ink-secondary">
                    <div className="px-2.5 py-1.5 rounded bg-surface border border-border/80 flex justify-between">
                      <span>leads.csv:</span>
                      <strong className="text-ink-primary tabular-nums">{historyData.current_table_counts.leads ?? 0}</strong>
                    </div>
                    <div className="px-2.5 py-1.5 rounded bg-surface border border-border/80 flex justify-between">
                      <span>bookings.csv:</span>
                      <strong className="text-ink-primary tabular-nums">{historyData.current_table_counts.bookings ?? 0}</strong>
                    </div>
                    <div className="px-2.5 py-1.5 rounded bg-surface border border-border/80 flex justify-between">
                      <span>invoices.csv:</span>
                      <strong className="text-ink-primary tabular-nums">{historyData.current_table_counts.invoices ?? 0}</strong>
                    </div>
                    <div className="px-2.5 py-1.5 rounded bg-surface border border-border/80 flex justify-between">
                      <span>payments.csv:</span>
                      <strong className="text-ink-primary tabular-nums">{historyData.current_table_counts.payments ?? 0}</strong>
                    </div>
                    <div className="px-2.5 py-1.5 rounded bg-surface border border-border/80 flex justify-between">
                      <span>production:</span>
                      <strong className="text-ink-primary tabular-nums">{historyData.current_table_counts.production_videos ?? 0}</strong>
                    </div>
                    <div className="px-2.5 py-1.5 rounded bg-surface border border-border/80 flex justify-between">
                      <span>messages.txt:</span>
                      <strong className="text-ink-primary tabular-nums">{historyData.current_table_counts.messages ?? 0}</strong>
                    </div>
                    <div className="px-2.5 py-1.5 rounded bg-surface border border-border/80 flex justify-between">
                      <span>team.csv:</span>
                      <strong className="text-ink-primary tabular-nums">{historyData.current_table_counts.team_members ?? 0}</strong>
                    </div>
                    <div className="px-2.5 py-1.5 rounded bg-surface border border-border/80 flex justify-between">
                      <span>costs.csv:</span>
                      <strong className="text-ink-primary tabular-nums">{historyData.current_table_counts.cost_rules ?? 0}</strong>
                    </div>
                  </div>

                  {historyData.events && historyData.events.length > 0 && (
                    <div className="pt-2 border-t border-border space-y-1.5">
                      <span className="font-semibold text-ink-primary inline-flex items-center gap-1.5">
                        <History className="w-3.5 h-3.5 text-ink-secondary" />
                        <span>Recent Import History ({historyData.events.length})</span>
                      </span>
                      <div className="max-h-28 overflow-y-auto divide-y divide-border border border-border rounded-lg bg-surface">
                        {historyData.events.slice(0, 8).map((ev, i) => (
                          <div key={i} className="px-2.5 py-1.5 flex items-center justify-between gap-2 text-[11px]">
                            <div className="truncate">
                              <span className="font-semibold text-ink-primary">{ev.filename}</span>{" "}
                              <span className="text-ink-muted">({ev.file_type})</span>
                            </div>
                            <div className="shrink-0 text-ink-secondary tabular-nums">
                              +{ev.rows_inserted} new · {ev.rows_updated} upd · {ev.rows_skipped} skp
                              <span className="text-ink-muted ml-1.5">({ev.timestamp})</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Reset Database / Delete all files Action (Red Button) */}
              <div className="p-3.5 rounded-xl bg-red-950/20 border border-red-900/40 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
                <div className="space-y-0.5">
                  <span className="font-semibold text-red-400 block">Reset database</span>
                  <span className="text-red-300/80 text-[11px]">Clear all studio records to start fresh</span>
                </div>
                {confirmingReset ? (
                  <div className="flex items-center gap-2 shrink-0">
                    <button
                      type="button"
                      disabled={isResetting}
                      onClick={() => setConfirmingReset(false)}
                      className="px-2.5 py-1 rounded bg-surface border border-border text-ink-secondary hover:text-ink-primary"
                    >
                      Cancel
                    </button>
                    <button
                      type="button"
                      disabled={isResetting}
                      onClick={handleResetDatabase}
                      className="px-3 py-1 rounded bg-status-critical hover:bg-red-700 text-white font-medium flex items-center gap-1 shadow-xs disabled:opacity-50"
                    >
                      {isResetting ? <Loader2 className="w-3 h-3 animate-spin" /> : <Trash2 className="w-3 h-3" />}
                      <span>{isResetting ? "Deleting..." : "Confirm delete"}</span>
                    </button>
                  </div>
                ) : (
                  <button
                    type="button"
                    onClick={() => setConfirmingReset(true)}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-red-950/50 hover:bg-red-900/70 text-red-400 hover:text-red-300 border border-red-900/60 rounded-lg text-xs font-medium cursor-pointer transition-colors shrink-0"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                    <span>Delete all files</span>
                  </button>
                )}
              </div>
            </div>
          )}

          {/* STAGE 2: DRY-RUN PREVIEW OF SELECTED FILES BEFORE COMMIT */}
          {stage === "preview" && (
            <div className="space-y-4">
              <div className="flex items-center justify-between text-xs">
                <span className="font-medium text-ink-secondary inline-flex items-center gap-2">
                  <span>
                    {selectedFiles.length} file{selectedFiles.length === 1 ? "" : "s"} staged for import
                  </span>
                  {isPreviewLoading && (
                    <span className="inline-flex items-center gap-1 text-brand">
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      <span>Running dry-run preview...</span>
                    </span>
                  )}
                </span>
                <div className="flex items-center gap-3">
                  <button
                    type="button"
                    onClick={() => {
                      setSelectedFiles([]);
                      setPreviewResults([]);
                      setStage("select");
                    }}
                    className="text-red-600 hover:underline font-medium flex items-center gap-1 text-xs cursor-pointer"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                    <span>Clear selection</span>
                  </button>
                  <label className="text-brand hover:text-brand-hover font-medium cursor-pointer flex items-center gap-1">
                    <Plus className="w-3.5 h-3.5" />
                    <span>Add more files</span>
                    <input
                      type="file"
                      multiple
                      accept=".csv,.txt"
                      onChange={handleFileChange}
                      className="hidden"
                    />
                  </label>
                </div>
              </div>

              <div className="border border-border rounded-xl divide-y divide-border overflow-hidden max-h-72 overflow-y-auto">
                {selectedFiles.map((file, idx) => {
                  const pr = previewByFilename.get(file.name);
                  return (
                    <div key={idx} className="p-3.5 bg-surface space-y-2 text-xs">
                      <div className="flex items-center justify-between gap-3">
                        <div className="flex items-center gap-2.5 min-w-0">
                          <FileText className="w-4 h-4 text-brand shrink-0" />
                          <div className="truncate">
                            <span className="font-semibold text-ink-primary">{file.name}</span>
                            <span className="text-ink-muted ml-2">({formatFileSize(file.size)})</span>
                          </div>
                          {pr && (
                            <span className="px-2 py-0.5 rounded-full bg-brand-soft text-brand font-medium text-[11px]">
                              Detected: {pr.file_type}
                            </span>
                          )}
                        </div>
                        <button
                          onClick={() => removeFile(idx)}
                          className="p-1 text-ink-muted hover:text-status-critical transition-colors rounded cursor-pointer"
                          title="Remove file"
                          aria-label={`Remove ${file.name}`}
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>

                      {pr && (
                        <div className="pl-6 space-y-1">
                          <div className="flex flex-wrap items-center gap-2.5 text-ink-secondary">
                            <span>Valid rows: <strong>{pr.rows_processed - (pr.errors?.length || 0)}</strong></span>
                            <span>•</span>
                            <span className="text-status-success font-medium">New: +{pr.rows_inserted}</span>
                            <span>•</span>
                            <span className="text-ink-primary font-medium">Changed: {pr.rows_updated || 0}</span>
                            <span>•</span>
                            <span className="text-ink-muted">Unchanged/Skipped: {pr.rows_skipped || 0}</span>
                            {pr.errors && pr.errors.length > 0 && (
                              <>
                                <span>•</span>
                                <span className="text-status-critical font-semibold">Invalid: {pr.errors.length}</span>
                              </>
                            )}
                          </div>
                          {pr.warnings && pr.warnings.length > 0 && (
                            <p className="text-status-warning bg-status-warning-bg/70 px-2 py-1 rounded text-[11px]">
                              Warning: {pr.warnings.slice(0, 2).join(" | ")}
                            </p>
                          )}
                          {pr.errors && pr.errors.length > 0 && (
                            <p className="text-status-critical bg-status-critical-bg px-2 py-1 rounded text-[11px]">
                              Rejected rows: {pr.errors.slice(0, 2).join(" | ")}
                            </p>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>

              <p className="text-xs text-ink-secondary bg-brand-soft/40 p-3 rounded-lg border border-[#F0D5C9]">
                Preview runs inside a database savepoint and rolls back automatically until you click <strong>Confirm &amp; Import</strong>.
              </p>
            </div>
          )}

          {/* STAGE 3: IMPORTING PROGRESS */}
          {stage === "importing" && (
            <div className="py-12 text-center space-y-4">
              <div className="w-12 h-12 rounded-full bg-brand-soft text-brand flex items-center justify-center mx-auto">
                <Loader2 className="w-6 h-6 animate-spin" />
              </div>
              <div className="space-y-1">
                <h3 className="text-base font-semibold text-ink-primary">Ingesting data files...</h3>
                <p className="text-xs text-ink-secondary max-w-sm mx-auto leading-relaxed">
                  Parsing dates, deduplicating records, matching client identities, and reconciling invoices with bank payments.
                </p>
              </div>
            </div>
          )}

          {/* STAGE 4: RESULTS REPORT (STAYS VISIBLE UNTIL USER CLICKS DONE) */}
          {stage === "result" && (
            <div className="space-y-4">
              <div
                className={`p-4 rounded-xl border flex items-start gap-3 ${
                  allFailed
                    ? "bg-status-critical-bg border-status-critical-border text-status-critical"
                    : hasErrors
                    ? "bg-status-warning-bg border-status-warning-border text-status-warning"
                    : "bg-status-success-bg border-status-success-border text-status-success"
                }`}
              >
                {!hasErrors ? (
                  <CheckCircle2 className="w-5 h-5 shrink-0 mt-0.5 text-status-success" />
                ) : (
                  <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5" />
                )}
                <div className="space-y-0.5 text-xs">
                  <p className="font-semibold text-sm">
                    {allFailed
                      ? "Import encountered errors"
                      : hasErrors
                      ? "Import completed with warnings"
                      : "All files imported successfully"}
                  </p>
                  <p className="opacity-90">
                    Ingested {totalInserted} new records ({totalUpdated} updated, {totalSkipped} unchanged/skipped) across {results.length} file{results.length === 1 ? "" : "s"}.
                  </p>
                </div>
              </div>

              <div className="border border-border rounded-xl divide-y divide-border overflow-hidden max-h-60 overflow-y-auto">
                {results.map((res, idx) => (
                  <div key={idx} className="p-3 bg-surface text-xs space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-ink-primary">{res.filename}</span>
                      <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-brand-soft text-brand">
                        {res.file_type}
                      </span>
                    </div>
                    <div className="flex flex-wrap items-center gap-2.5 text-ink-secondary text-xs">
                      <span>Processed: {res.rows_processed}</span>
                      <span>•</span>
                      <span className="text-status-success font-medium">Inserted: {res.rows_inserted}</span>
                      <span>•</span>
                      <span className="text-ink-primary font-medium">Updated: {res.rows_updated || 0}</span>
                      <span>•</span>
                      <span className="text-ink-muted">Skipped: {res.rows_skipped || 0}</span>
                    </div>
                    {res.warnings && res.warnings.length > 0 && (
                      <p className="text-status-warning text-xs bg-status-warning-bg p-1.5 rounded">
                        {res.warnings.join(" | ")}
                      </p>
                    )}
                    {res.errors && res.errors.length > 0 && (
                      <p className="text-status-critical text-xs bg-status-critical-bg p-1.5 rounded">
                        {res.errors.join(" | ")}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="px-6 py-3.5 bg-canvas border-t border-border flex items-center justify-between gap-3">
          {stage === "select" && (
            <div className="w-full flex justify-end">
              <button
                onClick={handleModalClose}
                className="px-4 py-2 text-sm font-medium text-ink-secondary hover:text-ink-primary transition-colors cursor-pointer"
              >
                Close
              </button>
            </div>
          )}

          {stage === "preview" && (
            <>
              <button
                onClick={() => setStage("select")}
                className="px-4 py-2 text-sm font-medium text-ink-secondary hover:text-ink-primary transition-colors cursor-pointer"
              >
                Back
              </button>
              <button
                onClick={handleUploadCommit}
                className="px-5 py-2.5 bg-brand hover:bg-brand-hover text-white text-sm font-medium rounded-lg transition-colors cursor-pointer shadow-xs"
              >
                Confirm &amp; Import {selectedFiles.length} File{selectedFiles.length === 1 ? "" : "s"}
              </button>
            </>
          )}

          {stage === "importing" && (
            <div className="w-full text-center text-xs text-ink-secondary">
              Please wait while files are processed...
            </div>
          )}

          {stage === "result" && (
            <div className="w-full flex justify-end">
              <button
                onClick={handleModalClose}
                className="px-6 py-2.5 bg-brand hover:bg-brand-hover text-white text-sm font-medium rounded-lg transition-colors cursor-pointer shadow-xs"
              >
                Done
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
