"""
Title Cleaner - Utilities for cleaning audio file titles
"""
import re

from core.metadata_manager import MetadataManager

class TitleCleaner:
    """Cleans audio titles and extracts featured artists"""
    
    @staticmethod
    def clean_title(title, artist, composer="", unwanted_patterns=None):
    # ---- FIXED FEATURED ARTIST EXTRACTION ----

      # Matches:
      # (feat X), [feat X], feat. X, ft. X, featuring X
      # with or without parentheses
      ft_matches = re.findall(
          r'(?:[\(\[]\s*(?:feat|ft|featuring)\.?\s*(.*?)\s*[\)\]]|'
          r'(?:feat|ft|featuring)\.?\s+(.*?)(?:$| - ))',
          title,
          flags=re.IGNORECASE
      )

      for m1, m2 in ft_matches:
          match = m1 or m2
          parts = re.split(r',|&| and ', match, flags=re.IGNORECASE)
          ft_artists.extend([p.strip() for p in parts if p.strip()])

      # Artist, FeaturedArtist - Title
      if artist and ' - ' in title:
          before_dash = title.split(' - ')[0]
          if ',' in before_dash:
              parts = before_dash.split(',')[1:]
              ft_artists.extend([p.strip() for p in parts if p.strip()])

      # Artist & FeaturedArtist
      if artist:
          and_matches = re.findall(
              rf'{re.escape(artist)}\s*(?:&|and)\s+([^-\(\[\|]+)',
              title,
              flags=re.IGNORECASE
          )
          ft_artists.extend([m.strip() for m in and_matches])

    @staticmethod
    def batch_clean_titles(file_paths, metadata_manager, ui_artist=None):
        """
        Batch-clean titles.
        
        Returns:
            Dict[path] = {title, composer, featuring}
        """
        from mutagen import File as MutagenFile
        
        cleaned_data = {}
        
        for path in file_paths:
            try:
                audio = MutagenFile(path, easy=True)
                if not audio:
                    continue
                
                title = audio.get("title", [""])[0]
                artist = audio.get("artist", [""])[0]
                composer = audio.get("composer", [""])[0]
                
                artist_for_clean = ui_artist if ui_artist else artist
                
                cleaned_title, updated_composer, featuring_list = TitleCleaner.clean_title(
                    title, artist_for_clean, composer
                )

                
                cleaned_data[path] = {
                    "title": cleaned_title,
                    "composer": updated_composer,
                    "featuring": ", ".join(featuring_list) if featuring_list else ""
                }
                
            except Exception as e:
                print(f"Error cleaning {path}: {e}")
        
        return cleaned_data
    

    @staticmethod
    def clean_title(title, artist, composer="", unwanted_patterns=None):
        import re

        if not title:
            return title, composer, []

        # ---------------------------
        # REQUIRED: initialize list
        # ---------------------------
        ft_artists = []

        # ---------------------------
        # FIXED FEATURED ARTIST EXTRACTION
        # ---------------------------

        # Matches:
        # (feat X), [feat X], feat. X, ft. X, featuring X
        ft_matches = re.findall(
            r'(?:[\(\[]\s*(?:feat|ft|featuring)\.?\s*(.*?)\s*[\)\]]|'
            r'(?:feat|ft|featuring)\.?\s+(.*?)(?:$| - ))',
            title,
            flags=re.IGNORECASE
        )

        for m1, m2 in ft_matches:
            match = m1 or m2
            if match:
                parts = re.split(r',|&| and ', match, flags=re.IGNORECASE)
                ft_artists.extend([p.strip() for p in parts if p.strip()])

        # Artist, FeaturedArtist - Title
        if artist and ' - ' in title:
            before_dash = title.split(' - ')[0]
            if ',' in before_dash:
                parts = before_dash.split(',')[1:]
                ft_artists.extend([p.strip() for p in parts if p.strip()])

        # Artist & FeaturedArtist
        if artist:
            and_matches = re.findall(
                rf'{re.escape(artist)}\s*(?:&|and)\s+([^-\(\[\|]+)',
                title,
                flags=re.IGNORECASE
            )
            ft_artists.extend([m.strip() for m in and_matches])

        # Deduplicate
        ft_artists = list(dict.fromkeys(ft_artists))

        # ---------------------------
        # REMOVE ARTIST NAMES / CLEAN TITLE
        # ---------------------------

        if unwanted_patterns is None:
            from utils import UNWANTED_PATTERNS
            unwanted_patterns = UNWANTED_PATTERNS

        for pattern in unwanted_patterns:
            title = re.sub(pattern, '', title, flags=re.IGNORECASE)

        if artist:
            title = re.sub(
                rf'^{re.escape(artist)}\s*[,\.\-–—]\s*',
                '',
                title,
                flags=re.IGNORECASE
            )
            title = re.sub(
                rf'{re.escape(artist)}\s*(?:&|and)\s+[^-\(\[]+',
                '',
                title,
                flags=re.IGNORECASE
            )
            title = re.sub(
                rf'\b{re.escape(artist)}\b',
                '',
                title,
                flags=re.IGNORECASE
            )


            # --------------------------------------
            # REMOVE FEATURE TAGS FROM TITLE
            # --------------------------------------

            # Remove (feat X), [feat X]
            title = re.sub(
                r'[\(\[]\s*(?:feat|ft|featuring)\.?\s*.*?[\)\]]',
                '',
                title,
                flags=re.IGNORECASE
            )

            # Remove standalone: feat. X, ft. X, featuring X
            title = re.sub(
                r'(?:feat|ft|featuring)\.?\s+[^-\(\[]+',
                '',
                title,
                flags=re.IGNORECASE
            )

            # Remove leftover dangling parentheses/brackets/spaces
            title = re.sub(r'\(\s*\)', '', title)
            title = re.sub(r'\[\s*\]', '', title)


        # Clean whitespace + punctuation
        title = re.sub(r'\s+', ' ', title).strip(" -_,;:.()[]")

        # ---------------------------
        # UPDATE COMPOSER FIELD
        # ---------------------------

        existing = [c.strip() for c in composer.split(',') if c.strip()] if composer else []
        for ft in ft_artists:
            if ft and not any(ft.lower() == e.lower() for e in existing):
                existing.append(ft)

        updated_composer = ", ".join(existing) if existing else ""

        return title, updated_composer, ft_artists

    
    @staticmethod
    def apply_cleaned_titles(cleaned_data):
        from mutagen import File as MutagenFile
        saved_count = 0

        for path, data in cleaned_data.items():
            try:
                metadata = {
                    "title": data["title"],
                    "composer": data["composer"],
                    "featuring": data["featuring"],     # <-- SEND THIS
                    "comment": data["featuring"],       # <-- optional if you want mirroring
                }

                MetadataManager.write_metadata(
                    path,
                    metadata,
                    cover_data=None,
                    allow_blanks=True
                )

                saved_count += 1

            except Exception as e:
                print(f"Error saving {path}: {e}")

        return saved_count

