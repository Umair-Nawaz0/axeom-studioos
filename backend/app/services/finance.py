import json
import re
from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional, Set, Tuple

from ..config import settings
from .date_service import get_active_reference_date
from ..models import (
    BillingToolError,
    FinanceReconciliationResponse,
    NeverBilledItem,
    OverdueInvoice,
    WeOweItem,
)

MONTH_NAME_TO_INT = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}


def get_finance_reconciliation(cur, ref_date: Optional[date] = None) -> FinanceReconciliationResponse:
    """
    100% dynamic financial reconciliation engine.
    Derives source-status overdue invoices, reconciled receivables, exact & candidate
    payment allocations, duplicate overpayments, paid-without-bank-deposit discrepancies,
    paid-cancelled shoot obligations, and unbilled completed shoots without hardcoded IDs.
    """
    if ref_date is None:
        ref_date = get_active_reference_date()

    cur.execute(
        """
        SELECT id, canonical_name, aliases, notes
        FROM clients;
        """
    )
    client_rows = cur.fetchall()

    alias_to_client_id: Dict[str, str] = {}
    client_by_id: Dict[str, Dict[str, Any]] = {}
    for c in client_rows:
        cid = str(c["id"])
        meta: Dict[str, Any] = {}
        if (c.get("notes") or "").startswith("{"):
            try:
                meta = json.loads(c["notes"])
            except Exception:
                meta = {}
        c_obj = {
            "id": cid,
            "canonical_name": c["canonical_name"],
            "entity_type": meta.get("entity_type", "client"),
            "pays_for": meta.get("pays_for", []),
            "billed_via_payer": meta.get("billed_via_payer"),
        }
        client_by_id[cid] = c_obj
        alias_to_client_id[c["canonical_name"].strip().lower()] = cid
        for a in c.get("aliases") or []:
            if isinstance(a, str) and a.strip():
                alias_to_client_id[a.strip().lower()] = cid

    cur.execute(
        """
        SELECT i.invoice_no, i.client_id, i.bill_to, i.email, i.issued, i.due,
               i.amount, i.status AS tool_status, i.memo,
               c.canonical_name AS client_name
        FROM invoices i
        LEFT JOIN clients c ON i.client_id = c.id
        ORDER BY i.issued ASC, i.invoice_no ASC;
        """
    )
    invoices = cur.fetchall()

    cur.execute(
        """
        SELECT p.payment_id, p.payment_date, p.payer, p.payer_email,
               p.amount, p.method, p.reference, p.matched_invoice_no
        FROM payments p
        ORDER BY p.payment_date ASC, p.payment_id ASC;
        """
    )
    payments = cur.fetchall()

    cur.execute(
        """
        SELECT b.booking_id, b.client_id, b.date, b.client_name, b.email,
               b.service, b.status, b.price,
               c.canonical_name
        FROM bookings b
        LEFT JOIN clients c ON b.client_id = c.id
        ORDER BY b.date ASC, b.booking_id ASC;
        """
    )
    bookings = cur.fetchall()

    cur.execute(
        """
        SELECT m.client_id, m.message_date, m.message_text, c.canonical_name
        FROM messages m
        LEFT JOIN clients c ON m.client_id = c.id
        ORDER BY m.message_date ASC;
        """
    )
    messages = cur.fetchall()

    # Map each payment to a canonical client_id and explicit invoice reference if present
    inv_by_no: Dict[str, Dict[str, Any]] = {i["invoice_no"]: i for i in invoices}
    direct_payments_by_inv: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    unreferenced_payments_by_client: Dict[Optional[str], List[Dict[str, Any]]] = defaultdict(list)
    payments_by_client: Dict[Optional[str], List[Dict[str, Any]]] = defaultdict(list)

    total_collected_in_bank = Decimal("0.00")
    method_counts: Counter = Counter()
    method_totals: Dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
    exact_ref_count = 0
    narrative_ref_count = 0
    blank_ref_count = 0

    for p in payments:
        amt = Decimal(str(p["amount"])).quantize(Decimal("0.01"))
        total_collected_in_bank += amt
        meth = (p.get("method") or "Unknown").strip()
        method_counts[meth] += 1
        method_totals[meth] += amt

        ref = (p.get("reference") or "").strip()
        matched_inv = p.get("matched_invoice_no")
        if not matched_inv and ref:
            m_inv = re.search(r"\b(INV-\d+)\b", ref, re.IGNORECASE)
            if m_inv and m_inv.group(1).upper() in inv_by_no:
                matched_inv = m_inv.group(1).upper()

        cid = None
        if matched_inv and matched_inv in inv_by_no and inv_by_no[matched_inv].get("client_id"):
            cid = str(inv_by_no[matched_inv]["client_id"])
        if not cid:
            em = (p.get("payer_email") or "").strip().lower()
            py = (p.get("payer") or "").strip().lower()
            cid = alias_to_client_id.get(em) or alias_to_client_id.get(py)

        p["_client_id"] = cid
        p["_client_name"] = client_by_id[cid]["canonical_name"] if cid and cid in client_by_id else (p.get("payer") or "Unknown")
        p["_matched_inv"] = matched_inv
        p["_ref_type"] = "exact_invoice" if matched_inv else ("narrative" if ref else "blank")
        p["_allocated_invoices"] = [matched_inv] if matched_inv else []
        p["_allocation_note"] = f"Exact reference to {matched_inv}" if matched_inv else ""

        if matched_inv:
            exact_ref_count += 1
            direct_payments_by_inv[matched_inv].append(p)
        else:
            if ref:
                narrative_ref_count += 1
            else:
                blank_ref_count += 1
            unreferenced_payments_by_client[cid].append(p)
        payments_by_client[cid].append(p)

    # 1. Detect narrative & blank-reference payment allocations per client
    candidate_allocations: List[Dict[str, Any]] = []
    candidate_paid_by_inv: Dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
    candidate_note_by_inv: Dict[str, str] = {}
    billing_tool_is_wrong: List[BillingToolError] = []
    we_owe: List[WeOweItem] = []

    invs_by_client: Dict[Optional[str], List[Dict[str, Any]]] = defaultdict(list)
    for inv in invoices:
        cid = str(inv["client_id"]) if inv.get("client_id") else None
        invs_by_client[cid].append(inv)

    # First handle exact-reference conflicts (unpaid-but-paid, or duplicate payment)
    for inv_no, p_list in direct_payments_by_inv.items():
        inv = inv_by_no.get(inv_no)
        if not inv:
            continue
        inv_amt = Decimal(str(inv["amount"])).quantize(Decimal("0.01"))
        paid_sum = sum((Decimal(str(p["amount"])) for p in p_list), Decimal("0.00")).quantize(Decimal("0.01"))
        status_low = (inv.get("tool_status") or "").lower()
        cname = inv.get("client_name") or inv.get("bill_to") or "Unknown"

        if status_low == "unpaid" and paid_sum >= inv_amt:
            p_desc = ", ".join(f"{p['payment_id']} (${p['amount']} on {p['payment_date']})" for p in p_list)
            billing_tool_is_wrong.append(
                BillingToolError(
                    invoice=inv_no,
                    tool_says="unpaid",
                    truth="paid",
                    how_you_know=f"Payment {p_desc} from {cname} explicitly references {inv_no} in payments.csv.",
                    confidence="confirmed",
                )
            )

        if paid_sum > inv_amt:
            overpay_amt = (paid_sum - inv_amt).quantize(Decimal("0.01"))
            p_desc = " and ".join(
                f"{p['payment_id']} (${p['amount']} on {p['payment_date']})" for p in p_list
            )
            we_owe.append(
                WeOweItem(
                    client=cname,
                    amount=overpay_amt,
                    why=f"Duplicate payment on {inv_no} (${inv_amt}): {cname} paid via {p_desc} (total ${paid_sum}, excess ${overpay_amt}).",
                    obligation_type="overpayment_credit_or_refund_review",
                    status="unresolved_owner_decision",
                )
            )
            for idx_p, p in enumerate(p_list):
                if idx_p > 0:
                    p["_allocation_note"] = f"Duplicate payment on {inv_no} — ${overpay_amt} excess credit/refund review"

    # Next resolve narrative and blank-reference payments per client
    matched_paid_invoices: Set[str] = set(direct_payments_by_inv.keys())

    for cid, p_list in unreferenced_payments_by_client.items():
        c_invs = [i for i in invs_by_client.get(cid, []) if (i.get("tool_status") or "").lower() != "void"]
        cname = client_by_id[cid]["canonical_name"] if cid and cid in client_by_id else "Unknown"

        # Pass 1: Narrative references (e.g. "july sessions", "half now half later", or monthly agency "June"/"July"/"Aug"/"Sept")
        for p in p_list:
            ref = (p.get("reference") or "").strip()
            if not ref:
                continue
            ref_low = ref.lower()
            p_amt = Decimal(str(p["amount"])).quantize(Decimal("0.01"))

            # Check if narrative mentions a month name
            mentioned_month = None
            for m_tok, m_num in MONTH_NAME_TO_INT.items():
                if re.search(rf"\b{m_tok}\b", ref_low):
                    mentioned_month = m_num
                    break

            if mentioned_month is not None:
                # 1a. Check if unpaid invoices in that month sum to p_amt
                unpaid_month_invs = [
                    i
                    for i in c_invs
                    if (i.get("tool_status") or "").lower() == "unpaid"
                    and i["issued"].month == mentioned_month
                    and i["invoice_no"] not in candidate_paid_by_inv
                ]
                unpaid_sum = sum((Decimal(str(i["amount"])) for i in unpaid_month_invs), Decimal("0.00"))
                if unpaid_month_invs and unpaid_sum == p_amt:
                    inv_nos = [i["invoice_no"] for i in unpaid_month_invs]
                    p["_allocated_invoices"] = inv_nos
                    p["_allocation_note"] = f"Candidate batch allocation across {', '.join(inv_nos)} ({ref})"
                    candidate_allocations.append(
                        {
                            "payment_id": p["payment_id"],
                            "payment_date": str(p["payment_date"]),
                            "client": cname,
                            "amount": float(p_amt),
                            "reference": ref,
                            "candidate_invoices": inv_nos,
                            "allocation_type": "lump_sum_unpaid_batch",
                            "confidence": "candidate_pending_confirmation",
                            "why": (
                                f"Payment {p['payment_id']} (${p_amt} on {p['payment_date']}) references '{ref}', "
                                f"matching {len(inv_nos)} open invoices ({', '.join(inv_nos)}) totaling ${unpaid_sum}."
                            ),
                        }
                    )
                    for i in unpaid_month_invs:
                        ino = i["invoice_no"]
                        iamt = Decimal(str(i["amount"])).quantize(Decimal("0.01"))
                        candidate_paid_by_inv[ino] = iamt
                        candidate_note_by_inv[ino] = (
                            f"Candidate match: {p['payment_id']} (${p_amt} on {p['payment_date']}, ref '{ref}')"
                        )
                        billing_tool_is_wrong.append(
                            BillingToolError(
                                invoice=ino,
                                tool_says="unpaid",
                                truth="paid (candidate batch match)",
                                how_you_know=(
                                    f"Matches {cname}'s ${p_amt} lump-sum payment {p['payment_id']} on {p['payment_date']} "
                                    f"referencing '{ref}' across {', '.join(inv_nos)}."
                                ),
                                confidence="candidate_pending_confirmation",
                            )
                        )
                    continue

                # 1b. Check if paid invoices in that month (or billed for that month's shoots) sum to p_amt
                paid_month_invs = [
                    i
                    for i in c_invs
                    if (i.get("tool_status") or "").lower() == "paid"
                    and i["invoice_no"] not in matched_paid_invoices
                    and (
                        i["issued"].month == mentioned_month
                        or re.search(rf"\b0?{mentioned_month}/\d{{1,2}}\b", i.get("memo") or "")
                        or (i["issued"].month == mentioned_month + 1 and i["issued"].day <= 5)
                    )
                ]
                # Find subset of paid_month_invs summing to p_amt
                selected_paid: List[Dict[str, Any]] = []
                running = Decimal("0.00")
                for i in paid_month_invs:
                    iamt = Decimal(str(i["amount"])).quantize(Decimal("0.01"))
                    if running + iamt <= p_amt:
                        selected_paid.append(i)
                        running += iamt
                if running == p_amt and selected_paid:
                    inv_nos = [i["invoice_no"] for i in selected_paid]
                    for ino in inv_nos:
                        matched_paid_invoices.add(ino)
                    p["_allocated_invoices"] = inv_nos
                    p["_allocation_note"] = f"Monthly agency payment covering {', '.join(inv_nos)}"
                    candidate_allocations.append(
                        {
                            "payment_id": p["payment_id"],
                            "payment_date": str(p["payment_date"]),
                            "client": cname,
                            "amount": float(p_amt),
                            "reference": ref,
                            "candidate_invoices": inv_nos,
                            "allocation_type": "third_party_monthly_batch",
                            "confidence": "confirmed_paid_batch",
                            "why": (
                                f"Agency payment {p['payment_id']} (${p_amt} on {p['payment_date']}, ref '{ref}') "
                                f"covers {len(inv_nos)} paid invoices ({', '.join(inv_nos)})."
                            ),
                        }
                    )
                    continue

            # 1c. Partial payment reference (e.g. "half now half later" matching status='partial' or open invoice)
            partial_invs = [
                i
                for i in c_invs
                if (i.get("tool_status") or "").lower() == "partial"
                or (
                    (i.get("tool_status") or "").lower() == "unpaid"
                    and "half" in ref_low
                    and Decimal(str(i["amount"])) == p_amt * 2
                )
            ]
            partial_invs.sort(key=lambda x: (0 if (x.get("tool_status") or "").lower() == "partial" else 1, x["issued"]))
            if partial_invs:
                target_inv = partial_invs[0]
                ino = target_inv["invoice_no"]
                iamt = Decimal(str(target_inv["amount"])).quantize(Decimal("0.01"))
                candidate_paid_by_inv[ino] += p_amt
                candidate_note_by_inv[ino] = (
                    f"Partial payment {p['payment_id']} (${p_amt} on {p['payment_date']}, ref '{ref}'); "
                    f"${(iamt - p_amt):.2f} remaining"
                )
                p["_allocated_invoices"] = [ino]
                p["_allocation_note"] = f"Partial payment (50%) on {ino}; ${(iamt - p_amt):.2f} still owed"
                candidate_allocations.append(
                    {
                        "payment_id": p["payment_id"],
                        "payment_date": str(p["payment_date"]),
                        "client": cname,
                        "amount": float(p_amt),
                        "reference": ref,
                        "candidate_invoices": [ino],
                        "allocation_type": "partial_payment",
                        "confidence": "candidate_pending_confirmation",
                        "why": (
                            f"Payment {p['payment_id']} (${p_amt} on {p['payment_date']}, ref '{ref}') "
                            f"is a 50% partial payment against {ino} (${iamt} face amount, leaving ${(iamt - p_amt):.2f})."
                        ),
                    }
                )

        # Pass 2: Match blank-reference payments to the client's closest preceding unreferenced 'paid' invoice of equal amount
        for p in p_list:
            if p["_allocated_invoices"]:
                continue
            p_amt = Decimal(str(p["amount"])).quantize(Decimal("0.01"))
            p_date = p["payment_date"]
            unmatched_paid = [
                i
                for i in c_invs
                if (i.get("tool_status") or "").lower() == "paid"
                and i["invoice_no"] not in matched_paid_invoices
                and Decimal(str(i["amount"])).quantize(Decimal("0.01")) == p_amt
            ]
            if unmatched_paid:
                # Prefer invoice issued on or shortly before payment_date
                prior = [i for i in unmatched_paid if i["issued"] <= p_date]
                chosen = (
                    min(prior, key=lambda x: abs((p_date - x["issued"]).days))
                    if prior
                    else min(unmatched_paid, key=lambda x: abs((p_date - x["issued"]).days))
                )
                ino = chosen["invoice_no"]
                matched_paid_invoices.add(ino)
                p["_allocated_invoices"] = [ino]
                p["_allocation_note"] = f"Matched by client + amount (${p_amt}) + date proximity to paid {ino}"

    # 2. Detect 'paid' invoices that have NO bank payment in payments.csv
    paid_without_bank_invs: Set[str] = set()
    for cid, c_invs in invs_by_client.items():
        paid_invs = [i for i in c_invs if (i.get("tool_status") or "").lower() == "paid"]
        paid_sum = sum((Decimal(str(i["amount"])) for i in paid_invs), Decimal("0.00"))
        bank_sum = sum((Decimal(str(p["amount"])) for p in payments_by_client.get(cid, [])), Decimal("0.00"))
        if paid_sum > bank_sum:
            cname = client_by_id[cid]["canonical_name"] if cid and cid in client_by_id else "Unknown"
            p_ids = [p["payment_id"] for p in payments_by_client.get(cid, [])]
            for i in paid_invs:
                ino = i["invoice_no"]
                if ino not in matched_paid_invoices:
                    paid_without_bank_invs.add(ino)
                    billing_tool_is_wrong.append(
                        BillingToolError(
                            invoice=ino,
                            tool_says="paid",
                            truth="unpaid (no bank deposit)",
                            how_you_know=(
                                f"Marked 'paid' in invoices.csv (${i['amount']}), but no bank deposit exists in payments.csv. "
                                f"{cname} has ${paid_sum} in 'paid' invoices vs only ${bank_sum} in bank payments "
                                f"({', '.join(p_ids) if p_ids else 'none'})."
                            ),
                            confidence="confirmed",
                        )
                    )

    # Also surface void duplicate invoices in billing_tool_is_wrong / audit notes if present
    for inv in invoices:
        if (inv.get("tool_status") or "").lower() == "void":
            memo = (inv.get("memo") or "").strip()
            dup_of = [
                other["invoice_no"]
                for other in invoices
                if other["invoice_no"] != inv["invoice_no"]
                and other.get("client_id") == inv.get("client_id")
                and (other.get("memo") or "").strip() == memo
                and memo
            ]
            if dup_of:
                billing_tool_is_wrong.append(
                    BillingToolError(
                        invoice=inv["invoice_no"],
                        tool_says="void",
                        truth=f"void duplicate of {', '.join(dup_of)}",
                        how_you_know=(
                            f"{inv['invoice_no']} (${inv['amount']}) duplicates {', '.join(dup_of)} on '{memo}' "
                            f"and is excluded from non-void revenue and receivables."
                        ),
                        confidence="confirmed",
                    )
                )

    # 3. Compute Invoice Totals, Source-Status Overdue, and Reconciled Overdue
    gross_invoiced_including_void = Decimal("0.00")
    void_invoices_total = Decimal("0.00")
    total_invoiced = Decimal("0.00")
    source_open_receivables = Decimal("0.00")
    true_unpaid_receivables = Decimal("0.00")

    source_overdue_invoices: List[OverdueInvoice] = []
    overdue_invoices: List[OverdueInvoice] = []
    invoices_ledger: List[Dict[str, Any]] = []

    for inv in invoices:
        no = inv["invoice_no"]
        amt = Decimal(str(inv["amount"])).quantize(Decimal("0.01"))
        due_d: date = inv["due"]
        issued_d: date = inv["issued"]
        tool_status = (inv.get("tool_status") or "").strip().lower()
        cname = inv.get("client_name") or inv.get("bill_to") or "Unknown"

        gross_invoiced_including_void += amt
        if tool_status == "void":
            void_invoices_total += amt
            invoices_ledger.append(
                {
                    "invoice_no": no,
                    "client": cname,
                    "bill_to": inv.get("bill_to"),
                    "issued": str(issued_d),
                    "due": str(due_d),
                    "amount": float(amt),
                    "source_status": tool_status,
                    "reconciled_status": "void",
                    "amount_owed": 0.0,
                    "is_source_overdue": False,
                    "is_reconciled_overdue": False,
                    "days_late": 0,
                    "memo": inv.get("memo") or "",
                    "payment_evidence": "Void duplicate invoice (excluded from active revenue)",
                }
            )
            continue

        total_invoiced += amt
        days_late = max(0, (ref_date - due_d).days)
        is_past_due = due_d < ref_date  # Strictly due < reference_date (due == reference_date is due today, not overdue)

        direct_p_list = direct_payments_by_inv.get(no, [])
        direct_paid = sum((Decimal(str(p["amount"])) for p in direct_p_list), Decimal("0.00")).quantize(Decimal("0.01"))
        cand_paid = candidate_paid_by_inv.get(no, Decimal("0.00")).quantize(Decimal("0.01"))

        payment_ev = ""
        if direct_p_list:
            payment_ev = ", ".join(f"{p['payment_id']} (${p['amount']} on {p['payment_date']})" for p in direct_p_list)
        elif no in candidate_note_by_inv:
            payment_ev = candidate_note_by_inv[no]
        elif no in paid_without_bank_invs:
            payment_ev = "Discrepancy: Marked paid in tool, but $0.00 found in bank payments"

        # Pre-reconciliation source-status open & overdue (strictly status in ('unpaid', 'partial') and due < ref_date)
        if tool_status in ("unpaid", "partial"):
            source_open_receivables += amt
            if is_past_due:
                rec_state = "open_overdue"
                if direct_paid >= amt:
                    rec_state = "paid_in_bank_conflict"
                elif cand_paid >= amt:
                    rec_state = "candidate_batch_paid"
                elif cand_paid > Decimal("0.00"):
                    rec_state = "partial_paid_candidate"
                source_overdue_invoices.append(
                    OverdueInvoice(
                        client=cname,
                        invoice=no,
                        amount_owed=amt,
                        face_amount=amt,
                        source_status=tool_status,
                        reconciliation_status=rec_state,
                        payment_evidence=payment_ev or None,
                        days_late=days_late,
                        due_date=due_d,
                    )
                )

        # Reconciled ground-truth balance
        if no in paid_without_bank_invs:
            true_paid = Decimal("0.00")
            reconciled_status = "unpaid_discrepancy"
        elif direct_paid >= amt:
            true_paid = amt  # Cap at face amount so overpayments never create negative invoice balance
            reconciled_status = "paid" if tool_status == "paid" else "paid_in_bank"
        elif cand_paid >= amt:
            true_paid = amt
            reconciled_status = "paid_candidate_batch"
        elif cand_paid > Decimal("0.00"):
            true_paid = cand_paid
            reconciled_status = "partial_paid"
        elif tool_status == "paid":
            true_paid = amt
            reconciled_status = "paid"
        else:
            true_paid = Decimal("0.00")
            reconciled_status = "overdue" if is_past_due else ("due_today" if due_d == ref_date else "open_not_due")

        balance = (amt - true_paid).quantize(Decimal("0.01"))
        if balance > Decimal("0.00"):
            true_unpaid_receivables += balance
            if is_past_due:
                overdue_invoices.append(
                    OverdueInvoice(
                        client=cname,
                        invoice=no,
                        amount_owed=balance,
                        face_amount=amt,
                        source_status=tool_status,
                        reconciliation_status=reconciled_status,
                        payment_evidence=payment_ev or None,
                        days_late=days_late,
                        due_date=due_d,
                    )
                )

        invoices_ledger.append(
            {
                "invoice_no": no,
                "client": cname,
                "bill_to": inv.get("bill_to"),
                "issued": str(issued_d),
                "due": str(due_d),
                "amount": float(amt),
                "source_status": tool_status,
                "reconciled_status": reconciled_status,
                "amount_owed": float(balance),
                "is_source_overdue": bool(tool_status in ("unpaid", "partial") and is_past_due),
                "is_reconciled_overdue": bool(balance > Decimal("0.00") and is_past_due),
                "days_late": days_late if is_past_due else 0,
                "memo": inv.get("memo") or "",
                "payment_evidence": payment_ev,
            }
        )

    source_overdue_invoices.sort(key=lambda x: (-x.days_late, x.invoice))
    overdue_invoices.sort(key=lambda x: (-x.days_late, x.invoice))
    source_overdue_total = sum((x.amount_owed for x in source_overdue_invoices), Decimal("0.00"))
    overdue_total = sum((x.amount_owed for x in overdue_invoices), Decimal("0.00"))

    # 4. Detect Paid-Cancelled Shoot Obligations & Unbilled Completed Bookings Dynamically
    bookings_by_client: Dict[Optional[str], List[Dict[str, Any]]] = defaultdict(list)
    for b in bookings:
        cid = str(b["client_id"]) if b.get("client_id") else None
        bookings_by_client[cid].append(b)

    retainer_covered_bookings_count = 0
    never_billed_items: List[NeverBilledItem] = []

    for cid, b_list in bookings_by_client.items():
        c_obj = client_by_id.get(cid or "", {})
        cname = c_obj.get("canonical_name") or (b_list[0].get("client_name") if b_list else "Unknown")
        billed_via = c_obj.get("billed_via_payer")
        c_invs = [i for i in invs_by_client.get(cid, []) if (i.get("tool_status") or "").lower() != "void"]

        # 4a. Check cancelled bookings that were invoiced and paid
        cancelled_bs = [b for b in b_list if (b.get("status") or "").lower() == "cancelled"]
        for cb in cancelled_bs:
            bid = cb["booking_id"]
            b_price = Decimal(str(cb["price"])).quantize(Decimal("0.01"))
            if b_price <= Decimal("0.00"):
                continue
            matching_paid_invs = [
                i
                for i in c_invs
                if re.search(rf"\b{re.escape(bid)}\b", i.get("memo") or "")
                and (i.get("tool_status") or "").lower() == "paid"
            ]
            if matching_paid_invs:
                p_inv = matching_paid_invs[0]
                ino = p_inv["invoice_no"]
                p_refs = direct_payments_by_inv.get(ino, [])
                p_str = (
                    f"paid via {p_refs[0]['payment_id']} on {p_refs[0]['payment_date']}"
                    if p_refs
                    else "marked paid"
                )
                # Check if client also messaged about cancelling after paying
                cancel_msgs = [
                    m
                    for m in messages
                    if str(m.get("client_id") or "") == str(cid or "")
                    and "cancel" in (m.get("message_text") or "").lower()
                ]
                msg_note = (
                    f" Client messaged on {cancel_msgs[0]['message_date'].strftime('%Y-%m-%d')}: "
                    f"\"{cancel_msgs[0]['message_text']}\""
                    if cancel_msgs
                    else ""
                )
                we_owe.append(
                    WeOweItem(
                        client=cname,
                        amount=b_price,
                        why=(
                            f"Cancelled booking {bid} ({cb['service']} on {cb['date']}) was billed on {ino} "
                            f"(${b_price}, {p_str}) and never credited against subsequent invoices.{msg_note}"
                        ),
                        obligation_type="paid_cancelled_service_credit",
                        status="unresolved_owner_decision",
                    )
                )

        # 4b. Check completed $0 Retainer Shoots covered by monthly retainer invoices
        comp_bs = [b for b in b_list if (b.get("status") or "").lower() == "completed"]
        for b in comp_bs:
            if Decimal(str(b["price"])) == Decimal("0.00") and "retainer" in (b.get("service") or "").lower():
                retainer_covered_bookings_count += 1

        # If client is billed via a third-party agency payer, check payer total separately
        if billed_via:
            continue

        priced_comp = [b for b in comp_bs if Decimal(str(b["price"])) > Decimal("0.00")]
        comp_sum = sum((Decimal(str(b["price"])) for b in priced_comp), Decimal("0.00")).quantize(Decimal("0.01"))
        inv_sum = sum((Decimal(str(i["amount"])) for i in c_invs), Decimal("0.00")).quantize(Decimal("0.01"))

        if comp_sum > inv_sum:
            shortfall = (comp_sum - inv_sum).quantize(Decimal("0.01"))
            # Match invoices to completed bookings by: (1) explicit Bxxx in memo, (2) M/D date in memo, (3) issued 0..7 days after booking
            unmatched_bs = list(priced_comp)
            unmatched_invs = list(c_invs)
            blank_memo_count = sum(1 for i in c_invs if not (i.get("memo") or "").strip())

            # Pass 1: Explicit booking_id in memo
            for i in list(unmatched_invs):
                memo = i.get("memo") or ""
                for b in list(unmatched_bs):
                    if re.search(rf"\b{re.escape(b['booking_id'])}\b", memo):
                        unmatched_bs.remove(b)
                        unmatched_invs.remove(i)
                        break

            # Pass 2: Explicit M/D date in memo
            for i in list(unmatched_invs):
                memo = i.get("memo") or ""
                for b in list(unmatched_bs):
                    b_dt: date = b["date"]
                    md_str = f"{b_dt.month}/{b_dt.day}"
                    md_pad = f"{b_dt.month:02d}/{b_dt.day:02d}"
                    if md_str in memo or md_pad in memo:
                        unmatched_bs.remove(b)
                        unmatched_invs.remove(i)
                        break

            # Pass 3: Same price and invoice issued 0..6 days after booking date
            for i in list(unmatched_invs):
                iamt = Decimal(str(i["amount"])).quantize(Decimal("0.01"))
                candidates = [
                    b
                    for b in unmatched_bs
                    if Decimal(str(b["price"])).quantize(Decimal("0.01")) == iamt
                    and 0 <= (i["issued"] - b["date"]).days <= 6
                ]
                if candidates:
                    best_b = min(candidates, key=lambda b: (i["issued"] - b["date"]).days)
                    unmatched_bs.remove(best_b)
                    unmatched_invs.remove(i)

            for b in unmatched_bs:
                b_amt = Decimal(str(b["price"])).quantize(Decimal("0.01"))
                is_ambiguous = blank_memo_count > 0 and len(priced_comp) > 5
                conf = "needs_billing_review" if is_ambiguous else "confirmed"
                why_text = (
                    f"{cname} has {len(priced_comp)} completed bookings (${comp_sum}) vs {len(c_invs)} invoices (${inv_sum}) — "
                    f"${shortfall} client shortfall. {b['booking_id']} ({b['service']} on {b['date']}) has no matching invoice"
                    + (
                        f" ({blank_memo_count} invoices for {cname} have blank memos; verify August billing window)."
                        if is_ambiguous
                        else "."
                    )
                )
                never_billed_items.append(
                    NeverBilledItem(
                        client=cname,
                        booking_id_or_month=b["booking_id"],
                        amount=b_amt,
                        confidence=conf,
                        service=b.get("service"),
                        booking_date=str(b["date"]),
                        why=why_text,
                    )
                )

    confirmed_never_billed = sum(
        (x.amount for x in never_billed_items if x.confidence == "confirmed"),
        Decimal("0.00"),
    )
    potential_unbilled_total = sum((x.amount for x in never_billed_items), Decimal("0.00"))

    payments_ledger = [
        {
            "payment_id": p["payment_id"],
            "payment_date": str(p["payment_date"]),
            "payer": p.get("payer") or "",
            "payer_email": p.get("payer_email") or "",
            "client": p.get("_client_name") or "",
            "amount": float(Decimal(str(p["amount"])).quantize(Decimal("0.01"))),
            "method": p.get("method") or "",
            "reference": p.get("reference") or "",
            "reference_type": p.get("_ref_type"),
            "allocated_invoices": p.get("_allocated_invoices") or [],
            "allocation_note": p.get("_allocation_note") or "",
        }
        for p in payments
    ]

    payment_summary = {
        "total_payments_count": len(payments),
        "total_payments_amount": float(total_collected_in_bank),
        "by_method_count": dict(method_counts),
        "by_method_amount": {k: float(v) for k, v in method_totals.items()},
        "exact_invoice_references": exact_ref_count,
        "narrative_references": narrative_ref_count,
        "blank_references": blank_ref_count,
    }

    return FinanceReconciliationResponse(
        reference_date=ref_date,
        total_invoiced=total_invoiced,
        gross_invoiced_including_void=gross_invoiced_including_void,
        void_invoices_total=void_invoices_total,
        total_collected_in_bank=total_collected_in_bank,
        source_open_receivables=source_open_receivables,
        source_overdue_total=source_overdue_total,
        source_overdue_count=len(source_overdue_invoices),
        true_unpaid_receivables=true_unpaid_receivables,
        overdue_total=overdue_total,
        overdue_invoices=overdue_invoices,
        source_overdue_invoices=source_overdue_invoices,
        we_owe=we_owe,
        never_billed_total=potential_unbilled_total,
        potential_unbilled_total=confirmed_never_billed,
        never_billed_items=never_billed_items,
        retainer_covered_bookings_count=retainer_covered_bookings_count,
        billing_tool_is_wrong=billing_tool_is_wrong,
        candidate_allocations=candidate_allocations,
        invoices_ledger=invoices_ledger,
        payments_ledger=payments_ledger,
        payment_summary=payment_summary,
    )
