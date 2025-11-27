# ============================================================
#                    CLEANUP PATTERNS
# ============================================================
UNWANTED_PATTERNS = [
    # Video/Audio markers
    r'[\(\[](?:official\s*)?(?:video|audio|music\s*video|mv|visuali[sz]er|lyric\s*video|lyrics?)[\)\]]',
    r'[\(\[](?:4k|hd|hq|uhd|1080p?|720p?)[\)\]]',
    
    # Versions and edits
    r'[\(\[]\d+[\)\]]',  # (1), (2)
    r'[\(\[](?:copy|remaster(?:ed)?|edit|video\s*edit)[\)\]]',
    r'[\(\[](?:extended|original|radio|single)(?:\s*(?:version|mix|edit))?[\)\]]',
    r'[\(\[](?:explicit|clean)[\)\]]',
    
    # Platforms and misc
    r'[\(\[](?:youtube|vevo|spotify|soundcloud|tiktok)[\)\]]',
    r'[\(\[](?:album|outro|intro)[\)\]]',
    r'[\(\[]prod\.?\s*by\s+.*?[\)\]]',
    r'\|\s*.*$',  # Everything after |
    r'[-–—]\s*topic$',
    
    # Featured artists (we extract these separately)
    r'[\(\[](?:ft\.?|feat\.?)\s+.*?[\)\]]',
]