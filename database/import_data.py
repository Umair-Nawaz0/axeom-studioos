import csv
import json
import os
import re
from datetime import datetime
import psycopg2
from psycopg2.extras import execute_values

DB_CONFIG = {
    'dbname': os.getenv('DB_NAME', 'axeom_db'),
    'user': os.getenv('DB_USER', 'umair')
}
if os.getenv('DB_PASSWORD'):
    DB_CONFIG['password'] = os.getenv('DB_PASSWORD')
if os.getenv('DB_HOST'):
    DB_CONFIG['host'] = os.getenv('DB_HOST')
if os.getenv('DB_PORT'):
    DB_CONFIG['port'] = int(os.getenv('DB_PORT'))

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

DATA_DIR = os.getenv("DATA_DIR")
if not DATA_DIR:
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidates = [
        os.path.join(base_dir, "data"),
        os.path.join(os.path.dirname(base_dir), "Axeom Challenge - Pack 213", "data"),
        "/home/umair/Downloads/Axeom Challenge - Pack 213/data"
    ]
    for c in candidates:
        if os.path.isdir(c):
            DATA_DIR = c
            break

# 31 CANONICAL CLIENT DEFINITIONS WITH COMPREHENSIVE ALIASES
CLIENTS_DATA = [
    {
        "canonical_name": "Ironclad DFW",
        "aliases": ["Ironclad Church", "Ironclad Media Team", "Imran Grant", "PASTOR IMRAN GRANT", "media@ironcladdfw.org", "972-555-0194"],
        "emails": ["media@ironcladdfw.org"],
        "phones": ["972-555-0194"]
    },
    {
        "canonical_name": "Rise & Grind",
        "aliases": ["Rise and Grind", "R&G Podcast", "Rise & Grind Podcast", "Nadia Okafor", "nadia@riseandgrind.fm", "nadia.okafor.mail@gmail.com", "972-555-0147"],
        "emails": ["nadia@riseandgrind.fm", "nadia.okafor.mail@gmail.com"],
        "phones": ["972-555-0147"]
    },
    {
        "canonical_name": "Metroplex Makers",
        "aliases": ["Metroplex Makers Podcast", "Raj Park", "RAJ PARK", "raj@metroplexmakers.fm", "817-555-0109"],
        "emails": ["raj@metroplexmakers.fm"],
        "phones": ["817-555-0109"]
    },
    {
        "canonical_name": "Green Dental",
        "aliases": ["Dr. Joy Green", "Dr Green", "Joy Green DDS", "JOY GREEN", "hello@greendental.com", "hello@greendental.con", "469-555-0100"],
        "emails": ["hello@greendental.com", "hello@greendental.con"],
        "phones": ["469-555-0100"]
    },
    {
        "canonical_name": "Hillcrest Roofing Co",
        "aliases": ["Hillcrest Roofing", "Ben Grant", "BEN GRANT", "@hillcrestroofingcodfw", "ben@hillcrestroofingco.com", "214-555-0163"],
        "emails": ["ben@hillcrestroofingco.com"],
        "phones": ["214-555-0163"]
    },
    {
        "canonical_name": "Canyon Builders",
        "aliases": ["Canyon Builders LLC", "Canyon & Co Builders", "Canyon", "Ben Malik", "ben@canyon.build", "469-555-0118"],
        "emails": ["ben@canyon.build"],
        "phones": ["469-555-0118"]
    },
    {
        "canonical_name": "Apex Med Spa",
        "aliases": ["Apex Medspa", "Apex Med Spa - Plano", "Apex Med Spa - Frisco", "Apex", "Lena Kim", "lena@apexmedspa.com", "frisco@apexmedspa.com", "972-555-0105"],
        "emails": ["lena@apexmedspa.com", "frisco@apexmedspa.com"],
        "phones": ["972-555-0105"]
    },
    {
        "canonical_name": "Oak Lane Wealth Partners",
        "aliases": ["Oak Lane WP", "Oak Lane Wealth", "Jared Romero", "JARED ROMERO", "jromero@oaklanewp.com", "214-555-0158"],
        "emails": ["jromero@oaklanewp.com"],
        "phones": ["214-555-0158"]
    },
    {
        "canonical_name": "Magnolia Bridal Boutique",
        "aliases": ["Magnolia Bridal", "Ivy Walsh", "IVY WALSH", "ivy@magnoliabridal.com", "469-555-0173"],
        "emails": ["ivy@magnoliabridal.com"],
        "phones": ["469-555-0173"]
    },
    {
        "canonical_name": "Mendez Law Firm PLLC",
        "aliases": ["Mendez Law Firm", "Mendez Law", "Mendez", "Ben Mendez", "BEN MENDEZ", "info@mendezlaw.com", "469-555-0125"],
        "emails": ["info@mendezlaw.com"],
        "phones": ["469-555-0125"]
    },
    {
        "canonical_name": "Luna Med Spa",
        "aliases": ["Luna Med Spa - Plano", "Luna Medspa", "Luna", "Paula Hale", "PAULA HALE", "paula@lunamedspa.com", "469-555-0162"],
        "emails": ["paula@lunamedspa.com"],
        "phones": ["469-555-0162"]
    },
    {
        "canonical_name": "Keystone Chiropractic",
        "aliases": ["Keystone Chiro", "Dr. Tran", "Nina Tran", "Tanya Tran", "drtran@keystonechiro.com", "tanya@keystonechiro.com", "469-555-0108", "469-555-0193"],
        "emails": ["drtran@keystonechiro.com", "tanya@keystonechiro.com"],
        "phones": ["469-555-0108", "469-555-0193"]
    },
    {
        "canonical_name": "Bloom Athletics",
        "aliases": ["Bloom Fitness", "Bloom Fit", "Bloom", "Megan Webb", "MEGAN WEBB", "megan@bloomfit.co", "megan@bloomathletics.com", "817-555-0129"],
        "emails": ["megan@bloomfit.co", "megan@bloomathletics.com"],
        "phones": ["817-555-0129"]
    },
    {
        "canonical_name": "Becker Insurance Group",
        "aliases": ["Becker Insurance", "Becker Ins", "Will Becker", "will@beckerinsures.com", "817-555-0165"],
        "emails": ["will@beckerinsures.com"],
        "phones": ["817-555-0165"]
    },
    {
        "canonical_name": "Crown Barbershop",
        "aliases": ["Crown Barbers", "Derek Delgado", "derek@crownbarbers.com", "817-555-0137"],
        "emails": ["derek@crownbarbers.com"],
        "phones": ["817-555-0137"]
    },
    {
        "canonical_name": "Stone Bridge Realty",
        "aliases": ["Stone Bridge Realty LLC", "Paula Haddad", "paula@stonebridgerealty.com", "972-555-0142"],
        "emails": ["paula@stonebridgerealty.com"],
        "phones": ["972-555-0142"]
    },
    {
        "canonical_name": "Haddad Dental",
        "aliases": ["Haddad Dental PLLC", "Dr. Carmen Haddad", "Dr Haddad", "Carmen Haddad DDS", "hello@haddaddental.com", "214-555-0198", "469-555-0120"],
        "emails": ["hello@haddaddental.com"],
        "phones": ["214-555-0198", "469-555-0120"]
    },
    {
        "canonical_name": "Lumen Social",
        "aliases": ["LUMEN SOCIAL LLC", "Aisha Novak", "aisha@lumenmktg.com", "Lumen - Northpoint", "Lumen - Ridgeway", "972-555-0120"],
        "emails": ["aisha@lumenmktg.com"],
        "phones": ["972-555-0120"]
    },
    {
        "canonical_name": "Ridgeway Pediatrics",
        "aliases": ["Ridgeway Peds", "Quinn Jackson", "qjackson@ridgewaypeds.com", "972-555-0131"],
        "emails": ["qjackson@ridgewaypeds.com"],
        "phones": ["972-555-0131"]
    },
    {
        "canonical_name": "Green Family Law",
        "aliases": ["Green Family Law PLLC", "Green Law", "Marcus Green", "info@greenfamilylaw.com", "214-555-0161"],
        "emails": ["info@greenfamilylaw.com"],
        "phones": ["214-555-0161"]
    },
    {
        "canonical_name": "Sterling Coffee Roasters",
        "aliases": ["Sterling Coffee", "Sterling Roasters", "Tasha Hassan", "TASHA HASSAN", "tasha@sterlingcoffee.com", "214-555-0169"],
        "emails": ["tasha@sterlingcoffee.com"],
        "phones": ["214-555-0169"]
    },
    {
        "canonical_name": "Kingsley Builders",
        "aliases": ["Kingsley Builders LLC", "Kingsley & Co Builders", "Kingsley", "Rosa Mendez", "rosa@kingsley.build", "469-555-0124"],
        "emails": ["rosa@kingsley.build"],
        "phones": ["469-555-0124"]
    },
    {
        "canonical_name": "Northpoint Physical Therapy",
        "aliases": ["Northpoint PT", "Nadia Shah", "nshah@northpointptdallas.com", "972-555-0102"],
        "emails": ["nshah@northpointptdallas.com"],
        "phones": ["972-555-0102"]
    },
    {
        "canonical_name": "Vista Gym",
        "aliases": ["Vista Gym TX", "Vista", "Carlos Novak", "CARLOS NOVAK", "carlos@vistagym.co", "214-555-0106"],
        "emails": ["carlos@vistagym.co"],
        "phones": ["214-555-0106"]
    },
    {
        "canonical_name": "Juniper Family Therapy",
        "aliases": ["Dr. Mia Price", "Juniper Therapy", "Mia Price", "mprice@juniperfamilytherapy.com", "214-555-0144"],
        "emails": ["mprice@juniperfamilytherapy.com"],
        "phones": ["214-555-0144"]
    },
    {
        "canonical_name": "Kim's Auto Spa",
        "aliases": ["Kim's Auto", "Kims Auto", "Nadia Kim", "nadia@kimsautospa.com", "469-555-0119"],
        "emails": ["nadia@kimsautospa.com"],
        "phones": ["469-555-0119"]
    },
    {
        "canonical_name": "Riverbend Coffee Roasters",
        "aliases": ["Riverbend Coffee", "Riverbend Roasters", "Mia Reed", "mia@riverbendcoffee.com", "469-555-0179"],
        "emails": ["mia@riverbendcoffee.com"],
        "phones": ["469-555-0179"]
    },
    {
        "canonical_name": "Mesquite Roofing Co",
        "aliases": ["Mesquite Roofing", "Jordan Becker", "JORDAN BECKER", "jordan@mesquiteroofingco.com", "469-555-0158"],
        "emails": ["jordan@mesquiteroofingco.com"],
        "phones": ["469-555-0158"]
    },
    {
        "canonical_name": "Stonebridge Realty Group",
        "aliases": ["Stonebridge RG", "Will Ortiz", "will@stonebridgerg.com", "469-555-0154"],
        "emails": ["will@stonebridgerg.com"],
        "phones": ["469-555-0154"]
    },
    {
        "canonical_name": "Kind Hands Homecare",
        "aliases": ["Kind Hands Home Care", "Priya Okafor", "priya@kindhandshomecare.com", "817-555-0153"],
        "emails": ["priya@kindhandshomecare.com"],
        "phones": ["817-555-0153"]
    },
    {
        "canonical_name": "Daniels Auto Detailing",
        "aliases": ["Daniels Auto", "Daniels Detailing", "Trent Daniels", "@danielsautodetaili", "trent.daniels.detail@gmail.com", "469-555-0189"],
        "emails": ["trent.daniels.detail@gmail.com"],
        "phones": ["469-555-0189"]
    }
]

def parse_us_date(d_str):
    # MM/DD/YYYY
    if not d_str or not d_str.strip():
        return None
    return datetime.strptime(d_str.strip(), '%m/%d/%Y').date()

def parse_intl_date(d_str):
    # DD/MM/YYYY
    if not d_str or not d_str.strip():
        return None
    return datetime.strptime(d_str.strip(), '%d/%m/%Y').date()

def parse_iso_date(d_str):
    # YYYY-MM-DD
    if not d_str or not d_str.strip():
        return None
    return datetime.strptime(d_str.strip(), '%Y-%m-%d').date()

def parse_iso_timestamp(d_str):
    # YYYY-MM-DD HH:MM
    if not d_str or not d_str.strip():
        return None
    return datetime.strptime(d_str.strip(), '%Y-%m-%d %H:%M')

def parse_price(p_str):
    if not p_str or not p_str.strip():
        return 0.00
    cleaned = p_str.replace('$', '').replace(',', '').strip()
    return float(cleaned)

def main():
    if DATABASE_URL:
        conn = psycopg2.connect(DATABASE_URL)
    else:
        conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    # Ensure schema and extensions exist
    schema_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")
    if os.path.isfile(schema_file):
        try:
            with open(schema_file, "r", encoding="utf-8") as sf:
                cur.execute(sf.read())
            conn.commit()
            print("Ensured schema and tables exist.")
        except Exception as e:
            conn.rollback()
            print(f"Schema notice: {e}")

    print("=== SEEDING / IMPORTING DATA INTO POSTGRESQL ===")
    print(f"Using DATA_DIR: {DATA_DIR}")

    # 1. UPSERT CLIENTS
    print("\n1. Upserting 31 Canonical Clients...")
    client_id_map = {} # canonical_name -> UUID
    email_to_client_id = {}
    name_to_client_id = {}

    for c in CLIENTS_DATA:
        cur.execute("""
            INSERT INTO clients (canonical_name, aliases, notes)
            VALUES (%s, %s, %s)
            ON CONFLICT DO NOTHING
            RETURNING id;
        """, (c["canonical_name"], json.dumps(c["aliases"]), None))
        row = cur.fetchone()
        if not row:
            cur.execute("SELECT id FROM clients WHERE canonical_name = %s;", (c["canonical_name"],))
            row = cur.fetchone()
        cid = row[0]
        client_id_map[c["canonical_name"]] = cid

        for em in c["emails"]:
            email_to_client_id[em.lower()] = cid
        name_to_client_id[c["canonical_name"].lower()] = cid
        name_to_client_id[c["canonical_name"].lower().replace(' ', '')] = cid
        for alias in c["aliases"]:
            name_to_client_id[alias.lower()] = cid
            name_to_client_id[alias.lower().replace(' ', '')] = cid

    print(f"Loaded {len(client_id_map)} canonical clients.")

    # Helper to resolve client_id from email or name
    def resolve_client(email_str, name_str):
        if email_str and email_str.strip().lower() in email_to_client_id:
            return email_to_client_id[email_str.strip().lower()]
        if name_str:
            clean_name = name_str.strip().lower()
            if clean_name in name_to_client_id:
                return name_to_client_id[clean_name]
            clean_tight = clean_name.replace(' ', '')
            if clean_tight in name_to_client_id:
                return name_to_client_id[clean_tight]
            for alias, cid in name_to_client_id.items():
                if alias in clean_name or clean_name in alias:
                    return cid
        return None

    # 2. IMPORT LEADS
    print("\n2. Importing leads.csv...")
    with open(os.path.join(DATA_DIR, 'leads.csv'), 'r', encoding='utf-8') as f:
        leads_reader = list(csv.DictReader(f))
    
    leads_inserted = 0
    for r in leads_reader:
        cid = resolve_client(r['email'], r['name']) or resolve_client(r['email'], r['business'])
        created_dt = parse_iso_timestamp(r['created'])
        reply_d = parse_iso_date(r['first_reply'])
        cur.execute("""
            INSERT INTO leads (lead_id, client_id, created, name, business, email, phone, source, first_reply, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (lead_id) DO UPDATE SET
                client_id = EXCLUDED.client_id,
                name = EXCLUDED.name,
                business = EXCLUDED.business,
                email = EXCLUDED.email,
                phone = EXCLUDED.phone,
                source = EXCLUDED.source,
                first_reply = EXCLUDED.first_reply,
                status = EXCLUDED.status;
        """, (r['lead_id'], cid, created_dt, r['name'], r['business'], r['email'], r['phone'], r['source'], reply_d, r['status']))
        leads_inserted += 1
    print(f"Upserted {leads_inserted} leads.")

    # 3. IMPORT BOOKINGS
    print("\n3. Importing bookings.csv...")
    with open(os.path.join(DATA_DIR, 'bookings.csv'), 'r', encoding='utf-8') as f:
        bookings_reader = list(csv.DictReader(f))

    bookings_inserted = 0
    for r in bookings_reader:
        cid = resolve_client(r['email'], r['client_name'])
        b_date = parse_us_date(r['date'])
        price_num = parse_price(r['price'])
        cur.execute("""
            INSERT INTO bookings (booking_id, client_id, date, client_name, email, service, status, price)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (booking_id) DO UPDATE SET
                client_id = EXCLUDED.client_id,
                date = EXCLUDED.date,
                client_name = EXCLUDED.client_name,
                email = EXCLUDED.email,
                service = EXCLUDED.service,
                status = EXCLUDED.status,
                price = EXCLUDED.price;
        """, (r['booking_id'], cid, b_date, r['client_name'], r['email'], r['service'], r['status'], price_num))
        bookings_inserted += 1
    print(f"Upserted {bookings_inserted} bookings.")

    # 4. IMPORT INVOICES
    print("\n4. Importing invoices.csv...")
    with open(os.path.join(DATA_DIR, 'invoices.csv'), 'r', encoding='utf-8') as f:
        invoices_reader = list(csv.DictReader(f))

    invoices_inserted = 0
    for r in invoices_reader:
        cid = resolve_client(r['email'], r['bill_to'])
        iss_d = parse_iso_date(r['issued'])
        due_d = parse_iso_date(r['due'])
        amt = float(r['amount'])
        cur.execute("""
            INSERT INTO invoices (invoice_no, client_id, bill_to, email, issued, due, amount, status, memo)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (invoice_no) DO UPDATE SET
                client_id = EXCLUDED.client_id,
                bill_to = EXCLUDED.bill_to,
                email = EXCLUDED.email,
                issued = EXCLUDED.issued,
                due = EXCLUDED.due,
                amount = EXCLUDED.amount,
                status = EXCLUDED.status,
                memo = EXCLUDED.memo;
        """, (r['invoice_no'], cid, r['bill_to'], r['email'], iss_d, due_d, amt, r['status'], r['memo']))
        invoices_inserted += 1
    print(f"Upserted {invoices_inserted} invoices.")

    # 5. IMPORT PAYMENTS
    print("\n5. Importing payments.csv...")
    with open(os.path.join(DATA_DIR, 'payments.csv'), 'r', encoding='utf-8') as f:
        payments_reader = list(csv.DictReader(f))

    payments_inserted = 0
    for r in payments_reader:
        p_date = parse_intl_date(r['date'])
        amt = float(r['amount'])
        ref = r['reference'].strip()
        matched_inv = ref if ref.startswith('INV-') else None
        
        cur.execute("""
            INSERT INTO payments (payment_id, payment_date, payer, payer_email, amount, method, reference, matched_invoice_no)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (payment_id) DO UPDATE SET
                payment_date = EXCLUDED.payment_date,
                payer = EXCLUDED.payer,
                payer_email = EXCLUDED.payer_email,
                amount = EXCLUDED.amount,
                method = EXCLUDED.method,
                reference = EXCLUDED.reference,
                matched_invoice_no = EXCLUDED.matched_invoice_no;
        """, (r['payment_id'], p_date, r['payer'], r['payer_email'], amt, r['method'], r['reference'], matched_inv))
        payments_inserted += 1
    print(f"Upserted {payments_inserted} payments.")

    # 6. IMPORT PRODUCTION BOARD
    print("\n6. Importing production_board.csv...")
    with open(os.path.join(DATA_DIR, 'production_board.csv'), 'r', encoding='utf-8') as f:
        pb_reader = list(csv.DictReader(f))

    pb_inserted = 0
    for r in pb_reader:
        cid = resolve_client(None, r['client'])
        appr_d = parse_iso_date(r['client_approved_on'])
        hours = float(r['editor_hours']) if r['editor_hours'].strip() else 0.00
        revs = int(r['revisions']) if r['revisions'].strip() else 0
        shoot_bk = r['shoot_booking'].strip() if r['shoot_booking'].strip() else None

        cur.execute("""
            INSERT INTO production_videos (video_id, client_id, client, title, editor, stage, notes_on_board, revisions, editor_hours, client_approved_on, shoot_booking)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (video_id) DO UPDATE SET
                client_id = EXCLUDED.client_id,
                client = EXCLUDED.client,
                title = EXCLUDED.title,
                editor = EXCLUDED.editor,
                stage = EXCLUDED.stage,
                notes_on_board = EXCLUDED.notes_on_board,
                revisions = EXCLUDED.revisions,
                editor_hours = EXCLUDED.editor_hours,
                client_approved_on = EXCLUDED.client_approved_on,
                shoot_booking = EXCLUDED.shoot_booking;
        """, (r['video_id'], cid, r['client'], r['title'], r['editor'], r['stage'], r['notes_on_board'], revs, hours, appr_d, shoot_bk))
        pb_inserted += 1
    print(f"Upserted {pb_inserted} production videos.")

    # 7. IMPORT MESSAGES
    print("\n7. Importing messages.txt...")
    vn_pattern = re.compile(r'^\[(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})\]\s+VOICE NOTE\s+(from|to)\s+(.+?),\s*(\d+:\d+)\.\s*Transcript:\s*\"(.*)\"$')
    reg_pattern = re.compile(r'^\[(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})\]\s+([A-Z\s]+?)\s+(from|to)\s+([^:]+):\s*(.*)$')

    with open(os.path.join(DATA_DIR, 'messages.txt'), 'r', encoding='utf-8') as f:
        msg_lines = [l.strip() for l in f if l.strip()]

    msgs_inserted = 0
    for line in msg_lines:
        m_vn = vn_pattern.match(line)
        if m_vn:
            dt, direction, sender, duration, transcript = m_vn.groups()
            msg_dt = parse_iso_timestamp(dt)
            channel = 'VOICE NOTE'
            sender_str = sender.strip()
            body_text = transcript.strip()
        else:
            m_reg = reg_pattern.match(line)
            if m_reg:
                dt, platform, direction, sender, body = m_reg.groups()
                msg_dt = parse_iso_timestamp(dt)
                channel = platform.strip()
                sender_str = sender.strip()
                body_text = body.strip()
            else:
                continue

        cid = resolve_client(None, sender_str)

        cur.execute("""
            INSERT INTO messages (client_id, message_date, channel, sender, message_text, original_line)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (original_line) DO UPDATE SET
                client_id = EXCLUDED.client_id,
                message_date = EXCLUDED.message_date,
                channel = EXCLUDED.channel,
                sender = EXCLUDED.sender,
                message_text = EXCLUDED.message_text;
        """, (cid, msg_dt, channel, sender_str, body_text, line))
        msgs_inserted += 1
    print(f"Upserted {msgs_inserted} messages.")

    # 8. IMPORT TEAM
    print("\n8. Importing team.csv...")
    with open(os.path.join(DATA_DIR, 'team.csv'), 'r', encoding='utf-8') as f:
        team_reader = list(csv.DictReader(f))

    for r in team_reader:
        joined_d = parse_iso_date(r['joined'])
        pay_val = None
        if r['pay'].strip():
            # e.g. '$35/hour'
            m = re.search(r'\$?([0-9]+(?:\.[0-9]+)?)', r['pay'])
            if m:
                pay_val = float(m.group(1))

        cur.execute("""
            INSERT INTO team_members (name, role, joined, pay)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (name) DO UPDATE SET
                role = EXCLUDED.role,
                joined = EXCLUDED.joined,
                pay = EXCLUDED.pay;
        """, (r['name'], r['role'], joined_d, pay_val))
    print(f"Upserted {len(team_reader)} team members.")

    # 9. IMPORT COSTS
    print("\n9. Importing costs.csv...")
    with open(os.path.join(DATA_DIR, 'costs.csv'), 'r', encoding='utf-8') as f:
        costs_reader = list(csv.DictReader(f))

    for r in costs_reader:
        cost_val = None
        unit_str = None
        if '$' in r['cost']:
            m = re.search(r'\$?([0-9]+(?:\.[0-9]+)?)', r['cost'])
            if m:
                cost_val = float(m.group(1))
            if 'hour' in r['cost']:
                unit_str = 'hour'

        cur.execute("""
            INSERT INTO cost_rules (rule_name, value, unit, notes)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT DO NOTHING;
        """, (r['item'], cost_val, unit_str, r['note']))
    print(f"Upserted {len(costs_reader)} cost rules.")

    conn.commit()
    cur.close()
    conn.close()
    print("\nALL DATA SUCCESSFULLY IMPORTED AND COMMITTED!")

if __name__ == '__main__':
    main()
