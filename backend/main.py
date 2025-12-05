"""
Audio Editor Application Entry Point
"""
import sys
from PySide6.QtWidgets import QApplication
from ui.main_window import MainWindow


def main():
    """Initialize and run the application"""
    app = QApplication(sys.argv)
    
    # Set application metadata
    app.setApplicationName("Sound Simulation")
    app.setOrganizationName("AudioEditor")
    app.setApplicationVersion("2.0")
    
    # Create and show main window
    window = MainWindow()
    window.show()
    
    # Run application event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()