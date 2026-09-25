"""Query helpers for completed-order reports and voiding."""

from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Order, OrderItem


@dataclass(frozen=True)
class ReportSummary:
    """The non-voided sales summary for one reporting period."""

    order_count: int
    total_revenue: float
    most_sold_item: str | None


def get_orders_for_period(session: Session, start_date: date, end_date: date) -> list[Order]:
    """Return all orders for a period, including voided orders."""
    statement = (
        select(Order)
        .where(
            Order.order_date >= start_date.isoformat(),
            Order.order_date <= end_date.isoformat(),
        )
        .order_by(Order.order_date.desc(), Order.order_time.desc(), Order.id.desc())
    )
    return list(session.scalars(statement))


def get_report_summary(session: Session, start_date: date, end_date: date) -> ReportSummary:
    """Return sales totals and the most sold item, excluding voided orders."""
    period_filters = (
        Order.order_date >= start_date.isoformat(),
        Order.order_date <= end_date.isoformat(),
        Order.is_void == 0,
    )
    order_count = session.scalar(select(func.count()).select_from(Order).where(*period_filters)) or 0
    total_revenue = session.scalar(select(func.sum(Order.total)).where(*period_filters)) or 0.0
    most_sold_item = session.execute(
        select(OrderItem.item_name)
        .join(Order, OrderItem.order_id == Order.id)
        .where(*period_filters)
        .group_by(OrderItem.item_name)
        .order_by(func.sum(OrderItem.quantity).desc(), OrderItem.item_name.asc())
        .limit(1)
    ).scalar_one_or_none()

    return ReportSummary(
        order_count=int(order_count),
        total_revenue=float(total_revenue),
        most_sold_item=most_sold_item,
    )


def get_order(session: Session, order_id: int) -> Order | None:
    """Return a completed order by its permanent internal ID."""
    return session.get(Order, order_id)


def void_order(session: Session, order_id: int) -> bool:
    """Void a completed order once while preserving it for historical lookup."""
    order = session.get(Order, order_id)
    if order is None or order.is_void:
        return False

    order.is_void = 1
    session.flush()
    return True
