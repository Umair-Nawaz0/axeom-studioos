# Axeom StudioOS

> **Axeom Technical Assessment — Pack 213 Submission**  
> Operational decision-support system and executive dashboard for a commercial video & podcast studio in Dallas.  
> Designed to pass the **10-Second Owner Test**, adhere to **"Suggest, never act alone"**, and resolve fragmented business records into verified truth.

---

## 1. Executive Summary & Problem Resolution

Axeom runs on 8 disconnected files (`leads.csv`, `bookings.csv`, `invoices.csv`, `payments.csv`, `production_board.csv`, `messages.txt`, `team.csv`, `costs.csv`). Axeom StudioOS reconciles these disparate sources into an unified, mobile-first operations center:

- **Who are our real clients?**  
  **30 canonical clients** resolved across spelling variations, emails, and phone numbers, plus **1 third-party billing payer** (`Lumen Social`, paying for *Ridgeway Pediatrics* and *Northpoint Physical Therapy*). Typo booking `B025` (`hello@greendental.con`) corroborated to *Joy Green DDS*.
- **Who really owes us money?**  
  Source records showed 13 unpaid invoices totaling $12,055.00. Cross-referencing unrecorded bank deposits, wire transfers, and lump-sum payments reconciles this down to **$9,505.00 across 8 truly overdue invoices** (as of October 6, 2026).
- **Do we owe anyone?**  
  **$2,400.00 in studio obligations**: $900.00 duplicate payment to *Magnolia Bridal Boutique* (invoices `INV-1095` paid via both `P5086` and `P5088`), and $1,500.00 credit owed to *Stone Bridge Realty* (cancelled shoot `B147` previously paid via `INV-1135`).
- **Did we do work we never billed?**  
  **$2,400.00 confirmed unbilled work**: Shoot `B072` (*Juniper Family Therapy*, $1,500.00) and shoot `B135` (*Kim's Auto Spa*, $900.00) were completed but never invoiced. An additional $255.00 review item exists for shoot `B095` (*Ironclad DFW*).
- **Why do client requests get lost?**  
  On **June 1, 2026 (`2026-06`)**, the studio broadcast message #28 encouraging clients to send edit requests via voice notes without an operational ingestion workflow. **0 of 39 client voice notes (0%)** were transcribed or logged to `production_board.csv`, triggering 22 repeated complaints and delivering 1 privacy violation (`V223`, missing face blur).
- **Which client is most likely to leave?**  
  **Keystone Chiropractic** (Dr. Tanya Tran). Repeated complaints about compliance name truncation ("Keystone Chiro"), followed by an explicit contract cancellation inquiry (message #185) and an open $2,500.00 retainer invoice (`INV-1119`).
- **Marketing performance:**  
  **Referral** achieved the highest observed conversion at **78.6%** (11 won out of 14 leads, $66,800.00 revenue). Crucially, `costs.csv` contains zero paid advertising spend (CAC is missing), meaning net channel ROI cannot be mathematically proven.
- **Monday morning top 3 actions:**  
  1. *Audit 6 Unsigned-Release Videos* (Priority 1: Urgent privacy remediation for delivered video `V223`).  
  2. *Review Keystone Chiropractic Contract* (Priority 2: Churn intervention and compliance correction).  
  3. *Reconcile 8 Overdue Invoices & 3 Unbilled Shoots* (Priority 3: Immediate cash collection and billing catch-up).

---

## 2. System Architecture

```
axeom_project/
├── backend/                  # FastAPI Application
│   ├── app/
│   │   ├── main.py           # REST API routes & middleware
│   │   ├── db.py             # PostgreSQL connection pool & auto-DDL
│   │   ├── config.py         # Config with DATABASE_URL & Gemini SDK
│   │   ├── models.py         # Pydantic schemas
│   │   └── services/         # Reconciliation, date, & Gemini AI pipelines
│   ├── requirements.txt      # Python dependencies
│   └── run.sh                # Local startup script
├── frontend/                 # Next.js 14 App Router + Tailwind CSS
│   ├── src/
│   │   ├── app/              # Routes: /today, /clients, /requests, /production, /money
│   │   ├── components/       # AppShell, AddFilesModal, UI elements
│   │   └── lib/              # Typed API client & custom events
│   ├── next.config.mjs       # Next.js API rewrites for production
│   └── package.json          # Node dependencies
├── database/                 # Database schema and seed utilities
│   ├── schema.sql            # PostgreSQL DDL
│   └── import_data.py        # Automated multi-file seeder & reconciliation
└── data/                     # Pack 213 baseline CSV & message files
```

---

## 3. Local Development Setup

### Prerequisites
- Node.js 18+ (tested on Node 20 & 22)
- Python 3.10+
- PostgreSQL (local instance or cloud database such as Neon)

### 1. Database Setup
```bash
# Set connection string (local or Neon)
export DATABASE_URL="postgresql://user:password@localhost:5432/axeom_db"

# Seed baseline Pack 213 data
python3 database/import_data.py
```

### 2. Backend Startup
```bash
cd backend
pip install -r requirements.txt
./run.sh
# Backend runs at http://localhost:8000
```

### 3. Frontend Startup
```bash
cd frontend
npm install
npm run dev
# Frontend runs at http://localhost:3000
```

---

## 4. Production Deployment Guide

### A. Database (Neon Serverless PostgreSQL)
1. Create a free PostgreSQL project at [neon.tech](https://neon.tech).
2. Copy your connection string: `postgresql://user:password@ep-xyz.us-east-2.aws.neon.tech/neondb?sslmode=require`.
3. Seed the Neon database directly from your local terminal:
   ```bash
   DATABASE_URL="your-neon-connection-string" python3 database/import_data.py
   ```

### B. Backend (Render Web Service)
1. Connect this GitHub repository to [Render](https://render.com).
2. Create a new **Web Service**:
   - **Root Directory:** `backend`
   - **Runtime:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
3. Add Environment Variables:
   - `DATABASE_URL`: Your Neon connection string.
   - `GEMINI_API_KEY`: Your Google AI Studio API key.
   - `REFERENCE_DATE`: `2026-10-06`
4. Copy the live backend URL (e.g., `https://axeom-backend.onrender.com`).

### C. Frontend (Vercel)
1. Import this GitHub repository to [Vercel](https://vercel.com).
2. In Project Settings, set **Root Directory** to `frontend`.
3. Add Environment Variable:
   - `NEXT_PUBLIC_API_BASE_URL`: `https://axeom-backend.onrender.com`
4. Click **Deploy**. Vercel will build and host the live link.

---

## 5. Testing & Verification

- **Automated Viewport Verification:** All core views (`/today`, `/clients`, `/requests`, `/production`, `/money`) are verified for zero horizontal overflow across Mobile (360px, 390px), Tablet (768px), and Desktop (1440px).
- **Dry-Run File Upload:** The "Add new files" button supports drag-and-drop CSV/TXT uploads, transactional schema validation, and order-independent reconciliation.
- **Safety Standard:** Suggest, never act alone. All notifications and actions require explicit human approval; no external emails, SMS, or webhooks are triggered autonomously.
