"""Application entry point."""

import sys

from PySide6.QtWidgets import QApplication, QMessageBox, QWidget

from app.database import initialize_database
from app.dialogs import FirstLaunchDialog
from app.runtime_paths import logs_directory
from app.services.configuration import configuration_exists, save_configuration
from app.services.data_workbook import start_data_sync, stop_data_sync
from app.ui.dashboard import DashboardWindow
from app.ui.theme import apply_theme


def configure_application_appearance(application: QApplication) -> None:
    """Apply the CafePOS theme so controls stay readable regardless of the OS color scheme."""
    apply_theme(application)


def complete_first_launch_setup(parent: QWidget | None = None) -> bool:
    """Create config.json before showing the application for the first time."""
    if configuration_exists():
        return True

    dialog = FirstLaunchDialog(parent)
    if not dialog.exec():
        return False

    try:
        save_configuration(*dialog.values)
    except OSError:
        QMessageBox.critical(parent, "CafePOS", "Configuration could not be saved.")
        return False
    return True


def main() -> int:
    """Start the CafePOS desktop application."""
    logs_directory()
    initialize_database()

    application = QApplication(sys.argv)
    application.setApplicationName("CafePOS")
    configure_application_appearance(application)

    if not complete_first_launch_setup():
        return 0

    start_data_sync()
    window = DashboardWindow()
    window.show()
    window.start_whatsapp()

    exit_code = application.exec()
    window.stop_whatsapp()
    stop_data_sync()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
