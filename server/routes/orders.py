"""
RestoOS Orders & Cart Line Items API
Manages table order sessions, menu browsing, item additions, quantity updates,
and 86-item inventory toggling.
"""

from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from ..database import get_db
from ..models import Order, OrderItem, DiningTable, MenuItem, AuditLog, Tenant, MenuCategory
from ..schemas import (
    OrderResponse,
    OrderCreate,
    OrderItemCreate,
    OrderItemUpdate,
    OrderItemResponse,
    MenuItemResponse,
    MenuItemUpdate86,
    MenuItemCreate,
    MenuItemUpdate,
    MenuCategoryCreate,
    MenuCategoryResponse,
    TenantResponse,
    TenantUpdate,
)
from ..auth_guard import require_admin, verify_token, TokenPayload

router = APIRouter(prefix="", tags=["Orders & Cart"])


def _format_order_response(order: Order) -> OrderResponse:
    """Builds a typed OrderResponse with items, subtotals, and total calculation."""
    items_resp = []
    total_amount = 0.0

    for item in order.items:
        subtotal = round(item.quantity * item.unit_price, 2)
        total_amount += subtotal
        items_resp.append(
            OrderItemResponse(
                id=item.id,
                order_id=item.order_id,
                menu_item_id=item.menu_item_id,
                item_name=item.item_name,
                quantity=item.quantity,
                unit_price=item.unit_price,
                subtotal=subtotal,
                prep_note=item.prep_note,
                is_kot_printed=item.is_kot_printed,
                is_bot_printed=item.is_bot_printed,
                status=item.status,
                created_at=item.created_at,
                is_veg=item.menu_item.is_veg if item.menu_item else None,
                tax_category=item.menu_item.tax_category if item.menu_item else None,
            )
        )

    return OrderResponse(
        id=order.id,
        tenant_id=order.tenant_id,
        table_id=order.table_id,
        table_code=order.table.code if order.table else None,
        order_type=order.order_type,
        status=order.status,
        created_at=order.created_at,
        updated_at=order.updated_at,
        items=items_resp,
        total_amount=round(total_amount, 2),
    )


# ============================================================================
# MENU CATALOG ENDPOINTS
# ============================================================================

@router.get("/menu", response_model=List[MenuItemResponse])
def get_menu_items(
    category: Optional[str] = Query(None, description="Category filter (Breakfast, Mains, Bar)"),
    is_veg: Optional[bool] = Query(None, description="Filter for vegetarian items only"),
    search: Optional[str] = Query(None, description="Search item name"),
    db: Session = Depends(get_db),
):
    """
    Retrieve restaurant menu catalog with category filtering and 'Veg only' switch.
    """
    query = select(MenuItem).where(MenuItem.is_active == True).order_by(MenuItem.category, MenuItem.name)

    if category:
        query = query.where(MenuItem.category == category)
    if is_veg is not None:
        query = query.where(MenuItem.is_veg == is_veg)
    if search:
        query = query.where(MenuItem.name.ilike(f"%{search}%"))

    items = db.scalars(query).all()
    return [
        MenuItemResponse(
            id=item.id,
            tenant_id=item.tenant_id,
            name=item.name,
            category=item.category,
            is_veg=item.is_veg,
            price=item.price,
            hsn_code=item.hsn_code,
            tax_category=item.tax_category,
            is_active=item.is_active,
            is_86=item.is_86,
            description=item.description,
        )
        for item in items
    ]


@router.patch("/menu/{menu_item_id}/86", response_model=MenuItemResponse)
def update_item_86_status(
    menu_item_id: int,
    payload: MenuItemUpdate86,
    db: Session = Depends(get_db),
):
    """
    Toggle 86 (Out of Stock) flag for a menu dish in real time across all POS stations.
    """
    item = db.get(MenuItem, menu_item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Menu item not found.")

    item.is_86 = payload.is_86
    db.commit()
    db.refresh(item)
    return MenuItemResponse(
        id=item.id,
        tenant_id=item.tenant_id,
        name=item.name,
        category=item.category,
        is_veg=item.is_veg,
        price=item.price,
        hsn_code=item.hsn_code,
        tax_category=item.tax_category,
        is_active=item.is_active,
        is_86=item.is_86,
        description=item.description,
    )


# ============================================================================
# CATEGORY MANAGEMENT (STATIONS & DUAL-TAX CLASSIFICATION)
# ============================================================================

@router.get("/categories", response_model=List[MenuCategoryResponse])
def get_categories(db: Session = Depends(get_db)):
    """
    List all active menu categories with live dish counts.
    Auto-seeds standard categories from existing menu items if table is empty.
    """
    from ..database import engine
    from ..models import Base
    Base.metadata.create_all(bind=engine)

    categories = list(db.scalars(select(MenuCategory).order_by(MenuCategory.sort_order, MenuCategory.name)).all())
    
    # If empty, seed from distinct categories in menu_items
    if not categories:
        distinct_cats = db.execute(
            select(MenuItem.category, MenuItem.tax_category).distinct()
        ).all()
        
        seen = set()
        for idx, (cat_name, tax_cat) in enumerate(distinct_cats):
            if not cat_name or cat_name in seen:
                continue
            seen.add(cat_name)
            is_bar = (tax_cat in ("VAT_ALCOHOL", "ALCOHOL_VAT") or "bar" in cat_name.lower())
            new_cat = MenuCategory(
                tenant_id=1,
                name=cat_name,
                department="BAR" if is_bar else "KITCHEN",
                tax_category="VAT_ALCOHOL" if is_bar else "GST_FOOD",
                sort_order=idx,
                is_active=True
            )
            db.add(new_cat)
        db.commit()
        categories = list(db.scalars(select(MenuCategory).order_by(MenuCategory.sort_order, MenuCategory.name)).all())

    result = []
    for cat in categories:
        count = db.scalars(
            select(MenuItem).where(MenuItem.category == cat.name, MenuItem.is_active == True)
        ).all()
        result.append(
            MenuCategoryResponse(
                id=cat.id,
                name=cat.name,
                department=cat.department,
                tax_category=cat.tax_category,
                sort_order=cat.sort_order,
                is_active=cat.is_active,
                item_count=len(count)
            )
        )
    return result


@router.post("/categories", response_model=MenuCategoryResponse, status_code=status.HTTP_201_CREATED)
def create_category(
    payload: MenuCategoryCreate,
    db: Session = Depends(get_db),
    auth: TokenPayload = Depends(require_admin),
):
    """Create or activate a menu category."""
    from ..database import engine
    from ..models import Base
    Base.metadata.create_all(bind=engine)

    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Category name cannot be blank.")

    existing = db.scalars(select(MenuCategory).where(MenuCategory.name.ilike(name))).first()
    if existing:
        existing.is_active = True
        if payload.department:
            existing.department = payload.department
        if payload.tax_category:
            existing.tax_category = payload.tax_category
        db.commit()
        db.refresh(existing)
        item_count = len(db.scalars(select(MenuItem).where(MenuItem.category == existing.name, MenuItem.is_active == True)).all())
        return MenuCategoryResponse(
            id=existing.id,
            name=existing.name,
            department=existing.department,
            tax_category=existing.tax_category,
            sort_order=existing.sort_order,
            is_active=existing.is_active,
            item_count=item_count
        )

    cat = MenuCategory(
        tenant_id=1,
        name=name,
        department=payload.department or "KITCHEN",
        tax_category=payload.tax_category or "GST_FOOD",
        sort_order=payload.sort_order or 0,
        is_active=True
    )
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return MenuCategoryResponse(
        id=cat.id,
        name=cat.name,
        department=cat.department,
        tax_category=cat.tax_category,
        sort_order=cat.sort_order,
        is_active=cat.is_active,
        item_count=0
    )


@router.delete("/categories/{category_id}")
def delete_category(
    category_id: int,
    db: Session = Depends(get_db),
    auth: TokenPayload = Depends(require_admin),
):
    """Archive / delete a category."""
    cat = db.get(MenuCategory, category_id)
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found.")
    cat.is_active = False
    db.commit()
    return {"status": "archived", "id": category_id, "name": cat.name}


@router.post("/menu", response_model=MenuItemResponse, status_code=status.HTTP_201_CREATED)
def create_menu_item(
    payload: MenuItemCreate,
    db: Session = Depends(get_db),
    auth: TokenPayload = Depends(require_admin),
):
    """Create a new dish/drink in the menu catalog and auto-register category."""
    tenant = db.scalars(select(Tenant)).first()
    tenant_id = tenant.id if tenant else 1

    cat_name = payload.category.strip()
    
    # Auto-register category if not exists
    from ..database import engine
    from ..models import Base
    Base.metadata.create_all(bind=engine)
    existing_cat = db.scalars(select(MenuCategory).where(MenuCategory.name.ilike(cat_name))).first()
    if not existing_cat:
        is_bar = (payload.tax_category in ("VAT_ALCOHOL", "ALCOHOL_VAT") or "bar" in cat_name.lower())
        new_cat = MenuCategory(
            tenant_id=tenant_id,
            name=cat_name,
            department="BAR" if is_bar else "KITCHEN",
            tax_category=payload.tax_category or ("VAT_ALCOHOL" if is_bar else "GST_FOOD"),
            is_active=True
        )
        db.add(new_cat)

    item = MenuItem(
        tenant_id=tenant_id,
        name=payload.name.strip(),
        category=cat_name,
        is_veg=payload.is_veg,
        price=round(payload.price, 2),
        hsn_code=payload.hsn_code or "996331",
        tax_category=payload.tax_category or "GST_FOOD",
        is_active=payload.is_active if payload.is_active is not None else True,
        is_86=payload.is_86 if payload.is_86 is not None else False,
        description=payload.description,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/menu/{menu_item_id}", response_model=MenuItemResponse)
def update_menu_item(
    menu_item_id: int,
    payload: MenuItemUpdate,
    db: Session = Depends(get_db),
    auth: TokenPayload = Depends(require_admin),
):
    """Update dish price, name, category, tax type, or availability."""
    item = db.get(MenuItem, menu_item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Menu item not found.")

    if payload.name is not None:
        item.name = payload.name.strip()
    if payload.category is not None:
        item.category = payload.category.strip()
    if payload.is_veg is not None:
        item.is_veg = payload.is_veg
    if payload.price is not None:
        old_price = item.price
        item.price = round(payload.price, 2)
        # Log rate change to audit
        db.add(
            AuditLog(
                tenant_id=item.tenant_id,
                action_type="RATE_CHANGE",
                staff_name="Manager / Settings",
                details_json=f'{{"dish": "{item.name}", "old_price": {old_price}, "new_price": {item.price}}}',
                timestamp=datetime.now(timezone.utc),
            )
        )
    if payload.hsn_code is not None:
        item.hsn_code = payload.hsn_code.strip()
    if payload.tax_category is not None:
        item.tax_category = payload.tax_category
    if payload.is_active is not None:
        item.is_active = payload.is_active
    if payload.is_86 is not None:
        item.is_86 = payload.is_86
    if payload.description is not None:
        item.description = payload.description

    db.commit()
    db.refresh(item)
    return item


@router.delete("/menu/{menu_item_id}")
def delete_menu_item(
    menu_item_id: int,
    db: Session = Depends(get_db),
    auth: TokenPayload = Depends(require_admin),
):
    """Delete or archive a menu item."""
    item = db.get(MenuItem, menu_item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Menu item not found.")

    item.is_active = False
    db.commit()
    return {"status": "archived", "id": menu_item_id, "name": item.name}


# ============================================================================
# RESTAURANT TENANT SETTINGS ENDPOINTS
# ============================================================================

@router.get("/tenant", response_model=TenantResponse)
def get_tenant_details(db: Session = Depends(get_db)):
    """Fetch restaurant profile, statutory numbers, and tax settings."""
    tenant = db.scalars(select(Tenant)).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant details not found.")
    return tenant


@router.put("/tenant", response_model=TenantResponse)
def update_tenant_details(
    payload: TenantUpdate,
    db: Session = Depends(get_db),
    auth: TokenPayload = Depends(require_admin),
):
    """Update restaurant profile, GSTIN, FSSAI, FL-3, address, and phone."""
    tenant = db.scalars(select(Tenant)).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found.")

    if payload.name is not None:
        tenant.name = payload.name.strip()
    if payload.outlet_name is not None:
        tenant.outlet_name = payload.outlet_name.strip()
    if payload.address is not None:
        tenant.address = payload.address.strip()
    if payload.gstin is not None:
        tenant.gstin = payload.gstin.strip()
    if payload.fssai is not None:
        tenant.fssai = payload.fssai.strip()
    if payload.fl3_license is not None:
        tenant.fl3_license = payload.fl3_license.strip()
    if payload.vatin is not None:
        tenant.vatin = payload.vatin.strip()
    if payload.phone is not None:
        tenant.phone = payload.phone.strip()

    db.commit()
    db.refresh(tenant)
    return tenant


# ============================================================================
# ORDERS ENDPOINTS
# ============================================================================

@router.get("/orders/table/{table_id}", response_model=OrderResponse)
def get_order_by_table(table_id: int, db: Session = Depends(get_db)):
    """
    Fetch the currently active order for a given dining table.
    If none exists and table is seated, automatically creates an active session.
    """
    table = db.get(DiningTable, table_id)
    if not table:
        raise HTTPException(status_code=404, detail="Table not found.")

    order = db.scalar(
        select(Order).where(
            Order.table_id == table_id,
            Order.status.in_(["ACTIVE", "ORDERED", "BILLED"])
        ).order_by(Order.id.desc()).limit(1)
    )

    if not order:
        order = Order(
            tenant_id=table.tenant_id,
            table_id=table.id,
            order_type="DINE_IN",
            status="ACTIVE",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(order)
        db.commit()
        db.refresh(order)

    return _format_order_response(order)


@router.get("/orders/{order_id}", response_model=OrderResponse)
def get_order_by_id(order_id: int, db: Session = Depends(get_db)):
    """Retrieve full details of an order session by ID."""
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")
    return _format_order_response(order)


@router.post("/orders", response_model=OrderResponse)
def create_order(payload: OrderCreate, db: Session = Depends(get_db)):
    """
    Create a new order for a table or takeaway counter.
    """
    table_id = payload.table_id
    tenant_id = 1

    if payload.table_code and not table_id:
        table = db.scalar(select(DiningTable).where(DiningTable.code == payload.table_code))
        if table:
            table_id = table.id
            tenant_id = table.tenant_id
    elif table_id:
        table = db.get(DiningTable, table_id)
        if table:
            tenant_id = table.tenant_id

    order = Order(
        tenant_id=tenant_id,
        table_id=table_id,
        order_type=payload.order_type,
        status="ACTIVE",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(order)
    db.flush()

    for item_data in payload.items:
        menu_item = db.get(MenuItem, item_data.menu_item_id)
        if not menu_item:
            continue
        order_item = OrderItem(
            order_id=order.id,
            menu_item_id=menu_item.id,
            item_name=menu_item.name,
            quantity=item_data.quantity,
            unit_price=menu_item.price,
            prep_note=item_data.prep_note,
            is_kot_printed=False,
            is_bot_printed=False,
            status="ORDERED",
            created_at=datetime.now(timezone.utc),
        )
        db.add(order_item)

    if table_id:
        table = db.get(DiningTable, table_id)
        if table and table.status == "OPEN":
            table.status = "SEATED"
            table.seated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(order)
    return _format_order_response(order)


@router.post("/orders/{order_id}/items", response_model=OrderResponse)
def add_items_to_order(
    order_id: int,
    payload: List[OrderItemCreate],
    db: Session = Depends(get_db),
):
    """
    Add items to an existing running order cart.
    If an unprinted item already exists with matching prep notes, increments quantity.
    """
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")

    for item_data in payload:
        menu_item = db.get(MenuItem, item_data.menu_item_id)
        if not menu_item:
            raise HTTPException(status_code=400, detail=f"Menu item {item_data.menu_item_id} invalid.")

        if menu_item.is_86:
            raise HTTPException(
                status_code=400,
                detail=f"Item '{menu_item.name}' is currently 86'd (Out of stock)."
            )

        # Check for unprinted line item to merge
        existing_item = db.scalar(
            select(OrderItem).where(
                OrderItem.order_id == order.id,
                OrderItem.menu_item_id == menu_item.id,
                OrderItem.is_kot_printed == False,
                OrderItem.is_bot_printed == False,
                OrderItem.prep_note == item_data.prep_note,
                OrderItem.status != "VOIDED"
            )
        )

        if existing_item:
            existing_item.quantity += item_data.quantity
        else:
            new_item = OrderItem(
                order_id=order.id,
                menu_item_id=menu_item.id,
                item_name=menu_item.name,
                quantity=item_data.quantity,
                unit_price=menu_item.price,
                prep_note=item_data.prep_note,
                is_kot_printed=False,
                is_bot_printed=False,
                status="ORDERED",
                created_at=datetime.now(timezone.utc),
            )
            db.add(new_item)

    order.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(order)
    return _format_order_response(order)


@router.patch("/orders/items/{item_id}", response_model=OrderItemResponse)
def update_order_item(
    item_id: int,
    payload: OrderItemUpdate,
    db: Session = Depends(get_db),
):
    """Update quantity, prep note, or status of an order line item."""
    item = db.get(OrderItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Order item not found.")

    if payload.quantity is not None:
        if payload.quantity <= 0:
            raise HTTPException(status_code=400, detail="Quantity must be at least 1.")
        item.quantity = payload.quantity

    if payload.prep_note is not None:
        item.prep_note = payload.prep_note

    if payload.status is not None:
        item.status = payload.status

    db.commit()
    db.refresh(item)

    return OrderItemResponse(
        id=item.id,
        order_id=item.order_id,
        menu_item_id=item.menu_item_id,
        item_name=item.item_name,
        quantity=item.quantity,
        unit_price=item.unit_price,
        subtotal=round(item.quantity * item.unit_price, 2),
        prep_note=item.prep_note,
        is_kot_printed=item.is_kot_printed,
        is_bot_printed=item.is_bot_printed,
        status=item.status,
        created_at=item.created_at,
        is_veg=item.menu_item.is_veg if item.menu_item else None,
        tax_category=item.menu_item.tax_category if item.menu_item else None,
    )


@router.delete("/orders/items/{item_id}")
def remove_order_item(
    item_id: int,
    staff_name: str = Query("Cashier 1", description="Authorizing staff member"),
    reason: Optional[str] = Query(None, description="Reason for voiding"),
    db: Session = Depends(get_db),
):
    """
    Remove or void an order line item.
    If already fired to Kitchen (KOT printed) or Bar (BOT printed), records
    mandatory VOID_KOT audit log entry to prevent fraud.
    """
    item = db.get(OrderItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Order item not found.")

    was_printed = item.is_kot_printed or item.is_bot_printed

    if was_printed:
        # Mark as VOIDED rather than hard deleting, and log audit event
        item.status = "VOIDED"
        audit = AuditLog(
            tenant_id=1,
            staff_name=staff_name,
            action_type="VOID_KOT",
            details_json=f'{{"item_id": {item.id}, "item_name": "{item.item_name}", "qty": {item.quantity}, "amount": {item.quantity * item.unit_price}, "reason": "{reason or "Customer cancelled"}"}}',
            timestamp=datetime.now(timezone.utc),
        )
        db.add(audit)
        db.commit()
        return {"status": "voided", "message": f"Printed item '{item.item_name}' marked VOIDED and audited."}
    else:
        # Unprinted item: safe to delete directly from cart
        db.delete(item)
        db.commit()
        return {"status": "deleted", "message": f"Item '{item.item_name}' removed from cart."}
