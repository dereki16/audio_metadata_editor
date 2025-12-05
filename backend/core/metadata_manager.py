"""
Metadata Manager - Handles reading and writing audio file metadata
"""
import os
from io import BytesIO
from mutagen import File as MutagenFile
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3, ID3NoHeaderError, APIC, COMM
from mutagen.flac import FLAC, Picture
from mutagen.mp4 import MP4, MP4Cover
from PIL import Image

class MetadataManager:

    def read_metadata(self, file_path):
        """Read metadata using Mutagen"""
        try:
            audio = MutagenFile(file_path, easy=True)
            if audio is None:
                return {}

            md = {}

            def get(key):
                return audio.get(key, [""])[0] if key in audio else ""

            md["title"] = get("title")
            md["artist"] = get("artist")
            md["album"] = get("album")
            md["album_artist"] = get("albumartist")
            md["track"] = get("tracknumber")
            md["disc"] = get("discnumber")
            md["year"] = get("date")
            md["genre"] = get("genre")
            md["comment"] = get("comment")
            md["composer"] = get("composer")

            # Add length if available
            try:
                md["length"] = round(audio.info.length, 2)
            except:
                md["length"] = ""

            return md

        except Exception as e:
            print(f"Metadata read error for {file_path}: {e}")
            return {}

    # -------------------------------------------------------
    # WRITE METADATA (with blank field support)
    # -------------------------------------------------------
    @staticmethod
    def write_metadata(file_path, metadata, cover_data=None, allow_blanks=True):
        """
        Write metadata to file. 
        
        Args:
            file_path: Path to audio file
            metadata: Dictionary of metadata fields
            cover_data: Optional cover image bytes
            allow_blanks: If True, empty strings will clear the field
        """
        try:
            ext = os.path.splitext(file_path)[1].lower()

            if ext == ".mp3":
                return MetadataManager._write_mp3(file_path, metadata, cover_data, allow_blanks)
            elif ext == ".flac":
                return MetadataManager._write_flac(file_path, metadata, cover_data, allow_blanks)
            elif ext == ".m4a":
                return MetadataManager._write_m4a(file_path, metadata, cover_data, allow_blanks)
            else:
                return MetadataManager._write_generic(file_path, metadata, allow_blanks)

        except Exception as e:
            print(f"Error writing metadata: {e}")
            return False

    # -------------------------------------------------------
    # MP3 WRITING
    # -------------------------------------------------------
    @staticmethod
    def _write_mp3(file_path, metadata, cover_data, allow_blanks=True):
        try:
            # Load EasyID3 for text tags
            try:
                audio = EasyID3(file_path)
            except ID3NoHeaderError:
                audio = EasyID3()

            # Map of field names
            field_map = {
                "title": "title",
                "artist": "artist",
                "album": "album",
                "album_artist": "albumartist",
                "track": "tracknumber",
                "disc": "discnumber",
                "year": "date",
                "genre": "genre",
                "composer": "composer"
            }

            # Set or clear fields
            for key, easy_key in field_map.items():
                val = metadata.get(key, None)

                # None → skip (do not modify)
                if val is None:
                    continue

                # Non-empty → write it
                if val != "":
                    audio[easy_key] = str(val)
                    continue

                # Empty "" + allow_blanks → clear
                if allow_blanks and easy_key in audio:
                    del audio[easy_key]


            audio.save(file_path)

            # Handle comment, featuring, and cover using raw ID3
            id3 = ID3(file_path)

            # Comment
            if "comment" in metadata:
                # Clear existing comments
                for k in list(id3.keys()):
                    if k.startswith("COMM"):
                        del id3[k]
                
                # Add new comment if not blank
                if metadata["comment"]:
                    id3.add(COMM(
                        encoding=3,
                        lang='eng',
                        desc='',
                        text=metadata["comment"]
                    ))

            # Custom "Featuring" field (using TXXX frame)
            if "featuring" in metadata:
                from mutagen.id3 import TXXX
                # Clear existing featuring tags
                for k in list(id3.keys()):
                    if k.startswith("TXXX:FEATURING"):
                        del id3[k]
                
                # Add featuring tag if not blank
                if metadata["featuring"]:
                    id3.add(TXXX(
                        encoding=3,
                        desc='FEATURING',
                        text=metadata["featuring"]
                    ))

            # Album art
            if cover_data:
                for k in list(id3.keys()):
                    if k.startswith("APIC"):
                        del id3[k]

                id3.add(APIC(
                    encoding=3,
                    mime='image/jpeg',
                    type=3,
                    desc='Cover',
                    data=cover_data
                ))

            id3.save(v2_version=3)
            return True

        except Exception as e:
            print("MP3 write error:", e)
            return False

    # -------------------------------------------------------
    # FLAC WRITING
    # -------------------------------------------------------
    @staticmethod
    def _write_flac(file_path, metadata, cover_data, allow_blanks=True):
        try:
            audio = FLAC(file_path)

            # Set or clear fields
            for key, val in metadata.items():
                if key == "featuring":  # Custom field
                    if val:
                        audio["FEATURING"] = str(val)
                    elif allow_blanks and "FEATURING" in audio:
                        del audio["FEATURING"]
                elif val:  # Non-empty value
                    audio[key] = str(val)
                elif allow_blanks and key in audio:  # Clear field
                    del audio[key]

            if cover_data:
                pic = Picture()
                pic.data = cover_data
                pic.type = 3
                pic.mime = 'image/jpeg'
                audio.clear_pictures()
                audio.add_picture(pic)

            audio.save()
            return True

        except Exception as e:
            print("FLAC write error:", e)
            return False

    # -------------------------------------------------------
    # M4A WRITING
    # -------------------------------------------------------
    @staticmethod
    def _write_m4a(file_path, metadata, cover_data, allow_blanks=True):
        try:
            audio = MP4(file_path)

            atom_map = {
                'title': '\xa9nam',
                'artist': '\xa9ART',
                'album': '\xa9alb',
                'album_artist': 'aART',
                'genre': '\xa9gen',
                'year': '\xa9day',
                'comment': '\xa9cmt',
                'composer': '\xa9wrt',
            }

            # Set or clear text fields
            for key, atom in atom_map.items():
                val = metadata.get(key, None)

                # None → skip (do not modify)
                if val is None:
                    continue

                # Non-empty → write it
                if val != "":
                    audio[easy_key] = str(val)
                    continue

                # Empty "" + allow_blanks → clear
                if allow_blanks and easy_key in audio:
                    del audio[easy_key]


            # Custom featuring field
            if "featuring" in metadata:
                featuring_atom = '----:com.apple.iTunes:FEATURING'
                if metadata["featuring"]:
                    audio[featuring_atom] = [metadata["featuring"].encode('utf-8')]
                elif allow_blanks and featuring_atom in audio:
                    del audio[featuring_atom]

            # Track number
            if "track" in metadata:
                t = metadata["track"]
                if t:
                    t = str(t)
                    if "/" in t:
                        a, b = t.split("/")
                        audio["trkn"] = [(int(a), int(b))]
                    else:
                        audio["trkn"] = [(int(t), 0)]
                elif allow_blanks and "trkn" in audio:
                    del audio["trkn"]

            # Disc number
            if "disc" in metadata:
                d = metadata["disc"]
                if d:
                    d = str(d)
                    if "/" in d:
                        a, b = d.split("/")
                        audio["disk"] = [(int(a), int(b))]
                    else:
                        audio["disk"] = [(int(d), 0)]
                elif allow_blanks and "disk" in audio:
                    del audio["disk"]

            # Cover
            if cover_data:
                audio["covr"] = [
                    MP4Cover(cover_data, imageformat=MP4Cover.FORMAT_JPEG)
                ]

            audio.save()
            return True

        except Exception as e:
            print("M4A write error:", e)
            return False

    # -------------------------------------------------------
    # GENERIC MUTAGEN WRITING
    # -------------------------------------------------------
    @staticmethod
    def _write_generic(file_path, metadata, allow_blanks=True):
        try:
            audio = MutagenFile(file_path, easy=True)
            if not audio:
                return False

            for key, val in metadata.items():
                if val:  # Non-empty value
                    audio[key] = str(val)
                elif allow_blanks and key in audio:  # Clear field
                    del audio[key]

            audio.save()
            return True

        except Exception:
            return False

    # -------------------------------------------------------
    # COVER EXTRACTION
    # -------------------------------------------------------
    @staticmethod
    def extract_cover(file_path):
        try:
            audio = MutagenFile(file_path)
            if not audio:
                return None

            # MP3
            if hasattr(audio, "tags") and audio.tags:
                for key in audio.tags.keys():
                    if key.startswith("APIC"):
                        return audio.tags[key].data

            # FLAC
            if hasattr(audio, "pictures") and audio.pictures:
                return audio.pictures[0].data

            # M4A
            if hasattr(audio, "tags") and "covr" in audio.tags:
                return bytes(audio["covr"][0])

        except Exception as e:
            print("Cover extraction error:", e)

        return None

    # -------------------------------------------------------
    # PIXMAP
    # -------------------------------------------------------
    @staticmethod
    def get_cover_as_pixmap(file_path, size=400):
        from PySide6.QtGui import QPixmap
        from PIL.ImageQt import ImageQt

        cover = MetadataManager.extract_cover(file_path)
        if not cover:
            return None

        try:
            img = Image.open(BytesIO(cover))
            img = img.convert("RGB")
            img.thumbnail((size, size))
            return QPixmap.fromImage(ImageQt(img))

        except Exception as e:
            print("Pixmap error:", e)
            return None