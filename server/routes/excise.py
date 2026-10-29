"""
RestoOS Maharashtra State Excise FL-3 & Form F.L.R.-3A Compliance API
Statutory register generation enforcing the balance equation:
Opening Stock + Inward Transport Permit (TP) - Sales (ml) - Breakage (ml) == Closing Stock.
Includes Dry Day status check, Inward TP processing, and Form FLR-4 Monthly Abstract.
"""

from datetime import datetime, timezone, date, timedelta
import calendar
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from ..database import get_db
from ..models import (
    LiquorBrand,
    LiquorTransportPermit,
    DailyExciseFLR3A,
    AuditLog,
)
from ..schemas import (
    LiquorBrandResponse,
    LiquorTPCreate,
    LiquorTPResponse,
    DailyFLR3ARegisterResponse,
    DailyFLR3AEntry,
    FLR4MonthlyAbstractResponse,
    FLR4CategorySummary,
    DryDayStatusResponse,
)

router = APIRouter(prefix="/excise", tags=["Liquor Bar & Maharashtra State Excise FLR-3A"])

# Official Maharashtra State Excise Statutory Dry Days Calendar (Fixed recurring dates)
MAHARASHTRA_DRY_DAYS = {
    (1, 26): "Republic Day (National Holiday)",
    (1, 30): "Mahatma Gandhi Punyatithi (Martyrs' Day)",
    (5, 1): "Maharashtra Day & International Labour Day",
    (8, 15): "Independence Day (National Holiday)",
    (10, 2): "Mahatma Gandhi Jayanti (National Holiday)",
}


@router.get("/dry-day", response_model=DryDayStatusResponse)
def check_dry_day_status(
    check_date: Optional[date] = Query(None, description="Date to check (default today)"),
):
    """
    Check if the specified date is a statutory Maharashtra State Excise Dry Day.
    Alcohol service is legally prohibited during Dry Days under FL-3 license conditions.
    """
    target = check_date or date.today()
    month_day = (target.month, target.day)

    is_dry = month_day in MAHARASHTRA_DRY_DAYS
    reason = MAHARASHTRA_DRY_DAYS.get(month_day)

    return DryDayStatusResponse(
        is_dry_day=is_dry,
        date=target,
        reason=reason,
        liquor_sale_permitted=not is_dry,
    )


@router.get("/brands", response_model=List[LiquorBrandResponse])
def get_liquor_brands(db: Session = Depends(get_db)):
    """Retrieve all bar brands tracked under State Excise FL-3 register."""
    brands = db.scalars(select(LiquorBrand).order_by(LiquorBrand.category, LiquorBrand.brand_name)).all()
    return [
        LiquorBrandResponse(
            id=b.id,
            tenant_id=b.tenant_id,
            brand_name=b.brand_name,
            category=b.category,
            bottle_size_ml=b.bottle_size_ml,
            state_excise_code=b.state_excise_code,
            mrp=b.mrp,
            vat_percent=b.vat_percent,
            sealed_bottles=b.sealed_bottles,
            open_bottle_ml=b.open_bottle_ml,
            total_ml=(b.sealed_bottles * b.bottle_size_ml) + b.open_bottle_ml,
        )
        for b in brands
    ]


@router.get("/flr3a", response_model=DailyFLR3ARegisterResponse)
def get_daily_flr3a_register(
    register_date: Optional[date] = Query(None, description="Date for FLR-3A register (default today)"),
    db: Session = Depends(get_db),
):
    """
    Generate or retrieve official Form F.L.R.-3A Daily Register for all brands.
    Verifies statutory balance equation:
    Opening + Inward Receipts - Sales(ml) - Breakage(ml) == Closing Stock
    """
    target_date = register_date or date.today()
    brands = db.scalars(select(LiquorBrand).order_by(LiquorBrand.id)).all()

    existing_rows = db.scalars(
        select(DailyExciseFLR3A).where(DailyExciseFLR3A.register_date == target_date)
    ).all()
    row_map = {r.brand_id: r for r in existing_rows}

    results = []

    for brand in brands:
        if brand.id in row_map:
            r = row_map[brand.id]
            # Verify conservation equation
            total_in = (r.opening_sealed * brand.bottle_size_ml) + r.opening_open_ml + (r.tp_received_bottles * brand.bottle_size_ml)
            total_out = r.sales_ml + r.breakage_ml
            expected_closing_ml = total_in - total_out
            actual_closing_ml = (r.closing_sealed * brand.bottle_size_ml) + r.closing_open_ml
            verified = (expected_closing_ml == actual_closing_ml)

            results.append(
                DailyFLR3AEntry(
                    id=r.id,
                    brand_id=brand.id,
                    brand_name=brand.brand_name,
                    category=brand.category,
                    bottle_size_ml=brand.bottle_size_ml,
                    state_excise_code=brand.state_excise_code,
                    opening_sealed=r.opening_sealed,
                    opening_open_ml=r.opening_open_ml,
                    tp_received_bottles=r.tp_received_bottles,
                    sales_ml=r.sales_ml,
                    breakage_ml=r.breakage_ml,
                    closing_sealed=r.closing_sealed,
                    closing_open_ml=r.closing_open_ml,
                    balance_verified=verified,
                )
            )
        else:
            # Generate dynamically from current brand stock
            opening_sealed = brand.sealed_bottles
            opening_open_ml = brand.open_bottle_ml
            tp_received = 0
            sales_ml = 0
            breakage_ml = 0
            closing_sealed = opening_sealed
            closing_open_ml = opening_open_ml

            entry = DailyExciseFLR3A(
                tenant_id=brand.tenant_id,
                register_date=target_date,
                brand_id=brand.id,
                opening_sealed=opening_sealed,
                opening_open_ml=opening_open_ml,
                tp_received_bottles=tp_received,
                sales_ml=sales_ml,
                breakage_ml=breakage_ml,
                closing_sealed=closing_sealed,
                closing_open_ml=closing_open_ml,
            )
            db.add(entry)
            results.append(
                DailyFLR3AEntry(
                    id=None,
                    brand_id=brand.id,
                    brand_name=brand.brand_name,
                    category=brand.category,
                    bottle_size_ml=brand.bottle_size_ml,
                    state_excise_code=brand.state_excise_code,
                    opening_sealed=opening_sealed,
                    opening_open_ml=opening_open_ml,
                    tp_received_bottles=tp_received,
                    sales_ml=sales_ml,
                    breakage_ml=breakage_ml,
                    closing_sealed=closing_sealed,
                    closing_open_ml=closing_open_ml,
                    balance_verified=True,
                )
            )

    db.commit()

    return DailyFLR3ARegisterResponse(
        register_date=target_date,
        total_brands=len(results),
        rows=results,
    )


@router.post("/tp", response_model=LiquorTPResponse)
def create_transport_permit_inward(payload: LiquorTPCreate, db: Session = Depends(get_db)):
    """
    Process Inward Liquor Transport Permit (TP).
    Updates legal consignment record, increments sealed bottles on liquor brands,
    and updates today's FLR-3A register tp_received_bottles.
    """
    now = datetime.now(timezone.utc)
    today = date.today()

    existing_tp = db.scalar(
        select(LiquorTransportPermit).where(LiquorTransportPermit.tp_number == payload.tp_number)
    )
    if existing_tp:
        raise HTTPException(status_code=400, detail=f"Transport Permit {payload.tp_number} already recorded.")

    tp = LiquorTransportPermit(
        tenant_id=1,
        tp_number=payload.tp_number,
        tp_date=payload.tp_date,
        supplier_name=payload.supplier_name,
        vehicle_no=payload.vehicle_no,
        invoice_no=payload.invoice_no,
        total_cases=payload.total_cases,
        total_bottles=payload.total_bottles,
        created_at=now,
    )
    db.add(tp)
    db.flush()

    # If itemized brand receipts were provided, update individual brands & FLR-3A
    if payload.items:
        for it in payload.items:
            brand = db.get(LiquorBrand, it.brand_id)
            if not brand:
                continue
            brand.sealed_bottles += it.bottles

            # Update today's FLR-3A entry
            flr3a = db.scalar(
                select(DailyExciseFLR3A).where(
                    DailyExciseFLR3A.register_date == today,
                    DailyExciseFLR3A.brand_id == brand.id
                )
            )
            if flr3a:
                flr3a.tp_received_bottles += it.bottles
                flr3a.closing_sealed += it.bottles

    # Audit log
    audit = AuditLog(
        tenant_id=1,
        staff_name="Storekeeper / Bar Manager",
        action_type="EXCISE_TP_INWARD",
        details_json=f'{{"tp_number": "{payload.tp_number}", "supplier": "{payload.supplier_name}", "bottles": {payload.total_bottles}}}',
        timestamp=now,
    )
    db.add(audit)

    db.commit()
    db.refresh(tp)

    return LiquorTPResponse(
        id=tp.id,
        tenant_id=tp.tenant_id,
        tp_number=tp.tp_number,
        tp_date=tp.tp_date,
        supplier_name=tp.supplier_name,
        vehicle_no=tp.vehicle_no,
        invoice_no=tp.invoice_no,
        total_cases=tp.total_cases,
        total_bottles=tp.total_bottles,
        created_at=tp.created_at,
    )


@router.get("/flr4", response_model=FLR4MonthlyAbstractResponse)
def get_flr4_monthly_abstract(
    month: Optional[int] = Query(None, ge=1, le=12),
    year: Optional[int] = Query(None, ge=2020, le=2035),
    db: Session = Depends(get_db),
):
    """
    Generate Form F.L.R.-4 Monthly Return Abstract.
    Summarizes opening balances, inward receipts, sales, and closing balances
    grouped by statutory category (IMFL Whisky, Beer, Wine, Rum).
    """
    target_date = date.today()
    target_month = month or target_date.month
    target_year = year or target_date.year
    month_name = calendar.month_name[target_month]

    brands = db.scalars(select(LiquorBrand)).all()
    categories_dict: Dict[str, Dict[str, Any]] = {}

    for b in brands:
        cat = b.category or "OTHER_SPIRITS"
        if cat not in categories_dict:
            categories_dict[cat] = {
                "opening_sealed": 0,
                "received_sealed": 0,
                "sales_bottles_equivalent": 0.0,
                "breakage_bottles_equivalent": 0.0,
                "closing_sealed": 0,
            }

        # Query all FLR-3A records for this brand in the given month/year
        start_date = date(target_year, target_month, 1)
        _, last_day = calendar.monthrange(target_year, target_month)
        end_date = date(target_year, target_month, last_day)

        records = db.scalars(
            select(DailyExciseFLR3A).where(
                DailyExciseFLR3A.brand_id == b.id,
                DailyExciseFLR3A.register_date >= start_date,
                DailyExciseFLR3A.register_date <= end_date,
            ).order_by(DailyExciseFLR3A.register_date)
        ).all()

        if records:
            first_rec = records[0]
            last_rec = records[-1]
            tot_tp = sum(r.tp_received_bottles for r in records)
            tot_sales_ml = sum(r.sales_ml for r in records)
            tot_breakage_ml = sum(r.breakage_ml for r in records)

            categories_dict[cat]["opening_sealed"] += first_rec.opening_sealed
            categories_dict[cat]["received_sealed"] += tot_tp
            categories_dict[cat]["sales_bottles_equivalent"] += round(tot_sales_ml / b.bottle_size_ml, 2)
            categories_dict[cat]["breakage_bottles_equivalent"] += round(tot_breakage_ml / b.bottle_size_ml, 2)
            categories_dict[cat]["closing_sealed"] += last_rec.closing_sealed
        else:
            categories_dict[cat]["opening_sealed"] += b.sealed_bottles
            categories_dict[cat]["closing_sealed"] += b.sealed_bottles

    summary_list = [
        FLR4CategorySummary(
            category=k,
            opening_sealed=v["opening_sealed"],
            received_sealed=v["received_sealed"],
            sales_bottles_equivalent=v["sales_bottles_equivalent"],
            breakage_bottles_equivalent=v["breakage_bottles_equivalent"],
            closing_sealed=v["closing_sealed"],
        )
        for k, v in categories_dict.items()
    ]

    return FLR4MonthlyAbstractResponse(
        month=target_month,
        year=target_year,
        month_name=month_name,
        total_active_brands=len(brands),
        categories=summary_list,
    )
