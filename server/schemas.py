"""
RestoOS Production Pydantic v2 Data Schemas & Validation Contracts
Comprehensive schemas for Tables, Orders, Dual-Tax Billing, Thermal Printing,
Shift Balancing, Two-Tier Inventory, Maharashtra State Excise FLR-3A, and Owner BI.
"""

from datetime import datetime, date
from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field, ConfigDict


# ============================================================================
# BASE SCHEMA CONFIGURATION
# ============================================================================

class SchemaBase(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )


# ============================================================================
# 1. TENANCY & USERS (RBAC)
# ============================================================================

class TenantResponse(SchemaBase):
    id: int
    name: str
    outlet_name: str
    address: str
    gstin: str
    fssai: str
    fl3_license: str
    vatin: str
    phone: str
    created_at: Optional[datetime] = None


class TenantUpdate(SchemaBase):
    name: Optional[str] = None
    outlet_name: Optional[str] = None
    address: Optional[str] = None
    gstin: Optional[str] = None
    fssai: Optional[str] = None
    fl3_license: Optional[str] = None
    vatin: Optional[str] = None
    phone: Optional[str] = None


class UserAuthRequest(SchemaBase):
    username: str
    pin: str = Field(min_length=4, max_length=6)


class UserResponse(SchemaBase):
    id: int
    tenant_id: int
    username: str
    display_name: str
    role: str
    is_active: bool
    created_at: Optional[datetime] = None


# ============================================================================
# 2. DINING TABLES & FLOOR PLAN
# ============================================================================

class TableSeatRequest(SchemaBase):
    guest_count: int = Field(default=2, ge=1, le=50)


class TableGuestCountUpdate(SchemaBase):
    guest_count: int = Field(ge=0, le=50)


class TableResponse(SchemaBase):
    id: int
    tenant_id: int
    code: str
    section: str
    seats: int
    status: str  # OPEN, SEATED, ORDERED, BILLED
    seated_at: Optional[datetime] = None
    guest_count: int
    elapsed_minutes: Optional[int] = None
    active_order_id: Optional[int] = None
    current_bill_id: Optional[int] = None


class TablesGroupedResponse(SchemaBase):
    sections: Dict[str, List[TableResponse]]
    total_tables: int
    occupied_tables: int
    open_tables: int


# ============================================================================
# 3. MENU ITEMS
# ============================================================================

class MenuItemResponse(SchemaBase):
    id: int
    tenant_id: int
    name: str
    category: str
    is_veg: bool
    price: float
    hsn_code: str
    tax_category: str  # GST_FOOD, VAT_ALCOHOL
    is_active: bool
    is_86: bool
    description: Optional[str] = None


class MenuCategoryCreate(SchemaBase):
    name: str
    department: Optional[str] = "KITCHEN"
    tax_category: Optional[str] = "GST_FOOD"
    sort_order: Optional[int] = 0


class MenuCategoryResponse(SchemaBase):
    id: int
    name: str
    department: str
    tax_category: str
    sort_order: int
    is_active: bool
    item_count: int = 0


class MenuItemUpdate86(SchemaBase):
    is_86: bool


class MenuItemCreate(SchemaBase):
    name: str
    category: str
    is_veg: bool = True
    price: float = Field(ge=0)
    hsn_code: Optional[str] = "996331"
    tax_category: Optional[str] = "GST_FOOD"
    is_active: Optional[bool] = True
    is_86: Optional[bool] = False
    description: Optional[str] = None


class MenuItemUpdate(SchemaBase):
    name: Optional[str] = None
    category: Optional[str] = None
    is_veg: Optional[bool] = None
    price: Optional[float] = Field(default=None, ge=0)
    hsn_code: Optional[str] = None
    tax_category: Optional[str] = None
    is_active: Optional[bool] = None
    is_86: Optional[bool] = None
    description: Optional[str] = None


# ============================================================================
# 4. ORDERS & ORDER ITEMS
# ============================================================================

class OrderItemCreate(SchemaBase):
    menu_item_id: int
    quantity: int = Field(default=1, ge=1)
    prep_note: Optional[str] = None


class OrderItemUpdate(SchemaBase):
    quantity: Optional[int] = Field(default=None, ge=1)
    prep_note: Optional[str] = None
    status: Optional[str] = None  # ORDERED, PREPARING, SERVED, VOIDED


class OrderCreate(SchemaBase):
    table_id: Optional[int] = None
    table_code: Optional[str] = None
    order_type: str = "DINE_IN"  # DINE_IN, TAKEAWAY
    items: List[OrderItemCreate] = []


class OrderItemResponse(SchemaBase):
    id: int
    order_id: int
    menu_item_id: int
    item_name: str
    quantity: int
    unit_price: float
    subtotal: float
    prep_note: Optional[str] = None
    is_kot_printed: bool
    is_bot_printed: bool
    status: str
    created_at: Optional[datetime] = None
    is_veg: Optional[bool] = None
    tax_category: Optional[str] = None


class OrderResponse(SchemaBase):
    id: int
    tenant_id: int
    table_id: Optional[int] = None
    table_code: Optional[str] = None
    order_type: str
    status: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    items: List[OrderItemResponse] = []
    total_amount: float = 0.0


# ============================================================================
# 5. KOT / BOT DISPATCH & TICKETING
# ============================================================================

class TicketResponse(SchemaBase):
    id: int
    tenant_id: int
    order_id: Optional[int] = None
    ticket_number: str
    ticket_type: str  # KOT, BOT
    table_code: str
    payload: Dict[str, Any]
    printed_at: Optional[datetime] = None
    raw_escpos_text: str


class FireKOTBOTRequest(SchemaBase):
    order_id: int


class FireKOTBOTResponse(SchemaBase):
    kot_ticket: Optional[TicketResponse] = None
    bot_ticket: Optional[TicketResponse] = None
    kot_text_80mm: Optional[str] = None
    bot_text_80mm: Optional[str] = None
    items_fired_count: int = 0
    message: str


# ============================================================================
# 6. BILLING & DUAL-TAX (GST + VAT) SETTLEMENT
# ============================================================================

class BillCalculationResponse(SchemaBase):
    order_id: int
    table_code: Optional[str] = None
    food_subtotal: float
    food_cgst: float
    food_sgst: float
    food_tax_total: float
    liquor_subtotal: float
    liquor_vat: float
    liquor_tax_total: float
    subtotal_combined: float
    total_tax: float
    round_off: float
    grand_total: float
    items_breakdown: List[Dict[str, Any]]


class BillSettleCartItem(SchemaBase):
    item_id: int
    name: Optional[str] = None
    quantity: float = 1.0
    unit_price: float
    notes: Optional[str] = None
    tax_category: Optional[str] = "GST_FOOD"


class BillSettleRequest(SchemaBase):
    order_id: Optional[int] = None
    table_id: Optional[int] = None
    table_code: Optional[str] = None
    items: Optional[List[BillSettleCartItem]] = None
    payment_mode: str = "CASH"  # CASH, UPI, CARD, KHATA
    amount_paid: Optional[float] = None
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    staff_name: str = "Cashier 1"


class BillResponse(SchemaBase):
    id: int
    tenant_id: int
    order_id: int
    invoice_number: str
    food_subtotal: float
    food_cgst: float
    food_sgst: float
    food_tax_total: float
    liquor_subtotal: float
    liquor_vat: float
    round_off: float
    grand_total: float
    payment_mode: str
    payment_status: str
    created_at: Optional[datetime] = None


class BillSettleResponse(SchemaBase):
    bill: BillResponse
    drawer_kick_command_hex: Optional[str] = None
    tax_invoice_80mm_text: str
    table_status_now: str
    message: str


# ============================================================================
# 7. CASH SHIFTS & DRAWER RECONCILIATION
# ============================================================================

class ShiftOpenRequest(SchemaBase):
    cashier_name: str
    opening_float: float = Field(default=0.0, ge=0.0)


class PettyCashRequest(SchemaBase):
    amount: float = Field(gt=0.0)
    voucher_type: str = "PAID_OUT"  # PAID_IN, PAID_OUT
    reason: str
    staff_name: str = "Cashier 1"


class SafeDropRequest(SchemaBase):
    amount: float = Field(gt=0.0)
    manager_pin: str
    notes: Optional[str] = None


class ShiftCloseRequest(SchemaBase):
    counted_cash: float = Field(ge=0.0)


class CashShiftResponse(SchemaBase):
    id: int
    tenant_id: int
    cashier_name: str
    opened_at: Optional[datetime] = None
    opening_float: float
    cash_sales: float
    paid_in: float
    paid_out: float
    safe_drops: float
    expected_cash: float
    counted_cash: Optional[float] = None
    variance: Optional[float] = None
    closed_at: Optional[datetime] = None
    is_closed: bool


class ZReportResponse(SchemaBase):
    shift_id: int
    cashier_name: str
    opened_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    opening_float: float
    cash_sales: float
    card_sales: float
    upi_sales: float
    khata_sales: float
    gross_sales: float
    net_sales: float
    total_tax_collected: float
    paid_in: float
    paid_out: float
    safe_drops: float
    expected_in_drawer: float
    counted_cash: float
    variance: float
    status: str
    z_report_80mm_text: str


# ============================================================================
# 8. TWO-TIER INVENTORY (STORE & KITCHEN LINE)
# ============================================================================

class RawMaterialResponse(SchemaBase):
    id: int
    tenant_id: int
    name: str
    category: str
    uom: str
    current_store_stock: float
    current_kitchen_stock: float
    total_stock: float
    min_reorder_level: float
    unit_cost: float
    is_low_stock: bool


class PurchaseOrderItemCreate(SchemaBase):
    raw_material_id: int
    ordered_qty: float = Field(gt=0.0)
    unit_price: float = Field(ge=0.0)


class PurchaseOrderCreate(SchemaBase):
    vendor_name: str
    items: List[PurchaseOrderItemCreate]


class PurchaseOrderResponse(SchemaBase):
    id: int
    tenant_id: int
    po_number: str
    vendor_name: str
    status: str
    total_amount: float
    created_at: Optional[datetime] = None
    items: List[Dict[str, Any]] = []


class GRNItemCreate(SchemaBase):
    raw_material_id: int
    batch_no: str
    expiry_date: Optional[date] = None
    received_qty: float = Field(gt=0.0)
    invoice_price: float = Field(ge=0.0)


class GRNCreateRequest(SchemaBase):
    po_id: Optional[int] = None
    vendor_invoice_no: Optional[str] = None
    items: List[GRNItemCreate]


class GRNResponse(SchemaBase):
    id: int
    tenant_id: int
    grn_number: str
    po_id: Optional[int] = None
    vendor_invoice_no: Optional[str] = None
    received_at: Optional[datetime] = None
    items: List[Dict[str, Any]] = []


class StoreIndentItemCreate(SchemaBase):
    raw_material_id: int
    requested_qty: float = Field(gt=0.0)
    issued_qty: Optional[float] = None


class StoreIndentCreate(SchemaBase):
    department: str = "Kitchen Line"
    items: List[StoreIndentItemCreate]


class StoreIndentResponse(SchemaBase):
    id: int
    tenant_id: int
    indent_number: str
    department: str
    status: str
    issued_at: Optional[datetime] = None
    items: List[Dict[str, Any]] = []


class WastageLogCreate(SchemaBase):
    raw_material_id: int
    quantity: float = Field(gt=0.0)
    reason_code: str  # BURNT, DROPPED, EXPIRED, TRIM
    supervisor_pin: str
    notes: Optional[str] = None


class WastageLogResponse(SchemaBase):
    id: int
    tenant_id: int
    raw_material_id: int
    material_name: Optional[str] = None
    quantity: float
    uom: Optional[str] = None
    reason_code: str
    authorized_by: str
    notes: Optional[str] = None
    created_at: Optional[datetime] = None


class RecipeBOMCreate(SchemaBase):
    menu_item_id: int
    raw_material_id: int
    quantity_required: float = Field(gt=0.0)
    prep_shrinkage_yield_pct: float = Field(default=100.0, gt=0.0)


class RecipeBOMResponse(SchemaBase):
    id: int
    menu_item_id: int
    dish_name: Optional[str] = None
    raw_material_id: int
    ingredient_name: Optional[str] = None
    quantity_required: float
    uom: Optional[str] = None
    prep_shrinkage_yield_pct: float


class Live86Item(SchemaBase):
    menu_item_id: int
    menu_item_name: str
    category: str
    is_86: bool
    bottleneck_ingredient: Optional[str] = None
    kitchen_stock_available: float = 0.0
    portions_possible: float = 0.0


class Live86Response(SchemaBase):
    items: List[Live86Item]
    total_86_count: int


# ============================================================================
# 9. LIQUOR BAR & MAHARASHTRA STATE EXCISE FLR-3A
# ============================================================================

class LiquorBrandResponse(SchemaBase):
    id: int
    tenant_id: int
    brand_name: str
    category: str
    bottle_size_ml: int
    state_excise_code: str
    mrp: float
    vat_percent: float
    sealed_bottles: int
    open_bottle_ml: int
    total_ml: int


class LiquorTPItemCreate(SchemaBase):
    brand_id: int
    cases: int = Field(ge=0)
    bottles: int = Field(ge=0)


class LiquorTPCreate(SchemaBase):
    tp_number: str
    tp_date: date
    supplier_name: str
    vehicle_no: str
    invoice_no: str
    total_cases: int = 0
    total_bottles: int = 0
    items: Optional[List[LiquorTPItemCreate]] = None


class LiquorTPResponse(SchemaBase):
    id: int
    tenant_id: int
    tp_number: str
    tp_date: date
    supplier_name: str
    vehicle_no: str
    invoice_no: str
    total_cases: int
    total_bottles: int
    created_at: Optional[datetime] = None


class DailyFLR3AEntry(SchemaBase):
    id: Optional[int] = None
    brand_id: int
    brand_name: str
    category: str
    bottle_size_ml: int
    state_excise_code: str
    opening_sealed: int
    opening_open_ml: int
    tp_received_bottles: int
    sales_ml: int
    breakage_ml: int
    closing_sealed: int
    closing_open_ml: int
    balance_verified: bool = True


class DailyFLR3ARegisterResponse(SchemaBase):
    register_date: date
    total_brands: int
    rows: List[DailyFLR3AEntry]


class FLR4CategorySummary(SchemaBase):
    category: str
    opening_sealed: int
    received_sealed: int
    sales_bottles_equivalent: float
    breakage_bottles_equivalent: float
    closing_sealed: int


class FLR4MonthlyAbstractResponse(SchemaBase):
    month: int
    year: int
    month_name: str
    total_active_brands: int
    categories: List[FLR4CategorySummary]


class DryDayStatusResponse(SchemaBase):
    is_dry_day: bool
    date: date
    reason: Optional[str] = None
    liquor_sale_permitted: bool


# ============================================================================
# 10. OWNER DASHBOARD & RESTO INTELLIGENCE
# ============================================================================

class DashboardKPIs(SchemaBase):
    gross_sales_today: float
    net_sales_today: float
    total_orders_today: int
    covers_today: int
    arpt: float  # Average Revenue Per Table
    average_turn_time_mins: float
    cash_in_drawer: float
    pending_upi: float
    total_tax_collected: float
    food_cgst_sgst: float
    liquor_vat: float


class HourlySalesHeatmapItem(SchemaBase):
    hour: int
    hour_label: str
    order_count: int
    sales_amount: float


class AvTVarianceItem(SchemaBase):
    raw_material_id: int
    ingredient_name: str
    uom: str
    theoretical_usage: float
    actual_usage: float
    variance: float
    variance_pct: float
    cost_variance: float
    status: str  # NORMAL, WATCH, CRITICAL


class BCGMatrixItem(SchemaBase):
    menu_item_id: int
    dish_name: str
    category: str
    volume_sold: int
    profit_margin: float
    revenue: float
    quadrant: str  # Star, Plowhorse, Puzzle, Dog


class BCGMatrixResponse(SchemaBase):
    stars: List[BCGMatrixItem]
    plowhorses: List[BCGMatrixItem]
    puzzles: List[BCGMatrixItem]
    dogs: List[BCGMatrixItem]


class AuditGlanceResponse(SchemaBase):
    suspicious_voids: List[Dict[str, Any]]
    excessive_discounts: List[Dict[str, Any]]
    manual_drawer_kicks: List[Dict[str, Any]]
    recent_events: List[Dict[str, Any]]
    total_flagged: int


class RestoIntelligenceRequest(SchemaBase):
    query: str


class RestoIntelligenceResponse(SchemaBase):
    query: str
    intent: str
    answer: str
    data: Optional[Any] = None
    sql_executed: Optional[str] = None


# ============================================================================
# 11. AUDIT LOGS
# ============================================================================

class AuditLogCreate(SchemaBase):
    staff_name: str
    action_type: str  # DRAWER_KICK_MANUAL, VOID_KOT, DISCOUNT_MANUAL, RATE_CHANGE, etc.
    details: Dict[str, Any]


class AuditLogResponse(SchemaBase):
    id: int
    tenant_id: int
    timestamp: Optional[datetime] = None
    staff_name: str
    action_type: str
    details: Dict[str, Any]
