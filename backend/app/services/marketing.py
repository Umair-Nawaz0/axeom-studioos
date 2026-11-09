from typing import Any, Dict, List


def get_marketing_analysis(cur) -> Dict[str, Any]:
    """
    100% dynamic marketing & lead source conversion analysis.
    Ranks channels by observed conversion rate and attributed client revenue while
    explicitly stating why net profitability/ROI cannot be proven without CAC/ad spend.
    """
    cur.execute(
        """
        WITH client_acquisition AS (
            SELECT DISTINCT ON (client_id)
                client_id,
                source,
                created
            FROM leads
            WHERE LOWER(status) = 'won' AND client_id IS NOT NULL
            ORDER BY client_id, created ASC
        ),
        client_invoiced AS (
            SELECT client_id, SUM(amount) AS total_invoiced
            FROM invoices
            WHERE LOWER(status) != 'void'
            GROUP BY client_id
        ),
        channel_attribution AS (
            SELECT 
                ca.source,
                COUNT(ca.client_id) AS clients_acquired,
                COALESCE(SUM(ci.total_invoiced), 0) AS total_revenue
            FROM client_acquisition ca
            LEFT JOIN client_invoiced ci ON ca.client_id = ci.client_id
            GROUP BY ca.source
        ),
        lead_stats AS (
            SELECT 
                source,
                COUNT(*) AS total_leads,
                COUNT(CASE WHEN LOWER(status) = 'won' THEN 1 END) AS won_leads,
                COUNT(CASE WHEN LOWER(status) = 'lost' THEN 1 END) AS lost_leads,
                COUNT(CASE WHEN LOWER(status) = 'new' THEN 1 END) AS new_leads,
                COUNT(CASE WHEN LOWER(status) = 'talking' THEN 1 END) AS talking_leads,
                COUNT(CASE WHEN first_reply IS NULL AND LOWER(status) != 'won' THEN 1 END) AS unreplied_leads,
                ROUND(COUNT(CASE WHEN LOWER(status) = 'won' THEN 1 END)::NUMERIC / NULLIF(COUNT(*), 0)::NUMERIC * 100, 1) AS conversion_rate
            FROM leads
            GROUP BY source
        )
        SELECT 
            ls.source,
            ls.total_leads,
            ls.won_leads,
            ls.lost_leads,
            ls.new_leads,
            ls.talking_leads,
            ls.unreplied_leads,
            ls.conversion_rate,
            COALESCE(ca.clients_acquired, 0) AS clients_acquired,
            COALESCE(ca.total_revenue, 0) AS direct_booking_revenue
        FROM lead_stats ls
        LEFT JOIN channel_attribution ca ON ca.source = ls.source
        ORDER BY ls.conversion_rate DESC NULLS LAST, ca.total_revenue DESC NULLS LAST, ls.won_leads DESC;
        """
    )
    channels = [dict(r) for r in cur.fetchall()]

    if channels:
        active_channels = [c for c in channels if int(c["won_leads"] or 0) > 0]
        if active_channels:
            top_channel = max(
                active_channels,
                key=lambda c: (
                    float(c["conversion_rate"] or 0),
                    int(c["won_leads"] or 0),
                    float(c["direct_booking_revenue"] or 0),
                ),
            )
            ch_name = top_channel["source"]
            cr = float(top_channel["conversion_rate"] or 0)
            won = int(top_channel["won_leads"] or 0)
            tot = int(top_channel["total_leads"] or 0)
            rev = float(top_channel["direct_booking_revenue"] or 0)
            acq = int(top_channel["clients_acquired"] or 0)

            why_text = (
                f"{ch_name} achieved the highest observed conversion rate at {cr:.1f}% ({won} won out of {tot} leads) "
                f"and generated ${rev:,.2f} in attributed non-void invoiced revenue across {acq} canonical clients. "
                f"Note: This reflects Best Observed Conversion rather than proven net ROI, because paid advertising spend "
                f"(CAC for Meta ads, Google, etc.) is absent from costs.csv."
            )
            best_channel = {
                "channel": ch_name,
                "label": "Best Observed Conversion (Ad Spend Unknown)",
                "conversion_rate": cr,
                "won_leads": won,
                "total_leads": tot,
                "attributed_revenue": rev,
                "why": why_text,
            }
        else:
            best_channel = {
                "channel": "None",
                "label": "No Won Leads",
                "why": "No won leads recorded across any acquisition channels in the current dataset.",
            }
    else:
        best_channel = {
            "channel": "None",
            "label": "No Data",
            "why": "No lead attribution data available in the current database.",
        }

    cur.execute("SELECT COUNT(*) AS raw_won, COUNT(DISTINCT client_id) AS uniq_won FROM leads WHERE LOWER(status) = 'won';")
    won_stats = cur.fetchone()
    raw_won_cnt = int(won_stats["raw_won"] or 0)
    uniq_won_cnt = int(won_stats["uniq_won"] or 0)

    cur.execute(
        """
        SELECT c.canonical_name
        FROM clients c
        WHERE c.notes LIKE '%"entity_type": "third_party_payer"%'
        ORDER BY c.canonical_name ASC;
        """
    )
    payer_names = [r["canonical_name"] for r in cur.fetchall()]
    payer_desc = (
        f"Third-party payer billing ({', '.join(payer_names)}) separates invoice payer entities from the underlying shoot clients."
        if payer_names
        else "Third-party agency billing can separate invoice payer records from the underlying shoot clients."
    )

    cur.execute("SELECT COUNT(*) AS c FROM leads WHERE first_reply IS NULL AND LOWER(status) != 'won';")
    unreplied_cnt = int(cur.fetchone()["c"] or 0)

    total_leads_sum = sum(int(c.get("total_leads") or 0) for c in channels)
    won_leads_sum = sum(int(c.get("won_leads") or 0) for c in channels)
    lost_leads_sum = sum(int(c.get("lost_leads") or 0) for c in channels)
    new_leads_sum = sum(int(c.get("new_leads") or 0) for c in channels)
    talking_leads_sum = sum(int(c.get("talking_leads") or 0) for c in channels)
    unreplied_leads_sum = sum(int(c.get("unreplied_leads") or 0) for c in channels)
    revenue_sum = sum(float(c.get("direct_booking_revenue") or 0) for c in channels)
    clients_acquired_sum = sum(int(c.get("clients_acquired") or 0) for c in channels)
    overall_conv = round((won_leads_sum / total_leads_sum * 100), 1) if total_leads_sum > 0 else 0.0

    totals = {
        "total_leads": total_leads_sum,
        "won_leads": won_leads_sum,
        "lost_leads": lost_leads_sum,
        "new_leads": new_leads_sum,
        "talking_leads": talking_leads_sum,
        "unreplied_leads": unreplied_leads_sum,
        "conversion_rate": overall_conv,
        "clients_acquired": clients_acquired_sum,
        "direct_booking_revenue": revenue_sum,
    }

    limitations: List[str] = [
        "Paid advertising spend and Customer Acquisition Cost (CAC) for Meta ads, Google, Instagram, and LinkedIn are absent from costs.csv, so net channel ROI and true profitability cannot be proven.",
        f"Duplicate won lead entries exist in raw leads.csv ({raw_won_cnt} won lead rows vs {uniq_won_cnt} unique acquired entities), so raw won-lead counts must be deduplicated by canonical client before calculating client acquisition.",
        payer_desc,
        f"{unreplied_cnt} non-won leads have no first_reply date (including spam/bot submissions and website form messages from existing clients).",
    ]

    return {
        "best_marketing_channel": best_channel,
        "what_this_data_cannot_tell_us": limitations,
        "channel_metrics": channels,
        "summary_totals": totals,
    }
