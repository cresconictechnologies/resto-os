# DESIGN.md — UI/UX Design System & Layout Contract (Inspired by Covers)

> Visual contract and interface specification modeled after the **Covers** (Rasa Sahyadri) minimal, high-speed Indian restaurant POS standard.
>
> **V1 SCOPE LOCK:** 
> - **Merged Counter Operations (Direct Counter Billing - No KOT):** Table floor management, order punching, bill printing, and settlement are **100% merged into the Cash Counter**. No KOT tickets, no kitchen order ticket delays, and no separate floor order terminal.
> - **Settings & Dish Catalog Management:** Built-in settings workspace for adding dishes, modifying live selling prices, toggling 86 out-of-stock items, and configuring statutory restaurant credentials (GSTIN, FSSAI, State Excise FL-3, MVAT).
> - **Desktop Terminals:**
>   - **Desktop 1 (Cash Counter 1):** Unified Table Selection + Menu Order Punching + Direct GST Billing + 24V Cash Drawer + Shift Z-Report + Settings (and local DB host).
>   - **Desktop 2 (Cash Counter 2 / Takeaway Counter):** Secondary billing & order terminal for rush hours or dedicated Takeaway / Delivery counter.
>   - **Desktop 3 (Central Store & Back-Office):** Grocery purchases (PO/GRN), Store-to-Kitchen Indents, Recipe BOM, Wastage logs, and P&L reports.
> - **Explicitly Excluded for V1:** NO KOT (Kitchen Order Tickets), NO KDS (Kitchen Display System), NO captain mobile screen, NO guest QR ordering, NO mobile app, NO separate floor terminal.

---

## 1. V1 Merged Counter Deployment Topology

```
+--------------------------------------------------------------------------------------------------+
|                                      RESTAURANT LOCAL LAN (Wired/Wi-Fi)                          |
|                                                                                                  |
|   [ DESKTOP 1: CASH COUNTER 1 ]        [ DESKTOP 2: CASH COUNTER 2 ]        [ DESKTOP 3: STORE & ADMIN ] 
|   (Main Billing & Table Orders)        (Secondary / Takeaway Counter)       (Back-Office & Procurement)  
|   - Interactive Floor Table Map        - Interactive Floor Table Map        - Raw Grocery Purchases      
|   - Menu Search & "Veg Only" Toggle    - Menu Search & Quick Items          - Vendor POs & GRN Inward    
|   - Cart & Prep Notes                  - Takeaway & Delivery Orders         - Store-to-Kitchen Indents   
|   - Direct "Send to Kitchen" (KOT)     - Direct "Send to Kitchen" (KOT)     - Recipe BOM & Wastage Logs  
|   - GST Bill Print & Settlement        - GST Bill Print & Settlement        - Menu Setup, Rates, P&L     
|   - Cash, UPI, Card, Khata (Credit)    - Cash, UPI, Card Settlements        - Staff PINs & Shift Audits  
|   - 24V Cash Drawer Kick Solenoid      - Optional 2nd Cash Drawer                                        
|   - Shift Open / Close (Z-Report)                                                                        
|   * [Runs Local Fastify + PostgreSQL]                                                            |
+-------------------------------------------------+------------------------------------------------+
                                                  |
                                                  | Raw TCP (Port 9100) or ESC/POS Driver
                                                  v
                               +------------------------------------+
                               |     KITCHEN THERMAL PRINTER        |
                               |  Physical 80mm KOT Ticket Output   |
                               +------------------------------------+
```

---

## 2. Design Philosophy & Visual Tone

* **Minimalist & Utilitarian:** No glossy skeuomorphism, heavy drop-shadows, or unnecessary illustrations. Every element has a functional purpose during peak restaurant rush hours.
* **Warm & Low-Fatigue Palette:**
  * Background: Clean warm neutral (`#F9FAFB` / `#F3F4F6`)
  * Surface Cards: Pure white (`#FFFFFF`) with subtle 1px border (`#E5E7EB`)
  * Text Primary: Deep charcoal (`#111827`)
  * Text Muted: Neutral gray (`#6B7280`)
  * Brand & Primary Actions: Forest green (`#15803D` / `#166534`) for primary commits like "Send to kitchen", "Print", and "Settle"
  * Seated / Live State: Warm Amber (`#D97706` / `#B45309`) for timers and active tables
  * Open / Available State: Soft green indicator (`#22C55E`)
* **Typography & Tabular Numerals:**
  * Primary Font: `Inter`, `Geist`, or `Plus Jakarta Sans`.
  * Numerals & Prices: Strict `font-mono` / `tabular-nums` ensuring currency figures (`₹`) and timers align vertically without jitter.

---

## 3. The Unified Cash Counter & Table Order Workflow

The Cash Counter terminal integrates the entire lifecycle of a table into a single, seamless 2-panel interface:

```
+-------------------------------------------------------------------------------------------------------------+
| Rasa Sahyadri · Koregaon Park · Counter 1                                          10:33 pm  ● Local Server |
| [ Tables open: 10 / 16 ]                 [ Covers today: 24 ]                    [ Sales today: ₹3,976.00 ] |
+---------------------------------------------------------------------+---------------------------------------+
|  LEFT PANEL: FLOOR VIEW OR MENU GRID                                |  RIGHT PANEL: TABLE CART & BILLING    |
|                                                                     |                                       |
|  [ View: Tables (Floor) ]  [ View: Menu Grid ]   [+ Takeaway]       |  Table: T7 (2 seats · #08-1 · 20m)    |
|  Search dishes [Ctrl+F]                [X] Veg only                 |  -----------------------------------  |
|                                                                     |  1x Chicken Sukka            ₹340.00  |
|  [Breakfast & Snacks] [Veg Starters] [Non-Veg Starters] [Mains]...  |     >> Note: Extra spicy              |
|                                                                     |  1x Mutton Rassa (Full)      ₹750.00  |
|  +-------------------+  +-------------------+  +-----------------+  |  2x Jowar Bhakri              ₹70.00  |
|  | Chicken Sukka     |  | Mutton Rassa      |  | Jowar Bhakri    |  |  -----------------------------------  |
|  | Non-Veg           |  | Non-Veg           |  | Veg             |  |  Subtotal:                     ₹1,160 |
|  | ₹340.00           |  | ₹750.00           |  | ₹35.00          |  |  CGST 2.5% + SGST 2.5%:         ₹58  |
|  +-------------------+  +-------------------+  +-----------------+  |  TOTAL:                       ₹1,218  |
|                                                                     |  -----------------------------------  |
|                                                                     |  [ Send KOT to Kitchen (F2) ]         |
|                                                                     |  [ Print Bill (F3) ]                  |
|                                                                     |  [ Settle & Cash Drawer (F4) ]        |
+---------------------------------------------------------------------+---------------------------------------+
```

### 3.1 Step-by-Step Operator Journey at Cash Counter
1. **Table Selection:** Cashier sees the floor map on the screen (`T1`, `T2`, `T3` with occupancy and seating timers). Tapping `T7` loads Table T7.
2. **Order Punching:** 
   - Cashier clicks/types dishes from the menu grid (filtered by category or search with `Veg only` switch).
   - Can add custom notes ("Extra spicy", "No garlic").
3. **Send to Kitchen (KOT):**
   - Hitting `[ Send KOT to Kitchen ]` (or keyboard `F2`) immediately streams an ESC/POS print job to the physical 80mm kitchen printer and updates Table T7 to `ORDERED`.
4. **Running Orders:**
   - If guests order extra roti or dessert later, cashier taps `T7`, adds items, and clicks `[ Send KOT ]`. Only newly added items print on the kitchen ticket.
5. **Print Customer Bill:**
   - Cashier clicks `[ Print Bill ]` (or `F3`). The local thermal printer prints the statutory GST invoice (CGST 2.5% + SGST 2.5%, FSSAI, GSTIN, amount in words).
6. **Settle Payment & Pop Drawer:**
   - Cashier clicks `[ Settle & Cash Drawer ]` (or `F4`).
   - Selects tender: `[ Cash ]`, `[ UPI QR ]`, `[ Card ]`, or `[ Khata / Credit ]`.
   - If `Cash` is selected, system generates the 24V solenoid pulse (`\x1b\x70\x00\x19\xfa`) to pop open the cash drawer, calculates change due, logs the transaction, and returns `T7` to `Open` status!

### 3.2 Takeaway & Delivery Fast Lane
- Clicking `[+ Takeaway]` immediately creates an OTC (Over-The-Counter) ticket without binding to a physical dining table.
- Cashier enters customer name/phone, punches items, collects payment, and prints both KOT and receipt in a single step.

---

## 4. Shift Management & Cash Security

* **Shift Open:** Cashier records opening drawer float (e.g. ₹2,000 in change).
* **Paid-In & Paid-Out:** Vouchers for petty cash expenses (e.g. ₹250 for urgent ice or dairy purchase).
* **Safe Drops:** Warning prompt when drawer cash exceeds ₹15,000, instructing cashier to drop cash into safe.
* **Blind Cash Close (Z-Report):**
  - At shift end, cashier enters physical note count without seeing expected system balance.
  - System calculates Over / Short variance, prints the end-of-day Z-Report slip, and locks the register.


---

## 5. Desktop 3: Central Store & Admin Back-Office Layout

### 5.1 Grocery & Inventory Purchase to Store
* **Vendor & Purchase Order (PO) Management:**
  * Vendor catalog with contracted item rates.
  * Draft $\rightarrow$ Approved $\rightarrow$ Sent purchase orders.
* **Goods Received Note (GRN) receiving dock:**
  * Record bulk inward delivery: Batch number, expiry date, invoice number, unit cost, actual weight vs PO weight.
  * Auto-updates Central Store stock balance.

### 5.2 Store-to-Kitchen Indent / Requisition
* **Internal Stock Transfer:**
  * Daily Kitchen Requisition Note: Chef/Kitchen requests raw items (e.g. 10 kg Chicken, 5 kg Paneer, 20 L Oil) from Central Store.
  * Store Issue Note: Storekeeper approves and transfers quantity from Central Store to Kitchen Stock.
* **Kitchen Wastage & Spoilage Log:**
  * Log food waste with mandatory reason codes (Burnt, Expired, Dropped, Prep trim).
* **Recipe Bill of Materials (BOM):**
  * Define ingredients per dish with prep yield losses (e.g. 15% potato peel loss).
  * Auto-calculates theoretical food cost % and live 86-item warning counts.

---

## 6. Physical 80mm ESC/POS Thermal Printing Specs

### 6.1 Kitchen Order Ticket (KOT) Slip
```text
========================================
             KITCHEN TICKET
Table: T7 (Ground Floor)      KOT #: 104
Date: 26-Oct-2026 21:05       Waiter: Rahul
========================================
QTY  ITEM                             
----------------------------------------
 1   Chicken Sukka                    
     >> Note: Extra spicy             
 1   Mutton Rassa (Full)              
 2   Jowar Bhakri                     
========================================
```

### 6.2 Bar Order Ticket (BOT) Slip
```text
========================================
            BAR ORDER TICKET (BOT)
Table: T7 (Ground Floor)      BOT #: 058
Date: 26-Oct-2026 21:05       Waiter: Rahul
========================================
QTY  ITEM                      POUR     
----------------------------------------
 2   Blenders Pride Whisky     60 ml (Large)
     >> Mixer: Soda & Ice               
 1   Kingfisher Premium Beer   650 ml   
 1   Sula Shiraz Red Wine      Glass (150ml)
========================================
```

### 6.3 Consolidated Dual-Tax Customer Invoice (Food GST + Liquor VAT)
```text
================================================
                 RASA SAHYADRI
      RESTAURANT & PERMIT ROOM (BAR)
       Lane 6, North Main Road, Pune
       GSTIN: 27AAKFR4621M1Z5
       FSSAI: 11523034000412
    EXCISE LIC (FL-3): FL3-PUN-KP-0412
       MVAT TIN: 27912345678V
================================================
TAX INVOICE: KPB3/2026/009005
Date: 26-Oct-2026 21:30       Table: T7
Cashier: Counter 1            Guests: 2
------------------------------------------------
PART A: FOOD & BEVERAGES (GST)
ITEM                       QTY    RATE    AMOUNT
Chicken Sukka                1  340.00    340.00
Mutton Rassa (Full)          1  750.00    750.00
Jowar Bhakri                 2   35.00     70.00
------------------------------------------------
Food Sub-total:                         1,160.00
CGST @2.5%:                                29.00
SGST @2.5%:                                29.00
Food Total (Incl. GST):                 1,218.00
------------------------------------------------
PART B: LIQUOR & BAR (STATE VAT)
ITEM                       QTY    RATE    AMOUNT
Blenders Pride (60ml)        2  220.00    440.00
Kingfisher Premium (650ml)   1  280.00    280.00
------------------------------------------------
Liquor Sub-total:                         720.00
MVAT @5.0%:                                36.00
Liquor Total (Incl. VAT):                 756.00
------------------------------------------------
Round off:                                  0.00
GRAND TOTAL:                        Rs. 1,974.00
One Thousand Nine Hundred Seventy Four Rupees only
------------------------------------------------
Payment Mode: UPI (Received)
================================================
        Statutory: Alcohol Consumption Is 
             Injurious To Health
================================================
```


---

## 7. Owner Executive Dashboard & Data-Driven Intelligence

The Owner Dashboard is the central command center. The Owner has **Universal Access** across all store systems, financial ledgers, recipe matrices, and staff governance, paired with deep real-time operational analytics.

```
+-------------------------------------------------------------------------------------------------------------+
| RESTO OS  [Outlet: Rasa Sahyadri - Koregaon Park v]      [Last 7 Days: 20-Oct - 26-Oct v]  [Download Excel] |
| Good evening, Aditya (Owner)                             Live Clock: 10:33 PM              ● All Nodes Sync |
+-------------------------------------------------------------------------------------------------------------+
|  TOP EXECUTIVE METRICS                                                                                      |
|  +--------------------+  +--------------------+  +--------------------+  +-------------------------------+  |
|  | Gross Sales Today  |  | Total Orders / Cov |  | Avg Ticket Size    |  | UPI & Card to Verify          |  |
|  | ₹24,850.00         |  | 42 orders / 118 cov|  | ₹591.66            |  | ₹16,420.00 (3 pending audit)  |  |
|  | +14.2% vs last Mon |  | Turn Time: 34 mins |  | Food Cost: 29.4%   |  | Cash in Drawer: ₹8,430.00     |  |
|  +--------------------+  +--------------------+  +--------------------+  +-------------------------------+  |
+---------------------------------------------------------------------+---------------------------------------+
|  LEFT PANEL: AUDIT AT A GLANCE & AI FRAUD RADAR                     |  RIGHT PANEL: DATA-DRIVEN CHARTS      |
|                                                                     |                                       |
|  [!] Audit at a Glance (Flagged items for your review):             |  HOURLY REVENUE HEATMAP               |
|  • Counter 1 opened cash drawer without sale (2 times: 3:15pm, 6:40)|  ₹4k |         ██    ██              |
|  • Cashier Rahul gave ₹450 manual discount on Table T4 (Reason: VIP)|  ₹2k |   ██    ██    ██    ██        |
|  • Void KOT: 2x Kolhapuri Chicken cancelled post-prep (Table T8)    |  ₹0k +-------------------------       |
|                                                                     |      12pm  2pm   8pm   10pm           |
|  RECENT AUDIT TRAIL (Who changed what, by name):                    |                                       |
|  22:15 - Rahul (Cashier)     - Bill Settled (T7: ₹1,218.00 via UPI) |  MENU PROFITABILITY (BCG MATRIX)      |
|  21:40 - Sneha (Manager)     - GRN Approved (PO-104: 50kg Chicken)  |  • Stars: Kolhapuri Chicken, Veg Thali|
|  20:10 - Rahul (Cashier)     - Cash Drawer Manual Kick (No Sale)    |  • Plowhorses: Jowar Bhakri, Roti     |
|  19:05 - Sneha (Manager)     - Recipe Price Updated (Mutton Rassa)  |  • Puzzles: Sol Kadhi, Kokum Sharbat  |
|  16:30 - Suresh (Storekeeper)- Store Indent Issued to Kitchen       |  • Dogs: Puran Poli (Low Volume/Cost) |
|                                                                     |                                       |
|  NATURAL LANGUAGE "ASK RESTO INTELLIGENCE":                         |  RAW GROCERY & STOCK VARIANCE (AvT)   |
|  [ What was our chicken consumption vs sales this week?       [Ask] ]  • Chicken: Theoretical 24kg | Actual 26kg (-2kg)
|  Chips: [Busiest hour this week?] [Top grossing dishes?] [Cash Short?]|  • Paneer:  Theoretical 12kg | Actual 12.2kg (OK)
+---------------------------------------------------------------------+---------------------------------------+
```

### 7.1 Universal Access & Governance Controls
The Owner role has complete, unconstrained administrative authority across the entire platform:
1. **Full Pricing & Menu Control:** Instantly update dish prices, tax rates (GST/HSN), enable/disable categories, and adjust portion sizing.
2. **Procurement & Financial Sign-Off:** View all supplier rate contracts, approve high-value Purchase Orders, inspect Goods Received Notes (GRN), and verify vendor invoice balances.
3. **Manager Override & Anti-Theft Governance:**
   - Audit-at-a-glance dashboard that automatically highlights anomalies (excessive voids, out-of-pattern discounts, off-peak cash drawer kicks).
   - Full device terminal governance: revoke lost/damaged POS desktops with 1-click Re-Link while strictly preserving the offline invoice series.
   - CA (Chartered Accountant) Read-Only portal access for seamless GSTR-1, GSTR-3B tax filing and Profit & Loss audits.

---

### 7.2 Data-Driven Statistics & Analytics Suite

#### A. Financial Performance & Sales Metrics
* **Multi-Period Aggregations:** Filter metrics by Today, Yesterday, Last 7 Days, Month-to-Date, or Custom Financial Date Ranges.
* **Revenue Breakdown:**
  * Gross Sales vs Net Sales (excl. GST).
  * Statutory GST Collections split by CGST (2.5%), SGST (2.5%), and Liquor VAT (where applicable).
  * Payment Tender Mix: Visual pie chart of Cash vs Dynamic UPI vs Card vs Khata (Customer Credit).
  * Discount Slippage: Total discounts granted vs authorized baseline with breakdown by staff member.

#### B. Operational Throughput & Dining Analytics
* **Table & Cover Velocity:**
  * Total Covers (Guests) served today.
  * Average Revenue Per Table (ARPT) and Average Spend Per Cover (ASPC).
  * Table Turnaround Duration: Tracking average seating time across ground floor and terrace sections.
* **Hourly Pacing Heatmap:**
  * Bar chart plotting orders and revenue by hour to optimize kitchen prep and staff shift scheduling (lunch rush 12:30–3:30 PM vs dinner rush 7:30–11:30 PM).

#### C. Two-Tier Inventory & Food Cost Variance (AvT)
* **Actual vs. Theoretical (AvT) Food Cost:**
  $$\text{Food Cost Variance} = \text{Actual Consumption} - \text{Theoretical BOM Consumption}$$
  * Identifies exact ingredient discrepancies (e.g. theoretical chicken usage based on 40 curries sold = 20 kg, but kitchen stock depleted by 23 kg $\rightarrow$ 3 kg variance flagged as prep trim loss, over-portioning, or unauthorized shrinkage).
* **Stock-in-Hand Valuations:**
  * Live valuation of Central Bulk Store vs Kitchen Line Stock in Rupees (`₹`).
  * Low-Stock & Reorder Alerts based on contracted lead times.
* **Kitchen Spoilage & Wastage Intelligence:**
  * Wastage cost categorized by reason codes: Burnt dishes, Dropped food, Expired ingredients, Prep trim.

#### D. Menu Engineering Matrix (BCG Quadrant)
Visual quadrant classification to drive intelligent menu design:
1. **Stars (High Popularity + High Margin):** Kolhapuri Chicken, Special Veg Thali $\rightarrow$ Maintain quality and promote heavily.
2. **Plowhorses (High Popularity + Low Margin):** Jowar Bhakri, Chapati, Tandoori Roti $\rightarrow$ Optimize recipe cost, modest price bumps.
3. **Puzzles (Low Popularity + High Margin):** Sol Kadhi, Kokum Sharbat, Surmai Fry $\rightarrow$ Reposition on menu or bundle with thalis.
4. **Dogs (Low Popularity + Low Margin):** Low-moving specialty items $\rightarrow$ Candidates for 86ing or retirement to reduce prep overhead.

#### E. Cash Drawer & Register Integrity (Z-Report Ledger)
* Shift-by-shift cash reconciliation table: Opening float, Cash Collected, Petty Cash Paid-Out, Safe Drops, Closing Physical Count, and exact **Over/Short Variance**.
* Microswitch audit log recording every single physical cash drawer kick, cross-referenced with authorized transaction IDs.

#### F. Natural Language "Ask Resto Intelligence"
Built-in conversational search bar allowing the owner to type direct business queries:
* *"What sold best today?"*
* *"How were sales yesterday compared to last Sunday?"*
* *"What did we spend from the cash drawer this week?"*
* *"Show all voided KOTs above ₹500."*
* Returns instant tabular and natural language responses directly extracted from local database tables.

