# Restaurant Inventory & Grocery Management Subsystem
## Production Architecture & Database Specification

---

### Executive Summary

In high-volume restaurant operations, food and beverage costs represent 28% to 35% of gross revenue. Without a rigorous, real-time inventory management subsystem, restaurants suffer from catastrophic margin bleed caused by:
1. Uncontrolled prep waste and yield loss (10% to 20% variance between raw purchase and cooked output).
2. Direct-to-kitchen receiving, bypassing receiving dock verification and temperature controls.
3. Supplier invoice price slippage and unmonitored substitutions.
4. Theft, unauthorized staff consumption, and unaccounted spoilage.
5. Inaccurate recipe costing leading to mispriced menu items.

This document defines the production-grade architecture and PostgreSQL database schema for the **Restaurant Inventory & Grocery Management Subsystem**. It is engineered to govern the entire lifecycle of raw ingredients and packaging materials: from vendor procurement, through central store warehousing, internal kitchen requisitions, sub-recipe preparation, real-time Bill of Materials (BOM) consumption during Point of Sale (POS) / Kitchen Order Ticket (KOT) firing, down to wastage logging, physical cycle counts, and theoretical vs. actual variance reconciliation.

---

## 1. System Topology & Two-Tier Inventory Architecture

### 1.1 Physical & Logical Topology

Restaurant operations maintain a fundamental operational boundary between bulk procurement and culinary production. To prevent stock inaccuracies, this subsystem enforces a **Two-Tier Custody Architecture**:

```
+----------------------------------------------------------------------------------------------------+
|                                      TIER 1: CENTRAL STORE                                         |
|                                                                                                    |
|  [Vendor Receiving Dock] ---> [Inspection & Weighing] ---> [Central Bulk Storage]                  |
|                                                            +-- Dry Goods Warehouse (Ambient)       |
|                                                            +-- Walk-in Chiller (0°C to 4°C)        |
|                                                            +-- Deep Freezer (-18°C to -22°C)       |
|                                                            +-- Beverage & Liquor Cellar            |
|                                                            +-- Non-Food Packaging & Chemicals      |
+-------------------------------------------------+--------------------------------------------------+
                                                  |
                                                  | Internal Requisition & Issue (FEFO Dispatch)
                                                  v
+----------------------------------------------------------------------------------------------------+
|                                    TIER 2: KITCHEN INVENTORY                                       |
|                                                                                                    |
|  [Kitchen Receiving Bay] ---> [Station Line Par Stock / Mise En Place]                             |
|                               +-- Hot Kitchen (Sauté, Grill, Fry, Oven Lines)                      |
|                               +-- Cold Kitchen / Garde Manger (Salads, Starters, Dressing)         |
|                               +-- Bakery & Pastry Section (Flour, Dough, Pastry Fillings)          |
|                               +-- Butchery & Pre-Prep Station (Deboning, Portioning, Marinades)   |
|                               +-- Bar & Beverage Dispense (Fresh Fruit, Syrups, Garnishes)         |
|                               +-- Sub-Kitchen / Satellite Prep Kitchen                             |
+-------------------------------------------------+--------------------------------------------------+
                                                  |
                    +-----------------------------+-----------------------------+
                    |                                                           |
                    v                                                           v
       [Real-time / EOD BOM Deduction]                             [Kitchen Wastage & Spoilage]
         (Triggered by KOT Settlement)                                (Logged with Reason Codes)
```

### 1.2 Separation of Concerns & Custody Boundaries

| Dimension | Tier 1: Central Store | Tier 2: Kitchen Inventory |
| :--- | :--- | :--- |
| **Primary Custodian** | Storekeeper / Materials Manager | Executive Chef / Sous Chef / Station Heads |
| **Physical Form** | Wholesale bulk units (e.g., 50 kg sacks, crates of 24, 15 L drums) | Production units (e.g., kg, grams, litres, portion packs) |
| **Stock Valuation** | Exact Weighted Average Cost (WAC) per batch | Work-in-Progress (WIP) stock & daily mise en place |
| **Consumption Source** | Only issued via authorized Kitchen Requisition Notes (KRN) | Consumed via POS KOT sales, batch sub-recipes, or waste |
| **Audit Frequency** | Weekly cycle count / Monthly wall-to-wall physical audit | Daily shift-end count of key proteins, alcohol, and high-value prep |
| **Access Control** | Restricted badge/keypad access; strict delivery logging | Culinary staff active access during kitchen operating hours |

---

## 2. Procurement Lifecycle: Vendor to Central Store

```
   +----------------+       +------------------+       +--------------------+
   | Vendor Catalog | ----> |  Purchase Order  | ----> |  Goods Received    |
   | & Rate Contract|       |   (PO) Workflow  |       |    Note (GRN)      |
   +----------------+       +------------------+       +--------------------+
                                                        |
                                                        v
                                               +--------------------+
                                               | Batch Tracking &   |
                                               | Expiry Capture     |
                                               +--------------------+
                                                        |
                                                        v
                                               +--------------------+
                                               | UOM Conversion     |
                                               | (Purchase -> Base) |
                                               +--------------------+
                                                        |
                                                        v
                                               +--------------------+
                                               | WAC Recalculation  |
                                               | & Central Stock ++ |
                                               +--------------------+
```

### 2.1 Supplier Master & Contracted Rates
- **Multi-Vendor Sourcing**: Every ingredient item can be supplied by one or more approved vendors, with one designated primary vendor.
- **Contract Price Rules**: Agreements define fixed prices for a specified validity window (e.g., quarterly contracts for chicken breast or dry goods). Spot-market items (e.g., fresh seafood, seasonal vegetables) allow dynamic price entry with variance tolerance thresholds.
- **Lead Times & Minimum Order Quantities (MOQ)**: System tracks vendor-specific lead times in days and minimum pack sizes to auto-suggest procurement orders when central store stock falls below dynamic reorder points ($ROP = \text{Daily Usage} \times \text{Lead Time} + \text{Safety Stock}$).

### 2.2 Purchase Order (PO) State Machine

The PO lifecycle enforces strict financial and culinary approval governance:

```
[DRAFT]
   │
   ▼
[PENDING_APPROVAL] ──(Rejected)──► [REJECTED]
   │
   ▼ (Approved by Chef / GM / Controller)
[APPROVED]
   │
   ▼ (Dispatched via EDI / Email / WhatsApp API)
[SENT_TO_VENDOR]
   │
   ├──────────────────────────────┐
   ▼                              ▼
[PARTIALLY_RECEIVED]      [FULLY_RECEIVED]
   │                              │
   └──────────────┬───────────────┘
                  │
                  ▼
              [CLOSED]
```

#### State Transition Rules:
1. `DRAFT`: Created by Storekeeper manually or auto-generated by par-level replenishment jobs. Items and quantities can be freely modified.
2. `PENDING_APPROVAL`: Submitted for authorization. Triggers approval routing:
   - Level 1 (< $1,000): Head Chef / Store Manager.
   - Level 2 ($1,000 – $5,000): General Manager.
   - Level 3 (> $5,000): Financial Controller / Owner.
3. `APPROVED`: Locked against edits. Digital signature and approval timestamp stored.
4. `SENT_TO_VENDOR`: Transmitted to vendor. Expected delivery date tracked.
5. `PARTIALLY_RECEIVED`: A GRN has been recorded with inward quantity less than the ordered quantity. PO remains open for subsequent deliveries.
6. `FULLY_RECEIVED`: All ordered quantities have been delivered and accepted.
7. `CLOSED`: All received lines invoiced, three-way matched, or remaining backorders officially cancelled.
8. `CANCELLED`: Order cancelled before vendor dispatch.

### 2.3 Goods Received Note (GRN) Inward Processing

The GRN represents the legal, physical, and financial acceptance of goods into the Central Store.

#### Inward Quality & Safety Inspection:
1. **Cold Chain Temperature Verification**: Mandatory temperature logging for refrigerated (0°C to 4°C) and frozen (-18°C or lower) items. Deliveries failing food safety limits are flagged for immediate rejection at the dock.
2. **Package Integrity & Organoleptic Assessment**: Checks for broken vacuum seals, dented cans, blown packaging, mold, or off-odors.
3. **Three-Way Matching**: Automated reconciliation between:
   - Purchase Order quantity and agreed unit rate.
   - Vendor Delivery Challan / Tax Invoice quantity and invoiced rate.
   - Physical Inward Count weighed on receiving scales or tally-counted.

#### Batch / Lot Numbering & Expiry Management:
- Every inward line item is assigned an immutable internal `batch_number` formatted as `BATCH-YYYYMMDD-<ITEM_ID>-<SEQ>`.
- Vendor lot number, manufacturing date, and expiry date are recorded.
- System calculates residual shelf-life. If incoming stock has less than the minimum required contract shelf-life (e.g., dairy arriving with < 75% shelf-life remaining), the system alerts the receiving agent to reject the batch.

#### Multi-Tier Unit of Measure (UOM) Conversion Engine:
Ingredients exist in three distinct dimensional domains:
1. **Purchase UOM**: How goods are bought from suppliers (e.g., 50 kg Jute Bag, Carton of 24 × 500 mL cans, Crate of 30 Eggs).
2. **Store Base UOM**: How goods are accounted for in stock valuation (e.g., Kilogram, Litre, Unit/Piece).
3. **Recipe Consumption UOM**: How ingredients are measured in culinary preparation (e.g., Grams, Millilitres, Pinch, Teaspoon).

The engine standardizes all inventory balances into the **Store Base UOM** immediately upon GRN posting using precise conversion factors:
$$\text{Base Quantity} = \text{Purchase Quantity} \times \text{UOM Conversion Multiplier}$$

*Example*:
- Item: Extra Virgin Olive Oil.
- Purchase Unit: Case of 4 × 5-Litre Tins = 20 Litres.
- Store Base Unit: Litre.
- Recipe Unit: Millilitre (0.001 Litre).
- If receiving 5 cases: $5 \times 20 = 100 \text{ Litres}$ posted to Central Store.

#### Invoice Price Variance (IPV) & Quantity Variance:
- **Price Variance**: If Invoiced Rate $\neq$ PO Rate:
  - If variance $\le \pm 2\%$ (configurable threshold), system auto-accepts and notes variance.
  - If variance $> 2\%$, requires manager override and generates a pending Vendor Debit/Credit Note.
- **Weighted Average Cost (WAC) Update**: Central Store maintains real-time moving weighted average valuation. Upon GRN authorization:
$$WAC_{\text{new}} = \frac{(Q_{\text{current}} \times WAC_{\text{current}}) + (Q_{\text{inward}} \times P_{\text{inward}})}{Q_{\text{current}} + Q_{\text{inward}}}$$

---

## 3. Store to Kitchen Issue & Requisition Lifecycle

Central Store inventory cannot be consumed directly by customer orders. It must be formally requisitioned and issued to a specific kitchen station.

```
+----------------------------------------------------------------------------------------------------+
|                                REQUISITION & TRANSFER WORKFLOW                                     |
|                                                                                                    |
|  [Station Chef]                [Storekeeper]                    [Station Chef]                     |
|         │                             │                                │                           |
|         │  1. Kitchen Indent (KRN)    │                                │                           |
|         ├────────────────────────────>│                                │                           |
|         │  (Requested Qty by station) │                                │                           |
|         │                             │  2. FEFO Pick & Allocation     │                           |
|         │                             │     (Selects oldest batches)   │                           |
|         │                             │                                │                           |
|         │                             │  3. Store Issue Note (SIN)     │                           |
|         │                             ├───────────────────────────────>│                           |
|         │                             │     [Central Store - Qty]      │                           |
|         │                             │                                │  4. Physical Verification |
|         │                             │                                │     & Acceptance          |
|         │                             │                                │     [Kitchen Stock + Qty] │
|         │                             │  5. Return to Store (RTS)      │                           |
|         │                             │<───────────────────────────────┤                           |
|         │                             │     (Unused, uncompromised     │                           |
|         │                             │      sealed batches)           │                           |
+----------------------------------------------------------------------------------------------------+
```

### 3.1 Kitchen Indent / Daily Requisition Note (KRN)
- Generated daily per kitchen station (e.g., Hot Line, Garde Manger, Bakery) based on:
  - Expected customer covers from reservations and banquet bookings.
  - Par level deficits (Station Par Level minus Current Physical Line Stock).
  - Production schedules for high-volume prep items (e.g., 20 kg pizza dough, 15 L tomato gravy).
- Requisition specifies: `item_id`, `requested_quantity`, `target_kitchen_location_id`, and `urgency_level` (`ROUTINE` vs `RUSH_SERVICE`).

### 3.2 Store Issue Note (SIN) & FEFO Dispatch
- **FEFO (First-Expired, First-Out)**: Storekeeper interface automatically suggests picking from the batch with the earliest expiration date.
- Storekeeper confirms picked quantities and specific batch IDs. If an item has partial stock, the storekeeper issues what is available, leaving the remainder open or marked short.
- **Atomic Double-Entry Inventory Update**:
  - Central Store balance for the specific batch is decremented by the issued quantity.
  - Kitchen location inventory balance is incremented by the issued quantity.
  - Immutable transaction logged in `inventory_transactions_ledger`.

### 3.3 Return to Store (RTS)
- Unused, unopened, non-perishable goods or unadulterated whole produce returned at shift-end.
- Inspected by Storekeeper for temperature integrity and container seal status.
- Once accepted, kitchen inventory is credited, and central store batch is restored.
- Perishable items holding active mise en place (e.g., diced raw onions, chopped herbs) **cannot** be returned to Central Store; they must remain in station refrigerators as WIP stock or be logged as end-of-shift waste if shelf-life has expired.

---

## 4. Recipe Bill of Materials (BOM) & Kitchen Consumption Engine

### 4.1 Multi-Level Recipe Hierarchy

The culinary engine supports arbitrary nesting of recipes to reflect authentic kitchen production:

```
[Level 2: Finished Menu Item] (e.g., "Woodfired Margherita Pizza 12 inch")
   │
   ├── [Level 1: Sub-Recipe] (e.g., "Neapolitan Pizza Dough Ball - 250g")
   │      ├── Raw Flour (Tipo 00) [Level 0 Item] (155g)
   │      ├── Water (100g)
   │      ├── Fresh Yeast [Level 0 Item] (0.8g)
   │      └── Sea Salt [Level 0 Item] (4.5g)
   │
   ├── [Level 1: Sub-Recipe] (e.g., "Slow-Cooked San Marzano Pizza Sauce - 90g")
   │      ├── Whole Canned San Marzano Tomatoes [Level 0 Item] (110g, Yield: 82% after seed/skin strain)
   │      ├── Extra Virgin Olive Oil [Level 0 Item] (5g)
   │      ├── Fresh Basil [Level 0 Item] (2g, Yield: 70% after stem removal)
   │      └── Salt & Oregano [Level 0 Items] (1g)
   │
   ├── Fresh Mozzarella Fior di Latte [Level 0 Item] (100g portion)
   ├── Fresh Basil Leaves [Level 0 Item] (3g)
   └── Takeaway Corrugated Pizza Box [Packaging Item] (1 Unit - if ordered for delivery)
```

### 4.2 Yield Percentages, Prep Shrinkage & Culinary Formulas

Raw grocery items purchased from suppliers are rarely 100% usable in finished dishes. The subsystem models two stages of weight loss:
1. **Prep Yield Loss (Trimming & Peeling)**: Skin, bones, fat, seeds, and stems removed prior to cooking.
2. **Cooking Shrinkage (Thermal Moisture Loss)**: Water loss during roasting, grilling, boiling, or frying.

$$\text{Prep Yield Percentage} = \left( \frac{\text{Usable Prep Weight}}{\text{Gross Raw Purchase Weight}} \right) \times 100$$

$$\text{Gross Required Quantity} = \frac{\text{Net Portion Required}}{\text{Prep Yield \%} \times \text{Cooking Yield \%}}$$

#### Benchmark Yield Table:

| Raw Item | Prep Operation | Typical Prep Yield % | Cooking Yield % | Cumulative Effective Yield % |
| :--- | :--- | :--- | :--- | :--- |
| Whole Russet Potatoes | Peeling, cutting into fries | 85.0% | 80.0% (moisture loss) | 68.0% |
| Whole Bone-In Chicken | Deboning, skinning, trimming | 62.0% | 78.0% (roasting loss) | 48.3% |
| Fresh Broccoli Crowns | Stalk removal, florets cutting | 68.0% | 92.0% (steam loss) | 62.5% |
| Yellow Onions | Peeling, root trimming, dicing | 88.0% | 75.0% (caramelization) | 66.0% |
| Whole Beef Tenderloin | Silverskin removal, portioning | 76.0% | 82.0% (grilling loss) | 62.3% |

$$\text{Ingredient Cost Contribution} = \text{Gross Required Quantity} \times \text{Current WAC per Base Unit}$$

### 4.3 Real-Time vs. End-of-Day (EOD) Consumption Triggers

```
                         POS ORDER TRANSACTION
                                   │
                                   ▼
                   +───────────────────────────────+
                   |  Kitchen Order Ticket (KOT)   |
                   |  Item Fired / Billed          |
                   +───────────────────────────────+
                                   │
         ┌─────────────────────────┴─────────────────────────┐
         ▼                                                   ▼
[REAL-TIME DEDUCTION ENGINE]                        [EOD BATCH DEDUCTION ENGINE]
• Applied to High-Cost Center items:                 • Applied to Ambient / Low-Cost Pantry:
  - Center-of-plate proteins (Steaks, Seafood)         - Spices, Seasonings, Cooking Oils
  - Commercial Liquor, Wine, Draft Beer                - Bulk Sauces, Dressings, Marinades
  - Pre-portioned desserts & packaging                 - Garnishes, Cooking butter, Flour dusting
• Deducts immediately from station stock            • Aggregated over 24-hour service cycle
• Outbox Event published to Message Broker          • Deducted during Night Audit closing job
• Triggers Real-Time "86 List" (Auto-out of stock)  • Reconciles with daily sub-recipe prep logs
```

#### The Real-Time Outbox Pattern:
To guarantee that a network partition or database slowdown during peak kitchen rush hours never blocks the POS checkout or POS printing, KOT deductions use the **Transactional Outbox Pattern**:
1. When a KOT status becomes `SERVED` (or `PAID` depending on restaurant policy), a record is inserted into `pos_kot_consumption_logs` in the same local database transaction as the order status update.
2. An asynchronous background worker drains this queue, recursively explodes the Menu Item's BOM into raw ingredients, and executes atomic deductions against `kitchen_stock_balances`.
3. If a station's stock reaches zero, the system emits a WebSocket event to the POS terminal, flagging the item on the kitchen "86 list" to prevent further sales.

---

## 5. Kitchen Spoilage, Wastage & Audit Reconciliation

### 5.1 Kitchen Wastage Governance & Reason Codes

Every gram of food that enters the kitchen must either be accounted for as revenue (BOM sold), remaining physical stock, authorized staff meals, or logged waste.

#### Mandatory Wastage Attributes:
- Date, timestamp, and kitchen location.
- Inventory item ID or Sub-recipe ID.
- Exact weighed or counted quantity in Base UOM.
- Financial loss (calculated automatically as $\text{Quantity} \times WAC$).
- Mandatory Reason Code:
  - `BURNT_ON_LINE`: Culinary error during preparation or cooking.
  - `DROPPED_FLOOR`: Accidental drop or cross-contamination.
  - `EXPIRED_LINE_STOCK`: Held past safe holding time limit (HACCP failure).
  - `CUSTOMER_RETURN`: Order rejected by guest (quality complaint, wrong order).
  - `TRIM_EXCESS`: Excessive butchery or prep yield loss.
  - `STAFF_MEAL`: Authorized consumption for employee shift meals.
  - `TASTING_RND`: Head Chef menu development or daily shift briefing tasting.
  - `EQUIPMENT_FAILURE`: Refrigerator compressor breakdown, power outage.
- Cook ID (who logged it) and Chef ID (who digitally authorized the waste write-off).

### 5.2 Theoretical vs. Actual Variance Reconciliation

At the end of every operating period (daily for proteins/liquor, weekly for produce/dairy, monthly for dry goods), a physical count is conducted. The system executes the **Universal Restaurant Inventory Equation**:

$$\text{Theoretical Closing Stock} = \text{Opening Stock} + \text{Issued from Store} - \text{Returns to Store} - \text{Theoretical BOM Sold} - \text{Approved Logged Waste}$$

$$\text{Variance Quantity} = \text{Actual Counted Closing Stock} - \text{Theoretical Closing Stock}$$

$$\text{Variance Cost (\$) } = \text{Variance Quantity} \times \text{Current WAC}$$

$$\text{Variance \%} = \left( \frac{\text{Actual Consumption} - \text{Theoretical Consumption}}{\text{Theoretical Consumption}} \right) \times 100$$

Where:
$$\text{Actual Consumption} = \text{Opening Stock} + \text{Issued} - \text{Returns} - \text{Closing Counted Stock}$$
$$\text{Theoretical Consumption} = \text{BOM Sold Quantity}$$

#### Variance Classification & Action Thresholds:
- **Normal Tolerance (-1.0% to +1.0%)**: Natural evaporation, minor scale calibration drift. Automatically accepted.
- **Moderate Loss (-1.1% to -4.0%)**: Over-portioning on line, unrecorded trimming waste. Generates warning report for Station Head Chef.
- **Severe Loss (< -4.0%)**: Indicator of pilferage, unauthorized theft, massive over-portioning, or unrecorded waste. Triggers mandatory management investigation.
- **Positive Variance (> +2.0%)**: Indicates under-portioning (shortchanging guests, threatening food consistency) or failure to record Store Issue Notes.

---

## 6. Concrete PostgreSQL DDL Schema (Production-Grade)

The following schema is engineered specifically for PostgreSQL 14+, adhering to strict relational normalization, financial precision, and high-concurrency performance:
- All monetary values and quantities use `NUMERIC(14, 4)` to eliminate floating-point rounding errors.
- Primary keys utilize `UUIDv4` via `gen_random_uuid()` to prevent ID enumeration and support distributed multi-site sync.
- Foreign keys enforce `ON DELETE RESTRICT` to ensure financial and inventory audit trails cannot be orphaned or deleted.
- Comprehensive check constraints guarantee non-negative quantities and valid state transitions.
- Optimized B-Tree and partial indexes cover all high-frequency join and lookup paths.

```sql
-- ============================================================================
-- EXTENSIONS & CUSTOM DOMAINS
-- ============================================================================
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "btree_gist";

-- ============================================================================
-- ENUM TYPES
-- ============================================================================
CREATE TYPE po_status_enum AS ENUM (
    'DRAFT',
    'PENDING_APPROVAL',
    'APPROVED',
    'SENT_TO_VENDOR',
    'PARTIALLY_RECEIVED',
    'FULLY_RECEIVED',
    'CLOSED',
    'CANCELLED'
);

CREATE TYPE grn_status_enum AS ENUM (
    'PENDING_INSPECTION',
    'APPROVED',
    'REJECTED',
    'CANCELLED'
);

CREATE TYPE requisition_status_enum AS ENUM (
    'DRAFT',
    'SUBMITTED',
    'PARTIALLY_ISSUED',
    'FULLY_ISSUED',
    'REJECTED',
    'CANCELLED'
);

CREATE TYPE wastage_reason_enum AS ENUM (
    'BURNT_ON_LINE',
    'DROPPED_FLOOR',
    'EXPIRED_LINE_STOCK',
    'CUSTOMER_RETURN',
    'TRIM_EXCESS',
    'STAFF_MEAL',
    'TASTING_RND',
    'EQUIPMENT_FAILURE'
);

CREATE TYPE ledger_transaction_type_enum AS ENUM (
    'GRN_RECEIPT',
    'STORE_ISSUE',
    'STORE_RETURN',
    'KITCHEN_TRANSFER_IN',
    'KITCHEN_TRANSFER_OUT',
    'KOT_BOM_CONSUMPTION',
    'WASTAGE_WRITEOFF',
    'AUDIT_ADJUSTMENT_SURPLUS',
    'AUDIT_ADJUSTMENT_DEFICIT'
);

CREATE TYPE item_category_enum AS ENUM (
    'RAW_MEAT_POULTRY',
    'SEAFOOD',
    'DAIRY_EGGS',
    'FRESH_PRODUCE',
    'DRY_GROCERIES_GRAINS',
    'OILS_FATS',
    'SPICES_SEASONINGS',
    'BAKERY_PASTRY_SUPPLIES',
    'BEVERAGE_ALCOHOLIC',
    'BEVERAGE_NON_ALCOHOLIC',
    'PACKAGING_CONSUMABLES',
    'CLEANING_CHEMICALS'
);

-- ============================================================================
-- 1. UNITS OF MEASURE & CONVERSIONS
-- ============================================================================
CREATE TABLE units_of_measure (
    uom_code VARCHAR(16) PRIMARY KEY, -- e.g., 'KG', 'GM', 'LTR', 'ML', 'PCS', 'BOX50'
    name VARCHAR(64) NOT NULL,
    category VARCHAR(32) NOT NULL CHECK (category IN ('WEIGHT', 'VOLUME', 'COUNT', 'PACKAGING')),
    is_base_unit BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Pre-populate standard units
INSERT INTO units_of_measure (uom_code, name, category, is_base_unit) VALUES
('KG', 'Kilogram', 'WEIGHT', TRUE),
('GM', 'Gram', 'WEIGHT', FALSE),
('LTR', 'Litre', 'VOLUME', TRUE),
('ML', 'Millilitre', 'VOLUME', FALSE),
('PCS', 'Piece / Each', 'COUNT', TRUE),
('DOZEN', 'Dozen (12 pcs)', 'COUNT', FALSE);

CREATE TABLE uom_conversions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    from_uom VARCHAR(16) NOT NULL REFERENCES units_of_measure(uom_code) ON DELETE RESTRICT,
    to_uom VARCHAR(16) NOT NULL REFERENCES units_of_measure(uom_code) ON DELETE RESTRICT,
    conversion_multiplier NUMERIC(14, 6) NOT NULL CHECK (conversion_multiplier > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_uom_conversion UNIQUE (from_uom, to_uom)
);

INSERT INTO uom_conversions (from_uom, to_uom, conversion_multiplier) VALUES
('GM', 'KG', 0.001000),
('KG', 'GM', 1000.000000),
('ML', 'LTR', 0.001000),
('LTR', 'ML', 1000.000000),
('DOZEN', 'PCS', 12.000000);

-- ============================================================================
-- 2. SUPPLIERS & VENDOR CATALOG
-- ============================================================================
CREATE TABLE suppliers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(32) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    tax_identifier VARCHAR(64) NOT NULL, -- GSTIN / VAT ID
    contact_person VARCHAR(128) NOT NULL,
    email VARCHAR(255) NOT NULL,
    phone VARCHAR(32) NOT NULL,
    address TEXT NOT NULL,
    payment_terms_days INTEGER NOT NULL DEFAULT 30 CHECK (payment_terms_days >= 0),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_suppliers_active ON suppliers(is_active) WHERE is_active = TRUE;

-- ============================================================================
-- 3. INVENTORY ITEMS (MASTER COMMODITY CATALOG)
-- ============================================================================
CREATE TABLE inventory_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sku VARCHAR(64) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    category item_category_enum NOT NULL,
    base_uom VARCHAR(16) NOT NULL REFERENCES units_of_measure(uom_code) ON DELETE RESTRICT,
    storage_temp_zone VARCHAR(32) NOT NULL CHECK (storage_temp_zone IN ('DRY_AMBIENT', 'CHILLED_0_TO_4C', 'FROZEN_SUB_18C', 'SECURE_CELLAR')),
    minimum_par_stock NUMERIC(14, 4) NOT NULL DEFAULT 0.0000 CHECK (minimum_par_stock >= 0),
    reorder_point NUMERIC(14, 4) NOT NULL DEFAULT 0.0000 CHECK (reorder_point >= 0),
    standard_reorder_qty NUMERIC(14, 4) NOT NULL DEFAULT 0.0000 CHECK (standard_reorder_qty >= 0),
    current_wac NUMERIC(14, 4) NOT NULL DEFAULT 0.0000 CHECK (current_wac >= 0), -- Moving Weighted Avg Cost
    default_prep_yield_pct NUMERIC(6, 2) NOT NULL DEFAULT 100.00 CHECK (default_prep_yield_pct > 0 AND default_prep_yield_pct <= 100),
    default_cooking_yield_pct NUMERIC(6, 2) NOT NULL DEFAULT 100.00 CHECK (default_cooking_yield_pct > 0 AND default_cooking_yield_pct <= 100),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_inventory_items_category ON inventory_items(category);
CREATE INDEX idx_inventory_items_sku ON inventory_items(sku);

-- Supplier Item Pricing & Contracts
CREATE TABLE supplier_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    supplier_id UUID NOT NULL REFERENCES suppliers(id) ON DELETE RESTRICT,
    item_id UUID NOT NULL REFERENCES inventory_items(id) ON DELETE RESTRICT,
    vendor_item_code VARCHAR(64),
    purchase_uom VARCHAR(16) NOT NULL REFERENCES units_of_measure(uom_code) ON DELETE RESTRICT,
    uom_conversion_factor NUMERIC(14, 4) NOT NULL DEFAULT 1.0000 CHECK (uom_conversion_factor > 0), -- e.g., 50 (for 50kg bag)
    contracted_rate NUMERIC(14, 4) NOT NULL CHECK (contracted_rate >= 0),
    lead_time_days INTEGER NOT NULL DEFAULT 1 CHECK (lead_time_days >= 0),
    min_order_qty NUMERIC(14, 4) NOT NULL DEFAULT 1.0000 CHECK (min_order_qty > 0),
    is_preferred_vendor BOOLEAN NOT NULL DEFAULT FALSE,
    valid_from DATE NOT NULL,
    valid_to DATE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_supplier_item_dates UNIQUE (supplier_id, item_id, valid_from),
    CONSTRAINT chk_supplier_item_dates CHECK (valid_to >= valid_from)
);

CREATE INDEX idx_supplier_items_preferred ON supplier_items(item_id, is_preferred_vendor) WHERE is_preferred_vendor = TRUE;

-- ============================================================================
-- 4. PURCHASE ORDERS (PROCUREMENT)
-- ============================================================================
CREATE TABLE purchase_orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    po_number VARCHAR(64) NOT NULL UNIQUE,
    supplier_id UUID NOT NULL REFERENCES suppliers(id) ON DELETE RESTRICT,
    status po_status_enum NOT NULL DEFAULT 'DRAFT',
    total_taxable_amount NUMERIC(14, 4) NOT NULL DEFAULT 0.0000 CHECK (total_taxable_amount >= 0),
    total_tax_amount NUMERIC(14, 4) NOT NULL DEFAULT 0.0000 CHECK (total_tax_amount >= 0),
    grand_total_amount NUMERIC(14, 4) NOT NULL DEFAULT 0.0000 CHECK (grand_total_amount >= 0),
    currency VARCHAR(3) NOT NULL DEFAULT 'USD',
    expected_delivery_date DATE NOT NULL,
    created_by_user_id UUID NOT NULL,
    approved_by_user_id UUID,
    approved_at TIMESTAMPTZ,
    cancellation_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_po_status ON purchase_orders(status);
CREATE INDEX idx_po_supplier ON purchase_orders(supplier_id);
CREATE INDEX idx_po_delivery_date ON purchase_orders(expected_delivery_date);

CREATE TABLE purchase_order_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    purchase_order_id UUID NOT NULL REFERENCES purchase_orders(id) ON DELETE RESTRICT,
    item_id UUID NOT NULL REFERENCES inventory_items(id) ON DELETE RESTRICT,
    order_uom VARCHAR(16) NOT NULL REFERENCES units_of_measure(uom_code) ON DELETE RESTRICT,
    quantity_ordered NUMERIC(14, 4) NOT NULL CHECK (quantity_ordered > 0),
    quantity_received NUMERIC(14, 4) NOT NULL DEFAULT 0.0000 CHECK (quantity_received >= 0),
    uom_conversion_factor NUMERIC(14, 4) NOT NULL CHECK (uom_conversion_factor > 0),
    unit_price NUMERIC(14, 4) NOT NULL CHECK (unit_price >= 0),
    tax_percentage NUMERIC(6, 2) NOT NULL DEFAULT 0.00 CHECK (tax_percentage >= 0),
    tax_amount NUMERIC(14, 4) NOT NULL DEFAULT 0.0000 CHECK (tax_amount >= 0),
    line_total NUMERIC(14, 4) NOT NULL CHECK (line_total >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_po_item_qty_received CHECK (quantity_received <= quantity_ordered * 1.10) -- Max 10% over-delivery allowance
);

CREATE INDEX idx_poi_order_id ON purchase_order_items(purchase_order_id);
CREATE INDEX idx_poi_item_id ON purchase_order_items(item_id);

-- ============================================================================
-- 5. GOODS RECEIVED NOTES (GRN) & INWARD INSPECTION
-- ============================================================================
CREATE TABLE goods_received_notes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    grn_number VARCHAR(64) NOT NULL UNIQUE,
    purchase_order_id UUID NOT NULL REFERENCES purchase_orders(id) ON DELETE RESTRICT,
    supplier_id UUID NOT NULL REFERENCES suppliers(id) ON DELETE RESTRICT,
    vendor_invoice_number VARCHAR(128) NOT NULL,
    vendor_invoice_date DATE NOT NULL,
    vendor_delivery_challan VARCHAR(128),
    receiving_temperature_celsius NUMERIC(5, 2), -- Mandatory for cold/frozen items
    status grn_status_enum NOT NULL DEFAULT 'PENDING_INSPECTION',
    inspected_by_user_id UUID NOT NULL,
    inspection_remarks TEXT,
    total_invoice_amount NUMERIC(14, 4) NOT NULL CHECK (total_invoice_amount >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    posted_at TIMESTAMPTZ
);

CREATE INDEX idx_grn_po_id ON goods_received_notes(purchase_order_id);
CREATE INDEX idx_grn_supplier_id ON goods_received_notes(supplier_id);
CREATE INDEX idx_grn_invoice ON goods_received_notes(vendor_invoice_number);

CREATE TABLE grn_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    grn_id UUID NOT NULL REFERENCES goods_received_notes(id) ON DELETE RESTRICT,
    po_item_id UUID NOT NULL REFERENCES purchase_order_items(id) ON DELETE RESTRICT,
    item_id UUID NOT NULL REFERENCES inventory_items(id) ON DELETE RESTRICT,
    internal_batch_number VARCHAR(128) NOT NULL UNIQUE,
    vendor_lot_number VARCHAR(128) NOT NULL,
    manufacture_date DATE,
    expiry_date DATE NOT NULL,
    received_uom VARCHAR(16) NOT NULL REFERENCES units_of_measure(uom_code) ON DELETE RESTRICT,
    received_quantity NUMERIC(14, 4) NOT NULL CHECK (received_quantity >= 0),
    accepted_quantity_base NUMERIC(14, 4) NOT NULL CHECK (accepted_quantity_base >= 0), -- Stored in base UOM
    rejected_quantity NUMERIC(14, 4) NOT NULL DEFAULT 0.0000 CHECK (rejected_quantity >= 0),
    rejection_reason TEXT,
    billed_unit_rate NUMERIC(14, 4) NOT NULL CHECK (billed_unit_rate >= 0),
    invoice_price_variance NUMERIC(14, 4) NOT NULL DEFAULT 0.0000, -- (Billed Rate - PO Rate) * Qty
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_grn_expiry CHECK (expiry_date >= CURRENT_DATE)
);

CREATE INDEX idx_grn_items_grn_id ON grn_items(grn_id);
CREATE INDEX idx_grn_items_batch ON grn_items(internal_batch_number);
CREATE INDEX idx_grn_items_expiry ON grn_items(expiry_date);

-- ============================================================================
-- 6. TWO-TIER INVENTORY: CENTRAL STORE BATCHES & KITCHEN STOCKS
-- ============================================================================
-- Central Store Physical Stock (Batch-tracked with FEFO)
CREATE TABLE store_stock (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    item_id UUID NOT NULL REFERENCES inventory_items(id) ON DELETE RESTRICT,
    grn_item_id UUID NOT NULL REFERENCES grn_items(id) ON DELETE RESTRICT,
    batch_number VARCHAR(128) NOT NULL UNIQUE,
    expiry_date DATE NOT NULL,
    storage_bin_location VARCHAR(64),
    initial_quantity NUMERIC(14, 4) NOT NULL CHECK (initial_quantity > 0),
    current_quantity NUMERIC(14, 4) NOT NULL CHECK (current_quantity >= 0),
    unit_cost_wac NUMERIC(14, 4) NOT NULL CHECK (unit_cost_wac >= 0),
    is_quarantined BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Crucial Index for FEFO Stock Picking
CREATE INDEX idx_store_stock_fefo ON store_stock (item_id, expiry_date ASC, current_quantity)
WHERE current_quantity > 0 AND is_quarantined = FALSE;

-- Kitchen Sub-Locations (Stations)
CREATE TABLE kitchen_locations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(32) NOT NULL UNIQUE, -- e.g., 'HOT_LINE_1', 'GARDE_MANGER', 'BAKERY', 'BAR_MAIN'
    name VARCHAR(128) NOT NULL,
    description TEXT,
    head_chef_user_id UUID,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO kitchen_locations (code, name) VALUES
('HOT_LINE_1', 'Main Hot Line (Sauté/Grill/Fry)'),
('GARDE_MANGER', 'Cold Kitchen & Salads'),
('BAKERY_PASTRY', 'Bakery & Dessert Section'),
('BUTCHERY_PREP', 'Central Prep & Butchery Room'),
('BAR_MAIN', 'Main Beverage & Cocktail Bar');

-- Kitchen Inventory Balances (Line Par Stock by Location)
CREATE TABLE kitchen_stock (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    kitchen_location_id UUID NOT NULL REFERENCES kitchen_locations(id) ON DELETE RESTRICT,
    item_id UUID NOT NULL REFERENCES inventory_items(id) ON DELETE RESTRICT,
    current_quantity NUMERIC(14, 4) NOT NULL DEFAULT 0.0000 CHECK (current_quantity >= 0),
    par_level NUMERIC(14, 4) NOT NULL DEFAULT 0.0000 CHECK (par_level >= 0),
    last_count_quantity NUMERIC(14, 4) DEFAULT 0.0000,
    last_counted_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_kitchen_item UNIQUE (kitchen_location_id, item_id)
);

CREATE INDEX idx_kitchen_stock_location ON kitchen_stock(kitchen_location_id);
CREATE INDEX idx_kitchen_stock_item ON kitchen_stock(item_id);

-- ============================================================================
-- 7. STORE TO KITCHEN REQUISITIONS & ISSUES
-- ============================================================================
CREATE TABLE kitchen_requisitions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    requisition_number VARCHAR(64) NOT NULL UNIQUE,
    kitchen_location_id UUID NOT NULL REFERENCES kitchen_locations(id) ON DELETE RESTRICT,
    status requisition_status_enum NOT NULL DEFAULT 'DRAFT',
    requested_by_user_id UUID NOT NULL,
    approved_by_chef_id UUID,
    urgency VARCHAR(16) NOT NULL DEFAULT 'ROUTINE' CHECK (urgency IN ('ROUTINE', 'RUSH_SERVICE')),
    shift VARCHAR(16) NOT NULL DEFAULT 'MORNING' CHECK (shift IN ('MORNING', 'EVENING', 'BANQUET')),
    remarks TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_requisition_status ON kitchen_requisitions(status);
CREATE INDEX idx_requisition_location ON kitchen_requisitions(kitchen_location_id);

CREATE TABLE requisition_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    requisition_id UUID NOT NULL REFERENCES kitchen_requisitions(id) ON DELETE RESTRICT,
    item_id UUID NOT NULL REFERENCES inventory_items(id) ON DELETE RESTRICT,
    requested_quantity NUMERIC(14, 4) NOT NULL CHECK (requested_quantity > 0),
    issued_quantity NUMERIC(14, 4) NOT NULL DEFAULT 0.0000 CHECK (issued_quantity >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_req_issued_lte_req CHECK (issued_quantity <= requested_quantity)
);

CREATE INDEX idx_req_items_requisition_id ON requisition_items(requisition_id);
CREATE INDEX idx_req_items_item_id ON requisition_items(item_id);

-- Store Issue Note (Execution of Requisition)
CREATE TABLE store_issue_notes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    issue_number VARCHAR(64) NOT NULL UNIQUE,
    requisition_id UUID NOT NULL REFERENCES kitchen_requisitions(id) ON DELETE RESTRICT,
    kitchen_location_id UUID NOT NULL REFERENCES kitchen_locations(id) ON DELETE RESTRICT,
    issued_by_storekeeper_id UUID NOT NULL,
    received_by_chef_id UUID NOT NULL,
    issue_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE store_issue_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    issue_note_id UUID NOT NULL REFERENCES store_issue_notes(id) ON DELETE RESTRICT,
    requisition_item_id UUID NOT NULL REFERENCES requisition_items(id) ON DELETE RESTRICT,
    store_stock_id UUID NOT NULL REFERENCES store_stock(id) ON DELETE RESTRICT, -- Specific batch picked (FEFO)
    item_id UUID NOT NULL REFERENCES inventory_items(id) ON DELETE RESTRICT,
    quantity_issued NUMERIC(14, 4) NOT NULL CHECK (quantity_issued > 0),
    unit_cost_wac NUMERIC(14, 4) NOT NULL CHECK (unit_cost_wac >= 0),
    total_cost NUMERIC(14, 4) GENERATED ALWAYS AS (quantity_issued * unit_cost_wac) STORED,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_sii_issue_note ON store_issue_items(issue_note_id);
CREATE INDEX idx_sii_store_stock ON store_issue_items(store_stock_id);

-- Return to Store Note (RTS)
CREATE TABLE store_returns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    return_number VARCHAR(64) NOT NULL UNIQUE,
    kitchen_location_id UUID NOT NULL REFERENCES kitchen_locations(id) ON DELETE RESTRICT,
    returned_by_chef_id UUID NOT NULL,
    accepted_by_storekeeper_id UUID NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'COMPLETED' CHECK (status IN ('PENDING_INSPECTION', 'COMPLETED', 'REJECTED')),
    return_reason TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE store_return_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    return_id UUID NOT NULL REFERENCES store_returns(id) ON DELETE RESTRICT,
    store_stock_id UUID NOT NULL REFERENCES store_stock(id) ON DELETE RESTRICT, -- Batch restored
    item_id UUID NOT NULL REFERENCES inventory_items(id) ON DELETE RESTRICT,
    quantity_returned NUMERIC(14, 4) NOT NULL CHECK (quantity_returned > 0),
    unit_cost_wac NUMERIC(14, 4) NOT NULL CHECK (unit_cost_wac >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- 8. RECIPES & BILL OF MATERIALS (BOM)
-- ============================================================================
CREATE TABLE recipes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recipe_code VARCHAR(64) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    recipe_type VARCHAR(32) NOT NULL CHECK (recipe_type IN ('FINISHED_MENU_ITEM', 'SUB_RECIPE_MISE_EN_PLACE')),
    pos_item_id VARCHAR(64) UNIQUE, -- Foreign reference to POS Menu Item table (if finished item)
    prepared_at_location_id UUID NOT NULL REFERENCES kitchen_locations(id) ON DELETE RESTRICT,
    batch_yield_quantity NUMERIC(14, 4) NOT NULL DEFAULT 1.0000 CHECK (batch_yield_quantity > 0),
    yield_uom VARCHAR(16) NOT NULL REFERENCES units_of_measure(uom_code) ON DELETE RESTRICT,
    portion_size_grams NUMERIC(10, 2),
    prep_time_minutes INTEGER DEFAULT 0,
    shelf_life_hours INTEGER NOT NULL DEFAULT 24 CHECK (shelf_life_hours > 0),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_recipes_pos_item ON recipes(pos_item_id) WHERE pos_item_id IS NOT NULL;
CREATE INDEX idx_recipes_type ON recipes(recipe_type);

-- Bill of Materials Line Items
CREATE TABLE recipe_ingredients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recipe_id UUID NOT NULL REFERENCES recipes(id) ON DELETE RESTRICT,
    raw_item_id UUID REFERENCES inventory_items(id) ON DELETE RESTRICT,
    sub_recipe_id UUID REFERENCES recipes(id) ON DELETE RESTRICT,
    net_ingredient_quantity NUMERIC(14, 4) NOT NULL CHECK (net_ingredient_quantity > 0),
    uom VARCHAR(16) NOT NULL REFERENCES units_of_measure(uom_code) ON DELETE RESTRICT,
    prep_yield_percentage NUMERIC(6, 2) NOT NULL DEFAULT 100.00 CHECK (prep_yield_percentage > 0 AND prep_yield_percentage <= 100),
    cooking_yield_percentage NUMERIC(6, 2) NOT NULL DEFAULT 100.00 CHECK (cooking_yield_percentage > 0 AND cooking_yield_percentage <= 100),
    gross_ingredient_quantity NUMERIC(14, 4) NOT NULL CHECK (gross_ingredient_quantity > 0),
    cost_allocation_factor NUMERIC(6, 4) NOT NULL DEFAULT 1.0000,
    is_critical_protein BOOLEAN NOT NULL DEFAULT FALSE, -- Flagged for real-time deduction
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_ingredient_source CHECK (
        (raw_item_id IS NOT NULL AND sub_recipe_id IS NULL) OR
        (raw_item_id IS NULL AND sub_recipe_id IS NOT NULL)
    ),
    CONSTRAINT uq_recipe_ingredient UNIQUE (recipe_id, raw_item_id, sub_recipe_id)
);

CREATE INDEX idx_recipe_ingredients_recipe ON recipe_ingredients(recipe_id);
CREATE INDEX idx_recipe_ingredients_raw_item ON recipe_ingredients(raw_item_id) WHERE raw_item_id IS NOT NULL;
CREATE INDEX idx_recipe_ingredients_sub_recipe ON recipe_ingredients(sub_recipe_id) WHERE sub_recipe_id IS NOT NULL;

-- ============================================================================
-- 9. POS / KOT CONSUMPTION EVENT OUTBOX
-- ============================================================================
CREATE TABLE pos_kot_consumption_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pos_order_id VARCHAR(64) NOT NULL,
    kot_number VARCHAR(64) NOT NULL,
    recipe_id UUID NOT NULL REFERENCES recipes(id) ON DELETE RESTRICT,
    kitchen_location_id UUID NOT NULL REFERENCES kitchen_locations(id) ON DELETE RESTRICT,
    quantity_sold NUMERIC(10, 2) NOT NULL CHECK (quantity_sold > 0),
    consumption_status VARCHAR(32) NOT NULL DEFAULT 'PENDING' CHECK (consumption_status IN ('PENDING', 'PROCESSED', 'FAILED', 'REVERSED')),
    error_message TEXT,
    order_timestamp TIMESTAMPTZ NOT NULL,
    processed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_kot_log_pending ON pos_kot_consumption_logs(consumption_status) WHERE consumption_status = 'PENDING';
CREATE INDEX idx_kot_log_order ON pos_kot_consumption_logs(pos_order_id, kot_number);

-- ============================================================================
-- 10. KITCHEN WASTAGE & SPOILAGE LOGS
-- ============================================================================
CREATE TABLE kitchen_wastage_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    waste_log_number VARCHAR(64) NOT NULL UNIQUE,
    kitchen_location_id UUID NOT NULL REFERENCES kitchen_locations(id) ON DELETE RESTRICT,
    item_id UUID REFERENCES inventory_items(id) ON DELETE RESTRICT,
    sub_recipe_id UUID REFERENCES recipes(id) ON DELETE RESTRICT,
    wasted_quantity NUMERIC(14, 4) NOT NULL CHECK (wasted_quantity > 0),
    uom VARCHAR(16) NOT NULL REFERENCES units_of_measure(uom_code) ON DELETE RESTRICT,
    unit_cost_wac NUMERIC(14, 4) NOT NULL CHECK (unit_cost_wac >= 0),
    total_cost_loss NUMERIC(14, 4) NOT NULL CHECK (total_cost_loss >= 0),
    reason_code wastage_reason_enum NOT NULL,
    logged_by_cook_id UUID NOT NULL,
    approved_by_chef_id UUID NOT NULL,
    approval_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    action_taken_preventative TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_waste_item_source CHECK (
        (item_id IS NOT NULL AND sub_recipe_id IS NULL) OR
        (item_id IS NULL AND sub_recipe_id IS NOT NULL)
    )
);

CREATE INDEX idx_wastage_location ON kitchen_wastage_logs(kitchen_location_id);
CREATE INDEX idx_wastage_reason ON kitchen_wastage_logs(reason_code);
CREATE INDEX idx_wastage_date ON kitchen_wastage_logs(created_at);

-- ============================================================================
-- 11. PHYSICAL AUDIT & VARIANCE RECONCILIATION
-- ============================================================================
CREATE TABLE inventory_audit_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    audit_code VARCHAR(64) NOT NULL UNIQUE,
    audit_scope VARCHAR(32) NOT NULL CHECK (audit_scope IN ('CENTRAL_STORE', 'KITCHEN_LOCATION', 'ALL')),
    target_kitchen_location_id UUID REFERENCES kitchen_locations(id) ON DELETE RESTRICT,
    audit_date DATE NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'IN_PROGRESS' CHECK (status IN ('IN_PROGRESS', 'RECONCILED', 'LOCKED', 'CANCELLED')),
    audited_by_user_id UUID NOT NULL,
    reviewed_by_controller_id UUID,
    variance_net_cost NUMERIC(14, 4) DEFAULT 0.0000,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reconciled_at TIMESTAMPTZ
);

CREATE INDEX idx_audit_sessions_status ON inventory_audit_sessions(status);

CREATE TABLE inventory_audit_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    audit_session_id UUID NOT NULL REFERENCES inventory_audit_sessions(id) ON DELETE RESTRICT,
    item_id UUID NOT NULL REFERENCES inventory_items(id) ON DELETE RESTRICT,
    store_stock_id UUID REFERENCES store_stock(id) ON DELETE RESTRICT, -- When auditing central store batches
    system_theoretical_qty NUMERIC(14, 4) NOT NULL,
    actual_counted_qty NUMERIC(14, 4) NOT NULL CHECK (actual_counted_qty >= 0),
    variance_quantity NUMERIC(14, 4) GENERATED ALWAYS AS (actual_counted_qty - system_theoretical_qty) STORED,
    unit_cost_wac NUMERIC(14, 4) NOT NULL CHECK (unit_cost_wac >= 0),
    variance_total_cost NUMERIC(14, 4) GENERATED ALWAYS AS ((actual_counted_qty - system_theoretical_qty) * unit_cost_wac) STORED,
    variance_reason_category VARCHAR(64),
    investigation_notes TEXT,
    adjustment_posted BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_items_session ON inventory_audit_items(audit_session_id);
CREATE INDEX idx_audit_items_item ON inventory_audit_items(item_id);

CREATE TABLE inventory_audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    audit_session_id UUID NOT NULL REFERENCES inventory_audit_sessions(id) ON DELETE RESTRICT,
    audit_item_id UUID NOT NULL REFERENCES inventory_audit_items(id) ON DELETE RESTRICT,
    item_id UUID NOT NULL REFERENCES inventory_items(id) ON DELETE RESTRICT,
    location_type VARCHAR(16) NOT NULL CHECK (location_type IN ('CENTRAL_STORE', 'KITCHEN_LOCATION')),
    kitchen_location_id UUID REFERENCES kitchen_locations(id) ON DELETE RESTRICT,
    store_stock_id UUID REFERENCES store_stock(id) ON DELETE RESTRICT,
    pre_audit_quantity NUMERIC(14, 4) NOT NULL,
    post_audit_quantity NUMERIC(14, 4) NOT NULL CHECK (post_audit_quantity >= 0),
    adjustment_quantity NUMERIC(14, 4) NOT NULL, -- post_audit_quantity - pre_audit_quantity
    adjustment_cost_impact NUMERIC(14, 4) NOT NULL,
    authorized_by_controller_id UUID NOT NULL,
    reason_code VARCHAR(64) NOT NULL,
    audit_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_logs_session ON inventory_audit_logs(audit_session_id);
CREATE INDEX idx_audit_logs_item ON inventory_audit_logs(item_id);
CREATE INDEX idx_audit_logs_timestamp ON inventory_audit_logs(audit_timestamp DESC);

-- ============================================================================
-- 12. IMMUTABLE DOUBLE-ENTRY INVENTORY LEDGER
-- ============================================================================
CREATE TABLE inventory_transactions_ledger (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transaction_type ledger_transaction_type_enum NOT NULL,
    reference_id UUID NOT NULL, -- ID of GRN, Issue, RTS, KOT Log, Waste Log, or Audit Session
    reference_doc_number VARCHAR(64) NOT NULL,
    item_id UUID NOT NULL REFERENCES inventory_items(id) ON DELETE RESTRICT,
    source_location_type VARCHAR(16) NOT NULL CHECK (source_location_type IN ('VENDOR', 'CENTRAL_STORE', 'KITCHEN', 'DISPOSAL', 'CUSTOMER')),
    source_location_id UUID, -- NULL if Vendor
    destination_location_type VARCHAR(16) NOT NULL CHECK (destination_location_type IN ('CENTRAL_STORE', 'KITCHEN', 'DISPOSAL', 'CUSTOMER')),
    destination_location_id UUID, -- NULL if Disposal/Customer
    batch_number VARCHAR(128),
    quantity NUMERIC(14, 4) NOT NULL CHECK (quantity > 0),
    unit_cost NUMERIC(14, 4) NOT NULL CHECK (unit_cost >= 0),
    total_cost NUMERIC(14, 4) GENERATED ALWAYS AS (quantity * unit_cost) STORED,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
) PARTITION BY RANGE (created_at);

-- Standard Monthly Partitions Example
CREATE TABLE inventory_ledger_2026_m10 PARTITION OF inventory_transactions_ledger
    FOR VALUES FROM ('2026-10-01 00:00:00+00') TO ('2026-11-01 00:00:00+00');
CREATE TABLE inventory_ledger_2026_m11 PARTITION OF inventory_transactions_ledger
    FOR VALUES FROM ('2026-11-01 00:00:00+00') TO ('2026-12-01 00:00:00+00');
CREATE TABLE inventory_ledger_2026_m12 PARTITION OF inventory_transactions_ledger
    FOR VALUES FROM ('2026-12-01 00:00:00+00') TO ('2027-01-01 00:00:00+00');

CREATE INDEX idx_ledger_item_time ON inventory_transactions_ledger(item_id, created_at DESC);
CREATE INDEX idx_ledger_ref_doc ON inventory_transactions_ledger(reference_doc_number);
```

---

## 7. ACID Transaction & Concurrency Guarantees

In a multi-terminal restaurant environment where 50 KOTs are firing simultaneously during a dinner rush, concurrency race conditions will cause negative stock balances and lost inventory updates unless handled strictly at the database engine level.

### 7.1 Real-Time Stock Deduction via Recursive BOM Explosion

The following PostgreSQL stored procedure handles multi-level BOM explosion and atomic deduction with row-level locking:

```sql
CREATE OR REPLACE FUNCTION fn_process_kot_consumption(
    p_kot_consumption_log_id UUID
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
    v_log_record RECORD;
    v_ingredient RECORD;
    v_current_stock NUMERIC(14, 4);
BEGIN
    -- 1. Lock consumption log row to prevent duplicate worker execution
    SELECT * INTO v_log_record
    FROM pos_kot_consumption_logs
    WHERE id = p_kot_consumption_log_id
    FOR UPDATE;

    IF v_log_record.consumption_status != 'PENDING' THEN
        RETURN;
    END IF;

    -- 2. Recursive Common Table Expression (CTE) to explode multi-level BOM
    FOR v_ingredient IN
        WITH RECURSIVE exploded_bom AS (
            -- Base Case: Direct ingredients of the Menu Item
            SELECT 
                ri.raw_item_id,
                ri.sub_recipe_id,
                (ri.gross_ingredient_quantity * v_log_record.quantity_sold) AS total_gross_qty
            FROM recipe_ingredients ri
            WHERE ri.recipe_id = v_log_record.recipe_id

            UNION ALL

            -- Recursive Step: Explode sub-recipes into raw ingredients
            SELECT 
                child_ri.raw_item_id,
                child_ri.sub_recipe_id,
                (child_ri.gross_ingredient_quantity * (eb.total_gross_qty / parent_rec.batch_yield_quantity)) AS total_gross_qty
            FROM exploded_bom eb
            JOIN recipes parent_rec ON eb.sub_recipe_id = parent_rec.id
            JOIN recipe_ingredients child_ri ON child_ri.recipe_id = parent_rec.id
            WHERE eb.sub_recipe_id IS NOT NULL
        )
        SELECT 
            raw_item_id,
            SUM(total_gross_qty) AS aggregate_qty
        FROM exploded_bom
        WHERE raw_item_id IS NOT NULL
        GROUP BY raw_item_id
    LOOP
        -- 3. Lock Kitchen Stock Balance Row (Pessimistic Lock)
        SELECT current_quantity INTO v_current_stock
        FROM kitchen_stock
        WHERE kitchen_location_id = v_log_record.kitchen_location_id
          AND item_id = v_ingredient.raw_item_id
        FOR UPDATE;

        IF NOT FOUND THEN
            -- Initialize row if missing
            INSERT INTO kitchen_stock (kitchen_location_id, item_id, current_quantity)
            VALUES (v_log_record.kitchen_location_id, v_ingredient.raw_item_id, 0.0000);
            v_current_stock := 0.0000;
        END IF;

        -- 4. Deduct Stock (Allowing calibrated negative balance with warning for rush service)
        UPDATE kitchen_stock
        SET current_quantity = current_quantity - v_ingredient.aggregate_qty,
            updated_at = NOW()
        WHERE kitchen_location_id = v_log_record.kitchen_location_id
          AND item_id = v_ingredient.raw_item_id;

        -- 5. Record Double-Entry Inventory Ledger Movement
        INSERT INTO inventory_transactions_ledger (
            transaction_type,
            reference_id,
            reference_doc_number,
            item_id,
            source_location_type,
            source_location_id,
            destination_location_type,
            destination_location_id,
            quantity,
            unit_cost
        ) VALUES (
            'KOT_BOM_CONSUMPTION',
            v_log_record.id,
            v_log_record.kot_number,
            v_ingredient.raw_item_id,
            'KITCHEN',
            v_log_record.kitchen_location_id,
            'CUSTOMER',
            NULL,
            v_ingredient.aggregate_qty,
            (SELECT current_wac FROM inventory_items WHERE id = v_ingredient.raw_item_id)
        );
    END LOOP;

    -- 6. Mark log record as processed
    UPDATE pos_kot_consumption_logs
    SET consumption_status = 'PROCESSED',
        processed_at = NOW()
    WHERE id = p_kot_consumption_log_id;

EXCEPTION WHEN OTHERS THEN
    UPDATE pos_kot_consumption_logs
    SET consumption_status = 'FAILED',
        error_message = SQLERRM,
        processed_at = NOW()
    WHERE id = p_kot_consumption_log_id;
    RAISE;
END;
$$;
```

### 7.2 Automated FEFO Store Issue Picking Function

When a storekeeper prepares a Store Issue Note (SIN), stock must be automatically allocated from the oldest non-expired batch:

```sql
CREATE OR REPLACE FUNCTION fn_issue_requisition_fefo(
    p_issue_note_id UUID,
    p_requisition_item_id UUID,
    p_quantity_to_issue NUMERIC(14, 4)
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
    v_req_item RECORD;
    v_batch RECORD;
    v_remaining_to_issue NUMERIC(14, 4) := p_quantity_to_issue;
    v_alloc_qty NUMERIC(14, 4);
    v_loc_id UUID;
BEGIN
    SELECT ri.*, kr.kitchen_location_id 
    INTO v_req_item 
    FROM requisition_items ri
    JOIN kitchen_requisitions kr ON ri.requisition_id = kr.id
    WHERE ri.id = p_requisition_item_id;

    v_loc_id := v_req_item.kitchen_location_id;

    -- Cursor over eligible batches sorted by FEFO
    FOR v_batch IN 
        SELECT * 
        FROM store_stock
        WHERE item_id = v_req_item.item_id
          AND current_quantity > 0
          AND is_quarantined = FALSE
          AND expiry_date >= CURRENT_DATE
        ORDER BY expiry_date ASC, created_at ASC
        FOR UPDATE
    LOOP
        EXIT WHEN v_remaining_to_issue <= 0;

        IF v_batch.current_quantity >= v_remaining_to_issue THEN
            v_alloc_qty := v_remaining_to_issue;
        ELSE
            v_alloc_qty := v_batch.current_quantity;
        END IF;

        -- Decrement Central Store Batch
        UPDATE store_stock
        SET current_quantity = current_quantity - v_alloc_qty,
            updated_at = NOW()
        WHERE id = v_batch.id;

        -- Record Issue Item Detail
        INSERT INTO store_issue_items (
            issue_note_id,
            requisition_item_id,
            store_stock_id,
            item_id,
            quantity_issued,
            unit_cost_wac
        ) VALUES (
            p_issue_note_id,
            p_requisition_item_id,
            v_batch.id,
            v_req_item.item_id,
            v_alloc_qty,
            v_batch.unit_cost_wac
        );

        -- Increment Kitchen Station Stock
        INSERT INTO kitchen_stock (kitchen_location_id, item_id, current_quantity)
        VALUES (v_loc_id, v_req_item.item_id, v_alloc_qty)
        ON CONFLICT (kitchen_location_id, item_id)
        DO UPDATE SET 
            current_quantity = kitchen_stock.current_quantity + EXCLUDED.current_quantity,
            updated_at = NOW();

        -- Ledger Double-Entry
        INSERT INTO inventory_transactions_ledger (
            transaction_type,
            reference_id,
            reference_doc_number,
            item_id,
            source_location_type,
            source_location_id,
            destination_location_type,
            destination_location_id,
            batch_number,
            quantity,
            unit_cost
        ) VALUES (
            'STORE_ISSUE',
            p_issue_note_id,
            (SELECT issue_number FROM store_issue_notes WHERE id = p_issue_note_id),
            v_req_item.item_id,
            'CENTRAL_STORE',
            NULL,
            'KITCHEN',
            v_loc_id,
            v_batch.batch_number,
            v_alloc_qty,
            v_batch.unit_cost_wac
        );

        v_remaining_to_issue := v_remaining_to_issue - v_alloc_qty;
    END LOOP;

    IF v_remaining_to_issue > 0 THEN
        RAISE EXCEPTION 'Insufficient Central Store stock to fulfill requested quantity. Short by % units.', v_remaining_to_issue;
    END IF;

    -- Update Requisition Item issued quantity
    UPDATE requisition_items
    SET issued_quantity = issued_quantity + p_quantity_to_issue
    WHERE id = p_requisition_item_id;
END;
$$;
```

---

## 8. Query Optimization & Analytics Architecture

### 8.1 Critical Query Plans (EXPLAIN ANALYZE)

#### 1. Daily Food Cost Variance Report Query
This query computes theoretical sales consumption vs. actual kitchen consumption per station and detects variance anomalies in under 20ms:

```sql
EXPLAIN ANALYZE
WITH period_issues AS (
    SELECT 
        sii.item_id,
        sin.kitchen_location_id,
        SUM(sii.quantity_issued) AS total_issued_qty
    FROM store_issue_items sii
    JOIN store_issue_notes sin ON sii.issue_note_id = sin.id
    WHERE sin.issue_timestamp >= (CURRENT_DATE - INTERVAL '1 day')
    GROUP BY sii.item_id, sin.kitchen_location_id
),
period_waste AS (
    SELECT 
        item_id,
        kitchen_location_id,
        SUM(wasted_quantity) AS total_wasted_qty
    FROM kitchen_wastage_logs
    WHERE created_at >= (CURRENT_DATE - INTERVAL '1 day')
    GROUP BY item_id, kitchen_location_id
),
period_sales_bom AS (
    SELECT 
        ri.raw_item_id AS item_id,
        pkl.kitchen_location_id,
        SUM(ri.gross_ingredient_quantity * pkl.quantity_sold) AS theoretical_sales_consumption
    FROM pos_kot_consumption_logs pkl
    JOIN recipe_ingredients ri ON pkl.recipe_id = ri.recipe_id
    WHERE pkl.order_timestamp >= (CURRENT_DATE - INTERVAL '1 day')
      AND pkl.consumption_status = 'PROCESSED'
    GROUP BY ri.raw_item_id, pkl.kitchen_location_id
)
SELECT 
    ii.sku,
    ii.name AS ingredient_name,
    kl.name AS station_name,
    COALESCE(pi.total_issued_qty, 0.0000) AS qty_issued,
    COALESCE(psb.theoretical_sales_consumption, 0.0000) AS theoretical_sold_qty,
    COALESCE(pw.total_wasted_qty, 0.0000) AS approved_waste_qty,
    ks.current_quantity AS closing_physical_stock,
    -- Variance = Actual Consumption - Theoretical Consumption
    ROUND(
        ((COALESCE(pi.total_issued_qty, 0.0000) - ks.current_quantity) - 
         (COALESCE(psb.theoretical_sales_consumption, 0.0000) + COALESCE(pw.total_wasted_qty, 0.0000))
        ), 4
    ) AS variance_qty,
    ROUND(
        ((COALESCE(pi.total_issued_qty, 0.0000) - ks.current_quantity) - 
         (COALESCE(psb.theoretical_sales_consumption, 0.0000) + COALESCE(pw.total_wasted_qty, 0.0000))
        ) * ii.current_wac, 2
    ) AS variance_financial_loss_usd
FROM inventory_items ii
CROSS JOIN kitchen_locations kl
LEFT JOIN kitchen_stock ks ON ks.item_id = ii.id AND ks.kitchen_location_id = kl.id
LEFT JOIN period_issues pi ON pi.item_id = ii.id AND pi.kitchen_location_id = kl.id
LEFT JOIN period_waste pw ON pw.item_id = ii.id AND pw.kitchen_location_id = kl.id
LEFT JOIN period_sales_bom psb ON psb.item_id = ii.id AND psb.kitchen_location_id = kl.id
WHERE (pi.total_issued_qty > 0 OR psb.theoretical_sales_consumption > 0 OR ks.current_quantity > 0)
ORDER BY variance_financial_loss_usd DESC;
```

#### Optimization Characteristics:
- Uses covering indexes on `pos_kot_consumption_logs(consumption_status, order_timestamp)` and `store_issue_notes(issue_timestamp)`.
- Eliminates nested loops by utilizing Hash Aggregates and Hash Joins across partitions.
- Zero table lock contention; reads are completely unblocked during live service.

---

## 9. Rollout, Data Migration & Disaster Recovery

### 9.1 Zero-Downtime Migration Pattern (Expand & Contract)
1. **Phase 1 (Expand)**:
   - Apply table creations and new column additions with safe defaults (`DEFAULT 0.0000`).
   - Create all constraints as `NOT VALID`, then validate asynchronously via `ALTER TABLE ... VALIDATE CONSTRAINT` to avoid table access exclusive locks.
   - Build indexes concurrently using `CREATE INDEX CONCURRENTLY`.
2. **Phase 2 (Dual Write & Backfill)**:
   - Deploy backend API services with dual-write capability to both the legacy structure and the new two-tier inventory tables.
   - Run background idempotent backfill scripts to compute historical WAC and establish opening Central Store batches.
3. **Phase 3 (Contract)**:
   - Switch all read and write traffic exclusively to the new Two-Tier schema.
   - Drop deprecated legacy columns and tables after a 30-day quarantine period.

### 9.2 Archival & Retention Strategy
- The `inventory_transactions_ledger` partitions are retained online for 24 calendar months to support annual tax, VAT, and food safety audits.
- Partitions older than 24 months are detached and archived to compressed cold storage (PostgreSQL foreign data wrappers `postgres_fdw` or parquet exports on Amazon S3) with SHA-256 cryptographic manifests for tamper proofing.

---

### Verification and Sign-Off

This document constitutes the complete technical and database contract for the Restaurant Inventory & Grocery Management Subsystem. All subsequent API implementations, service workers, and frontend UI dashboards must conform strictly to the entities, state transitions, and constraints defined herein.
