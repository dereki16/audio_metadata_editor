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
        """Read metadata using Mutagen, filtering out garbage track numbers.
        Robustly extract comment from multiple possible locations (easy tags, raw ID3 COMM, synopsis/description).
        """
        try:
            audio = MutagenFile(file_path, easy=True)
            if audio is None:
                return {}

            md = {}

            def get_easy(key):
                return audio.get(key, [""])[0] if key in audio else ""

            md["title"] = get_easy("title")
            md["artist"] = get_easy("artist")
            md["album"] = get_easy("album")
            md["album_artist"] = get_easy("albumartist")

            # Primary easy-mode comment
            comment_val = get_easy("comment")

            # If empty, try raw ID3 COMM frames (for mp3)
            if not comment_val:
                try:
                    from mutagen.id3 import ID3, COMM
                    id3 = ID3(file_path)
                    comm_frames = id3.getall("COMM")
                    if comm_frames:
                        # Choose first non-empty COMM text
                        for c in comm_frames:
                            if c.text:
                                comment_val = c.text[0] if isinstance(c.text, (list, tuple)) else str(c.text)
                                if comment_val:
                                    break
                except Exception:
                    # ignore if not mp3 or no ID3
                    pass

            # If still empty, check common alternative tags often seen in ffmpeg output
            if not comment_val:
                try:
                    raw = MutagenFile(file_path)  # non-easy
                    if raw and hasattr(raw, "tags") and raw.tags:
                        # try common keys that ffmpeg prints: 'synopsis', 'description', 'purl'
                        for key in ("synopsis", "description", "purl"):
                            if key in raw.tags:
                                v = raw.tags.get(key)
                                # value may be list or single value
                                if isinstance(v, (list, tuple)) and len(v) > 0:
                                    comment_val = str(v[0])
                                    break
                                elif v:
                                    comment_val = str(v)
                                    break
                except Exception:
                    pass

            md["comment"] = comment_val or ""

            # track handling (your existing logic)
            track_raw = get_easy("tracknumber")
            if track_raw:
                track_num = track_raw.split('/')[0].strip() if '/' in track_raw else track_raw.strip()
                try:
                    track_int = int(track_num)
                    if track_int == 63:
                        md["track"] = ""
                        print(f"Filtered out garbage track number 63 from {os.path.basename(file_path)}")
                    elif 1 <= track_int <= 999:
                        md["track"] = track_num
                    else:
                        md["track"] = ""
                        print(f"Ignoring invalid track number {track_int} for {os.path.basename(file_path)}")
                except (ValueError, TypeError):
                    md["track"] = ""
            else:
                md["track"] = ""

            # disc
            disc_raw = get_easy("discnumber")
            if disc_raw:
                disc_num = disc_raw.split('/')[0].strip() if '/' in disc_raw else disc_raw.strip()
                try:
                    disc_int = int(disc_num)
                    if 1 <= disc_int <= 99:
                        md["disc"] = disc_num
                    else:
                        md["disc"] = ""
                except (ValueError, TypeError):
                    md["disc"] = ""
            else:
                md["disc"] = ""

            md["year"] = get_easy("date")
            md["genre"] = get_easy("genre")
            md["composer"] = get_easy("composer")

            # Add length if available
            try:
                md["length"] = round(audio.info.length, 2)
            except Exception:
                md["length"] = ""

            # Debug print for comment
            print(f"DEBUG Comment for {os.path.basename(file_path)}: '{md['comment']}'")
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
    # WRITE MP3
    # -------------------------------------------------------
    @staticmethod
    def _write_mp3(file_path, metadata, cover_data, allow_blanks=True):
        try:
            # Load EasyID3 for text tags (create if missing)
            try:
                audio_easy = EasyID3(file_path)
            except ID3NoHeaderError:
                # create empty tags then re-open
                audio_easy = EasyID3()
                audio_easy.save(file_path)
                audio_easy = EasyID3(file_path)

            # Map of field names => EasyID3 keys
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

            # Set or clear fields in EasyID3
            for key, atom in field_map.items():
                val = metadata.get(key, None)
                if val is None:
                    continue  # skip modification
                if val != "":
                    audio_easy[atom] = str(val)
                else:
                    # empty string: clear if allowed
                    if allow_blanks and atom in audio_easy:
                        del audio_easy[atom]

            # Also handle easy mode 'comment' if present (so both readers see it)
            if "comment" in metadata:
                cval = metadata.get("comment", None)
                if cval is None:
                    pass
                elif cval != "":
                    # EasyID3 uses 'comment' key (some versions) — set as list
                    try:
                        audio_easy["comment"] = str(cval)
                    except Exception:
                        # fallback: set TXXX/COMM via raw id3 later
                        pass
                else:
                    # empty -> remove from easy tags if exists
                    if allow_blanks and "comment" in audio_easy:
                        del audio_easy["comment"]

            # Save easy tags first
            audio_easy.save(file_path)

            # Now handle raw ID3 frames for robust compatibility (COMM, TXXX FEATURING, APIC)
            from mutagen.id3 import ID3, COMM, APIC, TXXX
            id3 = ID3(file_path)

            # COMMENT (COMM) - clear existing and add if provided
            if "comment" in metadata:
                # remove all existing COMM frames
                for k in list(id3.keys()):
                    if k.startswith("COMM"):
                        del id3[k]
                # add new one if non-empty
                if metadata.get("comment"):
                    id3.add(COMM(
                        encoding=3,
                        lang='eng',
                        desc='',
                        text=str(metadata.get("comment"))
                    ))

            # FEATURE tag stored as TXXX:FEATURING (optional)
            if "featuring" in metadata:
                # remove existing TXXX:FEATURING frames
                for k in list(id3.keys()):
                    if k.startswith("TXXX:FEATURING"):
                        del id3[k]
                if metadata.get("featuring"):
                    id3.add(TXXX(encoding=3, desc="FEATURING", text=str(metadata.get("featuring"))))

            # Album art (APIC)
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

            # Save raw id3
            id3.save(v2_version=3)
            return True

        except Exception as e:
            print("MP3 write error:", e)
            import traceback
            traceback.print_exc()
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
            for key, atom in field_map.items():
                val = metadata.get(key, None)

                # None → skip (do not modify)
                if val is None:
                    continue

                # Non-empty → write it
                if val != "":
                    audio[atom] = str(val)
                    continue

                # Empty "" + allow_blanks → clear
                if allow_blanks and atom in audio:
                    del audio[atom]


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
                    audio[atom] = [str(val)]  # FIXED: M4A needs list format
                    continue

                # Empty "" + allow_blanks → clear
                if allow_blanks and atom in audio:
                    del audio[atom]

            # Custom featuring field
            if "featuring" in metadata:
                featuring_atom = '----:com.apple.iTunes:FEATURING'
                if metadata["featuring"]:
                    audio[featuring_atom] = [metadata["featuring"].encode('utf-8')]
                elif allow_blanks and featuring_atom in audio:
                    del audio[featuring_atom]

            # Track number - ONLY write if explicitly provided
            if "track" in metadata:
                t = metadata["track"]
                if t and str(t).strip():  # Only if non-empty
                    t = str(t).strip()
                    try:
                        if "/" in t:
                            a, b = t.split("/", 1)
                            audio["trkn"] = [(int(a), int(b))]
                        else:
                            audio["trkn"] = [(int(t), 0)]
                    except (ValueError, TypeError):
                        # Invalid track number format, skip it
                        pass
                elif allow_blanks and "trkn" in audio:
                    del audio["trkn"]

            # Disc number - ONLY write if explicitly provided
            if "disc" in metadata:
                d = metadata["disc"]
                if d and str(d).strip():  # Only if non-empty
                    d = str(d).strip()
                    try:
                        if "/" in d:
                            a, b = d.split("/", 1)
                            audio["disk"] = [(int(a), int(b))]
                        else:
                            audio["disk"] = [(int(d), 0)]
                    except (ValueError, TypeError):
                        # Invalid disc number format, skip it
                        pass
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