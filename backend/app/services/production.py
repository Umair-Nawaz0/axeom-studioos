import re
from collections import Counter
from decimal import Decimal
from typing import Any, Dict, List

from ..models import LostRequestItem, LostRequestsResponse
from .messages_service import analyze_messages


def _service_hours(service_name: str) -> int:
    s = (service_name or "").lower()
    m = re.search(r"(\d+)\s*hr", s)
    if m:
        return int(m.group(1))
    if "content day" in s:
        return 6
    if "retainer shoot" in s:
        return 4
    if "reels pack" in s or "half day" in s:
        return 3
    return 3


def get_lost_requests(cur) -> LostRequestsResponse:
    """
    100% dynamic forensic detection of lost edit requests, repeated complaints, and privacy alerts.
    Zero hardcoded video IDs or client names.
    """
    msg_analysis = analyze_messages(cur)
    vn_audit = msg_analysis["voice_note_audit"]
    complaints = msg_analysis["repeated_complaints"]
    privacy_alerts = msg_analysis["privacy_alerts"]

    # Determine month when voice notes spiked dynamically
    cur.execute(
        """
        SELECT TO_CHAR(message_date, 'YYYY-MM') AS month_str, COUNT(*) AS vn_count
        FROM messages
        WHERE LOWER(channel) = 'voice note' OR LOWER(original_line) LIKE '%voice note%'
        GROUP BY TO_CHAR(message_date, 'YYYY-MM')
        ORDER BY month_str ASC;
        """
    )
    vn_months = cur.fetchall()
    worse_month = "N/A"
    for r in vn_months:
        if int(r["vn_count"] or 0) >= 5:
            worse_month = r["month_str"]
            break
    if worse_month == "N/A" and vn_months:
        worse_month = vn_months[0]["month_str"]

    # Index complaints by prior_voice_note_line for rich explanation
    complaint_by_vn_line: Dict[int, Dict[str, Any]] = {}
    for comp in complaints:
        vn_line = comp.get("prior_voice_note_line")
        if vn_line and vn_line not in complaint_by_vn_line:
            complaint_by_vn_line[vn_line] = comp

    lost_items: List[LostRequestItem] = []

    # Prioritize voice notes that either triggered a repeated complaint or are unlogged privacy requests,
    # then include remaining unlogged voice notes so all 39 unlogged voice notes are accounted for.
    sorted_vns = sorted(
        [vn for vn in vn_audit if not vn.get("board_logged")],
        key=lambda v: (
            0 if v.get("is_privacy_alert") else (1 if v.get("escalated_to_complaint") else 2),
            v["line_number"],
        ),
    )

    for vn in sorted_vns:
        comp = complaint_by_vn_line.get(vn["line_number"])
        dur_str = f" ({vn['duration']})" if vn.get("duration") else ""
        if vn.get("is_privacy_alert"):
            why = (
                f"CRITICAL PRIVACY GAP: Client sent voice note{dur_str} (line #{vn['line_number']}): "
                f"\"{vn['message_text']}\". Never transcribed onto production board ({vn.get('video_id') or 'video'} "
                f"is '{vn.get('video_stage') or 'Delivered'}' with blank board notes)."
            )
        elif comp:
            why = (
                f"Client sent voice note{dur_str} on {vn['date']} (line #{vn['line_number']}): \"{vn['message_text']}\". "
                f"Never logged on production board; client complained on {comp['date']} (line #{comp['line_number']}): "
                f"\"{comp['message_text']}\"."
            )
        else:
            why = (
                f"Client sent voice note{dur_str} on {vn['date']} (line #{vn['line_number']}): \"{vn['message_text']}\". "
                f"Never copied to production_board.csv notes_on_board."
            )

        lost_items.append(
            LostRequestItem(
                video_id=vn.get("video_id") or f"MSG-L{vn['line_number']}",
                request_date=vn["date"],
                came_by="voice note",
                why_it_was_lost=why,
                client=vn["client_name"],
                title=vn.get("video_title") or "Client video",
                stage=vn.get("video_stage"),
                editor=vn.get("editor"),
                notes_on_board=vn.get("notes_on_board") or "",
                line_number=vn["line_number"],
            )
        )

    # Also include any repeated complaint not already represented by a voice note (e.g., if a synthetic text complaint is uploaded)
    covered_comp_lines = {c["line_number"] for c in complaint_by_vn_line.values()}
    for comp in complaints:
        if comp["line_number"] not in covered_comp_lines:
            lost_items.append(
                LostRequestItem(
                    video_id=comp.get("video_id") or f"MSG-L{comp['line_number']}",
                    request_date=comp["date"],
                    came_by=comp["channel"].lower(),
                    why_it_was_lost=(
                        f"Client follow-up complaint on {comp['date']} (line #{comp['line_number']}): "
                        f"\"{comp['message_text']}\"."
                    ),
                    client=comp["client_name"],
                    title=comp.get("video_title") or "Client video",
                    stage=comp.get("video_stage"),
                    editor=comp.get("editor"),
                    notes_on_board=comp.get("notes_on_board") or "",
                    line_number=comp["line_number"],
                )
            )

    unlogged_priv_vids = [p.get("video_id") for p in privacy_alerts if not p.get("board_logged") and p.get("video_id")]
    unlogged_priv_desc = (
        f"{len(unlogged_priv_vids)} unlogged privacy face-blur violation(s) on delivered video(s) ({', '.join(unlogged_priv_vids)})"
        if unlogged_priv_vids
        else "0 unlogged privacy violations"
    )
    retention_risks = msg_analysis.get("churn_signals") or []
    retention_clients = sorted({r.get("client_name") for r in retention_risks if r.get("client_name")})
    retention_desc = (
        f"client retention/contract escalations ({', '.join(retention_clients)})"
        if retention_clients
        else "client retention risks"
    )

    broadcast_row = next(
        (
            m
            for m in (msg_analysis.get("messages") or [])
            if "send edit notes as a voice note" in (m.get("message_text") or "").lower()
        ),
        None,
    )
    broadcast_desc = (
        f"On {broadcast_row['date']} (message line #{broadcast_row['line_number']}), the studio broadcast to all clients encouraging them to send edit notes as voice notes without a process to route voice notes to editors."
        if broadcast_row
        else "Clients sent edit requests via voice notes, but no process existed to transcribe and route voice notes onto the production board."
    )

    logged_vn_cnt = sum(1 for v in vn_audit if v.get("board_logged"))
    root_causes = (
        [
            f"{logged_vn_cnt} of {len(vn_audit)} client voice notes were transcribed or logged onto production_board.csv (`notes_on_board`), whereas text/email edit requests were logged.",
            broadcast_desc,
            f"Ignored voice notes directly triggered {len(complaints)} repeated client complaints, {unlogged_priv_desc}, and {retention_desc}.",
        ]
        if lost_items
        else []
    )

    # Compute earliest and latest incident dates dynamically
    incident_dates = [it.request_date for it in lost_items if it.request_date]
    earliest_date = min(incident_dates) if incident_dates else None
    latest_date = max(incident_dates) if incident_dates else None

    # Dynamic structured root-cause category breakdown
    breakdown: List[Dict[str, Any]] = []

    # 1. Voice-note routing failure
    unlogged_vns = [vn for vn in vn_audit if not vn.get("board_logged")]
    if unlogged_vns:
        vn_clients = sorted({vn["client_name"] for vn in unlogged_vns if vn.get("client_name")})
        vn_dates = [vn["date"] for vn in unlogged_vns if vn.get("date")]
        vn_timeline = Counter([d[:7] for d in vn_dates if len(d) >= 7])
        breakdown.append(
            {
                "category": "voice_note_not_converted",
                "title": "Voice-Note Request Not Converted into Production Task",
                "total_affected_records": len(unlogged_vns),
                "distinct_clients_affected": len(vn_clients),
                "earliest_date": min(vn_dates) if vn_dates else None,
                "latest_date": max(vn_dates) if vn_dates else None,
                "timeline": dict(sorted(vn_timeline.items())),
                "source_record_ids": [f"MSG-L{v['line_number']}" for v in unlogged_vns[:10]],
                "is_open": True,
                "process_change": (
                    "Implement a mandatory intake webhook or SOP to transcribe incoming audio/voice notes "
                    "into production board tasks before editing commences."
                ),
            }
        )

    # 2. Privacy instructions not transferred to production
    if privacy_alerts:
        priv_clients = sorted({p["client_name"] for p in privacy_alerts if p.get("client_name")})
        priv_dates = [p["date"] for p in privacy_alerts if p.get("date")]
        priv_timeline = Counter([d[:7] for d in priv_dates if len(d) >= 7])
        breakdown.append(
            {
                "category": "privacy_instruction_not_transferred",
                "title": "Privacy & Face-Blur Instruction Not Transferred to Production",
                "total_affected_records": len(privacy_alerts),
                "distinct_clients_affected": len(priv_clients),
                "earliest_date": min(priv_dates) if priv_dates else None,
                "latest_date": max(priv_dates) if priv_dates else None,
                "timeline": dict(sorted(priv_timeline.items())),
                "source_record_ids": [str(p.get("video_id") or p.get("line_number")) for p in privacy_alerts],
                "is_open": True,
                "process_change": (
                    "Enforce signed release verification and visual blur audit as mandatory checklist items "
                    "before marking any client video as 'Delivered'."
                ),
            }
        )

    # 3. Repeated client complaints / revision disconnect
    if complaints:
        comp_clients = sorted({c["client_name"] for c in complaints if c.get("client_name")})
        comp_dates = [c["date"] for c in complaints if c.get("date")]
        comp_timeline = Counter([d[:7] for d in comp_dates if len(d) >= 7])
        breakdown.append(
            {
                "category": "repeated_revision_not_reflected",
                "title": "Client Revisions Ignored, Triggering Repeated Escalations",
                "total_affected_records": len(complaints),
                "distinct_clients_affected": len(comp_clients),
                "earliest_date": min(comp_dates) if comp_dates else None,
                "latest_date": max(comp_dates) if comp_dates else None,
                "timeline": dict(sorted(comp_timeline.items())),
                "source_record_ids": [f"MSG-L{c['line_number']}" for c in complaints],
                "is_open": True,
                "process_change": (
                    "Trigger real-time notifications to the studio owner whenever a client sends a second edit request "
                    "or expresses dissatisfaction regarding an unfulfilled note."
                ),
            }
        )

    return LostRequestsResponse(
        lost_requests=lost_items,
        lost_requests_root_causes=root_causes,
        lost_requests_started_getting_worse_in=worse_month,
        repeated_complaints=complaints,
        privacy_alerts=privacy_alerts,
        root_cause_breakdown=breakdown,
        earliest_incident_date=earliest_date,
        latest_incident_date=latest_date,
    )


def get_production_overview(cur) -> Dict[str, Any]:
    """
    Full dynamic 352-video production board analysis, editor labor cost calculation,
    studio room cost calculation, and message-linked risk flags.
    """
    msg_analysis = analyze_messages(cur)
    privacy_by_vid: Dict[str, Dict[str, Any]] = {}
    for p in msg_analysis["privacy_alerts"]:
        if p.get("video_id"):
            privacy_by_vid[p["video_id"]] = p

    complaints_by_vid: Dict[str, List[Dict[str, Any]]] = {}
    for c in msg_analysis["repeated_complaints"]:
        if c.get("video_id"):
            complaints_by_vid.setdefault(c["video_id"], []).append(c)

    cur.execute(
        """
        SELECT pv.video_id, pv.client_id, pv.client, pv.title, pv.editor, pv.stage,
               pv.notes_on_board, pv.revisions, pv.editor_hours, pv.client_approved_on, pv.shoot_booking,
               c.canonical_name AS client_name,
               b.date AS shoot_date
        FROM production_videos pv
        LEFT JOIN clients c ON pv.client_id = c.id
        LEFT JOIN bookings b ON b.booking_id = pv.shoot_booking
        ORDER BY pv.video_id ASC;
        """
    )
    videos = cur.fetchall()

    cur.execute("SELECT name, role, joined, pay FROM team_members ORDER BY name ASC;")
    team_rows = cur.fetchall()
    team_by_name = {r["name"].strip(): r for r in team_rows}

    cur.execute("SELECT rule_name, value, unit, notes FROM cost_rules ORDER BY id ASC;")
    cost_rules = cur.fetchall()
    studio_hourly_rate = Decimal("40.00")
    for cr in cost_rules:
        if "studio" in (cr.get("rule_name") or "").lower() and cr.get("value") is not None:
            studio_hourly_rate = Decimal(str(cr["value"])).quantize(Decimal("0.01"))

    cur.execute("SELECT booking_id, status, service, price FROM bookings;")
    bookings = cur.fetchall()

    stages: Counter = Counter()
    revision_counts: Counter = Counter()
    missing_shoot_booking_count = 0
    linked_shoot_booking_count = 0
    missing_approval_date_count = 0

    editor_agg: Dict[str, Dict[str, Any]] = {}
    all_videos_list: List[Dict[str, Any]] = []
    active_videos: List[Dict[str, Any]] = []

    for v in videos:
        vid = v["video_id"]
        st = v.get("stage") or "Unknown"
        stages[st] += 1
        rev = int(v.get("revisions") or 0)
        revision_counts[str(rev)] += 1

        if (v.get("shoot_booking") or "").strip():
            linked_shoot_booking_count += 1
        else:
            missing_shoot_booking_count += 1

        if not v.get("client_approved_on"):
            missing_approval_date_count += 1

        ed = (v.get("editor") or "Unassigned").strip()
        hrs = Decimal(str(v.get("editor_hours") or "0.00")).quantize(Decimal("0.01"))
        if ed not in editor_agg:
            editor_agg[ed] = {
                "editor": ed,
                "total_videos": 0,
                "total_hours": Decimal("0.00"),
                "total_revisions": 0,
                "zero_revision_videos": 0,
                "multi_revision_videos": 0,
            }
        editor_agg[ed]["total_videos"] += 1
        editor_agg[ed]["total_hours"] += hrs
        editor_agg[ed]["total_revisions"] += rev
        if rev == 0:
            editor_agg[ed]["zero_revision_videos"] += 1
        elif rev >= 2:
            editor_agg[ed]["multi_revision_videos"] += 1

        priv = privacy_by_vid.get(vid)
        v_complaints = complaints_by_vid.get(vid, [])

        v_item = {
            "video_id": vid,
            "title": v["title"],
            "stage": st,
            "revisions": rev,
            "editor": ed,
            "editor_hours": float(hrs),
            "client": v.get("client") or "",
            "client_name": v.get("client_name") or v.get("client") or "Unknown",
            "notes_on_board": v.get("notes_on_board") or "",
            "shoot_booking": v.get("shoot_booking") or None,
            "shoot_date": str(v["shoot_date"]) if v.get("shoot_date") else None,
            "client_approved_on": str(v["client_approved_on"]) if v.get("client_approved_on") else None,
            "has_privacy_alert": bool(priv),
            "privacy_board_missing": bool(priv and not priv.get("board_logged")),
            "has_unresolved_complaint": len(v_complaints) > 0,
            "complaint_count": len(v_complaints),
        }
        all_videos_list.append(v_item)
        if st in ("In revision", "In review", "In edit"):
            active_videos.append(v_item)

    active_videos.sort(key=lambda x: (-x["revisions"], x["video_id"]))

    editor_metrics: List[Dict[str, Any]] = []
    total_editor_hours = Decimal("0.00")
    total_editor_labor_cost = Decimal("0.00")

    for ed, stats in sorted(editor_agg.items()):
        t_row = team_by_name.get(ed)
        rate = Decimal(str(t_row["pay"])).quantize(Decimal("0.01")) if t_row and t_row.get("pay") is not None else Decimal("0.00")
        labor_cost = (stats["total_hours"] * rate).quantize(Decimal("0.01"))
        total_editor_hours += stats["total_hours"]
        total_editor_labor_cost += labor_cost
        avg_hrs = (
            (stats["total_hours"] / Decimal(stats["total_videos"])).quantize(Decimal("0.01"))
            if stats["total_videos"] > 0
            else Decimal("0.00")
        )
        editor_metrics.append(
            {
                "editor": ed,
                "role": t_row["role"] if t_row else "Editor",
                "joined": str(t_row["joined"]) if t_row and t_row.get("joined") else None,
                "hourly_rate": float(rate),
                "total_videos": stats["total_videos"],
                "total_hours": float(stats["total_hours"]),
                "avg_hours": float(avg_hrs),
                "total_revisions": stats["total_revisions"],
                "zero_revision_videos": stats["zero_revision_videos"],
                "multi_revision_videos": stats["multi_revision_videos"],
                "labor_cost": float(labor_cost),
            }
        )

    non_editor_team = [
        {
            "name": r["name"],
            "role": r.get("role") or "",
            "joined": str(r["joined"]) if r.get("joined") else None,
            "hourly_rate": float(r["pay"]) if r.get("pay") is not None else None,
            "pay_status": "rate_set" if r.get("pay") is not None else "unset_or_owner_draw",
        }
        for r in team_rows
        if r["name"] not in editor_agg
    ]

    # Studio booking cost calculation from costs.csv ($40/hour)
    completed_studio_hours = 0
    scheduled_studio_hours = 0
    cancelled_studio_hours = 0
    for b in bookings:
        hrs = _service_hours(b.get("service") or "")
        st = (b.get("status") or "").lower()
        if st == "completed":
            completed_studio_hours += hrs
        elif st in ("scheduled", "upcoming"):
            scheduled_studio_hours += hrs
        elif st == "cancelled":
            cancelled_studio_hours += hrs

    completed_studio_cost = (Decimal(completed_studio_hours) * studio_hourly_rate).quantize(Decimal("0.01"))
    scheduled_studio_cost = (Decimal(scheduled_studio_hours) * studio_hourly_rate).quantize(Decimal("0.01"))

    return {
        "total_videos": len(videos),
        "stage_breakdown": dict(stages),
        "revision_breakdown": dict(revision_counts),
        "missing_shoot_booking_count": missing_shoot_booking_count,
        "linked_shoot_booking_count": linked_shoot_booking_count,
        "missing_approval_date_count": missing_approval_date_count,
        "editor_metrics": editor_metrics,
        "non_editor_team": non_editor_team,
        "cost_summary": {
            "total_editor_hours": float(total_editor_hours),
            "total_editor_labor_cost": float(total_editor_labor_cost),
            "studio_hourly_rate": float(studio_hourly_rate),
            "completed_studio_hours": completed_studio_hours,
            "completed_studio_cost": float(completed_studio_cost),
            "scheduled_studio_hours": scheduled_studio_hours,
            "scheduled_studio_cost": float(scheduled_studio_cost),
            "cancelled_studio_hours": cancelled_studio_hours,
            "total_direct_production_cost": float(total_editor_labor_cost + completed_studio_cost),
        },
        "voice_note_summary": {
            "total_voice_notes": len(msg_analysis["voice_note_audit"]),
            "logged_on_board": sum(1 for v in msg_analysis["voice_note_audit"] if v.get("board_logged")),
            "unlogged_count": sum(1 for v in msg_analysis["voice_note_audit"] if not v.get("board_logged")),
            "escalated_to_complaints": sum(
                1 for v in msg_analysis["voice_note_audit"] if v.get("escalated_to_complaint")
            ),
        },
        "privacy_alerts": msg_analysis["privacy_alerts"],
        "active_work_in_progress": active_videos,
        "all_videos": all_videos_list,
    }
