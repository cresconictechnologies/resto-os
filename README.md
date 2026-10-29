# RestoOS — High-Throughput Restaurant Management & POS Platform

> Production-grade, offline-resilient restaurant operating system engineered for fast-paced dining establishments and bars. Built for Rasa Sahyadri (Koregaon Park, Pune) with dual deployment targets: Local LAN Desktop Mesh and Vercel + Supabase Cloud.

- **GitHub Repository:** [github.com/cresconictechnologies/resto-os](https://github.com/cresconictechnologies/resto-os)
- **Live Vercel Production:** [restaurant-management-woad-psi.vercel.app](https://restaurant-management-woad-psi.vercel.app)
- **Local Counter Instance:** `http://127.0.0.1:8000`

---

## 1. Role-Based Access Control (RBAC)

The application features strict station-level permission enforcement tailored for restaurant operations:

| Role | Station Access | Capabilities | Restricted Areas |
| :--- | :--- | :--- | :--- |
| **CASHIER** (Hotel Staff) | • Cash Counter & Floor<br>• Cashier Shifts | • Interactive Floor Table Map (Ground & Terrace)<br>• Menu item browsing & Veg/Non-Veg filters<br>• Instant Bill Printing (`F3`) & Settle & Drawer (`F4`)<br>• Split tender (Cash, UPI, Card)<br>• Shift float, petty cash vouchers & Blind Close Z-Report | 🚫 Owner BI & Analytics<br>🚫 Store & Grocery Purchasing<br>🚫 Bar & State Excise (FLR-3A)<br>🚫 Settings & Menu Rate Edits |
| **OWNER / ADMIN** | **Whole Software** (Full Suite) | • **Executive Analytics Dashboard** (Gross/Net sales, ARPT, 24-hr heatmap, AvT cost variance, BCG Matrix, NLP queries)<br>• Central Store & Grocery Inventory (PO, GRN, Indents)<br>• State Excise FL-3 Registers (Form FLR-3A & FLR-4)<br>• Master Menu & Dish Creation, Pricing, Category & Station mapping<br>• Statutory Profile (GSTIN, FSSAI, FL-3 license) | *None (Full Access)* |

### Default Credentials
- **Cashier (Pooja More):** PIN `1234`
- **Owner / Admin (Mahesh Patil):** PIN `9999`
- **Manager (Sachin Kadam):** PIN `9999`

---

## 2. Architecture & Dual Deployment Modes

### Mode 1: Local Offline LAN (Zero-Cloud Desktop Counter)
- **Database:** High-speed SQLite in WAL mode (`journal_mode=WAL`, `synchronous=NORMAL`).
- **Resilience:** Unbreakable during internet outages or power cuts. Runs on local desktop counter at `http://127.0.0.1:8000`.
- **Peripheral Integration:** Direct 24V Solenoid RJ12 cash drawer kick via ESC/POS hex (`1b700019fa`) and 80mm thermal receipt printing.

### Mode 2: Cloud Sync (Vercel Serverless + Supabase PostgreSQL)
- **Database:** Hosted PostgreSQL on [Supabase](https://supabase.com).
- **Backend API:** FastAPI Serverless functions deployed on [Vercel](https://vercel.com) (`@vercel/python`).
- **Frontend SPA:** Single-page application served via Vercel Edge CDN with instantaneous caching and client-side routing.

---

## 3. Quick Start & Local Setup

### Prerequisites
- Python 3.10+
- Modern Web Browser (Chrome / Edge / Firefox)

### Running Locally
```bash
# Clone the repository
git clone https://github.com/cresconictechnologies/resto-os.git
cd resto-os

# Install dependencies
pip install -r requirements.txt

# Start RestoOS server
python -m uvicorn server.main:app --host 0.0.0.0 --port 8000 --reload
```
Open **`http://127.0.0.1:8000`** in your browser.

---

## 4. Supabase Setup Guide

1. Create a project at [supabase.com](https://supabase.com).
2. Go to **SQL Editor** in your Supabase project dashboard.
3. Open [`supabase_schema.sql`](./supabase_schema.sql) in this repo, copy its contents, and click **Run**.
4. Copy your Database Connection URI from **Project Settings -> Database -> Connection String (URI)**.
5. In your `.env` file (or Vercel Environment Variables):
   ```bash
   DATABASE_URL=postgresql://postgres:[YOUR-PASSWORD]@db.[YOUR-PROJECT-REF].supabase.co:5432/postgres
   SUPABASE_URL=https://[YOUR-PROJECT-REF].supabase.co
   SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
   ```

---

## 5. Vercel Deployment Guide

Deploy to Vercel in one command using the Vercel CLI:
```bash
# Login to Vercel
npx vercel login

# Deploy to preview
npx vercel

# Deploy to production
npx vercel --prod
```

Configure your environment variables (`DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`) in the Vercel Project Settings under **Environment Variables**.

---

## 6. Comprehensive Verification Suite

Run all automated unit and integration tests covering all 10 operational domains:
```bash
python -m server.test_api
```

Test coverage includes:
- System Health & Configuration
- Table layout & Floor State machine
- Menu browsing, Cart & Cash counter billing
- Statutory Dual-Taxation (Food GST 5% + State MVAT 5%)
- Cashier Shift Float, Vouchers & Blind Close Z-Report
- Two-tier Raw Material Inventory & Live 86 Locking
- Maharashtra State Excise FLR-3A Daily Register & FLR-4 Abstract
- Owner Executive BI, BCG Matrix & NLP Resto Intelligence
- Settings & Menu Catalog Management
- Role-Based Access Control (RBAC) & PIN Authorization
