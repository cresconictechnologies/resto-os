"""
RestoOS ESC/POS Thermal Printing & Hardware Interfacing Utility
Generates statutory 80mm (42-48 column) formatted receipts, KOT/BOT tickets,
and raw ESC/POS hardware control bytes (Cash Drawer Kick, Paper Cut).
"""

from datetime import datetime
from typing import List, Dict, Any, Optional

# ESC/POS Hardware Control Codes
ESC = "\x1b"
GS = "\x1d"

# 24V Solenoid RJ-12 Cash Drawer Kick Pulse: ESC p m t1 t2
# m = 0 (pin 2), t1 = 25 (50ms on), t2 = 250 (500ms off) -> \x1b\x70\x00\x19\xfa
DRAWER_KICK_BYTES = b"\x1b\x70\x00\x19\xfa"
DRAWER_KICK_HEX = "1b700019fa"

# Paper Feed & Full/Partial Cut
CUT_PAPER_BYTES = b"\x1d\x56\x41\x03"

LINE_WIDTH = 42  # Standard 80mm font A column width


def format_divider(char: str = "-") -> str:
    """Returns a full-width receipt separator line."""
    return char * LINE_WIDTH


def format_center(text: str, width: int = LINE_WIDTH) -> str:
    """Centers text within receipt line width."""
    return text.center(width)


def format_lr(left: str, right: str, width: int = LINE_WIDTH) -> str:
    """Formats a two-column line with left-aligned and right-aligned text."""
    space_len = max(1, width - len(left) - len(right))
    return f"{left}{' ' * space_len}{right}"


def generate_kot_bot_80mm(
    ticket_type: str,  # 'KOT' or 'BOT'
    ticket_number: str,
    table_code: str,
    items: List[Dict[str, Any]],
    server_name: str = "Captain",
    timestamp: Optional[datetime] = None,
) -> str:
    """
    Renders standard 80mm Kitchen/Bar Order Ticket (KOT/BOT).
    Station headers, double-width table code, dish line items, prep notes.
    """
    now = timestamp or datetime.now()
    header_title = "KITCHEN ORDER TICKET (KOT)" if ticket_type == "KOT" else "BAR ORDER TICKET (BOT)"
    station = "KITCHEN DISPENSE" if ticket_type == "KOT" else "BAR DISPENSE"

    lines = [
        format_divider("="),
        format_center(f"*** {header_title} ***"),
        format_center(f"Station: {station}"),
        format_divider("="),
        format_lr(f"Ticket: {ticket_number}", f"Date: {now.strftime('%d-%b-%Y')}"),
        format_lr(f"Table : [ {table_code} ]", f"Time: {now.strftime('%H:%M:%S')}"),
        format_lr(f"Server: {server_name}", f"Status: NEW ORDER"),
        format_divider("-"),
        f"{'QTY':<5} {'ITEM NAME':<26} {'ST'}".ljust(LINE_WIDTH),
        format_divider("-"),
    ]

    for item in items:
        qty_str = f" {item.get('quantity', 1)}x"
        name = item.get("item_name", "")[:24]
        lines.append(f"{qty_str:<5} {name:<26}")
        prep_note = item.get("prep_note")
        if prep_note:
            lines.append(f"      ** NOTE: {prep_note[:32]} **")

    lines.extend([
        format_divider("="),
        format_center(f"Total Fired Items: {sum(it.get('quantity', 1) for it in items)}"),
        format_divider("="),
        "\n\n",  # Paper feed space for tear bar
    ])

    return "\n".join(lines)


def generate_tax_invoice_80mm(
    tenant_info: Dict[str, Any],
    invoice_number: str,
    table_code: str,
    guest_count: int,
    order_type: str,
    food_items: List[Dict[str, Any]],
    liquor_items: List[Dict[str, Any]],
    food_subtotal: float,
    food_cgst: float,
    food_sgst: float,
    liquor_subtotal: float,
    liquor_vat: float,
    round_off: float,
    grand_total: float,
    payment_mode: str,
    cashier_name: str = "Cashier 1",
    timestamp: Optional[datetime] = None,
) -> str:
    """
    Renders statutory Indian Restaurant Tax Invoice (80mm Thermal Receipt).
    Includes Outlet details, GSTIN, FSSAI, FL-3, Part A Food (CGST+SGST),
    Part B Liquor (MVAT), and payment tender details.
    """
    now = timestamp or datetime.now()

    lines = [
        format_center(tenant_info.get("outlet_name", "RASA SAHYADRI").upper()),
        format_center(tenant_info.get("name", "Sahyadri Heritage Foods LLP")),
        format_center(tenant_info.get("address", "Koregaon Park, Pune - 411001")[:LINE_WIDTH]),
        format_center(f"Phone: {tenant_info.get('phone', '020-26123456')}"),
        format_divider("-"),
        format_center("TAX INVOICE"),
        format_center(f"GSTIN: {tenant_info.get('gstin', '27AAKFR4621M1Z5')}"),
        format_center(f"FSSAI Lic: {tenant_info.get('fssai', '11523034000412')}"),
    ]

    fl3 = tenant_info.get("fl3_license")
    if fl3 and (liquor_subtotal > 0 or liquor_items):
        lines.append(format_center(f"Excise FL-3: {fl3}"))
        vatin = tenant_info.get("vatin")
        if vatin:
            lines.append(format_center(f"VAT TIN: {vatin}"))

    lines.extend([
        format_divider("="),
        format_lr(f"Invoice: {invoice_number}", f"Date: {now.strftime('%d/%m/%y')}"),
        format_lr(f"Table  : {table_code} ({order_type})", f"Time: {now.strftime('%H:%M')}"),
        format_lr(f"Cashier: {cashier_name}", f"Covers: {guest_count}"),
        format_divider("-"),
        f"{'ITEM':<22} {'QTY':<4} {'RATE':<7} {'AMOUNT':>7}",
        format_divider("-"),
    ])

    # Part A: Food & Beverages (GST)
    if food_items:
        lines.append("[ PART A: FOOD & NON-ALC (GST 5%) ]")
        for item in food_items:
            name = item.get("item_name", "")[:20]
            qty = item.get("quantity", 1)
            rate = item.get("unit_price", 0.0)
            amt = qty * rate
            lines.append(f"{name:<22} {qty:<4} {rate:>6.1f} {amt:>7.2f}")
        lines.append(format_lr("Food Subtotal:", f"{food_subtotal:>8.2f}"))
        lines.append(format_lr("CGST @ 2.5%:", f"{food_cgst:>8.2f}"))
        lines.append(format_lr("SGST @ 2.5%:", f"{food_sgst:>8.2f}"))
        lines.append(format_divider("-"))

    # Part B: Liquor & Spirits (State VAT)
    if liquor_items:
        lines.append("[ PART B: LIQUOR (MVAT 5%) ]")
        for item in liquor_items:
            name = item.get("item_name", "")[:20]
            qty = item.get("quantity", 1)
            rate = item.get("unit_price", 0.0)
            amt = qty * rate
            lines.append(f"{name:<22} {qty:<4} {rate:>6.1f} {amt:>7.2f}")
        lines.append(format_lr("Liquor Subtotal:", f"{liquor_subtotal:>8.2f}"))
        lines.append(format_lr("MVAT @ 5.0%:", f"{liquor_vat:>8.2f}"))
        lines.append(format_divider("-"))

    # Totals & Settlement
    if round_off != 0.0:
        lines.append(format_lr("Round Off:", f"{round_off:>+8.2f}"))

    lines.extend([
        format_divider("="),
        format_lr("GRAND TOTAL:", f"INR {grand_total:>9.2f}"),
        format_divider("="),
        format_lr(f"Payment Mode: {payment_mode}", "Status: PAID"),
        format_divider("-"),
        format_center("Tax Summary (Statutory)"),
        format_lr(f"CGST (2.5%) on Food Rs.{food_subtotal:.2f}:", f"Rs.{food_cgst:.2f}"),
        format_lr(f"SGST (2.5%) on Food Rs.{food_subtotal:.2f}:", f"Rs.{food_sgst:.2f}"),
    ])

    if liquor_subtotal > 0:
        lines.append(format_lr(f"MVAT (5.0%) on Liquor Rs.{liquor_subtotal:.2f}:", f"Rs.{liquor_vat:.2f}"))

    lines.extend([
        format_divider("-"),
        format_center("Thank You For Dining With Us!"),
        format_center("Visit Again! Rasa Sahyadri Pune"),
        "\n\n",
    ])

    return "\n".join(lines)


def generate_z_report_80mm(shift_data: Dict[str, Any]) -> str:
    """Renders 80mm End-of-Shift Blind Close Z-Report."""
    lines = [
        format_divider("="),
        format_center("END OF SHIFT Z-REPORT"),
        format_center("RestoOS Cash Drawer Balancing"),
        format_divider("="),
        format_lr(f"Shift ID : #{shift_data.get('shift_id')}", f"Status: CLOSED"),
        format_lr(f"Cashier  : {shift_data.get('cashier_name')}", ""),
        format_lr(f"Opened   : {str(shift_data.get('opened_at'))[:16]}", ""),
        format_lr(f"Closed   : {str(shift_data.get('closed_at'))[:16]}", ""),
        format_divider("-"),
        format_center("SALES BREAKDOWN BY TENDER"),
        format_divider("-"),
        format_lr("Cash Sales:", f"Rs. {shift_data.get('cash_sales', 0):>8.2f}"),
        format_lr("UPI Sales:", f"Rs. {shift_data.get('upi_sales', 0):>8.2f}"),
        format_lr("Card Sales:", f"Rs. {shift_data.get('card_sales', 0):>8.2f}"),
        format_lr("Khata / Ledger:", f"Rs. {shift_data.get('khata_sales', 0):>8.2f}"),
        format_divider("-"),
        format_lr("GROSS SALES:", f"Rs. {shift_data.get('gross_sales', 0):>8.2f}"),
        format_lr("NET TAX:", f"Rs. {shift_data.get('total_tax_collected', 0):>8.2f}"),
        format_divider("-"),
        format_center("CASH DRAWER RECONCILIATION"),
        format_divider("-"),
        format_lr("Opening Float:", f"Rs. {shift_data.get('opening_float', 0):>8.2f}"),
        format_lr("(+) Cash Sales:", f"Rs. {shift_data.get('cash_sales', 0):>8.2f}"),
        format_lr("(+) Paid In:", f"Rs. {shift_data.get('paid_in', 0):>8.2f}"),
        format_lr("(-) Paid Out:", f"Rs. {shift_data.get('paid_out', 0):>8.2f}"),
        format_lr("(-) Safe Drops:", f"Rs. {shift_data.get('safe_drops', 0):>8.2f}"),
        format_divider("-"),
        format_lr("EXPECTED IN DRAWER:", f"Rs. {shift_data.get('expected_in_drawer', 0):>8.2f}"),
        format_lr("COUNTED CASH (BLIND):", f"Rs. {shift_data.get('counted_cash', 0):>8.2f}"),
        format_divider("="),
    ]

    var = shift_data.get("variance", 0.0)
    var_label = "EXACT MATCH (BALANCED)" if var == 0 else ("SHORTAGE" if var < 0 else "OVERAGE")
    lines.append(format_lr(f"VARIANCE ({var_label}):", f"Rs. {var:>+8.2f}"))
    lines.extend([
        format_divider("="),
        format_center("Cashier Signature: _______________"),
        format_center("Manager Signature: _______________"),
        "\n\n",
    ])
    return "\n".join(lines)
