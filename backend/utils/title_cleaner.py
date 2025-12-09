import re

class TitleCleaner:
    """
    Completely rewritten title cleaner
    - Fixes artist/title prefix cases
    - Extracts featured artists heavily
    - Removes uploader usernames
    - Properly trims junk text
    """

    # ------------------------------------------------------------
    # Master unwanted patterns
    # ------------------------------------------------------------
    YT_GARBAGE = [
        r'\[.*?official.*?\]',
        r'\(.*?official.*?\)',
        r'\[.*?music\s*video.*?\]',
        r'\(.*?music\s*video.*?\)',
        r'\[.*?audio.*?\]',
        r'\(.*?audio.*?\)',
        r'\[.*?lyrics.*?\]',
        r'\(.*?lyrics.*?\)',
        r'\[.*?explicit.*?\]',
        r'\(.*?explicit.*?\)',
        r'\[.*?clean.*?\]',
        r'\(.*?clean.*?\)',
        r'\[.*?radio\s*edit.*?\]',
        r'\(.*?radio\s*edit.*?\)',
        r'\[.*?hd.*?\]',
        r'\(.*?hd.*?\)',
        r'\[.*?hq.*?\]',
        r'\(.*?hq.*?\)',
        r'\(official.*?\)',
        r'\[official.*?\]',
        r'\(video.*?\)',
        r'\[video.*?\]',
        r'\(full.*?\)',
        r'\[full.*?\]',
    ]

    # ------------------------------------------------------------
    @staticmethod
    def clean_title(title, original_artist, composer="", ui_artist=None):
        """
        Cleans title and returns (clean_title, updated_composer, features)
        """

        if not title:
            return title, composer, []

        artist = ui_artist.strip() if ui_artist else original_artist.strip()

        ft_artists = []

        # ------------------------------------------------------------
        # Extract ALL featured artists
        # ------------------------------------------------------------
        ft_matches = re.findall(
            r'(?:feat|ft|featuring)\.?\s*([^\-\(\)\[\]]+)',
            title,
            flags=re.IGNORECASE
        )

        for m in ft_matches:
            parts = re.split(r',|&| and ', m)
            ft_artists.extend([p.strip() for p in parts if p.strip()])

        # From prefix: Artist1, Artist2 - Title
        if ' - ' in title:
            prefix = title.split(' - ')[0]
            if ',' in prefix:
                extra = [p.strip() for p in prefix.split(',')[1:] if p.strip()]
                ft_artists.extend(extra)

        # Deduplicate
        ft_artists = list(dict.fromkeys(ft_artists))

        # ------------------------------------------------------------
        # REMOVE FULL ARTIST PREFIXES (your biggest issue)
        # Examples:
        #   "Tainy, Rauw Alejandro - SCI-FI"
        #   "The Marias, Josh Conway - Song"
        # ------------------------------------------------------------
        if ' - ' in title:
            left, right = title.split(' - ', 1)

            # If UI artist is provided, trust it FIRST
            if ui_artist:
                left_artists = [artist]

            else:
                # Example: "Tainy, Bad Bunny, Julieta Venegas"
                left_artists = [p.strip() for p in re.split(r',|&| and ', left) if p.strip()]

            # Add into featured list EXCEPT primary artist
            for la in left_artists:
                if la.lower() != artist.lower() and la not in ft_artists:
                    ft_artists.append(la)

            # Keep the RIGHT SIDE (always the title)
            title = right

        # ------------------------------------------------------------
        # Remove YouTube garbage patterns
        # ------------------------------------------------------------
        for pattern in TitleCleaner.YT_GARBAGE:
            title = re.sub(pattern, '', title, flags=re.IGNORECASE)

        # ------------------------------------------------------------
        # Remove featured patterns from inside title text
        # ------------------------------------------------------------
        title = re.sub(r'[\(\[]\s*(?:feat|ft|featuring)\.?\s*[^\)\]]+[\)\]]', '', title, flags=re.IGNORECASE)
        title = re.sub(r'(?:feat|ft|featuring)\.?\s+[^\-\(\[]+', '', title, flags=re.IGNORECASE)

        # Fix broken parentheses (e.g., "(full v)")
        title = title.replace("(full v)", "full version")

        # Cleanup: remove empty parentheses/brackets leftover
        title = re.sub(r'\(\s*\)', '', title)
        title = re.sub(r'\[\s*\]', '', title)

        # ------------------------------------------------------------
        # FINAL TRIM & SPACING
        # ------------------------------------------------------------
        title = re.sub(r'\s+', ' ', title).strip(' -_,;:.()[]')

        # ------------------------------------------------------------
        # UPDATE COMPOSER FIELD
        # ------------------------------------------------------------
        existing = [c.strip() for c in composer.split(',') if c.strip()] if composer else []
        for ft in ft_artists:
            if ft.lower() not in [e.lower() for e in existing]:
                existing.append(ft)
        updated_composer = ", ".join(existing)

        return title, updated_composer, ft_artists

    # ------------------------------------------------------------
    @staticmethod
    def batch_clean_titles(file_paths, metadata_manager, ui_artist=None):
        from mutagen import File as MF

        cleaned = {}

        for path in file_paths:
            try:
                audio = MF(path, easy=True)
                if not audio:
                    continue

                title = audio.get("title", [""])[0]
                artist = audio.get("artist", [""])[0]
                composer = audio.get("composer", [""])[0]

                clean_title, new_composer, features = TitleCleaner.clean_title(
                    title,
                    artist,
                    composer,
                    ui_artist=ui_artist
                )

                cleaned[path] = {
                    "title": clean_title,
                    "composer": new_composer,
                    "featuring": ", ".join(features)
                }

            except Exception as e:
                print("Clean error:", path, e)

        return cleaned

    # ------------------------------------------------------------
    @staticmethod
    def apply_cleaned_titles(cleaned_data):
        from core.metadata_manager import MetadataManager

        saved = 0

        for path, data in cleaned_data.items():
            try:
                MetadataManager.write_metadata(
                    path,
                    {
                        "title": data["title"],
                        "composer": data["composer"],
                        "comment": data["featuring"]
                    },
                )
                saved += 1
            except:
                pass

        return saved
