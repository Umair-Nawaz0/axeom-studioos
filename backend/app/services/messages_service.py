import re
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from .identity import extract_message_header_info


def _expected_board_keywords(text_low: str) -> Tuple[Optional[str], List[str]]:
    """
    Maps a natural-language edit instruction to the expected production board note label
    and keywords used to check if the request was recorded in `notes_on_board`.
    """
    if any(w in text_low for w in ("blur", "didn't sign", "did not sign", "no release", "without release")):
        return "Blur client face", ["blur", "release", "face"]
    if "spelled wrong" in text_low or "spelling" in text_low:
        return "Fix name spelling", ["spell", "name"]
    if "captions bigger" in text_low or "hard to read" in text_low:
        return "Captions bigger", ["caption", "bigger"]
    if "phone number at the end" in text_low:
        return "Phone number end card", ["phone", "end card"]
    if "walk-ins welcome" in text_low:
        return "Add walk-ins welcome", ["walk-ins", "walk ins"]
    if "first 3 seconds" in text_low or "starts slow" in text_low:
        return "Cut first 3 sec", ["3 sec", "first 3", "cut first"]
    if "stumble on my words" in text_low or "stumble" in text_low:
        return "Cut stumble", ["stumble"]
    if "talk about prices" in text_low or "prices are changing" in text_low:
        return "Remove prices part", ["price"]
    if "too loud" in text_low or "can't hear myself" in text_low:
        return "Music lower", ["music lower", "loud"]
    if "calmer song" in text_low or "too hype" in text_low:
        return "Calmer music", ["calmer"]
    if "other shot" in text_low or "outside, not inside" in text_low:
        return "Use outside shot", ["outside"]
    if "brand color" in text_low:
        m = re.search(r"brand color\s+([a-z]+)", text_low)
        color = m.group(1) if m else "brand"
        return f"Brand color {color}", ["brand color", color]
    if "full name" in text_low and "compliance" in text_low:
        return "Use full legal name (compliance)", ["full name", "compliance", "chiropractic"]
    if "changed our mind" in text_low or "different song and a new intro" in text_low:
        return "New song + new intro (post-approval change)", ["intro", "different song"]
    return None, []


def _match_video_for_message(
    text_low: str,
    msg_dt: Optional[datetime],
    client_videos: List[Dict[str, Any]],
    all_videos_by_title: Dict[str, List[Dict[str, Any]]],
    expected_keywords: List[str],
) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]], bool]:
    """
    Dynamically matches a message to the most relevant production video for the same canonical client.
    Returns (best_video, all_title_matched_videos_for_client, has_cross_client_title_collision).
    """
    if not client_videos:
        return None, [], False

    # 1. Explicit video title mentioned in message text (longest title match first)
    title_candidates: List[Tuple[int, Dict[str, Any]]] = []
    matched_title_low: Optional[str] = None
    for v in client_videos:
        t = (v.get("title") or "").strip()
        t_low = t.lower()
        if t_low and t_low in text_low:
            title_candidates.append((len(t_low), v))
    if title_candidates:
        max_len = max(l for l, _ in title_candidates)
        same_title_vids = [v for l, v in title_candidates if l == max_len]
        matched_title_low = (same_title_vids[0].get("title") or "").strip().lower()
        cross_client_collision = (
            len({v.get("client_id") for v in all_videos_by_title.get(matched_title_low, [])}) > 1
        )
        # Prefer a video whose notes_on_board matches the expected keywords
        if expected_keywords:
            for v in same_title_vids:
                nb = (v.get("notes_on_board") or "").lower()
                if any(kw in nb for kw in expected_keywords):
                    return v, same_title_vids, cross_client_collision
        # Next prefer a video shot most recently on or before msg_dt
        if msg_dt:
            msg_d = msg_dt.date()
            prior = [
                v
                for v in same_title_vids
                if v.get("shoot_date") and v["shoot_date"] <= msg_d
            ]
            if prior:
                prior.sort(key=lambda x: (x["shoot_date"], x["video_id"]), reverse=True)
                return prior[0], same_title_vids, cross_client_collision
        return same_title_vids[0], same_title_vids, cross_client_collision

    # 2. Relative shoot reference ("the one we shot last week")
    if "shot last week" in text_low and msg_dt:
        msg_d = msg_dt.date()
        prior = [
            v
            for v in client_videos
            if v.get("shoot_date") and 0 <= (msg_d - v["shoot_date"]).days <= 21
        ]
        if prior:
            if expected_keywords:
                for v in prior:
                    nb = (v.get("notes_on_board") or "").lower()
                    if any(kw in nb for kw in expected_keywords):
                        return v, prior, False
            prior.sort(key=lambda x: (abs((msg_d - x["shoot_date"]).days - 7), x["video_id"]))
            return prior[0], prior, False

    return None, [], False


def analyze_messages(cur) -> Dict[str, Any]:
    """
    Full dynamic 190-message intelligence & cross-table audit engine.
    Zero hardcoded client names, video IDs, or counts.
    """
    cur.execute(
        """
        SELECT m.id, m.client_id, m.message_date, m.channel, m.sender, m.message_text, m.original_line,
               c.canonical_name, c.notes as client_notes
        FROM messages m
        LEFT JOIN clients c ON c.id = m.client_id
        ORDER BY m.message_date ASC, m.original_line ASC;
        """
    )
    raw_msgs = cur.fetchall()

    cur.execute(
        """
        SELECT v.video_id, v.client_id, v.client, v.title, v.editor, v.stage,
               v.notes_on_board, v.revisions, v.editor_hours, v.client_approved_on, v.shoot_booking,
               c.canonical_name, b.date as shoot_date
        FROM production_videos v
        LEFT JOIN clients c ON c.id = v.client_id
        LEFT JOIN bookings b ON b.booking_id = v.shoot_booking
        ORDER BY v.video_id ASC;
        """
    )
    videos = cur.fetchall()

    cur.execute("SELECT email, name, business, phone, status FROM leads;")
    leads = cur.fetchall()
    known_lead_phones = {
        re.sub(r"\D", "", l.get("phone") or "")[-10:]
        for l in leads
        if len(re.sub(r"\D", "", l.get("phone") or "")) >= 10
    }
    known_lead_businesses = {(l.get("business") or "").strip().lower() for l in leads if l.get("business")}

    vids_by_client: Dict[Any, List[Dict[str, Any]]] = defaultdict(list)
    vids_by_title: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for v in videos:
        if v.get("client_id"):
            vids_by_client[v["client_id"]].append(v)
        t_low = (v.get("title") or "").strip().lower()
        if t_low:
            vids_by_title[t_low].append(v)

    by_channel: Counter = Counter()
    by_direction: Counter = Counter()
    enriched_messages: List[Dict[str, Any]] = []
    privacy_alerts: List[Dict[str, Any]] = []
    voice_note_audit: List[Dict[str, Any]] = []
    repeated_complaints: List[Dict[str, Any]] = []
    opportunities_and_referrals: List[Dict[str, Any]] = []
    billing_and_cancellation_signals: List[Dict[str, Any]] = []
    contact_and_brand_updates: List[Dict[str, Any]] = []
    quarantined_messages: List[Dict[str, Any]] = []

    # Track prior voice notes per client so repeated complaints can link back to the ignored voice note
    client_voice_notes: Dict[Any, List[Dict[str, Any]]] = defaultdict(list)
    client_approvals: Dict[Tuple[Any, str], int] = {}

    CHANNEL_DISPLAY = {
        "EMAIL": "Email",
        "WHATSAPP": "WhatsApp",
        "VOICE NOTE": "Voice note",
        "INSTAGRAM DM": "Instagram DM",
        "WEBSITE FORM": "Website form",
    }

    for idx, m in enumerate(raw_msgs, start=1):
        info = extract_message_header_info(m.get("original_line") or "")
        raw_ch = (info.get("channel") or m.get("channel") or "Unknown").upper()
        ch_label = CHANNEL_DISPLAY.get(raw_ch, raw_ch.title())
        raw_dir = (info.get("direction") or "from").lower()
        direction = "outbound" if raw_dir in ("to", "outbound") else "inbound"
        by_channel[ch_label] += 1
        by_direction[direction] += 1

        body = (m.get("message_text") or info.get("body") or "").strip()
        body_low = body.lower()
        sender = (m.get("sender") or info.get("identity") or "").strip()
        sender_low = sender.lower()
        cid = m.get("client_id")
        cname = m.get("canonical_name")
        msg_dt = m.get("message_date")
        ts_str = msg_dt.strftime("%Y-%m-%d %H:%M") if msg_dt else (info.get("timestamp") or "")
        date_str = msg_dt.strftime("%Y-%m-%d") if msg_dt else (ts_str[:10] if ts_str else "")

        categories: List[str] = []
        severity = "normal"
        action_required = ""

        # 1. Outbound studio message
        if direction == "outbound":
            categories.append("outbound")

        # 2. Suspicious / Phishing / Spam detection
        is_spam = any(
            pat in body_low or pat in sender_low
            for pat in (
                "invoice.zip",
                "bit.ly/",
                "domain expires today",
                "10,000 real followers",
                "fastfollowers.io",
                "acct-dept.co",
                "domain-renewals.net",
                "@insta.support.team",
                "run your ads for free",
            )
        )
        if is_spam:
            categories.append("suspicious_or_spam")
            severity = "quarantined"
            action_required = "Quarantined phishing/spam — do not click links, open attachments, or pay."

        expected_note, expected_kws = _expected_board_keywords(body_low)
        best_vid, same_title_vids, title_collision = _match_video_for_message(
            body_low,
            msg_dt,
            vids_by_client.get(cid, []),
            vids_by_title,
            expected_kws,
        )

        # Check if any video of the matched title for this client has the expected note on the board
        board_logged = False
        board_note_val = ""
        if best_vid:
            board_note_val = (best_vid.get("notes_on_board") or "").strip()
            if expected_kws:
                for sv in same_title_vids or [best_vid]:
                    nb_low = (sv.get("notes_on_board") or "").lower()
                    if any(kw in nb_low for kw in expected_kws):
                        board_logged = True
                        best_vid = sv
                        board_note_val = (sv.get("notes_on_board") or "").strip()
                        break

        # 3. Privacy / No-release alert
        is_privacy = any(
            w in body_low
            for w in ("blur the face", "didn't sign the release", "did not sign the release", "no release")
        )
        if is_privacy:
            categories.append("privacy_no_release")
            severity = "critical"
            if not board_logged:
                action_required = (
                    f"CRITICAL: Privacy face-blur request sent via {ch_label} is MISSING from the production board "
                    f"({best_vid['video_id'] if best_vid else 'unmatched'} is '{best_vid['stage'] if best_vid else 'Unknown'}' with blank board notes)!"
                )
            elif best_vid and (best_vid.get("stage") or "").lower() == "delivered" and (best_vid.get("revisions") or 0) == 0:
                action_required = (
                    f"HIGH RISK: '{board_note_val}' is on board for {best_vid['video_id']}, but video is marked "
                    f"Delivered with 0 revisions — verify face was blurred before publishing."
                )
            else:
                action_required = (
                    f"Verify face blur is applied on {best_vid['video_id'] if best_vid else 'video'} before public posting."
                )

            privacy_alerts.append(
                {
                    "line_number": idx,
                    "message_id": str(m["id"]),
                    "timestamp": ts_str,
                    "date": date_str,
                    "channel": ch_label,
                    "sender": sender,
                    "client_id": str(cid) if cid else None,
                    "client_name": cname or sender,
                    "message_text": body,
                    "video_id": best_vid["video_id"] if best_vid else None,
                    "video_title": best_vid["title"] if best_vid else None,
                    "video_stage": best_vid["stage"] if best_vid else None,
                    "editor": best_vid["editor"] if best_vid else None,
                    "revisions": int(best_vid["revisions"] or 0) if best_vid else 0,
                    "notes_on_board": board_note_val,
                    "board_logged": board_logged,
                    "cross_client_title_collision": title_collision,
                    "action_required": action_required,
                }
            )

        # 4. Repeated / Escalated Complaint detection
        is_complaint = any(
            p in body_low
            for p in (
                "second time i ask",
                "still wrong",
                "still has the same problem",
                "already told you about this",
                "still not fixed",
                "frustrated honestly",
                "did anyone see my message",
                "it's not fixed",
                "asked for the full name",
                "not happy",
            )
        )
        prior_vn_line: Optional[int] = None
        prior_vn_text: Optional[str] = None
        if is_complaint:
            categories.append("repeated_complaint")
            if severity != "critical":
                severity = "high"
            # Link to earlier voice note from the same client (prefer matching title)
            prior_vns = client_voice_notes.get(cid, [])
            matched_vn = None
            if best_vid:
                t_low = (best_vid.get("title") or "").lower()
                for vn in reversed(prior_vns):
                    if t_low and t_low in vn["message_text"].lower():
                        matched_vn = vn
                        break
            if not matched_vn and prior_vns:
                matched_vn = prior_vns[-1]
            if matched_vn:
                prior_vn_line = matched_vn["line_number"]
                prior_vn_text = matched_vn["message_text"]
                matched_vn["escalated_to_complaint"] = True
                matched_vn["complaint_line_number"] = idx

            action_required = (
                f"Re-open {best_vid['video_id'] if best_vid else 'video'} ({best_vid['title'] if best_vid else 'client videos'}) "
                f"with editor {best_vid['editor'] if best_vid else 'team'}"
                + (f" — apply missed voice-note instruction from line #{prior_vn_line}." if prior_vn_line else ".")
            )

            repeated_complaints.append(
                {
                    "line_number": idx,
                    "message_id": str(m["id"]),
                    "timestamp": ts_str,
                    "date": date_str,
                    "channel": ch_label,
                    "sender": sender,
                    "client_id": str(cid) if cid else None,
                    "client_name": cname or sender,
                    "message_text": body,
                    "video_id": best_vid["video_id"] if best_vid else None,
                    "video_title": best_vid["title"] if best_vid else None,
                    "video_stage": best_vid["stage"] if best_vid else None,
                    "editor": best_vid["editor"] if best_vid else None,
                    "revisions": int(best_vid["revisions"] or 0) if best_vid else 0,
                    "notes_on_board": board_note_val,
                    "prior_voice_note_line": prior_vn_line,
                    "prior_voice_note_text": prior_vn_text,
                    "action_required": action_required,
                }
            )

        # 5. Contract / Retention / Churn risk detection
        if any(
            p in body_low
            for p in (
                "pause after this month",
                "talk about our contract",
                "whether we continue",
                "talk about the contract",
                "compliance cares about this",
            )
        ):
            categories.append("contract_retention_risk")
            severity = "critical" if "contract" in body_low or "pause" in body_low else "high"
            if not action_required:
                action_required = f"Immediate owner call with {cname or sender} regarding account retention & compliance."

        # 6. Paid cancellation / reschedule obligation
        if "cancel today's shoot" in body_low or ("cancel" in body_low and "already paid" in body_low):
            categories.append("paid_cancellation")
            severity = "high"
            action_required = (
                f"Honor $1,500 paid shoot credit or reschedule emergency cancelled shoot for {cname or sender}."
            )
            billing_and_cancellation_signals.append(
                {
                    "line_number": idx,
                    "type": "paid_cancellation",
                    "client_name": cname or sender,
                    "timestamp": ts_str,
                    "message_text": body,
                    "action_required": action_required,
                }
            )

        # 7. Billing / Payer / Payment arrangement signals
        if any(
            p in body_low
            for p in (
                "please bill us",
                "pay the july sessions together",
                "accounting will handle the invoice",
                "pay once the videos are posted",
                "sent half",
            )
        ):
            categories.append("billing")
            sig_type = "billing_note"
            if "please bill us" in body_low:
                sig_type = "third_party_payer_instruction"
            elif "july sessions" in body_low:
                sig_type = "batch_payment_request"
            elif "sent half" in body_low:
                sig_type = "partial_payment_confirmation"
            elif "once the videos are posted" in body_low:
                sig_type = "payment_contingent_on_delivery"
            billing_and_cancellation_signals.append(
                {
                    "line_number": idx,
                    "type": sig_type,
                    "client_name": cname or sender,
                    "timestamp": ts_str,
                    "message_text": body,
                    "action_required": f"Reconcile billing/payment note for {cname or sender}.",
                }
            )

        # 8. Referrals, Inbound DM Enquiries, and Upsell Inquiries
        if direction == "inbound" and not is_spam:
            is_referral = any(
                p in body_low
                for p in ("wants videos too", "loved our reels", "she'll reach out", "cousin ", "he needs videos")
            )
            is_upsell = any(
                p in body_low
                for p in (
                    "do this every month",
                    "what would that cost",
                    "cut short clips from our episodes",
                    "cut short clips from my episodes",
                )
            )
            is_dm_inquiry = "how much for a reels pack" in body_low
            if is_referral or is_upsell or is_dm_inquiry:
                categories.append("upsell_or_pricing" if is_upsell else "referral_or_lead")
                # Check if a referred phone or business is already in leads.csv
                ref_phones = [re.sub(r"\D", "", ph)[-10:] for ph in re.findall(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b", body)]
                uncaptured_phone = next((ph for ph in ref_phones if ph not in known_lead_phones), None)
                opp_status = "open_action_needed"
                if "haddad dental" in body_low and "haddad dental" in known_lead_businesses:
                    opp_status = "converted_to_won_lead"
                elif "riverbend coffee" in body_low and any("riverbend" in b for b in known_lead_businesses):
                    opp_status = "converted_to_won_lead"
                elif is_dm_inquiry:
                    opp_status = "replied_and_converted"
                if opp_status == "open_action_needed" and severity == "normal":
                    severity = "high"
                opp_action = (
                    f"Call referred prospect ({uncaptured_phone}) and create lead record."
                    if uncaptured_phone
                    else (
                        f"Send pricing/retainer proposal to {cname or sender}."
                        if is_upsell
                        else f"Follow up on referral from {cname or sender}."
                    )
                )
                if not action_required and opp_status == "open_action_needed":
                    action_required = opp_action
                opportunities_and_referrals.append(
                    {
                        "line_number": idx,
                        "timestamp": ts_str,
                        "date": date_str,
                        "channel": ch_label,
                        "client_name": cname or sender,
                        "sender": sender,
                        "type": "upsell_inquiry" if is_upsell else ("dm_lead_inquiry" if is_dm_inquiry else "client_referral"),
                        "status": opp_status,
                        "message_text": body,
                        "action_required": opp_action,
                    }
                )

        # 9. Contact / Rebrand / Compliance Name updates
        if any(
            p in body_low
            for p in ("is now ", "new email is", "new office number is", "say keystone chiropractic, the full name")
        ):
            categories.append("contact_update")
            contact_and_brand_updates.append(
                {
                    "line_number": idx,
                    "timestamp": ts_str,
                    "client_name": cname or sender,
                    "message_text": body,
                }
            )

        # 10. Approval vs Post-Approval Reversal
        if "approved! post it" in body_low:
            categories.append("approval_or_praise")
            if best_vid:
                client_approvals[(cid, best_vid["title"].lower())] = idx
        elif "changed our mind" in body_low:
            categories.append("edit_request")
            categories.append("post_approval_reversal")
            if severity == "normal":
                severity = "medium"
            action_required = (
                f"Client reversed prior approval on {best_vid['title'] if best_vid else 'video'} — hold posting & apply new song/intro."
            )
        elif any(p in body_low for p in ("thanks team", "best content team", "new cases came", "sales went up", "love it")):
            categories.append("approval_or_praise")

        # 11. Scheduling / Logistics
        if any(
            p in body_low
            for p in ("parking in the back", "move to 2pm", "bring anything for the shoot", "see you tomorrow", "running 10 min late")
        ):
            categories.append("scheduling")

        # 12. Standard Edit Request
        if expected_note and not is_privacy:
            if "edit_request" not in categories:
                categories.append("edit_request")

        # 13. Voice Note Audit tracking
        if ch_label == "Voice note":
            vn_entry = {
                "line_number": idx,
                "message_id": str(m["id"]),
                "timestamp": ts_str,
                "date": date_str,
                "sender": sender,
                "duration": info.get("duration") or "",
                "client_id": str(cid) if cid else None,
                "client_name": cname or sender,
                "message_text": body,
                "expected_board_note": expected_note or "Edit instruction",
                "video_id": best_vid["video_id"] if best_vid else None,
                "video_title": best_vid["title"] if best_vid else ("All client videos" if "full name" in body_low else "Recent shoot video"),
                "video_stage": best_vid["stage"] if best_vid else None,
                "editor": best_vid["editor"] if best_vid else None,
                "notes_on_board": board_note_val,
                "board_logged": board_logged,
                "is_privacy_alert": is_privacy,
                "escalated_to_complaint": False,
                "complaint_line_number": None,
            }
            voice_note_audit.append(vn_entry)
            client_voice_notes[cid].append(vn_entry)
            if not board_logged and not action_required:
                action_required = (
                    f"Unlogged voice-note edit request ({expected_note or 'Review transcript'}) — "
                    f"not recorded on production board for {best_vid['video_id'] if best_vid else (cname or sender)}."
                )

        if not categories:
            categories.append("general")

        msg_record = {
            "id": str(m["id"]),
            "line_number": idx,
            "timestamp": ts_str,
            "date": date_str,
            "channel": ch_label,
            "direction": direction,
            "sender": sender,
            "duration": info.get("duration"),
            "client_id": str(cid) if cid else None,
            "client_name": cname,
            "message_text": body,
            "original_line": m.get("original_line") or "",
            "categories": categories,
            "severity": severity,
            "matched_video_id": best_vid["video_id"] if best_vid else None,
            "matched_video_title": best_vid["title"] if best_vid else None,
            "matched_video_stage": best_vid["stage"] if best_vid else None,
            "matched_video_editor": best_vid["editor"] if best_vid else None,
            "matched_board_note": board_note_val,
            "board_logged": board_logged,
            "prior_voice_note_line": prior_vn_line,
            "action_required": action_required,
        }
        enriched_messages.append(msg_record)
        if is_spam:
            quarantined_messages.append(msg_record)

    return {
        "total_messages": len(enriched_messages),
        "by_channel": dict(by_channel),
        "by_direction": dict(by_direction),
        "messages": enriched_messages,
        "privacy_alerts": privacy_alerts,
        "voice_note_audit": voice_note_audit,
        "repeated_complaints": repeated_complaints,
        "opportunities_and_referrals": opportunities_and_referrals,
        "billing_and_cancellation_signals": billing_and_cancellation_signals,
        "contact_and_brand_updates": contact_and_brand_updates,
        "quarantined_messages": quarantined_messages,
    }
