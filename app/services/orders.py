"""Order calculation and persistence helpers."""

from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Order, OrderItem, SplitPayment


@dataclass
class CartLine:
    """A menu item held in the current in-memory cart."""

    menu_item_id: int
    item_name: str
    unit_price: float
    quantity: int = 1
    note: str | None = None


@dataclass
class Discount:
    """The one optional discount applied to an order."""

    kind: str
    value: float
    scope: str = "order"
    menu_item_id: int | None = None


def calculate_order_totals(
    lines: list[CartLine],
    discount: Discount | None = None,
) -> tuple[float, float, float]:
    """Return subtotal, discount amount, and final total for cart lines."""
    if not lines or any(line.quantity <= 0 for line in lines):
        raise ValueError("An order must contain at least one item.")

    subtotal = round(sum(line.unit_price * line.quantity for line in lines), 2)
    if discount is None:
        return subtotal, 0.0, subtotal

    if discount.kind not in {"flat", "percentage"}:
        raise ValueError("Unknown discount type.")
    if discount.scope not in {"order", "item"}:
        raise ValueError("Unknown discount scope.")
    if discount.value < 0:
        raise ValueError("Discount cannot be negative.")

    discount_base = subtotal
    if discount.scope == "item":
        line = next((line for line in lines if line.menu_item_id == discount.menu_item_id), None)
        if line is None:
            raise ValueError("Discounted item is not in the cart.")
        discount_base = round(line.unit_price * line.quantity, 2)

    if discount.kind == "flat":
        discount_amount = round(discount.value, 2)
    else:
        discount_amount = round(discount_base * discount.value / 100, 2)

    if discount_amount > discount_base:
        raise ValueError("Discount cannot exceed the bill value.")

    return subtotal, discount_amount, round(subtotal - discount_amount, 2)


def calculate_gst(taxable_amount: float, gst_rate: float) -> tuple[float, float, float]:
    """Return (taxable value, CGST, SGST) for GST charged on top of the amount.

    The GST is divided into two equal halves, each rounded to paise, so
    taxable value + CGST + SGST is exactly the amount the customer pays.
    """
    if gst_rate < 0 or gst_rate > 100:
        raise ValueError("GST rate must be between 0 and 100.")
    taxable_amount = round(taxable_amount, 2)
    if gst_rate == 0:
        return taxable_amount, 0.0, 0.0

    half_tax = round(taxable_amount * gst_rate / 200, 2)
    return taxable_amount, half_tax, half_tax


def round_to_rupee(amount: float) -> float:
    """Round an amount to the nearest whole rupee, with exactly half a rupee rounding up."""
    paise = Decimal(str(round(amount, 2)))
    return float(paise.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


@dataclass
class BillTotals:
    """Every amount shown on a bill; ``total`` is what the customer pays.

    ``total`` is a whole number of rupees because nobody can pay paise. ``round_off`` is what was added
    (positive) or taken off (negative) the exact amount to get there, so the bill still adds up.
    """

    subtotal: float
    discount_amount: float
    taxable_amount: float
    cgst: float
    sgst: float
    total: float
    gst_rate: float
    round_off: float = 0.0


def calculate_bill_totals(
    lines: list[CartLine],
    discount: Discount | None = None,
    gst_rate: float = 0.0,
) -> BillTotals:
    """Return the full bill: subtotal, discount, GST added on top, and the total rounded to whole rupees."""
    subtotal, discount_amount, after_discount = calculate_order_totals(lines, discount)
    taxable_amount, cgst, sgst = calculate_gst(after_discount, gst_rate)
    exact_total = round(taxable_amount + cgst + sgst, 2)
    total = round_to_rupee(exact_total)
    round_off = round(total - exact_total, 2)
    return BillTotals(subtotal, discount_amount, taxable_amount, cgst, sgst, total, gst_rate, round_off)


def validate_payment(
    payment_mode: str,
    total: float,
    split_payments: dict[str, float] | None = None,
) -> None:
    """Validate that a split payment equals the final payable amount."""
    if payment_mode not in {"Cash", "UPI", "Split"}:
        raise ValueError("Unknown payment method.")

    if payment_mode != "Split":
        return

    if split_payments is None:
        raise ValueError("Payment mismatch.")
    if any(amount < 0 for amount in split_payments.values()):
        raise ValueError("Payment mismatch.")
    if abs(sum(split_payments.values()) - total) > 0.01:
        raise ValueError("Payment mismatch.")


def next_bill_number(session: Session, order_date: str) -> int:
    """Return the next bill number for a local calendar date."""
    largest_bill_number = session.scalar(
        select(func.max(Order.bill_number)).where(Order.order_date == order_date)
    )
    return (largest_bill_number or 0) + 1


def save_order(
    session: Session,
    lines: list[CartLine],
    discount: Discount | None,
    payment_mode: str,
    split_payments: dict[str, float] | None = None,
    completed_at: datetime | None = None,
    service_type: str = "Dine In",
    gst_rate: float = 0.0,
    source: str = "Counter",
    customer_phone: str | None = None,
) -> Order:
    """Save a completed, immutable order and its historical item snapshots.

    ``gst_rate`` is the percentage added on top of the discounted amount; the
    resulting CGST, SGST and final total are stored on the order so later rate
    changes never alter this bill.
    """
    bill = calculate_bill_totals(lines, discount, gst_rate)
    subtotal, total = bill.subtotal, bill.total
    taxable_amount, cgst, sgst = bill.taxable_amount, bill.cgst, bill.sgst
    validate_payment(payment_mode, total, split_payments)

    completed_at = completed_at or datetime.now()
    order_date = completed_at.date().isoformat()
    order = Order(
        bill_number=next_bill_number(session, order_date),
        order_date=order_date,
        order_time=completed_at.strftime("%H:%M:%S"),
        service_type=service_type,
        payment_mode=payment_mode,
        source=source,
        customer_phone=customer_phone or None,
        subtotal=subtotal,
        discount_type=_discount_type(discount),
        discount_value=discount.value if discount else None,
        discount_scope=discount.scope if discount else None,
        discount_menu_item_id=discount.menu_item_id if discount else None,
        total=total,
        round_off=bill.round_off,
        gst_rate=gst_rate if gst_rate > 0 else None,
        taxable_amount=taxable_amount if gst_rate > 0 else None,
        cgst=cgst if gst_rate > 0 else None,
        sgst=sgst if gst_rate > 0 else None,
    )
    session.add(order)
    session.flush()

    for line in lines:
        session.add(
            OrderItem(
                order_id=order.id,
                menu_item_id=line.menu_item_id,
                item_name=line.item_name,
                quantity=line.quantity,
                unit_price=line.unit_price,
                note=line.note,
            )
        )

    if payment_mode == "Split" and split_payments is not None:
        for mode, amount in split_payments.items():
            if amount > 0:
                session.add(SplitPayment(order_id=order.id, payment_mode=mode, amount=amount))

    session.flush()
    return order


def _discount_type(discount: Discount | None) -> str | None:
    """Store the discount type and scope using the existing text column."""
    if discount is None:
        return None
    return f"{discount.kind}_{discount.scope}"
