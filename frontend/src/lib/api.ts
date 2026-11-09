// Axeom StudioOS Typed API Client & Utilities

const isProduction = process.env.NODE_ENV === "production";
const envBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;

export const API_BASE_URL = envBaseUrl || (isProduction ? "https://axeom-backend.onrender.com" : "http://localhost:8000");

export function isApiConfigured(): boolean {
  return true;
}

export interface RecommendedAction {
  id: string;
  priority: number;
  title: string;
  urgency: "Critical" | "High" | "Medium";
  why_it_matters: string;
  client_name?: string;
  evidence: string[];
  suggested_action: string;
  what_is_uncertain?: string;
  status: "pending" | "approved" | "dismissed";
}

export interface DashboardSummary {
  reference_date: string;
  overview: {
    active_clients_count: number;
    payers_count?: number;
    total_entities_count?: number;
    total_invoiced: string;
    gross_invoiced_including_void?: string;
    total_bank_collected: string;
    source_open_receivables?: string;
    source_overdue_receivables?: string;
    source_overdue_count?: number;
    true_unpaid_receivables: string;
    overdue_receivables: string;
    reconciled_overdue_count?: number;
    unanswered_leads_count: number;
    legitimate_unanswered_leads_count?: number;
    lost_requests_count: number;
    repeated_complaints_count?: number;
    privacy_alerts_count?: number;
    double_payment_owed: string;
    we_owe_total?: string;
    never_billed_total?: string;
    confirmed_never_billed_total?: string;
  };
  monday_top_3: RecommendedAction[];
  financial_alerts: {
    overdue_invoices_count: number;
    source_overdue_invoices_count?: number;
    source_overdue_total?: string;
    reconciled_overdue_total?: string;
    billing_tool_errors_count: number;
    never_billed_total: string;
    confirmed_never_billed_total?: string;
    we_owe_total?: string;
  };
  production_alerts: {
    lost_requests_count: number;
    repeated_complaints_count?: number;
    privacy_alerts_count?: number;
    root_cause_date: string;
  };
  lead_alerts: {
    unanswered_count: number;
    legitimate_unanswered_count?: number;
    existing_client_unanswered_count?: number;
    junk_unanswered_count?: number;
    urgent_lead: string;
  };
  privacy_alerts_count?: number;
  data_status?: {
    is_empty: boolean;
    is_partial: boolean;
    imported_counts: Record<string, number>;
  };
}

export interface ClientHealthFactor {
  factor: string;
  description: string;
  weight: number;
}

export interface ClientHealthSummary {
  health_status: "healthy" | "monitor" | "at_risk" | "critical" | "paused" | "insufficient_data";
  health_score: number;
  risk_score: "Low" | "Medium" | "High" | "Not assessed";
  contributing_factors: ClientHealthFactor[];
  supporting_record_ids: string[];
  last_interaction_date?: string | null;
  unresolved_requests_count: number;
  recurrence_count: number;
  next_step: string;
  data_completeness: number;
}

export interface ClientItem {
  id: string;
  canonical_name: string;
  aliases: string[];
  notes?: string;
  created_at: string;
  total_bookings: number;
  total_invoiced: string;
  total_videos: number;
  total_messages: number;
  risk_score: "Low" | "Medium" | "High" | "Not assessed";
  risk_reason?: string;
  entity_type?: "client" | "payer";
  pays_for?: string[];
  billed_via_payer?: string | null;
  match_confidence?: string;
  health_status?: "healthy" | "monitor" | "at_risk" | "critical" | "paused" | "insufficient_data";
  health_score?: number;
  contributing_factors?: ClientHealthFactor[];
  supporting_record_ids?: string[];
  last_interaction_date?: string | null;
  unresolved_requests_count?: number;
  recurrence_count?: number;
  next_step?: string;
  data_completeness?: number;
}

export interface ClientLead {
  id?: string;
  lead_id: string;
  created: string;
  name: string;
  business?: string;
  email?: string;
  phone?: string;
  source: string;
  status: string;
  notes?: string;
}

export interface ClientBooking {
  id?: string;
  booking_id: string;
  date: string;
  service: string;
  location?: string;
  price: number;
  status: string;
}

export interface ClientInvoice {
  id?: string;
  invoice_no: string;
  issued: string;
  due: string;
  amount: number;
  status: string;
  memo?: string;
  bill_to?: string;
}

export interface ClientPayment {
  id?: string;
  payment_id: string;
  payment_date: string;
  amount: number;
  method?: string;
  bank_account?: string;
  payer?: string;
  payer_name?: string;
  payer_email?: string;
  reference?: string;
  matched_invoice_no?: string;
}

export interface ClientVideo {
  id?: string;
  video_id: string;
  title: string;
  stage: string;
  revisions: number;
  editor?: string;
  editor_hours?: number;
  notes_on_board?: string;
  shoot_booking?: string;
  client_approved_on?: string;
  approved_date?: string;
}

export interface ClientMessage {
  id?: string;
  message_date?: string;
  timestamp?: string;
  channel: string;
  direction?: string;
  sender: string;
  message_text: string;
  duration?: string;
  original_line?: string;
}

export interface ClientDetail {
  id: string;
  canonical_name: string;
  aliases: string[];
  notes?: string;
  created_at: string;
  entity_type?: "client" | "payer";
  pays_for?: string[];
  billed_via_payer?: string | null;
  leads: ClientLead[];
  bookings: ClientBooking[];
  invoices: ClientInvoice[];
  payments: ClientPayment[];
  production_videos: ClientVideo[];
  messages: ClientMessage[];
  alerts?: Array<{
    type: string;
    severity: string;
    title: string;
    detail: string;
    date?: string;
  }>;
  financial_summary: {
    total_invoiced: string;
    total_paid_in_bank?: string;
    completed_bookings_value?: string;
    total_bookings: number;
    total_videos: number;
    total_messages: number;
    entity_type?: string;
    pays_for?: string[];
    billed_via_payer?: string | null;
  };
  health_summary?: ClientHealthSummary;
}

export interface OverdueInvoice {
  client: string;
  invoice: string;
  amount_owed: number;
  face_amount?: number;
  source_status?: string;
  reconciliation_status?: string;
  payment_evidence?: string;
  days_late: number;
  due_date: string;
}

export interface WeOweItem {
  client: string;
  amount: number;
  why: string;
  obligation_type?: string;
  status?: string;
}

export interface NeverBilledItem {
  client: string;
  booking_id_or_month: string;
  amount: number;
  confidence?: string;
  service?: string;
  booking_date?: string;
  why?: string;
}

export interface BillingToolError {
  invoice: string;
  tool_says: string;
  truth: string;
  how_you_know: string;
  confidence?: string;
}

export interface FinanceReconciliation {
  reference_date: string;
  total_invoiced: string;
  gross_invoiced_including_void?: string;
  void_invoices_total?: string;
  total_collected_in_bank: string;
  source_open_receivables?: string;
  source_overdue_total?: string;
  source_overdue_count?: number;
  true_unpaid_receivables: string;
  overdue_total: string;
  overdue_invoices: OverdueInvoice[];
  source_overdue_invoices?: OverdueInvoice[];
  we_owe: WeOweItem[];
  never_billed_total: string;
  potential_unbilled_total?: string;
  never_billed_items: NeverBilledItem[];
  retainer_covered_bookings_count?: number;
  billing_tool_is_wrong: BillingToolError[];
  candidate_allocations?: Array<{
    payment_id: string;
    payment_date: string;
    client: string;
    amount: number;
    reference: string;
    candidate_invoices: string[];
    allocation_type: string;
    confidence: string;
    why: string;
  }>;
  invoices_ledger?: Array<{
    invoice_no: string;
    client: string;
    bill_to?: string;
    issued: string;
    due: string;
    amount: number;
    source_status: string;
    reconciled_status: string;
    amount_owed: number;
    is_source_overdue: boolean;
    is_reconciled_overdue: boolean;
    days_late: number;
    memo: string;
    payment_evidence: string;
  }>;
  payments_ledger?: Array<{
    payment_id: string;
    payment_date: string;
    payer: string;
    payer_email: string;
    client: string;
    amount: number;
    method: string;
    reference: string;
    reference_type: string;
    allocated_invoices: string[];
    allocation_note: string;
  }>;
  payment_summary?: {
    total_payments_count: number;
    total_payments_amount: number;
    by_method_count: Record<string, number>;
    by_method_amount: Record<string, number>;
    exact_invoice_references: number;
    narrative_references: number;
    blank_references: number;
  };
}

export interface LostRequestItem {
  video_id: string;
  request_date: string;
  came_by: string;
  why_it_was_lost: string;
  client: string;
  title: string;
  stage?: string;
  editor?: string;
  notes_on_board?: string;
  line_number?: number;
}

export interface PrivacyAlertItem {
  line_number: number;
  message_id: string;
  timestamp: string;
  date: string;
  channel: string;
  sender: string;
  client_id?: string | null;
  client_name: string;
  message_text: string;
  video_id?: string | null;
  video_title?: string | null;
  video_stage?: string | null;
  editor?: string | null;
  revisions: number;
  notes_on_board: string;
  board_logged: boolean;
  cross_client_title_collision: boolean;
  action_required: string;
}

export interface RepeatedComplaintItem {
  line_number: number;
  message_id: string;
  timestamp: string;
  date: string;
  channel: string;
  sender: string;
  client_id?: string | null;
  client_name: string;
  message_text: string;
  video_id?: string | null;
  video_title?: string | null;
  video_stage?: string | null;
  editor?: string | null;
  revisions: number;
  notes_on_board: string;
  prior_voice_note_line?: number | null;
  prior_voice_note_text?: string | null;
  action_required: string;
}

export interface LostRequestsResponse {
  lost_requests: LostRequestItem[];
  lost_requests_root_causes: string[];
  lost_requests_started_getting_worse_in: string;
  repeated_complaints?: RepeatedComplaintItem[];
  privacy_alerts?: PrivacyAlertItem[];
}

export interface ProductionVideoItem {
  video_id: string;
  title: string;
  stage: string;
  revisions: number;
  editor?: string;
  editor_hours?: number;
  client?: string;
  client_name?: string;
  notes_on_board?: string;
  shoot_booking?: string | null;
  shoot_date?: string | null;
  client_approved_on?: string | null;
  has_privacy_alert?: boolean;
  privacy_board_missing?: boolean;
  has_unresolved_complaint?: boolean;
  complaint_count?: number;
}

export interface ProductionOverview {
  total_videos?: number;
  stage_breakdown: Record<string, number>;
  revision_breakdown?: Record<string, number>;
  missing_shoot_booking_count?: number;
  linked_shoot_booking_count?: number;
  missing_approval_date_count?: number;
  editor_metrics: Array<{
    editor: string;
    role?: string;
    joined?: string;
    hourly_rate?: number;
    total_videos: number;
    total_hours?: number;
    avg_hours: number;
    total_revisions: number;
    zero_revision_videos?: number;
    multi_revision_videos?: number;
    labor_cost?: number;
  }>;
  non_editor_team?: Array<{
    name: string;
    role: string;
    joined?: string;
    hourly_rate?: number | null;
    pay_status: string;
  }>;
  cost_summary?: {
    total_editor_hours: number;
    total_editor_labor_cost: number;
    studio_hourly_rate: number;
    completed_studio_hours: number;
    completed_studio_cost: number;
    scheduled_studio_hours: number;
    scheduled_studio_cost: number;
    cancelled_studio_hours: number;
    total_direct_production_cost: number;
  };
  voice_note_summary?: {
    total_voice_notes: number;
    logged_on_board: number;
    unlogged_count: number;
    escalated_to_complaints: number;
  };
  privacy_alerts?: PrivacyAlertItem[];
  active_work_in_progress: ProductionVideoItem[];
  all_videos?: ProductionVideoItem[];
}

export interface LeadItem {
  lead_id: string;
  client_id?: string | null;
  linked_client_name?: string | null;
  created: string;
  name: string;
  business?: string;
  email?: string;
  phone?: string;
  source: string;
  first_reply?: string | null;
  status: string;
  triage_category?: "legitimate_prospect" | "existing_client_inquiry" | "junk_or_spam";
  is_duplicate?: boolean;
  duplicate_of?: string[];
}

export interface LeadsOverviewResponse {
  total_leads_count?: number;
  status_breakdown: Record<string, number>;
  channel_conversion: Array<{
    source: string;
    total: number;
    won: number;
    unanswered?: number;
    conversion_rate: number;
  }>;
  unanswered_leads_count: number;
  legitimate_unanswered_count?: number;
  existing_client_unanswered_count?: number;
  junk_unanswered_count?: number;
  duplicate_enquiries?: Array<{
    email: string;
    lead_ids: string[];
  }>;
  unanswered_leads: LeadItem[];
  all_leads?: LeadItem[];
  message_opportunities_and_referrals?: Array<{
    line_number: number;
    timestamp: string;
    date: string;
    channel: string;
    client_name: string;
    sender: string;
    type: string;
    status: string;
    message_text: string;
    action_required: string;
  }>;
}

export interface ChannelMetric {
  source: string;
  total_leads: number;
  won_leads: number;
  lost_leads: number;
  new_leads: number;
  talking_leads?: number;
  unreplied_leads: number;
  conversion_rate: number;
  clients_acquired: number;
  direct_booking_revenue: number;
}

export interface MarketingAnalysisResponse {
  best_marketing_channel: {
    channel: string;
    label?: string;
    conversion_rate?: number;
    won_leads?: number;
    total_leads?: number;
    attributed_revenue?: number;
    why: string;
  };
  what_this_data_cannot_tell_us: string[];
  channel_metrics: ChannelMetric[];
  summary_totals?: {
    total_leads: number;
    won_leads: number;
    lost_leads: number;
    new_leads: number;
    talking_leads?: number;
    unreplied_leads: number;
    conversion_rate: number;
    clients_acquired: number;
    direct_booking_revenue: number;
  };
}

export interface MessagesIntelligenceResponse {
  total_messages: number;
  by_channel: Record<string, number>;
  by_direction: Record<string, number>;
  messages: Array<{
    id: string;
    line_number: number;
    timestamp: string;
    date: string;
    channel: string;
    direction: string;
    sender: string;
    duration?: string | null;
    client_id?: string | null;
    client_name?: string | null;
    message_text: string;
    original_line: string;
    categories: string[];
    severity: string;
    matched_video_id?: string | null;
    matched_video_title?: string | null;
    matched_video_stage?: string | null;
    matched_video_editor?: string | null;
    matched_board_note?: string;
    board_logged: boolean;
    prior_voice_note_line?: number | null;
    action_required?: string;
  }>;
  privacy_alerts: PrivacyAlertItem[];
  repeated_complaints: RepeatedComplaintItem[];
  opportunities_and_referrals: Array<{
    line_number: number;
    timestamp: string;
    date: string;
    channel: string;
    client_name: string;
    sender: string;
    type: string;
    status: string;
    message_text: string;
    action_required: string;
  }>;
  quarantined_messages: Array<any>;
}

export interface JevBenchmarkResponse {
  task_name: string;
  why_chosen: string;
  api_endpoint?: string;
  model?: string;
  api_key_configured?: boolean;
  active_provider?: string;
  sample_size: number;
  correct_predictions: number;
  accuracy_percentage: number;
  evaluation_summary: string;
  per_label_metrics?: Array<{
    label: string;
    support: number;
    tp: number;
    fp: number;
    fn: number;
    precision: number;
    recall: number;
    f1: number;
  }>;
  confusion_matrix?: Record<string, Record<string, number>>;
  misclassified_samples?: Array<any>;
  samples: Array<{
    line_number?: number;
    text: string;
    ground_truth: string;
    prediction: string;
    confidence: number;
    provider?: string;
    matched: boolean;
  }>;
}

export interface JevClassifyResponse {
  text: string;
  category: string;
  confidence: number;
  provider: string;
  model?: string;
  cached?: boolean;
  is_urgent_prob?: number;
  has_privacy_risk_prob?: number;
  notes: string;
}

export interface GeminiStatusResponse {
  provider: string;
  configured: boolean;
  status: string;
  model: string;
  sdk: string;
  total_messages: number;
  classified_count: number;
  pending_count: number;
  human_confirmed_count: number;
  failed_count: number;
  last_job_time?: string | null;
  message: string;
}

export interface GeminiClassifyResponse {
  message_id: string;
  primary_category: string;
  secondary_categories: string[];
  is_spam_or_test: boolean;
  spam_reason?: string | null;
  sentiment: string;
  urgency: string;
  needs_human_follow_up: boolean;
  needs_reply?: boolean | null;
  requested_action?: string | null;
  concise_summary: string;
  evidence_quotes: string[];
  mentioned_record_ids: string[];
  confidence: number;
  classification_notes?: string | null;
  status: string;
  provider: string;
  model: string;
}

export interface GeminiBatchClassifyResponse {
  processed: number;
  skipped: number;
  failed: number;
  status: string;
  message?: string;
  results: GeminiClassifyResponse[];
}

export interface GeminiHumanReviewRequest {
  primary_category: string;
  is_spam_or_test: boolean;
  urgency: string;
  notes?: string;
  secondary_categories?: string[];
  reviewer?: string;
}

export interface ActionDraftResponse {
  action_id: string;
  fingerprint: string;
  title: string;
  client_name?: string | null;
  target_record?: string | null;
  draft_text: string;
  evidence: string[];
  status: string;
  responsible_area: string;
}

export interface IdentityReviewActionRequest {
  table_name: string;
  record_id: string;
  action: "confirm" | "reject" | "assign";
  suggested_client_id?: string;
  assigned_client_id?: string;
  reason?: string;
  performed_by?: string;
}

export interface UploadResult {
  file_type: string;
  filename: string;
  rows_processed: number;
  rows_inserted: number;
  rows_updated: number;
  rows_skipped?: number;
  warnings?: string[];
  errors: string[];
  message: string;
}

export interface HealthResponse {
  status: string;
  database: string;
  reference_date: string;
  version: string;
}

export interface CurrentDateInfo {
  date: string;
  time: string;
  timezone: string;
  day_of_week: string;
  source: string;
  ip?: string;
  is_external_api: boolean;
}

export interface ReferenceDateInfo {
  reference_date: string;
  location_date: string;
  is_today: boolean;
  timezone: string;
  source: string;
  baseline_date: string;
}

export function formatCurrency(val: string | number | undefined | null): string {
  if (val === undefined || val === null) return "$0.00";
  const num = typeof val === "number" ? val : parseFloat(String(val).replace(/[^0-9.-]/g, ""));
  if (isNaN(num)) return "$0.00";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(num);
}

export function formatDate(dateStr: string | undefined | null): string {
  if (!dateStr || dateStr.toLowerCase() === "unknown" || dateStr.toLowerCase() === "in progress") {
    return dateStr || "Date not recorded";
  }
  const parts = dateStr.split("T")[0].split("-");
  if (parts.length === 3) {
    const year = parseInt(parts[0], 10);
    const month = parseInt(parts[1], 10) - 1;
    const day = parseInt(parts[2], 10);
    const d = new Date(year, month, day);
    if (!isNaN(d.getTime())) {
      return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
    }
  }
  return dateStr;
}

async function fetchApi<T>(endpoint: string, options?: RequestInit): Promise<T> {
  if (!isApiConfigured()) {
    throw new Error(
      "API Configuration Error: NEXT_PUBLIC_API_BASE_URL is not set in production. Please configure your backend URL."
    );
  }

  const url = `${API_BASE_URL}${endpoint}`;
  try {
    const res = await fetch(url, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...options?.headers,
      },
    });

    if (!res.ok) {
      let detailMsg = `HTTP ${res.status}: ${res.statusText}`;
      try {
        const errorData = await res.json();
        if (errorData?.detail) {
          detailMsg = typeof errorData.detail === "string" ? errorData.detail : JSON.stringify(errorData.detail);
        }
      } catch {
        // fallback
      }
      throw new Error(detailMsg);
    }

    return await res.json();
  } catch (err: any) {
    if (err.message?.includes("Failed to fetch") || err.message?.includes("NetworkError")) {
      throw new Error("Unable to reach the studio backend. Please check your network connection or try again.");
    }
    throw err;
  }
}

export const api = {
  getHealth: (refDate?: string) =>
    fetchApi<HealthResponse>(`/api/health${refDate ? `?reference_date=${encodeURIComponent(refDate)}` : ""}`),
  getCurrentDate: (refresh?: boolean) =>
    fetchApi<CurrentDateInfo>(`/api/date/current${refresh ? "?refresh=true" : ""}`),
  getReferenceDate: () => fetchApi<ReferenceDateInfo>("/api/reference-date"),
  setReferenceDate: (reference_date: string) =>
    fetchApi<{ status: string; reference_date: string; is_today: boolean; message: string }>(
      "/api/reference-date",
      {
        method: "POST",
        body: JSON.stringify({ reference_date }),
      }
    ),
  resetReferenceDate: () =>
    fetchApi<{ status: string; reference_date: string; message: string }>("/api/reference-date/reset", {
      method: "POST",
    }),
  getDashboard: (refDate?: string) =>
    fetchApi<DashboardSummary>(
      `/api/dashboard/summary${refDate ? `?reference_date=${encodeURIComponent(refDate)}` : ""}`
    ),
  updateActionStatus: (actionId: string, status: "pending" | "approved" | "dismissed") =>
    fetchApi<{ action_id: string; status: string; updated: boolean }>(`/api/actions/${actionId}/status`, {
      method: "POST",
      body: JSON.stringify({ status }),
    }),
  getClients: (refDate?: string) =>
    fetchApi<ClientItem[]>(`/api/clients${refDate ? `?reference_date=${encodeURIComponent(refDate)}` : ""}`),
  getClientDetail: (id: string, refDate?: string) =>
    fetchApi<ClientDetail>(
      `/api/clients/${id}${refDate ? `?reference_date=${encodeURIComponent(refDate)}` : ""}`
    ),
  getIdentityReview: () => fetchApi<any>("/api/identity/review"),
  getFinanceReconciliation: (refDate?: string) =>
    fetchApi<FinanceReconciliation>(
      `/api/finance/reconciliation${refDate ? `?reference_date=${encodeURIComponent(refDate)}` : ""}`
    ),
  getLostRequests: () => fetchApi<LostRequestsResponse>("/api/production/lost-requests"),
  getProductionOverview: () => fetchApi<ProductionOverview>("/api/production/overview"),
  getMessages: () => fetchApi<MessagesIntelligenceResponse>("/api/messages"),
  getLeadsOverview: () => fetchApi<LeadsOverviewResponse>("/api/leads/overview"),
  getMarketingAnalysis: () => fetchApi<MarketingAnalysisResponse>("/api/marketing/analysis"),
  getJevBenchmark: () => fetchApi<JevBenchmarkResponse>("/api/jev/benchmark"),
  classifyMessage: (text: string) =>
    fetchApi<JevClassifyResponse>("/api/jev/classify", {
      method: "POST",
      body: JSON.stringify({ text }),
    }),
  getGeminiStatus: () => fetchApi<GeminiStatusResponse>("/api/gemini/status"),
  classifyWithGemini: (text: string, message_id?: string, dry_run: boolean = false) =>
    fetchApi<GeminiClassifyResponse>("/api/gemini/classify", {
      method: "POST",
      body: JSON.stringify({ text, message_id, dry_run }),
    }),
  batchClassifyWithGemini: (dry_run: boolean = false, force_reclassify: boolean = false, limit?: number) =>
    fetchApi<GeminiBatchClassifyResponse>("/api/gemini/batch", {
      method: "POST",
      body: JSON.stringify({ dry_run, force_reclassify, limit }),
    }),
  saveGeminiReview: (messageId: string, review: GeminiHumanReviewRequest) =>
    fetchApi<{ status: string; message_id: string; classification: any }>(`/api/gemini/review/${messageId}`, {
      method: "POST",
      body: JSON.stringify(review),
    }),
  getGeminiClassifications: (params?: { category?: string; status?: string; is_spam?: boolean; limit?: number }) => {
    const q = new URLSearchParams();
    if (params?.category) q.append("category", params.category);
    if (params?.status) q.append("status", params.status);
    if (params?.is_spam !== undefined) q.append("is_spam", String(params.is_spam));
    if (params?.limit) q.append("limit", String(params.limit));
    return fetchApi<any[]>(`/api/gemini/classifications?${q.toString()}`);
  },
  getActionDraft: (actionId: string, referenceDate?: string) => {
    const q = referenceDate ? `?reference_date=${encodeURIComponent(referenceDate)}` : "";
    return fetchApi<ActionDraftResponse>(`/api/actions/${encodeURIComponent(actionId)}/draft${q}`);
  },
  updateActionDraft: (actionId: string, draftText: string) =>
    fetchApi<{ action_id: string; updated: boolean; draft_text: string }>(
      `/api/actions/${encodeURIComponent(actionId)}/draft`,
      {
        method: "PUT",
        body: JSON.stringify({ draft_text: draftText }),
      }
    ),
  processIdentityAction: (payload: IdentityReviewActionRequest) =>
    fetchApi<{ status: string; action: string; table: string; record_id: string }>(`/api/identity/action`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  resetDatabase: () =>
    fetchApi<{ status: string; message: string }>("/api/database/reset", {
      method: "POST",
    }),
  getUploadHistory: () =>
    fetchApi<{
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
    }>("/api/upload/history"),
  searchGlobal: (q: string) =>
    fetchApi<{
      query: string;
      results: Array<{
        type: string;
        id: string;
        title: string;
        subtitle: string;
        source: string;
        href: string;
      }>;
    }>(`/api/search?q=${encodeURIComponent(q)}`),
  previewFiles: async (files: File[]): Promise<UploadResult[]> => {
    if (!isApiConfigured()) {
      throw new Error("API Configuration Error: NEXT_PUBLIC_API_BASE_URL is not set.");
    }
    const formData = new FormData();
    for (const f of files) {
      formData.append("files", f);
    }

    const res = await fetch(`${API_BASE_URL}/api/upload/preview`, {
      method: "POST",
      body: formData,
    });

    if (!res.ok) {
      let detailMsg = `Preview failed (HTTP ${res.status})`;
      try {
        const errorData = await res.json();
        if (errorData?.detail) {
          detailMsg = typeof errorData.detail === "string" ? errorData.detail : JSON.stringify(errorData.detail);
        }
      } catch {
        // fallback
      }
      throw new Error(detailMsg);
    }

    return await res.json();
  },
  uploadFiles: async (files: File[]): Promise<UploadResult[]> => {
    if (!isApiConfigured()) {
      throw new Error("API Configuration Error: NEXT_PUBLIC_API_BASE_URL is not set.");
    }
    const formData = new FormData();
    for (const f of files) {
      formData.append("files", f);
    }

    const res = await fetch(`${API_BASE_URL}/api/upload`, {
      method: "POST",
      body: formData,
    });

    if (!res.ok) {
      let detailMsg = `Upload failed (HTTP ${res.status})`;
      try {
        const errorData = await res.json();
        if (errorData?.detail) {
          detailMsg = typeof errorData.detail === "string" ? errorData.detail : JSON.stringify(errorData.detail);
        }
      } catch {
        // fallback
      }
      throw new Error(detailMsg);
    }

    return await res.json();
  },
};

export function notifyDataRefreshed() {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent("axeom:data-refreshed"));
  }
}

export function notifyReferenceDateChanged(newDate: string) {
  if (typeof window !== "undefined") {
    window.dispatchEvent(
      new CustomEvent("axeom:reference-date-changed", { detail: { reference_date: newDate } })
    );
    window.dispatchEvent(new CustomEvent("axeom:data-refreshed"));
  }
}
