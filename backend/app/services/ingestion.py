import csv
import io
import re
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Set, Tuple

from ..models import UploadResult
from .identity import extract_message_header_info, reconcile_all_entities

MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20 MB safety ceiling
IMPORT_HISTORY: List[Dict[str, Any]] = []


def get_import_history(cur=None) -> Dict[str, Any]:
    table_counts: Dict[str, int] = {}
    if cur is not None:
        for tbl in ("clients", "leads", "bookings", "invoices", "payments", "production_videos", "messages", "team_members", "cost_rules"):
            cur.execute(f"SELECT COUNT(*) AS c FROM {tbl};")
            table_counts[tbl] = int(cur.fetchone()["c"] or 0)
    return {
        "events": list(reversed(IMPORT_HISTORY[-50:])),
        "current_table_counts": table_counts,
    }


def clear_import_history() -> None:
    IMPORT_HISTORY.clear()


def parse_explicit_date(raw: Optional[str], expected_fmt: str) -> Optional[date]:
    if raw is None or not str(raw).strip():
        return None
    s = str(raw).strip()
    fmts = [expected_fmt]
    if expected_fmt != "%Y-%m-%d" and re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        fmts.append("%Y-%m-%d")
    for fmt in fmts:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Invalid date '{s}' (expected {expected_fmt})")


def parse_explicit_timestamp(raw: Optional[str]) -> datetime:
    if raw is None or not str(raw).strip():
        raise ValueError("Missing timestamp")
    s = str(raw).strip()
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    raise ValueError(f"Invalid timestamp '{s}' (expected YYYY-MM-DD HH:MM)")


def parse_decimal_amount(raw: Optional[str], allow_null: bool = False) -> Optional[Decimal]:
    if raw is None or not str(raw).strip():
        if allow_null:
            return None
        raise ValueError("Missing numeric amount")
    cleaned = str(raw).strip().replace("$", "").replace(",", "")
    if not re.match(r"^-?\d+(?:\.\d+)?$", cleaned):
        raise ValueError(f"Invalid currency/numeric value '{raw}'")
    try:
        return Decimal(cleaned).quantize(Decimal("0.01"))
    except InvalidOperation as exc:
        raise ValueError(f"Invalid decimal '{raw}'") from exc


def _check_headers(fieldnames: Optional[List[str]], required: Set[str], filename: str) -> Optional[UploadResult]:
    if not fieldnames:
        return UploadResult(
            file_type="invalid",
            filename=filename,
            rows_processed=0,
            rows_inserted=0,
            rows_updated=0,
            rows_skipped=0,
            errors=[f"File '{filename}' is empty or missing a CSV header row."],
            message=f"Rejected '{filename}': empty CSV.",
        )
    normalized = {h.strip() for h in fieldnames if h is not None}
    missing = sorted(required - normalized)
    if missing:
        return UploadResult(
            file_type="invalid",
            filename=filename,
            rows_processed=0,
            rows_inserted=0,
            rows_updated=0,
            rows_skipped=0,
            errors=[f"Missing required column(s) in '{filename}': {', '.join(missing)}"],
            message=f"Rejected '{filename}': missing required columns ({', '.join(missing)}).",
        )
    return None


def process_uploaded_file(
    cur,
    filename: str,
    content_bytes: bytes,
    run_reconcile: bool = True,
    dry_run: bool = False,
) -> UploadResult:
    safe_name = (filename or "unknown").split("/")[-1].split("\\")[-1]
    fn_low = safe_name.lower()

    if not (fn_low.endswith(".csv") or fn_low.endswith(".txt")):
        return UploadResult(
            file_type="unsupported",
            filename=safe_name,
            rows_processed=0,
            rows_inserted=0,
            rows_updated=0,
            rows_skipped=0,
            errors=[f"Unsupported file extension in '{safe_name}'. Only .csv and .txt files are accepted."],
            message=f"Rejected '{safe_name}': unsupported file extension.",
        )

    if len(content_bytes) > MAX_UPLOAD_BYTES:
        return UploadResult(
            file_type="oversized",
            filename=safe_name,
            rows_processed=0,
            rows_inserted=0,
            rows_updated=0,
            rows_skipped=0,
            errors=[f"File '{safe_name}' exceeds maximum allowed size of 20 MB."],
            message=f"Rejected '{safe_name}': file too large.",
        )

    if len(content_bytes) == 0:
        return UploadResult(
            file_type="empty",
            filename=safe_name,
            rows_processed=0,
            rows_inserted=0,
            rows_updated=0,
            rows_skipped=0,
            errors=[f"File '{safe_name}' contains 0 bytes."],
            message=f"Rejected '{safe_name}': empty file.",
        )

    # Strict UTF-8 decode first; detect binary/NUL corruption explicitly
    if b"\x00" in content_bytes:
        return UploadResult(
            file_type="corrupted",
            filename=safe_name,
            rows_processed=0,
            rows_inserted=0,
            rows_updated=0,
            rows_skipped=0,
            errors=[f"File '{safe_name}' contains binary NUL bytes and cannot be parsed as text/CSV."],
            message=f"Rejected '{safe_name}': corrupted binary content.",
        )

    try:
        text = content_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        return UploadResult(
            file_type="corrupted",
            filename=safe_name,
            rows_processed=0,
            rows_inserted=0,
            rows_updated=0,
            rows_skipped=0,
            errors=[f"File '{safe_name}' has invalid UTF-8 text encoding."],
            message=f"Rejected '{safe_name}': invalid text encoding.",
        )

    if not text.strip():
        return UploadResult(
            file_type="empty",
            filename=safe_name,
            rows_processed=0,
            rows_inserted=0,
            rows_updated=0,
            rows_skipped=0,
            errors=[f"File '{safe_name}' contains only whitespace."],
            message=f"Rejected '{safe_name}': empty content.",
        )

    # Detect target table by header signature first (works even for custom filenames!), then filename
    first_line = text.splitlines()[0].strip() if text.splitlines() else ""
    cur.execute("SAVEPOINT ingest_file_sp;")
    try:
        if fn_low.endswith(".txt") or first_line.startswith("["):
            res = _ingest_messages(cur, safe_name, text)
        elif "lead_id" in first_line or "lead" in fn_low:
            res = _ingest_leads(cur, safe_name, text)
        elif "booking_id" in first_line or "booking" in fn_low:
            res = _ingest_bookings(cur, safe_name, text)
        elif "invoice_no" in first_line or "invoice" in fn_low:
            res = _ingest_invoices(cur, safe_name, text)
        elif "payment_id" in first_line or "payment" in fn_low:
            res = _ingest_payments(cur, safe_name, text)
        elif "video_id" in first_line or "production" in fn_low or "board" in fn_low:
            res = _ingest_production(cur, safe_name, text)
        elif ("role" in first_line and "joined" in first_line) or "team" in fn_low:
            res = _ingest_team(cur, safe_name, text)
        elif ("item" in first_line and "cost" in first_line) or "cost" in fn_low:
            res = _ingest_costs(cur, safe_name, text)
        else:
            res = UploadResult(
                file_type="unknown",
                filename=safe_name,
                rows_processed=0,
                rows_inserted=0,
                rows_updated=0,
                rows_skipped=0,
                errors=[f"Could not recognize schema/headers for '{safe_name}'."],
                message=f"Rejected '{safe_name}': unrecognized file format.",
            )

        if dry_run:
            cur.execute("ROLLBACK TO SAVEPOINT ingest_file_sp;")
            cur.execute("RELEASE SAVEPOINT ingest_file_sp;")
            res.message = f"[Preview] {res.message}"
            return res

        if run_reconcile and (res.rows_inserted > 0 or res.rows_updated > 0):
            reconcile_all_entities(cur)
        cur.execute("RELEASE SAVEPOINT ingest_file_sp;")
        IMPORT_HISTORY.append(
            {
                "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
                "filename": safe_name,
                "file_type": res.file_type,
                "rows_processed": res.rows_processed,
                "rows_inserted": res.rows_inserted,
                "rows_updated": res.rows_updated,
                "rows_skipped": res.rows_skipped,
                "rejected_count": len(res.errors),
                "warnings_count": len(res.warnings),
                "message": res.message,
            }
        )
        return res
    except Exception as exc:
        cur.execute("ROLLBACK TO SAVEPOINT ingest_file_sp;")
        cur.execute("RELEASE SAVEPOINT ingest_file_sp;")
        return UploadResult(
            file_type="error",
            filename=safe_name,
            rows_processed=0,
            rows_inserted=0,
            rows_updated=0,
            rows_skipped=0,
            errors=[f"Transaction rolled back for '{safe_name}': {str(exc)}"],
            message=f"Failed to import '{safe_name}' safely; rolled back.",
        )


def _format_summary_msg(label: str, ins: int, upd: int, skp: int, errs: List[str]) -> str:
    parts = [f"{ins} inserted", f"{upd} updated", f"{skp} unchanged/skipped"]
    if errs:
        parts.append(f"{len(errs)} rejected")
    return f"{label}: " + ", ".join(parts) + "."


def _ingest_leads(cur, filename: str, text: str) -> UploadResult:
    rdr = csv.DictReader(io.StringIO(text))
    hdr_err = _check_headers(
        rdr.fieldnames,
        {"lead_id", "created", "name", "business", "email", "phone", "source", "first_reply", "status"},
        filename,
    )
    if hdr_err:
        return hdr_err

    cur.execute("SELECT lead_id, created, name, business, email, phone, source, first_reply, status FROM leads;")
    existing = {r["lead_id"]: r for r in cur.fetchall()}

    rows = list(rdr)
    inserted = updated = skipped = 0
    errors: List[str] = []
    warnings: List[str] = []
    seen_ids: Set[str] = set()

    for idx, r in enumerate(rows, start=2):
        if None in r and r[None]:
            warnings.append(f"Row {idx}: extra unlabelled column values ignored.")
        lid = (r.get("lead_id") or "").strip()
        if not lid:
            errors.append(f"Row {idx}: missing lead_id.")
            continue
        if lid in seen_ids:
            errors.append(f"Row {idx}: duplicate lead_id '{lid}' within '{filename}'.")
            continue
        seen_ids.add(lid)

        try:
            created_dt = parse_explicit_timestamp(r.get("created"))
            reply_d = parse_explicit_date(r.get("first_reply"), "%Y-%m-%d")
        except ValueError as ve:
            errors.append(f"Row {idx} ({lid}): {ve}")
            continue

        name = r.get("name") or ""
        business = r.get("business") or ""
        email = r.get("email") or ""
        phone = r.get("phone") or ""
        source = r.get("source") or ""
        status = r.get("status") or ""

        cur.execute("SAVEPOINT row_sp;")
        try:
            if lid in existing:
                ex = existing[lid]
                ex_created = ex["created"].replace(tzinfo=None) if ex["created"] else None
                same = (
                    ex_created == created_dt
                    and (ex["name"] or "") == name
                    and (ex["business"] or "") == business
                    and (ex["email"] or "") == email
                    and (ex["phone"] or "") == phone
                    and (ex["source"] or "") == source
                    and ex["first_reply"] == reply_d
                    and (ex["status"] or "") == status
                )
                if same:
                    skipped += 1
                else:
                    cur.execute(
                        """
                        UPDATE leads
                        SET created=%s, name=%s, business=%s, email=%s, phone=%s, source=%s, first_reply=%s, status=%s
                        WHERE lead_id=%s;
                        """,
                        (created_dt, name, business, email, phone, source, reply_d, status, lid),
                    )
                    updated += 1
            else:
                cur.execute(
                    """
                    INSERT INTO leads (lead_id, created, name, business, email, phone, source, first_reply, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);
                    """,
                    (lid, created_dt, name, business, email, phone, source, reply_d, status),
                )
                inserted += 1
            cur.execute("RELEASE SAVEPOINT row_sp;")
        except Exception as exc:
            cur.execute("ROLLBACK TO SAVEPOINT row_sp;")
            errors.append(f"Row {idx} ({lid}): {exc}")

    return UploadResult(
        file_type="leads",
        filename=filename,
        rows_processed=len(rows),
        rows_inserted=inserted,
        rows_updated=updated,
        rows_skipped=skipped,
        warnings=warnings,
        errors=errors,
        message=_format_summary_msg("Leads", inserted, updated, skipped, errors),
    )


def _ingest_bookings(cur, filename: str, text: str) -> UploadResult:
    rdr = csv.DictReader(io.StringIO(text))
    hdr_err = _check_headers(
        rdr.fieldnames,
        {"booking_id", "date", "client_name", "email", "service", "status", "price"},
        filename,
    )
    if hdr_err:
        return hdr_err

    cur.execute("SELECT booking_id, date, client_name, email, service, status, price FROM bookings;")
    existing = {r["booking_id"]: r for r in cur.fetchall()}

    rows = list(rdr)
    inserted = updated = skipped = 0
    errors: List[str] = []
    warnings: List[str] = []
    seen_ids: Set[str] = set()

    for idx, r in enumerate(rows, start=2):
        bid = (r.get("booking_id") or "").strip()
        if not bid:
            errors.append(f"Row {idx}: missing booking_id.")
            continue
        if bid in seen_ids:
            errors.append(f"Row {idx}: duplicate booking_id '{bid}' within '{filename}'.")
            continue
        seen_ids.add(bid)

        try:
            b_date = parse_explicit_date(r.get("date"), "%m/%d/%Y")
            if b_date is None:
                raise ValueError("Missing booking date")
            price = parse_decimal_amount(r.get("price"), allow_null=False)
        except ValueError as ve:
            errors.append(f"Row {idx} ({bid}): {ve}")
            continue

        client_name = r.get("client_name") or ""
        email = r.get("email") or ""
        service = r.get("service") or ""
        status = r.get("status") or ""

        cur.execute("SAVEPOINT row_sp;")
        try:
            if bid in existing:
                ex = existing[bid]
                same = (
                    ex["date"] == b_date
                    and (ex["client_name"] or "") == client_name
                    and (ex["email"] or "") == email
                    and (ex["service"] or "") == service
                    and (ex["status"] or "") == status
                    and Decimal(str(ex["price"])) == price
                )
                if same:
                    skipped += 1
                else:
                    cur.execute(
                        """
                        UPDATE bookings
                        SET date=%s, client_name=%s, email=%s, service=%s, status=%s, price=%s
                        WHERE booking_id=%s;
                        """,
                        (b_date, client_name, email, service, status, price, bid),
                    )
                    updated += 1
            else:
                cur.execute(
                    """
                    INSERT INTO bookings (booking_id, date, client_name, email, service, status, price)
                    VALUES (%s, %s, %s, %s, %s, %s, %s);
                    """,
                    (bid, b_date, client_name, email, service, status, price),
                )
                inserted += 1
            cur.execute("RELEASE SAVEPOINT row_sp;")
        except Exception as exc:
            cur.execute("ROLLBACK TO SAVEPOINT row_sp;")
            errors.append(f"Row {idx} ({bid}): {exc}")

    return UploadResult(
        file_type="bookings",
        filename=filename,
        rows_processed=len(rows),
        rows_inserted=inserted,
        rows_updated=updated,
        rows_skipped=skipped,
        warnings=warnings,
        errors=errors,
        message=_format_summary_msg("Bookings", inserted, updated, skipped, errors),
    )


def _ingest_invoices(cur, filename: str, text: str) -> UploadResult:
    rdr = csv.DictReader(io.StringIO(text))
    hdr_err = _check_headers(
        rdr.fieldnames,
        {"invoice_no", "bill_to", "email", "issued", "due", "amount", "status", "memo"},
        filename,
    )
    if hdr_err:
        return hdr_err

    cur.execute("SELECT invoice_no, bill_to, email, issued, due, amount, status, memo FROM invoices;")
    existing = {r["invoice_no"]: r for r in cur.fetchall()}

    rows = list(rdr)
    inserted = updated = skipped = 0
    errors: List[str] = []
    warnings: List[str] = []
    seen_ids: Set[str] = set()

    for idx, r in enumerate(rows, start=2):
        ino = (r.get("invoice_no") or "").strip()
        if not ino:
            errors.append(f"Row {idx}: missing invoice_no.")
            continue
        if ino in seen_ids:
            errors.append(f"Row {idx}: duplicate invoice_no '{ino}' within '{filename}'.")
            continue
        seen_ids.add(ino)

        try:
            issued = parse_explicit_date(r.get("issued"), "%Y-%m-%d")
            due = parse_explicit_date(r.get("due"), "%Y-%m-%d")
            if issued is None or due is None:
                raise ValueError("Missing issued or due date")
            amt = parse_decimal_amount(r.get("amount"), allow_null=False)
        except ValueError as ve:
            errors.append(f"Row {idx} ({ino}): {ve}")
            continue

        bill_to = r.get("bill_to") or ""
        email = r.get("email") or ""
        status = (r.get("status") or "").strip()
        memo = r.get("memo") or ""

        cur.execute("SAVEPOINT row_sp;")
        try:
            if ino in existing:
                ex = existing[ino]
                same = (
                    (ex["bill_to"] or "") == bill_to
                    and (ex["email"] or "") == email
                    and ex["issued"] == issued
                    and ex["due"] == due
                    and Decimal(str(ex["amount"])) == amt
                    and (ex["status"] or "") == status
                    and (ex["memo"] or "") == memo
                )
                if same:
                    skipped += 1
                else:
                    cur.execute(
                        """
                        UPDATE invoices
                        SET bill_to=%s, email=%s, issued=%s, due=%s, amount=%s, status=%s, memo=%s
                        WHERE invoice_no=%s;
                        """,
                        (bill_to, email, issued, due, amt, status, memo, ino),
                    )
                    updated += 1
            else:
                cur.execute(
                    """
                    INSERT INTO invoices (invoice_no, bill_to, email, issued, due, amount, status, memo)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
                    """,
                    (ino, bill_to, email, issued, due, amt, status, memo),
                )
                inserted += 1
            cur.execute("RELEASE SAVEPOINT row_sp;")
        except Exception as exc:
            cur.execute("ROLLBACK TO SAVEPOINT row_sp;")
            errors.append(f"Row {idx} ({ino}): {exc}")

    return UploadResult(
        file_type="invoices",
        filename=filename,
        rows_processed=len(rows),
        rows_inserted=inserted,
        rows_updated=updated,
        rows_skipped=skipped,
        warnings=warnings,
        errors=errors,
        message=_format_summary_msg("Invoices", inserted, updated, skipped, errors),
    )


def _ingest_payments(cur, filename: str, text: str) -> UploadResult:
    rdr = csv.DictReader(io.StringIO(text))
    hdr_err = _check_headers(
        rdr.fieldnames,
        {"payment_id", "date", "payer", "payer_email", "amount", "method", "reference"},
        filename,
    )
    if hdr_err:
        return hdr_err

    cur.execute("SELECT payment_id, payment_date, payer, payer_email, amount, method, reference FROM payments;")
    existing = {r["payment_id"]: r for r in cur.fetchall()}

    cur.execute("SELECT invoice_no FROM invoices;")
    existing_invoices = {r["invoice_no"].upper(): r["invoice_no"] for r in cur.fetchall()}

    rows = list(rdr)
    inserted = updated = skipped = 0
    errors: List[str] = []
    warnings: List[str] = []
    seen_ids: Set[str] = set()

    for idx, r in enumerate(rows, start=2):
        pid = (r.get("payment_id") or "").strip()
        if not pid:
            errors.append(f"Row {idx}: missing payment_id.")
            continue
        if pid in seen_ids:
            errors.append(f"Row {idx}: duplicate payment_id '{pid}' within '{filename}'.")
            continue
        seen_ids.add(pid)

        try:
            p_date = parse_explicit_date(r.get("date"), "%d/%m/%Y")
            if p_date is None:
                raise ValueError("Missing payment date")
            amt = parse_decimal_amount(r.get("amount"), allow_null=False)
        except ValueError as ve:
            errors.append(f"Row {idx} ({pid}): {ve}")
            continue

        payer = r.get("payer") or ""
        payer_email = r.get("payer_email") or ""
        method = r.get("method") or ""
        ref = (r.get("reference") or "").strip()

        m_inv = re.search(r"\b(INV-\d+)\b", ref, re.IGNORECASE)
        matched_inv = existing_invoices.get(m_inv.group(1).upper()) if m_inv else None
        if m_inv and not matched_inv:
            warnings.append(
                f"Row {idx} ({pid}): referenced invoice '{m_inv.group(1)}' not yet in invoices table; stored raw reference for automatic linking when invoices arrive."
            )

        cur.execute("SAVEPOINT row_sp;")
        try:
            if pid in existing:
                ex = existing[pid]
                same = (
                    ex["payment_date"] == p_date
                    and (ex["payer"] or "") == payer
                    and (ex["payer_email"] or "") == payer_email
                    and Decimal(str(ex["amount"])) == amt
                    and (ex["method"] or "") == method
                    and (ex["reference"] or "") == ref
                )
                if same:
                    skipped += 1
                else:
                    cur.execute(
                        """
                        UPDATE payments
                        SET payment_date=%s, payer=%s, payer_email=%s, amount=%s, method=%s, reference=%s, matched_invoice_no=%s
                        WHERE payment_id=%s;
                        """,
                        (p_date, payer, payer_email, amt, method, ref, matched_inv, pid),
                    )
                    updated += 1
            else:
                cur.execute(
                    """
                    INSERT INTO payments (payment_id, payment_date, payer, payer_email, amount, method, reference, matched_invoice_no)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
                    """,
                    (pid, p_date, payer, payer_email, amt, method, ref, matched_inv),
                )
                inserted += 1
            cur.execute("RELEASE SAVEPOINT row_sp;")
        except Exception as exc:
            cur.execute("ROLLBACK TO SAVEPOINT row_sp;")
            errors.append(f"Row {idx} ({pid}): {exc}")

    return UploadResult(
        file_type="payments",
        filename=filename,
        rows_processed=len(rows),
        rows_inserted=inserted,
        rows_updated=updated,
        rows_skipped=skipped,
        warnings=warnings,
        errors=errors,
        message=_format_summary_msg("Payments", inserted, updated, skipped, errors),
    )


def _ingest_production(cur, filename: str, text: str) -> UploadResult:
    rdr = csv.DictReader(io.StringIO(text))
    hdr_err = _check_headers(
        rdr.fieldnames,
        {
            "video_id",
            "client",
            "title",
            "editor",
            "stage",
            "notes_on_board",
            "revisions",
            "editor_hours",
            "client_approved_on",
            "shoot_booking",
        },
        filename,
    )
    if hdr_err:
        return hdr_err

    cur.execute(
        "SELECT video_id, client, title, editor, stage, notes_on_board, revisions, editor_hours, client_approved_on, shoot_booking FROM production_videos;"
    )
    existing = {r["video_id"]: r for r in cur.fetchall()}

    rows = list(rdr)
    inserted = updated = skipped = 0
    errors: List[str] = []
    warnings: List[str] = []
    seen_ids: Set[str] = set()

    for idx, r in enumerate(rows, start=2):
        vid = (r.get("video_id") or "").strip()
        if not vid:
            errors.append(f"Row {idx}: missing video_id.")
            continue
        if vid in seen_ids:
            errors.append(f"Row {idx}: duplicate video_id '{vid}' within '{filename}'.")
            continue
        seen_ids.add(vid)

        title = (r.get("title") or "").strip()
        if not title:
            errors.append(f"Row {idx} ({vid}): missing video title.")
            continue

        try:
            hours = parse_decimal_amount(r.get("editor_hours"), allow_null=True) or Decimal("0.00")
            rev_raw = (r.get("revisions") or "").strip()
            revs = int(rev_raw) if rev_raw else 0
            appr = parse_explicit_date(r.get("client_approved_on"), "%Y-%m-%d")
        except ValueError as ve:
            errors.append(f"Row {idx} ({vid}): {ve}")
            continue

        client_str = r.get("client") or ""
        editor = r.get("editor") or ""
        stage = r.get("stage") or ""
        notes = r.get("notes_on_board") or ""
        bk = (r.get("shoot_booking") or "").strip() or None

        cur.execute("SAVEPOINT row_sp;")
        try:
            if vid in existing:
                ex = existing[vid]
                same = (
                    (ex["client"] or "") == client_str
                    and (ex["title"] or "") == title
                    and (ex["editor"] or "") == editor
                    and (ex["stage"] or "") == stage
                    and (ex["notes_on_board"] or "") == notes
                    and int(ex["revisions"] or 0) == revs
                    and Decimal(str(ex["editor_hours"] or 0)) == hours
                    and ex["client_approved_on"] == appr
                    and (ex["shoot_booking"] or None) == bk
                )
                if same:
                    skipped += 1
                else:
                    cur.execute(
                        """
                        UPDATE production_videos
                        SET client=%s, title=%s, editor=%s, stage=%s, notes_on_board=%s,
                            revisions=%s, editor_hours=%s, client_approved_on=%s, shoot_booking=%s
                        WHERE video_id=%s;
                        """,
                        (client_str, title, editor, stage, notes, revs, hours, appr, bk, vid),
                    )
                    updated += 1
            else:
                cur.execute(
                    """
                    INSERT INTO production_videos
                        (video_id, client, title, editor, stage, notes_on_board, revisions, editor_hours, client_approved_on, shoot_booking)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                    """,
                    (vid, client_str, title, editor, stage, notes, revs, hours, appr, bk),
                )
                inserted += 1
            cur.execute("RELEASE SAVEPOINT row_sp;")
        except Exception as exc:
            cur.execute("ROLLBACK TO SAVEPOINT row_sp;")
            errors.append(f"Row {idx} ({vid}): {exc}")

    return UploadResult(
        file_type="production_videos",
        filename=filename,
        rows_processed=len(rows),
        rows_inserted=inserted,
        rows_updated=updated,
        rows_skipped=skipped,
        warnings=warnings,
        errors=errors,
        message=_format_summary_msg("Production board", inserted, updated, skipped, errors),
    )


def _ingest_messages(cur, filename: str, text: str) -> UploadResult:
    raw_lines = [(line_no, l.strip()) for line_no, l in enumerate(text.splitlines(), start=1) if l.strip()]
    cur.execute("SELECT original_line FROM messages;")
    existing_lines = {r["original_line"] for r in cur.fetchall() if r.get("original_line")}

    inserted = updated = skipped = 0
    errors: List[str] = []
    warnings: List[str] = []

    for line_no, line in raw_lines:
        info = extract_message_header_info(line)
        if info["channel"] == "UNKNOWN" or not info["timestamp"]:
            errors.append(f"Line {line_no}: malformed message header '{line[:60]}'")
            continue

        try:
            msg_dt = parse_explicit_timestamp(info["timestamp"])
        except ValueError as ve:
            errors.append(f"Line {line_no}: {ve}")
            continue

        if line in existing_lines:
            skipped += 1
            continue

        cur.execute("SAVEPOINT row_sp;")
        try:
            cur.execute(
                """
                INSERT INTO messages (message_date, channel, sender, message_text, original_line)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (original_line) DO NOTHING;
                """,
                (msg_dt, info["channel"], info["identity"], info["body"], line),
            )
            existing_lines.add(line)
            inserted += 1
            cur.execute("RELEASE SAVEPOINT row_sp;")
        except Exception as exc:
            cur.execute("ROLLBACK TO SAVEPOINT row_sp;")
            errors.append(f"Line {line_no}: {exc}")

    return UploadResult(
        file_type="messages",
        filename=filename,
        rows_processed=len(raw_lines),
        rows_inserted=inserted,
        rows_updated=updated,
        rows_skipped=skipped,
        warnings=warnings,
        errors=errors,
        message=_format_summary_msg("Messages", inserted, updated, skipped, errors),
    )


def _ingest_team(cur, filename: str, text: str) -> UploadResult:
    rdr = csv.DictReader(io.StringIO(text))
    hdr_err = _check_headers(rdr.fieldnames, {"name", "role", "joined", "pay"}, filename)
    if hdr_err:
        return hdr_err

    cur.execute("SELECT name, role, joined, pay FROM team_members;")
    existing = {r["name"]: r for r in cur.fetchall()}

    rows = list(rdr)
    inserted = updated = skipped = 0
    errors: List[str] = []
    seen_names: Set[str] = set()

    for idx, r in enumerate(rows, start=2):
        nm = (r.get("name") or "").strip()
        if not nm:
            errors.append(f"Row {idx}: missing team member name.")
            continue
        if nm in seen_names:
            errors.append(f"Row {idx}: duplicate team member '{nm}' within '{filename}'.")
            continue
        seen_names.add(nm)

        try:
            joined_d = parse_explicit_date(r.get("joined"), "%Y-%m-%d")
            pay_raw = (r.get("pay") or "").strip()
            pay_val: Optional[Decimal] = None
            if pay_raw:
                m = re.search(r"\$?([0-9]+(?:\.[0-9]+)?)", pay_raw)
                if not m:
                    raise ValueError(f"Invalid pay format '{pay_raw}'")
                pay_val = Decimal(m.group(1)).quantize(Decimal("0.01"))
        except ValueError as ve:
            errors.append(f"Row {idx} ({nm}): {ve}")
            continue

        role = r.get("role") or ""
        if nm in existing:
            ex = existing[nm]
            ex_pay = Decimal(str(ex["pay"])).quantize(Decimal("0.01")) if ex["pay"] is not None else None
            if (ex["role"] or "") == role and ex["joined"] == joined_d and ex_pay == pay_val:
                skipped += 1
            else:
                cur.execute(
                    "UPDATE team_members SET role=%s, joined=%s, pay=%s WHERE name=%s;",
                    (role, joined_d, pay_val, nm),
                )
                updated += 1
        else:
            cur.execute(
                "INSERT INTO team_members (name, role, joined, pay) VALUES (%s, %s, %s, %s);",
                (nm, role, joined_d, pay_val),
            )
            inserted += 1

    return UploadResult(
        file_type="team",
        filename=filename,
        rows_processed=len(rows),
        rows_inserted=inserted,
        rows_updated=updated,
        rows_skipped=skipped,
        errors=errors,
        message=_format_summary_msg("Team", inserted, updated, skipped, errors),
    )


def _ingest_costs(cur, filename: str, text: str) -> UploadResult:
    rdr = csv.DictReader(io.StringIO(text))
    hdr_err = _check_headers(rdr.fieldnames, {"item", "cost", "note"}, filename)
    if hdr_err:
        return hdr_err

    cur.execute("SELECT id, rule_name, value, unit, notes FROM cost_rules ORDER BY id ASC;")
    existing: Dict[str, Dict[str, Any]] = {}
    for r in cur.fetchall():
        if r["rule_name"] not in existing:
            existing[r["rule_name"]] = r

    rows = list(rdr)
    inserted = updated = skipped = 0
    errors: List[str] = []
    seen_items: Set[str] = set()

    for idx, r in enumerate(rows, start=2):
        item_name = (r.get("item") or "").strip()
        if not item_name:
            errors.append(f"Row {idx}: missing cost item name.")
            continue
        if item_name in seen_items:
            errors.append(f"Row {idx}: duplicate cost item '{item_name}' within '{filename}'.")
            continue
        seen_items.add(item_name)

        cost_raw = (r.get("cost") or "").strip()
        cost_val: Optional[Decimal] = None
        unit_str: Optional[str] = None
        if "$" in cost_raw or re.search(r"\b\d+(?:\.\d+)?\b", cost_raw):
            m = re.search(r"\$([0-9]+(?:\.[0-9]+)?)", cost_raw)
            if m:
                cost_val = Decimal(m.group(1)).quantize(Decimal("0.01"))
            if "hour" in cost_raw.lower():
                unit_str = "hour"

        note = r.get("note") or ""
        if item_name in existing:
            ex = existing[item_name]
            ex_val = Decimal(str(ex["value"])).quantize(Decimal("0.01")) if ex["value"] is not None else None
            if ex_val == cost_val and (ex["unit"] or None) == unit_str and (ex["notes"] or "") == note:
                skipped += 1
            else:
                cur.execute(
                    "UPDATE cost_rules SET value=%s, unit=%s, notes=%s WHERE id=%s;",
                    (cost_val, unit_str, note, ex["id"]),
                )
                updated += 1
        else:
            cur.execute(
                "INSERT INTO cost_rules (rule_name, value, unit, notes) VALUES (%s, %s, %s, %s);",
                (item_name, cost_val, unit_str, note),
            )
            inserted += 1

    return UploadResult(
        file_type="costs",
        filename=filename,
        rows_processed=len(rows),
        rows_inserted=inserted,
        rows_updated=updated,
        rows_skipped=skipped,
        errors=errors,
        message=_format_summary_msg("Cost rules", inserted, updated, skipped, errors),
    )
