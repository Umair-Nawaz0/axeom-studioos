import json
import re
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple

GENERIC_EMAIL_DOMAINS = {
    "gmail.com",
    "yahoo.com",
    "hotmail.com",
    "outlook.com",
    "icloud.com",
    "aol.com",
    "proton.me",
    "protonmail.com",
    "example.com",
}

BUSINESS_KEYWORDS = {
    "dental",
    "builders",
    "roofing",
    "spa",
    "medspa",
    "wealth",
    "partners",
    "bridal",
    "boutique",
    "law",
    "firm",
    "pllc",
    "llc",
    "inc",
    "corp",
    "co",
    "chiropractic",
    "athletics",
    "fitness",
    "insurance",
    "group",
    "barbershop",
    "barbers",
    "realty",
    "pediatrics",
    "coffee",
    "roasters",
    "therapy",
    "physical",
    "gym",
    "auto",
    "detailing",
    "homecare",
    "makers",
    "podcast",
    "social",
    "dfw",
    "church",
    "studio",
    "clinic",
    "agency",
}

ABBREV_WORDS = {"wp", "rg", "ins", "chiro", "pt", "peds", "fit"}


def normalize_phone(phone_str: Optional[str]) -> Optional[str]:
    if not phone_str:
        return None
    digits = re.sub(r"\D", "", phone_str)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits if len(digits) == 10 else (digits if len(digits) >= 7 else None)


def strip_location_and_agency_prefix(name: str, agency_prefixes: Optional[Set[str]] = None) -> str:
    s = (name or "").strip()
    if agency_prefixes:
        for pref in agency_prefixes:
            s = re.sub(rf"^{re.escape(pref)}\s*-\s*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s+-\s+[A-Za-z\s]+$", "", s)
    return s.strip()


def smart_title_if_upper(name: str) -> str:
    s = (name or "").strip()
    if s.isupper() and len(s) > 4:
        titled = s.title()
        for acr in ("LLC", "PLLC", "DDS", "DFW", "TX", "RG", "WP", "PT"):
            titled = re.sub(rf"\b{acr.title()}\b", acr, titled)
        return titled
    return s


def extract_message_header_info(original_line: str) -> Dict[str, Optional[str]]:
    """
    Parses header metadata from raw message line without guessing from body text:
    - [YYYY-MM-DD HH:MM] VOICE NOTE from/to <identity>, <duration>. Transcript: "..."
    - [YYYY-MM-DD HH:MM] <CHANNEL> from/to <identity>: <body>
    """
    line = (original_line or "").strip()
    vn = re.match(
        r"^\[(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})\]\s+VOICE NOTE\s+(from|to)\s+(.+?),\s*(\d+:\d+)\.\s*Transcript:\s*\"(.*)\"$",
        line,
    )
    if vn:
        ts, direction, ident, duration, body = vn.groups()
        return _enrich_identity_fields("VOICE NOTE", direction.lower(), ident.strip(), duration, body, ts)

    reg = re.match(
        r"^\[(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})\]\s+([A-Z\s]+?)\s+(from|to)\s+([^:]+):\s*(.*)$",
        line,
    )
    if reg:
        ts, chan, direction, ident, body = reg.groups()
        return _enrich_identity_fields(chan.strip(), direction.lower(), ident.strip(), None, body, ts)

    return {
        "channel": "UNKNOWN",
        "direction": "from",
        "identity": "",
        "email": None,
        "phone": None,
        "handle": None,
        "person_hint": None,
        "duration": None,
        "timestamp": None,
        "body": line,
    }


def _enrich_identity_fields(
    channel: str,
    direction: str,
    ident: str,
    duration: Optional[str],
    body: str,
    ts: str,
) -> Dict[str, Optional[str]]:
    em_match = re.search(r"([\w.+-]+@[\w.-]+\.[a-zA-Z]{2,})", ident)
    email = em_match.group(1).lower() if em_match else None

    ph = normalize_phone(ident) if re.search(r"\d{3}[-\s.]?\d{4}", ident) else None
    handle_match = re.match(r"^(@[\w._-]+)$", ident)
    handle = handle_match.group(1).lower() if handle_match else None

    person_hint = None
    paren = re.search(r"\(([^)]+)\)", ident)
    if paren and "broadcast" not in paren.group(1).lower():
        person_hint = paren.group(1).strip()
    elif "<" in ident:
        person_hint = ident.split("<", 1)[0].strip()

    return {
        "channel": channel,
        "direction": direction,
        "identity": ident,
        "email": email,
        "phone": ph,
        "handle": handle,
        "person_hint": person_hint,
        "duration": duration,
        "timestamp": ts,
        "body": body,
    }


def reconcile_all_entities(cur) -> Dict[str, Any]:
    """
    Order-independent, dynamic multi-signal client & payer identity resolution.
    Derives canonical clients, aliases, payer-vs-client relationships, and record links
    directly from database records without hardcoded client names.
    """
    cur.execute("SELECT * FROM leads;")
    leads = cur.fetchall()
    cur.execute("SELECT * FROM bookings;")
    bookings = cur.fetchall()
    cur.execute("SELECT * FROM invoices;")
    invoices = cur.fetchall()
    cur.execute("SELECT * FROM payments;")
    payments = cur.fetchall()
    cur.execute("SELECT * FROM production_videos;")
    videos = cur.fetchall()
    cur.execute("SELECT * FROM messages;")
    messages = cur.fetchall()

    # Preserve manual overrides stored in clients.notes if any exist
    cur.execute("SELECT id, canonical_name, aliases, notes FROM clients;")
    existing_clients = cur.fetchall()
    existing_by_name = {c["canonical_name"].lower(): c for c in existing_clients}
    manual_overrides: Dict[Tuple[str, str], str] = {}
    rejected_overrides: Set[Tuple[str, str, str]] = set()
    for c in existing_clients:
        notes_txt = c.get("notes") or ""
        if notes_txt.startswith("{"):
            try:
                meta = json.loads(notes_txt)
                for ov in meta.get("manual_overrides", []):
                    manual_overrides[(ov["table"], str(ov["record_id"]))] = c["canonical_name"]
                for rej in meta.get("rejected_overrides", []):
                    rejected_overrides.add((rej["table"], str(rej["record_id"]), str(c["id"])))
            except Exception:
                pass

    # Collect known domains across commercial records to detect 1-char TLD typos (.con -> .com)
    known_domains: Set[str] = set()
    for r in bookings + invoices + [l for l in leads if (l.get("status") or "").lower() == "won"]:
        em = (r.get("email") or "").strip().lower()
        if "@" in em:
            known_domains.add(em.split("@", 1)[1])

    typo_suggestions_map: Dict[Tuple[str, str], Dict[str, Any]] = {}

    def email_cluster_key(raw_email: Optional[str]) -> Optional[str]:
        if not raw_email or "@" not in raw_email:
            return None
        em = raw_email.strip().lower()
        user, dom = em.split("@", 1)
        if dom.endswith(".con") and (dom[:-1] + "m") in known_domains:
            fixed_dom = dom[:-1] + "m"
            sug = f"{user}@{fixed_dom}"
            tkey = (em, sug)
            if tkey not in typo_suggestions_map:
                typo_suggestions_map[tkey] = {
                    "raw_email": em,
                    "suggested_email": sug,
                    "occurrences": 0,
                    "reason": "1-character TLD typo (.con -> .com) corroborated by domain records",
                }
            typo_suggestions_map[tkey]["occurrences"] += 1
            dom = fixed_dom
        if dom in GENERIC_EMAIL_DOMAINS:
            return f"email:{user}@{dom}"
        return f"dom:{dom}"

    # Union-Find over commercial identity keys
    parent: Dict[str, str] = {}

    def find(x: str) -> str:
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(prefer_root: str, other: str):
        ra, rb = find(prefer_root), find(other)
        if ra != rb:
            parent[rb] = ra

    comm_keys: Set[str] = set()
    for l in leads:
        if (l.get("status") or "").lower() == "won":
            k = email_cluster_key(l.get("email"))
            if k:
                comm_keys.add(k)
    for b in bookings:
        k = email_cluster_key(b.get("email"))
        if k:
            comm_keys.add(k)
    for i in invoices:
        k = email_cluster_key(i.get("email"))
        if k:
            comm_keys.add(k)

    # Fallback for commercial records that have no email (e.g. synthetic or partial uploads)
    name_only_comm_keys: Dict[str, str] = {}
    for b in bookings:
        if not email_cluster_key(b.get("email")) and (b.get("client_name") or "").strip():
            nk = f"biz:{b['client_name'].strip().lower()}"
            comm_keys.add(nk)
            name_only_comm_keys[b["client_name"].strip().lower()] = nk
    for i in invoices:
        if not email_cluster_key(i.get("email")) and (i.get("bill_to") or "").strip():
            nk = f"biz:{i['bill_to'].strip().lower()}"
            comm_keys.add(nk)
            name_only_comm_keys[i["bill_to"].strip().lower()] = nk

    for k in comm_keys:
        find(k)

    # 1. Detect explicit rebrand announcements in messages ("X is now Y! New email is Z")
    rebrand_preferred_name: Dict[str, str] = {}
    for m in messages:
        info = extract_message_header_info(m.get("original_line") or "")
        body = m.get("message_text") or info["body"] or ""
        m_reb = re.search(
            r"is now\s+([^!?.]+)[!?.]\s*new email is\s+([\w.+-]+@[\w.-]+\.[a-zA-Z]{2,})",
            body,
            re.IGNORECASE,
        )
        if info["email"] and m_reb:
            old_k = email_cluster_key(info["email"])
            new_k = email_cluster_key(m_reb.group(2))
            if old_k and new_k:
                comm_keys.update([old_k, new_k])
                union(new_k, old_k)
                rebrand_preferred_name[find(new_k)] = m_reb.group(1).strip()

    # 2. Corroborate personal emails with corporate domains ONLY when full person name matches
    person_by_key: Dict[str, Set[str]] = defaultdict(set)
    for l in leads:
        k = email_cluster_key(l.get("email"))
        if k and (l.get("name") or "").strip():
            nm = l["name"].strip().lower()
            if " " in nm:  # Require full first+last name, never single first name alone
                person_by_key[k].add(nm)
    for m in messages:
        info = extract_message_header_info(m.get("original_line") or "")
        if info["email"] and info["person_hint"] and " " in info["person_hint"]:
            k = email_cluster_key(info["email"])
            if k:
                person_by_key[k].add(info["person_hint"].lower())

    for k_pers in list(comm_keys):
        if k_pers.startswith("email:"):
            corp_matches = [
                k_corp
                for k_corp in comm_keys
                if k_corp.startswith("dom:") and (person_by_key[k_pers] & person_by_key[k_corp])
            ]
            if len(corp_matches) == 1:
                union(corp_matches[0], k_pers)

    # 3. Detect third-party billing agency / payer relationships from message evidence
    payer_targets_raw: Dict[str, List[str]] = {}
    agency_prefixes: Set[str] = set()
    for m in messages:
        info = extract_message_header_info(m.get("original_line") or "")
        body = m.get("message_text") or info["body"] or ""
        mb = re.search(
            r"bill us\s*(?:\(([^)]+)\))?\s*for\s+(.+?)\s+and\s+([^.!?]+)[.!?]",
            body,
            re.IGNORECASE,
        )
        if info["email"] and mb:
            pk = email_cluster_key(info["email"])
            if pk and pk in comm_keys:
                root_pk = find(pk)
                if mb.group(1):
                    agency_prefixes.add(mb.group(1).strip())
                payer_targets_raw[root_pk] = [mb.group(2).strip(), mb.group(3).strip()]

    clusters: Dict[str, Set[str]] = defaultdict(set)
    for k in comm_keys:
        clusters[find(k)].add(k)

    if not clusters and not videos:
        return {"clients_count": 0, "payers_count": 0, "typo_suggestions": list(typo_suggestions_map.values())}

    # Gather raw names, lead business names, person names, emails, phones per cluster
    lead_biz_names: Dict[str, Counter] = defaultdict(Counter)
    candidate_biz_names: Dict[str, Set[str]] = defaultdict(set)
    all_aliases: Dict[str, Set[str]] = defaultdict(set)
    person_names: Dict[str, Set[str]] = defaultdict(set)
    doctor_last_names: Dict[str, Set[str]] = defaultdict(set)
    cluster_emails: Dict[str, Set[str]] = defaultdict(set)
    cluster_phones: Dict[str, Set[str]] = defaultdict(set)

    def register_person(root: str, p_name: str):
        p = p_name.strip()
        if not p:
            return
        all_aliases[root].add(p)
        low = p.lower()
        person_names[root].add(low)
        if low.startswith(("dr ", "dr.")) or low.endswith(" dds"):
            cleaned = re.sub(r"(?:^|\s)(?:dr\.?|dds)(?=\s|$)", " ", low).strip()
            if cleaned:
                person_names[root].add(cleaned)
            parts = cleaned.split()
            if parts:
                doctor_last_names[root].add(parts[-1])

    for l in leads:
        k = email_cluster_key(l.get("email"))
        if k and find(k) in clusters:
            r = find(k)
            if (l.get("email") or "").strip():
                em = l["email"].strip()
                cluster_emails[r].add(em.lower())
                all_aliases[r].add(em.lower())
            if (l.get("phone") or "").strip():
                ph = normalize_phone(l["phone"])
                if ph:
                    cluster_phones[r].add(ph)
                all_aliases[r].add(l["phone"].strip())
            lead_person_norm = ""
            if (l.get("name") or "").strip():
                register_person(r, l["name"])
                lead_person_norm = re.sub(r"(?:^|\s)(?:dr\.?|dds|pastor)(?=\s|$)", " ", l["name"].lower()).strip()
            if (l.get("business") or "").strip():
                raw_b = l["business"].strip()
                all_aliases[r].add(raw_b)
                clean_b = strip_location_and_agency_prefix(raw_b, agency_prefixes)
                clean_b_norm = re.sub(r"(?:^|\s)(?:dr\.?|dds|pastor)(?=\s|$)", " ", clean_b.lower()).strip()
                if lead_person_norm and clean_b_norm == lead_person_norm:
                    register_person(r, raw_b)
                else:
                    lead_biz_names[r][clean_b] += 1
                    candidate_biz_names[r].add(clean_b)

    for i in invoices:
        k = email_cluster_key(i.get("email")) or name_only_comm_keys.get((i.get("bill_to") or "").strip().lower())
        if k and find(k) in clusters:
            r = find(k)
            if (i.get("email") or "").strip():
                em = i["email"].strip().lower()
                cluster_emails[r].add(em)
                all_aliases[r].add(em)
            if (i.get("bill_to") or "").strip():
                bt = i["bill_to"].strip()
                all_aliases[r].add(bt)
                candidate_biz_names[r].add(strip_location_and_agency_prefix(bt, agency_prefixes))

    for p in payments:
        k = email_cluster_key(p.get("payer_email"))
        if k and find(k) in clusters:
            r = find(k)
            if (p.get("payer_email") or "").strip():
                em = p["payer_email"].strip().lower()
                cluster_emails[r].add(em)
                all_aliases[r].add(em)
            if (p.get("payer") or "").strip():
                py = p["payer"].strip()
                all_aliases[r].add(py)
                candidate_biz_names[r].add(
                    strip_location_and_agency_prefix(smart_title_if_upper(py), agency_prefixes)
                )

    # First-pass non-payer booking names so payer-billed bookings can resolve to recipient clients
    for b in bookings:
        k = email_cluster_key(b.get("email")) or name_only_comm_keys.get((b.get("client_name") or "").strip().lower())
        if k and find(k) in clusters and find(k) not in payer_targets_raw:
            r = find(k)
            if (b.get("email") or "").strip():
                em = b["email"].strip().lower()
                cluster_emails[r].add(em)
                all_aliases[r].add(em)
            if (b.get("client_name") or "").strip():
                cn = b["client_name"].strip()
                all_aliases[r].add(cn)
                if cn.lower().startswith(("dr ", "dr.")):
                    register_person(r, cn)
                else:
                    candidate_biz_names[r].add(strip_location_and_agency_prefix(cn, agency_prefixes))

    def match_recipient_cluster_by_name(raw_label: str) -> Optional[str]:
        clean = strip_location_and_agency_prefix(raw_label, agency_prefixes).lower()
        if not clean:
            return None
        exact = [
            cr
            for cr in clusters
            if cr not in payer_targets_raw
            and any(clean == n.lower() for n in candidate_biz_names[cr] | all_aliases[cr])
        ]
        if len(exact) == 1:
            return exact[0]
        sub = [
            cr
            for cr in clusters
            if cr not in payer_targets_raw
            and any(
                len(n) >= 4 and (clean in n.lower() or n.lower() in clean)
                for n in candidate_biz_names[cr]
            )
        ]
        return sub[0] if len(sub) == 1 else None

    # Resolve bookings -> root cluster (preserving recipient client when booked via agency payer!)
    booking_to_root: Dict[str, Optional[str]] = {}
    for b in bookings:
        bid = b["booking_id"]
        k = email_cluster_key(b.get("email")) or name_only_comm_keys.get((b.get("client_name") or "").strip().lower())
        r = find(k) if k and find(k) in clusters else None
        if r in payer_targets_raw and (b.get("client_name") or "").strip():
            recip = match_recipient_cluster_by_name(b["client_name"])
            if recip:
                r = recip
        booking_to_root[bid] = r
        if r and (b.get("client_name") or "").strip():
            cn = b["client_name"].strip()
            all_aliases[r].add(cn)
            candidate_biz_names[r].add(strip_location_and_agency_prefix(cn, agency_prefixes))

    # Harvest production video client strings from populated shoot_booking links
    for v in videos:
        bk = (v.get("shoot_booking") or "").strip()
        if bk and booking_to_root.get(bk):
            r = booking_to_root[bk]
            if (v.get("client") or "").strip():
                vc = v["client"].strip()
                all_aliases[r].add(vc)
                if vc.lower().startswith(("dr ", "dr.")) or vc.lower().endswith(" dds"):
                    register_person(r, vc)
                else:
                    candidate_biz_names[r].add(strip_location_and_agency_prefix(vc, agency_prefixes))

    # Also detect contact phone updates in messages ("new office number is 469-555-0120")
    for m in messages:
        info = extract_message_header_info(m.get("original_line") or "")
        body = m.get("message_text") or info["body"] or ""
        if info["email"]:
            k = email_cluster_key(info["email"])
            if k and find(k) in clusters:
                r = find(k)
                m_ph = re.search(r"new (?:office |phone )?number is\s+([\d\s().+-]{10,})", body, re.IGNORECASE)
                if m_ph:
                    new_ph = normalize_phone(m_ph.group(1))
                    if new_ph:
                        cluster_phones[r].add(new_ph)
                        all_aliases[r].add(m_ph.group(1).strip().rstrip("."))

    # Score canonical business name for each cluster
    def choose_canonical_name(root: str) -> str:
        if root in rebrand_preferred_name:
            return rebrand_preferred_name[root]

        def _score(nm: str) -> int:
            low = nm.lower()
            if not low or low in person_names[root] or low.startswith(("dr ", "dr.", "pastor ")):
                return -200
            words = re.findall(r"[a-z&']+", low)
            biz_hits = sum(1 for w in words if w in BUSINESS_KEYWORDS)
            abbrev_pen = sum(6 for w in words if w in ABBREV_WORDS)
            apostrophe_bonus = 4 if "'" in nm else 0
            caps_pen = 15 if nm.isupper() else 0
            return biz_hits * 12 + len(nm) + apostrophe_bonus - abbrev_pen - caps_pen

        if lead_biz_names[root]:
            lead_choice = sorted(
                lead_biz_names[root].keys(),
                key=lambda s: (-lead_biz_names[root][s], -len(s)),
            )[0]
            # If candidate_biz_names has a properly punctuated expansion of a possessive lead name
            lead_alnum = re.sub(r"[^a-z0-9]", "", lead_choice.lower())
            punct_expansions = [
                c
                for c in candidate_biz_names[root]
                if "'" in c
                and not c.isupper()
                and re.sub(r"[^a-z0-9]", "", c.lower()).startswith(lead_alnum)
                and len(c) > len(lead_choice)
            ]
            if punct_expansions:
                return max(punct_expansions, key=_score)
            return lead_choice

        pool = [n for n in candidate_biz_names[root] if n.strip()]
        if pool:
            best = max(pool, key=_score)
            if _score(best) > -150:
                return best
        # Fallback if entity only ever used a person name
        any_names = [a for a in all_aliases[root] if "@" not in a and not re.search(r"\d{3}.*\d{4}", a)]
        return sorted(any_names, key=len, reverse=True)[0] if any_names else root

    canon_by_root: Dict[str, str] = {r: choose_canonical_name(r) for r in clusters}

    # Resolve payer -> canonical recipient client names
    payer_for_canonical: Dict[str, List[str]] = {}
    recipient_billed_by: Dict[str, str] = {}
    for pk, raw_targets in payer_targets_raw.items():
        resolved_targets = []
        for rt in raw_targets:
            tr = match_recipient_cluster_by_name(rt)
            resolved_targets.append(canon_by_root[tr] if tr else rt)
            if tr:
                recipient_billed_by[tr] = canon_by_root[pk]
        payer_for_canonical[pk] = resolved_targets

    # Upsert canonical clients into `clients` table and capture UUIDs
    root_to_uuid: Dict[str, str] = {}
    canon_to_uuid: Dict[str, str] = {}

    for r, cname in canon_by_root.items():
        alias_list = sorted(a for a in all_aliases[r] if a and a != cname)
        prev = existing_by_name.get(cname.lower())
        prev_overrides = []
        prev_rejected = []
        if prev and (prev.get("notes") or "").startswith("{"):
            try:
                p_meta = json.loads(prev["notes"])
                prev_overrides = p_meta.get("manual_overrides", [])
                prev_rejected = p_meta.get("rejected_overrides", [])
            except Exception:
                prev_overrides = []
                prev_rejected = []

        meta = {
            "entity_type": "payer" if r in payer_for_canonical else "client",
            "pays_for": payer_for_canonical.get(r, []),
            "billed_via_payer": recipient_billed_by.get(r),
            "emails": sorted(cluster_emails[r]),
            "phones": sorted(cluster_phones[r]),
            "manual_overrides": prev_overrides,
            "rejected_overrides": prev_rejected,
        }
        cur.execute(
            """
            INSERT INTO clients (canonical_name, aliases, notes)
            VALUES (%s, %s, %s)
            ON CONFLICT (canonical_name) DO UPDATE SET
                aliases = EXCLUDED.aliases,
                notes = EXCLUDED.notes
            RETURNING id;
            """,
            (cname, json.dumps(alias_list), json.dumps(meta)),
        )
        cid = str(cur.fetchone()["id"])
        root_to_uuid[r] = cid
        canon_to_uuid[cname] = cid

    # Remove stale seeded client rows that have zero records and are not part of current clusters
    active_uuids = set(root_to_uuid.values())
    for c in existing_clients:
        if str(c["id"]) not in active_uuids and not manual_overrides:
            cur.execute("DELETE FROM clients WHERE id = %s;", (c["id"],))

    # Helper to resolve production video row without shoot_booking
    def match_video_root(raw_client_str: Optional[str]) -> Optional[str]:
        if not raw_client_str or not raw_client_str.strip():
            return None
        vc = raw_client_str.strip()
        vc_clean = strip_location_and_agency_prefix(vc, agency_prefixes).lower()

        # 1. Exact alias or canonical match among service clients
        exact = [
            r
            for r in clusters
            if r not in payer_for_canonical
            and (
                vc.lower() == canon_by_root[r].lower()
                or vc_clean == canon_by_root[r].lower()
                or any(vc.lower() == a.lower() or vc_clean == a.lower() for a in all_aliases[r] | candidate_biz_names[r])
            )
        ]
        if len(exact) == 1:
            return exact[0]

        # 2. Doctor title match ("Dr Haddad", "Dr Green")
        if vc_clean.startswith(("dr ", "dr.")):
            last = re.sub(r"^dr\.?\s+", "", vc_clean).split()[-1]
            doc_hits = [r for r in clusters if r not in payer_for_canonical and last in doctor_last_names[r]]
            if len(doc_hits) == 1:
                return doc_hits[0]

        # 3. Conservative substring match on candidate business names (require unique hit)
        if len(vc_clean) >= 4:
            sub = [
                r
                for r in clusters
                if r not in payer_for_canonical
                and any(vc_clean in n.lower() or n.lower() in vc_clean for n in candidate_biz_names[r])
            ]
            if len(sub) == 1:
                return sub[0]

        # 4. If a commercial video exists for a brand-new standalone client with no bookings/invoices yet
        return None

    # Helper to resolve message sender/recipient conservatively
    # Build normalized alphanumeric business-stem index for Instagram handles (@hillcrestroofingcodfw, @danielsautodetaili)
    alnum_stems: Dict[str, str] = {}
    for r in clusters:
        for nm in {canon_by_root[r]} | candidate_biz_names[r]:
            stem = re.sub(r"[^a-z0-9]", "", nm.lower())
            if len(stem) >= 8:
                alnum_stems[stem] = r

    def match_message_root(original_line: str, sender_col: str) -> Optional[str]:
        info = extract_message_header_info(original_line)
        # 1. Exact email match
        if info["email"]:
            ek = email_cluster_key(info["email"])
            if ek and find(ek) in clusters:
                return find(ek)
        # 2. Exact 10-digit phone match (corroborating person first name if multiple share phone, though phones are unique)
        if info["phone"]:
            ph_hits = [r for r in clusters if info["phone"] in cluster_phones[r]]
            if len(ph_hits) == 1:
                return ph_hits[0]
            if len(ph_hits) > 1 and info["person_hint"]:
                ph_filtered = [
                    r
                    for r in ph_hits
                    if any(info["person_hint"].lower() in p for p in person_names[r])
                ]
                if len(ph_filtered) == 1:
                    return ph_filtered[0]
        # 3. Social handle match (@hillcrestroofingcodfw -> hillcrestroofingco, @danielsautodetaili -> danielsautodetailing)
        if info["handle"]:
            h_clean = re.sub(r"[^a-z0-9]", "", info["handle"].lstrip("@").lower())
            if len(h_clean) >= 10:
                h_hits = {
                    r
                    for stem, r in alnum_stems.items()
                    if h_clean.startswith(stem[:12]) or stem.startswith(h_clean[:12])
                }
                if len(h_hits) == 1:
                    return next(iter(h_hits))
        return None

    # Apply links to leads (only link leads that belong to an established commercial client; keep prospects unlinked!)
    for l in leads:
        lid = l["lead_id"]
        ov = manual_overrides.get(("leads", lid))
        if ov and ov in canon_to_uuid:
            cid = canon_to_uuid[ov]
        else:
            k = email_cluster_key(l.get("email"))
            r = find(k) if k and find(k) in clusters else None
            if not r and (l.get("phone") or "").strip():
                ph = normalize_phone(l["phone"])
                ph_hits = [cr for cr in clusters if ph and ph in cluster_phones[cr]]
                if len(ph_hits) == 1 and (l.get("business") or "").strip():
                    # Verify business name also aligns before linking by phone
                    lb = strip_location_and_agency_prefix(l["business"], agency_prefixes).lower()
                    if any(lb in n.lower() or n.lower() in lb for n in candidate_biz_names[ph_hits[0]]):
                        r = ph_hits[0]
            cid = root_to_uuid[r] if r else None
        if cid and ("leads", str(lid), str(cid)) in rejected_overrides:
            cid = None
        if str(l.get("client_id") or "") != str(cid or ""):
            cur.execute("UPDATE leads SET client_id = %s WHERE lead_id = %s;", (cid, lid))

    # Apply links to bookings
    for b in bookings:
        bid = b["booking_id"]
        ov = manual_overrides.get(("bookings", bid))
        cid = canon_to_uuid[ov] if (ov and ov in canon_to_uuid) else (
            root_to_uuid.get(booking_to_root.get(bid)) if booking_to_root.get(bid) else None
        )
        if cid and ("bookings", str(bid), str(cid)) in rejected_overrides:
            cid = None
        if str(b.get("client_id") or "") != str(cid or ""):
            cur.execute("UPDATE bookings SET client_id = %s WHERE booking_id = %s;", (cid, bid))

    # Apply links to invoices
    for i in invoices:
        ino = i["invoice_no"]
        ov = manual_overrides.get(("invoices", ino))
        if ov and ov in canon_to_uuid:
            cid = canon_to_uuid[ov]
        else:
            k = email_cluster_key(i.get("email")) or name_only_comm_keys.get((i.get("bill_to") or "").strip().lower())
            r = find(k) if k and find(k) in clusters else None
            cid = root_to_uuid[r] if r else None
        if cid and ("invoices", str(ino), str(cid)) in rejected_overrides:
            cid = None
        if str(i.get("client_id") or "") != str(cid or ""):
            cur.execute("UPDATE invoices SET client_id = %s WHERE invoice_no = %s;", (cid, ino))

    # Re-link payments.matched_invoice_no safely whenever exact invoice_no exists in `invoices`
    existing_inv_nos = {i["invoice_no"].upper(): i["invoice_no"] for i in invoices}
    for p in payments:
        pid = p["payment_id"]
        ref = (p.get("reference") or "").strip()
        m_inv = re.search(r"\b(INV-\d+)\b", ref, re.IGNORECASE)
        target_inv = existing_inv_nos.get(m_inv.group(1).upper()) if m_inv else None
        if (p.get("matched_invoice_no") or None) != target_inv:
            cur.execute("UPDATE payments SET matched_invoice_no = %s WHERE payment_id = %s;", (target_inv, pid))

    # Apply links to production_videos
    for v in videos:
        vid = v["video_id"]
        ov = manual_overrides.get(("production_videos", vid))
        if ov and ov in canon_to_uuid:
            cid = canon_to_uuid[ov]
        else:
            bk = (v.get("shoot_booking") or "").strip()
            r = booking_to_root.get(bk) if bk and booking_to_root.get(bk) else match_video_root(v.get("client"))
            cid = root_to_uuid[r] if r else None
        if cid and ("production_videos", str(vid), str(cid)) in rejected_overrides:
            cid = None
        if str(v.get("client_id") or "") != str(cid or ""):
            cur.execute("UPDATE production_videos SET client_id = %s WHERE video_id = %s;", (cid, vid))

    # Apply links to messages
    for m in messages:
        mid = str(m["id"])
        ov = manual_overrides.get(("messages", mid))
        if ov and ov in canon_to_uuid:
            cid = canon_to_uuid[ov]
        else:
            r = match_message_root(m.get("original_line") or "", m.get("sender") or "")
            cid = root_to_uuid[r] if r else None
        if cid and ("messages", str(mid), str(cid)) in rejected_overrides:
            cid = None
        if str(m.get("client_id") or "") != str(cid or ""):
            cur.execute("UPDATE messages SET client_id = %s WHERE id = %s;", (cid, mid))

    return {
        "clients_count": sum(1 for r in clusters if r not in payer_for_canonical),
        "payers_count": len(payer_for_canonical),
        "typo_suggestions": list(typo_suggestions_map.values()),
    }
