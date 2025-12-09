"""
Tag Inference - Smart metadata cleaning and inference from filenames and existing tags
"""
import os
import re
from collections import Counter


class TagInference:
    """Infers and cleans metadata from filenames and existing tags"""
    
    # Noise patterns to remove from titles (case-insensitive)
    NOISE_PATTERNS = [
        r'\(official\s+(?:music\s+)?video\)',
        r'\(official\s+lyric\s+video\)',
        r'\(official\s+audio\)',
        r'\(official\s+visualizer\)',
        r'\(lyric\s+video\)',
        r'\(music\s+video\)',
        r'\(audio\)',
        r'\(visualizer\)',
        r'\[official\s+(?:music\s+)?video\]',
        r'\[official\s+lyric\s+video\]',
        r'\[official\s+audio\]',
        r'\[\d+k\s+upgrade\]',
        r'\(video\s+oficial[^)]*\)',
        r'\+\s*traducción',
        r'\+\s*letra',
        r'music\s+from\s+"[^"]*"',
        r'\s*-?\s*topic$',
    ]
    
    # Patterns that indicate supporting artists (keep these)
    FEATURE_INDICATORS = [
        r'\bfeat\.?\b',
        r'\bft\.?\b',
        r'\bwith\b',
        r'\bx\b',
    ]
    
    @staticmethod
    def analyze_folder(file_paths, metadata_manager):
        """
        Analyze a folder of files to infer artist/title patterns
        Returns dict of {file_path: {'artist': str, 'title': str, 'composer': str}}
        """
        if not file_paths:
            return {}
        
        print("\n=== ANALYZING FOLDER ===")
        
        # Step 1: Extract filename patterns
        filename_data = []
        for path in file_paths:
            filename = os.path.splitext(os.path.basename(path))[0]
            metadata = metadata_manager.read_metadata(path) or {}
            
            # Check for hyphen separator
            if ' - ' in filename or '-' in filename:
                # Try with spaces first
                if ' - ' in filename:
                    parts = filename.split(' - ', 1)
                else:
                    parts = filename.split('-', 1)
                
                if len(parts) == 2:
                    left = parts[0].strip()
                    right = parts[1].strip()
                    
                    filename_data.append({
                        'path': path,
                        'filename': filename,
                        'left': left,
                        'right': right,
                        'metadata': metadata
                    })
            else:
                # No hyphen, assume whole filename is title
                filename_data.append({
                    'path': path,
                    'filename': filename,
                    'left': None,
                    'right': filename,
                    'metadata': metadata
                })
        
        # Step 2: Determine which side is artist
        artist_side = TagInference._determine_artist_side(filename_data)
        
        print(f"Determined artist side: {artist_side}")
        
        # Step 3: Process each file
        results = {}
        for item in filename_data:
            result = TagInference._process_file(item, artist_side, metadata_manager)
            results[item['path']] = result
        
        return results
    
    @staticmethod
    def _determine_artist_side(filename_data):
        """
        Determine if artist is on left or right side of hyphen
        Returns: 'left', 'right', or 'unknown'
        """
        if not filename_data:
            return 'unknown'
        
        # Count how many times each side appears across files
        left_counter = Counter()
        right_counter = Counter()
        
        for item in filename_data:
            if item['left']:
                # Extract main artist (before first comma, but preserve &)
                left_main = TagInference._normalize_for_comparison(item['left'].split(',')[0].strip())
                left_counter[left_main] += 1
                
                right_main = TagInference._normalize_for_comparison(item['right'].split(',')[0].strip())
                right_counter[right_main] += 1
        
        if not left_counter and not right_counter:
            return 'unknown'
        
        # Get most common on each side
        most_common_left = left_counter.most_common(1)
        most_common_right = right_counter.most_common(1)
        
        total_files = len(filename_data)
        threshold = 0.3  # 30% threshold
        
        left_score = most_common_left[0][1] / total_files if most_common_left else 0
        right_score = most_common_right[0][1] / total_files if most_common_right else 0
        
        print(f"Left score: {left_score:.2%} ({most_common_left[0][0] if most_common_left else 'none'})")
        print(f"Right score: {right_score:.2%} ({most_common_right[0][0] if most_common_right else 'none'})")
        
        # If left side has higher repetition, it's likely the artist
        if left_score >= threshold and left_score > right_score:
            return 'left'
        elif right_score >= threshold and right_score > left_score:
            return 'right'
        else:
            # Default: assume left side is artist (standard format: "Artist - Title")
            return 'left'
    
    @staticmethod
    def _normalize_for_comparison(text):
        """Normalize text for comparison (lowercase, no underscores, no extra spaces)"""
        return re.sub(r'\s+', ' ', text.replace('_', ' ')).strip().lower()
    
    @staticmethod
    def _process_file(item, artist_side, metadata_manager):
        """Process a single file and extract clean metadata"""
        filename = item['filename']
        left = item['left']
        right = item['right']
        existing_meta = item['metadata']
        
        # Determine raw artist and title from filename
        if artist_side == 'left' and left:
            raw_artist = left
            raw_title = right
        elif artist_side == 'right' and right:
            raw_artist = right
            raw_title = left if left else right
        else:
            # No clear artist, try to use existing metadata or filename
            raw_artist = existing_meta.get('artist', '')
            raw_title = right or filename
        
        # Replace underscores with spaces in both fields
        raw_artist = raw_artist.replace('_', ' ').strip()
        raw_title = raw_title.replace('_', ' ').strip()
        
        # Clean existing artist metadata if it's junky
        if existing_meta.get('artist'):
            cleaned_existing = TagInference._clean_junky_artist(existing_meta['artist'])
            if cleaned_existing and not raw_artist:
                raw_artist = cleaned_existing
        
        # Parse artist field
        artist_info = TagInference._parse_artists(raw_artist)
        main_artist = artist_info['main']
        all_artists = artist_info['all_artists']
        
        # Clean title and extract features from it
        clean_title, title_features = TagInference._clean_title(raw_title, all_artists)
        
        # Combine all artists (from artist field + features from title)
        all_featured = list(all_artists)
        if title_features:
            # Add features that aren't already in the artist list
            for feat in title_features:
                feat_normalized = TagInference._normalize_for_comparison(feat)
                if not any(TagInference._normalize_for_comparison(a) == feat_normalized for a in all_featured):
                    all_featured.append(feat)
        
        # Build composer field: only add if there are supporting artists
        composer = ''
        if len(all_featured) > 1:
            # Multiple artists, include all in composer
            composer = ', '.join(all_featured)
        
        return {
            'artist': main_artist,
            'title': clean_title,
            'composer': composer
        }
    
    @staticmethod
    def _parse_artists(artist_string):
        """
        Parse artist string into main artist and all artists
        Handles complex cases like "Artist1 & Artist2 & Artist3"
        Returns: {'main': str, 'all_artists': [str]}
        """
        if not artist_string:
            return {'main': '', 'all_artists': []}
        
        # Check for comma-separated artists first (highest priority)
        if ',' in artist_string:
            parts = [p.strip() for p in artist_string.split(',')]
            # Filter out obvious junk (very long strings, contains weird chars)
            valid_parts = []
            for part in parts:
                # Stop at first sign of junk (sentences, weird formatting)
                if len(part) > 50 or any(indicator in part.lower() for indicator in ['recorded at', 'mixed by', 'endorsed by', 'http://', 'https://']):
                    break
                valid_parts.append(part)
            
            if valid_parts:
                return {
                    'main': valid_parts[0],
                    'all_artists': valid_parts
                }
        
        # Check for multiple & (like "Artist1 & Artist2 & Artist3")
        # Split and count the &'s
        and_parts = re.split(r'\s+&\s+', artist_string)
        
        if len(and_parts) > 2:
            # More than 2 parts means multiple &'s
            # First N-1 are main artists, last is feature
            # e.g., "Romeo Santos & Prince Royce & Dalvin" 
            # → main: "Romeo Santos & Prince Royce", all: ["Romeo Santos & Prince Royce", "Dalvin"]
            main_artist = ' & '.join(and_parts[:-1])
            all_artists = [main_artist] + [and_parts[-1]]
            
            return {
                'main': main_artist,
                'all_artists': all_artists
            }
        
        # Single artist or duo (0 or 1 &)
        return {
            'main': artist_string.strip(),
            'all_artists': [artist_string.strip()]
        }
    
    @staticmethod
    def _clean_junky_artist(artist_string):
        """Clean junky artist metadata (like The Marías example)"""
        if not artist_string or len(artist_string) < 100:
            return artist_string
        
        # Split by comma
        parts = [p.strip() for p in artist_string.split(',')]
        
        # Take only parts that look like artist names (short, no sentences)
        clean_parts = []
        for part in parts:
            # Stop at first junk indicator
            if any(indicator in part.lower() for indicator in [
                'recorded at', 'mixed by', 'mastered by', 'produced by',
                'endorsed by', 'apollo twin', 'pro tools', 'accompanied by',
                'http://', 'https://'
            ]):
                break
            
            # Only keep reasonable length names
            if len(part) < 50:
                clean_parts.append(part)
        
        return ', '.join(clean_parts) if clean_parts else artist_string
    
    @staticmethod
    def _clean_title(title_string, known_artists=None):
        """
        Clean title by removing noise and handling features
        Returns: (cleaned_title, [featured_artists])
        """
        if not title_string:
            return '', []
        
        original = title_string
        cleaned = title_string
        featured_artists = []
        
        # Remove noise patterns (case-insensitive)
        for pattern in TagInference.NOISE_PATTERNS:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
        
        # Handle "Artist - Title" format in the title field itself
        # Check if title contains artist name followed by dash
        if ' - ' in cleaned and known_artists:
            parts = cleaned.split(' - ', 1)
            if len(parts) == 2:
                potential_artists = parts[0]
                potential_title = parts[1]
                
                # Check if first part matches any known artist
                potential_normalized = TagInference._normalize_for_comparison(potential_artists)
                for artist in known_artists:
                    if artist and TagInference._normalize_for_comparison(artist) == potential_normalized:
                        # First part is the artist, use only the title part
                        cleaned = potential_title
                        break
        
        # Extract features from title (feat., ft., with, x)
        feat_pattern = r'\b(?:feat\.?|ft\.?|with|x)\s+([^()]+?)(?:\s*[\(\[]|$)'
        matches = re.finditer(feat_pattern, cleaned, re.IGNORECASE)
        
        for match in matches:
            feat_text = match.group(1).strip()
            # Split by commas or &
            feat_artists = re.split(r',|\s+&\s+', feat_text)
            featured_artists.extend([f.strip() for f in feat_artists if f.strip()])
        
        # Remove the feature mentions from title (but keep the base title)
        cleaned = re.sub(feat_pattern, '', cleaned, flags=re.IGNORECASE)
        
        # Clean up extra whitespace and punctuation
        cleaned = re.sub(r'\s+', ' ', cleaned)  # Multiple spaces to single
        cleaned = cleaned.strip()
        
        # Remove trailing punctuation from incomplete removals
        cleaned = re.sub(r'\s*[(\[]\s*$', '', cleaned)  # Trailing open parens/brackets
        
        # Final validation - if we removed everything, return original
        if not cleaned or len(cleaned) < 2:
            return original, []
        
        return cleaned, featured_artists
    
    @staticmethod
    def clean_filename(filename):
        """Clean filename by removing common junk patterns and underscores"""
        # Remove extension
        name = os.path.splitext(filename)[0]
        
        # Replace underscores with spaces
        name = name.replace('_', ' ')
        
        # Apply same noise removal as titles
        for pattern in TagInference.NOISE_PATTERNS:
            name = re.sub(pattern, '', name, flags=re.IGNORECASE)
        
        # Clean up
        name = re.sub(r'\s+', ' ', name).strip()
        name = re.sub(r'\s*[(\[]\s*$', '', name)
        
        return name if name else os.path.splitext(filename)[0]
    
    @staticmethod
    def batch_clean_files(file_paths, metadata_manager):
        """
        Main entry point for batch cleaning
        Returns: dict of {path: {'artist': str, 'title': str, 'composer': str}}
        """
        return TagInference.analyze_folder(file_paths, metadata_manager)
    
    @staticmethod
    def apply_cleaned_metadata(cleaned_data, metadata_manager):
        """
        Apply cleaned metadata to files
        Returns: number of files successfully updated
        """
        success_count = 0
        
        for path, clean_meta in cleaned_data.items():
            try:
                # Read existing metadata
                existing = metadata_manager.read_metadata(path) or {}
                
                # Update with cleaned values (only if they have content)
                if clean_meta.get('artist'):
                    existing['artist'] = clean_meta['artist']
                
                if clean_meta.get('title'):
                    existing['title'] = clean_meta['title']
                
                # Only set composer if there's actually content
                if clean_meta.get('composer'):
                    existing['composer'] = clean_meta['composer']
                else:
                    # Clear composer if no features
                    existing.pop('composer', None)
                
                # Write back
                if metadata_manager.write_metadata(path, existing):
                    success_count += 1
                    print(f"✓ Cleaned: {os.path.basename(path)}")
                else:
                    print(f"✗ Failed: {os.path.basename(path)}")
                    
            except Exception as e:
                print(f"✗ Error processing {os.path.basename(path)}: {e}")
        
        return success_count