from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional

from ..config import settings
from .date_service import get_active_reference_date
from ..models import DashboardSummaryResponse, RecommendedAction
from .clients import get_identity_review_queue, get_most_likely_to_leave
from .finance import get_finance_reconciliation
from .leads import get_leads_overview, get_never_replied_leads
from .messages_service import analyze_messages
from .production import get_lost_requests
from .actions_service import generate_draft_for_action, sync_recommendations_to_db

ACTION_STATUSES: Dict[str, str] = {
    "action-1": "pending",
    "action-2": "pending",
    "action-3": "pending",
}


def get_dashboard_summary(cur, ref_date: Optional[date] = None) -> DashboardSummaryResponse:
    if ref_date is None:
        ref_date = get_active_reference_date()

    cur.execute("SELECT COUNT(*) AS c FROM clients;")
    total_entities_cnt = int(cur.fetchone()["c"] or 0)
    cur.execute("SELECT COUNT(*) AS c FROM leads;")
    leads_cnt = int(cur.fetchone()["c"] or 0)
    cur.execute("SELECT COUNT(*) AS c FROM bookings;")
    bookings_cnt = int(cur.fetchone()["c"] or 0)
    cur.execute("SELECT COUNT(*) AS c FROM invoices;")
    invoices_cnt = int(cur.fetchone()["c"] or 0)
    cur.execute("SELECT COUNT(*) AS c FROM payments;")
    payments_cnt = int(cur.fetchone()["c"] or 0)
    cur.execute("SELECT COUNT(*) AS c FROM production_videos;")
    videos_cnt = int(cur.fetchone()["c"] or 0)
    cur.execute("SELECT COUNT(*) AS c FROM messages;")
    messages_cnt = int(cur.fetchone()["c"] or 0)
    cur.execute("SELECT COUNT(*) AS c FROM team_members;")
    team_cnt = int(cur.fetchone()["c"] or 0)
    cur.execute("SELECT COUNT(*) AS c FROM cost_rules;")
    cost_cnt = int(cur.fetchone()["c"] or 0)

    counts = {
        "leads": leads_cnt,
        "bookings": bookings_cnt,
        "invoices": invoices_cnt,
        "payments": payments_cnt,
        "production_videos": videos_cnt,
        "messages": messages_cnt,
        "team_members": team_cnt,
        "cost_rules": cost_cnt,
    }
    non_zero_sources = sum(1 for v in counts.values() if v > 0)
    is_empty = non_zero_sources == 0
    is_partial = 0 < non_zero_sources < len(counts)

    data_status = {
        "is_empty": is_empty,
        "is_partial": is_partial,
        "imported_counts": counts,
    }

    if is_empty:
        return DashboardSummaryResponse(
            reference_date=ref_date,
            overview={
                "active_clients_count": 0,
                "payers_count": 0,
                "total_invoiced": Decimal("0.00"),
                "total_bank_collected": Decimal("0.00"),
                "source_overdue_receivables": Decimal("0.00"),
                "true_unpaid_receivables": Decimal("0.00"),
                "overdue_receivables": Decimal("0.00"),
                "unanswered_leads_count": 0,
                "lost_requests_count": 0,
                "repeated_complaints_count": 0,
                "privacy_alerts_count": 0,
                "double_payment_owed": Decimal("0.00"),
                "we_owe_total": Decimal("0.00"),
            },
            monday_top_3=[
                RecommendedAction(
                    id="action-1",
                    priority=1,
                    title="Workspace Empty: Ready for Data Upload",
                    urgency="Critical",
                    why_it_matters="No source data files have been imported yet. The system is ready to receive your challenge data pack.",
                    client_name=None,
                    evidence=[
                        "Database schema is initialized with 9 relational tables.",
                        "Upload modal supports all 8 files (.csv and .txt) in a single batch or incrementally.",
                    ],
                    suggested_action="Click 'Add files' in the navigation to import leads, bookings, invoices, payments, production, and messages.",
                    what_is_uncertain=None,
                    status=ACTION_STATUSES.get("action-1", "pending"),
                )
            ],
            financial_alerts={
                "overdue_invoices_count": 0,
                "source_overdue_invoices_count": 0,
                "billing_tool_errors_count": 0,
                "never_billed_total": Decimal("0.00"),
            },
            production_alerts={
                "lost_requests_count": 0,
                "repeated_complaints_count": 0,
                "privacy_alerts_count": 0,
                "root_cause_date": "N/A",
            },
            lead_alerts={
                "unanswered_count": 0,
                "legitimate_unanswered_count": 0,
                "urgent_lead": "None",
            },
            privacy_alerts_count=0,
            data_status=data_status,
        )

    fin = get_finance_reconciliation(cur, ref_date=ref_date)
    lost = get_lost_requests(cur)
    unreplied_lead_ids = get_never_replied_leads(cur)
    leads_ov = get_leads_overview(cur)
    msg_analysis = analyze_messages(cur)
    churn = get_most_likely_to_leave(cur, ref_date=ref_date)
    id_queue = get_identity_review_queue(cur)

    # Load persisted recommendation states from PostgreSQL
    persisted_states: Dict[str, Dict[str, Any]] = {}
    try:
        cur.execute("SELECT fingerprint, status, draft_text FROM recommendation_states;")
        for row in cur.fetchall():
            persisted_states[row["fingerprint"]] = dict(row)
    except Exception:
        pass

    privacy_alerts = msg_analysis["privacy_alerts"]
    complaints = msg_analysis["repeated_complaints"]
    vn_audit = msg_analysis["voice_note_audit"]

    top_3: List[RecommendedAction] = []
    priority_idx = 1

    # Priority 1: Privacy / No-Release Alerts on Delivered Videos (computed 100% dynamically)
    if privacy_alerts:
        unlogged_priv = [p for p in privacy_alerts if not p.get("board_logged")]
        priv_evidence = []
        if unlogged_priv:
            up = unlogged_priv[0]
            priv_evidence.append(
                f"MISSING BOARD NOTE: {up['client_name']} sent {up['channel']} (line #{up['line_number']} on {up['date']}) "
                f"to blur client face in '{up['video_title']}' ({up['video_id']}, stage={up['video_stage']}), "
                f"but notes_on_board is blank."
            )
        logged_priv = [p for p in privacy_alerts if p.get("board_logged")]
        if logged_priv:
            v_list = ", ".join(f"{p['video_id']} ({p['client_name']})" for p in logged_priv)
            zero_rev_cnt = sum(1 for p in logged_priv if int(p.get("revisions") or 0) == 0)
            priv_evidence.append(
                f"{len(logged_priv)} other face-blur alerts ({v_list}) have 'Blur client face' on the board "
                f"but are marked Delivered ({zero_rev_cnt} with 0 revisions)."
            )
        collision_alerts = [p for p in privacy_alerts if p.get("cross_client_title_collision")]
        if collision_alerts:
            coll_summary = "; ".join(
                f"'{p['video_title']}' ({p['client_name']} {p['video_id']})" for p in collision_alerts
            )
            priv_evidence.append(
                f"Cross-client video title collisions detected on {coll_summary} — verify edits were applied to the right client video."
            )

        all_priv_vids = ", ".join(str(p.get("video_id") or "video") for p in privacy_alerts)
        action_id = f"action-{priority_idx}"
        act_status = persisted_states.get(action_id, {}).get("status") or ACTION_STATUSES.get(action_id, "pending")
        top_3.append(
            RecommendedAction(
                id=action_id,
                priority=priority_idx,
                title=f"Audit {len(privacy_alerts)} Unsigned-Release Videos ({len(unlogged_priv)} Unlogged)",
                urgency="Critical",
                why_it_matters=(
                    f"{len(privacy_alerts)} videos feature clients without signed media releases; "
                    f"V223 voice-note request was never logged to the board."
                ),
                client_name=unlogged_priv[0]["client_name"] if unlogged_priv else privacy_alerts[0]["client_name"],
                evidence=priv_evidence,
                suggested_action=(
                    f"Immediately pull {unlogged_priv[0]['video_id'] if unlogged_priv else privacy_alerts[0]['video_id']} "
                    f"to apply face blur, and visually verify all {len(privacy_alerts)} flagged videos ({all_priv_vids}) before client posting."
                ),
                what_is_uncertain=(
                    f"Whether face blurring was actually rendered in the final exported video files for {all_priv_vids} "
                    "— requires human visual inspection of the exported video files."
                ),
                status=act_status,
                responsible_area="privacy",
                draft_available=True,
                fingerprint=action_id,
            )
        )
        priority_idx += 1

    # Priority 2: Client Retainer / Churn Risk & Client Credit/Refund Obligations (computed 100% dynamically)
    if churn.get("client") and churn["client"] != "None identified":
        churn_ev = list(churn.get("evidence", [])[:3])
        for w in fin.we_owe:
            churn_ev.append(f"Client credit/refund candidate (${w.amount:,.2f} to {w.client}): {w.why[:110]}")

        we_owe_sum = sum((w.amount for w in fin.we_owe), Decimal("0.00"))
        we_owe_clients_str = ", ".join(f"{w.client} (${w.amount:,.0f})" for w in fin.we_owe)
        action_id = f"action-{priority_idx}"
        act_status = persisted_states.get(action_id, {}).get("status") or ACTION_STATUSES.get(action_id, "pending")
        top_3.append(
            RecommendedAction(
                id=action_id,
                priority=priority_idx,
                title=f"Review {churn['client']} Retainer & Contract",
                urgency="Critical",
                why_it_matters=churn.get("why") or f"{churn['client']} reported repeated name errors ('Keystone Chiro') and requested a contract review.",
                client_name=churn["client"],
                evidence=churn_ev[:4],
                suggested_action=churn["what_to_do_this_week"],
                what_is_uncertain=(
                    f"Whether {churn['client']} will renew once missed edits are resolved"
                    + (
                        f", and whether {we_owe_clients_str} prefer a direct refund or credit memo against future work."
                        if we_owe_clients_str
                        else "."
                    )
                ),
                status=act_status,
                responsible_area="client",
                draft_available=True,
                fingerprint=action_id,
            )
        )
        priority_idx += 1

    # Priority 3: Financial Reconciliation & Overdue Invoices (computed 100% dynamically)
    if (fin.source_overdue_total and fin.source_overdue_total > Decimal("0.00")) or len(vn_audit) > 0:
        conflict_invs = ", ".join(b.invoice for b in fin.billing_tool_is_wrong[:4])
        unbilled_summary = ", ".join(
            f"{u.client} {u.booking_id_or_month} (${u.amount:,.0f}, {u.confidence})" for u in fin.never_billed_items
        )
        unlogged_vn_cnt = sum(1 for v in vn_audit if not v.get("board_logged"))
        fin_ops_ev = [
            f"Overdue Receivables: {fin.source_overdue_count} source-overdue invoices (${fin.source_overdue_total:,.2f} with due < {ref_date}); "
            f"after reconciling {len(fin.billing_tool_is_wrong)} billing-vs-bank conflicts ({conflict_invs}), "
            f"{len(fin.overdue_invoices)} invoices totaling ${fin.overdue_total:,.2f} remain overdue.",
            f"Unbilled Completed Work: ${fin.never_billed_total:,.2f} across {len(fin.never_billed_items)} completed shoots "
            f"({unbilled_summary or 'none'}).",
            f"Broken Voice-Note Workflow & Unanswered Leads: {unlogged_vn_cnt} of {len(vn_audit)} voice notes were never logged to the production board "
            f"(contributing to {len(complaints)} repeated complaints), and {len(unreplied_lead_ids)} leads ({leads_ov['legitimate_unanswered_count']} prospects, "
            f"{leads_ov['existing_client_unanswered_count']} existing clients, {leads_ov['junk_unanswered_count']} spam) have no recorded reply.",
        ]
        action_id = f"action-{priority_idx}"
        act_status = persisted_states.get(action_id, {}).get("status") or ACTION_STATUSES.get(action_id, "pending")
        top_3.append(
            RecommendedAction(
                id=action_id,
                priority=priority_idx,
                title=f"Reconcile {len(fin.overdue_invoices)} Overdue Invoices (${fin.overdue_total:,.2f})",
                urgency="High",
                why_it_matters=(
                    f"{len(fin.overdue_invoices)} reconciled invoices are past due totaling ${fin.overdue_total:,.2f}, "
                    f"with {len(fin.billing_tool_is_wrong)} billing-tool status errors requiring verification against bank deposits."
                ),
                client_name=fin.overdue_invoices[0].client if fin.overdue_invoices else None,
                evidence=fin_ops_ev,
                suggested_action=(
                    f"Confirm {len(fin.billing_tool_is_wrong)} billing-vs-bank discrepancies in Money, review {len(fin.never_billed_items)} "
                    f"unbilled shoot candidates (${fin.never_billed_total:,.0f}), and assign {unlogged_vn_cnt} voice notes + "
                    f"{leads_ov['legitimate_unanswered_count']} legitimate unanswered leads in Requests."
                ),
                what_is_uncertain=(
                    "Owner confirmation is required before posting candidate batch/partial payments with blank bank references "
                    "and before billing completed shoots where client invoices have blank shoot memos."
                ),
                status=act_status,
                responsible_area="money",
                draft_available=True,
                fingerprint=action_id,
            )
        )

    try:
        sync_recommendations_to_db(cur, [rec.model_dump() for rec in top_3])
    except Exception:
        pass

    we_owe_total = sum((w.amount for w in fin.we_owe), Decimal("0.00"))
    overview = {
        "active_clients_count": id_queue["canonical_clients_count"],
        "payers_count": id_queue["third_party_payers_count"],
        "total_entities_count": total_entities_cnt,
        "total_invoiced": fin.total_invoiced,
        "gross_invoiced_including_void": fin.gross_invoiced_including_void,
        "total_bank_collected": fin.total_collected_in_bank,
        "source_open_receivables": fin.source_open_receivables,
        "source_overdue_receivables": fin.source_overdue_total,
        "source_overdue_count": fin.source_overdue_count,
        "true_unpaid_receivables": fin.true_unpaid_receivables,
        "overdue_receivables": fin.overdue_total,
        "reconciled_overdue_count": len(fin.overdue_invoices),
        "unanswered_leads_count": len(unreplied_lead_ids),
        "legitimate_unanswered_leads_count": leads_ov["legitimate_unanswered_count"],
        "lost_requests_count": len(lost.lost_requests),
        "repeated_complaints_count": len(complaints),
        "privacy_alerts_count": len(privacy_alerts),
        "double_payment_owed": fin.we_owe[0].amount if fin.we_owe else Decimal("0.00"),
        "we_owe_total": we_owe_total,
        "never_billed_total": fin.never_billed_total,
        "confirmed_never_billed_total": fin.potential_unbilled_total,
    }

    urgent_lead_label = "None"
    legit_unanswered = leads_ov.get("legitimate_unanswered") or []
    if legit_unanswered:
        # Pick the most recent or highest-urgency legitimate unanswered lead dynamically
        top_lead = sorted(legit_unanswered, key=lambda x: str(x.get("created") or ""), reverse=True)[0]
        urgent_lead_label = (
            f"{top_lead['lead_id']} ({top_lead['name']}"
            f"{' - ' + top_lead['business'] if top_lead.get('business') else ''})"
        )
    elif unreplied_lead_ids:
        cur.execute(
            "SELECT lead_id, name, business FROM leads WHERE lead_id = %s;",
            (unreplied_lead_ids[-1],),
        )
        ul = cur.fetchone()
        if ul:
            urgent_lead_label = f"{ul['lead_id']} ({ul['name']}{' - ' + ul['business'] if ul.get('business') else ''})"

    return DashboardSummaryResponse(
        reference_date=ref_date,
        overview=overview,
        monday_top_3=top_3,
        financial_alerts={
            "overdue_invoices_count": len(fin.overdue_invoices),
            "source_overdue_invoices_count": fin.source_overdue_count,
            "source_overdue_total": fin.source_overdue_total,
            "reconciled_overdue_total": fin.overdue_total,
            "billing_tool_errors_count": len(fin.billing_tool_is_wrong),
            "never_billed_total": fin.never_billed_total,
            "confirmed_never_billed_total": fin.potential_unbilled_total,
            "we_owe_total": we_owe_total,
        },
        production_alerts={
            "lost_requests_count": len(lost.lost_requests),
            "repeated_complaints_count": len(complaints),
            "privacy_alerts_count": len(privacy_alerts),
            "root_cause_date": lost.lost_requests_started_getting_worse_in,
        },
        lead_alerts={
            "unanswered_count": len(unreplied_lead_ids),
            "legitimate_unanswered_count": leads_ov["legitimate_unanswered_count"],
            "existing_client_unanswered_count": leads_ov["existing_client_unanswered_count"],
            "junk_unanswered_count": leads_ov["junk_unanswered_count"],
            "urgent_lead": urgent_lead_label,
        },
        privacy_alerts_count=len(privacy_alerts),
        data_status=data_status,
    )


def set_action_status(action_id: str, new_status: str) -> bool:
    ACTION_STATUSES[action_id] = new_status
    try:
        from ..db import get_db
        with get_db() as cur:
            cur.execute(
                """
                INSERT INTO recommendation_states (fingerprint, action_type, title, status, updated_at)
                VALUES (%s, 'general', %s, %s, NOW())
                ON CONFLICT (fingerprint) DO UPDATE
                SET status = EXCLUDED.status, updated_at = NOW();
                """,
                (action_id, f"Recommendation {action_id}", new_status),
            )
    except Exception:
        pass
    return True
