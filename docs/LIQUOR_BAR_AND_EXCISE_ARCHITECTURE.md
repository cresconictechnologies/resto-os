# Bar & Liquor Management Subsystem: State Excise, Compliance & Billing Architecture
## Production Technical Specification (India / Maharashtra FL-3 Standard)

**Document Version:** 1.0.0-PROD  
**Target Systems:** Bar Dispense Counter, Cash Counter Billing, Central Liquor Store, State Excise Compliance Engine  
**Regulatory Baseline:** Bombay Foreign Liquor Rules / Maharashtra State Excise (FL-3 / FLR-3 / FLR-3A / FLR-4), Pan-India State Excise & State VAT Acts  

---

## 1. Executive Summary & Legal Landscape

In India, alcoholic beverages for human consumption are **constitutionally excluded from the Goods and Services Tax (GST)** under Article 366(12A) of the Constitution of India. Consequently, restaurant bars operate under a strict dual-regulatory regime:
1. **Food & Soft Beverages:** Governed by Central/State **GST** (5% without ITC) and **FSSAI**.
2. **Alcoholic Liquor (IMFL, IFL, Beer, Wine):** Governed by **State Excise Departments** (under state licenses such as FL-3 / FLR-3 in Maharashtra, L-4/L-5 in Delhi, CL-9 in Karnataka) and **State Value Added Tax (VAT / MVAT)**.

### Zero-Tolerance Excise Policy
State Excise departments treat any discrepancy between physical bar stock and registered book stock as **illicit liquor, bootlegging, or duty evasion**. A mismatch of even two bottles can result in criminal seizure of stock, heavy compounding fines (₹25,000 to ₹1,00,000+), and suspension of the FL-3 license.

This document defines the complete operational, database, and hardware architecture to make our restaurant POS 100% excise-compliant, audit-proof, and streamlined for high-speed bar operations.

---

## 2. Core Mandatory Requirements for Bar Liquor Sales

```
+----------------------------------------------------------------------------------------------------+
|                                    STATUTORY EXCISE MANDATES                                       |
|                                                                                                    |
|  [FL-3 / FLR-3 License]      [Transport Permit - TP]      [Daily Brand Register - FLR-3A]          |
|  Valid on-premise license     Mandatory pass for every     Daily brand-wise & size-wise ledger      |
|  displayed at Cash Counter    inward wholesale bottle      Opening + TP Recd - Sales = Closing     |
|                                                                                                    |
|  [Dry Day Lockout]           [Dual Taxation (GST + VAT)]   [Monthly Return - FLR-4]                 |
|  Auto-disables liquor sales   Food on 5% GST, Liquor on    Consolidated monthly statement filed     |
|  on statutory dry days        State VAT (MVAT: 5% / 10%)   with Excise Dept by 7th of every month  |
+----------------------------------------------------------------------------------------------------+
```

### 2.1 Statutory License & Operating Constraints
1. **License Display & Permit Room Boundary:**
   - License type: **FL-3** (Hotel / Restaurant bar license for on-premise service of Foreign Liquor and Beer).
   - The license number and valid period must be printed on every bar cash memo / tax invoice.
2. **Minimum Legal Drinking Age (MLDA):**
   - Configurable per state: In Maharashtra, MLDA is **25 years** for hard spirits (IMFL/IFL) and **21 years** for mild beer and wine.
   - Cashier interface includes an age verification prompt for young patrons.
3. **Automated Dry Day Lockout:**
   - Built-in statutory dry day calendar (Republic Day Jan 26, Maharashtra Day May 1, Independence Day Aug 15, Gandhi Jayanti Oct 2, Ashadhi Ekadashi, Kartiki Ekadashi, State/National Election voting & counting days).
   - On dry days, the software **completely locks out all liquor items** from the billing menu, preventing accidental or unauthorized billing.
4. **Operating Hours Cut-Off:**
   - Configurable excise closing timer (e.g. Last order 11:00 PM, bar counter close 11:30 PM / 1:30 AM). Prevents post-hours order punching.

---

## 3. Mandatory State Excise Registers & Reports

The software must automatically generate the official excise registers in exact statutory formats ready for inspection by the Excise Sub-Inspector or downloading for the State Excise SCM Portal (`scmexcise.mahaonline.gov.in`):

### 3.1 Form FLR-3 & FLR-3A: Daily Brand-Wise Stock & Sales Register
* **Frequency:** Updated dynamically on every bill and sealed/printed **daily before closing the premises**.
* **Granularity:** Strict **Brand-Wise** and **Size-Wise** (SKU level).
* **The Universal Balance Equation:**
  $$\text{Closing Stock} = \text{Opening Stock} + \text{Receipts (via TP)} - \text{Sales} - \text{Breakage}$$

#### Form FLR-3A Layout:
| Sr. | Brand Name | Category | Bottle Size | Opening Stock | Receipts (TP No & Date) | Total Stock | Sales Today (Bottles / Pegs) | Breakage / Wastage | Closing Balance |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | Blenders Pride | IMFL Whisky | 750 ml | 14 btl + 12 pegs | 12 btl (TP-9821, 26-Oct) | 26 btl + 12 pegs | 4 btl + 18 pegs (118 pegs) | 0 | 21 btl + 19 pegs |
| 2 | Royal Challenge | IMFL Whisky | 750 ml | 8 btl + 5 pegs | 0 | 8 btl + 5 pegs | 2 btl + 10 pegs (60 pegs) | 0 | 5 btl + 20 pegs |
| 3 | Old Monk Rum | IMFL Rum | 750 ml | 6 btl + 0 pegs | 0 | 6 btl + 0 pegs | 1 btl + 15 pegs (40 pegs) | 0 | 4 btl + 10 pegs |
| 4 | Kingfisher Premium| Mild Beer | 650 ml | 48 btl | 24 btl (TP-9821, 26-Oct) | 72 btl | 28 btl | 1 btl (Dropped) | 43 btl |
| 5 | Corona Extra | Imported Beer| 330 ml | 30 btl | 0 | 30 btl | 12 btl | 0 | 18 btl |
| 6 | Sula Shiraz | Domestic Wine| 750 ml | 5 btl + 2 gls | 0 | 5 btl + 2 gls | 1 btl + 4 gls (9 gls) | 0 | 3 btl + 3 gls |

---

### 3.2 Transport Permit (TP) / Pass Inward Register
* In India, licensees can only purchase liquor from authorized wholesale distributors (FL-1). Every consignment moves with an official government **Transport Permit (TP)**.
* Storing even a single bottle without a valid TP is a criminal offense under the Prohibition Act.
* **Fields Captured on Inward Entry:**
  - Transport Permit (TP) Number & TP Issue Date
  - Wholesale Vendor Name & FL-1 License Number
  - Consignment Vehicle Number
  - State Excise Batch Number & Distillery Hologram / Barcode series
  - Case count, Bottle count, Bottle capacity (750ml, 375ml, 180ml, 650ml, 330ml, Kegs)
  - Wholesale Invoice Number & Purchase Value

---

### 3.3 Breakage, Spoilage & Wastage Register
* Accidental bottle breakage, cork-spoiled wine, or draft beer line purging must be legally accounted for; otherwise, missing volume is treated as unaccounted black-market sales.
* **Mandatory Capture:**
  - Date & Timestamp
  - Brand Name & Bottle Size
  - Volume Lost (e.g. 1 Full 750ml bottle, or 250ml draft purge)
  - Reason Code (`DROPPED_BY_STAFF`, `DEFECTIVE_CORK_SPOILED`, `DRAFT_LINE_CLEANING`, `DELIVERY_INWARD_DAMAGE`)
  - Staff / Bartender Name & Mandatory Manager / Licensee Override PIN.

---

### 3.4 Monthly Excise Return (Form FLR-4 / SCM Return)
* Submitted to the Superintendent / District Inspector of Prohibition and Excise by the **7th day of every month**.
* Aggregates month-to-date performance across 4 statutory categories:
  1. **IMFL (Spirits):** Whisky, Rum, Vodka, Gin, Brandy (in Bulk Litres / Cases / Bottles)
  2. **Beer (Fermented):** Strong Beer (>5% v/v) and Mild Beer (<=5% v/v)
  3. **Wine (Fermented Fruit):** Domestic and Imported Still/Sparkling Wines
  4. **Imported Foreign Liquor (BIO / Bottled in Origin):** Scotch, Tequila, Liqueurs
* Captures Total Opening + Total TP Inward - Total Monthly Sales - Total Breakages = Month-End Closing Stock.

---

### 3.5 Inspection / Visit Book Digital Log
* Under excise law, an Inspection Book must be physically present at the bar.
* The software provides a digital log for recording visits by the Excise Sub-Inspector, recording date, officer name, designation, remarks, and audit sign-off.

---

## 4. Peg Measurement & Dispense Mathematics

The bar engine operates on dual units: **Stock Unit (Bottles/Cases)** and **Dispense Unit (Milliliters/Pegs)**.

```
       1 Bottle (750 ml)
               │
   ┌───────────┴───────────┐
   ▼                       ▼
Small Peg (30 ml)      Large Peg (60 ml)
[25 Pegs per bottle]   [12.5 Pegs per bottle]
```

### 4.1 Measurement Conversion Table

| Category | Container / SKU | Base Volume (ml) | Standard Pours Available | Conversion Math |
| :--- | :--- | :--- | :--- | :--- |
| **Spirits (IMFL / IFL)** | Quart Bottle | 750 ml | • 30 ml (Small Peg)<br>• 60 ml (Large / Patiala Peg)<br>• 90 ml (Triple Peg)<br>• Full Bottle (750 ml) | $750 / 30 = 25\text{ Small Pegs}$<br>$750 / 60 = 12.5\text{ Large Pegs}$ |
| **Spirits (Imported)** | Liter Bottle | 1,000 ml | • 30 ml Small Peg<br>• 60 ml Large Peg | $1000 / 30 = 33.33\text{ Pegs}$ |
| **Spirits (Pint / Nip)**| Pint (375 ml)<br>Nip (180 ml) | 375 ml<br>180 ml | • Full Bottle<br>• Pegs | $375 / 30 = 12.5\text{ Pegs}$<br>$180 / 30 = 6\text{ Pegs}$ |
| **Bottled Beer** | Large Bottle<br>Pint Bottle<br>Can | 650 ml<br>330 ml<br>500 ml | • Full Unit (Bottle / Can) | 1 Unit = 1 Bottle (No peg split) |
| **Draught Beer (Kegs)**| Standard Keg<br>Large Keg | 30,000 ml (30 L)<br>50,000 ml (50 L) | • 330 ml (Mug)<br>• 500 ml (Glass/Stein)<br>• 1,500 ml (Pitcher)<br>• 3,000 ml (Beer Tower) | $30,000 / 330 = 90.9\text{ Mugs}$<br>$30,000 / 1500 = 20\text{ Pitchers}$ |
| **Wine** | Standard Bottle | 750 ml | • 150 ml (Glass)<br>• 750 ml (Full Bottle) | $750 / 150 = 5\text{ Glasses per bottle}$ |
| **Cocktails** | Multi-spirit BOM | Variable | Recipe Bill of Materials (BOM) | Dynamic deduction (e.g. LIIT = $5 \times 15\text{ml}$) |

### 4.2 Open Bottle vs Sealed Bottle Tracking
To prevent bar shrinkage and bartender free-pouring:
* **Sealed Stock:** Counted in whole bottles in the Central Liquor Godown and behind the bar counter.
* **Active Open Bottle Pool:** When the first 30ml peg of a new bottle is billed:
  1. The software automatically decrements 1 whole sealed bottle from stock.
  2. Initializes an **Open Bottle Ledger** with `volume_remaining_ml = 750 - 30 = 720 ml`.
  3. Subsequent peg sales deduct from `volume_remaining_ml`.
  4. When `volume_remaining_ml` reaches $< 30\text{ ml}$, the bottle is marked empty, and the next bottle is cracked open.
  5. Bartenders can never have more than 1 active open bottle of the same SKU on the rail without supervisor override.

---

## 5. Smart Order Routing: BOT (Bar Order Ticket) vs KOT

When a table places a mixed order (e.g., Butter Chicken, Naan, and Blenders Pride 60ml):
* The food items print on the **Kitchen Thermal Printer (KOT)**.
* The liquor items print on the **Bar Thermal Printer (BOT - Bar Order Ticket)** at the dispense station.

```text
========================================
            BAR ORDER TICKET (BOT)
Table: T7 (Ground Floor)      BOT #: 058
Date: 26-Oct-2026 21:05       Server: Rahul
========================================
QTY  ITEM                      POUR     
----------------------------------------
 2   Blenders Pride Whisky     60 ml (Large)
     >> Mixer: Soda & Ice               
 1   Kingfisher Premium Beer   650 ml   
 1   Sula Shiraz Red Wine      Glass (150ml)
========================================
```

---

## 6. Dual Taxation & Indian Bill Splitting (GST vs State VAT)

### 6.1 Tax Separation Rule
* **Food & Non-Alcoholic Beverages:** Attracts **GST @ 5%** (2.5% CGST + 2.5% SGST) with FSSAI and GSTIN credentials.
* **Alcoholic Beverages:** Attracts **State VAT (MVAT)** (e.g. 5% or 10% in Maharashtra) with State Excise License No. (FL-3) and VAT TIN.

### 6.2 Compliant Dual-Tax Receipt Layout (80mm)
```text
================================================
                 RASA SAHYADRI
      RESTAURANT & PERMIT ROOM (BAR)
       Lane 6, North Main Road, Pune
            Phone: 020 4123 4501
       GSTIN: 27AAKFR4621M1Z5
       FSSAI: 11523034000412
    EXCISE LIC (FL-3): FL3-PUN-KP-0412
       MVAT TIN: 27912345678V
================================================
TAX INVOICE: KPB3/2026/009008
Date: 26-Oct-2026 21:45       Table: T7
Cashier: Counter 1            Guests: 2
------------------------------------------------
PART A: FOOD & BEVERAGES (GST)
ITEM                       QTY    RATE    AMOUNT
Chicken Sukka                1  340.00    340.00
Jowar Bhakri                 2   35.00     70.00
------------------------------------------------
Food Sub-total:                           410.00
CGST @2.5%:                                10.25
SGST @2.5%:                                10.25
Food Total (Incl. GST):                   430.50
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
Round off:                                 -0.50
GRAND TOTAL:                        Rs. 1,186.00
One Thousand One Hundred Eighty Six Rupees only
------------------------------------------------
Payment Mode: UPI (Received)
================================================
        Statutory: Alcohol Consumption Is 
             Injurious To Health
================================================
```

---

## 7. Concrete PostgreSQL Database Schema for Bar & Excise

```sql
-- 1. Liquor Brands & SKUs Master
CREATE TABLE liquor_brands (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    brand_name VARCHAR(120) NOT NULL,
    category VARCHAR(50) NOT NULL, -- 'IMFL_WHISKY', 'IMFL_RUM', 'BEER_MILD', 'BEER_STRONG', 'WINE', 'IFL_SCOTCH'
    state_excise_code VARCHAR(50) NOT NULL, -- Government excise portal brand code
    bottle_size_ml INT NOT NULL, -- 750, 375, 180, 650, 330, 30000 (keg)
    strength_percent NUMERIC(4,2), -- e.g. 42.8% for IMFL, 5.0% for Beer
    mrp_price NUMERIC(10,2) NOT NULL,
    vat_rate_percent NUMERIC(4,2) DEFAULT 5.00, -- MVAT rate
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Transport Permits (TP) / Inward Wholesale Receipts
CREATE TABLE liquor_transport_permits (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    tp_number VARCHAR(80) NOT NULL, -- Transport Permit number from State Excise
    tp_date DATE NOT NULL,
    supplier_fl1_license VARCHAR(80) NOT NULL,
    vehicle_number VARCHAR(30),
    invoice_number VARCHAR(80) NOT NULL,
    total_cases INT NOT NULL,
    total_bottles INT NOT NULL,
    total_amount NUMERIC(12,2) NOT NULL,
    verified_by_user UUID NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_tenant_tp UNIQUE (tenant_id, tp_number)
);

-- 3. Transport Permit Itemized Lines
CREATE TABLE liquor_tp_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tp_id UUID NOT NULL REFERENCES liquor_transport_permits(id) ON DELETE CASCADE,
    brand_id UUID NOT NULL REFERENCES liquor_brands(id),
    batch_number VARCHAR(50) NOT NULL,
    manufacturing_date DATE,
    cases_received INT NOT NULL,
    bottles_per_case INT NOT NULL,
    total_bottles_received INT NOT NULL,
    unit_purchase_cost NUMERIC(10,2) NOT NULL
);

-- 4. Bar Stock Ledger (Perpetual Brand-Wise Balance)
CREATE TABLE bar_stock_ledger (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    brand_id UUID NOT NULL REFERENCES liquor_brands(id),
    sealed_bottles_count INT NOT NULL DEFAULT 0,
    open_bottle_remaining_ml INT NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_tenant_brand_stock UNIQUE (tenant_id, brand_id)
);

-- 5. Daily Excise Register Snapshot (Form FLR-3A)
CREATE TABLE daily_excise_flr3a_register (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    register_date DATE NOT NULL,
    brand_id UUID NOT NULL REFERENCES liquor_brands(id),
    opening_sealed_bottles INT NOT NULL,
    opening_open_ml INT NOT NULL,
    receipts_tp_bottles INT NOT NULL DEFAULT 0,
    sales_total_ml INT NOT NULL DEFAULT 0,
    sales_bottles_equivalent NUMERIC(8,2) NOT NULL DEFAULT 0,
    breakage_bottles INT NOT NULL DEFAULT 0,
    breakage_ml INT NOT NULL DEFAULT 0,
    closing_sealed_bottles INT NOT NULL,
    closing_open_ml INT NOT NULL,
    sealed_status BOOLEAN DEFAULT FALSE, -- Locked at day close
    sealed_at TIMESTAMPTZ,
    sealed_by_user UUID,
    CONSTRAINT uq_daily_brand_flr3a UNIQUE (tenant_id, register_date, brand_id)
);

-- 6. Breakage & Spoilage Log
CREATE TABLE liquor_breakage_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    brand_id UUID NOT NULL REFERENCES liquor_brands(id),
    breakage_date DATE NOT NULL,
    bottle_count INT DEFAULT 0,
    volume_ml INT DEFAULT 0,
    reason_code VARCHAR(50) NOT NULL, -- 'DROPPED_BY_STAFF', 'CORK_SPOILED', 'DRAFT_LINE_PURGE'
    witness_staff_name VARCHAR(100),
    manager_override_pin_used BOOLEAN DEFAULT TRUE,
    authorized_by_user UUID NOT NULL,
    remarks TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 7. Dry Days Calendar Table
CREATE TABLE statutory_dry_days (
    id SERIAL PRIMARY KEY,
    state_code VARCHAR(10) NOT NULL, -- e.g. 'MH' for Maharashtra
    dry_date DATE NOT NULL,
    occasion_name VARCHAR(100) NOT NULL, -- e.g. 'Gandhi Jayanti', 'Republic Day'
    is_mandatory BOOLEAN DEFAULT TRUE,
    CONSTRAINT uq_state_dry_date UNIQUE (state_code, dry_date)
);
```

---

## 8. Summary of Mandatory Bar Features Built into the 3-Desktop POS

1. **At Cash Counter 1 & 2:**
   - Dual-tax bill computation separating Food (5% GST) and Alcohol (State VAT).
   - Instant dispatch of Bar Order Tickets (BOT) to the bar dispense thermal printer.
   - Automated Dry Day warning/lockout preventing liquor sales on dry days.
   - Legal age verification check for bar tables.
2. **At Store & Admin PC (Desktop 3):**
   - Inward entry of Transport Permits (TPs) from wholesale distributors.
   - Automatic 1-click generation of **Form FLR-3A Daily Brand-Wise Register** ready for Excise Sub-Inspector inspections.
   - Monthly **Form FLR-4 Abstract Statement** generation for submission to the District State Excise Office.
   - Breakage and wastage reporting with supervisor PIN authorization.
   - Draft beer line flush and cocktail recipe BOM management.
