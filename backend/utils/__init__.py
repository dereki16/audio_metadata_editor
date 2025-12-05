# ====================
# utils/__init__.py
# ====================
"""
Utility functions and helpers
"""
from .title_cleaner import TitleCleaner

# Import UNWANTED_PATTERNS if it exists in a separate file
# from .patterns import UNWANTED_PATTERNS

# Or define it here:
UNWANTED_PATTERNS = [
    r'\[.*?official.*?\]',
    r'\(.*?official.*?\)',
    r'\[.*?music\s+video.*?\]',
    r'\(.*?music\s+video.*?\)',
    r'\[.*?audio.*?\]',
    r'\(.*?audio.*?\)',
    r'\[.*?lyrics.*?\]',
    r'\(.*?lyrics.*?\)',
    r'\[.*?explicit.*?\]',
    r'\(.*?explicit.*?\)',
    r'\[.*?clean.*?\]',
    r'\(.*?clean.*?\)',
    r'\[.*?radio\s+edit.*?\]',
    r'\(.*?radio\s+edit.*?\)',
    r'\[.*?hd.*?\]',
    r'\(.*?hd.*?\)',
    r'\[.*?hq.*?\]',
    r'\(.*?hq.*?\)',
]

__all__ = [
    'TitleCleaner',
    'UNWANTED_PATTERNS'
]