import json
import re
from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from ..config import settings
from .date_service import get_active_reference_date
from .messages_service import analyze_messages


def _parse_client_meta(notes_raw: Optional[str]) -> Dict[str, Any]:
    if notes_raw and notes_raw.strip().startswith("{"):
        try:
            return json.loads(notes_raw)
        except Exception:
            return {}
    return {}


def calculate_client_health(
    cid: str,
    canonical_name: str,
    meta: Dict[str, Any],
    has_activity: bool,
    msgs: List[Dict[str, Any]],
    priv_alerts: List[Dict[str, Any]],
    complaints: List[Dict[str, Any]],
    overdue_info: Optional[Dict[str, Any]],
    revision_info: Optional[Dict[str, Any]],
    ref_date: date,
) -> Dict[str, Any]:
    """
    Computes evidence-based deterministic client health status and factors.
    Strictly deterministic Python logic; no black-box AI scores.
    """
    if not has_activity:
        return {
            "health_status": "insufficient_data",
            "health_score": 50,
            "risk_score": "Not assessed",
            "contributing_factors": [{"factor": "no_records", "weight": 0, "description": "No activity records found."}],
            "supporting_record_ids": [],
            "last_interaction_date": None,
            "unresolved_requests_count": 0,
            "recurrence_count": 0,
            "next_step": "Import client activity records or initial booking.",
            "data_completeness": "minimal",
        }

    # Detect if client explicitly requested a pause
    is_paused = False
    pause_evidence = []
    for m in msgs:
        t_low = (m.get("message_text") or "").lower()
        if "pause after this month" in t_low or "pausing our retainer" in t_low or "pause the retainer" in t_low:
            is_paused = True
            pause_evidence.append(f"MSG-L{m.get('line_number') or m.get('id')}")

    if is_paused:
        return {
            "health_status": "paused",
            "health_score": 40,
            "risk_score": "Medium",
            "contributing_factors": [
                {
                    "factor": "client_requested_pause",
                    "weight": 30,
                    "description": "Client requested retainer pause; labelled 'Paused / reactivation needed'.",
                    "records": pause_evidence,
                }
            ],
            "supporting_record_ids": pause_evidence,
            "last_interaction_date": msgs[-1].get("date") if msgs else None,
            "unresolved_requests_count": 0,
            "recurrence_count": 0,
            "next_step": "Reach out for scheduled retainer reactivation discussion.",
            "data_completeness": "complete",
        }

    factors = []
    supporting_ids = []
    score = 100  # Start healthy

    # 1. Privacy / Unsigned release on delivered videos (weight -40)
    if priv_alerts:
        p_ids = [p.get("video_id") or f"MSG-L{p.get('line_number')}" for p in priv_alerts]
        supporting_ids.extend(p_ids)
        factors.append({
            "factor": "privacy_unsigned_release",
            "weight": -40,
            "description": f"{len(priv_alerts)} video(s) delivered without verified media releases or requested face blur.",
            "records": p_ids,
        })
        score -= min(45, len(priv_alerts) * 25)

    # 2. Unresolved repeated complaints / ignored voice notes (weight -35)
    if complaints:
        c_ids = [f"MSG-L{c.get('line_number') or c.get('id')}" for c in complaints]
        supporting_ids.extend(c_ids)
        factors.append({
            "factor": "unresolved_repeated_complaints",
            "weight": -35,
            "description": f"{len(complaints)} unresolved complaint(s) following ignored edit notes.",
            "records": c_ids,
        })
        score -= min(40, len(complaints) * 20)

    # 3. Contract / retention escalations (weight -30)
    contract_msgs = [
        m for m in msgs
        if any(w in (m.get("message_text") or "").lower() for w in ("talk about our contract", "whether we continue", "compliance cares"))
    ]
    if contract_msgs:
        m_ids = [f"MSG-L{m.get('line_number') or m.get('id')}" for m in contract_msgs]
        supporting_ids.extend(m_ids)
        factors.append({
            "factor": "contract_renewal_at_risk",
            "weight": -30,
            "description": "Client explicitly requested contract/compliance review.",
            "records": m_ids,
        })
        score -= 30

    # 4. Repeated revisions (weight -15)
    if revision_info and int(revision_info.get("revision_count") or 0) > 0:
        rcnt = int(revision_info["revision_count"])
        factors.append({
            "factor": "excessive_revision_cycles",
            "weight": -15,
            "description": f"{rcnt} video(s) in repeated revision cycles (>= 2 rounds).",
            "records": [],
        })
        score -= min(20, rcnt * 10)

    # 5. Overdue receivables (weight -10)
    if overdue_info and int(overdue_info.get("overdue_count") or 0) > 0:
        ocnt = int(overdue_info["overdue_count"])
        oamt = overdue_info.get("overdue_amt") or "0.00"
        factors.append({
            "factor": "overdue_receivables",
            "weight": -10,
            "description": f"{ocnt} invoice(s) overdue totaling ${oamt}.",
            "records": [],
        })
        score -= min(15, ocnt * 5)

    # Counter-signals (positive feedback, on-time approvals)
    positive_msgs = [
        m for m in msgs
        if any(w in (m.get("message_text") or "").lower() for w in ("approved! post it", "thanks team", "love it", "great work"))
    ]
    if positive_msgs:
        pos_ids = [f"MSG-L{m.get('line_number') or m.get('id')}" for m in positive_msgs]
        factors.append({
            "factor": "positive_feedback_counter_signal",
            "weight": +15,
            "description": f"{len(positive_msgs)} recorded positive approval(s).",
            "records": pos_ids,
        })
        score = min(100, score + 15)

    score = max(0, min(100, score))

    if score >= 80:
        health_status = "healthy"
        risk_score = "Low"
        next_step = "Continue scheduled monthly production."
    elif score >= 60:
        health_status = "monitor"
        risk_score = "Medium"
        next_step = "Check in on recent video delivery and upcoming shoot dates."
    elif score >= 40:
        health_status = "at_risk"
        risk_score = "High"
        next_step = "Prioritize pending revisions and schedule partner alignment call."
    else:
        health_status = "critical"
        risk_score = "High"
        next_step = "Immediate owner call: resolve compliance/privacy blocks and review contract."

    return {
        "health_status": health_status,
        "health_score": score,
        "risk_score": risk_score,
        "contributing_factors": factors,
        "supporting_record_ids": list(dict.fromkeys(supporting_ids)),
        "last_interaction_date": msgs[-1].get("date") if msgs else None,
        "unresolved_requests_count": len(complaints) + len(priv_alerts),
        "recurrence_count": len(complaints),
        "next_step": next_step,
        "data_completeness": "complete" if len(msgs) >= 2 else "partial",
    }


def get_clients_list(cur, ref_date: Optional[date] = None) -> List[Dict[str, Any]]:
    if ref_date is None:
        ref_date = get_active_reference_date()
    cur.execute(
        """
        SELECT 
            c.id,
            c.canonical_name,
            c.aliases,
            c.notes,
            c.created_at,
            COALESCE(b.total_bookings, 0) AS total_bookings,
            COALESCE(i.total_invoiced, 0) AS total_invoiced,
            COALESCE(pv.total_videos, 0) AS total_videos,
            COALESCE(m.total_messages, 0) AS total_messages
        FROM clients c
        LEFT JOIN (
            SELECT client_id, COUNT(*) AS total_bookings 
            FROM bookings 
            GROUP BY client_id
        ) b ON b.client_id = c.id
        LEFT JOIN (
            SELECT client_id, SUM(amount) AS total_invoiced 
            FROM invoices 
            WHERE status != 'void' 
            GROUP BY client_id
        ) i ON i.client_id = c.id
        LEFT JOIN (
            SELECT client_id, COUNT(*) AS total_videos 
            FROM production_videos 
            GROUP BY client_id
        ) pv ON pv.client_id = c.id
        LEFT JOIN (
            SELECT client_id, COUNT(*) AS total_messages 
            FROM messages 
            GROUP BY client_id
        ) m ON m.client_id = c.id
        ORDER BY c.canonical_name ASC;
        """
    )
    rows = cur.fetchall()

    msg_analysis = analyze_messages(cur)
    msgs_by_client: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for m in msg_analysis["messages"]:
        if m.get("client_id"):
            msgs_by_client[str(m["client_id"])].append(m)

    privacy_by_client: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for p in msg_analysis["privacy_alerts"]:
        if p.get("client_id"):
            privacy_by_client[str(p["client_id"])].append(p)

    complaints_by_client: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for c in msg_analysis["repeated_complaints"]:
        if c.get("client_id"):
            complaints_by_client[str(c["client_id"])].append(c)

    contract_risk_by_client: Dict[str, List[str]] = defaultdict(list)
    for m in msg_analysis["messages"]:
        cid = m.get("client_id")
        if cid and ("contract_retention_risk" in m.get("categories", []) or "paid_cancellation" in m.get("categories", [])):
            contract_risk_by_client[str(cid)].append(m["message_text"])

    cur.execute(
        """
        SELECT client_id, COUNT(*) AS overdue_count, SUM(amount) AS overdue_amt
        FROM invoices
        WHERE status IN ('unpaid', 'partial') AND due < %s
        GROUP BY client_id;
        """,
        (ref_date,),
    )
    overdues = {str(r["client_id"]): r for r in cur.fetchall() if r.get("client_id")}

    cur.execute(
        """
        SELECT client_id, COUNT(*) AS revision_count
        FROM production_videos
        WHERE stage = 'In revision' OR revisions >= 2
        GROUP BY client_id;
        """
    )
    revisions = {str(r["client_id"]): r for r in cur.fetchall() if r.get("client_id")}

    result: List[Dict[str, Any]] = []
    for r in rows:
        cid = str(r["id"])
        meta = _parse_client_meta(r.get("notes"))
        etype = meta.get("entity_type", "client")
        pays_for = meta.get("pays_for") or []
        billed_via = meta.get("billed_via_payer")

        tb = int(r["total_bookings"] or 0)
        ti = Decimal(str(r["total_invoiced"] or "0.00")).quantize(Decimal("0.01"))
        tv = int(r["total_videos"] or 0)
        tm = int(r["total_messages"] or 0)
        has_activity = tb > 0 or ti > Decimal("0.00") or tv > 0 or tm > 0

        health = calculate_client_health(
            cid=cid,
            canonical_name=r["canonical_name"],
            meta=meta,
            has_activity=has_activity,
            msgs=msgs_by_client.get(cid, []),
            priv_alerts=privacy_by_client.get(cid, []),
            complaints=complaints_by_client.get(cid, []),
            overdue_info=overdues.get(cid),
            revision_info=revisions.get(cid),
            ref_date=ref_date,
        )

        reasons = [f["description"] for f in health["contributing_factors"]]
        if not reasons:
            if etype == "payer":
                reasons.append(f"Third-party billing agency paying monthly for {', '.join(pays_for)}.")
            elif billed_via:
                reasons.append(f"Active account; invoices billed monthly via {billed_via}.")
            else:
                reasons.append("Healthy account with active bookings and no open disputes.")

        result.append(
            {
                "id": cid,
                "canonical_name": r["canonical_name"],
                "aliases": r["aliases"] if isinstance(r["aliases"], list) else [],
                "notes": r["notes"],
                "created_at": r["created_at"],
                "total_bookings": tb,
                "total_invoiced": ti,
                "total_videos": tv,
                "total_messages": tm,
                "risk_score": health["risk_score"],
                "health_status": health["health_status"],
                "health_score": health["health_score"],
                "contributing_factors": health["contributing_factors"],
                "supporting_record_ids": health["supporting_record_ids"],
                "last_interaction_date": health["last_interaction_date"],
                "unresolved_requests_count": health["unresolved_requests_count"],
                "recurrence_count": health["recurrence_count"],
                "next_step": health["next_step"],
                "data_completeness": health["data_completeness"],
                "risk_reason": " ".join(reasons),
                "entity_type": etype,
                "pays_for": pays_for,
                "billed_via_payer": billed_via,
                "match_confidence": "confirmed",
            }
        )
    return result


def get_client_360(cur, client_id: str, ref_date: Optional[date] = None) -> Optional[Dict[str, Any]]:
    if ref_date is None:
        ref_date = get_active_reference_date()
    cur.execute("SELECT * FROM clients WHERE id = %s;", (client_id,))
    client = cur.fetchone()
    if not client:
        return None

    meta = _parse_client_meta(client.get("notes"))
    etype = meta.get("entity_type", "client")
    pays_for = meta.get("pays_for") or []
    billed_via = meta.get("billed_via_payer")
    aliases_list = client["aliases"] if isinstance(client["aliases"], list) else []
    alias_low_set = {a.strip().lower() for a in aliases_list + [client["canonical_name"]] if isinstance(a, str) and a.strip()}

    cur.execute("SELECT * FROM leads WHERE client_id = %s ORDER BY created DESC;", (client_id,))
    leads = cur.fetchall()

    cur.execute("SELECT * FROM bookings WHERE client_id = %s ORDER BY date DESC;", (client_id,))
    bookings = cur.fetchall()

    cur.execute("SELECT * FROM invoices WHERE client_id = %s ORDER BY issued DESC;", (client_id,))
    invoices = cur.fetchall()
    inv_nos = {i["invoice_no"] for i in invoices}

    # Fetch all payments linked either by matched_invoice_no OR by payer/payer_email alias
    cur.execute("SELECT * FROM payments ORDER BY payment_date DESC, payment_id DESC;")
    all_payments = cur.fetchall()
    payments = [
        p
        for p in all_payments
        if (p.get("matched_invoice_no") and p["matched_invoice_no"] in inv_nos)
        or (p.get("payer_email") or "").strip().lower() in alias_low_set
        or (p.get("payer") or "").strip().lower() in alias_low_set
    ]

    cur.execute("SELECT * FROM production_videos WHERE client_id = %s ORDER BY video_id DESC;", (client_id,))
    videos = cur.fetchall()

    cur.execute("SELECT * FROM messages WHERE client_id = %s ORDER BY message_date ASC;", (client_id,))
    messages = cur.fetchall()

    # Build client-specific alerts from messages & finance
    msg_analysis = analyze_messages(cur)
    alerts: List[Dict[str, Any]] = []
    for p in msg_analysis["privacy_alerts"]:
        if p.get("client_id") == str(client_id):
            alerts.append(
                {
                    "type": "privacy_no_release",
                    "severity": "critical",
                    "title": f"Privacy / Face Blur Alert on {p.get('video_id') or 'Video'} ({p.get('video_title')})",
                    "detail": p.get("action_required") or p.get("message_text"),
                    "date": p.get("date"),
                }
            )
    for c in msg_analysis["repeated_complaints"]:
        if c.get("client_id") == str(client_id):
            alerts.append(
                {
                    "type": "repeated_complaint",
                    "severity": "high",
                    "title": f"Unresolved Edit Complaint on {c.get('video_id') or 'Video'} ({c.get('video_title')})",
                    "detail": c.get("message_text"),
                    "date": c.get("date"),
                }
            )
    for m in msg_analysis["messages"]:
        if m.get("client_id") == str(client_id) and (
            "contract_retention_risk" in m.get("categories", [])
            or "paid_cancellation" in m.get("categories", [])
        ):
            alerts.append(
                {
                    "type": "retention_or_cancellation",
                    "severity": "critical",
                    "title": "Contract / Account Retention Signal",
                    "detail": m.get("message_text"),
                    "date": m.get("date"),
                }
            )

    total_inv = sum((Decimal(str(i["amount"])) for i in invoices if i["status"] != "void"), Decimal("0.00"))
    total_paid_bank = sum((Decimal(str(p["amount"])) for p in payments), Decimal("0.00"))
    completed_bookings_val = sum(
        (Decimal(str(b["price"])) for b in bookings if (b.get("status") or "").lower() == "completed"),
        Decimal("0.00"),
    )

    cur.execute(
        """
        SELECT COUNT(*) AS overdue_count, SUM(amount) AS overdue_amt
        FROM invoices
        WHERE client_id = %s AND status IN ('unpaid', 'partial') AND due < %s;
        """,
        (client_id, ref_date),
    )
    overdue_row = cur.fetchone()

    cur.execute(
        """
        SELECT COUNT(*) AS revision_count
        FROM production_videos
        WHERE client_id = %s AND (stage = 'In revision' OR revisions >= 2);
        """,
        (client_id,),
    )
    rev_row = cur.fetchone()

    client_priv_alerts = [p for p in msg_analysis["privacy_alerts"] if p.get("client_id") == str(client_id)]
    client_complaints = [c for c in msg_analysis["repeated_complaints"] if c.get("client_id") == str(client_id)]
    has_activity = len(bookings) > 0 or total_inv > Decimal("0.00") or len(videos) > 0 or len(messages) > 0

    health = calculate_client_health(
        cid=str(client["id"]),
        canonical_name=client["canonical_name"],
        meta=meta,
        has_activity=has_activity,
        msgs=messages,
        priv_alerts=client_priv_alerts,
        complaints=client_complaints,
        overdue_info=dict(overdue_row) if overdue_row else None,
        revision_info=dict(rev_row) if rev_row else None,
        ref_date=ref_date,
    )

    return {
        "id": str(client["id"]),
        "canonical_name": client["canonical_name"],
        "aliases": aliases_list,
        "notes": client["notes"],
        "created_at": client["created_at"],
        "entity_type": etype,
        "pays_for": pays_for,
        "billed_via_payer": billed_via,
        "health_summary": health,
        "leads": leads,
        "bookings": bookings,
        "invoices": invoices,
        "payments": payments,
        "production_videos": videos,
        "messages": messages,
        "alerts": alerts,
        "financial_summary": {
            "total_invoiced": total_inv,
            "total_paid_in_bank": total_paid_bank,
            "completed_bookings_value": completed_bookings_val,
            "total_bookings": len(bookings),
            "total_videos": len(videos),
            "total_messages": len(messages),
            "entity_type": etype,
            "pays_for": pays_for,
            "billed_via_payer": billed_via,
        },
    }


def get_most_likely_to_leave(cur, ref_date: Optional[date] = None) -> Dict[str, Any]:
    """
    Dynamically identifies the active client most at risk of contract termination / churn
    from message transcripts, compliance complaints, and unpaid retainer invoices.
    """
    if ref_date is None:
        ref_date = get_active_reference_date()
    msg_analysis = analyze_messages(cur)
    cur.execute("SELECT id, canonical_name FROM clients;")
    clients_by_id = {str(r["id"]): r["canonical_name"] for r in cur.fetchall()}
    cur.execute(
        """
        SELECT invoice_no, client_id, amount, due, status, memo
        FROM invoices
        WHERE status IN ('unpaid', 'partial')
        ORDER BY issued ASC;
        """
    )
    open_invs_by_client: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for inv in cur.fetchall():
        if inv.get("client_id"):
            open_invs_by_client[str(inv["client_id"])].append(inv)

    # Score clients by active contract-review urgency, compliance complaints, and open retainer exposure
    client_scores: Dict[str, int] = defaultdict(int)
    client_msgs: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    for m in msg_analysis["messages"]:
        cid = m.get("client_id")
        if not cid:
            continue
        txt_low = (m.get("message_text") or "").lower()
        cats = m.get("categories") or []
        if "contract" in txt_low or "whether we continue" in txt_low:
            client_scores[cid] += 50
            client_msgs[cid].append(m)
        elif "compliance cares about this" in txt_low or "asked for the full name" in txt_low:
            client_scores[cid] += 30
            client_msgs[cid].append(m)
        elif "pause after this month" in txt_low:
            client_scores[cid] += 35
            client_msgs[cid].append(m)
        elif "repeated_complaint" in cats:
            client_scores[cid] += 10
            client_msgs[cid].append(m)

    for cid, invs in open_invs_by_client.items():
        if cid in client_scores:
            for inv in invs:
                if "retainer" in (inv.get("memo") or "").lower():
                    client_scores[cid] += 15

    if not client_scores:
        return {
            "client": "None identified",
            "evidence": [],
            "what_to_do_this_week": "No active churn signals detected.",
        }

    top_cid = max(client_scores.keys(), key=lambda k: client_scores[k])
    top_name = clients_by_id.get(top_cid, "Unknown Client")

    evidence: List[str] = []
    for m in sorted(client_msgs[top_cid], key=lambda x: x["line_number"]):
        evidence.append(
            f"[{m['date']}] {m['channel']} from {m['sender']} (line #{m['line_number']}): \"{m['message_text']}\""
        )

    for inv in open_invs_by_client.get(top_cid, []):
        is_ov = inv["due"] < ref_date
        ov_tag = f"OVERDUE (due {inv['due']})" if is_ov else f"open (due {inv['due']})"
        evidence.append(
            f"Invoice {inv['invoice_no']} for ${inv['amount']} ({inv.get('memo') or 'Retainer'}) remains {inv['status']} / {ov_tag}."
        )

    # Also note any client that already paused in prior messages
    already_paused: List[Dict[str, Any]] = []
    for cid, msgs in client_msgs.items():
        if cid == top_cid:
            continue
        for m in msgs:
            if "pause after this month" in (m.get("message_text") or "").lower():
                already_paused.append(
                    {
                        "client": clients_by_id.get(cid, "Unknown"),
                        "date": m["date"],
                        "line_number": m["line_number"],
                        "reason": m["message_text"],
                    }
                )

    return {
        "client": top_name,
        "evidence": evidence,
        "already_paused_clients": already_paused,
        "what_to_do_this_week": (
            f"Call {top_name} immediately to review their contract, confirm all future and existing videos enforce "
            f"their full legal name across captions/intros for compliance, and resolve open retainer billing."
        ),
    }


def get_identity_review_queue(cur) -> Dict[str, Any]:
    """
    Returns dynamic identity resolution audit: 30 canonical clients vs 1 third-party payer,
    corroborated domain typo fixes (.con -> .com), separated near-name collisions,
    rebrands/contact updates, and any unlinked records requiring human review.
    """
    cur.execute("SELECT id, canonical_name, aliases, notes FROM clients ORDER BY canonical_name ASC;")
    clients = cur.fetchall()

    service_clients = []
    payers = []
    for c in clients:
        meta = _parse_client_meta(c.get("notes"))
        item = {
            "id": str(c["id"]),
            "canonical_name": c["canonical_name"],
            "entity_type": meta.get("entity_type", "client"),
            "pays_for": meta.get("pays_for") or [],
            "billed_via_payer": meta.get("billed_via_payer"),
            "emails": meta.get("emails") or [],
            "phones": meta.get("phones") or [],
            "aliases": c["aliases"] if isinstance(c["aliases"], list) else [],
        }
        if item["entity_type"] == "payer":
            payers.append(item)
        else:
            service_clients.append(item)

    # Detect domain typos (.con) in bookings and invoices
    cur.execute("SELECT booking_id, client_name, email FROM bookings WHERE email ILIKE '%.con';")
    b_typos = cur.fetchall()
    cur.execute("SELECT invoice_no, bill_to, email FROM invoices WHERE email ILIKE '%.con';")
    i_typos = cur.fetchall()

    typo_records = [
        {"table": "bookings", "record_id": r["booking_id"], "name": r["client_name"], "raw_email": r["email"]}
        for r in b_typos
    ] + [
        {"table": "invoices", "record_id": r["invoice_no"], "name": r["bill_to"], "raw_email": r["email"]}
        for r in i_typos
    ]

    # Detect unlinked records across tables
    cur.execute("SELECT booking_id, client_name, email FROM bookings WHERE client_id IS NULL;")
    unlinked_bookings = [dict(r) for r in cur.fetchall()]
    cur.execute("SELECT invoice_no, bill_to, email FROM invoices WHERE client_id IS NULL;")
    unlinked_invoices = [dict(r) for r in cur.fetchall()]
    cur.execute("SELECT video_id, client, title FROM production_videos WHERE client_id IS NULL;")
    unlinked_videos = [dict(r) for r in cur.fetchall()]

    msg_analysis = analyze_messages(cur)
    unlinked_non_spam_messages = [
        {
            "id": m["id"],
            "line_number": m["line_number"],
            "channel": m["channel"],
            "sender": m["sender"],
            "message_text": m["message_text"],
        }
        for m in msg_analysis["messages"]
        if not m.get("client_id")
        and "suspicious_or_spam" not in (m.get("categories") or [])
        and m.get("direction") != "outbound"
    ]

    return {
        "canonical_clients_count": len(service_clients),
        "third_party_payers_count": len(payers),
        "total_entities_count": len(clients),
        "payers": payers,
        "typo_records_resolved": typo_records,
        "contact_and_brand_updates": msg_analysis["contact_and_brand_updates"],
        "quarantined_spam_count": len(msg_analysis["quarantined_messages"]),
        "unlinked_records": {
            "bookings": unlinked_bookings,
            "invoices": unlinked_invoices,
            "production_videos": unlinked_videos,
            "messages": unlinked_non_spam_messages,
        },
    }


def process_identity_review_action(
    cur,
    table_name: str,
    record_id: str,
    action: str,
    suggested_client_id: Optional[str] = None,
    assigned_client_id: Optional[str] = None,
    reason: Optional[str] = None,
    performed_by: str = "Studio Owner",
) -> Dict[str, Any]:
    """
    Executes and persists Confirm, Reject, or Assign identity actions.
    Updates the canonical link and records the action persistently so corrections survive re-imports.
    """
    valid_tables = {
        "leads": "lead_id",
        "bookings": "booking_id",
        "invoices": "invoice_no",
        "production_videos": "video_id",
        "messages": "id",
    }
    if table_name not in valid_tables:
        raise ValueError(f"Invalid table name '{table_name}'.")

    id_col = valid_tables[table_name]
    target_client_id = assigned_client_id if action == "assign" else suggested_client_id

    # Record in identity_review_actions table
    cur.execute(
        """
        INSERT INTO identity_review_actions (
            table_name, record_id, action, suggested_client_id, assigned_client_id, reason, performed_by, created_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
        ON CONFLICT (table_name, record_id, action) DO UPDATE
        SET suggested_client_id = EXCLUDED.suggested_client_id,
            assigned_client_id = EXCLUDED.assigned_client_id,
            reason = EXCLUDED.reason,
            performed_by = EXCLUDED.performed_by,
            created_at = NOW();
        """,
        (table_name, record_id, action, suggested_client_id, assigned_client_id, reason, performed_by),
    )

    if action in ("confirm", "assign") and target_client_id:
        cur.execute(f"UPDATE {table_name} SET client_id = %s WHERE {id_col} = %s;", (target_client_id, record_id))
        cur.execute("SELECT id, notes FROM clients WHERE id = %s;", (target_client_id,))
        client_row = cur.fetchone()
        if client_row:
            meta = _parse_client_meta(client_row.get("notes"))
            overrides = meta.get("manual_overrides") or []
            overrides = [ov for ov in overrides if not (ov.get("table") == table_name and str(ov.get("record_id")) == str(record_id))]
            overrides.append({
                "table": table_name,
                "record_id": str(record_id),
                "action": action,
                "by": performed_by,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            meta["manual_overrides"] = overrides
            cur.execute("UPDATE clients SET notes = %s WHERE id = %s;", (json.dumps(meta), target_client_id))

    elif action == "reject":
        cur.execute(f"UPDATE {table_name} SET client_id = NULL WHERE {id_col} = %s;", (record_id,))
        if suggested_client_id:
            cur.execute("SELECT id, notes FROM clients WHERE id = %s;", (suggested_client_id,))
            client_row = cur.fetchone()
            if client_row:
                meta = _parse_client_meta(client_row.get("notes"))
                rejected = meta.get("rejected_overrides") or []
                rejected = [r for r in rejected if not (r.get("table") == table_name and str(r.get("record_id")) == str(record_id))]
                rejected.append({
                    "table": table_name,
                    "record_id": str(record_id),
                    "rejected_client_id": suggested_client_id,
                    "by": performed_by,
                    "reason": reason or "User rejected suggested match",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                meta["rejected_overrides"] = rejected
                cur.execute("UPDATE clients SET notes = %s WHERE id = %s;", (json.dumps(meta), suggested_client_id))

    return {
        "status": "success",
        "action": action,
        "table": table_name,
        "record_id": record_id,
        "target_client_id": target_client_id,
        "performed_by": performed_by,
    }
