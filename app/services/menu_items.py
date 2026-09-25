"""Persistence helpers for menu items."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.menu_item import MenuItem


def add_menu_item(session: Session, name: str, category: str, price: float) -> MenuItem:
    """Add a menu item to the current transaction."""
    menu_item = MenuItem(name=name, category=category, price=price)
    session.add(menu_item)
    session.flush()
    return menu_item


def update_menu_item(
    session: Session,
    menu_item_id: int,
    name: str,
    category: str,
    price: float,
) -> MenuItem | None:
    """Update a menu item when it exists."""
    menu_item = session.get(MenuItem, menu_item_id)
    if menu_item is None:
        return None

    menu_item.name = name
    menu_item.category = category
    menu_item.price = price
    session.flush()
    return menu_item


def soft_delete_menu_item(session: Session, menu_item_id: int) -> bool:
    """Mark a menu item as deleted without removing its history."""
    menu_item = session.get(MenuItem, menu_item_id)
    if menu_item is None:
        return False

    menu_item.is_deleted = 1
    session.flush()
    return True


def get_menu_items(session: Session, search_text: str = "") -> list[MenuItem]:
    """Return active menu items matching a name search."""
    statement = select(MenuItem).where(MenuItem.is_deleted == 0)
    if search_text:
        statement = statement.where(MenuItem.name.ilike(f"%{search_text}%"))

    statement = statement.order_by(MenuItem.category, MenuItem.name)
    return list(session.scalars(statement))


def get_categories(session: Session) -> list[str]:
    """Return active menu categories in alphabetical order."""
    statement = (
        select(MenuItem.category)
        .where(MenuItem.is_deleted == 0)
        .distinct()
        .order_by(MenuItem.category)
    )
    return list(session.scalars(statement))
