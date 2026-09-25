"""WhatsApp order received from a customer, waiting for the owner to handle it."""

from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class OnlineOrder(Base):
    """A customer's WhatsApp order. It becomes a normal ``Order`` only once billed.

    ``external_id`` is the WhatsApp message id (or a relay event key) so the same
    message can never create two orders. ``relay_event_id`` remembers how far the
    relay has been read.
    """

    __tablename__ = "online_orders"
    __table_args__ = {"sqlite_autoincrement": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    external_id: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    relay_event_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    customer_phone: Mapped[str] = mapped_column(String, nullable=False, default="")
    customer_name: Mapped[str | None] = mapped_column(String, nullable=True)
    message_text: Mapped[str] = mapped_column(String, nullable=False, default="")
    items_json: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="New")
    prep_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quoted_total: Mapped[float | None] = mapped_column(Float, nullable=True)
    reject_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    received_at: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"), nullable=True)
    last_message: Mapped[str | None] = mapped_column(String, nullable=True)
