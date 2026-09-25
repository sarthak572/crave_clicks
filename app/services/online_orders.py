"""Rules for WhatsApp orders: recording them, moving them through their statuses, and the
wording of the messages the customer gets. No network and no screens in here."""

from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import OnlineOrder


NEW = "New"
ACCEPTED = "Accepted"
READY = "Ready"
OUT_FOR_DELIVERY = "Out for delivery"
COMPLETED = "Completed"
REJECTED = "Rejected"

ACTIVE_STATUSES = (NEW, ACCEPTED, READY, OUT_FOR_DELIVERY)
DONE_STATUSES = (COMPLETED, REJECTED)

_TRANSITIONS = {
    NEW: {ACCEPTED, REJECTED},
    ACCEPTED: {READY, OUT_FOR_DELIVERY, REJECTED, COMPLETED},
    READY: {COMPLETED},
    OUT_FOR_DELIVERY: {COMPLETED},
    COMPLETED: set(),
    REJECTED: set(),
}

# The message that goes to the customer when an order moves to each status.
STATUS_MESSAGE = {
    ACCEPTED: "accepted",
    READY: "ready",
    OUT_FOR_DELIVERY: "out_for_delivery",
    REJECTED: "rejected",
}

REJECT_REASONS = (
    "Item not available",
    "Shop is closed",
    "Too busy right now",
    "Outside our delivery area",
)


class OnlineOrderError(ValueError):
    """A status change that the order's current status does not allow."""


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def order_number(order: OnlineOrder) -> str:
    """The short number shown to the owner and the customer, e.g. W14."""
    return f"W{order.id}"


def normalize_phone(raw: str, country_code: str = "91") -> str:
    """Digits only, with the country code added to a plain 10-digit number."""
    digits = "".join(ch for ch in str(raw or "") if ch.isdigit())
    digits = digits.lstrip("0") if len(digits) == 11 and digits.startswith("0") else digits
    if len(digits) == 10:
        return f"{country_code}{digits}"
    return digits


def display_phone(digits: str) -> str:
    return f"+{digits}" if digits else "unknown number"


def record_incoming(session: Session, event: dict) -> tuple[OnlineOrder | None, bool]:
    """Save one customer message from the relay.

    If the same customer already has an order in progress, the message is added
    to that conversation instead of opening a new chat for every message they send.
    Returns ``(order, is_new)``; ``order`` is None if this message was already saved.
    """
    external_id = str(event.get("message_id") or "").strip() or (
        f"evt-{event.get('event_id', 0)}-{event.get('index', 0)}"
    )
    if session.scalar(select(OnlineOrder.id).where(OnlineOrder.external_id == external_id)) is not None:
        return None, False

    phone = str(event.get("from") or "")
    text = str(event.get("text") or "")
    stamp = _now()
    entry = f"[{stamp[11:16]}] {text}" if text else text

    existing = None
    if phone and phone != "unknown":
        existing = session.scalar(
            select(OnlineOrder)
            .where(OnlineOrder.customer_phone == phone)
            .where(OnlineOrder.status.in_(ACTIVE_STATUSES))
            .order_by(OnlineOrder.id.desc())
        )
    if existing is not None:
        if entry:
            existing.message_text = f"{existing.message_text}\n{entry}" if existing.message_text else entry
        existing.external_id = external_id
        existing.relay_event_id = int(event.get("event_id") or existing.relay_event_id or 0)
        existing.updated_at = stamp
        session.flush()
        return existing, False

    items = event.get("items")
    order = OnlineOrder(
        external_id=external_id,
        relay_event_id=int(event.get("event_id") or 0),
        customer_phone=phone,
        customer_name=(str(event.get("name") or "").strip() or None),
        message_text=entry,
        items_json=json.dumps(items) if items else None,
        status=NEW,
        received_at=stamp,
        updated_at=stamp,
    )
    session.add(order)
    session.flush()
    return order, True


def last_relay_event_id(session: Session) -> int:
    """Where to continue reading the relay after a restart."""
    return int(session.scalar(select(func.max(OnlineOrder.relay_event_id))) or 0)


def count_new(session: Session) -> int:
    return int(session.scalar(select(func.count()).select_from(OnlineOrder).where(OnlineOrder.status == NEW)) or 0)


def list_orders(session: Session, statuses: tuple[str, ...] | None = None) -> list[OnlineOrder]:
    query = select(OnlineOrder).order_by(OnlineOrder.id.desc())
    if statuses:
        query = query.where(OnlineOrder.status.in_(statuses))
    return list(session.scalars(query))


def change_status(
    session: Session,
    order_id: int,
    new_status: str,
    *,
    prep_minutes: int | None = None,
    quoted_total: float | None = None,
    reason: str | None = None,
) -> OnlineOrder:
    """Move an order to ``new_status`` if its current status allows it."""
    order = session.get(OnlineOrder, order_id)
    if order is None:
        raise OnlineOrderError("Order not found.")
    if new_status not in _TRANSITIONS.get(order.status, set()):
        raise OnlineOrderError(f"An order that is {order.status} cannot become {new_status}.")

    order.status = new_status
    order.updated_at = _now()
    if prep_minutes is not None:
        order.prep_minutes = prep_minutes
    if quoted_total is not None:
        order.quoted_total = quoted_total
    if reason is not None:
        order.reject_reason = reason
    session.flush()
    return order


def mark_billed(session: Session, online_order_id: int, order_id: int) -> None:
    """Link the finished bill to the online order and close it."""
    order = session.get(OnlineOrder, online_order_id)
    if order is None or order.status in DONE_STATUSES:
        return
    order.status = COMPLETED
    order.order_id = order_id
    order.updated_at = _now()


def cart_items(order: OnlineOrder) -> list[dict]:
    """The catalog items in an order: [{"id", "qty", "price"}], or none for a text order."""
    if not order.items_json:
        return []
    try:
        items = json.loads(order.items_json)
    except ValueError:
        return []
    return [item for item in items if isinstance(item, dict)]


def message_details(order: OnlineOrder, shop_name: str) -> dict[str, str]:
    """Everything a message template can mention about an order."""
    total = order.quoted_total
    return {
        "name": (order.customer_name or "there").strip() or "there",
        "phone": order.customer_phone,
        "order_no": order_number(order),
        "shop": shop_name,
        "minutes": str(order.prep_minutes) if order.prep_minutes else "20",
        "total": f"{total:.2f}" if total is not None else "-",
        "reason": (order.reject_reason or "").strip() or "not available right now",
    }
