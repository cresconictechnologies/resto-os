"""
RestoOS Production SQLAlchemy ORM Models
Architected for Restaurant Point of Sale, KOT/BOT Routing, Split Billing (GST + VAT),
Two-Tier Store-to-Kitchen Inventory, and FLR-3A Maharashtra Liquor State Excise Compliance.
"""

from datetime import datetime, timezone, date
from typing import Optional, List, Dict, Any
import json

from sqlalchemy import (
    String,
    Integer,
    Float,
    Boolean,
    DateTime,
    Date,
    Text,
    ForeignKey,
    Index,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    """Return current timestamp in UTC."""
    return datetime.now(timezone.utc)


# ============================================================================
# 1. TENANCY & ACCESS CONTROL (RBAC)
# ============================================================================

class Tenant(Base):
    """
    Multi-tenant enterprise boundary for restaurant outlets.
    Stores legal registrations (GSTIN, FSSAI, Maharashtra State Excise FL-3, VAT).
    """
    __tablename__ = "tenants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    outlet_name: Mapped[str] = mapped_column(String(100), nullable=False)
    address: Mapped[str] = mapped_column(Text, nullable=False)
    gstin: Mapped[str] = mapped_column(String(20), nullable=False)
    fssai: Mapped[str] = mapped_column(String(20), nullable=False)
    fl3_license: Mapped[str] = mapped_column(String(30), nullable=False)
    vatin: Mapped[str] = mapped_column(String(20), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    # Relationships
    users: Mapped[List["User"]] = relationship("User", back_populates="tenant", cascade="all, delete-orphan")
    tables: Mapped[List["DiningTable"]] = relationship("DiningTable", back_populates="tenant", cascade="all, delete-orphan")
    menu_items: Mapped[List["MenuItem"]] = relationship("MenuItem", back_populates="tenant", cascade="all, delete-orphan")
    orders: Mapped[List["Order"]] = relationship("Order", back_populates="tenant", cascade="all, delete-orphan")
    bills: Mapped[List["Bill"]] = relationship("Bill", back_populates="tenant", cascade="all, delete-orphan")
    shifts: Mapped[List["CashShift"]] = relationship("CashShift", back_populates="tenant", cascade="all, delete-orphan")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "outlet_name": self.outlet_name,
            "address": self.address,
            "gstin": self.gstin,
            "fssai": self.fssai,
            "fl3_license": self.fl3_license,
            "vatin": self.vatin,
            "phone": self.phone,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class User(Base):
    """
    Staff accounts with 4-digit PIN authentication for zero-friction POS station switches.
    Roles: OWNER, MANAGER, CASHIER, STOREKEEPER
    """
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # OWNER, MANAGER, CASHIER, STOREKEEPER
    pin_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="users")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "username": self.username,
            "display_name": self.display_name,
            "role": self.role,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ============================================================================
# 2. DINING SECTIONS, TABLES & POS FLOOR PLAN
# ============================================================================

class DiningTable(Base):
    """
    Floor layout dining tables with section categorization and live state tracking.
    Status: OPEN, SEATED, ORDERED, BILLED
    """
    __tablename__ = "dining_tables"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(10), nullable=False, index=True)  # e.g., T1, T2... T16
    section: Mapped[str] = mapped_column(String(50), nullable=False)           # Ground floor, Terrace
    seats: Mapped[int] = mapped_column(Integer, default=4)
    status: Mapped[str] = mapped_column(String(20), default="OPEN", index=True)  # OPEN, SEATED, ORDERED, BILLED
    seated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    guest_count: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="tables")
    orders: Mapped[List["Order"]] = relationship("Order", back_populates="table")

    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_tenant_table_code"),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "code": self.code,
            "section": self.section,
            "seats": self.seats,
            "status": self.status,
            "seated_at": self.seated_at.isoformat() if self.seated_at else None,
            "guest_count": self.guest_count,
        }


# ============================================================================
# 3. MENU, PRICING & TAXATION (GST FOOD vs VAT LIQUOR)
# ============================================================================

class MenuCategory(Base):
    """
    Menu categories representing kitchen/bar stations and default tax classifications.
    Allows dynamic category expansion (e.g. Soups, Seafood, Chinese, Mocktails).
    """
    __tablename__ = "menu_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False, default=1, index=True)
    name: Mapped[str] = mapped_column(String(60), nullable=False, unique=True, index=True)
    department: Mapped[str] = mapped_column(String(30), default="KITCHEN")  # KITCHEN, BAR
    tax_category: Mapped[str] = mapped_column(String(30), default="GST_FOOD")  # GST_FOOD, VAT_ALCOHOL
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "name": self.name,
            "department": self.department,
            "tax_category": self.tax_category,
            "sort_order": self.sort_order,
            "is_active": self.is_active,
        }


class MenuItem(Base):
    """
    Menu catalog with dual tax classification:
    - GST_FOOD (5% composite GST under composition or regular restaurant)
    - VAT_ALCOHOL (Maharashtra State VAT for alcoholic beverages)
    Includes 'is_86' flag for 86'd out-of-stock items.
    """
    __tablename__ = "menu_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    is_veg: Mapped[bool] = mapped_column(Boolean, default=True)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    hsn_code: Mapped[str] = mapped_column(String(20), default="996331")
    tax_category: Mapped[str] = mapped_column(String(20), default="GST_FOOD")  # GST_FOOD, VAT_ALCOHOL
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    is_86: Mapped[bool] = mapped_column(Boolean, default=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="menu_items")
    bom_recipes: Mapped[List["RecipeBOM"]] = relationship("RecipeBOM", back_populates="menu_item", cascade="all, delete-orphan")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "name": self.name,
            "category": self.category,
            "is_veg": self.is_veg,
            "price": self.price,
            "hsn_code": self.hsn_code,
            "tax_category": self.tax_category,
            "is_active": self.is_active,
            "is_86": self.is_86,
            "description": self.description,
        }


# ============================================================================
# 4. ORDER RUNNING SESSIONS & ORDER ITEMS
# ============================================================================

class Order(Base):
    """
    Running dining order session attached to a table or takeaway counter.
    Status: ACTIVE, BILLED, COMPLETED, CANCELLED
    """
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    table_id: Mapped[Optional[int]] = mapped_column(ForeignKey("dining_tables.id"), nullable=True, index=True)
    order_type: Mapped[str] = mapped_column(String(20), default="DINE_IN")  # DINE_IN, TAKEAWAY
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", index=True)  # ACTIVE, BILLED, COMPLETED, CANCELLED
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="orders")
    table: Mapped[Optional["DiningTable"]] = relationship("DiningTable", back_populates="orders")
    items: Mapped[List["OrderItem"]] = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    bills: Mapped[List["Bill"]] = relationship("Bill", back_populates="order")
    tickets: Mapped[List["Ticket"]] = relationship("Ticket", back_populates="order")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "table_id": self.table_id,
            "table_code": self.table.code if self.table else None,
            "order_type": self.order_type,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "items": [item.to_dict() for item in self.items],
        }


class OrderItem(Base):
    """
    Individual dishes or beverages ordered on a running ticket.
    Tracks printing status for KOT (Kitchen) and BOT (Bar Dispense).
    Status: ORDERED, PREPARING, SERVED, VOIDED
    """
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), nullable=False, index=True)
    menu_item_id: Mapped[int] = mapped_column(ForeignKey("menu_items.id"), nullable=False, index=True)
    item_name: Mapped[str] = mapped_column(String(120), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    unit_price: Mapped[float] = mapped_column(Float, nullable=False)
    prep_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_kot_printed: Mapped[bool] = mapped_column(Boolean, default=False)
    is_bot_printed: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(20), default="ORDERED")  # ORDERED, PREPARING, SERVED, VOIDED
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    # Relationships
    order: Mapped["Order"] = relationship("Order", back_populates="items")
    menu_item: Mapped["MenuItem"] = relationship("MenuItem")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "order_id": self.order_id,
            "menu_item_id": self.menu_item_id,
            "item_name": self.item_name,
            "quantity": self.quantity,
            "unit_price": self.unit_price,
            "subtotal": self.quantity * self.unit_price,
            "prep_note": self.prep_note,
            "is_kot_printed": self.is_kot_printed,
            "is_bot_printed": self.is_bot_printed,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ============================================================================
# 5. KOT / BOT ESC/POS TICKETING
# ============================================================================

class Ticket(Base):
    """
    Auditable kitchen and bar production slips printed to network/ESC-POS thermal printers.
    ticket_type: KOT (Kitchen Order Ticket), BOT (Bar Order Ticket)
    """
    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    order_id: Mapped[Optional[int]] = mapped_column(ForeignKey("orders.id"), nullable=True, index=True)
    ticket_number: Mapped[str] = mapped_column(String(30), nullable=False, index=True)  # e.g., KOT-0101, BOT-0042
    ticket_type: Mapped[str] = mapped_column(String(10), nullable=False)                # KOT, BOT
    table_code: Mapped[str] = mapped_column(String(10), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    printed_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    # Relationships
    order: Mapped[Optional["Order"]] = relationship("Order", back_populates="tickets")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "order_id": self.order_id,
            "ticket_number": self.ticket_number,
            "ticket_type": self.ticket_type,
            "table_code": self.table_code,
            "payload": json.loads(self.payload_json) if self.payload_json else {},
            "printed_at": self.printed_at.isoformat() if self.printed_at else None,
        }


# ============================================================================
# 6. BILLING, SPLIT TAXATION (GST + VAT) & SETTLEMENTS
# ============================================================================

class Bill(Base):
    """
    Final tax invoice complying with Indian GST & Maharashtra State Excise VAT:
    - Food taxed under GST (CGST 2.5% + SGST 2.5% = 5%)
    - Alcoholic beverages taxed under MVAT (typically 5% or 10%)
    - Strict gap-free sequential invoice numbering.
    Payment Modes: CASH, UPI, CARD, KHATA
    """
    __tablename__ = "bills"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), nullable=False, unique=True, index=True)
    invoice_number: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    food_subtotal: Mapped[float] = mapped_column(Float, default=0.0)
    food_cgst: Mapped[float] = mapped_column(Float, default=0.0)
    food_sgst: Mapped[float] = mapped_column(Float, default=0.0)
    liquor_subtotal: Mapped[float] = mapped_column(Float, default=0.0)
    liquor_vat: Mapped[float] = mapped_column(Float, default=0.0)
    round_off: Mapped[float] = mapped_column(Float, default=0.0)
    grand_total: Mapped[float] = mapped_column(Float, nullable=False)
    payment_mode: Mapped[str] = mapped_column(String(20), default="CASH")  # CASH, UPI, CARD, KHATA
    payment_status: Mapped[str] = mapped_column(String(20), default="PENDING")  # PAID, PENDING
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="bills")
    order: Mapped["Order"] = relationship("Order", back_populates="bills")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "order_id": self.order_id,
            "invoice_number": self.invoice_number,
            "food_subtotal": self.food_subtotal,
            "food_cgst": self.food_cgst,
            "food_sgst": self.food_sgst,
            "food_tax_total": round(self.food_cgst + self.food_sgst, 2),
            "liquor_subtotal": self.liquor_subtotal,
            "liquor_vat": self.liquor_vat,
            "round_off": self.round_off,
            "grand_total": self.grand_total,
            "payment_mode": self.payment_mode,
            "payment_status": self.payment_status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class InvoiceCounter(Base):
    """
    Tenant-scoped sequential invoice counter per Indian Financial Year (e.g. 2026-27).
    Guarantees gap-free sequential numbers per GSTIN without full table scans or cross-tenant leakage.
    """
    __tablename__ = "invoice_counters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    fin_year: Mapped[str] = mapped_column(String(10), nullable=False)  # e.g. "2026-27"
    last_number: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    __table_args__ = (
        UniqueConstraint("tenant_id", "fin_year", name="uq_tenant_fin_year_invoice"),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "fin_year": self.fin_year,
            "last_number": self.last_number,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


# ============================================================================
# 7. CASH SHIFTS & DRAWER RECONCILIATION
# ============================================================================

class CashShift(Base):
    """
    Cash drawer shift accountability ledger.
    Tracks opening float, cash sales, paid ins/outs, safe drops, and blind count variances.
    """
    __tablename__ = "cash_shifts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    cashier_name: Mapped[str] = mapped_column(String(100), nullable=False)
    opened_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    opening_float: Mapped[float] = mapped_column(Float, default=0.0)
    cash_sales: Mapped[float] = mapped_column(Float, default=0.0)
    paid_in: Mapped[float] = mapped_column(Float, default=0.0)
    paid_out: Mapped[float] = mapped_column(Float, default=0.0)
    safe_drops: Mapped[float] = mapped_column(Float, default=0.0)
    counted_cash: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    variance: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_closed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="shifts")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "cashier_name": self.cashier_name,
            "opened_at": self.opened_at.isoformat() if self.opened_at else None,
            "opening_float": self.opening_float,
            "cash_sales": self.cash_sales,
            "paid_in": self.paid_in,
            "paid_out": self.paid_out,
            "safe_drops": self.safe_drops,
            "expected_cash": round(
                self.opening_float + self.cash_sales + self.paid_in - self.paid_out - self.safe_drops, 2
            ),
            "counted_cash": self.counted_cash,
            "variance": self.variance,
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
            "is_closed": self.is_closed,
        }


# ============================================================================
# 8. TWO-TIER INVENTORY (CENTRAL STORE & KITCHEN LINE)
# ============================================================================

class RawMaterial(Base):
    """
    Inventory catalog item maintaining separation of custody:
    - Central Store Stock: Bulk storage (sack of onions, crates of chicken)
    - Kitchen Line Stock: Working prep stations (daily mise-en-place)
    """
    __tablename__ = "raw_materials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(30), nullable=False)  # PRODUCE, MEAT, GROCERY, DAIRY, PACKAGING
    uom: Mapped[str] = mapped_column(String(10), nullable=False)       # kg, L, pcs, g
    current_store_stock: Mapped[float] = mapped_column(Float, default=0.0)
    current_kitchen_stock: Mapped[float] = mapped_column(Float, default=0.0)
    min_reorder_level: Mapped[float] = mapped_column(Float, default=0.0)
    unit_cost: Mapped[float] = mapped_column(Float, default=0.0)

    # Relationships
    recipe_boms: Mapped[List["RecipeBOM"]] = relationship("RecipeBOM", back_populates="raw_material")
    wastage_logs: Mapped[List["WastageLog"]] = relationship("WastageLog", back_populates="raw_material")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "name": self.name,
            "category": self.category,
            "uom": self.uom,
            "current_store_stock": self.current_store_stock,
            "current_kitchen_stock": self.current_kitchen_stock,
            "total_stock": round(self.current_store_stock + self.current_kitchen_stock, 3),
            "min_reorder_level": self.min_reorder_level,
            "unit_cost": self.unit_cost,
        }


# ============================================================================
# 9. PROCUREMENT: PURCHASE ORDERS & GOODS RECEIVED NOTES (GRN)
# ============================================================================

class PurchaseOrder(Base):
    """Vendor procurement Purchase Order."""
    __tablename__ = "purchase_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    po_number: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    vendor_name: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="DRAFT")  # DRAFT, APPROVED, RECEIVED
    total_amount: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    # Relationships
    items: Mapped[List["PurchaseOrderItem"]] = relationship("PurchaseOrderItem", back_populates="purchase_order", cascade="all, delete-orphan")
    grns: Mapped[List["GoodsReceivedNote"]] = relationship("GoodsReceivedNote", back_populates="purchase_order")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "po_number": self.po_number,
            "vendor_name": self.vendor_name,
            "status": self.status,
            "total_amount": self.total_amount,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "items": [item.to_dict() for item in self.items],
        }


class PurchaseOrderItem(Base):
    """Line items for Purchase Orders."""
    __tablename__ = "purchase_order_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    purchase_order_id: Mapped[int] = mapped_column(ForeignKey("purchase_orders.id"), nullable=False, index=True)
    raw_material_id: Mapped[int] = mapped_column(ForeignKey("raw_materials.id"), nullable=False, index=True)
    ordered_qty: Mapped[float] = mapped_column(Float, nullable=False)
    unit_price: Mapped[float] = mapped_column(Float, nullable=False)

    # Relationships
    purchase_order: Mapped["PurchaseOrder"] = relationship("PurchaseOrder", back_populates="items")
    raw_material: Mapped["RawMaterial"] = relationship("RawMaterial")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "purchase_order_id": self.purchase_order_id,
            "raw_material_id": self.raw_material_id,
            "raw_material_name": self.raw_material.name if self.raw_material else None,
            "ordered_qty": self.ordered_qty,
            "unit_price": self.unit_price,
            "line_total": round(self.ordered_qty * self.unit_price, 2),
        }


class GoodsReceivedNote(Base):
    """Inward dock gate receipt note verifying delivered vendor goods against PO."""
    __tablename__ = "goods_received_notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    grn_number: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    po_id: Mapped[Optional[int]] = mapped_column(ForeignKey("purchase_orders.id"), nullable=True, index=True)
    vendor_invoice_no: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    # Relationships
    purchase_order: Mapped[Optional["PurchaseOrder"]] = relationship("PurchaseOrder", back_populates="grns")
    items: Mapped[List["GRNItem"]] = relationship("GRNItem", back_populates="grn", cascade="all, delete-orphan")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "grn_number": self.grn_number,
            "po_id": self.po_id,
            "vendor_invoice_no": self.vendor_invoice_no,
            "received_at": self.received_at.isoformat() if self.received_at else None,
            "items": [item.to_dict() for item in self.items],
        }


class GRNItem(Base):
    """Batch-level inward stock receipts with expiry dates and invoice verification."""
    __tablename__ = "grn_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    grn_id: Mapped[int] = mapped_column(ForeignKey("goods_received_notes.id"), nullable=False, index=True)
    raw_material_id: Mapped[int] = mapped_column(ForeignKey("raw_materials.id"), nullable=False, index=True)
    batch_no: Mapped[str] = mapped_column(String(50), nullable=False)
    expiry_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    received_qty: Mapped[float] = mapped_column(Float, nullable=False)
    invoice_price: Mapped[float] = mapped_column(Float, nullable=False)

    # Relationships
    grn: Mapped["GoodsReceivedNote"] = relationship("GoodsReceivedNote", back_populates="items")
    raw_material: Mapped["RawMaterial"] = relationship("RawMaterial")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "grn_id": self.grn_id,
            "raw_material_id": self.raw_material_id,
            "raw_material_name": self.raw_material.name if self.raw_material else None,
            "batch_no": self.batch_no,
            "expiry_date": self.expiry_date.isoformat() if self.expiry_date else None,
            "received_qty": self.received_qty,
            "invoice_price": self.invoice_price,
            "line_total": round(self.received_qty * self.invoice_price, 2),
        }


# ============================================================================
# 10. STORE INDENTS (CENTRAL STORE TO KITCHEN LINE TRANSFERS)
# ============================================================================

class StoreIndent(Base):
    """Internal requisition transferring stock from Central Store to Kitchen Line."""
    __tablename__ = "store_indents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    indent_number: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    department: Mapped[str] = mapped_column(String(50), default="Kitchen Line")
    status: Mapped[str] = mapped_column(String(20), default="ISSUED")  # REQUESTED, ISSUED, REJECTED
    issued_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    # Relationships
    items: Mapped[List["StoreIndentItem"]] = relationship("StoreIndentItem", back_populates="indent", cascade="all, delete-orphan")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "indent_number": self.indent_number,
            "department": self.department,
            "status": self.status,
            "issued_at": self.issued_at.isoformat() if self.issued_at else None,
            "items": [item.to_dict() for item in self.items],
        }


class StoreIndentItem(Base):
    """Line items for internal store transfer indents."""
    __tablename__ = "store_indent_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    indent_id: Mapped[int] = mapped_column(ForeignKey("store_indents.id"), nullable=False, index=True)
    raw_material_id: Mapped[int] = mapped_column(ForeignKey("raw_materials.id"), nullable=False, index=True)
    requested_qty: Mapped[float] = mapped_column(Float, nullable=False)
    issued_qty: Mapped[float] = mapped_column(Float, nullable=False)

    # Relationships
    indent: Mapped["StoreIndent"] = relationship("StoreIndent", back_populates="items")
    raw_material: Mapped["RawMaterial"] = relationship("RawMaterial")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "indent_id": self.indent_id,
            "raw_material_id": self.raw_material_id,
            "raw_material_name": self.raw_material.name if self.raw_material else None,
            "requested_qty": self.requested_qty,
            "issued_qty": self.issued_qty,
        }


# ============================================================================
# 11. RECIPE BILL OF MATERIALS (BOM) & KITCHEN CONSUMPTION
# ============================================================================

class RecipeBOM(Base):
    """
    Culinary Bill of Materials mapping each menu dish to raw ingredient portions.
    prep_shrinkage_yield_pct accounts for butcher trimming, peeling, and cooking reduction.
    """
    __tablename__ = "recipe_bom"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    menu_item_id: Mapped[int] = mapped_column(ForeignKey("menu_items.id"), nullable=False, index=True)
    raw_material_id: Mapped[int] = mapped_column(ForeignKey("raw_materials.id"), nullable=False, index=True)
    quantity_required: Mapped[float] = mapped_column(Float, nullable=False)
    prep_shrinkage_yield_pct: Mapped[float] = mapped_column(Float, default=100.0)

    # Relationships
    menu_item: Mapped["MenuItem"] = relationship("MenuItem", back_populates="bom_recipes")
    raw_material: Mapped["RawMaterial"] = relationship("RawMaterial", back_populates="recipe_boms")

    __table_args__ = (
        UniqueConstraint("menu_item_id", "raw_material_id", name="uq_recipe_dish_material"),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "menu_item_id": self.menu_item_id,
            "dish_name": self.menu_item.name if self.menu_item else None,
            "raw_material_id": self.raw_material_id,
            "ingredient_name": self.raw_material.name if self.raw_material else None,
            "quantity_required": self.quantity_required,
            "uom": self.raw_material.uom if self.raw_material else None,
            "prep_shrinkage_yield_pct": self.prep_shrinkage_yield_pct,
        }


# ============================================================================
# 12. KITCHEN WASTAGE & SPOILAGE LOGS
# ============================================================================

class WastageLog(Base):
    """
    Wastage logging capturing write-offs with mandatory authorization.
    Reason codes: BURNT, DROPPED, EXPIRED, TRIM
    """
    __tablename__ = "wastage_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    raw_material_id: Mapped[int] = mapped_column(ForeignKey("raw_materials.id"), nullable=False, index=True)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    reason_code: Mapped[str] = mapped_column(String(20), nullable=False)  # BURNT, DROPPED, EXPIRED, TRIM
    authorized_by: Mapped[str] = mapped_column(String(100), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    # Relationships
    raw_material: Mapped["RawMaterial"] = relationship("RawMaterial", back_populates="wastage_logs")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "raw_material_id": self.raw_material_id,
            "material_name": self.raw_material.name if self.raw_material else None,
            "quantity": self.quantity,
            "uom": self.raw_material.uom if self.raw_material else None,
            "reason_code": self.reason_code,
            "authorized_by": self.authorized_by,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ============================================================================
# 13. LIQUOR BAR & MAHARASHTRA STATE EXCISE FLR-3A COMPLIANCE
# ============================================================================

class LiquorBrand(Base):
    """
    Statutory liquor master tracked for State Excise FL-3 regulations.
    Maintains both sealed bottles count and open bottle running volume in ml.
    """
    __tablename__ = "liquor_brands"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    brand_name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(30), nullable=False)  # IMFL_WHISKY, BEER_MILD, WINE, RUM, etc.
    bottle_size_ml: Mapped[int] = mapped_column(Integer, nullable=False)  # 750, 650, 330
    state_excise_code: Mapped[str] = mapped_column(String(50), nullable=False)
    mrp: Mapped[float] = mapped_column(Float, nullable=False)
    vat_percent: Mapped[float] = mapped_column(Float, default=10.0)
    sealed_bottles: Mapped[int] = mapped_column(Integer, default=0)
    open_bottle_ml: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    daily_registers: Mapped[List["DailyExciseFLR3A"]] = relationship("DailyExciseFLR3A", back_populates="brand")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "brand_name": self.brand_name,
            "category": self.category,
            "bottle_size_ml": self.bottle_size_ml,
            "state_excise_code": self.state_excise_code,
            "mrp": self.mrp,
            "vat_percent": self.vat_percent,
            "sealed_bottles": self.sealed_bottles,
            "open_bottle_ml": self.open_bottle_ml,
            "total_ml": (self.sealed_bottles * self.bottle_size_ml) + self.open_bottle_ml,
        }


class LiquorTransportPermit(Base):
    """
    Official Maharashtra State Excise Inward Transport Permit (TP).
    Legal proof of inward liquor consignments received at the bar.
    """
    __tablename__ = "liquor_transport_permits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    tp_number: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    tp_date: Mapped[date] = mapped_column(Date, nullable=False)
    supplier_name: Mapped[str] = mapped_column(String(120), nullable=False)
    vehicle_no: Mapped[str] = mapped_column(String(30), nullable=False)
    invoice_no: Mapped[str] = mapped_column(String(50), nullable=False)
    total_cases: Mapped[int] = mapped_column(Integer, default=0)
    total_bottles: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "tp_number": self.tp_number,
            "tp_date": self.tp_date.isoformat() if self.tp_date else None,
            "supplier_name": self.supplier_name,
            "vehicle_no": self.vehicle_no,
            "invoice_no": self.invoice_no,
            "total_cases": self.total_cases,
            "total_bottles": self.total_bottles,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class DailyExciseFLR3A(Base):
    """
    Daily statutory Maharashtra State Excise Form F.L.R.-3A register.
    Mandatory balance equation verified daily:
    Opening + TP Receipts - Sales(ml) - Breakage(ml) == Closing Stock
    """
    __tablename__ = "daily_excise_flr3a"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    register_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    brand_id: Mapped[int] = mapped_column(ForeignKey("liquor_brands.id"), nullable=False, index=True)
    opening_sealed: Mapped[int] = mapped_column(Integer, default=0)
    opening_open_ml: Mapped[int] = mapped_column(Integer, default=0)
    tp_received_bottles: Mapped[int] = mapped_column(Integer, default=0)
    sales_ml: Mapped[int] = mapped_column(Integer, default=0)
    breakage_ml: Mapped[int] = mapped_column(Integer, default=0)
    closing_sealed: Mapped[int] = mapped_column(Integer, default=0)
    closing_open_ml: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    brand: Mapped["LiquorBrand"] = relationship("LiquorBrand", back_populates="daily_registers")

    __table_args__ = (
        UniqueConstraint("register_date", "brand_id", name="uq_excise_date_brand"),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "register_date": self.register_date.isoformat() if self.register_date else None,
            "brand_id": self.brand_id,
            "brand_name": self.brand.brand_name if self.brand else None,
            "opening_sealed": self.opening_sealed,
            "opening_open_ml": self.opening_open_ml,
            "tp_received_bottles": self.tp_received_bottles,
            "sales_ml": self.sales_ml,
            "breakage_ml": self.breakage_ml,
            "closing_sealed": self.closing_sealed,
            "closing_open_ml": self.closing_open_ml,
        }


# ============================================================================
# 14. CASH DRAWER, FRAUD PREVENTION & SYSTEM AUDIT LOG
# ============================================================================

class AuditLog(Base):
    """
    Immutable audit trail for high-risk operations.
    Action Types: DRAWER_KICK_MANUAL, VOID_KOT, DISCOUNT_MANUAL, RATE_CHANGE, etc.
    """
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    staff_name: Mapped[str] = mapped_column(String(100), nullable=False)
    action_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    details_json: Mapped[str] = mapped_column(Text, nullable=False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "staff_name": self.staff_name,
            "action_type": self.action_type,
            "details": json.loads(self.details_json) if self.details_json else {},
        }
