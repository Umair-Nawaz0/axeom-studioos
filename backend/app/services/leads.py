from collections import Counter
from typing import Any, Dict, List

from .messages_service import analyze_messages


def _classify_lead_quality(lead: Dict[str, Any]) -> str:
    name_low = (lead.get("name") or "").strip().lower()
    email_low = (lead.get("email") or "").strip().lower()
    if any(
        tok in name_low or tok in email_low
        for tok in ("test@test", "test test", "asdf", "a@a.co", "fastfollowers", "free followers", "seo services", "rank1seo")
    ):
        return "junk_or_spam"
    if lead.get("client_id") and (lead.get("status") or "").lower() != "won":
        return "existing_client_inquiry"
    return "legitimate_prospect"


def get_never_replied_leads(cur) -> List[str]:
    cur.execute(
        """
        SELECT lead_id 
        FROM leads 
        WHERE first_reply IS NULL AND LOWER(status) != 'won'
        ORDER BY lead_id ASC;
        """
    )
    rows = cur.fetchall()
    return [r["lead_id"] for r in rows]


def get_leads_overview(cur) -> Dict[str, Any]:
    cur.execute(
        """
        SELECT l.lead_id, l.client_id, l.created, l.name, l.business, l.email,
               l.phone, l.source, l.first_reply, l.status,
               c.canonical_name AS linked_client_name
        FROM leads l
        LEFT JOIN clients c ON l.client_id = c.id
        ORDER BY l.created DESC, l.lead_id ASC;
        """
    )
    all_leads = cur.fetchall()

    # Detect duplicate enquiries by normalized email or (name, business)
    email_counts = Counter(
        (l.get("email") or "").strip().lower()
        for l in all_leads
        if (l.get("email") or "").strip()
    )
    duplicate_lead_groups: Dict[str, List[str]] = {}
    for l in all_leads:
        em = (l.get("email") or "").strip().lower()
        if em and email_counts[em] > 1:
            duplicate_lead_groups.setdefault(em, []).append(l["lead_id"])

    statuses: Counter = Counter()
    all_leads_enriched: List[Dict[str, Any]] = []
    unanswered: List[Dict[str, Any]] = []
    junk_unanswered_count = 0
    existing_client_unanswered_count = 0
    legitimate_unanswered_count = 0

    for l in all_leads:
        st = l.get("status") or "Unknown"
        statuses[st] += 1
        q_type = _classify_lead_quality(l)
        em = (l.get("email") or "").strip().lower()
        dup_ids = [lid for lid in duplicate_lead_groups.get(em, []) if lid != l["lead_id"]]

        item = {
            "lead_id": l["lead_id"],
            "client_id": str(l["client_id"]) if l.get("client_id") else None,
            "linked_client_name": l.get("linked_client_name"),
            "created": l["created"].isoformat() if l.get("created") else None,
            "name": l.get("name") or "",
            "business": l.get("business") or "",
            "email": l.get("email") or "",
            "phone": l.get("phone") or "",
            "source": l.get("source") or "Unknown",
            "first_reply": str(l["first_reply"]) if l.get("first_reply") else None,
            "status": st,
            "triage_category": q_type,
            "is_duplicate": len(dup_ids) > 0,
            "duplicate_of": dup_ids,
        }
        all_leads_enriched.append(item)

        if l.get("first_reply") is None and st.lower() != "won":
            unanswered.append(item)
            if q_type == "junk_or_spam":
                junk_unanswered_count += 1
            elif q_type == "existing_client_inquiry":
                existing_client_unanswered_count += 1
            else:
                legitimate_unanswered_count += 1

    # Source breakdown with conversion rate
    cur.execute(
        """
        SELECT 
            source, 
            COUNT(*) AS total,
            COUNT(CASE WHEN LOWER(status) = 'won' THEN 1 END) AS won,
            COUNT(CASE WHEN first_reply IS NULL AND LOWER(status) != 'won' THEN 1 END) AS unanswered,
            ROUND(COUNT(CASE WHEN LOWER(status) = 'won' THEN 1 END)::NUMERIC / COUNT(*)::NUMERIC * 100, 1) AS conversion_rate
        FROM leads 
        GROUP BY source
        ORDER BY won DESC, total DESC;
        """
    )
    sources = [dict(r) for r in cur.fetchall()]

    msg_analysis = analyze_messages(cur)

    return {
        "total_leads_count": len(all_leads_enriched),
        "status_breakdown": dict(statuses),
        "channel_conversion": sources,
        "unanswered_leads_count": len(unanswered),
        "legitimate_unanswered_count": legitimate_unanswered_count,
        "existing_client_unanswered_count": existing_client_unanswered_count,
        "junk_unanswered_count": junk_unanswered_count,
        "duplicate_enquiries": [
            {"email": em, "lead_ids": sorted(lids)}
            for em, lids in duplicate_lead_groups.items()
        ],
        "unanswered_leads": unanswered,
        "all_leads": all_leads_enriched,
        "message_opportunities_and_referrals": msg_analysis["opportunities_and_referrals"],
    }
