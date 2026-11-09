import json
import os
from datetime import date
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .config import settings
from .db import get_db
from .services.date_service import (
    detect_location_date,
    get_active_reference_date,
    reset_active_reference_date,
    set_active_reference_date,
)
from .models import (
    ActionDraftResponse,
    ActionDraftUpdateRequest,
    DashboardSummaryResponse,
    FinanceReconciliationResponse,
    GeminiBatchClassifyRequest,
    GeminiBatchClassifyResponse,
    GeminiClassifyRequest,
    GeminiClassifyResponse,
    GeminiHumanReviewRequest,
    GeminiStatusResponse,
    HealthResponse,
    IdentityReviewActionRequest,
    JevClassificationRequest,
    JevClassificationResponse,
    LostRequestsResponse,
    UploadResult,
)
from .services.actions_service import generate_draft_for_action, update_recommendation_state
from .services.clients import (
    get_client_360,
    get_clients_list,
    get_identity_review_queue,
    process_identity_review_action,
)
from .services.dashboard import get_dashboard_summary, set_action_status
from .services.export import generate_answers_json
from .services.finance import get_finance_reconciliation
from .services.gemini_service import (
    classify_message_batch,
    deterministic_mock_classify,
    get_provider_status,
    save_human_review,
    validate_and_clean_item,
    GeminiMessageItem,
)
from .services.identity import reconcile_all_entities
from .services.ingestion import clear_import_history, get_import_history, process_uploaded_file
from .services.leads import get_leads_overview
from .services.marketing import get_marketing_analysis
from .services.messages_service import analyze_messages
from .services.production import get_lost_requests, get_production_overview

app = FastAPI(
    title="Axeom StudioOS API",
    description="Backend Operating System for Axeom Studio Challenge (Pack 213)",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ActionStatusUpdateRequest(BaseModel):
    status: str  # 'approved', 'dismissed', 'pending'


class MatchOverrideRequest(BaseModel):
    table_name: str  # 'leads', 'bookings', 'invoices', 'production_videos', 'messages'
    record_id: str
    client_id: str


class ReferenceDateUpdateRequest(BaseModel):
    reference_date: Optional[str] = None
    date: Optional[str] = None


def _resolve_ref_date(param: Optional[str]) -> date:
    if param and param.strip():
        val = param.strip().lower()
        if val in ("today", "auto", "location"):
            loc = detect_location_date()
            return date.fromisoformat(loc["date"])
        if val in ("baseline", "pack213"):
            return settings.REFERENCE_DATE
        try:
            return date.fromisoformat(param.strip())
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid reference_date format '{param}'. Expected YYYY-MM-DD.",
            )
    return get_active_reference_date()


@app.get("/api/date/current")
def get_current_date(refresh: bool = False):
    """
    Queries date/time APIs to determine today's date at the current location.
    Gracefully falls back to system clock if external API is unreachable.
    """
    return detect_location_date(force_refresh=refresh)


@app.get("/api/reference-date")
def get_reference_date_state():
    """
    Returns the active calculation reference date, location date from date API,
    and whether calculations are currently running against today's date.
    """
    active_d = get_active_reference_date()
    loc = detect_location_date()
    loc_d = date.fromisoformat(loc["date"])
    return {
        "reference_date": active_d.isoformat(),
        "location_date": loc["date"],
        "is_today": active_d == loc_d,
        "timezone": loc.get("timezone"),
        "source": loc.get("source"),
        "baseline_date": settings.REFERENCE_DATE.isoformat(),
    }


@app.post("/api/reference-date")
def update_reference_date(payload: ReferenceDateUpdateRequest):
    """
    Updates the active reference date for all calculations across Today, Money, Clients, etc.
    Accepts 'YYYY-MM-DD', 'today', 'auto', or 'baseline'.
    """
    raw_date = payload.reference_date or payload.date or "today"
    resolved_d = _resolve_ref_date(raw_date)
    set_active_reference_date(resolved_d)
    loc = detect_location_date()
    loc_d = date.fromisoformat(loc["date"])
    return {
        "status": "success",
        "reference_date": resolved_d.isoformat(),
        "is_today": resolved_d == loc_d,
        "message": f"Reference date updated to {resolved_d.isoformat()}.",
    }


@app.post("/api/reference-date/reset")
def reset_reference_date_endpoint():
    """Resets the reference date override to default dynamic location date."""
    reset_active_reference_date()
    active_d = get_active_reference_date()
    return {
        "status": "success",
        "reference_date": active_d.isoformat(),
        "message": f"Reference date reset to {active_d.isoformat()}.",
    }


@app.get("/api/health", response_model=HealthResponse)
def health_check(reference_date: Optional[str] = Query(None)):
    """Health check endpoint confirming DB connection and challenge reference date."""
    ref_d = _resolve_ref_date(reference_date)
    try:
        with get_db() as cur:
            cur.execute("SELECT 1;")
            return HealthResponse(
                status="healthy",
                database="connected",
                reference_date=ref_d,
                version="2.0.0",
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database unreachable: {str(e)}")


@app.get("/api/dashboard/summary", response_model=DashboardSummaryResponse)
def dashboard_summary(reference_date: Optional[str] = Query(None)):
    """10-second test summary: Monday morning Top 3 priorities, key alerts, and financial overview."""
    ref_d = _resolve_ref_date(reference_date)
    with get_db() as cur:
        return get_dashboard_summary(cur, ref_date=ref_d)


@app.post("/api/actions/{action_id}/status")
def update_action_status(action_id: str, payload: ActionStatusUpdateRequest):
    """Suggest, Never Act Alone approval toggle."""
    success = set_action_status(action_id, payload.status)
    if not success:
        raise HTTPException(status_code=404, detail=f"Action '{action_id}' not found.")
    return {"action_id": action_id, "status": payload.status, "updated": True}


@app.get("/api/actions/{action_id}/draft", response_model=ActionDraftResponse)
def get_action_draft(action_id: str, reference_date: Optional[str] = Query(None)):
    """
    Returns deterministic prefilled communication draft for an action recommendation.
    Never uses an LLM. Cites exact verified business records.
    """
    ref_d = _resolve_ref_date(reference_date)
    with get_db() as cur:
        cur.execute("SELECT * FROM recommendation_states WHERE fingerprint = %s;", (action_id,))
        row = cur.fetchone()
        if row and row.get("draft_text"):
            return ActionDraftResponse(
                action_id=action_id,
                fingerprint=row["fingerprint"],
                title=row["title"],
                client_name=row.get("target_client"),
                target_record=row.get("target_record"),
                draft_text=row["draft_text"],
                evidence=row.get("evidence") if isinstance(row.get("evidence"), list) else [],
                status=row.get("status") or "pending",
                responsible_area=row.get("responsible_area") or "client",
            )

        summary = get_dashboard_summary(cur, ref_date=ref_d)
        for act in summary.monday_top_3:
            if act.id == action_id or act.fingerprint == action_id:
                draft_text = generate_draft_for_action(act.dict())
                return ActionDraftResponse(
                    action_id=action_id,
                    fingerprint=action_id,
                    title=act.title,
                    client_name=act.client_name,
                    target_record=act.id,
                    draft_text=draft_text,
                    evidence=act.evidence,
                    status=act.status,
                    responsible_area=act.responsible_area or "client",
                )

        raise HTTPException(status_code=404, detail=f"Action '{action_id}' not found.")


@app.put("/api/actions/{action_id}/draft")
def update_action_draft(action_id: str, payload: ActionDraftUpdateRequest):
    """
    Allows the owner to edit and save a communication draft.
    Does NOT send external communications.
    """
    update_recommendation_state(fingerprint=action_id, status="pending", draft_text=payload.draft_text)
    return {"action_id": action_id, "updated": True, "draft_text": payload.draft_text}


@app.post("/api/database/reset")
def reset_database():
    """
    Truncates all tables in the database, allowing fresh data re-ingestion.
    Disabled in production mode for security.
    """
    env = os.getenv("APP_ENV", os.getenv("ENVIRONMENT", "development")).lower()
    if env in ("production", "prod"):
        raise HTTPException(
            status_code=403,
            detail="Database reset operation is disabled in production.",
        )
    with get_db() as cur:
        cur.execute(
            """
            TRUNCATE TABLE 
                messages, 
                production_videos, 
                invoices, 
                payments, 
                bookings, 
                leads, 
                team_members, 
                cost_rules, 
                clients,
                message_classifications,
                recommendation_states,
                identity_review_actions
            RESTART IDENTITY CASCADE;
            """
        )
        clear_import_history()
        return {
            "status": "success",
            "message": "Database has been completely truncated. Ready for fresh multi-file upload.",
        }


@app.get("/api/clients")
def list_clients(reference_date: Optional[str] = Query(None)):
    """List all canonical clients and third-party payers with aggregated metrics and risk scores."""
    ref_d = _resolve_ref_date(reference_date)
    with get_db() as cur:
        clients = get_clients_list(cur, ref_date=ref_d)
        return jsonable_encoder(clients)


@app.get("/api/clients/{client_id}")
def get_client_detail(client_id: str, reference_date: Optional[str] = Query(None)):
    """Client 360 view: Full chronological activity timeline across leads, bookings, videos, invoices, payments, and messages."""
    ref_d = _resolve_ref_date(reference_date)
    with get_db() as cur:
        detail = get_client_360(cur, client_id, ref_date=ref_d)
        if not detail:
            raise HTTPException(status_code=404, detail=f"Client '{client_id}' not found.")
        return jsonable_encoder(detail)


@app.get("/api/identity/review")
def identity_review():
    """Identity resolution audit: canonical clients vs third-party payers, domain typos, and unlinked records."""
    with get_db() as cur:
        return jsonable_encoder(get_identity_review_queue(cur))


@app.post("/api/clients/match-override")
def match_override(payload: MatchOverrideRequest):
    """
    Human-in-the-loop manual client resolution:
    Overrides or sets client_id on any ambiguous record and persists the override in clients.notes.
    """
    valid_tables = {
        "leads": "lead_id",
        "bookings": "booking_id",
        "invoices": "invoice_no",
        "production_videos": "video_id",
        "messages": "id",
    }
    if payload.table_name not in valid_tables:
        raise HTTPException(status_code=400, detail=f"Invalid table name '{payload.table_name}'.")

    id_col = valid_tables[payload.table_name]
    with get_db() as cur:
        cur.execute("SELECT id, notes FROM clients WHERE id = %s;", (payload.client_id,))
        client_row = cur.fetchone()
        if not client_row:
            raise HTTPException(status_code=404, detail=f"Client '{payload.client_id}' not found.")

        cur.execute(
            f"UPDATE {payload.table_name} SET client_id = %s WHERE {id_col} = %s;",
            (payload.client_id, payload.record_id),
        )
        # Persist override in clients.notes JSON so future re-imports preserve the manual link
        meta: Dict[str, Any] = {}
        if (client_row.get("notes") or "").startswith("{"):
            try:
                meta = json.loads(client_row["notes"])
            except Exception:
                meta = {}
        overrides = meta.get("manual_overrides") or []
        overrides = [
            ov
            for ov in overrides
            if not (ov.get("table") == payload.table_name and str(ov.get("record_id")) == str(payload.record_id))
        ]
        overrides.append({"table": payload.table_name, "record_id": str(payload.record_id)})
        meta["manual_overrides"] = overrides
        cur.execute("UPDATE clients SET notes = %s WHERE id = %s;", (json.dumps(meta), payload.client_id))

        return {
            "status": "success",
            "table": payload.table_name,
            "record_id": payload.record_id,
            "client_id": payload.client_id,
        }


@app.post("/api/identity/action")
def identity_action(payload: IdentityReviewActionRequest):
    """
    Executes Confirm, Reject, or Assign identity actions.
    Persists the override or rejection in database and client notes so corrections survive re-imports.
    """
    with get_db() as cur:
        try:
            res = process_identity_review_action(
                cur=cur,
                table_name=payload.table_name,
                record_id=payload.record_id,
                action=payload.action,
                suggested_client_id=payload.suggested_client_id,
                assigned_client_id=payload.assigned_client_id,
                reason=payload.reason,
                performed_by=payload.performed_by,
            )
            return res
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/finance/reconciliation", response_model=FinanceReconciliationResponse)
def finance_reconciliation(reference_date: Optional[str] = Query(None)):
    """Transparent financial reconciliation: Overdue receivables, billing tool mistakes, we owe, and unbilled work."""
    ref_d = _resolve_ref_date(reference_date)
    with get_db() as cur:
        return get_finance_reconciliation(cur, ref_date=ref_d)


@app.get("/api/production/lost-requests", response_model=LostRequestsResponse)
def lost_requests():
    """Identifies lost client requests, voice note routing failure, root cause, and timeline."""
    with get_db() as cur:
        return get_lost_requests(cur)


@app.get("/api/production/overview")
def production_overview():
    """Production board status, stage breakdown, editor hours, costs, and revision counts."""
    with get_db() as cur:
        overview = get_production_overview(cur)
        return jsonable_encoder(overview)


@app.get("/api/messages")
def messages_intelligence():
    """Complete 190-message intelligence: privacy alerts, repeated complaints, voice note audit, and opportunities."""
    with get_db() as cur:
        return jsonable_encoder(analyze_messages(cur))


@app.get("/api/leads/overview")
def leads_overview():
    """Lead pipeline breakdown, channel win rates, duplicate enquiries, and unanswered leads."""
    with get_db() as cur:
        leads = get_leads_overview(cur)
        return jsonable_encoder(leads)


@app.get("/api/marketing/analysis")
def marketing_analysis():
    """Marketing channel acquisition performance and rigorous limitations statement."""
    with get_db() as cur:
        analysis = get_marketing_analysis(cur)
        return jsonable_encoder(analysis)


@app.get("/api/answers")
@app.get("/api/answers-export")
def answers_export(
    live_link: str = "",
    video_link: str = "",
    code_link: str = "",
    reference_date: Optional[str] = Query(None),
):
    """Exports exact answers.json structure adhering 100% to template specification."""
    ref_d = _resolve_ref_date(reference_date)
    with get_db() as cur:
        return generate_answers_json(
            cur,
            pack_id="213",
            live_link=live_link,
            video_link=video_link,
            code_link=code_link,
            ref_date=ref_d,
        )


# ==========================================
# GOOGLE GEMINI MESSAGE CLASSIFICATION APIS
# (Google Gemini is the ONLY AI provider)
# ==========================================

@app.get("/api/gemini/status", response_model=GeminiStatusResponse)
def gemini_status():
    """
    Returns current Google Gemini provider status, configured model, and message counts.
    Never exposes API key.
    """
    return GeminiStatusResponse(**get_provider_status())


@app.post("/api/gemini/classify", response_model=GeminiClassifyResponse)
def gemini_classify(payload: GeminiClassifyRequest):
    """
    Classifies a message text or message ID using Google Gemini.
    In dry_run mode or if GEMINI_API_KEY is not set, runs deterministic mock classifier.
    """
    mid = payload.message_id or "test-msg"
    status_info = get_provider_status()
    if not status_info["configured"] and not payload.dry_run:
        raise HTTPException(
            status_code=503,
            detail="Google Gemini API key is not configured. Live classification is BLOCKED. Configure GEMINI_API_KEY or use dry_run=True.",
        )

    if status_info["configured"] and not payload.dry_run:
        batch_out = classify_message_batch(
            [{"id": mid, "message_text": payload.text, "channel": "Direct", "sender": "User"}],
            force_reclassify=True,
            dry_run=False,
        )
        if batch_out.get("results"):
            cleaned = batch_out["results"][0]
            return GeminiClassifyResponse(
                message_id=mid,
                primary_category=cleaned["primary_category"],
                secondary_categories=cleaned.get("secondary_categories", []),
                is_spam_or_test=cleaned.get("is_spam_or_test", False),
                spam_reason=cleaned.get("spam_reason"),
                sentiment=cleaned.get("sentiment", "neutral"),
                urgency=cleaned.get("urgency", "normal"),
                needs_human_follow_up=cleaned.get("needs_human_follow_up", False),
                needs_reply=cleaned.get("needs_reply"),
                requested_action=cleaned.get("requested_action"),
                concise_summary=cleaned.get("concise_summary", ""),
                evidence_quotes=cleaned.get("evidence_quotes", []),
                mentioned_record_ids=cleaned.get("mentioned_record_ids", []),
                confidence=cleaned.get("confidence", 0.95),
                classification_notes=cleaned.get("classification_notes"),
                status=cleaned.get("status", "classified"),
                provider="google_gemini",
                model=settings.GEMINI_MODEL,
            )

    mock_res = deterministic_mock_classify(mid, payload.text)
    cleaned = validate_and_clean_item(GeminiMessageItem(**mock_res), payload.text)
    return GeminiClassifyResponse(
        message_id=mid,
        primary_category=cleaned["primary_category"],
        secondary_categories=cleaned["secondary_categories"],
        is_spam_or_test=cleaned["is_spam_or_test"],
        spam_reason=cleaned["spam_reason"],
        sentiment=cleaned["sentiment"],
        urgency=cleaned["urgency"],
        needs_human_follow_up=cleaned["needs_human_follow_up"],
        needs_reply=cleaned["needs_reply"],
        requested_action=cleaned["requested_action"],
        concise_summary=cleaned["concise_summary"],
        evidence_quotes=cleaned["evidence_quotes"],
        mentioned_record_ids=cleaned["mentioned_record_ids"],
        confidence=cleaned["confidence"],
        classification_notes=cleaned["classification_notes"],
        status=cleaned["status"],
        provider="google_gemini",
        model=settings.GEMINI_MODEL,
    )


@app.post("/api/gemini/batch", response_model=GeminiBatchClassifyResponse)
def gemini_batch(payload: GeminiBatchClassifyRequest):
    """
    Batches message classification with official Google GenAI SDK.
    Skips already classified messages by content hash.
    """
    limit_clause = f"LIMIT {payload.limit}" if payload.limit and payload.limit > 0 else ""
    with get_db() as cur:
        cur.execute(
            f"SELECT id, message_date, channel, sender, message_text FROM messages ORDER BY message_date ASC {limit_clause};"
        )
        msgs = cur.fetchall()

    res = classify_message_batch(
        [dict(m) for m in msgs],
        force_reclassify=payload.force_reclassify,
        dry_run=payload.dry_run,
    )
    return GeminiBatchClassifyResponse(**res)


@app.post("/api/gemini/review/{message_id}")
def gemini_review(message_id: str, payload: GeminiHumanReviewRequest):
    """
    Persists human review override in PostgreSQL so corrections survive re-imports.
    """
    try:
        updated = save_human_review(
            message_id=message_id,
            primary_category=payload.primary_category,
            is_spam_or_test=payload.is_spam_or_test,
            urgency=payload.urgency,
            notes=payload.notes,
            secondary_categories=payload.secondary_categories,
            reviewer=payload.reviewer,
        )
        return {"status": "success", "message_id": message_id, "classification": updated}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/gemini/classifications")
def gemini_classifications(
    category: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    is_spam: Optional[bool] = Query(None),
    limit: int = Query(200),
):
    """Returns persistent classifications from PostgreSQL joined with original messages."""
    query = """
        SELECT mc.*, m.sender, m.channel, m.message_date, m.message_text
        FROM message_classifications mc
        LEFT JOIN messages m ON mc.message_id = m.id::text
        WHERE 1=1
    """
    params = []
    if category:
        query += " AND mc.primary_category = %s"
        params.append(category)
    if status:
        query += " AND mc.status = %s"
        params.append(status)
    if is_spam is not None:
        query += " AND mc.is_spam_or_test = %s"
        params.append(is_spam)
    query += " ORDER BY mc.updated_at DESC LIMIT %s;"
    params.append(limit)

    with get_db() as cur:
        cur.execute(query, tuple(params))
        rows = cur.fetchall()
        return jsonable_encoder([dict(r) for r in rows])


# Legacy TypeSafe Jev endpoints preserved for backward compatibility
@app.get("/api/jev/benchmark")
def jev_benchmark():
    """Deprecated benchmark endpoint. Google Gemini is the ONLY AI provider."""
    return {
        "status": "deprecated",
        "provider": "google_gemini",
        "model": settings.GEMINI_MODEL,
        "active_provider": "google_gemini",
        "note": "Google Gemini is the ONLY AI provider per specification. Use /api/gemini/status.",
        "sample_size": 0,
        "correct_predictions": 0,
        "accuracy_percentage": None,
    }


@app.post("/api/jev/classify", response_model=JevClassificationResponse)
def jev_classify(payload: JevClassificationRequest):
    """Deprecated classify endpoint. Routes to deterministic classifier with Gemini note."""
    mock_res = deterministic_mock_classify("legacy-jev", payload.text)
    return JevClassificationResponse(
        text=payload.text,
        category=mock_res["primary_category"],
        confidence=mock_res["confidence"],
        provider="google_gemini_mock",
        model=settings.GEMINI_MODEL,
        cached=False,
        is_urgent_prob=0.95 if mock_res["urgency"] in ("critical", "high") else 0.20,
        has_privacy_risk_prob=0.99 if mock_res["primary_category"] == "privacy_release_or_face_blur" else 0.01,
        notes="Classified via Gemini baseline rules. Use /api/gemini/classify for official API.",
    )


@app.post("/api/upload/preview", response_model=List[UploadResult])
async def preview_upload_files(files: List[UploadFile] = File(...)):
    """
    Dry-run import preview:
    Detects file types, validates every row against live schema/tables, and reports
    inserted/updated/skipped/rejected counts + warnings without mutating the database.
    """
    results: List[UploadResult] = []
    with get_db() as cur:
        for file in files:
            content = await file.read()
            res = process_uploaded_file(
                cur,
                file.filename or "unknown",
                content,
                run_reconcile=False,
                dry_run=True,
            )
            results.append(res)
    return results


@app.get("/api/upload/history")
def upload_history():
    """Returns recent import history events and current database row counts."""
    with get_db() as cur:
        return jsonable_encoder(get_import_history(cur))


@app.get("/api/search")
def global_search(q: str = ""):
    """
    Global search across clients, leads, bookings, invoices, payments, videos, and messages
    with full source provenance and navigation links.
    """
    query = (q or "").strip()
    if len(query) < 2:
        return {"query": query, "results": []}

    pat = f"%{query}%"
    results: List[Dict[str, Any]] = []
    with get_db() as cur:
        # 1. Clients & Third-Party Payers
        cur.execute(
            """
            SELECT id, canonical_name, aliases, notes
            FROM clients
            WHERE canonical_name ILIKE %s OR aliases::text ILIKE %s
            ORDER BY canonical_name ASC
            LIMIT 8;
            """,
            (pat, pat),
        )
        for r in cur.fetchall():
            results.append(
                {
                    "type": "client",
                    "id": str(r["id"]),
                    "title": r["canonical_name"],
                    "subtitle": f"Aliases: {', '.join((r.get('aliases') or [])[:3]) or 'None'}",
                    "source": "clients (reconciled entity)",
                    "href": f"/clients/{r['id']}",
                }
            )

        # 2. Leads
        cur.execute(
            """
            SELECT l.lead_id, l.name, l.business, l.email, l.phone, l.source, l.status, l.client_id
            FROM leads l
            WHERE l.lead_id ILIKE %s OR l.name ILIKE %s OR l.business ILIKE %s OR l.email ILIKE %s OR l.phone ILIKE %s
            ORDER BY l.lead_id ASC
            LIMIT 6;
            """,
            (pat, pat, pat, pat, pat),
        )
        for r in cur.fetchall():
            results.append(
                {
                    "type": "lead",
                    "id": r["lead_id"],
                    "title": f"{r['lead_id']} — {r.get('business') or r.get('name') or 'Lead'}",
                    "subtitle": f"{r.get('name') or ''} · {r.get('source') or ''} · status: {r.get('status') or ''}",
                    "source": f"leads.csv ({r['lead_id']})",
                    "href": f"/clients/{r['client_id']}" if r.get("client_id") else "/requests",
                }
            )

        # 3. Invoices
        cur.execute(
            """
            SELECT i.invoice_no, i.bill_to, i.amount, i.status, i.due, i.memo, i.client_id
            FROM invoices i
            WHERE i.invoice_no ILIKE %s OR i.bill_to ILIKE %s OR i.memo ILIKE %s
            ORDER BY i.invoice_no ASC
            LIMIT 6;
            """,
            (pat, pat, pat),
        )
        for r in cur.fetchall():
            results.append(
                {
                    "type": "invoice",
                    "id": r["invoice_no"],
                    "title": f"{r['invoice_no']} — {r.get('bill_to') or 'Client'} (${r['amount']})",
                    "subtitle": f"Status: {r.get('status')} · Due: {r.get('due')} · {r.get('memo') or 'No memo'}",
                    "source": f"invoices.csv ({r['invoice_no']})",
                    "href": f"/clients/{r['client_id']}" if r.get("client_id") else "/money",
                }
            )

        # 4. Payments
        cur.execute(
            """
            SELECT p.payment_id, p.payer, p.amount, p.payment_date, p.method, p.reference, i.client_id
            FROM payments p
            LEFT JOIN invoices i ON p.matched_invoice_no = i.invoice_no
            WHERE p.payment_id ILIKE %s OR p.payer ILIKE %s OR p.reference ILIKE %s
            ORDER BY p.payment_id ASC
            LIMIT 6;
            """,
            (pat, pat, pat),
        )
        for r in cur.fetchall():
            results.append(
                {
                    "type": "payment",
                    "id": r["payment_id"],
                    "title": f"{r['payment_id']} — {r.get('payer') or 'Payer'} (${r['amount']})",
                    "subtitle": f"{r.get('payment_date')} via {r.get('method')} · Ref: {r.get('reference') or 'Blank'}",
                    "source": f"payments.csv ({r['payment_id']})",
                    "href": f"/clients/{r['client_id']}" if r.get("client_id") else "/money",
                }
            )

        # 5. Bookings
        cur.execute(
            """
            SELECT b.booking_id, b.client_name, b.service, b.status, b.date, b.price, b.client_id
            FROM bookings b
            WHERE b.booking_id ILIKE %s OR b.client_name ILIKE %s OR b.service ILIKE %s
            ORDER BY b.booking_id ASC
            LIMIT 6;
            """,
            (pat, pat, pat),
        )
        for r in cur.fetchall():
            results.append(
                {
                    "type": "booking",
                    "id": r["booking_id"],
                    "title": f"{r['booking_id']} — {r.get('client_name')} ({r.get('service')})",
                    "subtitle": f"{r.get('date')} · {r.get('status')} · ${r.get('price')}",
                    "source": f"bookings.csv ({r['booking_id']})",
                    "href": f"/clients/{r['client_id']}" if r.get("client_id") else "/money",
                }
            )

        # 6. Production Videos
        cur.execute(
            """
            SELECT pv.video_id, pv.client, pv.title, pv.editor, pv.stage, pv.notes_on_board, pv.client_id
            FROM production_videos pv
            WHERE pv.video_id ILIKE %s OR pv.title ILIKE %s OR pv.client ILIKE %s OR pv.editor ILIKE %s OR pv.notes_on_board ILIKE %s
            ORDER BY pv.video_id ASC
            LIMIT 6;
            """,
            (pat, pat, pat, pat, pat),
        )
        for r in cur.fetchall():
            results.append(
                {
                    "type": "video",
                    "id": r["video_id"],
                    "title": f"{r['video_id']} — {r.get('title')} ({r.get('client')})",
                    "subtitle": f"Stage: {r.get('stage')} · Editor: {r.get('editor')}",
                    "source": f"production_board.csv ({r['video_id']})",
                    "href": f"/clients/{r['client_id']}" if r.get("client_id") else "/production",
                }
            )

        # 7. Messages
        cur.execute(
            """
            SELECT m.id, m.channel, m.sender, m.message_date, m.message_text, m.client_id
            FROM messages m
            WHERE m.sender ILIKE %s OR m.message_text ILIKE %s
            ORDER BY m.message_date DESC
            LIMIT 6;
            """,
            (pat, pat),
        )
        for r in cur.fetchall():
            results.append(
                {
                    "type": "message",
                    "id": f"MSG-{r['id']}",
                    "title": f"[{r.get('channel')}] {r.get('sender')}",
                    "subtitle": (r.get("message_text") or "")[:95],
                    "source": f"messages.txt ({r.get('message_date')})",
                    "href": f"/clients/{r['client_id']}" if r.get("client_id") else "/requests",
                }
            )

    return {"query": query, "results": results}


@app.post("/api/upload", response_model=List[UploadResult])
async def upload_files(files: List[UploadFile] = File(...)):
    """
    Dynamic multi-file upload pipeline:
    Validates headers/dates/amounts, upserts records safely with SAVEPOINT isolation,
    and runs order-independent entity & payment reconciliation across the batch.
    """
    results: List[UploadResult] = []
    with get_db() as cur:
        any_changes = False
        for file in files:
            content = await file.read()
            res = process_uploaded_file(cur, file.filename or "unknown", content, run_reconcile=False)
            if res.rows_inserted > 0 or res.rows_updated > 0:
                any_changes = True
            results.append(res)
        if any_changes:
            reconcile_all_entities(cur)
            # Re-link payments.matched_invoice_no if invoices and payments were uploaded in the same batch
            cur.execute(
                """
                UPDATE payments p
                SET matched_invoice_no = i.invoice_no
                FROM invoices i
                WHERE p.matched_invoice_no IS NULL
                  AND UPPER(TRIM(p.reference)) = i.invoice_no;
                """
            )
    return results
