"""
Action Center & Deterministic Communication Drafts Service for Axeom StudioOS.
Manages persistent recommendation states in PostgreSQL with stable fingerprints.
Generates deterministic, verified prefilled drafts for owner review/editing.
NEVER sends external communications automatically.
"""

import hashlib
import json
import logging
from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional

from ..db import get_db

logger = logging.getLogger(__name__)


def generate_fingerprint(action_type: str, record_id: str, client_name: Optional[str] = None) -> str:
    """Generates a stable fingerprint based on issue type and record IDs."""
    raw = f"{action_type}:{record_id}:{client_name or ''}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def get_recommendation_states(cur) -> Dict[str, Dict[str, Any]]:
    """Loads all persisted recommendation states from PostgreSQL."""
    cur.execute("SELECT * FROM recommendation_states;")
    rows = cur.fetchall()
    return {r["fingerprint"]: dict(r) for r in rows}


def update_recommendation_state(
    fingerprint: str,
    status: str,
    draft_text: Optional[str] = None,
    notes: Optional[str] = None,
) -> bool:
    """Updates the persistent status and/or draft text of a recommendation."""
    valid_statuses = {"pending", "approved", "deferred", "dismissed", "completed"}
    if status not in valid_statuses:
        raise ValueError(f"Invalid status '{status}'. Must be one of {valid_statuses}")

    with get_db() as cur:
        cur.execute(
            """
            UPDATE recommendation_states
            SET 
                status = %s,
                draft_text = COALESCE(%s, draft_text),
                notes = COALESCE(%s, notes),
                updated_at = NOW()
            WHERE fingerprint = %s;
            """,
            (status, draft_text, notes, fingerprint),
        )
        return cur.rowcount > 0


def generate_draft_for_action(action: Dict[str, Any]) -> str:
    """
    Deterministically generates an editable communication draft using verified fields.
    Never uses an LLM. Cites exact verified business records.
    """
    act_type = action.get("action_type") or ""
    client = action.get("client_name") or "Valued Client"
    evidence = action.get("evidence") or []
    target_record = action.get("target_record") or ""

    if "privacy" in act_type:
        return (
            f"Subject: Important Update: Media Release & Video Review for {client}\n\n"
            f"Hi {client} Team,\n\n"
            f"We are conducting a quality and compliance review of video {target_record or 'your recent content'}. "
            f"Before this video is finalized and distributed, we wanted to confirm that all required media releases "
            f"are on file and confirm whether any subject faces require blurring as requested.\n\n"
            f"Please let us know if you have any questions or additional instructions.\n\n"
            f"Best regards,\n"
            f"Axeom Studio Team"
        )

    if "retainer" in act_type or "client" in act_type:
        return (
            f"Subject: Axeom Studio & {client} — Monthly Partnership Check-in\n\n"
            f"Hi {client} Team,\n\n"
            f"I wanted to reach out personally to schedule a brief 10-minute check-in regarding our ongoing monthly "
            f"content partnership. We want to ensure all recent video deliverables, titling, and compliance branding "
            f"match your exact standards, and review our schedule for upcoming shoots.\n\n"
            f"Are you available for a quick call this week?\n\n"
            f"Best regards,\n"
            f"Studio Owner, Axeom Studio"
        )

    if "money" in act_type or "overdue" in act_type or "finance" in act_type:
        ev_summary = "; ".join(evidence[:2]) if evidence else "outstanding billing"
        return (
            f"Subject: Statement of Account / Invoice Follow-up — {client}\n\n"
            f"Hi {client} Accounts Team,\n\n"
            f"We are reconciling our studio billing records ({ev_summary}). "
            f"We show an outstanding balance for recent production sessions. "
            f"Could you please confirm if this payment has been processed, or let us know if you need updated invoice copies "
            f"or ACH wiring instructions?\n\n"
            f"Thank you for your prompt attention.\n\n"
            f"Warm regards,\n"
            f"Axeom Studio Billing"
        )

    if "lead" in act_type:
        return (
            f"Subject: Thank you for contacting Axeom Studio!\n\n"
            f"Hi {client},\n\n"
            f"Thank you for reaching out regarding video production and studio session booking. "
            f"We'd love to learn more about your upcoming project and discuss how we can help you create high-impact content.\n\n"
            f"Could you share a bit more about your target timeline and preferred shoot dates?\n\n"
            f"Best regards,\n"
            f"Axeom Studio Team"
        )

    return (
        f"Subject: Follow-up regarding {client}\n\n"
        f"Hi {client} Team,\n\n"
        f"We are following up on your recent studio request ({target_record}). "
        f"Please let us know how you would like us to proceed.\n\n"
        f"Best regards,\n"
        f"Axeom Studio"
    )


def sync_recommendations_to_db(cur, recommendations: List[Dict[str, Any]]):
    """
    Persists recommendation items to `recommendation_states` without overwriting
    existing owner-approved or dismissed states.
    """
    for rec in recommendations:
        fp = rec.get("fingerprint") or rec.get("id")
        cur.execute(
            """
            INSERT INTO recommendation_states (
                fingerprint, action_type, title, status, priority, urgency,
                responsible_area, target_client, target_record, why_it_matters,
                suggested_action, what_is_uncertain, evidence, draft_text, updated_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s, NOW()
            )
            ON CONFLICT (fingerprint) DO UPDATE
            SET 
                priority = EXCLUDED.priority,
                urgency = EXCLUDED.urgency,
                why_it_matters = EXCLUDED.why_it_matters,
                suggested_action = EXCLUDED.suggested_action,
                what_is_uncertain = EXCLUDED.what_is_uncertain,
                evidence = EXCLUDED.evidence,
                draft_text = CASE 
                    WHEN recommendation_states.draft_text IS NOT NULL AND recommendation_states.draft_text != '' 
                    THEN recommendation_states.draft_text 
                    ELSE EXCLUDED.draft_text 
                END,
                updated_at = NOW();
            """,
            (
                fp,
                rec.get("action_type") or "general",
                rec.get("title") or "Recommended Action",
                rec.get("status") or "pending",
                rec.get("priority", 1),
                rec.get("urgency", "High"),
                rec.get("responsible_area", "client"),
                rec.get("client_name"),
                rec.get("target_record"),
                rec.get("why_it_matters"),
                rec.get("suggested_action"),
                rec.get("what_is_uncertain"),
                json.dumps(rec.get("evidence", [])),
                rec.get("draft_text") or generate_draft_for_action(rec),
            ),
        )
