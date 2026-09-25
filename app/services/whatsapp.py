"""WhatsApp orders: sending and receiving via local whatsapp-web.js server.
"""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime

from PySide6.QtCore import QObject, Signal

from app.database import session_scope
from app.models import OnlineOrder
from app.runtime_paths import logs_directory
from app.services import online_orders
from app.services.configuration import get_whatsapp_settings, load_configuration


class WhatsAppError(Exception):
    """Something went wrong talking to the local whatsapp server."""


def _log(message: str) -> None:
    try:
        with open(logs_directory() / f"{date.today().isoformat()}.log", "a", encoding="utf-8") as log:
            log.write(f"{datetime.now():%H:%M:%S} whatsapp: {message}\n")
    except OSError:
        pass


def _request(request: urllib.request.Request, timeout: float, who: str) -> str:
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:200].strip()
        raise WhatsAppError(f"{who} answered {error.code}. {detail}".strip()) from error
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise WhatsAppError(f"Could not reach {who}. Check the server is running.") from error


def send_local_message(phone: str, text: str, timeout: float = 15.0) -> str:
    body = json.dumps({"phone": phone, "text": text}).encode("utf-8")
    request = urllib.request.Request(
        "http://localhost:3000/pos/send", data=body, method="POST", headers={"Content-Type": "application/json"}
    )
    return _request(request, timeout, "Local WhatsApp")


def fetch_relay_events(after: int, *, timeout: float = 10.0) -> dict:
    request = urllib.request.Request(f"http://localhost:3000/pos/events?after={int(after)}")
    reply = _request(request, timeout, "Local WhatsApp")
    return json.loads(reply)


def request_pairing_code(phone: str, timeout: float = 15.0) -> str:
    body = json.dumps({"phone": phone}).encode("utf-8")
    request = urllib.request.Request(
        "http://localhost:3000/pos/request_pairing_code", data=body, method="POST", headers={"Content-Type": "application/json"}
    )
    reply = _request(request, timeout, "Local WhatsApp")
    data = json.loads(reply)
    if "code" in data:
        return data["code"]
    return ""


class WhatsAppOrderService(QObject):
    orders_changed = Signal()
    new_order = Signal(int)
    connection_changed = Signal(str)
    qr_code_received = Signal(str)
    message_result = Signal(int, str, bool, str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.connection = "Off"
        self._cursor: int | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, name="whatsapp-poll", daemon=True)
            self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)

    def _run(self) -> None:
        while not self._stop.is_set():
            wait = 3.0
            try:
                settings = get_whatsapp_settings()
                if not settings.get("enabled"):
                    self._set_connection("Off")
                else:
                    wait = float(settings.get("poll_seconds", 5.0))
                    try:
                        import urllib.request
                        import json
                        status_reply = urllib.request.urlopen("http://localhost:3000/pos/status", timeout=2.0).read()
                        status = json.loads(status_reply)
                        if status.get("qr"):
                            self.qr_code_received.emit(status["qr"])
                    except Exception:
                        pass
                    try:
                        self.poll_once(settings)
                        self._set_connection("Connected")
                    except WhatsAppError as error:
                        self._set_connection(f"Offline: {error}")
            except Exception as error:
                _log(f"poller error: {error!r}")
            self._stop.wait(wait)

    def _set_connection(self, state: str) -> None:
        if state != self.connection:
            self.connection = state
            if state.startswith("Offline"):
                _log(state)
            self.connection_changed.emit(state)

    def poll_once(self, settings: dict | None = None) -> int:
        if self._cursor is None:
            with session_scope() as session:
                self._cursor = online_orders.last_relay_event_id(session)

        data = fetch_relay_events(self._cursor)
        events = data.get("events") if isinstance(data.get("events"), list) else []

        new_ids: list[int] = []
        any_change = False
        with session_scope() as session:
            for event in events:
                if isinstance(event, dict):
                    order, is_new = online_orders.record_incoming(session, event)
                    if order is not None:
                        any_change = True
                        if is_new:
                            new_ids.append(order.id)
        try:
            self._cursor = max(self._cursor, int(data.get("last_id", self._cursor)))
        except (TypeError, ValueError):
            pass

        for order_id in new_ids:
            self.new_order.emit(order_id)
            if settings and settings.get("auto_ack"):
                self.send_message_now(order_id, "received")
        if any_change:
            self.orders_changed.emit()
        return len(new_ids)

    def send_status_message(self, order_id: int, event_key: str) -> None:
        threading.Thread(
            target=self.send_message_now, args=(order_id, event_key), name="whatsapp-send", daemon=True
        ).start()

    def send_message_now(self, order_id: int, event_key: str) -> tuple[bool, str]:
        try:
            worked, text = self._send(order_id, event_key)
        except Exception as error:
            _log(f"send error for {order_id}/{event_key}: {error!r}")
            worked, text = False, "Unexpected error. See the log file."

        try:
            with session_scope() as session:
                order = session.get(OnlineOrder, order_id)
                if order is not None:
                    result = "sent" if worked else f"NOT sent - {text}"
                    order.last_message = f"{event_key}: {result} ({datetime.now():%H:%M})"
        except Exception as error:
            _log(f"could not record message result: {error!r}")

        if not worked:
            _log(f"order {order_id} {event_key}: {text}")
        self.message_result.emit(order_id, event_key, worked, text)
        self.orders_changed.emit()
        return worked, text

    @staticmethod
    def _send(order_id: int, event_key: str) -> tuple[bool, str]:
        settings = get_whatsapp_settings()
        shop_name = str(load_configuration().get("cafe_name") or "our shop")

        with session_scope() as session:
            order = session.get(OnlineOrder, order_id)
            if order is None:
                return False, "Order not found."
            
            details = online_orders.message_details(order, shop_name)
            phone = online_orders.normalize_phone(order.customer_phone, str(settings.get("country_code", "91")))
            
        text = ""
        if event_key == "accepted":
            text = f"Hi {details['name']}, your order {details['order_no']} from {details['shop']} has been accepted! It will be ready in approximately {details['minutes']} minutes. Total amount: {details['total']}"
        elif event_key == "ready":
            text = f"Hi {details['name']}, your order {details['order_no']} from {details['shop']} is now ready!"
        elif event_key == "out_for_delivery":
            text = f"Hi {details['name']}, your order {details['order_no']} from {details['shop']} is out for delivery and will reach you shortly."
        elif event_key == "rejected":
            text = f"Hi {details['name']}, unfortunately your order {details['order_no']} from {details['shop']} was rejected. Reason: {details['reason']}"
        elif event_key == "received":
            text = f"Hi {details['name']}, your order has been received by {details['shop']}."
        elif event_key.startswith("custom:"):
            text = event_key[7:]
        else:
            return False, "Unknown event key."

        if len(phone) < 11:
            return False, "The customer's phone number looks incomplete."
            
        try:
            send_local_message(phone, text)
        except WhatsAppError as error:
            return False, str(error)
        return True, "sent"
