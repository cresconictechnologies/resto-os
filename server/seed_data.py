"""
RestoOS Seed Data Script: "Rasa Sahyadri, Pune"
Populates rich, production-grade domain fixtures for:
- Tenant: Rasa Sahyadri (Koregaon Park, Pune) with GSTIN, FSSAI, Maharashtra FL-3, VAT
- Staff Accounts: Owner, Manager, Cashier, Storekeeper with SHA-256 PIN hashes
- Tables: T1 to T10 (Ground Floor), T11 to T16 (Terrace) with realistic live states (T7 active, T3 seated, T5 billed)
- Menu: 28 authentic regional dishes and bar items with dual taxation (GST_FOOD vs VAT_ALCOHOL)
- Two-Tier Inventory: Central Store & Kitchen Line raw materials, UOMs, and reorder levels
- Recipe BOMs: Precise yield and shrinkage mappings from dishes to raw ingredients
- Procurement & Internal Transfers: POs, GRNs with batch tracking, Store Indents
- Liquor Master & Maharashtra Excise: Brand catalog, Transport Permit (TP), FLR-3A Daily Register
- Operational Ledger: Open Cashier Shift with safe drops, auditable fraud-prevention event logs
"""

import hashlib
import json
import os
import sys
from datetime import datetime, timezone, date, timedelta

# Ensure UTF-8 output on Windows console
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Ensure parent directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from server.database import Base, engine, SessionLocal
from server.models import (
    Tenant,
    User,
    DiningTable,
    MenuItem,
    Order,
    OrderItem,
    Ticket,
    Bill,
    CashShift,
    RawMaterial,
    PurchaseOrder,
    PurchaseOrderItem,
    GoodsReceivedNote,
    GRNItem,
    StoreIndent,
    StoreIndentItem,
    RecipeBOM,
    WastageLog,
    LiquorBrand,
    LiquorTransportPermit,
    DailyExciseFLR3A,
    AuditLog,
)


def utcnow() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(timezone.utc)


def hash_pin(pin: str) -> str:
    """Compute standard SHA-256 hash for fast numeric PIN authentication."""
    return hashlib.sha256(pin.encode("utf-8")).hexdigest()


def seed_database():
    print("=" * 70)
    print("Initializing RestoOS Database Tables (WAL mode, Foreign Keys ON)...")
    print("=" * 70)

    # Recreate clean tables
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()

    try:
        now = utcnow()

        # ---------------------------------------------------------------------
        # 1. TENANT: Rasa Sahyadri, Koregaon Park, Pune
        # ---------------------------------------------------------------------
        print("\n[1/10] Seeding Restaurant Tenant Profile...")
        tenant = Tenant(
            name="Rasa Sahyadri",
            outlet_name="Rasa Sahyadri · Koregaon Park · Counter 1",
            address="Plot 42, Lane 7, Koregaon Park, Pune, Maharashtra 411001",
            gstin="27AAKFR4621M1Z5",
            fssai="11523034000412",
            fl3_license="FL3-PUN-KP-0412",
            vatin="27912345678V",
            phone="+91 20 2615 4890",
            created_at=now - timedelta(days=90),
        )
        db.add(tenant)
        db.flush()

        # ---------------------------------------------------------------------
        # 2. RBAC USERS (4-Digit PIN Access)
        # ---------------------------------------------------------------------
        print("[2/10] Seeding Staff Accounts & Role Credentials...")
        users = [
            User(
                tenant_id=tenant.id,
                username="mahesh_patil",
                display_name="Mahesh Patil",
                role="OWNER",
                pin_hash=hash_pin("1111"),
            ),
            User(
                tenant_id=tenant.id,
                username="sachin_kadam",
                display_name="Sachin Kadam",
                role="MANAGER",
                pin_hash=hash_pin("2222"),
            ),
            User(
                tenant_id=tenant.id,
                username="pooja_more",
                display_name="Pooja More",
                role="CASHIER",
                pin_hash=hash_pin("3333"),
            ),
            User(
                tenant_id=tenant.id,
                username="ganesh_shinde",
                display_name="Ganesh Shinde",
                role="STOREKEEPER",
                pin_hash=hash_pin("4444"),
            ),
        ]
        db.add_all(users)
        db.flush()

        # ---------------------------------------------------------------------
        # 3. DINING TABLES: T1-T10 Ground Floor, T11-T16 Terrace
        # ---------------------------------------------------------------------
        print("[3/10] Seeding Dining Floor Sections & Tables (T1-T16)...")
        tables_data = [
            # Ground floor (T1 to T10)
            ("T1", "Ground floor", 2, "OPEN", None, 0),
            ("T2", "Ground floor", 4, "OPEN", None, 0),
            ("T3", "Ground floor", 4, "SEATED", now - timedelta(minutes=20), 2),
            ("T4", "Ground floor", 4, "OPEN", None, 0),
            ("T5", "Ground floor", 6, "BILLED", now - timedelta(minutes=65), 5),
            ("T6", "Ground floor", 4, "OPEN", None, 0),
            ("T7", "Ground floor", 4, "ORDERED", now - timedelta(minutes=35), 3),
            ("T8", "Ground floor", 2, "OPEN", None, 0),
            ("T9", "Ground floor", 6, "OPEN", None, 0),
            ("T10", "Ground floor", 4, "OPEN", None, 0),
            # Terrace (T11 to T16)
            ("T11", "Terrace", 4, "OPEN", None, 0),
            ("T12", "Terrace", 4, "OPEN", None, 0),
            ("T13", "Terrace", 6, "OPEN", None, 0),
            ("T14", "Terrace", 4, "OPEN", None, 0),
            ("T15", "Terrace", 4, "OPEN", None, 0),
            ("T16", "Terrace", 8, "OPEN", None, 0),
        ]

        table_objs = {}
        for code, section, seats, status, seated_at, guests in tables_data:
            dt = DiningTable(
                tenant_id=tenant.id,
                code=code,
                section=section,
                seats=seats,
                status=status,
                seated_at=seated_at,
                guest_count=guests,
            )
            db.add(dt)
            table_objs[code] = dt
        db.flush()

        # ---------------------------------------------------------------------
        # 4. MENU ITEMS (Food & Bar Catalog with Tax Separation)
        # ---------------------------------------------------------------------
        print("[4/10] Seeding Menu Items (Breakfast, Starters, Mains, Bar)...")
        menu_items_raw = [
            # Breakfast
            ("Puneri Misal Pav", "Breakfast", True, 140.0, "996331", "GST_FOOD", "Fiery sprouted moth bean curry served with farsan, onions, lemon, and soft pavs"),
            ("Kanda Poha", "Breakfast", True, 80.0, "996331", "GST_FOOD", "Flattened rice tempered with mustard, diced onions, green chilies, and crunchy peanuts"),
            ("Kanda Bhaji", "Breakfast", True, 120.0, "996331", "GST_FOOD", "Crisp sliced onion fritters seasoned with carom seeds and green chilies"),
            ("Sabudana Vada", "Breakfast", True, 110.0, "996331", "GST_FOOD", "Crispy tapioca and mashed potato cutlets served with sweet-tangy peanut curd"),
            ("Thalipeeth with Loni", "Breakfast", True, 160.0, "996331", "GST_FOOD", "Traditional multigrain roasted flatbread accompanied by freshly churned white butter (loni)"),
            ("Vada Pav", "Breakfast", True, 45.0, "996331", "GST_FOOD", "Batata vada in pav with spicy garlic thecha and green chutney"),
            # Veg Starters
            ("Hara Bhara Kebab", "Veg Starters", True, 240.0, "996331", "GST_FOOD", "Spinach, green peas, and paneer patties pan-seared with aromatic garam masala"),
            ("Paneer Tikka", "Veg Starters", True, 280.0, "996331", "GST_FOOD", "Charcoal-grilled cottage cheese cubes in spiced yogurt and bell peppers"),
            ("Kothimbir Vadi", "Veg Starters", True, 180.0, "996331", "GST_FOOD", "Steamed and golden fried fresh cilantro and gram flour cakes"),
            # Non-Veg Starters
            ("Chicken Sukka", "Non-Veg Starters", False, 340.0, "996331", "GST_FOOD", "Tender chicken cooked dry with roasted desiccated coconut and Konkani spices"),
            ("Kolhapuri Chicken", "Non-Veg Starters", False, 380.0, "996331", "GST_FOOD", "Fiery pan-roasted chicken tossed with red Lavangi chilies and Kolhapuri masala"),
            ("Surmai Fry", "Non-Veg Starters", False, 480.0, "996331", "GST_FOOD", "Fresh Kingfish steak marinated in coastal spices and rava-crusted on tawa"),
            # Mains
            ("Maharashtrian Veg Thali", "Mains", True, 380.0, "996331", "GST_FOOD", "Complete feast: Bharli Vangi, Pithla, Dal Tadka, 2 Jowar Bhakris, Indrayani Rice, Koshimbir, Sol Kadhi"),
            ("Kolhapuri Chicken Thali", "Mains", False, 515.0, "996331", "GST_FOOD", "Kolhapuri Chicken Sukka, Tambda Rassa (red curry), Pandhra Rassa (white mutton broth), 2 Bhakris, Rice"),
            ("Mutton Rassa Full", "Mains", False, 750.0, "996331", "GST_FOOD", "Authentic Maratha slow-cooked goat curry paired with rich Tambda & Pandhra rassa"),
            ("Bharli Vangi", "Mains", True, 240.0, "996331", "GST_FOOD", "Baby brinjals stuffed with roasted peanuts, sesame seeds, and fragrant goda masala"),
            ("Masale Bhaat", "Mains", True, 260.0, "996331", "GST_FOOD", "Aromatic spiced rice cooked with ivy gourd (tindli), cashews, and fresh grated coconut"),
            # Breads
            ("Jowar Bhakri", "Breads", True, 35.0, "996331", "GST_FOOD", "Hand-flattened sorghum flatbread baked over clay tawa"),
            ("Chapati", "Breads", True, 25.0, "996331", "GST_FOOD", "Soft homemade whole wheat phulka roasted with pure ghee"),
            ("Butter Roti", "Breads", True, 30.0, "996331", "GST_FOOD", "Clay oven roasted tandoori roti with churned butter"),
            # Bar (MVAT Taxed)
            ("Blenders Pride 750ml", "Bar", False, 220.0, "220830", "VAT_ALCOHOL", "Blended Indian Whisky (60ml peg measure)"),
            ("Royal Challenge", "Bar", False, 190.0, "220830", "VAT_ALCOHOL", "Premium Grain Whisky (60ml peg measure)"),
            ("Old Monk Rum", "Bar", False, 150.0, "220840", "VAT_ALCOHOL", "Classic Vatted Dark Rum (60ml peg measure)"),
            ("Kingfisher Premium 650ml", "Bar", False, 280.0, "220300", "VAT_ALCOHOL", "Chilled Mild Lager Beer (650ml bottle)"),
            ("Corona Extra 330ml", "Bar", False, 340.0, "220300", "VAT_ALCOHOL", "Mexican Imported Lager served with lime wedge (330ml bottle)"),
            ("Sula Shiraz Wine", "Bar", False, 350.0, "220421", "VAT_ALCOHOL", "Nashik Valley Reserve Red Wine (150ml glass)"),
            # Non-Alcoholic Beverages (GST Taxed)
            ("Kokum Sharbat", "Beverages", True, 90.0, "220299", "GST_FOOD", "Refreshing Konkan wild kokum cooler with roasted cumin and rock salt"),
            ("Sol Kadhi", "Beverages", True, 90.0, "220299", "GST_FOOD", "Digestive elixir of freshly extracted coconut milk, tangy kokum, and green chili"),
        ]

        menu_items_map = {}
        for name, category, is_veg, price, hsn, tax_cat, desc in menu_items_raw:
            item = MenuItem(
                tenant_id=tenant.id,
                name=name,
                category=category,
                is_veg=is_veg,
                price=price,
                hsn_code=hsn,
                tax_category=tax_cat,
                is_active=True,
                is_86=False,
                description=desc,
            )
            db.add(item)
            menu_items_map[name] = item
        db.flush()

        # ---------------------------------------------------------------------
        # 5. TWO-TIER INVENTORY: RAW MATERIALS (Store & Kitchen Stock)
        # ---------------------------------------------------------------------
        print("[5/10] Seeding Raw Materials & Two-Tier Stock Quantities...")
        materials_data = [
            # Name, Category, UOM, Store Stock, Kitchen Stock, Min Reorder, Unit Cost
            ("Chicken (Fresh Bone-In)", "MEAT", "kg", 45.0, 12.5, 15.0, 220.0),
            ("Mutton (Goat Curry Cut)", "MEAT", "kg", 25.0, 8.0, 10.0, 680.0),
            ("Surmai Fish (Fresh Kingfish)", "MEAT", "kg", 15.0, 5.0, 5.0, 850.0),
            ("Potatoes (Batata)", "PRODUCE", "kg", 80.0, 25.0, 30.0, 32.0),
            ("Onions (Nashik Red)", "PRODUCE", "kg", 95.0, 30.0, 40.0, 28.0),
            ("Fresh Coconuts", "PRODUCE", "pcs", 50.0, 20.0, 15.0, 25.0),
            ("Refined Groundnut Oil", "GROCERY", "L", 120.0, 35.0, 50.0, 145.0),
            ("Malwa Paneer (Fresh)", "DAIRY", "kg", 18.0, 6.0, 8.0, 360.0),
            ("Indrayani Basmati Rice", "GROCERY", "kg", 150.0, 40.0, 50.0, 75.0),
            ("Jowar Flour (Sorghum)", "GROCERY", "kg", 60.0, 15.0, 20.0, 55.0),
            ("Puneri Special Farsan", "GROCERY", "kg", 30.0, 10.0, 10.0, 180.0),
            ("Fresh White Butter (Loni)", "DAIRY", "kg", 20.0, 5.0, 5.0, 520.0),
        ]

        materials_map = {}
        for name, cat, uom, store_stk, kitchen_stk, reorder, cost in materials_data:
            mat = RawMaterial(
                tenant_id=tenant.id,
                name=name,
                category=cat,
                uom=uom,
                current_store_stock=store_stk,
                current_kitchen_stock=kitchen_stk,
                min_reorder_level=reorder,
                unit_cost=cost,
            )
            db.add(mat)
            materials_map[name] = mat
        db.flush()

        # ---------------------------------------------------------------------
        # 6. RECIPE BILL OF MATERIALS (BOM)
        # ---------------------------------------------------------------------
        print("[6/10] Seeding Recipe BOM Mappings with Yields & Shrinkage...")
        recipes = [
            # Puneri Misal Pav
            ("Puneri Misal Pav", "Potatoes (Batata)", 0.100, 95.0),
            ("Puneri Misal Pav", "Onions (Nashik Red)", 0.050, 90.0),
            ("Puneri Misal Pav", "Refined Groundnut Oil", 0.020, 100.0),
            ("Puneri Misal Pav", "Puneri Special Farsan", 0.080, 100.0),
            # Kanda Poha
            ("Kanda Poha", "Onions (Nashik Red)", 0.100, 90.0),
            ("Kanda Poha", "Potatoes (Batata)", 0.050, 95.0),
            ("Kanda Poha", "Refined Groundnut Oil", 0.020, 100.0),
            # Kolhapuri Chicken Thali
            ("Kolhapuri Chicken Thali", "Chicken (Fresh Bone-In)", 0.350, 85.0),
            ("Kolhapuri Chicken Thali", "Onions (Nashik Red)", 0.150, 90.0),
            ("Kolhapuri Chicken Thali", "Refined Groundnut Oil", 0.040, 100.0),
            ("Kolhapuri Chicken Thali", "Indrayani Basmati Rice", 0.100, 100.0),
            # Mutton Rassa Full
            ("Mutton Rassa Full", "Mutton (Goat Curry Cut)", 0.500, 80.0),
            ("Mutton Rassa Full", "Onions (Nashik Red)", 0.200, 90.0),
            ("Mutton Rassa Full", "Refined Groundnut Oil", 0.050, 100.0),
            # Paneer Tikka
            ("Paneer Tikka", "Malwa Paneer (Fresh)", 0.250, 98.0),
            ("Paneer Tikka", "Refined Groundnut Oil", 0.020, 100.0),
            ("Paneer Tikka", "Fresh White Butter (Loni)", 0.030, 100.0),
            # Jowar Bhakri
            ("Jowar Bhakri", "Jowar Flour (Sorghum)", 0.120, 100.0),
            # Sol Kadhi
            ("Sol Kadhi", "Fresh Coconuts", 0.500, 70.0),
            # Surmai Fry
            ("Surmai Fry", "Surmai Fish (Fresh Kingfish)", 0.220, 90.0),
            ("Surmai Fry", "Refined Groundnut Oil", 0.040, 100.0),
        ]

        for dish_name, mat_name, qty, yld in recipes:
            if dish_name in menu_items_map and mat_name in materials_map:
                bom = RecipeBOM(
                    menu_item_id=menu_items_map[dish_name].id,
                    raw_material_id=materials_map[mat_name].id,
                    quantity_required=qty,
                    prep_shrinkage_yield_pct=yld,
                )
                db.add(bom)
        db.flush()

        # ---------------------------------------------------------------------
        # 7. PROCUREMENT & TRANSFERS: PO, GRN, STORE INDENT, WASTAGE
        # ---------------------------------------------------------------------
        print("[7/10] Seeding Procurement PO, Inward GRN, Store Indent & Wastage...")
        # Purchase Order
        po1 = PurchaseOrder(
            tenant_id=tenant.id,
            po_number="PO-2026-10-011",
            vendor_name="Pune Fresh Agro Wholesale Ltd",
            status="RECEIVED",
            total_amount=15420.0,
            created_at=now - timedelta(days=2),
        )
        db.add(po1)
        db.flush()

        po_item1 = PurchaseOrderItem(
            purchase_order_id=po1.id,
            raw_material_id=materials_map["Potatoes (Batata)"].id,
            ordered_qty=100.0,
            unit_price=30.0,
        )
        po_item2 = PurchaseOrderItem(
            purchase_order_id=po1.id,
            raw_material_id=materials_map["Onions (Nashik Red)"].id,
            ordered_qty=120.0,
            unit_price=26.0,
        )
        db.add_all([po_item1, po_item2])

        # Goods Received Note
        grn1 = GoodsReceivedNote(
            tenant_id=tenant.id,
            grn_number="GRN-2026-10-008",
            po_id=po1.id,
            vendor_invoice_no="INV-PUNE-8921",
            received_at=now - timedelta(days=1, hours=4),
        )
        db.add(grn1)
        db.flush()

        grn_item1 = GRNItem(
            grn_id=grn1.id,
            raw_material_id=materials_map["Potatoes (Batata)"].id,
            batch_no="BATCH-POT-261025",
            expiry_date=date.today() + timedelta(days=18),
            received_qty=100.0,
            invoice_price=30.0,
        )
        grn_item2 = GRNItem(
            grn_id=grn1.id,
            raw_material_id=materials_map["Onions (Nashik Red)"].id,
            batch_no="BATCH-ONI-261025",
            expiry_date=date.today() + timedelta(days=25),
            received_qty=120.0,
            invoice_price=26.0,
        )
        db.add_all([grn_item1, grn_item2])

        # Store Indent: Central Store to Kitchen Transfer
        indent1 = StoreIndent(
            tenant_id=tenant.id,
            indent_number="IND-2026-10-042",
            department="Main Kitchen Hot Line",
            status="ISSUED",
            issued_at=now - timedelta(hours=6),
        )
        db.add(indent1)
        db.flush()

        indent_item1 = StoreIndentItem(
            indent_id=indent1.id,
            raw_material_id=materials_map["Chicken (Fresh Bone-In)"].id,
            requested_qty=15.0,
            issued_qty=15.0,
        )
        indent_item2 = StoreIndentItem(
            indent_id=indent1.id,
            raw_material_id=materials_map["Onions (Nashik Red)"].id,
            requested_qty=20.0,
            issued_qty=20.0,
        )
        db.add_all([indent_item1, indent_item2])

        # Kitchen Wastage Log
        wastage1 = WastageLog(
            tenant_id=tenant.id,
            raw_material_id=materials_map["Mutton (Goat Curry Cut)"].id,
            quantity=0.650,
            reason_code="TRIM",
            authorized_by="Sachin Kadam",
            notes="Excess connective tendon tissue excised during prep",
            created_at=now - timedelta(hours=5),
        )
        db.add(wastage1)

        # ---------------------------------------------------------------------
        # 8. LIQUOR BAR & MAHARASHTRA STATE EXCISE FLR-3A
        # ---------------------------------------------------------------------
        print("[8/10] Seeding Liquor Brands, Transport Permits & FLR-3A Register...")
        liquor_brands_data = [
            # Name, Category, Size, Excise Code, MRP, VAT %, Sealed, Open ml
            ("Blenders Pride 750ml", "IMFL_WHISKY", 750, "MH-EXC-IMFL-0941", 980.0, 10.0, 24, 450),
            ("Royal Challenge", "IMFL_WHISKY", 750, "MH-EXC-IMFL-0812", 860.0, 10.0, 18, 390),
            ("Old Monk Rum", "RUM", 750, "MH-EXC-RUM-0104", 620.0, 10.0, 30, 540),
            ("Kingfisher Premium 650ml", "BEER_MILD", 650, "MH-EXC-BEER-0322", 180.0, 10.0, 72, 0),
            ("Corona Extra 330ml", "BEER_MILD", 330, "MH-EXC-BEER-0551", 260.0, 10.0, 48, 0),
            ("Sula Shiraz Wine", "WINE", 750, "MH-EXC-WINE-0419", 890.0, 10.0, 15, 300),
        ]

        bar_brand_map = {}
        for b_name, b_cat, b_size, b_code, b_mrp, b_vat, b_sealed, b_open in liquor_brands_data:
            lb = LiquorBrand(
                tenant_id=tenant.id,
                brand_name=b_name,
                category=b_cat,
                bottle_size_ml=b_size,
                state_excise_code=b_code,
                mrp=b_mrp,
                vat_percent=b_vat,
                sealed_bottles=b_sealed,
                open_bottle_ml=b_open,
            )
            db.add(lb)
            bar_brand_map[b_name] = lb
        db.flush()

        # Liquor Transport Permit (TP)
        tp1 = LiquorTransportPermit(
            tenant_id=tenant.id,
            tp_number="TP-MH-PUN-2026-0881",
            tp_date=date.today() - timedelta(days=1),
            supplier_name="Maharashtra State Beverages Corporation Ltd (MSBCL Depot 4)",
            vehicle_no="MH-12-RN-4821",
            invoice_no="MSBCL-INV-99341",
            total_cases=15,
            total_bottles=180,
            created_at=now - timedelta(days=1),
        )
        db.add(tp1)
        db.flush()

        # FLR-3A Daily Register for today
        for b_name, lb in bar_brand_map.items():
            tp_rec = 12 if "Beer" in b_name else 0
            sales = 120 if "Whisky" in lb.category or "RUM" in lb.category else 0
            breakage = 0
            tot_in = (lb.sealed_bottles * lb.bottle_size_ml) + lb.open_bottle_ml + (tp_rec * lb.bottle_size_ml)
            tot_rem = tot_in - sales - breakage
            c_sealed = tot_rem // lb.bottle_size_ml
            c_open = tot_rem % lb.bottle_size_ml

            reg = DailyExciseFLR3A(
                tenant_id=tenant.id,
                register_date=date.today(),
                brand_id=lb.id,
                opening_sealed=lb.sealed_bottles,
                opening_open_ml=lb.open_bottle_ml,
                tp_received_bottles=tp_rec,
                sales_ml=sales,
                breakage_ml=breakage,
                closing_sealed=c_sealed,
                closing_open_ml=c_open,
            )
            db.add(reg)
        db.flush()

        # ---------------------------------------------------------------------
        # 9. LIVE ORDERS, TICKETS (KOT/BOT) & BILLING TRANSACTIONS
        # ---------------------------------------------------------------------
        print("[9/10] Seeding Live Table Orders (T7 Active, T5 Billed, T3 Seated)...")

        # --- Table T7: Live Running Order ---
        order_t7 = Order(
            tenant_id=tenant.id,
            table_id=table_objs["T7"].id,
            order_type="DINE_IN",
            status="ACTIVE",
            created_at=now - timedelta(minutes=30),
        )
        db.add(order_t7)
        db.flush()

        items_t7 = [
            OrderItem(
                order_id=order_t7.id,
                menu_item_id=menu_items_map["Kolhapuri Chicken Thali"].id,
                item_name="Kolhapuri Chicken Thali",
                quantity=2,
                unit_price=515.0,
                prep_note="Extra tambda rassa bowl",
                is_kot_printed=True,
                status="PREPARING",
            ),
            OrderItem(
                order_id=order_t7.id,
                menu_item_id=menu_items_map["Jowar Bhakri"].id,
                item_name="Jowar Bhakri",
                quantity=4,
                unit_price=35.0,
                prep_note="Hot crisp",
                is_kot_printed=True,
                status="PREPARING",
            ),
            OrderItem(
                order_id=order_t7.id,
                menu_item_id=menu_items_map["Sol Kadhi"].id,
                item_name="Sol Kadhi",
                quantity=2,
                unit_price=90.0,
                prep_note="Chilled",
                is_kot_printed=True,
                status="SERVED",
            ),
            OrderItem(
                order_id=order_t7.id,
                menu_item_id=menu_items_map["Blenders Pride 750ml"].id,
                item_name="Blenders Pride 750ml (60ml Peg)",
                quantity=2,
                unit_price=220.0,
                prep_note="With soda and ice cubes",
                is_bot_printed=True,
                status="SERVED",
            ),
        ]
        db.add_all(items_t7)

        # KOT for Kitchen Items
        kot_t7 = Ticket(
            tenant_id=tenant.id,
            order_id=order_t7.id,
            ticket_number="KOT-0081",
            ticket_type="KOT",
            table_code="T7",
            payload_json=json.dumps({
                "ticket_no": "KOT-0081",
                "table": "T7",
                "server": "Sachin Kadam",
                "items": [
                    {"name": "Kolhapuri Chicken Thali", "qty": 2, "note": "Extra tambda rassa bowl"},
                    {"name": "Jowar Bhakri", "qty": 4, "note": "Hot crisp"},
                    {"name": "Sol Kadhi", "qty": 2, "note": "Chilled"},
                ],
                "time": (now - timedelta(minutes=28)).isoformat(),
            }),
            printed_at=now - timedelta(minutes=28),
        )
        # BOT for Bar Items
        bot_t7 = Ticket(
            tenant_id=tenant.id,
            order_id=order_t7.id,
            ticket_number="BOT-0034",
            ticket_type="BOT",
            table_code="T7",
            payload_json=json.dumps({
                "ticket_no": "BOT-0034",
                "table": "T7",
                "server": "Sachin Kadam",
                "items": [
                    {"name": "Blenders Pride 750ml (60ml Peg)", "qty": 2, "note": "With soda and ice cubes"},
                ],
                "time": (now - timedelta(minutes=29)).isoformat(),
            }),
            printed_at=now - timedelta(minutes=29),
        )
        db.add_all([kot_t7, bot_t7])

        # --- Table T5: Completed & Billed Order ---
        order_t5 = Order(
            tenant_id=tenant.id,
            table_id=table_objs["T5"].id,
            order_type="DINE_IN",
            status="BILLED",
            created_at=now - timedelta(minutes=60),
        )
        db.add(order_t5)
        db.flush()

        items_t5 = [
            OrderItem(
                order_id=order_t5.id,
                menu_item_id=menu_items_map["Maharashtrian Veg Thali"].id,
                item_name="Maharashtrian Veg Thali",
                quantity=2,
                unit_price=380.0,
                is_kot_printed=True,
                status="SERVED",
            ),
            OrderItem(
                order_id=order_t5.id,
                menu_item_id=menu_items_map["Kothimbir Vadi"].id,
                item_name="Kothimbir Vadi",
                quantity=1,
                unit_price=180.0,
                is_kot_printed=True,
                status="SERVED",
            ),
            OrderItem(
                order_id=order_t5.id,
                menu_item_id=menu_items_map["Kokum Sharbat"].id,
                item_name="Kokum Sharbat",
                quantity=2,
                unit_price=90.0,
                is_kot_printed=True,
                status="SERVED",
            ),
        ]
        db.add_all(items_t5)

        # Tax calculation for Table T5:
        # Food Subtotal: (2 * 380) + (1 * 180) + (2 * 90) = 760 + 180 + 180 = 1120.0
        # CGST (2.5%): 28.00
        # SGST (2.5%): 28.00
        # Grand Total: 1176.00
        bill_t5 = Bill(
            tenant_id=tenant.id,
            order_id=order_t5.id,
            invoice_number="KPB3/2026/009001",
            food_subtotal=1120.0,
            food_cgst=28.0,
            food_sgst=28.0,
            liquor_subtotal=0.0,
            liquor_vat=0.0,
            round_off=0.0,
            grand_total=1176.0,
            payment_mode="UPI",
            payment_status="PAID",
            created_at=now - timedelta(minutes=10),
        )
        db.add(bill_t5)

        # ---------------------------------------------------------------------
        # 10. CASH SHIFT & FRAUD PREVENTION AUDIT LOGS
        # ---------------------------------------------------------------------
        print("[10/10] Seeding Cashier Shift Session & Security Audit Trail...")
        # Open Cash Shift for Cashier Pooja More
        shift = CashShift(
            tenant_id=tenant.id,
            cashier_name="Pooja More",
            opened_at=now.replace(hour=5, minute=30, second=0, microsecond=0),  # 11:00 AM IST
            opening_float=5000.0,
            cash_sales=18450.0,
            paid_in=0.0,
            paid_out=450.0,      # Urgent kitchen ice purchase
            safe_drops=15000.0,   # Cash drop to main safe
            counted_cash=None,
            variance=None,
            closed_at=None,
            is_closed=False,
        )
        db.add(shift)

        # Audit Logs
        audit_events = [
            (
                "DRAWER_KICK_MANUAL",
                "Pooja More",
                {"reason": "Change breakdown for 500 Rupee note", "supervisor": "Sachin Kadam"},
                now - timedelta(hours=3),
            ),
            (
                "VOID_KOT",
                "Sachin Kadam",
                {"table": "T9", "item": "Kanda Bhaji", "qty": 1, "reason": "Guest allergic to onion, replaced with Sabudana Vada"},
                now - timedelta(hours=2),
            ),
            (
                "DISCOUNT_MANUAL",
                "Mahesh Patil",
                {"invoice": "KPB3/2026/008998", "discount_pct": 10.0, "amount": 210.0, "reason": "Pune Corporate Club Partner Privilege"},
                now - timedelta(hours=4),
            ),
            (
                "RATE_CHANGE",
                "Mahesh Patil",
                {"item": "Surmai Fry", "old_rate": 450.0, "new_rate": 480.0, "reason": "Konkan jetty fresh fish wholesale price surge"},
                now - timedelta(days=1),
            ),
        ]

        for action, staff, details, ts in audit_events:
            audit = AuditLog(
                tenant_id=tenant.id,
                timestamp=ts,
                staff_name=staff,
                action_type=action,
                details_json=json.dumps(details),
            )
            db.add(audit)

        # Commit everything atomically
        db.commit()
        print("\n" + "=" * 70)
        print("RestoOS Database Seeding Completed Successfully!")
        print(f"Database File: {engine.url.database}")
        print("Summary of Seeded Entities:")
        print(f"  • Tenants:           {db.query(Tenant).count()}")
        print(f"  • Users (RBAC):      {db.query(User).count()}")
        print(f"  • Dining Tables:     {db.query(DiningTable).count()}")
        print(f"  • Menu Items:        {db.query(MenuItem).count()}")
        print(f"  • Raw Materials:     {db.query(RawMaterial).count()}")
        print(f"  • Recipe BOMs:       {db.query(RecipeBOM).count()}")
        print(f"  • Purchase Orders:   {db.query(PurchaseOrder).count()}")
        print(f"  • GRN Inwards:       {db.query(GoodsReceivedNote).count()}")
        print(f"  • Store Indents:     {db.query(StoreIndent).count()}")
        print(f"  • Wastage Logs:      {db.query(WastageLog).count()}")
        print(f"  • Liquor Brands:     {db.query(LiquorBrand).count()}")
        print(f"  • Transport Permits: {db.query(LiquorTransportPermit).count()}")
        print(f"  • FLR-3A Records:    {db.query(DailyExciseFLR3A).count()}")
        print(f"  • Live Orders:       {db.query(Order).count()}")
        print(f"  • KOT/BOT Tickets:   {db.query(Ticket).count()}")
        print(f"  • Invoices (Bills):  {db.query(Bill).count()}")
        print(f"  • Cash Shifts:       {db.query(CashShift).count()}")
        print(f"  • Audit Logs:        {db.query(AuditLog).count()}")
        print("=" * 70)

    except Exception as e:
        db.rollback()
        print(f"ERROR: Seeding failed due to: {e}", file=sys.stderr)
        raise e
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
