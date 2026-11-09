"""
End-to-End QA, Data Verification, Incremental Upload, and Release Gate Test Suite
for Axeom StudioOS — Challenge Pack 213 (Reference Date: 2026-10-06).

Runs strictly against the isolated PostgreSQL schema `qa_test` (`DB_SCHEMA=qa_test`)
so the live `public` schema is never mutated by destructive, synthetic, partial,
or bad-upload tests.
"""

import os
import sys
import unittest
from decimal import Decimal
from unittest.mock import patch, MagicMock

# Force isolated QA schema before importing backend modules
os.environ["DB_SCHEMA"] = "qa_test"
os.environ["REFERENCE_DATE"] = "2026-10-06"

BACKEND_DIR = "/home/umair/Downloads/axeom_project/backend"
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from fastapi.testclient import TestClient

from app.main import app
from app.db import get_db
from app.services.ingestion import (
    process_uploaded_file,
    parse_explicit_date,
    parse_decimal_amount,
)
from app.services.identity import reconcile_all_entities
from app.services.finance import get_finance_reconciliation
from app.services.production import get_production_overview, get_lost_requests
from app.services.messages_service import analyze_messages
from app.services.leads import get_leads_overview
from app.services.marketing import get_marketing_analysis
from app.services.clients import (
    get_clients_list,
    get_most_likely_to_leave,
    get_identity_review_queue,
)
from app.services.dashboard import get_dashboard_summary
from app.services import jev

FIXTURES_DIR = "/home/umair/Downloads/axeom_project/tests/fixtures/pack_213/data"
PACK_FILES = [
    "leads.csv",
    "bookings.csv",
    "invoices.csv",
    "payments.csv",
    "production_board.csv",
    "messages.txt",
    "team.csv",
    "costs.csv",
]


def reset_all_tables(cur):
    """Truncate all 10 tables in the current schema."""
    cur.execute(
        """
        TRUNCATE TABLE
            cost_rules,
            team_members,
            messages,
            production_videos,
            payments,
            invoices,
            bookings,
            leads,
            clients
        RESTART IDENTITY CASCADE;
        """
    )


def load_pristine_pack213():
    """Reset `qa_test` schema and ingest all 8 pristine Pack 213 files."""
    with get_db(schema="qa_test") as cur:
        reset_all_tables(cur)
        results = []
        for rel_path in PACK_FILES:
            full_path = os.path.join(FIXTURES_DIR, rel_path)
            filename = os.path.basename(full_path)
            with open(full_path, "rb") as f:
                content = f.read()
            res = process_uploaded_file(cur, filename, content, run_reconcile=False)
            results.append(res)
        reconcile_all_entities(cur)
    return results


class TestPack213EndToEndQA(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        load_pristine_pack213()

    @classmethod
    def tearDownClass(cls):
        load_pristine_pack213()

    def test_01_phase1_explicit_parsers_and_row_counts(self):
        """Verify explicit date/currency parsers, exact row counts, and source ID uniqueness."""
        self.assertEqual(str(parse_explicit_date("2026-10-06", "%Y-%m-%d")), "2026-10-06")
        self.assertEqual(str(parse_explicit_date("10/06/2026", "%m/%d/%Y")), "2026-10-06")
        self.assertEqual(str(parse_explicit_date("06/10/2026", "%d/%m/%Y")), "2026-10-06")
        with self.assertRaises(ValueError):
            parse_explicit_date("2026-13-45", "%Y-%m-%d")

        self.assertEqual(parse_decimal_amount("$1,500.00"), Decimal("1500.00"))
        self.assertEqual(parse_decimal_amount("$0"), Decimal("0.00"))
        with self.assertRaises(ValueError):
            parse_decimal_amount("$12,O00")

        with get_db(schema="qa_test") as cur:
            expected_counts = {
                "leads": 99,
                "bookings": 177,
                "invoices": 158,
                "payments": 129,
                "production_videos": 352,
                "messages": 190,
                "team_members": 5,
                "cost_rules": 2,
            }
            for table, expected in expected_counts.items():
                cur.execute(f"SELECT COUNT(*) AS c FROM {table};")
                self.assertEqual(
                    cur.fetchone()["c"], expected, f"Expected {expected} in {table}"
                )

    def test_02_phase1_idempotent_reimport(self):
        """Re-importing all 8 unmodified Pack 213 files must insert 0, update 0, skip 1,112 rows."""
        with get_db(schema="qa_test") as cur:
            total_inserted = 0
            total_updated = 0
            total_skipped = 0
            for rel_path in PACK_FILES:
                full_path = os.path.join(FIXTURES_DIR, rel_path)
                filename = os.path.basename(full_path)
                with open(full_path, "rb") as f:
                    content = f.read()
                res = process_uploaded_file(cur, filename, content, run_reconcile=False)
                self.assertEqual(res.errors, [])
                total_inserted += res.rows_inserted
                total_updated += res.rows_updated
                total_skipped += res.rows_skipped

            self.assertEqual(total_inserted, 0)
            self.assertEqual(total_updated, 0)
            self.assertEqual(total_skipped, 1112)

    def test_03_phase2_identity_resolution_and_payer_separation(self):
        """Verify 30 canonical service clients + 1 third-party payer (Lumen Social) and alias rules."""
        with get_db(schema="qa_test") as cur:
            clients = get_clients_list(cur)
            service_clients = [c for c in clients if c.get("entity_type") == "client"]
            payers = [c for c in clients if c.get("entity_type") == "payer"]

            self.assertEqual(len(service_clients), 30)
            self.assertEqual(len(payers), 1)
            self.assertEqual(payers[0]["canonical_name"], "Lumen Social")
            self.assertEqual(
                set(payers[0]["pays_for"]),
                {"Ridgeway Pediatrics", "Northpoint Physical Therapy"},
            )

            names = {c["canonical_name"] for c in service_clients}
            self.assertIn("Juniper Family Therapy", names)
            self.assertNotIn("Price", names)
            self.assertIn("Mesquite Roofing Co", names)
            self.assertIn("Metroplex Makers Podcast", names)
            self.assertIn("Daniels Auto Detailing", names)
            self.assertIn("Kim's Auto Spa", names)
            self.assertIn("Stone Bridge Realty", names)
            self.assertIn("Stonebridge Realty Group", names)
            self.assertIn("Bloom Athletics", names)
            self.assertIn("Keystone Chiropractic", names)

            cur.execute(
                """
                SELECT v.video_id, c.canonical_name
                FROM production_videos v
                JOIN clients c ON v.client_id = c.id
                WHERE v.video_id IN ('V020', 'V179', 'V223');
                """
            )
            vid_map = {r["video_id"]: r["canonical_name"] for r in cur.fetchall()}
            self.assertEqual(vid_map["V020"], "Magnolia Bridal Boutique")
            self.assertEqual(vid_map["V179"], "Stone Bridge Realty")
            self.assertEqual(vid_map["V223"], "Stonebridge Realty Group")

            review = get_identity_review_queue(cur)
            self.assertEqual(len(review["unlinked_records"]["bookings"]), 0)
            self.assertEqual(len(review["unlinked_records"]["invoices"]), 0)
            self.assertEqual(len(review["unlinked_records"]["production_videos"]), 0)
            self.assertEqual(len(review["unlinked_records"]["messages"]), 0)
            self.assertEqual(review["quarantined_spam_count"], 5)

    def test_04_phase3_financial_reconciliation_and_exceptions(self):
        """Verify exact Pack 213 financial totals, strict overdue cutoff, and payment exceptions."""
        with get_db(schema="qa_test") as cur:
            fin = get_finance_reconciliation(cur).model_dump()

            self.assertEqual(str(fin["reference_date"]), "2026-10-06")
            self.assertEqual(str(fin["gross_invoiced_including_void"]), "159895.00")
            self.assertEqual(str(fin["void_invoices_total"]), "1500.00")
            self.assertEqual(str(fin["total_invoiced"]), "158395.00")
            self.assertEqual(str(fin["total_collected_in_bank"]), "132230.00")
            self.assertEqual(str(fin["source_open_receivables"]), "29615.00")
            self.assertEqual(str(fin["true_unpaid_receivables"]), "27065.00")

            self.assertEqual(fin["source_overdue_count"], 13)
            self.assertEqual(str(fin["source_overdue_total"]), "12055.00")
            self.assertEqual(len(fin["overdue_invoices"]), 8)
            self.assertEqual(str(fin["overdue_total"]), "9505.00")

            source_overdue_ids = {inv["invoice"] for inv in fin["source_overdue_invoices"]}
            reconciled_overdue_ids = {inv["invoice"] for inv in fin["overdue_invoices"]}
            self.assertNotIn("INV-1141", source_overdue_ids)
            self.assertNotIn("INV-1141", reconciled_overdue_ids)

            self.assertIn("INV-1105", source_overdue_ids)
            self.assertIn("INV-1125", source_overdue_ids)
            self.assertNotIn("INV-1105", reconciled_overdue_ids)
            self.assertNotIn("INV-1125", reconciled_overdue_ids)

            inv_1122 = next(i for i in fin["overdue_invoices"] if i["invoice"] == "INV-1122")
            self.assertEqual(inv_1122["amount_owed"], 450.0)

            we_owe_map = {item["client"]: item["amount"] for item in fin["we_owe"]}
            self.assertEqual(we_owe_map["Magnolia Bridal Boutique"], 900.0)
            self.assertEqual(we_owe_map["Stone Bridge Realty"], 1500.0)

            self.assertEqual(str(fin["never_billed_total"]), "2655.00")
            self.assertEqual(fin["retainer_covered_bookings_count"], 19)
            nb_map = {i["booking_id_or_month"]: i for i in fin["never_billed_items"]}
            self.assertEqual(nb_map["B072"]["amount"], 1500.0)
            self.assertEqual(nb_map["B072"]["confidence"], "confirmed")
            self.assertEqual(nb_map["B135"]["amount"], 900.0)
            self.assertEqual(nb_map["B135"]["confidence"], "confirmed")
            self.assertEqual(nb_map["B095"]["amount"], 255.0)
            self.assertEqual(nb_map["B095"]["confidence"], "needs_billing_review")

    def test_05_phase4_production_voice_notes_privacy_and_costs(self):
        """Verify 352 videos, 39 unlogged voice notes, 6 privacy alerts (V223 unlogged), and costs."""
        with get_db(schema="qa_test") as cur:
            prod = get_production_overview(cur)
            lost = get_lost_requests(cur).model_dump()

            self.assertEqual(prod["total_videos"], 352)
            self.assertEqual(
                prod["stage_breakdown"],
                {
                    "Delivered": 322,
                    "In edit": 19,
                    "In review": 10,
                    "In revision": 1,
                },
            )
            self.assertEqual(len(prod["active_work_in_progress"]), 30)
            self.assertEqual(prod["missing_shoot_booking_count"], 91)

            self.assertEqual(prod["voice_note_summary"]["total_voice_notes"], 39)
            self.assertEqual(prod["voice_note_summary"]["logged_on_board"], 0)
            self.assertEqual(prod["voice_note_summary"]["unlogged_count"], 39)
            self.assertEqual(prod["voice_note_summary"]["escalated_to_complaints"], 22)
            self.assertEqual(len(lost["lost_requests"]), 39)
            self.assertEqual(lost["lost_requests_started_getting_worse_in"], "2026-06")
            self.assertIn("2026-06-01", " ".join(lost["lost_requests_root_causes"]))

            alerts = prod["privacy_alerts"]
            self.assertEqual(len(alerts), 6)
            logged_vids = {a["video_id"] for a in alerts if a["board_logged"]}
            unlogged_vids = {a["video_id"] for a in alerts if not a["board_logged"]}
            self.assertEqual(logged_vids, {"V020", "V062", "V075", "V135", "V170"})
            self.assertEqual(unlogged_vids, {"V223"})

            costs = prod["cost_summary"]
            self.assertEqual(costs["total_editor_hours"], 1578.5)
            self.assertEqual(costs["total_editor_labor_cost"], 46717.30)
            self.assertEqual(costs["completed_studio_hours"], 542.0)
            self.assertEqual(costs["completed_studio_cost"], 21680.00)
            self.assertEqual(costs["scheduled_studio_hours"], 64.0)
            self.assertEqual(costs["scheduled_studio_cost"], 2560.00)

    def test_06_phase5_leads_marketing_messages_and_churn(self):
        """Verify 99 leads, 20 unanswered triage (13/3/4), 190 messages, Referral channel, and churn."""
        with get_db(schema="qa_test") as cur:
            leads = get_leads_overview(cur)
            mkt = get_marketing_analysis(cur)
            msgs = analyze_messages(cur)
            churn = get_most_likely_to_leave(cur)

            self.assertEqual(leads["total_leads_count"], 99)
            self.assertEqual(leads["unanswered_leads_count"], 20)
            self.assertEqual(leads["legitimate_unanswered_count"], 13)
            self.assertEqual(leads["existing_client_unanswered_count"], 3)
            self.assertEqual(leads["junk_unanswered_count"], 4)
            self.assertTrue(
                any(
                    set(d["lead_ids"]) == {"L005", "L050"}
                    for d in leads["duplicate_enquiries"]
                )
            )

            self.assertEqual(mkt["best_marketing_channel"]["channel"], "Referral")
            self.assertEqual(
                mkt["best_marketing_channel"]["label"],
                "Best Observed Conversion (Ad Spend Unknown)",
            )

            self.assertEqual(msgs["total_messages"], 190)
            self.assertEqual(
                msgs["by_channel"],
                {
                    "Email": 72,
                    "WhatsApp": 72,
                    "Voice note": 39,
                    "Instagram DM": 5,
                    "Website form": 2,
                },
            )
            self.assertEqual(msgs["by_direction"], {"inbound": 187, "outbound": 3})
            self.assertEqual(len(msgs["quarantined_messages"]), 5)
            self.assertEqual(len(msgs["opportunities_and_referrals"]), 7)

            self.assertEqual(churn["client"], "Keystone Chiropractic")
            self.assertTrue(
                any(
                    "Becker Insurance Group" in p["client"]
                    for p in churn["already_paused_clients"]
                )
            )

    def test_07_phase6_jev_deferral_and_deterministic_rules(self):
        """Verify Jev API integration is cleanly deferred without fake benchmark metrics while deterministic rules work."""
        jev._CLASSIFICATION_CACHE.clear()

        res_priv = jev.classify_message(
            "Please blur the patient face in reel 2, no release signed."
        )
        self.assertEqual(res_priv["category"], "Privacy / No-Release Alert")
        self.assertEqual(res_priv["provider"], "deterministic_rules")

        res_comp = jev.classify_message(
            "This is the second time I ask. office tour is still wrong."
        )
        self.assertEqual(res_comp["category"], "Complaint / Revision Follow-up")
        self.assertEqual(res_comp["provider"], "deterministic_rules")

        bench = jev.evaluate_jev_benchmark()
        self.assertEqual(bench["status"], "deferred_no_api_key")
        self.assertEqual(bench["active_provider"], "deterministic_rules")
        self.assertIsNone(bench["accuracy_percentage"])
        self.assertEqual(bench["sample_size"], 0)

    def test_08_phase7_incremental_synthetic_upload_and_existing_row_update(self):
        """
        Verify that uploading synthetic `QA TEST ONLY` rows across all files and updating
        existing rows dynamically updates counts, financials, privacy alerts, and unknown senders.
        """
        with get_db(schema="qa_test") as cur:
            leads_csv = (
                "lead_id,created,name,business,email,phone,source,first_reply,status\n"
                "L9991,2026-10-05 10:00,QA Test Lead,QA Test Dental,qa.dental@example.com,555-9991,Referral,,new\n"
                "L9992,2026-10-06 11:00,QA Test Lead Dup,QA Test Dental,qa.dental@example.com,555-9991,Website,,new\n"
            ).encode("utf-8")
            r_leads = process_uploaded_file(cur, "leads.csv", leads_csv, run_reconcile=False)
            self.assertEqual(r_leads.rows_inserted, 2)

            bookings_csv = (
                "booking_id,date,client_name,email,service,status,price\n"
                "B9991,10/04/2026,Apex Med Spa,maya@apexmedspa.com,Reels Pack,completed,$900\n"
            ).encode("utf-8")
            r_book = process_uploaded_file(cur, "bookings.csv", bookings_csv, run_reconcile=False)
            self.assertEqual(r_book.rows_inserted, 1)

            invoices_csv = (
                "invoice_no,bill_to,email,issued,due,amount,status,memo\n"
                "INV-9991,Apex Med Spa,maya@apexmedspa.com,2026-10-04,2026-10-15,$900,paid,QA TEST ONLY\n"
                "INV-1140,Ironclad DFW,media@ironcladdfw.org,2026-09-21,2026-10-05,255.00,paid,QA TEST ONLY updated to paid\n"
            ).encode("utf-8")
            r_inv = process_uploaded_file(cur, "invoices.csv", invoices_csv, run_reconcile=False)
            self.assertEqual(r_inv.rows_inserted, 1)
            self.assertEqual(r_inv.rows_updated, 1)

            payments_csv = (
                "payment_id,date,payer,payer_email,amount,method,reference\n"
                "P9991,05/10/2026,Apex Med Spa,maya@apexmedspa.com,$900,card,INV-9991 QA TEST ONLY\n"
                "P9992,05/10/2026,Ironclad DFW,media@ironcladdfw.org,$255,ACH,INV-1140 QA TEST ONLY\n"
            ).encode("utf-8")
            r_pay = process_uploaded_file(cur, "payments.csv", payments_csv, run_reconcile=False)
            self.assertEqual(r_pay.rows_inserted, 2)

            videos_csv = (
                "video_id,client,title,editor,stage,notes_on_board,revisions,editor_hours,client_approved_on,shoot_booking\n"
                "V9991,Apex Med Spa,QA Test Reel,Nina,Delivered,,0,4.0,2026-10-05,B9991\n"
                "V351,Daniels Detailing,Interior deep clean,Theo,Delivered,QA TEST ONLY,1,7.0,2026-10-06,B159\n"
            ).encode("utf-8")
            r_vid = process_uploaded_file(
                cur, "production_board.csv", videos_csv, run_reconcile=False
            )
            self.assertEqual(r_vid.rows_inserted, 1)
            self.assertEqual(r_vid.rows_updated, 1)

            msgs_txt = (
                "[2026-10-05 14:20] VOICE NOTE from +1 214-555-0102 (Maya, 0:31): "
                "QA TEST ONLY: Please blur the face of the client in QA Test Reel, she didn't sign the release.\n"
                "[2026-10-05 15:00] EMAIL from mystery@unknownbiz.org: "
                "QA TEST ONLY: Hi, we'd love a quote for a 2-day brand shoot next month.\n"
            ).encode("utf-8")
            r_msg = process_uploaded_file(cur, "messages.txt", msgs_txt, run_reconcile=False)
            self.assertEqual(r_msg.rows_inserted, 2)

            reconcile_all_entities(cur)

            fin = get_finance_reconciliation(cur).model_dump()
            self.assertEqual(str(fin["total_invoiced"]), "159295.00")
            self.assertEqual(str(fin["total_collected_in_bank"]), "133385.00")
            self.assertEqual(len(fin["overdue_invoices"]), 7)
            self.assertEqual(str(fin["overdue_total"]), "9250.00")

            prod = get_production_overview(cur)
            self.assertEqual(prod["total_videos"], 353)
            self.assertEqual(len(prod["privacy_alerts"]), 7)

            leads = get_leads_overview(cur)
            self.assertEqual(leads["total_leads_count"], 101)
            self.assertEqual(leads["unanswered_leads_count"], 22)

            # Verify dry-run preview does not mutate database
            preview_csv = (
                "lead_id,created,name,business,email,phone,source,first_reply,status\n"
                "L9999,2026-10-06 12:00,Preview Only,Preview Co,preview@example.com,555-0000,Website,,new\n"
            ).encode("utf-8")
            r_prev = process_uploaded_file(cur, "leads.csv", preview_csv, run_reconcile=False, dry_run=True)
            self.assertEqual(r_prev.rows_inserted, 1)
            cur.execute("SELECT COUNT(*) AS c FROM leads WHERE lead_id = 'L9999';")
            self.assertEqual(cur.fetchone()["c"], 0)

            # Verify payment arriving BEFORE invoice and reconciling when invoice arrives later
            early_pay_csv = (
                "payment_id,date,payer,payer_email,amount,method,reference\n"
                "P9995,05/10/2026,Apex Med Spa,maya@apexmedspa.com,$600,card,INV-9995 QA TEST ONLY\n"
            ).encode("utf-8")
            r_ep = process_uploaded_file(cur, "payments.csv", early_pay_csv, run_reconcile=False)
            self.assertEqual(r_ep.rows_inserted, 1)
            self.assertGreater(len(r_ep.warnings), 0)

            later_inv_csv = (
                "invoice_no,bill_to,email,issued,due,amount,status,memo\n"
                "INV-9995,Apex Med Spa,maya@apexmedspa.com,2026-10-05,2026-10-15,$600,unpaid,QA TEST ONLY\n"
            ).encode("utf-8")
            r_li = process_uploaded_file(cur, "invoices.csv", later_inv_csv, run_reconcile=True)
            self.assertEqual(r_li.rows_inserted, 1)
            fin_after = get_finance_reconciliation(cur).model_dump()
            inv_9995 = next(i for i in fin_after["invoices_ledger"] if i["invoice_no"] == "INV-9995")
            self.assertEqual(inv_9995["reconciled_status"], "paid_in_bank")
            self.assertEqual(inv_9995["amount_owed"], 0.0)

        load_pristine_pack213()

    def test_09_phase7_partial_upload_and_bad_upload_rejection(self):
        """Verify partial single-file uploads do not crash and malformed uploads are rejected cleanly."""
        with get_db(schema="qa_test") as cur:
            reset_all_tables(cur)

            with open(os.path.join(FIXTURES_DIR, "payments.csv"), "rb") as f:
                res_pay = process_uploaded_file(cur, "payments.csv", f.read(), run_reconcile=True)
            self.assertEqual(res_pay.rows_inserted, 129)
            dash = get_dashboard_summary(cur).model_dump()
            self.assertTrue(dash["data_status"]["is_partial"])
            self.assertEqual(str(dash["overview"]["total_bank_collected"]), "132230.00")

            bad_headers = b"wrong_col1,wrong_col2\n1,2\n"
            r_bad_hdr = process_uploaded_file(cur, "invoices.csv", bad_headers, run_reconcile=False)
            self.assertEqual(r_bad_hdr.rows_inserted, 0)
            self.assertGreater(len(r_bad_hdr.errors), 0)

            bad_date = (
                b"invoice_no,bill_to,email,issued,due,amount,status,memo\n"
                b"INV-8881,Apex Med Spa,maya@apexmedspa.com,2026-13-45,2026-10-10,$900,unpaid,test\n"
            )
            r_bad_date = process_uploaded_file(cur, "invoices.csv", bad_date, run_reconcile=False)
            self.assertEqual(r_bad_date.rows_inserted, 0)
            self.assertTrue(any("date" in e.lower() for e in r_bad_date.errors))

            bad_curr = (
                b"invoice_no,bill_to,email,issued,due,amount,status,memo\n"
                b"INV-8882,Apex Med Spa,maya@apexmedspa.com,2026-10-01,2026-10-10,$12O00,unpaid,test\n"
            )
            r_bad_curr = process_uploaded_file(cur, "invoices.csv", bad_curr, run_reconcile=False)
            self.assertEqual(r_bad_curr.rows_inserted, 0)
            self.assertTrue(any("currency" in e.lower() for e in r_bad_curr.errors))

            dup_in_file = (
                b"invoice_no,bill_to,email,issued,due,amount,status,memo\n"
                b"INV-8883,Apex Med Spa,maya@apexmedspa.com,2026-10-01,2026-10-10,$900,unpaid,first\n"
                b"INV-8883,Apex Med Spa,maya@apexmedspa.com,2026-10-01,2026-10-10,$900,unpaid,dup\n"
            )
            r_dup = process_uploaded_file(cur, "invoices.csv", dup_in_file, run_reconcile=False)
            self.assertEqual(r_dup.rows_inserted, 1)
            self.assertTrue(any("duplicate" in e.lower() for e in r_dup.errors))

            r_exe = process_uploaded_file(cur, "malware.exe", b"MZ...", run_reconcile=False)
            self.assertEqual(r_exe.file_type, "unsupported")
            self.assertGreater(len(r_exe.errors), 0)

        load_pristine_pack213()

    def test_10_phase8_fastapi_endpoints_and_answers_export(self):
        """Verify all FastAPI endpoints return 200 OK and dynamic `/api/answers` matches Pack 213."""
        client = TestClient(app)

        for path in [
            "/api/health",
            "/api/dashboard/summary",
            "/api/clients",
            "/api/identity/review",
            "/api/finance/reconciliation",
            "/api/production/overview",
            "/api/production/lost-requests",
            "/api/messages",
            "/api/leads/overview",
            "/api/marketing/analysis",
            "/api/jev/benchmark",
            "/api/upload/history",
            "/api/search?q=Keystone",
            "/api/search?q=INV-1111",
            "/api/answers",
        ]:
            resp = client.get(path)
            self.assertEqual(resp.status_code, 200, f"GET {path} failed with {resp.status_code}")

        search_res = client.get("/api/search?q=INV-1111").json()
        self.assertTrue(any(r["id"] == "INV-1111" for r in search_res["results"]))

        ans = client.get("/api/answers").json()
        self.assertEqual(str(ans["pack_id"]), "213")
        self.assertEqual(ans["client_count"], 30)
        self.assertEqual(len(ans["payers_who_are_not_clients"]), 1)
        self.assertEqual(ans["overdue_total"], 9505.0)
        self.assertEqual(ans["source_overdue_total"], 12055.0)
        self.assertEqual(ans["never_billed_total"], 2655.0)
        self.assertEqual(len(ans["lost_requests"]), 39)
        self.assertEqual(ans["most_likely_to_leave"]["client"], "Keystone Chiropractic")
        self.assertEqual(ans["best_marketing_channel"]["channel"], "Referral")


if __name__ == "__main__":
    unittest.main(verbosity=2)
