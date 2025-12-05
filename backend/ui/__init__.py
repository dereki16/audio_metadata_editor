# ====================
# ui/__init__.py
# ====================
"""
User interface components
"""
from .main_window import MainWindow
from .left_panel import LeftPanel
from .right_panel import RightPanel
from .genre_manager import GenreManager

__all__ = [
    'MainWindow',
    'LeftPanel',
    'RightPanel',
    'GenreManager'
]
