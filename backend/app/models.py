from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import date, datetime
from decimal import Decimal


class HealthResponse(BaseModel):
    status: str
    database: str
    reference_date: date
    version: str


class ClientSummary(BaseModel):
    id: str
    canonical_name: str
    aliases: List[str]
    notes: Optional[str] = None
    created_at: datetime
    total_bookings: int
    total_invoiced: Decimal
    total_videos: int
    total_messages: int
    risk_score: str  # 'Low', 'Medium', 'High', 'Not assessed'
    risk_reason: Optional[str] = None
    entity_type: str = "client"  # 'client' or 'payer'
    pays_for: List[str] = Field(default_factory=list)
    billed_via_payer: Optional[str] = None
    match_confidence: str = "confirmed"


class ClientDetail(BaseModel):
    id: str
    canonical_name: str
    aliases: List[str]
    notes: Optional[str]
    created_at: datetime
    leads: List[Dict[str, Any]]
    bookings: List[Dict[str, Any]]
    invoices: List[Dict[str, Any]]
    payments: List[Dict[str, Any]]
    production_videos: List[Dict[str, Any]]
    messages: List[Dict[str, Any]]
    financial_summary: Dict[str, Any]
    entity_type: str = "client"
    pays_for: List[str] = Field(default_factory=list)
    billed_via_payer: Optional[str] = None
    alerts: List[Dict[str, Any]] = Field(default_factory=list)


class OverdueInvoice(BaseModel):
    client: str
    invoice: str
    amount_owed: Decimal
    face_amount: Optional[Decimal] = None
    source_status: Optional[str] = None
    reconciliation_status: Optional[str] = None
    payment_evidence: Optional[str] = None
    days_late: int
    due_date: date


class WeOweItem(BaseModel):
    client: str
    amount: Decimal
    why: str
    obligation_type: str = "credit_or_refund_review"
    status: str = "unresolved_owner_decision"


class NeverBilledItem(BaseModel):
    client: str
    booking_id_or_month: str
    amount: Decimal
    confidence: str = "confirmed"
    service: Optional[str] = None
    booking_date: Optional[str] = None
    why: Optional[str] = None


class BillingToolError(BaseModel):
    invoice: str
    tool_says: str
    truth: str
    how_you_know: str
    confidence: str = "high"


class FinanceReconciliationResponse(BaseModel):
    reference_date: date
    total_invoiced: Decimal
    gross_invoiced_including_void: Optional[Decimal] = None
    void_invoices_total: Optional[Decimal] = None
    total_collected_in_bank: Decimal
    source_open_receivables: Optional[Decimal] = None
    source_overdue_total: Optional[Decimal] = None
    source_overdue_count: Optional[int] = None
    true_unpaid_receivables: Decimal
    overdue_total: Decimal
    overdue_invoices: List[OverdueInvoice]
    source_overdue_invoices: List[OverdueInvoice] = Field(default_factory=list)
    we_owe: List[WeOweItem]
    never_billed_total: Decimal
    potential_unbilled_total: Optional[Decimal] = None
    never_billed_items: List[NeverBilledItem]
    retainer_covered_bookings_count: int = 0
    billing_tool_is_wrong: List[BillingToolError]
    candidate_allocations: List[Dict[str, Any]] = Field(default_factory=list)
    invoices_ledger: List[Dict[str, Any]] = Field(default_factory=list)
    payments_ledger: List[Dict[str, Any]] = Field(default_factory=list)
    payment_summary: Dict[str, Any] = Field(default_factory=dict)


class LostRequestItem(BaseModel):
    video_id: str
    request_date: str
    came_by: str
    why_it_was_lost: str
    client: str
    title: str
    stage: Optional[str] = None
    editor: Optional[str] = None
    notes_on_board: Optional[str] = None
    line_number: Optional[int] = None


class LostRequestsResponse(BaseModel):
    lost_requests: List[LostRequestItem]
    lost_requests_root_causes: List[str]
    lost_requests_started_getting_worse_in: str
    repeated_complaints: List[Dict[str, Any]] = Field(default_factory=list)
    privacy_alerts: List[Dict[str, Any]] = Field(default_factory=list)
    root_cause_breakdown: List[Dict[str, Any]] = Field(default_factory=list)
    earliest_incident_date: Optional[str] = None
    latest_incident_date: Optional[str] = None


class RecommendedAction(BaseModel):
    id: str
    priority: int
    title: str
    urgency: str  # 'Critical', 'High', 'Medium'
    why_it_matters: str
    client_name: Optional[str]
    evidence: List[str]
    suggested_action: str
    what_is_uncertain: Optional[str] = None
    status: str  # 'pending', 'approved', 'dismissed', 'deferred', 'completed'
    responsible_area: Optional[str] = "client"
    draft_available: bool = True
    fingerprint: Optional[str] = None


class ActionDraftResponse(BaseModel):
    action_id: str
    fingerprint: str
    title: str
    client_name: Optional[str]
    target_record: Optional[str]
    draft_text: str
    evidence: List[str] = Field(default_factory=list)
    status: str
    responsible_area: str = "client"


class ActionDraftUpdateRequest(BaseModel):
    draft_text: str


class GeminiStatusResponse(BaseModel):
    provider: str = "google_gemini"
    configured: bool
    status: str
    model: str
    sdk: str = "google-genai"
    total_messages: int
    classified_count: int
    pending_count: int
    human_confirmed_count: int
    failed_count: int
    last_job_time: Optional[str] = None
    message: str


class GeminiClassifyRequest(BaseModel):
    text: str
    message_id: Optional[str] = None
    dry_run: bool = False


class GeminiClassifyResponse(BaseModel):
    message_id: str
    primary_category: str
    secondary_categories: List[str] = Field(default_factory=list)
    is_spam_or_test: bool = False
    spam_reason: Optional[str] = None
    sentiment: str = "neutral"
    urgency: str = "normal"
    needs_human_follow_up: bool = False
    needs_reply: Optional[bool] = None
    requested_action: Optional[str] = None
    concise_summary: str = ""
    evidence_quotes: List[str] = Field(default_factory=list)
    mentioned_record_ids: List[str] = Field(default_factory=list)
    confidence: float = 0.0
    classification_notes: Optional[str] = None
    status: str = "classified_unreviewed"
    provider: str = "google_gemini"
    model: str = "gemini-2.5-flash"


class GeminiBatchClassifyRequest(BaseModel):
    force_reclassify: bool = False
    dry_run: bool = False
    limit: Optional[int] = None


class GeminiBatchClassifyResponse(BaseModel):
    processed: int
    skipped: int
    failed: int
    status: str
    message: Optional[str] = None
    results: List[Dict[str, Any]] = Field(default_factory=list)


class GeminiHumanReviewRequest(BaseModel):
    primary_category: str
    is_spam_or_test: bool = False
    urgency: str = "normal"
    notes: Optional[str] = None
    secondary_categories: Optional[List[str]] = None
    reviewer: str = "Studio Owner"


class IdentityReviewActionRequest(BaseModel):
    table_name: str
    record_id: str
    action: str  # 'confirm', 'reject', 'assign'
    suggested_client_id: Optional[str] = None
    assigned_client_id: Optional[str] = None
    reason: Optional[str] = None
    performed_by: str = "Studio Owner"


class DashboardSummaryResponse(BaseModel):
    reference_date: date
    overview: Dict[str, Any]
    monday_top_3: List[RecommendedAction]
    financial_alerts: Dict[str, Any]
    production_alerts: Dict[str, Any]
    lead_alerts: Dict[str, Any]
    privacy_alerts_count: int = 0
    data_status: Optional[Dict[str, Any]] = None


class UploadResult(BaseModel):
    file_type: str
    filename: str
    rows_processed: int
    rows_inserted: int
    rows_updated: int
    rows_skipped: int = 0
    warnings: List[str] = Field(default_factory=list)
    errors: List[str]
    message: str


class JevClassificationRequest(BaseModel):
    text: str


class JevClassificationResponse(BaseModel):
    text: str
    category: str
    confidence: float
    provider: str  # 'jev' or 'heuristic_fallback'
    model: Optional[str] = None
    cached: bool = False
    is_urgent_prob: Optional[float] = None
    has_privacy_risk_prob: Optional[float] = None
    notes: Optional[str]
