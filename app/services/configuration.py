"""Local configuration used by first-launch setup and receipt printing."""

import json
from pathlib import Path

from app.runtime_paths import application_directory


CONFIG_PATH = application_directory() / "config.json"


def configuration_exists() -> bool:
    """Return whether first-launch setup has already created a configuration file."""
    return CONFIG_PATH.is_file()


def load_configuration(config_path: Path | None = None) -> dict[str, object]:
    """Read local configuration, treating unreadable optional values as absent."""
    path = config_path or CONFIG_PATH
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def save_configuration(
    cafe_name: str,
    receipt_footer: str,
    gst_rate: float | None = None,
) -> None:
    """Save the café details while keeping every other stored setting.

    ``gst_rate`` is only written when given, so callers that do not know about
    GST never erase the rate the owner set.
    """
    config = load_configuration()
    config["cafe_name"] = cafe_name.strip()
    config["receipt_footer"] = receipt_footer.strip()
    if gst_rate is not None:
        config["gst_rate"] = gst_rate
    _write_configuration(config)


def get_gst_rate(config_path: Path | None = None) -> float:
    """Return the owner's GST percentage (for example 5 or 18), or 0 when not set."""
    value = load_configuration(config_path).get("gst_rate")
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return 0.0
    try:
        rate = float(value)
    except ValueError:
        return 0.0
    return rate if 0 < rate <= 100 else 0.0


def get_whatsapp_settings(config_path: Path | None = None) -> dict[str, object]:
    """Return the WhatsApp order settings, filling anything missing with safe defaults."""
    stored = load_configuration(config_path).get("whatsapp")
    stored = stored if isinstance(stored, dict) else {}

    def text(key: str, default: str = "") -> str:
        value = stored.get(key, default)
        return value.strip() if isinstance(value, str) else default

    try:
        poll_seconds = float(stored.get("poll_seconds", 5))
    except (TypeError, ValueError):
        poll_seconds = 5.0

    return {
        "enabled": stored.get("enabled") is True,
        "country_code": "".join(ch for ch in text("country_code", "91") if ch.isdigit()) or "91",
        "auto_ack": stored.get("auto_ack") is True,
        "poll_seconds": min(max(poll_seconds, 2.0), 60.0),
    }


def save_whatsapp_settings(settings: dict[str, object], config_path: Path | None = None) -> None:
    """Store the WhatsApp settings while keeping every other configuration value."""
    path = config_path or CONFIG_PATH
    config = load_configuration(path)
    merged = get_whatsapp_settings(path)
    merged.update(settings)
    config["whatsapp"] = merged
    _write_configuration(config, path)


def get_default_printer(config_path: Path | None = None) -> str | None:
    """Return the stored receipt printer, if one has been selected."""
    return text_value(load_configuration(config_path), "default_printer", "Default Printer")


def save_default_printer(printer_name: str, config_path: Path | None = None) -> None:
    """Store a printer choice while preserving the existing café settings."""
    path = config_path or CONFIG_PATH
    config = load_configuration(path)
    key = "Default Printer" if "Default Printer" in config else "default_printer"
    config[key] = printer_name
    _write_configuration(config, path)


def text_value(config: dict[str, object], *keys: str) -> str | None:
    """Return the first non-empty string stored under the supplied keys."""
    for key in keys:
        value = config.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _write_configuration(config: dict[str, object], config_path: Path | None = None) -> None:
    path = config_path or CONFIG_PATH
    path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

def get_database_path(config_path: Path | None = None) -> Path:
    """Return the configured database path, falling back to the app directory."""
    path_str = text_value(load_configuration(config_path), "database_path")
    if path_str:
        return Path(path_str)
    return application_directory() / "cafepos.db"

def get_reports_folder(config_path: Path | None = None) -> Path:
    """Return the configured reports folder, falling back to the app directory."""
    path_str = text_value(load_configuration(config_path), "reports_folder")
    if path_str:
        return Path(path_str)
    return application_directory() / "reports"

def save_paths(db_path: str, reports_folder: str, config_path: Path | None = None) -> None:
    """Save the database and reports locations while keeping other settings."""
    path = config_path or CONFIG_PATH
    config = load_configuration(path)
    config["database_path"] = db_path
    config["reports_folder"] = reports_folder
    _write_configuration(config, path)

