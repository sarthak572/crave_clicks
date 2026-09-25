"""Menu item database model."""

from sqlalchemy import Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class MenuItem(Base):
    """A currently available or soft-deleted cafe menu item."""

    __tablename__ = "menu_items"
    __table_args__ = {"sqlite_autoincrement": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    is_deleted: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
