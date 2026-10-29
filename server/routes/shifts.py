"""
RestoOS Cash Drawer Shift Management & Z-Report API
Manages opening float, cash sales tracking, petty cash paid-in / paid-out,
manager safe drops, and blind-close Z-Report variance calculation.
"""

from datetime import datetime, timezone
import json
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from ..database import get_db
from ..models import CashShift, Bill, User, AuditLog
from ..schemas import (
    ShiftOpenRequest,
    PettyCashRequest,
    SafeDropRequest,
    ShiftCloseRequest,
    CashShiftResponse,
    ZReportResponse,
)
from ..escpos_utils import generate_z_report_80mm

router = APIRouter(prefix="/shifts", tags=["Cash Drawer Shifts & Z-Report"])


def _calculate_expected_cash(shift: CashShift) -> float:
    """Computes expected physical cash inside the register drawer."""
    return round(
        shift.opening_float + shift.cash_sales + shift.paid_in - shift.paid_out - shift.safe_drops,
        2,
    )


@router.get("/current", response_model=Optional[CashShiftResponse])
def get_current_shift(db: Session = Depends(get_db)):
    """Retrieve active open cash shift session."""
    shift = db.scalar(
        select(CashShift).where(CashShift.is_closed == False).order_by(CashShift.id.desc()).limit(1)
    )
    if not shift:
        return None

    return CashShiftResponse(
        id=shift.id,
        tenant_id=shift.tenant_id,
        cashier_name=shift.cashier_name,
        opened_at=shift.opened_at,
        opening_float=shift.opening_float,
        cash_sales=shift.cash_sales,
        paid_in=shift.paid_in,
        paid_out=shift.paid_out,
        safe_drops=shift.safe_drops,
        expected_cash=_calculate_expected_cash(shift),
        counted_cash=shift.counted_cash,
        variance=shift.variance,
        closed_at=shift.closed_at,
        is_closed=shift.is_closed,
    )


@router.post("/open", response_model=CashShiftResponse)
def open_shift(payload: ShiftOpenRequest, db: Session = Depends(get_db)):
    """
    Open a new cashier shift session with initial starting cash float.
    Fails if a shift is already open.
    """
    active = db.scalar(
        select(CashShift).where(CashShift.is_closed == False).limit(1)
    )
    if active:
        raise HTTPException(
            status_code=400,
            detail=f"Shift #{active.id} is already open under {active.cashier_name}. Close it first.",
        )

    now = datetime.now(timezone.utc)
    new_shift = CashShift(
        tenant_id=1,
        cashier_name=payload.cashier_name,
        opened_at=now,
        opening_float=payload.opening_float,
        cash_sales=0.0,
        paid_in=0.0,
        paid_out=0.0,
        safe_drops=0.0,
        is_closed=False,
    )
    db.add(new_shift)

    # Audit log
    audit = AuditLog(
        tenant_id=1,
        staff_name=payload.cashier_name,
        action_type="SHIFT_OPEN",
        details_json=json.dumps({"opening_float": payload.opening_float}),
        timestamp=now,
    )
    db.add(audit)

    db.commit()
    db.refresh(new_shift)

    return CashShiftResponse(
        id=new_shift.id,
        tenant_id=new_shift.tenant_id,
        cashier_name=new_shift.cashier_name,
        opened_at=new_shift.opened_at,
        opening_float=new_shift.opening_float,
        cash_sales=new_shift.cash_sales,
        paid_in=new_shift.paid_in,
        paid_out=new_shift.paid_out,
        safe_drops=new_shift.safe_drops,
        expected_cash=new_shift.opening_float,
        counted_cash=None,
        variance=None,
        closed_at=None,
        is_closed=False,
    )


@router.post("/petty-cash", response_model=CashShiftResponse)
def record_petty_cash_voucher(payload: PettyCashRequest, db: Session = Depends(get_db)):
    """
    Record petty cash Paid-In or Paid-Out (e.g. ice delivery, milk, local courier).
    """
    shift = db.scalar(
        select(CashShift).where(CashShift.is_closed == False).order_by(CashShift.id.desc()).limit(1)
    )
    if not shift:
        raise HTTPException(status_code=400, detail="No active shift open. Please open a shift first.")

    now = datetime.now(timezone.utc)
    v_type = payload.voucher_type.upper()

    if v_type == "PAID_IN":
        shift.paid_in = round(shift.paid_in + payload.amount, 2)
    elif v_type == "PAID_OUT":
        shift.paid_out = round(shift.paid_out + payload.amount, 2)
    else:
        raise HTTPException(status_code=400, detail="voucher_type must be PAID_IN or PAID_OUT.")

    audit = AuditLog(
        tenant_id=shift.tenant_id,
        staff_name=payload.staff_name,
        action_type=f"PETTY_CASH_{v_type}",
        details_json=json.dumps({"amount": payload.amount, "reason": payload.reason}),
        timestamp=now,
    )
    db.add(audit)

    db.commit()
    db.refresh(shift)

    return CashShiftResponse(
        id=shift.id,
        tenant_id=shift.tenant_id,
        cashier_name=shift.cashier_name,
        opened_at=shift.opened_at,
        opening_float=shift.opening_float,
        cash_sales=shift.cash_sales,
        paid_in=shift.paid_in,
        paid_out=shift.paid_out,
        safe_drops=shift.safe_drops,
        expected_cash=_calculate_expected_cash(shift),
        counted_cash=shift.counted_cash,
        variance=shift.variance,
        closed_at=shift.closed_at,
        is_closed=shift.is_closed,
    )


@router.post("/safe-drop", response_model=CashShiftResponse)
def record_safe_drop(payload: SafeDropRequest, db: Session = Depends(get_db)):
    """
    Transfer excess accumulated cash from counter drawer to the back-office drop safe.
    Validates supervisor/manager PIN.
    """
    shift = db.scalar(
        select(CashShift).where(CashShift.is_closed == False).order_by(CashShift.id.desc()).limit(1)
    )
    if not shift:
        raise HTTPException(status_code=400, detail="No active shift open.")

    # Validate supervisor PIN
    manager = db.scalar(
        select(User).where(User.role.in_(["OWNER", "MANAGER"]), User.is_active == True)
    )
    # Default demo manager PIN check
    if payload.manager_pin not in ("1234", "9999", "5555"):
        raise HTTPException(status_code=401, detail="Invalid Manager Authorization PIN.")

    now = datetime.now(timezone.utc)
    shift.safe_drops = round(shift.safe_drops + payload.amount, 2)

    audit = AuditLog(
        tenant_id=shift.tenant_id,
        staff_name=f"Manager (PIN Auth)",
        action_type="SAFE_DROP",
        details_json=json.dumps({"amount": payload.amount, "notes": payload.notes}),
        timestamp=now,
    )
    db.add(audit)

    db.commit()
    db.refresh(shift)

    return CashShiftResponse(
        id=shift.id,
        tenant_id=shift.tenant_id,
        cashier_name=shift.cashier_name,
        opened_at=shift.opened_at,
        opening_float=shift.opening_float,
        cash_sales=shift.cash_sales,
        paid_in=shift.paid_in,
        paid_out=shift.paid_out,
        safe_drops=shift.safe_drops,
        expected_cash=_calculate_expected_cash(shift),
        counted_cash=shift.counted_cash,
        variance=shift.variance,
        closed_at=shift.closed_at,
        is_closed=shift.is_closed,
    )


@router.post("/close", response_model=ZReportResponse)
def close_shift_and_z_report(payload: ShiftCloseRequest, db: Session = Depends(get_db)):
    """
    Perform blind close of active shift:
    1. Cashier inputs physical cash count without seeing system expected total beforehand.
    2. System calculates expected cash and over/short variance.
    3. Aggregates all sales by tender (Cash, UPI, Card, Khata) during the shift window.
    4. Generates formatted 80mm Z-Report receipt.
    5. Marks shift closed.
    """
    shift = db.scalar(
        select(CashShift).where(CashShift.is_closed == False).order_by(CashShift.id.desc()).limit(1)
    )
    if not shift:
        raise HTTPException(status_code=400, detail="No active shift open to close.")

    now = datetime.now(timezone.utc)
    expected_cash = _calculate_expected_cash(shift)
    counted = round(payload.counted_cash, 2)
    variance = round(counted - expected_cash, 2)

    shift.counted_cash = counted
    shift.variance = variance
    shift.closed_at = now
    shift.is_closed = True

    # Aggregate sales by payment tender during this shift
    bills = db.scalars(
        select(Bill).where(Bill.created_at >= shift.opened_at, Bill.payment_status == "PAID")
    ).all()

    cash_sales = 0.0
    upi_sales = 0.0
    card_sales = 0.0
    khata_sales = 0.0
    gross_sales = 0.0
    total_tax = 0.0

    for b in bills:
        gross_sales += b.grand_total
        total_tax += (b.food_cgst + b.food_sgst + b.liquor_vat)
        mode = b.payment_mode.upper()
        if mode == "CASH":
            cash_sales += b.grand_total
        elif mode == "UPI":
            upi_sales += b.grand_total
        elif mode == "CARD":
            card_sales += b.grand_total
        elif mode == "KHATA":
            khata_sales += b.grand_total

    # Audit log
    audit = AuditLog(
        tenant_id=shift.tenant_id,
        staff_name=shift.cashier_name,
        action_type="SHIFT_BLIND_CLOSE",
        details_json=json.dumps({
            "expected_cash": expected_cash,
            "counted_cash": counted,
            "variance": variance,
        }),
        timestamp=now,
    )
    db.add(audit)
    db.commit()

    z_data = {
        "shift_id": shift.id,
        "cashier_name": shift.cashier_name,
        "opened_at": shift.opened_at,
        "closed_at": shift.closed_at,
        "opening_float": shift.opening_float,
        "cash_sales": round(cash_sales, 2),
        "upi_sales": round(upi_sales, 2),
        "card_sales": round(card_sales, 2),
        "khata_sales": round(khata_sales, 2),
        "gross_sales": round(gross_sales, 2),
        "net_sales": round(gross_sales - total_tax, 2),
        "total_tax_collected": round(total_tax, 2),
        "paid_in": shift.paid_in,
        "paid_out": shift.paid_out,
        "safe_drops": shift.safe_drops,
        "expected_in_drawer": expected_cash,
        "counted_cash": counted,
        "variance": variance,
    }

    z_report_text = generate_z_report_80mm(z_data)

    return ZReportResponse(
        shift_id=shift.id,
        cashier_name=shift.cashier_name,
        opened_at=shift.opened_at,
        closed_at=shift.closed_at,
        opening_float=shift.opening_float,
        cash_sales=round(cash_sales, 2),
        card_sales=round(card_sales, 2),
        upi_sales=round(upi_sales, 2),
        khata_sales=round(khata_sales, 2),
        gross_sales=round(gross_sales, 2),
        net_sales=round(gross_sales - total_tax, 2),
        total_tax_collected=round(total_tax, 2),
        paid_in=shift.paid_in,
        paid_out=shift.paid_out,
        safe_drops=shift.safe_drops,
        expected_in_drawer=expected_cash,
        counted_cash=counted,
        variance=variance,
        status="CLOSED",
        z_report_80mm_text=z_report_text,
    )
