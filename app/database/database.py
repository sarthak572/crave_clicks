"""SQLite engine, session management, and database initialization."""

from collections.abc import Callable, Generator
from contextlib import contextmanager

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.database.base import Base
from app.runtime_paths import application_directory
from app.services.configuration import get_database_path


DATABASE_PATH = get_database_path()
engine = create_engine(
    f"sqlite:///{DATABASE_PATH}",
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@event.listens_for(Engine, "connect")
def enable_foreign_keys(dbapi_connection: object, _connection_record: object) -> None:
    """Enable SQLite foreign-key enforcement for every connection."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def initialize_database() -> None:
    """Create the SQLite database and all known tables when needed."""
    import app.models  # noqa: F401

    Base.metadata.create_all(engine)
    _add_missing_order_columns()
    _apply_default_menu()


def _load_default_menu() -> tuple[int, list[dict]] | None:
    """Read default_menu.json and return its (version, items), or None when unusable.

    The file is either a plain list of items (version 0) or an object with a
    "version" number and an "items" list.
    """
    import json
    import sys
    from pathlib import Path

    menu_file = application_directory() / "default_menu.json"
    if not menu_file.exists():
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            menu_file = Path(meipass) / "default_menu.json"
        if not menu_file.exists():
            return None

    try:
        data = json.loads(menu_file.read_text(encoding="utf-8"))
        version, items = (int(data.get("version", 0)), data["items"]) if isinstance(data, dict) else (0, data)
        return version, [
            {"name": str(item["name"]), "category": str(item["category"]), "price": float(item["price"])}
            for item in items
        ]
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None


def _apply_default_menu() -> None:
    """Load default_menu.json into a new database, or once per new menu version.

    The applied version is kept in SQLite's ``user_version`` pragma. When the
    menu file carries a newer version than the database, the current menu items
    are soft-deleted (so historical orders are untouched) and replaced with the
    file's items. Later edits made in Menu Management are never overwritten
    until the menu file's version is raised again.
    """
    from app.models.menu_item import MenuItem

    menu = _load_default_menu()
    if menu is None:
        return
    version, items = menu

    with session_scope() as session:
        applied_version = session.execute(text("PRAGMA user_version")).scalar() or 0
        has_items = session.query(MenuItem).first() is not None
        if has_items and applied_version >= version:
            return

        for existing in session.query(MenuItem).filter(MenuItem.is_deleted == 0):
            existing.is_deleted = 1
        for item in items:
            session.add(MenuItem(name=item["name"], category=item["category"], price=item["price"], is_deleted=0))
        session.execute(text(f"PRAGMA user_version = {version}"))



def _add_missing_order_columns() -> None:
    """Add columns introduced after a database was first created."""
    with engine.begin() as connection:
        existing_columns = {
            column[1]
            for column in connection.exec_driver_sql("PRAGMA table_info(orders)")
        }
        missing_columns = {
            "discount_scope": "TEXT",
            "discount_menu_item_id": "INTEGER",
            "gst_rate": "REAL",
            "taxable_amount": "REAL",
            "cgst": "REAL",
            "sgst": "REAL",
            "source": "TEXT",
            "customer_phone": "TEXT",
            "round_off": "REAL",
        }
        for name, column_type in missing_columns.items():
            if name not in existing_columns:
                connection.execute(text(f"ALTER TABLE orders ADD COLUMN {name} {column_type}"))


_TRACKED_TABLES = {"menu_items", "orders", "order_items", "split_payments"}
_change_listeners: list[Callable[[], None]] = []


def add_change_listener(listener: Callable[[], None]) -> None:
    """Call ``listener`` after any committed change to menu or order data."""
    _change_listeners.append(listener)


@event.listens_for(Session, "after_flush")
def _flag_tracked_changes(session: Session, _flush_context: object) -> None:
    """Remember that this session wrote menu or order rows."""
    if session.info.get("data_changed"):
        return
    for instance in (*session.new, *session.dirty, *session.deleted):
        if getattr(instance, "__tablename__", None) in _TRACKED_TABLES:
            session.info["data_changed"] = True
            return


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """Provide a transaction that commits on success and rolls back on error."""
    session = SessionLocal()
    data_changed = False
    try:
        yield session
        session.commit()
        data_changed = bool(session.info.get("data_changed"))
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    if data_changed:
        for listener in _change_listeners:
            try:
                listener()
            except Exception:  # a failing listener must never break billing
                pass
