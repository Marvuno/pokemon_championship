#!/usr/bin/env python3
"""
Launch Pokemon Champion with its graphical interface.

    python play.py

The original terminal version still works exactly as before:

    python main.py
"""

import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))


def main():
    os.chdir(ROOT)
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)

    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        sys.stderr.write(
            "Pokemon Champion's interface needs PySide6, which is missing\n"
            "from this Python install.\n\n"
            "  pip install PySide6\n\n"
            "PLAY.bat installs this automatically; if you're running\n"
            "play.py directly, install it yourself first.\n")
        raise SystemExit(1)

    from GUI_qt.main_window import MainWindow

    app = QApplication(sys.argv)
    window = MainWindow(ROOT)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
