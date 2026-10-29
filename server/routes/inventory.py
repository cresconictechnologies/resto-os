"""
RestoOS Two-Tier Inventory (Central Store & Kitchen Line) Management API
Separation of custody:
1. Central Store Bulk Stock (PO -> GRN Inward with Weighted Average Costing)
2. Store-to-Kitchen Indents (Stock Transfer)
3. Kitchen Line Working Stock & Spoilage/Wastage Governance
4. Live 86 Dish Bottleneck Analysis based on Recipe BOMs
"""

from datetime import datetime, timezone, date
import json
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from ..database import get_db
from ..models import (
    RawMaterial,
    PurchaseOrder,
    PurchaseOrderItem,
    GoodsReceivedNote,
    GRNItem,
    StoreIndent,
    StoreIndentItem,
    RecipeBOM,
    WastageLog,
    MenuItem,
    AuditLog,
)
from ..schemas import (
    RawMaterialResponse,
    PurchaseOrderCreate,
    PurchaseOrderResponse,
    GRNCreateRequest,
    GRNResponse,
    StoreIndentCreate,
    StoreIndentResponse,
    WastageLogCreate,
    WastageLogResponse,
    Live86Response,
    Live86Item,
)

router = APIRouter(prefix="/inventory", tags=["Two-Tier Store & Kitchen Inventory"])


# ============================================================================
# 1. RAW MATERIALS MASTER & STOCK BALANCES
# ============================================================================

@router.get("/raw-materials", response_model=List[RawMaterialResponse])
def get_raw_materials(
    category: Optional[str] = Query(None, description="PRODUCE, MEAT, GROCERY, DAIRY, PACKAGING"),
    low_stock_only: bool = Query(False, description="Filter only items below min reorder level"),
    db: Session = Depends(get_db),
):
    """
    List raw materials with Central Store vs Kitchen Line breakdown.
    """
    query = select(RawMaterial).order_by(RawMaterial.category, RawMaterial.name)
    if category:
        query = query.where(RawMaterial.category == category)

    materials = db.scalars(query).all()
    results = []

    for m in materials:
        total = round(m.current_store_stock + m.current_kitchen_stock, 3)
        is_low = total <= m.min_reorder_level
        if low_stock_only and not is_low:
            continue

        results.append(
            RawMaterialResponse(
                id=m.id,
                tenant_id=m.tenant_id,
                name=m.name,
                category=m.category,
                uom=m.uom,
                current_store_stock=round(m.current_store_stock, 3),
                current_kitchen_stock=round(m.current_kitchen_stock, 3),
                total_stock=total,
                min_reorder_level=m.min_reorder_level,
                unit_cost=m.unit_cost,
                is_low_stock=is_low,
            )
        )
    return results


# ============================================================================
# 2. PROCUREMENT: PURCHASE ORDERS & GRN INWARDS
# ============================================================================

@router.post("/po", response_model=PurchaseOrderResponse)
def create_purchase_order(payload: PurchaseOrderCreate, db: Session = Depends(get_db)):
    """
    Create a Purchase Order to send to an approved supplier.
    """
    now = datetime.now(timezone.utc)
    po_count = db.scalar(select(func.count(PurchaseOrder.id))) or 0
    po_number = f"PO-{now.strftime('%y%m')}-{(po_count + 1):04d}"

    total_amount = sum(it.ordered_qty * it.unit_price for it in payload.items)

    po = PurchaseOrder(
        tenant_id=1,
        po_number=po_number,
        vendor_name=payload.vendor_name,
        status="APPROVED",
        total_amount=round(total_amount, 2),
        created_at=now,
    )
    db.add(po)
    db.flush()

    po_items_data = []
    for it in payload.items:
        raw_mat = db.get(RawMaterial, it.raw_material_id)
        if not raw_mat:
            continue
        line_item = PurchaseOrderItem(
            purchase_order_id=po.id,
            raw_material_id=raw_mat.id,
            ordered_qty=it.ordered_qty,
            unit_price=it.unit_price,
        )
        db.add(line_item)
        po_items_data.append({
            "raw_material_id": raw_mat.id,
            "raw_material_name": raw_mat.name,
            "ordered_qty": it.ordered_qty,
            "unit_price": it.unit_price,
            "line_total": round(it.ordered_qty * it.unit_price, 2),
        })

    db.commit()
    db.refresh(po)

    return PurchaseOrderResponse(
        id=po.id,
        tenant_id=po.tenant_id,
        po_number=po.po_number,
        vendor_name=po.vendor_name,
        status=po.status,
        total_amount=po.total_amount,
        created_at=po.created_at,
        items=po_items_data,
    )


@router.get("/po", response_model=List[PurchaseOrderResponse])
def list_purchase_orders(db: Session = Depends(get_db)):
    """List recent purchase orders."""
    pos = db.scalars(select(PurchaseOrder).order_by(PurchaseOrder.id.desc()).limit(20)).all()
    results = []
    for po in pos:
        items_data = [item.to_dict() for item in po.items]
        results.append(
            PurchaseOrderResponse(
                id=po.id,
                tenant_id=po.tenant_id,
                po_number=po.po_number,
                vendor_name=po.vendor_name,
                status=po.status,
                total_amount=po.total_amount,
                created_at=po.created_at,
                items=items_data,
            )
        )
    return results


@router.post("/grn", response_model=GRNResponse)
def receive_goods_grn(payload: GRNCreateRequest, db: Session = Depends(get_db)):
    """
    Process Goods Received Note (GRN) inward delivery into Central Store.
    Updates Central Store stock and recalculates Weighted Average Cost (WAC).
    """
    now = datetime.now(timezone.utc)
    grn_count = db.scalar(select(func.count(GoodsReceivedNote.id))) or 0
    grn_number = f"GRN-{now.strftime('%y%m')}-{(grn_count + 1):04d}"

    grn = GoodsReceivedNote(
        tenant_id=1,
        grn_number=grn_number,
        po_id=payload.po_id,
        vendor_invoice_no=payload.vendor_invoice_no,
        received_at=now,
    )
    db.add(grn)
    db.flush()

    grn_items_data = []

    for it in payload.items:
        raw_mat = db.get(RawMaterial, it.raw_material_id)
        if not raw_mat:
            raise HTTPException(status_code=400, detail=f"Raw material {it.raw_material_id} invalid.")

        # Recalculate Weighted Average Cost (WAC)
        old_val = raw_mat.current_store_stock * raw_mat.unit_cost
        inward_val = it.received_qty * it.invoice_price
        new_store_qty = raw_mat.current_store_stock + it.received_qty

        if new_store_qty > 0:
            new_wac = (old_val + inward_val) / new_store_qty
            raw_mat.unit_cost = round(new_wac, 2)

        raw_mat.current_store_stock = round(new_store_qty, 3)

        grn_item = GRNItem(
            grn_id=grn.id,
            raw_material_id=raw_mat.id,
            batch_no=it.batch_no,
            expiry_date=it.expiry_date,
            received_qty=it.received_qty,
            invoice_price=it.invoice_price,
        )
        db.add(grn_item)
        grn_items_data.append({
            "raw_material_id": raw_mat.id,
            "raw_material_name": raw_mat.name,
            "batch_no": it.batch_no,
            "expiry_date": it.expiry_date.isoformat() if it.expiry_date else None,
            "received_qty": it.received_qty,
            "invoice_price": it.invoice_price,
            "line_total": round(it.received_qty * it.invoice_price, 2),
        })

    # If linked to a PO, mark it RECEIVED
    if payload.po_id:
        po = db.get(PurchaseOrder, payload.po_id)
        if po:
            po.status = "RECEIVED"

    db.commit()
    db.refresh(grn)

    return GRNResponse(
        id=grn.id,
        tenant_id=grn.tenant_id,
        grn_number=grn.grn_number,
        po_id=grn.po_id,
        vendor_invoice_no=grn.vendor_invoice_no,
        received_at=grn.received_at,
        items=grn_items_data,
    )


# ============================================================================
# 3. STORE INDENTS (CENTRAL STORE TO KITCHEN LINE TRANSFER)
# ============================================================================

@router.post("/indent", response_model=StoreIndentResponse)
def create_store_indent(payload: StoreIndentCreate, db: Session = Depends(get_db)):
    """
    Issue stock from Central Store to Kitchen Line.
    Deducts Central Store stock and increments Kitchen Line stock.
    """
    now = datetime.now(timezone.utc)
    indent_count = db.scalar(select(func.count(StoreIndent.id))) or 0
    indent_number = f"IND-{now.strftime('%y%m')}-{(indent_count + 1):04d}"

    indent = StoreIndent(
        tenant_id=1,
        indent_number=indent_number,
        department=payload.department,
        status="ISSUED",
        issued_at=now,
    )
    db.add(indent)
    db.flush()

    items_data = []

    for it in payload.items:
        raw_mat = db.get(RawMaterial, it.raw_material_id)
        if not raw_mat:
            raise HTTPException(status_code=400, detail=f"Raw material {it.raw_material_id} invalid.")

        qty_to_issue = it.issued_qty if it.issued_qty is not None else it.requested_qty

        # Verify sufficient store stock
        if raw_mat.current_store_stock < qty_to_issue:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient Central Store stock for '{raw_mat.name}'. Available: {raw_mat.current_store_stock} {raw_mat.uom}, requested: {qty_to_issue} {raw_mat.uom}",
            )

        # Transfer custody: Store -> Kitchen
        raw_mat.current_store_stock = round(raw_mat.current_store_stock - qty_to_issue, 3)
        raw_mat.current_kitchen_stock = round(raw_mat.current_kitchen_stock + qty_to_issue, 3)

        indent_item = StoreIndentItem(
            indent_id=indent.id,
            raw_material_id=raw_mat.id,
            requested_qty=it.requested_qty,
            issued_qty=qty_to_issue,
        )
        db.add(indent_item)
        items_data.append({
            "raw_material_id": raw_mat.id,
            "raw_material_name": raw_mat.name,
            "requested_qty": it.requested_qty,
            "issued_qty": qty_to_issue,
        })

    db.commit()
    db.refresh(indent)

    return StoreIndentResponse(
        id=indent.id,
        tenant_id=indent.tenant_id,
        indent_number=indent.indent_number,
        department=indent.department,
        status=indent.status,
        issued_at=indent.issued_at,
        items=items_data,
    )


# ============================================================================
# 4. KITCHEN WASTAGE & SPOILAGE LOGS
# ============================================================================

@router.post("/wastage", response_model=WastageLogResponse)
def log_kitchen_wastage(payload: WastageLogCreate, db: Session = Depends(get_db)):
    """
    Log kitchen food spoilage/wastage (BURNT, DROPPED, EXPIRED, TRIM).
    Validates supervisor PIN and deducts from Kitchen Line stock.
    """
    if payload.supervisor_pin not in ("1234", "9999", "5555"):
        raise HTTPException(status_code=401, detail="Invalid Supervisor PIN authorization.")

    raw_mat = db.get(RawMaterial, payload.raw_material_id)
    if not raw_mat:
        raise HTTPException(status_code=404, detail="Raw material not found.")

    if raw_mat.current_kitchen_stock < payload.quantity:
        raise HTTPException(
            status_code=400,
            detail=f"Kitchen stock only has {raw_mat.current_kitchen_stock} {raw_mat.uom}. Cannot waste {payload.quantity} {raw_mat.uom}.",
        )

    now = datetime.now(timezone.utc)
    raw_mat.current_kitchen_stock = round(raw_mat.current_kitchen_stock - payload.quantity, 3)

    wastage = WastageLog(
        tenant_id=1,
        raw_material_id=raw_mat.id,
        quantity=payload.quantity,
        reason_code=payload.reason_code.upper(),
        authorized_by="Chef Supervisor",
        notes=payload.notes,
        created_at=now,
    )
    db.add(wastage)

    # Audit log
    audit = AuditLog(
        tenant_id=1,
        staff_name="Chef Supervisor (PIN Auth)",
        action_type="KITCHEN_WASTAGE",
        details_json=json.dumps({
            "ingredient": raw_mat.name,
            "qty": payload.quantity,
            "reason": payload.reason_code,
            "cost_loss": round(payload.quantity * raw_mat.unit_cost, 2),
        }),
        timestamp=now,
    )
    db.add(audit)

    db.commit()
    db.refresh(wastage)

    return WastageLogResponse(
        id=wastage.id,
        tenant_id=wastage.tenant_id,
        raw_material_id=wastage.raw_material_id,
        material_name=raw_mat.name,
        quantity=wastage.quantity,
        uom=raw_mat.uom,
        reason_code=wastage.reason_code,
        authorized_by=wastage.authorized_by,
        notes=wastage.notes,
        created_at=wastage.created_at,
    )


# ============================================================================
# 5. LIVE 86-ITEM BOTTLENECK ANALYSIS
# ============================================================================

@router.get("/live-86", response_model=Live86Response)
def get_live_86_analysis(db: Session = Depends(get_db)):
    """
    Computes real-time 86 (Out of Stock) dish availability:
    Evaluates every menu dish against Recipe BOMs and Kitchen Line stock.
    Identifies bottleneck raw ingredients and calculates max possible portions.
    """
    menu_items = db.scalars(
        select(MenuItem).where(MenuItem.is_active == True, MenuItem.tax_category == "GST_FOOD")
    ).all()

    results = []
    total_86 = 0

    for dish in menu_items:
        boms = dish.bom_recipes

        if not boms:
            # No BOM defined -> assume available
            results.append(
                Live86Item(
                    menu_item_id=dish.id,
                    menu_item_name=dish.name,
                    category=dish.category,
                    is_86=dish.is_86,
                    bottleneck_ingredient=None,
                    kitchen_stock_available=999.0,
                    portions_possible=999.0,
                )
            )
            continue

        bottleneck_name = None
        min_portions = 99999.0
        lowest_stock = 0.0

        for bom in boms:
            rm = bom.raw_material
            if not rm:
                continue

            # Effective ingredient consumption factoring prep shrinkage yield %
            yield_multiplier = (bom.prep_shrinkage_yield_pct or 100.0) / 100.0
            effective_qty_per_portion = bom.quantity_required / max(0.01, yield_multiplier)

            available_stock = rm.current_kitchen_stock
            portions = available_stock / max(0.001, effective_qty_per_portion)

            if portions < min_portions:
                min_portions = portions
                bottleneck_name = f"{rm.name} ({available_stock:.1f} {rm.uom} left)"
                lowest_stock = available_stock

        is_auto_86 = (min_portions < 1.0) or dish.is_86
        if is_auto_86:
            total_86 += 1

        results.append(
            Live86Item(
                menu_item_id=dish.id,
                menu_item_name=dish.name,
                category=dish.category,
                is_86=is_auto_86,
                bottleneck_ingredient=bottleneck_name if min_portions < 5.0 else None,
                kitchen_stock_available=round(lowest_stock, 2),
                portions_possible=max(0.0, round(min_portions, 1)),
            )
        )

    return Live86Response(
        items=results,
        total_86_count=total_86,
    )
