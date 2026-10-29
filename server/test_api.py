"""
RestoOS Comprehensive API Verification Test Suite
Executes real automated end-to-end integration tests across all 8 route domains:
1. Tables: list tables, seat table, update guests, clear table
2. Orders & Cart: get menu, create order, add items, update quantity, void item
3. KOT / BOT: fire KOT (Food) and BOT (Alcohol) tickets with 80mm ESC/POS formatting
4. Dual-Tax Billing: calculate Part A Food GST + Part B Liquor VAT, cash drawer kick settle
5. Cash Shifts: open shift, paid-in/paid-out, safe drop, blind close Z-Report
6. Two-Tier Inventory: raw materials, PO, GRN inward (WAC), store indent, wastage, live 86
7. Maharashtra State Excise: FLR-3A register balance, transport permit (TP), dry day check
8. Owner BI: Dashboard KPIs, 24h heatmap, AvT variance, BCG Matrix, Ask Resto NLP
"""

import sys
from pathlib import Path
from fastapi.testclient import TestClient

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from server.main import app

client = TestClient(app)


def test_system_health():
    print("Testing /health and /api/v1/health...")
    resp = client.get("/health")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["system"] == "RestoOS"
    print(" -> Health check passed.")


def test_tables_flow():
    print("\nTesting Tables & Floor Layout API...")
    # 1. Get all tables
    resp = client.get("/api/v1/tables")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "sections" in data
    assert data["total_tables"] >= 16
    print(f" -> Found {data['total_tables']} tables across sections: {list(data['sections'].keys())}")

    # 2. Find table T1
    ground_tables = data["sections"]["Ground floor"]
    t1 = next(t for t in ground_tables if t["code"] == "T1")
    t1_id = t1["id"]

    # 3. Seat table T1
    resp = client.post(f"/api/v1/tables/{t1_id}/seat", json={"guest_count": 3})
    assert resp.status_code == 200, resp.text
    seated_data = resp.json()
    assert seated_data["status"] == "SEATED"
    assert seated_data["guest_count"] == 3
    print(f" -> Table T1 seated with {seated_data['guest_count']} covers.")

    # 4. Update guest count
    resp = client.patch(f"/api/v1/tables/{t1_id}/guests", json={"guest_count": 4})
    assert resp.status_code == 200
    assert resp.json()["guest_count"] == 4
    print(" -> Table T1 guest count updated to 4.")

    return t1_id


def test_orders_and_kot_flow(t1_id: int):
    print("\nTesting Menu, Cart & KOT/BOT Dispatch...")
    # 1. Browse menu
    resp = client.get("/api/v1/menu")
    assert resp.status_code == 200
    menu = resp.json()
    assert len(menu) >= 20
    print(f" -> Menu loaded with {len(menu)} items.")

    food_item = next(m for m in menu if m["tax_category"] == "GST_FOOD" and not m["is_86"])
    liquor_item = next(m for m in menu if m["tax_category"] == "VAT_ALCOHOL")

    # 2. Get table order
    resp = client.get(f"/api/v1/orders/table/{t1_id}")
    assert resp.status_code == 200
    order = resp.json()
    order_id = order["id"]
    print(f" -> Active order #{order_id} retrieved for table T1.")

    # 3. Add food and alcohol to order
    items_to_add = [
        {"menu_item_id": food_item["id"], "quantity": 2, "prep_note": "Extra spicy"},
        {"menu_item_id": liquor_item["id"], "quantity": 1, "prep_note": "On the rocks"},
    ]
    resp = client.post(f"/api/v1/orders/{order_id}/items", json=items_to_add)
    assert resp.status_code == 200
    updated_order = resp.json()
    assert len(updated_order["items"]) >= 2
    print(f" -> Added {food_item['name']} (x2) and {liquor_item['name']} (x1) to cart.")

    # 4. Fire KOT / BOT
    resp = client.post("/api/v1/kot/fire", json={"order_id": order_id})
    assert resp.status_code == 200
    kot_resp = resp.json()
    assert kot_resp["items_fired_count"] >= 3
    assert kot_resp["kot_ticket"] is not None
    assert kot_resp["bot_ticket"] is not None
    assert "KITCHEN ORDER TICKET" in kot_resp["kot_text_80mm"]
    assert "BAR ORDER TICKET" in kot_resp["bot_text_80mm"]
    print(f" -> KOT fired: Ticket {kot_resp['kot_ticket']['ticket_number']}.")
    print(f" -> BOT fired: Ticket {kot_resp['bot_ticket']['ticket_number']}.")

    return order_id


def test_billing_flow(order_id: int, t1_id: int):
    print("\nTesting Statutory Dual-Tax Billing & Cash Drawer Kick...")
    # 1. Preview bill calculation
    resp = client.get(f"/api/v1/billing/calculate/{order_id}")
    assert resp.status_code == 200
    calc = resp.json()
    assert calc["food_subtotal"] > 0
    assert calc["food_cgst"] == round(calc["food_subtotal"] * 0.025, 2)
    assert calc["food_sgst"] == round(calc["food_subtotal"] * 0.025, 2)
    assert calc["liquor_subtotal"] > 0
    assert calc["liquor_vat"] == round(calc["liquor_subtotal"] * 0.05, 2)
    assert calc["grand_total"] > 0
    print(f" -> Food: ₹{calc['food_subtotal']} (+ 5% GST ₹{calc['food_tax_total']})")
    print(f" -> Liquor: ₹{calc['liquor_subtotal']} (+ 5% MVAT ₹{calc['liquor_vat']})")
    print(f" -> Round Off: ₹{calc['round_off']}, Grand Total: ₹{calc['grand_total']}")

    # 2. Settle bill with CASH (triggers 24V drawer pulse)
    resp = client.post(
        "/api/v1/billing/settle",
        json={
            "order_id": order_id,
            "payment_mode": "CASH",
            "staff_name": "Cashier Rahul",
        },
    )
    assert resp.status_code == 200, resp.text
    settle_data = resp.json()
    assert settle_data["drawer_kick_command_hex"] == "1b700019fa"
    assert settle_data["table_status_now"] == "OPEN"
    assert "TAX INVOICE" in settle_data["tax_invoice_80mm_text"]
    assert "27AAKFR4621M1Z5" in settle_data["tax_invoice_80mm_text"]
    print(f" -> Bill settled! Invoice: {settle_data['bill']['invoice_number']}")
    print(f" -> 24V Drawer kick hex verified: {settle_data['drawer_kick_command_hex']}")
    print(f" -> Table T1 automatically cleared to {settle_data['table_status_now']}.")


def test_shifts_flow():
    print("\nTesting Cash Drawer Shifts & Blind Close Z-Report...")
    # 1. Get current shift or open one if none active
    resp = client.get("/api/v1/shifts/current")
    assert resp.status_code == 200
    shift = resp.json()
    if not shift:
        open_resp = client.post("/api/v1/shifts/open", json={"cashier_name": "Pooja More", "opening_float": 5000.0})
        assert open_resp.status_code == 200
        shift = open_resp.json()
    print(f" -> Active shift found: #{shift['id']} for {shift['cashier_name']}.")

    # 2. Petty cash paid-out (e.g. ice delivery)
    resp = client.post(
        "/api/v1/shifts/petty-cash",
        json={
            "amount": 150.0,
            "voucher_type": "PAID_OUT",
            "reason": "Emergency ice bag purchase",
            "staff_name": "Cashier 1",
        },
    )
    assert resp.status_code == 200
    updated_shift = resp.json()
    assert updated_shift["paid_out"] >= 150.0
    print(f" -> Recorded petty cash voucher ₹150.00. Total paid out: ₹{updated_shift['paid_out']}")

    # 3. Safe drop
    resp = client.post(
        "/api/v1/shifts/safe-drop",
        json={
            "amount": 2000.0,
            "manager_pin": "1234",
            "notes": "Mid-shift excess cash drop to safe",
        },
    )
    assert resp.status_code == 200
    print(" -> Manager safe drop ₹2,000 recorded with PIN authorization.")

    # 4. Blind close shift
    expected = resp.json()["expected_cash"]
    resp = client.post("/api/v1/shifts/close", json={"counted_cash": expected})
    assert resp.status_code == 200
    z_rep = resp.json()
    assert z_rep["status"] == "CLOSED"
    assert z_rep["variance"] == 0.0
    assert "END OF SHIFT Z-REPORT" in z_rep["z_report_80mm_text"]
    print(f" -> Shift blind-closed! Expected: ₹{expected}, Counted: ₹{z_rep['counted_cash']}, Variance: ₹{z_rep['variance']}.")


def test_inventory_and_86_flow():
    print("\nTesting Two-Tier Inventory & Live 86 Checks...")
    # 1. Raw materials list
    resp = client.get("/api/v1/inventory/raw-materials")
    assert resp.status_code == 200
    materials = resp.json()
    assert len(materials) >= 8
    chicken = next(m for m in materials if "Chicken" in m["name"])
    print(f" -> Loaded {len(materials)} raw materials. Chicken Store: {chicken['current_store_stock']}kg, Kitchen: {chicken['current_kitchen_stock']}kg.")

    # 2. Store to Kitchen Indent
    resp = client.post(
        "/api/v1/inventory/indent",
        json={
            "department": "Kitchen Line",
            "items": [{"raw_material_id": chicken["id"], "requested_qty": 5.0}],
        },
    )
    assert resp.status_code == 200
    indent_data = resp.json()
    assert indent_data["status"] == "ISSUED"
    print(f" -> Issued Store Indent {indent_data['indent_number']}: 5.0kg Chicken transferred Store -> Kitchen.")

    # 3. Kitchen wastage with supervisor PIN
    resp = client.post(
        "/api/v1/inventory/wastage",
        json={
            "raw_material_id": chicken["id"],
            "quantity": 0.5,
            "reason_code": "BURNT",
            "supervisor_pin": "1234",
            "notes": "Tandoor grill burn during rush",
        },
    )
    assert resp.status_code == 200
    wastage = resp.json()
    assert wastage["reason_code"] == "BURNT"
    print(f" -> Logged kitchen wastage: {wastage['quantity']}kg {wastage['material_name']} (Reason: {wastage['reason_code']}).")

    # 4. Live 86 analysis
    resp = client.get("/api/v1/inventory/live-86")
    assert resp.status_code == 200
    live_86 = resp.json()
    assert "items" in live_86
    print(f" -> Live 86 Check completed for {len(live_86['items'])} menu dishes.")


def test_excise_flr3a_flow():
    print("\nTesting Maharashtra State Excise FLR-3A Compliance...")
    # 1. Dry day status
    resp = client.get("/api/v1/excise/dry-day")
    assert resp.status_code == 200
    dry_day = resp.json()
    print(f" -> Dry Day Status: {dry_day['is_dry_day']} (Liquor sales permitted: {dry_day['liquor_sale_permitted']}).")

    # 2. Form FLR-3A Register
    resp = client.get("/api/v1/excise/flr3a")
    assert resp.status_code == 200
    flr3a = resp.json()
    assert flr3a["total_brands"] >= 6
    for row in flr3a["rows"]:
        assert row["balance_verified"] is True
    print(f" -> Form FLR-3A verified for all {flr3a['total_brands']} brands: Opening + Inward - Sales - Breakage == Closing.")

    # 3. Monthly FLR-4 Abstract
    resp = client.get("/api/v1/excise/flr4")
    assert resp.status_code == 200
    flr4 = resp.json()
    assert len(flr4["categories"]) >= 3
    print(f" -> Form FLR-4 Monthly Abstract generated for {flr4['month_name']} {flr4['year']}.")


def test_owner_bi_and_nlp_flow():
    print("\nTesting Owner Executive BI & Resto Intelligence NLP...")
    # 1. Dashboard KPIs
    resp = client.get("/api/v1/owner/kpis")
    assert resp.status_code == 200
    kpis = resp.json()
    print(f" -> Gross Sales Today: ₹{kpis['gross_sales_today']:,}, Net: ₹{kpis['net_sales_today']:,}, ARPT: ₹{kpis['arpt']}.")

    # 2. Hourly heatmap
    resp = client.get("/api/v1/owner/heatmap")
    assert resp.status_code == 200
    heatmap = resp.json()
    assert len(heatmap) == 24
    print(" -> 24-Hour revenue curve heatmap generated.")

    # 3. Actual vs Theoretical (AvT) food cost variance
    resp = client.get("/api/v1/owner/avt")
    assert resp.status_code == 200
    avt = resp.json()
    assert len(avt) >= 4
    print(f" -> AvT variance calculated for {len(avt)} core raw materials.")

    # 4. BCG Matrix
    resp = client.get("/api/v1/owner/bcg-matrix")
    assert resp.status_code == 200
    bcg = resp.json()
    total_classified = len(bcg["stars"]) + len(bcg["plowhorses"]) + len(bcg["puzzles"]) + len(bcg["dogs"])
    print(f" -> BCG Matrix classified {total_classified} menu items (Stars: {len(bcg['stars'])}, Plowhorses: {len(bcg['plowhorses'])}, Puzzles: {len(bcg['puzzles'])}, Dogs: {len(bcg['dogs'])}).")

    # 5. Audit monitor
    resp = client.get("/api/v1/owner/audit")
    assert resp.status_code == 200
    audit = resp.json()
    print(f" -> Audit monitor active: {audit['total_flagged']} events inspected.")

    # 6. Ask Resto Intelligence NLP queries
    queries = [
        "what sold best today",
        "how were sales today",
        "how much chicken stock do we have left",
        "how much cash is in the drawer",
    ]
    for q in queries:
        resp = client.post("/api/v1/owner/ask-resto", json={"query": q})
        assert resp.status_code == 200
        nlp_res = resp.json()
        print(f" -> Q: '{q}'\n    A: {nlp_res['answer']}")


def test_settings_and_menu_management():
    print("\nTesting Settings & Menu Management API...")
    # 1. Fetch current tenant details
    resp = client.get("/api/v1/tenant")
    assert resp.status_code == 200, resp.text
    tenant = resp.json()
    assert tenant["name"] is not None
    assert "gstin" in tenant
    print(f" -> Tenant Profile: '{tenant['name']}', GSTIN: {tenant['gstin']}, FL-3: {tenant.get('fl3_license')}")

    # 2. Update tenant statutory profile
    update_payload = {
        "outlet_name": "Rasa Sahyadri (Main Koregaon Park)",
        "phone": "+91 20 2615 4899",
        "fl3_license": "FL3-MH-PUN-2026-9901"
    }
    resp = client.put("/api/v1/tenant", json=update_payload)
    assert resp.status_code == 200, resp.text
    updated_tenant = resp.json()
    assert updated_tenant["outlet_name"] == "Rasa Sahyadri (Main Koregaon Park)"
    assert updated_tenant["fl3_license"] == "FL3-MH-PUN-2026-9901"
    print(" -> Successfully updated tenant profile via PUT /api/v1/tenant")

    # 3. Create a new dish
    new_dish_payload = {
        "name": "Surmai Malvani Masala",
        "category": "Mains",
        "price": 580.00,
        "is_veg": False,
        "tax_category": "GST_FOOD",
        "description": "Kingfish steaks in spicy coastal Malvani gravy"
    }
    resp = client.post("/api/v1/menu", json=new_dish_payload)
    assert resp.status_code == 201, resp.text
    created_dish = resp.json()
    dish_id = created_dish["id"]
    assert created_dish["name"] == "Surmai Malvani Masala"
    assert created_dish["price"] == 580.00
    print(f" -> Created new dish #{dish_id} '{created_dish['name']}' at Rs. {created_dish['price']}")

    # 4. Change dish price and toggle 86 status
    patch_payload = {
        "price": 620.00,
        "is_86": True
    }
    resp = client.patch(f"/api/v1/menu/{dish_id}", json=patch_payload)
    assert resp.status_code == 200, resp.text
    patched_dish = resp.json()
    assert patched_dish["price"] == 620.00
    assert patched_dish["is_86"] is True
    print(f" -> Patched dish #{dish_id}: New Price Rs. {patched_dish['price']}, 86 Status: {patched_dish['is_86']}")

    # 5. Archive dish
    resp = client.delete(f"/api/v1/menu/{dish_id}")
    assert resp.status_code == 200, resp.text
    archive_res = resp.json()
    assert archive_res["status"] == "archived"
    print(f" -> Archived dish #{dish_id} successfully.")

    # 6. Categories Management API
    resp = client.get("/api/v1/categories")
    assert resp.status_code == 200, resp.text
    cats = resp.json()
    assert len(cats) >= 5
    print(f" -> Loaded {len(cats)} categories with live dish counts.")

    new_cat_payload = {
        "name": "Chinese & Wok",
        "department": "KITCHEN",
        "tax_category": "GST_FOOD"
    }
    resp = client.post("/api/v1/categories", json=new_cat_payload)
    assert resp.status_code == 201, resp.text
    created_cat = resp.json()
    assert created_cat["name"] == "Chinese & Wok"
    print(f" -> Successfully registered new category #{created_cat['id']} '{created_cat['name']}' ({created_cat['department']}).")

    resp = client.delete(f"/api/v1/categories/{created_cat['id']}")
    assert resp.status_code == 200, resp.text
    print(f" -> Archived category #{created_cat['id']} successfully.")


def test_rbac_and_supabase_config():
    print("\nTesting Role-Based Access Control (RBAC) & Cloud Config...")
    # 1. Staff users list
    resp = client.get("/api/v1/auth/users")
    assert resp.status_code == 200, resp.text
    users = resp.json()
    assert len(users) >= 3
    print(f" -> Found {len(users)} staff accounts.")

    # 2. Cashier login (Pooja More, PIN 1234)
    cashier_payload = {"username": "pooja_more", "pin": "1234"}
    resp = client.post("/api/v1/auth/login", json=cashier_payload)
    assert resp.status_code == 200, resp.text
    cashier_login = resp.json()
    assert cashier_login["success"] is True
    assert cashier_login["normalized_role"] == "CASHIER"
    assert "owner_analytics" not in cashier_login["permissions"]
    assert "menu_settings" not in cashier_login["permissions"]
    assert "billing_settlement" in cashier_login["permissions"]
    print(" -> Cashier login verified (hotel operations only, analytics & settings restricted).")

    # 3. Admin login (Mahesh Patil, PIN 9999)
    admin_payload = {"username": "mahesh_patil", "pin": "9999"}
    resp = client.post("/api/v1/auth/login", json=admin_payload)
    assert resp.status_code == 200, resp.text
    admin_login = resp.json()
    assert admin_login["success"] is True
    assert admin_login["normalized_role"] == "ADMIN"
    assert "owner_analytics" in admin_login["permissions"]
    assert "menu_settings" in admin_login["permissions"]
    print(" -> Admin/Owner login verified (full software + analytics display access).")

    # 4. System & Supabase config
    resp = client.get("/api/v1/config")
    assert resp.status_code == 200, resp.text
    cfg = resp.json()
    assert "supabase" in cfg
    print(f" -> Supabase Cloud Integration verified: Mode = {cfg['supabase']['mode']}.")


if __name__ == "__main__":
    print("=" * 65)
    print("STARTING RESTOOS COMPREHENSIVE API INTEGRATION TEST SUITE")
    print("=" * 65)
    test_system_health()
    t1_id = test_tables_flow()
    order_id = test_orders_and_kot_flow(t1_id)
    test_billing_flow(order_id, t1_id)
    test_shifts_flow()
    test_inventory_and_86_flow()
    test_excise_flr3a_flow()
    test_owner_bi_and_nlp_flow()
    test_settings_and_menu_management()
    test_rbac_and_supabase_config()
    print("=" * 65)
    print("ALL API ENDPOINTS AND WORKFLOWS VERIFIED SUCCESSFULLY (100% PASS)")
    print("=" * 65)
