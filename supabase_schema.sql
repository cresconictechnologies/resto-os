-- ============================================================================
-- RestoOS — High-Throughput Restaurant, Bar & Two-Tier Inventory OS
-- Supabase / PostgreSQL Production Migration Schema
-- Designed for Rasa Sahyadri · Koregaon Park, Pune (Permit Room FL-3)
-- ============================================================================

-- 1. Enable UUID Extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 2. Tenants (Multi-Outlet Master)
CREATE TABLE IF NOT EXISTS tenants (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    outlet_name VARCHAR(100) NOT NULL,
    address TEXT NOT NULL,
    gstin VARCHAR(15) NOT NULL,
    fssai VARCHAR(14) NOT NULL,
    fl3_license VARCHAR(30) NOT NULL,
    vatin VARCHAR(20) NOT NULL,
    phone VARCHAR(20) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 3. Staff Users & Role-Based Access Control (RBAC)
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    username VARCHAR(50) UNIQUE NOT NULL,
    display_name VARCHAR(100) NOT NULL,
    role VARCHAR(20) NOT NULL CHECK (role IN ('OWNER', 'MANAGER', 'CASHIER', 'STOREKEEPER', 'ADMIN')),
    pin_hash VARCHAR(128) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_users_tenant_id ON users(tenant_id);
CREATE INDEX IF NOT EXISTS ix_users_username ON users(username);

-- 4. Dining Sections & Tables Floor Plan
CREATE TABLE IF NOT EXISTS dining_tables (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    code VARCHAR(10) NOT NULL,
    section VARCHAR(50) NOT NULL,
    seats INTEGER DEFAULT 4,
    status VARCHAR(20) DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'SEATED', 'ORDERED', 'BILLED')),
    CONSTRAINT uq_tenant_table_code UNIQUE (tenant_id, code)
);
CREATE INDEX IF NOT EXISTS ix_dining_tables_tenant_id ON dining_tables(tenant_id);
CREATE INDEX IF NOT EXISTS ix_dining_tables_status ON dining_tables(status);

-- 5. Menu Categories & Preparation Stations
CREATE TABLE IF NOT EXISTS menu_categories (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL DEFAULT 1 REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(60) UNIQUE NOT NULL,
    department VARCHAR(30) DEFAULT 'KITCHEN' CHECK (department IN ('KITCHEN', 'BAR')),
    tax_category VARCHAR(30) DEFAULT 'GST_FOOD' CHECK (tax_category IN ('GST_FOOD', 'VAT_ALCOHOL')),
    sort_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE
);
CREATE INDEX IF NOT EXISTS ix_menu_categories_name ON menu_categories(name);

-- 6. Menu Items Catalog
CREATE TABLE IF NOT EXISTS menu_items (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(120) NOT NULL,
    category VARCHAR(50) NOT NULL,
    is_veg BOOLEAN DEFAULT TRUE,
    price NUMERIC(10, 2) NOT NULL,
    hsn_code VARCHAR(20) DEFAULT '996331',
    tax_category VARCHAR(20) DEFAULT 'GST_FOOD' CHECK (tax_category IN ('GST_FOOD', 'VAT_ALCOHOL')),
    is_active BOOLEAN DEFAULT TRUE,
    is_86 BOOLEAN DEFAULT FALSE,
    description TEXT
);
CREATE INDEX IF NOT EXISTS ix_menu_items_tenant_id ON menu_items(tenant_id);
CREATE INDEX IF NOT EXISTS ix_menu_items_name ON menu_items(name);
CREATE INDEX IF NOT EXISTS ix_menu_items_category ON menu_items(category);

-- 7. Orders & Active Table Sessions
CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    table_id INTEGER NOT NULL REFERENCES dining_tables(id) ON DELETE RESTRICT,
    status VARCHAR(20) DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'COMPLETED', 'CANCELLED')),
    guest_count INTEGER DEFAULT 2,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    closed_at TIMESTAMP WITH TIME ZONE
);
CREATE INDEX IF NOT EXISTS ix_orders_tenant_id ON orders(tenant_id);
CREATE INDEX IF NOT EXISTS ix_orders_table_id ON orders(table_id);
CREATE INDEX IF NOT EXISTS ix_orders_status ON orders(status);

-- 8. Order Items
CREATE TABLE IF NOT EXISTS order_items (
    id SERIAL PRIMARY KEY,
    order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    menu_item_id INTEGER NOT NULL REFERENCES menu_items(id) ON DELETE RESTRICT,
    quantity INTEGER DEFAULT 1 CHECK (quantity > 0),
    unit_price NUMERIC(10, 2) NOT NULL,
    notes TEXT DEFAULT '',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_order_items_order_id ON order_items(order_id);

-- 9. Tax Invoices & Dual-Tax Settlement (Bills)
CREATE TABLE IF NOT EXISTS bills (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    order_id INTEGER NOT NULL UNIQUE REFERENCES orders(id) ON DELETE RESTRICT,
    invoice_number VARCHAR(50) UNIQUE NOT NULL,
    food_subtotal NUMERIC(10, 2) NOT NULL DEFAULT 0.0,
    liquor_subtotal NUMERIC(10, 2) NOT NULL DEFAULT 0.0,
    cgst NUMERIC(10, 2) NOT NULL DEFAULT 0.0,
    sgst NUMERIC(10, 2) NOT NULL DEFAULT 0.0,
    mvat NUMERIC(10, 2) NOT NULL DEFAULT 0.0,
    round_off NUMERIC(10, 2) NOT NULL DEFAULT 0.0,
    grand_total NUMERIC(10, 2) NOT NULL DEFAULT 0.0,
    payment_mode VARCHAR(20) NOT NULL CHECK (payment_mode IN ('CASH', 'UPI', 'CARD', 'SPLIT')),
    cashier_name VARCHAR(100) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_bills_invoice_number ON bills(invoice_number);

-- 9b. Tenant-Scoped Indian Financial Year Invoicing Sequences
CREATE TABLE IF NOT EXISTS invoice_counters (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    fin_year VARCHAR(10) NOT NULL,
    last_number INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_tenant_fin_year_invoice UNIQUE (tenant_id, fin_year)
);
CREATE INDEX IF NOT EXISTS ix_invoice_counters_tenant ON invoice_counters(tenant_id, fin_year);

-- 10. Cash Drawer Shifts & Blind Close
CREATE TABLE IF NOT EXISTS cash_shifts (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    cashier_id INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    opening_float NUMERIC(10, 2) NOT NULL DEFAULT 1000.00,
    cash_sales NUMERIC(10, 2) DEFAULT 0.0,
    upi_sales NUMERIC(10, 2) DEFAULT 0.0,
    card_sales NUMERIC(10, 2) DEFAULT 0.0,
    paid_out NUMERIC(10, 2) DEFAULT 0.0,
    safe_drop NUMERIC(10, 2) DEFAULT 0.0,
    closing_cash_actual NUMERIC(10, 2),
    closing_cash_expected NUMERIC(10, 2),
    cash_variance NUMERIC(10, 2),
    is_closed BOOLEAN DEFAULT FALSE,
    opened_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    closed_at TIMESTAMP WITH TIME ZONE
);
CREATE INDEX IF NOT EXISTS ix_cash_shifts_is_closed ON cash_shifts(is_closed);

-- 11. Two-Tier Inventory (Central Store vs Kitchen Line)
CREATE TABLE IF NOT EXISTS raw_materials (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    category VARCHAR(50) NOT NULL,
    uom VARCHAR(20) NOT NULL,
    store_quantity NUMERIC(10, 2) DEFAULT 0.0,
    kitchen_quantity NUMERIC(10, 2) DEFAULT 0.0,
    cost_per_uom NUMERIC(10, 2) NOT NULL,
    min_stock_limit NUMERIC(10, 2) NOT NULL DEFAULT 5.0
);

-- 12. State Excise FL-3 Liquor Daily Register (FLR-3A)
CREATE TABLE IF NOT EXISTS daily_excise_flr3a (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    brand_name VARCHAR(100) NOT NULL,
    category VARCHAR(30) NOT NULL,
    size_ml INTEGER NOT NULL,
    opening_bottles NUMERIC(10, 2) NOT NULL,
    inward_tp_bottles NUMERIC(10, 2) DEFAULT 0.0,
    sales_pegs INTEGER DEFAULT 0,
    sales_bottles INTEGER DEFAULT 0,
    breakage_bottles NUMERIC(10, 2) DEFAULT 0.0,
    closing_bottles NUMERIC(10, 2) NOT NULL,
    register_date DATE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 13. System Audit Log
CREATE TABLE IF NOT EXISTS audit_logs (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    action_type VARCHAR(50) NOT NULL,
    user_name VARCHAR(100) NOT NULL,
    details TEXT NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- SEED DATA: Rasa Sahyadri · Pune
-- ============================================================================

INSERT INTO tenants (id, name, outlet_name, address, gstin, fssai, fl3_license, vatin, phone)
VALUES (1, 'Rasa Sahyadri', 'Rasa Sahyadri (Main Koregaon Park)', 'Plot 42, Lane 7, Koregaon Park, Pune, Maharashtra 411001', '27AAKFR4621M1Z5', '11523034000412', 'FL3-MH-PUN-2026-9901', '27912345678V', '+91 20 2615 4899')
ON CONFLICT (id) DO NOTHING;

-- Staff Users (PIN: 9999 for Owner, 1234 for Cashier, 5678 for Storekeeper)
INSERT INTO users (id, tenant_id, username, display_name, role, pin_hash, is_active)
VALUES 
(1, 1, 'mahesh_patil', 'Mahesh Patil', 'OWNER', '9999', TRUE),
(2, 1, 'sachin_kadam', 'Sachin Kadam', 'MANAGER', '9999', TRUE),
(3, 1, 'pooja_more', 'Pooja More', 'CASHIER', '1234', TRUE),
(4, 1, 'ganesh_shinde', 'Ganesh Shinde', 'STOREKEEPER', '5678', TRUE)
ON CONFLICT (id) DO NOTHING;

-- Dining Tables
INSERT INTO dining_tables (id, tenant_id, code, section, seats, status)
VALUES
(1, 1, 'T1', 'Ground floor', 2, 'OPEN'),
(2, 1, 'T2', 'Ground floor', 4, 'OPEN'),
(3, 1, 'T3', 'Ground floor', 4, 'OPEN'),
(4, 1, 'T4', 'Ground floor', 6, 'OPEN'),
(5, 1, 'T5', 'Ground floor', 2, 'OPEN'),
(6, 1, 'T6', 'Ground floor', 4, 'OPEN'),
(7, 1, 'T7', 'Ground floor', 2, 'OPEN'),
(8, 1, 'T8', 'Ground floor', 6, 'OPEN'),
(9, 1, 'T9', 'Terrace', 4, 'OPEN'),
(10, 1, 'T10', 'Terrace', 4, 'OPEN'),
(11, 1, 'T11', 'Terrace', 2, 'OPEN'),
(12, 1, 'T12', 'Terrace', 6, 'OPEN'),
(13, 1, 'T13', 'Terrace', 4, 'OPEN'),
(14, 1, 'T14', 'Terrace', 4, 'OPEN'),
(15, 1, 'T15', 'Terrace', 2, 'OPEN'),
(16, 1, 'T16', 'Terrace', 8, 'OPEN')
ON CONFLICT (id) DO NOTHING;

-- Menu Categories
INSERT INTO menu_categories (name, department, tax_category, sort_order)
VALUES
('Mains', 'KITCHEN', 'GST_FOOD', 1),
('Veg Starters', 'KITCHEN', 'GST_FOOD', 2),
('Non-Veg Starters', 'KITCHEN', 'GST_FOOD', 3),
('Breakfast & Snacks', 'KITCHEN', 'GST_FOOD', 4),
('Breads', 'KITCHEN', 'GST_FOOD', 5),
('Biryani & Rice', 'KITCHEN', 'GST_FOOD', 6),
('Desserts', 'KITCHEN', 'GST_FOOD', 7),
('Beverages', 'KITCHEN', 'GST_FOOD', 8),
('Bar & Spirits', 'BAR', 'VAT_ALCOHOL', 9)
ON CONFLICT (name) DO NOTHING;
