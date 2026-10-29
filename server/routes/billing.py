"""
RestoOS Dual-Tax Statutory Billing & Settlement API
Indian Statutory Tax Engine: Part A Food (5% GST: CGST 2.5% + SGST 2.5%) +
Part B Liquor (5% Maharashtra VAT) + Round-off = Grand Total.
Includes 24V Solenoid Cash Drawer Kick Hardware Interfacing and 80mm ESC/POS Invoice.
"""

from datetime import datetime, timezone
import math
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from ..database import get_db
from ..models import Order, OrderItem, DiningTable, Bill, Tenant, CashShift, AuditLog
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

    # Liquor Tax: 5% MVAT
    liquor_vat = round(liquor_subtotal * 0.05, 2)

    subtotal_combined = round(food_subtotal + liquor_subtotal, 2)
    total_tax = round(food_tax_total + liquor_vat, 2)
    raw_grand_total = subtotal_combined + total_tax

    # Indian Currency Rule: Round off to nearest rupee
    grand_total = round(raw_grand_total)
    round_off = round(grand_total - raw_grand_total, 2)

    return {
        "food_subtotal": food_subtotal,
        "food_cgst": food_cgst,
        "food_sgst": food_sgst,
        "food_tax_total": food_tax_total,
        "liquor_subtotal": liquor_subtotal,
        "liquor_vat": liquor_vat,
        "liquor_tax_total": liquor_vat,
        "subtotal_combined": subtotal_combined,
        "total_tax": total_tax,
        "round_off": round_off,
        "grand_total": float(grand_total),
        "food_items": food_items,
        "liquor_items": liquor_items,
    }


@router.get("/calculate/{order_id}", response_model=BillCalculationResponse)
def calculate_bill(order_id: int, db: Session = Depends(get_db)):
    """
    Preview live bill calculation with statutory Part A (Food 5% GST) and Part B (Spirits 5% MVAT).
    """
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")

    calc = _compute_order_taxes(order)
    all_breakdown = calc["food_items"] + calc["liquor_items"]

    return BillCalculationResponse(
        order_id=order.id,
        table_code=order.table.code if order.table else "COUNTER",
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
def settle_bill(payload: BillSettleRequest, db: Session = Depends(get_db)):
    """
    Finalize bill payment (CASH, UPI, CARD, KHATA):
    1. Validates order totals with statutory GST + VAT taxes.
    2. Generates sequential invoice number (e.g. INV-2026-0002).
    3. If CASH:
       - Generates 24V Solenoid Drawer Kick hex ('1b700019fa').
       - Logs audit event for cash drawer opening.
       - Accrues cash sales into active CashShift.
    4. Marks order COMPLETED and clears dining table to OPEN.
    5. Returns 80mm ESC/POS Statutory Tax Invoice text.
    """
    order = db.get(Order, payload.order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")

    if not order.items:
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
    now = datetime.now(timezone.utc)

    # Generate sequential Tax Invoice Number
    year = now.year
    bill_count = db.scalar(select(func.count(Bill.id))) or 0
    invoice_number = f"INV-{year}-{(bill_count + 1):04d}"

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

    # Hardware Cash Drawer Kick Pulse
    drawer_kick_hex = None
    is_cash = payload.payment_mode.upper() == "CASH"

    if is_cash:
        drawer_kick_hex = DRAWER_KICK_HEX

        # Log microswitch / drawer kick audit event
        audit = AuditLog(
            tenant_id=order.tenant_id,
            staff_name=payload.staff_name,
            action_type="DRAWER_KICK_BILL",
            details_json=f'{{"invoice_number": "{invoice_number}", "grand_total": {calc["grand_total"]}, "mode": "CASH"}}',
            timestamp=now,
        )
        db.add(audit)

        # Accrue to active cashier shift if open
        active_shift = db.scalar(
            select(CashShift).where(CashShift.is_closed == False).order_by(CashShift.id.desc()).limit(1)
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
        cashier_name=payload.staff_name,
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


@router.get("/invoices/{bill_id}", response_model=BillResponse)
def get_bill_invoice(bill_id: int, db: Session = Depends(get_db)):
    """Retrieve settled invoice details."""
    bill = db.get(Bill, bill_id)
    if not bill:
        raise HTTPException(status_code=404, detail="Invoice not found.")

    return BillResponse(
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
