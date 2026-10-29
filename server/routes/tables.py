"""
RestoOS Dining Tables & Floor Plan API
Manages table floor layouts (Ground floor, Terrace), occupancy states,
seating timers, and guest count tracking.
"""

from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from ..database import get_db
from ..models import DiningTable, Order, Bill
from ..schemas import TableResponse, TablesGroupedResponse, TableSeatRequest, TableGuestCountUpdate

router = APIRouter(prefix="/tables", tags=["Tables & Floor Layout"])


def _compute_table_response(table: DiningTable, db: Session) -> TableResponse:
    """Computes elapsed minutes and active order ID for a dining table."""
    now = datetime.now(timezone.utc)
    elapsed_minutes = None
    if table.seated_at:
        seated = table.seated_at
        if seated.tzinfo is None:
            seated = seated.replace(tzinfo=timezone.utc)
        elapsed_minutes = max(0, int((now - seated).total_seconds() // 60))

    # Find active order
    active_order = db.scalar(
        select(Order).where(
            Order.table_id == table.id,
            Order.status.in_(["ACTIVE", "ORDERED", "BILLED"])
        ).order_by(Order.id.desc()).limit(1)
    )

    current_bill_id = None
    if active_order:
        active_bill = db.scalar(
            select(Bill).where(
                Bill.order_id == active_order.id,
                Bill.payment_status == "PENDING"
            ).order_by(Bill.id.desc()).limit(1)
        )
        if active_bill:
            current_bill_id = active_bill.id

    return TableResponse(
        id=table.id,
        tenant_id=table.tenant_id,
        code=table.code,
        section=table.section,
        seats=table.seats,
        status=table.status,
        seated_at=table.seated_at,
        guest_count=table.guest_count,
        elapsed_minutes=elapsed_minutes,
        active_order_id=active_order.id if active_order else None,
        current_bill_id=current_bill_id,
    )


@router.get("", response_model=TablesGroupedResponse)
def get_all_tables(
    section: Optional[str] = Query(None, description="Filter by section (Ground floor, Terrace)"),
    db: Session = Depends(get_db),
):
    """
    Retrieve all dining tables grouped by section with live occupancy and seating timers.
    """
    query = select(DiningTable).order_by(DiningTable.section, DiningTable.id)
    if section:
        query = query.where(DiningTable.section == section)

    tables = db.scalars(query).all()

    sections_dict: Dict[str, List[TableResponse]] = {}
    occupied_count = 0
    open_count = 0

    for table in tables:
        table_resp = _compute_table_response(table, db)
        if table.status in ("SEATED", "ORDERED", "BILLED"):
            occupied_count += 1
        else:
            open_count += 1

        sec_name = table.section or "Main Dining"
        if sec_name not in sections_dict:
            sections_dict[sec_name] = []
        sections_dict[sec_name].append(table_resp)

    return TablesGroupedResponse(
        sections=sections_dict,
        total_tables=len(tables),
        occupied_tables=occupied_count,
        open_tables=open_count,
    )


@router.get("/{table_id}", response_model=TableResponse)
def get_table_by_id(table_id: int, db: Session = Depends(get_db)):
    """Retrieve details and status for a specific dining table."""
    table = db.get(DiningTable, table_id)
    if not table:
        raise HTTPException(status_code=404, detail=f"Table with ID {table_id} not found.")
    return _compute_table_response(table, db)


@router.post("/{table_id}/seat", response_model=TableResponse)
def seat_table(
    table_id: int,
    payload: TableSeatRequest,
    db: Session = Depends(get_db),
):
    """
    Seat guests at a dining table.
    Sets status to 'SEATED', stamps current UTC timestamp, and initializes active order.
    """
    table = db.get(DiningTable, table_id)
    if not table:
        raise HTTPException(status_code=404, detail=f"Table with ID {table_id} not found.")

    table.status = "SEATED"
    table.seated_at = datetime.now(timezone.utc)
    table.guest_count = payload.guest_count

    # Check for existing active order or create one
    existing_order = db.scalar(
        select(Order).where(
            Order.table_id == table.id,
            Order.status.in_(["ACTIVE", "ORDERED"])
        ).limit(1)
    )

    if not existing_order:
        new_order = Order(
            tenant_id=table.tenant_id,
            table_id=table.id,
            order_type="DINE_IN",
            status="ACTIVE",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(new_order)

    db.commit()
    db.refresh(table)
    return _compute_table_response(table, db)


@router.patch("/{table_id}/guests", response_model=TableResponse)
def update_table_guest_count(
    table_id: int,
    payload: TableGuestCountUpdate,
    db: Session = Depends(get_db),
):
    """Update guest count / covers for an occupied table."""
    table = db.get(DiningTable, table_id)
    if not table:
        raise HTTPException(status_code=404, detail=f"Table with ID {table_id} not found.")

    table.guest_count = payload.guest_count
    db.commit()
    db.refresh(table)
    return _compute_table_response(table, db)


@router.post("/{table_id}/clear", response_model=TableResponse)
def clear_table(table_id: int, db: Session = Depends(get_db)):
    """
    Reset a table to OPEN status after guests depart and sanitation is completed.
    """
    table = db.get(DiningTable, table_id)
    if not table:
        raise HTTPException(status_code=404, detail=f"Table with ID {table_id} not found.")

    table.status = "OPEN"
    table.seated_at = None
    table.guest_count = 0

    # Close any open active order that was abandoned or settled
    active_orders = db.scalars(
        select(Order).where(
            Order.table_id == table.id,
            Order.status.in_(["ACTIVE", "ORDERED", "BILLED"])
        )
    ).all()
    for o in active_orders:
        o.status = "COMPLETED"
        o.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(table)
    return _compute_table_response(table, db)
