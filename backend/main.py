import sys
from PySide6.QtWidgets import QApplication
from ui import AudioEditor

# ============================================================
#                          MAIN
# ============================================================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AudioEditor()
    window.show()
    sys.exit(app.exec())