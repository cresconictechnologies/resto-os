"""
RestoOS Dual-Tax Statutory Billing & Settlement API
Indian Statutory Tax Engine: Part A Food (5% GST: CGST 2.5% + SGST 2.5%) +
Part B Liquor (5% Maharashtra VAT) + Round-off = Grand Total.
Includes atomic tenant-scoped invoice sequences per Indian Financial Year,
unified frontend cart settlement, Recipe BOM inventory deduction, and 24V Cash Drawer Kick.
"""

from datetime import datetime, timezone
import math
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, Header, status
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from ..database import get_db
from ..models import (
    Order,
    OrderItem,
    DiningTable,
    Bill,
    Tenant,
    CashShift,
    AuditLog,
    InvoiceCounter,
    RecipeBOM,
    RawMaterial,
    MenuItem,
)
from ..schemas import (
    BillCalculationResponse,
    BillSettleRequest,
    BillSettleResponse,
    BillResponse,
)
from ..escpos_utils import (
    generate_tax_invoice_80mm,
    DRAWER_KICK_HEX,
)
from ..auth_guard import verify_token, TokenPayload

router = APIRouter(prefix="/billing", tags=["Dual-Tax Billing & Settlement"])


def _compute_order_taxes(order: Order) -> Dict[str, Any]:
    """
    Computes statutory Indian dual-tax breakdown:
    Part A: Food Subtotal, CGST @ 2.5%, SGST @ 2.5%
    Part B: Liquor Subtotal, MVAT @ 5.0%
    Combined: Subtotal, Total Tax, Round-off, Grand Total
    """
    food_subtotal = 0.0
    liquor_subtotal = 0.0
    food_items = []
    liquor_items = []

    for item in order.items:
        if item.status == "VOIDED":
            continue
        line_total = round(item.quantity * item.unit_price, 2)
        tax_cat = item.menu_item.tax_category if item.menu_item else "GST_FOOD"

        item_dict = {
            "id": item.id,
            "item_name": item.item_name,
            "quantity": item.quantity,
            "unit_price": item.unit_price,
            "line_total": line_total,
            "tax_category": tax_cat,
        }

        if tax_cat == "VAT_ALCOHOL":
            liquor_subtotal += line_total
            liquor_items.append(item_dict)
        else:
            food_subtotal += line_total
            food_items.append(item_dict)

    food_subtotal = round(food_subtotal, 2)
    liquor_subtotal = round(liquor_subtotal, 2)

    # Food Tax: 5% total (2.5% CGST + 2.5% SGST)
    food_cgst = round(food_subtotal * 0.025, 2)
    food_sgst = round(food_subtotal * 0.025, 2)
    food_tax_total = round(food_cgst + food_sgst, 2)

    # Liquor Tax: 5% Maharashtra State Excise VAT
    liquor_vat = round(liquor_subtotal * 0.05, 2)
    liquor_tax_total = liquor_vat

    subtotal_combined = round(food_subtotal + liquor_subtotal, 2)
    total_tax = round(food_tax_total + liquor_tax_total, 2)
    raw_grand_total = subtotal_combined + total_tax

    # Indian Currency Rule: Round off to nearest whole rupee
    grand_total = round(raw_grand_total)
    round_off = round(grand_total - raw_grand_total, 2)

    return {
        "food_subtotal": food_subtotal,
        "food_cgst": food_cgst,
        "food_sgst": food_sgst,
        "food_tax_total": food_tax_total,
        "liquor_subtotal": liquor_subtotal,
        "liquor_vat": liquor_vat,
        "liquor_tax_total": liquor_tax_total,
        "subtotal_combined": subtotal_combined,
        "total_tax": total_tax,
        "round_off": round_off,
        "grand_total": float(grand_total),
        "food_items": food_items,
        "liquor_items": liquor_items,
    }


def _get_next_invoice_number(db: Session, tenant_id: int, now: datetime) -> str:
    """
    Computes tenant-scoped, gap-free sequential invoice numbers per Indian Financial Year (Apr 1 - Mar 31).
    Uses row-level locking on InvoiceCounter to prevent race conditions and full table scans.
    """
    year = now.year
    if now.month >= 4:
        fin_year = f"{year}-{str(year + 1)[-2:]}"
    else:
        fin_year = f"{year - 1}-{str(year)[-2:]}"

    counter = db.scalar(
        select(InvoiceCounter)
        .where(InvoiceCounter.tenant_id == tenant_id, InvoiceCounter.fin_year == fin_year)
        .with_for_update()
    )
    if not counter:
        counter = InvoiceCounter(tenant_id=tenant_id, fin_year=fin_year, last_number=1)
        db.add(counter)
        db.flush()
        seq = 1
    else:
        counter.last_number += 1
        seq = counter.last_number
        db.flush()

    return f"INV-{fin_year}-{seq:04d}"


@router.get("/calculate/{order_id}", response_model=BillCalculationResponse)
def calculate_bill(
    order_id: int,
    db: Session = Depends(get_db),
    auth: TokenPayload = Depends(verify_token),
):
    """
    Preview live statutory tax breakdown for an order before settling:
    - CGST 2.5% + SGST 2.5% on Food
    - MVAT 5% on Alcohol
    - Round-off and Grand Total
    """
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")

    if not order.items:
        raise HTTPException(status_code=400, detail="Cannot calculate bill for an empty order.")

    calc = _compute_order_taxes(order)
    all_breakdown = calc["food_items"] + calc["liquor_items"]

    return BillCalculationResponse(
        order_id=order.id,
        food_subtotal=calc["food_subtotal"],
        food_cgst=calc["food_cgst"],
        food_sgst=calc["food_sgst"],
        food_tax_total=calc["food_tax_total"],
        liquor_subtotal=calc["liquor_subtotal"],
        liquor_vat=calc["liquor_vat"],
        liquor_tax_total=calc["liquor_tax_total"],
        subtotal_combined=calc["subtotal_combined"],
        total_tax=calc["total_tax"],
        round_off=calc["round_off"],
        grand_total=calc["grand_total"],
        items_breakdown=all_breakdown,
    )


@router.post("/settle", response_model=BillSettleResponse)
def settle_bill(
    payload: BillSettleRequest,
    idempotency_key: Optional[str] = Header(None),
    db: Session = Depends(get_db),
    auth: TokenPayload = Depends(verify_token),
):
    """
    Finalize bill payment (CASH, UPI, CARD, KHATA):
    1. Supports existing order_id OR unified full-cart payload from frontend POS.
    2. Enforces idempotency to eliminate double-billing bugs.
    3. Issues gap-free sequential invoice number per tenant and Indian FY.
    4. Automatically deducts raw ingredients via Recipe BOM.
    5. Accrues cash sales into active CashShift with row-level locking.
    6. Returns 80mm ESC/POS Statutory Tax Invoice text and 24V Drawer kick hex.
    """
    now = datetime.now(timezone.utc)
    order: Optional[Order] = None

    # Case A: Frontend passed cart items directly (Unified Settlement)
    if not payload.order_id and payload.items:
        table = None
        if payload.table_id:
            table = db.get(DiningTable, payload.table_id)
        elif payload.table_code:
            table = db.scalar(select(DiningTable).where(DiningTable.code == payload.table_code.strip()))

        tenant_id = table.tenant_id if table else (auth.tenant_id or 1)

        # Check if table already has an active pending order
        if table:
            order = db.scalar(
                select(Order)
                .where(Order.table_id == table.id, Order.status.in_(["PENDING", "IN_PROGRESS", "ACTIVE"]))
                .with_for_update()
            )

        if not order:
            order = Order(
                tenant_id=tenant_id,
                table_id=table.id if table else None,
                order_type="DINE_IN" if table else "TAKEAWAY",
                status="PENDING",
                created_at=now,
                updated_at=now,
            )
            db.add(order)
            db.flush()

        # Populate order items from cart
        for item_data in payload.items:
            menu_item = db.get(MenuItem, item_data.item_id)
            item_name = menu_item.name if menu_item else (item_data.name or f"Dish #{item_data.item_id}")
            unit_price = item_data.unit_price if item_data.unit_price > 0 else (menu_item.price if menu_item else 100.0)

            oi = OrderItem(
                order_id=order.id,
                menu_item_id=item_data.item_id,
                item_name=item_name,
                quantity=int(item_data.quantity),
                unit_price=unit_price,
                status="SERVED",
                prep_note=item_data.notes or "",
                created_at=now,
            )
            db.add(oi)

        db.flush()
        db.refresh(order)

    # Case B: Existing Order ID provided
    elif payload.order_id:
        order = db.scalar(
            select(Order).where(Order.id == payload.order_id).with_for_update()
        )
        if not order:
            raise HTTPException(status_code=404, detail="Order not found.")

        # Idempotency check: if order is already settled, return existing bill without re-billing
        if order.status == "COMPLETED":
            existing_bill = db.scalar(select(Bill).where(Bill.order_id == order.id))
            if existing_bill:
                bill_resp = BillResponse(
                    id=existing_bill.id,
                    tenant_id=existing_bill.tenant_id,
                    order_id=existing_bill.order_id,
                    invoice_number=existing_bill.invoice_number,
                    food_subtotal=existing_bill.food_subtotal,
                    food_cgst=existing_bill.food_cgst,
                    food_sgst=existing_bill.food_sgst,
                    food_tax_total=round(existing_bill.food_cgst + existing_bill.food_sgst, 2),
                    liquor_subtotal=existing_bill.liquor_subtotal,
                    liquor_vat=existing_bill.liquor_vat,
                    round_off=existing_bill.round_off,
                    grand_total=existing_bill.grand_total,
                    payment_mode=existing_bill.payment_mode,
                    payment_status=existing_bill.payment_status,
                    created_at=existing_bill.created_at,
                )
                return BillSettleResponse(
                    bill=bill_resp,
                    drawer_kick_command_hex=None,
                    tax_invoice_80mm_text=f"*** REPRINT ***\nINVOICE: {existing_bill.invoice_number}\nGRAND TOTAL: Rs. {existing_bill.grand_total:.2f}",
                    table_status_now="OPEN",
                    message="Order already settled. Returning idempotent bill record.",
                )
            raise HTTPException(status_code=409, detail="Order is already completed and closed.")

    if not order or not order.items:
        raise HTTPException(status_code=400, detail="Cannot settle an empty order.")

    tenant = db.get(Tenant, order.tenant_id)
    tenant_info = tenant.to_dict() if tenant else {
        "outlet_name": "RASA SAHYADRI",
        "name": "Sahyadri Heritage Foods LLP",
        "address": "Koregaon Park, Pune - 411001",
        "gstin": "27AAKFR4621M1Z5",
        "fssai": "11523034000412",
        "fl3_license": "FL3-PUN-KP-0412",
        "vatin": "27912345678V",
        "phone": "020-26123456",
    }

    calc = _compute_order_taxes(order)

    # Generate tenant-scoped gap-free sequence (Indian Financial Year)
    invoice_number = _get_next_invoice_number(db, order.tenant_id, now)

    # Insert Bill (order_id is strictly unique)
    bill = Bill(
        tenant_id=order.tenant_id,
        order_id=order.id,
        invoice_number=invoice_number,
        food_subtotal=calc["food_subtotal"],
        food_cgst=calc["food_cgst"],
        food_sgst=calc["food_sgst"],
        liquor_subtotal=calc["liquor_subtotal"],
        liquor_vat=calc["liquor_vat"],
        round_off=calc["round_off"],
        grand_total=calc["grand_total"],
        payment_mode=payload.payment_mode.upper(),
        payment_status="PAID",
        created_at=now,
    )
    db.add(bill)
    db.flush()

    # Deduct raw ingredients via Recipe BOM for live AvT tracking
    try:
        for oi in order.items:
            if oi.status == "VOIDED" or not oi.menu_item_id:
                continue
            boms = db.scalars(
                select(RecipeBOM).where(RecipeBOM.menu_item_id == oi.menu_item_id)
            ).all()
            for bom in boms:
                raw_mat = db.get(RawMaterial, bom.raw_material_id)
                if raw_mat:
                    deduct = bom.quantity_required * oi.quantity
                    raw_mat.current_kitchen_stock = max(0.0, round(raw_mat.current_kitchen_stock - deduct, 3))
    except Exception as e:
        print(f"[RestoOS] BOM stock deduction notice: {e}")

    # Hardware Cash Drawer Kick Pulse & CashShift accrual
    drawer_kick_hex = None
    is_cash = payload.payment_mode.upper() == "CASH"

    if is_cash:
        drawer_kick_hex = DRAWER_KICK_HEX

        # Log microswitch / drawer kick audit event
        audit = AuditLog(
            tenant_id=order.tenant_id,
            staff_name=payload.staff_name or auth.display_name,
            action_type="DRAWER_KICK_BILL",
            details_json=f'{{"invoice_number": "{invoice_number}", "grand_total": {calc["grand_total"]}, "mode": "CASH"}}',
            timestamp=now,
        )
        db.add(audit)

        # Accrue to active cashier shift with row-level lock
        active_shift = db.scalar(
            select(CashShift)
            .where(CashShift.is_closed == False)
            .with_for_update()
            .order_by(CashShift.id.desc())
            .limit(1)
        )
        if active_shift:
            active_shift.cash_sales = round(active_shift.cash_sales + calc["grand_total"], 2)

    # Close order and reset table
    order.status = "COMPLETED"
    order.updated_at = now

    table_code = "COUNTER"
    guest_count = 1
    if order.table:
        table_code = order.table.code
        guest_count = order.table.guest_count
        order.table.status = "OPEN"
        order.table.seated_at = None
        order.table.guest_count = 0

    db.commit()
    db.refresh(bill)

    # Generate ESC/POS 80mm Statutory Tax Receipt
    receipt_text = generate_tax_invoice_80mm(
        tenant_info=tenant_info,
        invoice_number=invoice_number,
        table_code=table_code,
        guest_count=guest_count,
        order_type=order.order_type,
        food_items=calc["food_items"],
        liquor_items=calc["liquor_items"],
        food_subtotal=calc["food_subtotal"],
        food_cgst=calc["food_cgst"],
        food_sgst=calc["food_sgst"],
        liquor_subtotal=calc["liquor_subtotal"],
        liquor_vat=calc["liquor_vat"],
        round_off=calc["round_off"],
        grand_total=calc["grand_total"],
        payment_mode=bill.payment_mode,
        cashier_name=payload.staff_name or auth.display_name,
        timestamp=now,
    )

    bill_resp = BillResponse(
        id=bill.id,
        tenant_id=bill.tenant_id,
        order_id=bill.order_id,
        invoice_number=bill.invoice_number,
        food_subtotal=bill.food_subtotal,
        food_cgst=bill.food_cgst,
        food_sgst=bill.food_sgst,
        food_tax_total=round(bill.food_cgst + bill.food_sgst, 2),
        liquor_subtotal=bill.liquor_subtotal,
        liquor_vat=bill.liquor_vat,
        round_off=bill.round_off,
        grand_total=bill.grand_total,
        payment_mode=bill.payment_mode,
        payment_status=bill.payment_status,
        created_at=bill.created_at,
    )

    return BillSettleResponse(
        bill=bill_resp,
        drawer_kick_command_hex=drawer_kick_hex,
        tax_invoice_80mm_text=receipt_text,
        table_status_now="OPEN",
        message=f"Bill settled via {payload.payment_mode}. Invoice {invoice_number} generated.",
    )


@router.get("/invoice/{bill_id}")
def get_bill_invoice(
    bill_id: int,
    db: Session = Depends(get_db),
    auth: TokenPayload = Depends(verify_token),
):
    """Retrieves 80mm ESC/POS tax invoice for reprint."""
    bill = db.get(Bill, bill_id)
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found.")

    tenant = db.get(Tenant, bill.tenant_id)
    tenant_info = tenant.to_dict() if tenant else {}
    order = bill.order
    calc = _compute_order_taxes(order) if order else {}

    receipt_text = generate_tax_invoice_80mm(
        tenant_info=tenant_info,
        invoice_number=bill.invoice_number,
        table_code=order.table.code if (order and order.table) else "COUNTER",
        guest_count=order.table.guest_count if (order and order.table) else 1,
        order_type=order.order_type if order else "DINE_IN",
        food_items=calc.get("food_items", []),
        liquor_items=calc.get("liquor_items", []),
        food_subtotal=bill.food_subtotal,
        food_cgst=bill.food_cgst,
        food_sgst=bill.food_sgst,
        liquor_subtotal=bill.liquor_subtotal,
        liquor_vat=bill.liquor_vat,
        round_off=bill.round_off,
        grand_total=bill.grand_total,
        payment_mode=bill.payment_mode,
        cashier_name="Cashier 1",
        timestamp=bill.created_at or datetime.now(timezone.utc),
    )

    return {
        "bill": bill.to_dict(),
        "tax_invoice_80mm_text": receipt_text,
    }
