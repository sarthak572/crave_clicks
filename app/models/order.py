"""Completed order database model."""

from sqlalchemy import Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class Order(Base):
    """A completed cafe order."""

    __tablename__ = "orders"
    __table_args__ = {"sqlite_autoincrement": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bill_number: Mapped[int] = mapped_column(Integer, nullable=False)
    order_date: Mapped[str] = mapped_column(String, nullable=False)
    order_time: Mapped[str] = mapped_column(String, nullable=False)
    service_type: Mapped[str] = mapped_column(String, nullable=False)
    payment_mode: Mapped[str] = mapped_column(String, nullable=False)
    subtotal: Mapped[float] = mapped_column(Float, nullable=False)
    discount_type: Mapped[str | None] = mapped_column(String, nullable=True)
    discount_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    discount_scope: Mapped[str | None] = mapped_column(String, nullable=True)
    discount_menu_item_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total: Mapped[float] = mapped_column(Float, nullable=False)
    round_off: Mapped[float | None] = mapped_column(Float, nullable=True)
    gst_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    taxable_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    cgst: Mapped[float | None] = mapped_column(Float, nullable=True)
    sgst: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str | None] = mapped_column(String, nullable=True)
    customer_phone: Mapped[str | None] = mapped_column(String, nullable=True)
    is_void: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    items: Mapped[list["OrderItem"]] = relationship(back_populates="order")
    split_payments: Mapped[list["SplitPayment"]] = relationship(back_populates="order")
