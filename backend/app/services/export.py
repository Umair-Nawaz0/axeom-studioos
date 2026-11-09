import json
from datetime import date
from typing import Any, Dict, List, Optional

from .clients import get_most_likely_to_leave
from .dashboard import get_dashboard_summary
from .finance import get_finance_reconciliation
from .leads import get_never_replied_leads
from .marketing import get_marketing_analysis
from .production import get_lost_requests


def generate_answers_json(
    cur,
    pack_id: str = "213",
    live_link: str = "",
    video_link: str = "",
    code_link: str = "",
    ref_date: Optional[date] = None,
) -> Dict[str, Any]:
    """
    100% dynamic answers.json generator adhering to the official Pack 213 template.
    Zero static imports from clients_meta.py or hardcoded client/invoice/video lists.
    """
    fin = get_finance_reconciliation(cur, ref_date=ref_date)
    lost = get_lost_requests(cur)
    never_replied = get_never_replied_leads(cur)
    churn = get_most_likely_to_leave(cur, ref_date=ref_date)
    mkt = get_marketing_analysis(cur)
    dash = get_dashboard_summary(cur, ref_date=ref_date)

    cur.execute("SELECT canonical_name, aliases, notes FROM clients ORDER BY canonical_name ASC;")
    db_clients = cur.fetchall()

    clients_list: List[Dict[str, Any]] = []
    payers_not_clients: List[Dict[str, Any]] = []

    for c in db_clients:
        meta: Dict[str, Any] = {}
        if (c.get("notes") or "").startswith("{"):
            try:
                meta = json.loads(c["notes"])
            except Exception:
                meta = {}
        etype = meta.get("entity_type", "client")
        if etype == "payer":
            payers_not_clients.append(
                {
                    "name": c["canonical_name"],
                    "pays_for": meta.get("pays_for") or [],
                }
            )
        else:
            aliases = c["aliases"] if isinstance(c["aliases"], list) else []
            emails = meta.get("emails") or [a for a in aliases if "@" in a]
            phones = meta.get("phones") or [a for a in aliases if any(ch.isdigit() for ch in a) and "@" not in a]
            clients_list.append(
                {
                    "name": c["canonical_name"],
                    "other_names_used_in_the_data": aliases,
                    "emails": emails,
                    "phones": phones,
                }
            )

    overdue_list = [
        {
            "client": item.client,
            "invoice": item.invoice,
            "amount_owed": float(item.amount_owed),
            "days_late": item.days_late,
        }
        for item in fin.overdue_invoices
    ]

    source_overdue_list = [
        {
            "client": item.client,
            "invoice": item.invoice,
            "amount_owed": float(item.amount_owed),
            "days_late": item.days_late,
            "source_status": item.source_status,
            "reconciliation_status": item.reconciliation_status,
        }
        for item in fin.source_overdue_invoices
    ]

    we_owe_list = [
        {
            "client": item.client,
            "amount": float(item.amount),
            "why": item.why,
        }
        for item in fin.we_owe
    ]

    never_billed_list = [
        {
            "client": item.client,
            "booking_id_or_month": item.booking_id_or_month,
            "amount": float(item.amount),
            "confidence": item.confidence,
        }
        for item in fin.never_billed_items
    ]

    billing_wrong_list = [
        {
            "invoice": item.invoice,
            "tool_says": item.tool_says,
            "truth": item.truth,
            "how_you_know": item.how_you_know,
        }
        for item in fin.billing_tool_is_wrong
    ]

    lost_req_list = [
        {
            "video_id": item.video_id,
            "request_date": item.request_date,
            "came_by": item.came_by,
            "why_it_was_lost": item.why_it_was_lost,
        }
        for item in lost.lost_requests
    ]

    top_3 = [
        f"{a.priority}. [{a.urgency}] {a.title}: {a.suggested_action} (Uncertain: {a.what_is_uncertain})"
        for a in dash.monday_top_3
    ]

    return {
        "pack_id": pack_id,
        "your_name": "Umair",
        "your_email": "umair@example.com",
        "live_link": live_link,
        "video_link": video_link,
        "code_or_files_link": code_link,
        "client_count": len(clients_list),
        "clients": clients_list,
        "payers_who_are_not_clients": payers_not_clients,
        "overdue": overdue_list,
        "overdue_total": float(fin.overdue_total),
        "source_overdue": source_overdue_list,
        "source_overdue_total": float(fin.source_overdue_total or 0),
        "we_owe": we_owe_list,
        "never_billed": never_billed_list,
        "never_billed_total": float(fin.never_billed_total),
        "confirmed_never_billed_total": float(fin.potential_unbilled_total or 0),
        "billing_tool_is_wrong": billing_wrong_list,
        "lost_requests": lost_req_list,
        "lost_requests_root_causes": lost.lost_requests_root_causes,
        "lost_requests_started_getting_worse_in": lost.lost_requests_started_getting_worse_in,
        "never_replied_leads": never_replied,
        "most_likely_to_leave": {
            "client": churn["client"],
            "evidence": churn["evidence"],
            "what_to_do_this_week": churn["what_to_do_this_week"],
        },
        "best_marketing_channel": {
            "channel": mkt["best_marketing_channel"]["channel"],
            "why": mkt["best_marketing_channel"]["why"],
        },
        "what_this_data_cannot_tell_us": mkt["what_this_data_cannot_tell_us"],
        "monday_top_3": top_3,
    }
