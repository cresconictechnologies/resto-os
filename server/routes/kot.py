"""
RestoOS Multi-Station KOT / BOT Dispatch API
Intelligently routes food items to Kitchen Station (KOT) and alcoholic beverages
to Bar Dispense Station (BOT), generating ESC/POS thermal printer tickets.
"""

from datetime import datetime, timezone
import json
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from ..database import get_db
from ..models import Order, OrderItem, DiningTable, Ticket, MenuItem
from ..schemas import FireKOTBOTRequest, FireKOTBOTResponse, TicketResponse
from ..escpos_utils import generate_kot_bot_80mm

router = APIRouter(prefix="/kot", tags=["KOT & BOT Dispatch"])


@router.post("/fire", response_model=FireKOTBOTResponse)
def fire_kot_bot(payload: FireKOTBOTRequest, db: Session = Depends(get_db)):
    """
    Fire pending order items:
    - Food items (GST_FOOD) generate a Kitchen Order Ticket (KOT).
    - Liquor / Alcohol items (VAT_ALCOHOL) generate a Bar Order Ticket (BOT).
    - Generates 80mm ESC/POS print-ready text.
    - Marks items as printed and updates Table status to 'ORDERED'.
    """
    order = db.get(Order, payload.order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")

    table_code = order.table.code if order.table else "COUNTER"
    tenant_id = order.tenant_id

    # Find unprinted items
    unprinted_items = [
        item for item in order.items
        if item.status != "VOIDED" and not (item.is_kot_printed and item.is_bot_printed)
    ]

    if not unprinted_items:
        return FireKOTBOTResponse(
            kot_ticket=None,
            bot_ticket=None,
            kot_text_80mm=None,
            bot_text_80mm=None,
            items_fired_count=0,
            message="No unprinted items to fire.",
        )

    food_items_to_print = []
    liquor_items_to_print = []

    for item in unprinted_items:
        # Determine category from menu item
        tax_cat = item.menu_item.tax_category if item.menu_item else "GST_FOOD"
        if tax_cat == "VAT_ALCOHOL" and not item.is_bot_printed:
            liquor_items_to_print.append(item)
        elif not item.is_kot_printed:
            food_items_to_print.append(item)

    now = datetime.now(timezone.utc)
    kot_ticket_resp = None
    bot_ticket_resp = None
    kot_text = None
    bot_text = None
    total_fired = 0

    # 1. Generate KOT if food items exist
    if food_items_to_print:
        kot_count = db.scalar(
            select(func.count(Ticket.id)).where(Ticket.ticket_type == "KOT")
        ) or 0
        kot_number = f"KOT-{(kot_count + 1):04d}"

        kot_items_payload = [
            {
                "item_id": item.id,
                "item_name": item.item_name,
                "quantity": item.quantity,
                "prep_note": item.prep_note,
            }
            for item in food_items_to_print
        ]

        kot_text = generate_kot_bot_80mm(
            ticket_type="KOT",
            ticket_number=kot_number,
            table_code=table_code,
            items=kot_items_payload,
            server_name="Captain",
            timestamp=now,
        )

        ticket_kot = Ticket(
            tenant_id=tenant_id,
            order_id=order.id,
            ticket_number=kot_number,
            ticket_type="KOT",
            table_code=table_code,
            payload_json=json.dumps(kot_items_payload),
            printed_at=now,
        )
        db.add(ticket_kot)
        db.flush()

        for it in food_items_to_print:
            it.is_kot_printed = True
            total_fired += it.quantity

        kot_ticket_resp = TicketResponse(
            id=ticket_kot.id,
            tenant_id=ticket_kot.tenant_id,
            order_id=ticket_kot.order_id,
            ticket_number=ticket_kot.ticket_number,
            ticket_type=ticket_kot.ticket_type,
            table_code=ticket_kot.table_code,
            payload={"items": kot_items_payload},
            printed_at=ticket_kot.printed_at,
            raw_escpos_text=kot_text,
        )

    # 2. Generate BOT if liquor items exist
    if liquor_items_to_print:
        bot_count = db.scalar(
            select(func.count(Ticket.id)).where(Ticket.ticket_type == "BOT")
        ) or 0
        bot_number = f"BOT-{(bot_count + 1):04d}"

        bot_items_payload = [
            {
                "item_id": item.id,
                "item_name": item.item_name,
                "quantity": item.quantity,
                "prep_note": item.prep_note,
            }
            for item in liquor_items_to_print
        ]

        bot_text = generate_kot_bot_80mm(
            ticket_type="BOT",
            ticket_number=bot_number,
            table_code=table_code,
            items=bot_items_payload,
            server_name="Bartender",
            timestamp=now,
        )

        ticket_bot = Ticket(
            tenant_id=tenant_id,
            order_id=order.id,
            ticket_number=bot_number,
            ticket_type="BOT",
            table_code=table_code,
            payload_json=json.dumps(bot_items_payload),
            printed_at=now,
        )
        db.add(ticket_bot)
        db.flush()

        for it in liquor_items_to_print:
            it.is_bot_printed = True
            total_fired += it.quantity

        bot_ticket_resp = TicketResponse(
            id=ticket_bot.id,
            tenant_id=ticket_bot.tenant_id,
            order_id=ticket_bot.order_id,
            ticket_number=ticket_bot.ticket_number,
            ticket_type=ticket_bot.ticket_type,
            table_code=ticket_bot.table_code,
            payload={"items": bot_items_payload},
            printed_at=ticket_bot.printed_at,
            raw_escpos_text=bot_text,
        )

    # Update order & table states
    order.status = "ORDERED"
    order.updated_at = now
    if order.table:
        order.table.status = "ORDERED"

    db.commit()

    return FireKOTBOTResponse(
        kot_ticket=kot_ticket_resp,
        bot_ticket=bot_ticket_resp,
        kot_text_80mm=kot_text,
        bot_text_80mm=bot_text,
        items_fired_count=total_fired,
        message=f"Successfully fired {total_fired} items to Kitchen/Bar.",
    )


@router.get("/tickets", response_model=List[TicketResponse])
def list_tickets(
    ticket_type: Optional[str] = Query(None, description="KOT or BOT"),
    limit: int = Query(20, le=100),
    db: Session = Depends(get_db),
):
    """List recent KOT / BOT tickets for reprint or monitoring."""
    query = select(Ticket).order_by(Ticket.id.desc()).limit(limit)
    if ticket_type:
        query = query.where(Ticket.ticket_type == ticket_type)

    tickets = db.scalars(query).all()
    results = []
    for t in tickets:
        payload = json.loads(t.payload_json) if t.payload_json else {}
        results.append(
            TicketResponse(
                id=t.id,
                tenant_id=t.tenant_id,
                order_id=t.order_id,
                ticket_number=t.ticket_number,
                ticket_type=t.ticket_type,
                table_code=t.table_code,
                payload=payload,
                printed_at=t.printed_at,
                raw_escpos_text="",
            )
        )
    return results
