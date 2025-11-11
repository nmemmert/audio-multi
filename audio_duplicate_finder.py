import os
import hashlib
import contextlib
import threading
import queue
import csv
import tkinter as tk
from tkinter import scrolledtext
from tkinter import filedialog, ttk, messagebox
import requests
from bs4 import BeautifulSoup
import re
from mutagen import File as MutagenFile
import musicbrainzngs
import pygame
import json
import random

# Windows 11 Inspired Modern Styling
MODERN_FONT = ("Segoe UI Variable", 10)
MODERN_FONT_BOLD = ("Segoe UI Variable", 10, "bold")
MODERN_FONT_LARGE = ("Segoe UI Variable", 12, "bold")
HEADER_FONT = ("Segoe UI Variable", 16, "bold")
TITLE_FONT = ("Segoe UI Variable", 14, "bold")

# Windows 11 Color Palette
PRIMARY_COLOR = "#005FB8"  # Windows 11 accent blue
SECONDARY_COLOR = "#0078D4"  # Lighter blue
ACCENT_COLOR = "#106EBE"  # Even lighter blue
SUCCESS_COLOR = "#0F7B0F"  # Windows 11 green
WARNING_COLOR = "#C42B1C"  # Windows 11 red
ERROR_COLOR = "#D13438"  # Error red

# Mica-inspired backgrounds
BG_COLOR = "#F8F9FA"  # Very light gray with slight blue tint
FRAME_BG = "#FFFFFF"  # Pure white for cards
CARD_BG = "#FAFAFA"  # Slightly off-white for depth
BUTTON_BG = "#F3F3F3"  # Light gray buttons
BUTTON_HOVER = "#E5E5E5"  # Hover state
BUTTON_ACTIVE = "#CCCCCC"  # Active/pressed state

# Text colors
TEXT_PRIMARY = "#202020"  # Near black
TEXT_SECONDARY = "#5D5D5D"  # Medium gray
TEXT_MUTED = "#8A8A8A"  # Light gray

# Border colors
BORDER_LIGHT = "#E5E5E5"
BORDER_MEDIUM = "#CCCCCC"
BORDER_DARK = "#8A8A8A"

def audio_fingerprint(path):
    """Generate a fingerprint based on file size and partial content hash."""
    try:
        # Get file size
        file_size = os.path.getsize(path)
        
        # Read first and last chunks of file for content hash
        with open(path, 'rb') as f:
            # Read first 64KB
            f.seek(0)
            first_chunk = f.read(65536)
            
            # Read last 64KB if file is large enough
            if file_size > 131072:  # 128KB
                f.seek(-65536, 2)
                last_chunk = f.read(65536)
            else:
                last_chunk = b''
            
            # Create hash from size + first chunk + last chunk
            hasher = hashlib.sha256()
            hasher.update(str(file_size).encode())
            hasher.update(first_chunk)
            hasher.update(last_chunk)
            
            return hasher.hexdigest()
    except Exception as e:
        # Fallback to simple file hash if partial reading fails
        return hashlib.sha256(str(os.path.getsize(path)).encode()).hexdigest()

def download_audio_files(url, download_folder, existing_folder, msg_queue):
    """Download audio files from a webpage, checking for duplicates in existing folder."""
    try:
        # Create download folder
        os.makedirs(download_folder, exist_ok=True)
        msg_queue.put(f"Created download folder: {download_folder}")
        
        # Build fingerprint cache for existing files if folder provided
        existing_fingerprints = {}
        if existing_folder and os.path.exists(existing_folder):
            msg_queue.put(f"Scanning existing files in: {existing_folder}")
            audio_extensions = ('.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a', '.wma', '.aiff')
            
            for root, _, files in os.walk(existing_folder):
                for f in files:
                    if f.lower().endswith(audio_extensions):
                        full_path = os.path.join(root, f)
                        try:
                            fp = audio_fingerprint(full_path)
                            existing_fingerprints[fp] = full_path
                        except Exception as e:
                            msg_queue.put(f"Couldn't fingerprint {f}: {str(e)[:30]}...")
            
            msg_queue.put(f"Found {len(existing_fingerprints)} existing audio files to check against")
        
        # Fetch and parse the page
        msg_queue.put(f"Fetching page: {url}")
        response = requests.get(url, timeout=30)
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Find all audio links
        audio_links = []
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            text = a_tag.get_text().strip()
            if re.search(r"\.(mp3|m4a|wav|aac)$", href, re.IGNORECASE):
                full_url = href if href.startswith("http") else f"{url.rstrip('/')}/{href.lstrip('/')}"
                audio_links.append((full_url, text))
        
        msg_queue.put(f"Found {len(audio_links)} audio files to download")
        
        # Download each file
        successful_downloads = 0
        skipped_duplicates = 0
        corrupted_files = []
        
        for i, (link, text) in enumerate(audio_links):
            msg_queue.put(f"Processing {i+1}/{len(audio_links)}: {text[:50]}...")
            
            # Sanitize filename
            _, ext = os.path.splitext(link.split("/")[-1])
            safe_text = re.sub(r'[<>:"/\\|?*]', '_', text)
            filename = os.path.join(download_folder, safe_text + ext)
            
            # Check if file already exists in download folder
            if os.path.exists(filename):
                msg_queue.put(f"File already exists: {text}")
                continue
            
            try:
                # Download file to check for duplicates
                file_response = requests.get(link, timeout=30)
                
                # Integrity checks
                if file_response.status_code != 200:
                    msg_queue.put(f"Failed: HTTP {file_response.status_code} for {text}")
                    continue
                    
                content_length = file_response.headers.get('Content-Length')
                if content_length:
                    expected_size = int(content_length)
                    actual_size = len(file_response.content)
                    if actual_size != expected_size:
                        msg_queue.put(f"Corrupted: {text} (size mismatch)")
                        continue
                
                if len(file_response.content) == 0:
                    msg_queue.put(f"Empty file: {text}")
                    continue
                
                # Temporarily save file to check fingerprint
                temp_filename = filename + ".tmp"
                with open(temp_filename, "wb") as f:
                    f.write(file_response.content)
                
                # Check if this file is a duplicate of existing files
                if existing_fingerprints:
                    try:
                        file_fingerprint = audio_fingerprint(temp_filename)
                        if file_fingerprint in existing_fingerprints:
                            os.remove(temp_filename)
                            existing_file = existing_fingerprints[file_fingerprint]
                            msg_queue.put(f"Duplicate found: {text} matches {os.path.basename(existing_file)}")
                            skipped_duplicates += 1
                            continue
                    except Exception as e:
                        msg_queue.put(f"Error checking duplicate for {text}: {str(e)[:30]}...")
                
                # File is not a duplicate, keep it
                os.rename(temp_filename, filename)
                successful_downloads += 1
                msg_queue.put(f"Downloaded: {text} ({len(file_response.content)} bytes)")
                
                # Add to existing fingerprints to avoid downloading duplicates within this session
                try:
                    file_fingerprint = audio_fingerprint(filename)
                    existing_fingerprints[file_fingerprint] = filename
                except:
                    pass  # If fingerprinting fails, just continue
                
            except Exception as e:
                if os.path.exists(temp_filename):
                    try:
                        os.remove(temp_filename)
                    except:
                        pass
                msg_queue.put(f"Error downloading {text}: {str(e)[:50]}...")
        
        msg_queue.put(f"Download complete: {successful_downloads} downloaded, {skipped_duplicates} duplicates skipped")
        return successful_downloads, len(audio_links), skipped_duplicates
        
    except Exception as e:
        msg_queue.put(f"Download error: {str(e)}")
        return 0, 0, 0

def find_duplicates(folder1, folder2, msg_queue):
    fingerprints = {}
    duplicates = []
    audio_extensions = ('.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a', '.wma', '.aiff')
    processed_count = 0

    for folder in [folder1, folder2]:
        for root, _, files in os.walk(folder):
            for f in files:
                if f.lower().endswith(audio_extensions):
                    full_path = os.path.join(root, f)
                    try:
                        fp = audio_fingerprint(full_path)
                        processed_count += 1
                        if fp in fingerprints:
                            duplicates.append((fingerprints[fp], full_path))
                        else:
                            fingerprints[fp] = full_path
                    except Exception as e:
                        msg_queue.put(f"Skipped: {os.path.basename(full_path)} ({str(e)[:50]}...)")
    return duplicates, processed_count

def update_tree(duplicates):
    for row in tree.get_children():
        tree.delete(row)
    if duplicates:
        for d in duplicates:
            tree.insert("", tk.END, values=(d[0], d[1]))
    else:
        tk.messagebox.showinfo("Result", "No duplicates found")

def check_queue(msg_queue):
    try:
        while True:
            msg = msg_queue.get_nowait()
            text_output.insert(tk.END, msg + '\n')
            text_output.see(tk.END)
    except queue.Empty:
        pass
    root.after(100, lambda: check_queue(msg_queue))

def update_tree_and_enable(duplicates, button, processed_count):
    update_tree(duplicates)
    button.config(state='normal')
    status_label.config(text=f"Processed {processed_count} audio files.")

def export_csv():
    if not tree.get_children():
        tk.messagebox.showinfo("No Data", "No duplicates to export.")
        return
    from tkinter import filedialog
    file_path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
    if file_path:
        with open(file_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["Duplicate File 1", "Duplicate File 2"])
            for item in tree.get_children():
                writer.writerow(tree.item(item, 'values'))
        tk.messagebox.showinfo("Exported", f"Exported to {file_path}")

def delete_file(path):
    if tk.messagebox.askyesno("Confirm", f"Delete {path}?"):
        try:
            os.remove(path)
            tk.messagebox.showinfo("Deleted", f"Deleted {path}")
            # Remove from tree
            for item in tree.get_children():
                values = tree.item(item, 'values')
                if values[0] == path or values[1] == path:
                    tree.delete(item)
                    break
        except Exception as e:
            tk.messagebox.showerror("Error", f"Failed to delete: {e}")

def show_menu(event):
    selected = tree.selection()
    if selected:
        menu = tk.Menu(root, tearoff=0)
        values = tree.item(selected[0], 'values')
        menu.add_command(label="Delete File 1", command=lambda: delete_file(values[0]))
        menu.add_command(label="Delete File 2", command=lambda: delete_file(values[1]))
        menu.post(event.x_root, event.y_root)

def select_folder(entry_widget):
    folder = filedialog.askdirectory()
    if folder:
        entry_widget.delete(0, tk.END)
        entry_widget.insert(0, folder)

def run_download():
    url = url_var.get()
    download_folder = download_entry.get()
    existing_folder = existing_entry.get()
    
    if not url:
        messagebox.showerror("Error", "Please select or enter a URL")
        return
    if not download_folder:
        messagebox.showerror("Error", "Please specify a download folder")
        return
    
    # Disable download button
    download_button.config(state='disabled')
    status_label.config(text="Downloading...")
    
    msg_queue = queue.Queue()
    check_queue(msg_queue)
    
    def worker():
        successful, total, skipped = download_audio_files(url, download_folder, existing_folder, msg_queue)
        root.after(0, lambda: download_complete(successful, total, skipped))
    
    threading.Thread(target=worker, daemon=True).start()

def download_complete(successful, total, skipped):
    download_button.config(state='normal')
    status_label.config(text=f"Download complete: {successful}/{total} files, {skipped} duplicates skipped")

def select_download_folder():
    folder = filedialog.askdirectory()
    if folder:
        download_entry.delete(0, tk.END)
        download_entry.insert(0, folder)

def select_existing_folder():
    folder = filedialog.askdirectory()
    if folder:
        existing_entry.delete(0, tk.END)
        existing_entry.insert(0, folder)

def run_check():
    folder1 = entry1.get()
    folder2 = entry2.get()
    if not folder1 or not folder2:
        messagebox.showerror("Error", "Please select both folders")
        return

    # Get the button
    button = None
    for widget in frame.grid_slaves(row=2, column=1):
        if isinstance(widget, tk.Button):
            button = widget
            break
    button.config(state='disabled')
    status_label.config(text="Processing...")
    msg_queue = queue.Queue()
    check_queue(msg_queue)

    def worker():
        duplicates, processed_count = find_duplicates(folder1, folder2, msg_queue)
        root.after(0, lambda: update_tree_and_enable(duplicates, button, processed_count))

    threading.Thread(target=worker, daemon=True).start()

# Initialize MusicBrainz
musicbrainzngs.set_useragent("AudioDuplicateFinder", "1.0", "https://github.com/user/audio-finder")

def get_audio_metadata(file_path):
    """Extract metadata from audio file."""
    try:
        audio = MutagenFile(file_path, easy=True)
        if audio is None:
            return None
            
        metadata = {
            'filename': os.path.basename(file_path),
            'filepath': file_path,
            'title': audio.get('title', ['Unknown'])[0],
            'artist': audio.get('artist', ['Unknown'])[0],
            'album': audio.get('album', ['Unknown'])[0],
            'year': audio.get('date', ['Unknown'])[0],
            'genre': audio.get('genre', ['Unknown'])[0],
            'tracknumber': audio.get('tracknumber', [''])[0],
            'duration': getattr(audio.info, 'length', 0),
        }
        return metadata
    except Exception as e:
        return {
            'filename': os.path.basename(file_path),
            'filepath': file_path,
            'title': 'Error reading file',
            'artist': str(e),
            'album': '',
            'year': '',
            'genre': '',
            'tracknumber': '',
            'duration': 0,
        }

def parse_filename_metadata(filename):
    """Parse metadata information from filename using common patterns."""
    # Remove file extension
    name = os.path.splitext(filename)[0]
    
    # Common patterns for audio files
    patterns = [
        # Pattern: "Artist - Title"
        r'^(.+?)\s*-\s*(.+)$',
        # Pattern: "Artist_Title" (underscore)
        r'^(.+?)_(.+)$',
        # Pattern: "Track Number. Artist - Title"
        r'^\d+\.?\s*(.+?)\s*-\s*(.+)$',
        # Pattern: "Track Number - Artist - Title"
        r'^\d+\s*-\s*(.+?)\s*-\s*(.+)$',
        # Pattern: "Artist Title" (space separated, assume last word is title)
        r'^(.+?)\s+([^\s]+)$',
        # Pattern: "[Year] Artist - Title"
        r'^\[\d{4}\]\s*(.+?)\s*-\s*(.+)$',
        # Pattern: "(Album) Artist - Title"  
        r'^\(.+?\)\s*(.+?)\s*-\s*(.+)$'
    ]
    
    parsed = {'artist': '', 'title': '', 'album': ''}
    
    for pattern in patterns:
        match = re.match(pattern, name, re.IGNORECASE)
        if match:
            groups = match.groups()
            if len(groups) >= 2:
                artist = groups[0].strip()
                title = groups[1].strip()
                
                # Clean up common prefixes/suffixes
                artist = re.sub(r'^(the\s+)', '', artist, flags=re.IGNORECASE)
                title = re.sub(r'\s*\(.*?\)\s*$', '', title)  # Remove trailing parentheses
                title = re.sub(r'\s*\[.*?\]\s*$', '', title)  # Remove trailing brackets
                
                parsed['artist'] = artist
                parsed['title'] = title
                break
    
    # If no pattern matched, use filename as title
    if not parsed['title']:
        # Clean filename for title
        cleaned = re.sub(r'[\[\(].*?[\]\)]', '', name)  # Remove bracketed content
        cleaned = re.sub(r'^\d+\.?\s*', '', cleaned)    # Remove leading numbers
        cleaned = cleaned.strip()
        parsed['title'] = cleaned if cleaned else name
    
    return parsed

def enhance_metadata_with_filename(file_metadata):
    """Enhance existing metadata using filename information.""" 
    filename = os.path.basename(file_metadata['file_path'])
    filename_data = parse_filename_metadata(filename)
    
    enhanced = file_metadata.copy()
    
    # Use filename data if current metadata is missing or generic
    if not enhanced['artist'] or enhanced['artist'].lower() in ['unknown', '']:
        enhanced['artist'] = filename_data['artist']
        
    if not enhanced['title'] or enhanced['title'].lower() in ['unknown', '']:
        enhanced['title'] = filename_data['title']
        
    # Prefer filename data if it looks more complete
    if (filename_data['artist'] and filename_data['title'] and 
        len(filename_data['artist']) > 2 and len(filename_data['title']) > 2):
        if not enhanced['artist'] or len(enhanced['artist']) < 3:
            enhanced['artist'] = filename_data['artist']
        if not enhanced['title'] or len(enhanced['title']) < 3:
            enhanced['title'] = filename_data['title']
    
    return enhanced

def search_musicbrainz(artist, title, album=""):
    """Search MusicBrainz for track information with enhanced matching."""
    try:
        # Clean input data
        if artist:
            artist = artist.strip()
        if title:
            title = title.strip()
        if album:
            album = album.strip()
            
        if not artist or artist.lower() in ['unknown', ''] or not title or title.lower() in ['unknown', '']:
            return None
            
        # Try multiple search strategies for better matching
        search_attempts = [
            # Exact search
            {'artist': artist, 'recording': title, 'release': album if album and album.lower() != 'unknown' else ""},
            # Artist and title only (in case album is wrong)
            {'artist': artist, 'recording': title},
            # Fuzzy search - remove common words that might interfere
            {'artist': re.sub(r'\b(the|and|&|feat\.?|ft\.?)\b', '', artist, flags=re.IGNORECASE).strip(), 
             'recording': re.sub(r'\b(feat\.?|ft\.?|featuring)\b.*$', '', title, flags=re.IGNORECASE).strip()},
        ]
        
        for search_params in search_attempts:
            # Skip if we've removed too much
            if not search_params.get('artist') or not search_params.get('recording'):
                continue
                
            try:
                result = musicbrainzngs.search_recordings(
                    limit=5,
                    **search_params
                )
                
                if result['recording-list']:
                    # Score results based on similarity
                    best_match = None
                    best_score = 0
                    
                    for recording in result['recording-list']:
                        score = 0
                        rec_title = recording.get('title', '').lower()
                        rec_artist = ''
                        if recording.get('artist-credit'):
                            rec_artist = recording['artist-credit'][0]['artist']['name'].lower()
                        
                        # Simple scoring system
                        if rec_title == title.lower():
                            score += 50
                        elif title.lower() in rec_title or rec_title in title.lower():
                            score += 30
                            
                        if rec_artist == artist.lower():
                            score += 40
                        elif artist.lower() in rec_artist or rec_artist in artist.lower():
                            score += 25
                        
                        if score > best_score:
                            best_score = score
                            best_match = recording
                    
                    # Return best match if score is reasonable
                    if best_match and best_score >= 40:
                        return best_match
                        
            except Exception as e:
                continue  # Try next search strategy
                
        return None
    except Exception as e:
        return None

def update_audio_metadata(file_path, metadata):
    """Update metadata in audio file."""
    try:
        audio = MutagenFile(file_path, easy=True)
        if audio is None:
            return False
            
        # Update metadata
        audio['title'] = metadata.get('title', '')
        audio['artist'] = metadata.get('artist', '')
        audio['album'] = metadata.get('album', '')
        if metadata.get('year'):
            audio['date'] = metadata.get('year', '')
        if metadata.get('genre'):
            audio['genre'] = metadata.get('genre', '')
        if metadata.get('tracknumber'):
            audio['tracknumber'] = metadata.get('tracknumber', '')
            
        audio.save()
        return True
    except Exception as e:
        return False

def scan_folder_metadata(folder_path, msg_queue):
    """Scan folder for audio files and extract metadata."""
    audio_extensions = ('.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a', '.wma', '.aiff')
    files_metadata = []
    
    msg_queue.put(f"Scanning folder: {folder_path}")
    
    for root, _, files in os.walk(folder_path):
        for file in files:
            if file.lower().endswith(audio_extensions):
                file_path = os.path.join(root, file)
                msg_queue.put(f"Reading metadata: {file}")
                
                metadata = get_audio_metadata(file_path)
                if metadata:
                    # Enhance metadata with filename information
                    enhanced_metadata = enhance_metadata_with_filename(metadata)
                    files_metadata.append(enhanced_metadata)
    
    msg_queue.put(f"Found {len(files_metadata)} audio files")
    return files_metadata

def check_musicbrainz_metadata(metadata_list, msg_queue):
    """Check metadata against MusicBrainz and suggest updates."""
    suggestions = []
    
    for i, metadata in enumerate(metadata_list):
        # Show original filename for context
        filename = os.path.basename(metadata['file_path'])
        msg_queue.put(f"Checking ({i+1}/{len(metadata_list)}): {filename}")
        msg_queue.put(f"  Current: {metadata['artist']} - {metadata['title']}")
        
        mb_result = search_musicbrainz(
            metadata['artist'], 
            metadata['title'], 
            metadata.get('album', '')
        )
        
        if mb_result:
            # Compare and suggest updates
            current_title = metadata['title']
            current_artist = metadata['artist']
            current_album = metadata.get('album', '')
            
            mb_title = mb_result.get('title', '')
            mb_artist = mb_result['artist-credit'][0]['artist']['name'] if mb_result.get('artist-credit') else ''
            mb_album = ''
            if mb_result.get('release-list'):
                mb_album = mb_result['release-list'][0]['title']
            
            msg_queue.put(f"  Found: {mb_artist} - {mb_title}")
            
            # Check if updates are needed
            needs_update = (
                current_title != mb_title and mb_title or
                current_artist != mb_artist and mb_artist or
                current_album != mb_album and mb_album
            )
            
            if needs_update:
                suggestions.append({
                    'file': metadata,
                    'musicbrainz': {
                        'title': mb_title,
                        'artist': mb_artist,
                        'album': mb_album,
                        'release_date': mb_result.get('release-list', [{}])[0].get('date', '') if mb_result.get('release-list') else ''
                    }
                })
                msg_queue.put(f"  → Suggested update available")
            else:
                msg_queue.put(f"  → Metadata already correct")
        else:
            # Try searching with filename data as fallback
            filename_data = parse_filename_metadata(filename)
            if filename_data['artist'] and filename_data['title']:
                msg_queue.put(f"  Trying filename data: {filename_data['artist']} - {filename_data['title']}")
                mb_result = search_musicbrainz(
                    filename_data['artist'],
                    filename_data['title'],
                    ''
                )
                
                if mb_result:
                    mb_title = mb_result.get('title', '')
                    mb_artist = mb_result['artist-credit'][0]['artist']['name'] if mb_result.get('artist-credit') else ''
                    mb_album = ''
                    if mb_result.get('release-list'):
                        mb_album = mb_result['release-list'][0]['title']
                    
                    msg_queue.put(f"  Found via filename: {mb_artist} - {mb_title}")
                    
                    suggestions.append({
                        'file': metadata,
                        'musicbrainz': {
                            'title': mb_title,
                            'artist': mb_artist,
                            'album': mb_album,
                            'release_date': mb_result.get('release-list', [{}])[0].get('date', '') if mb_result.get('release-list') else ''
                        }
                    })
                else:
                    msg_queue.put(f"  → No matches found")
            else:
                msg_queue.put(f"  → No matches found")
    
    msg_queue.put(f"Found {len(suggestions)} suggested updates")
    return suggestions
    
    msg_queue.put(f"Found {len(suggestions)} files with potential metadata updates")
    return suggestions

def select_meta_folder():
    folder = filedialog.askdirectory()
    if folder:
        meta_folder_entry.delete(0, tk.END)
        meta_folder_entry.insert(0, folder)

def run_metadata_scan():
    folder = meta_folder_entry.get()
    if not folder:
        messagebox.showerror("Error", "Please select a folder to scan")
        return
    
    scan_button.config(state='disabled')
    check_mb_button.config(state='disabled')
    
    msg_queue = queue.Queue()
    check_queue(msg_queue)
    
    def worker():
        metadata_list = scan_folder_metadata(folder, msg_queue)
        root.after(0, lambda: metadata_scan_complete(metadata_list))
    
    threading.Thread(target=worker, daemon=True).start()

def metadata_scan_complete(metadata_list):
    scan_button.config(state='normal')
    check_mb_button.config(state='normal')
    
    # Clear existing items
    for item in meta_tree.get_children():
        meta_tree.delete(item)
    
    # Add metadata to tree
    for metadata in metadata_list:
        meta_tree.insert("", tk.END, values=(
            metadata['filename'],
            metadata['title'],
            metadata['artist'],
            metadata['album'],
            metadata['year'],
            "", "", ""  # Empty MusicBrainz columns initially
        ))

def run_musicbrainz_check():
    if not meta_tree.get_children():
        messagebox.showerror("Error", "Please scan metadata first")
        return
    
    scan_button.config(state='disabled')
    check_mb_button.config(state='disabled')
    
    msg_queue = queue.Queue()
    check_queue(msg_queue)
    
    # Get current metadata from tree
    metadata_list = []
    for item in meta_tree.get_children():
        values = meta_tree.item(item, 'values')
        metadata_list.append({
            'filename': values[0],
            'title': values[1],
            'artist': values[2],
            'album': values[3],
            'year': values[4],
            'filepath': values[0]  # We'll need to reconstruct full path
        })
    
    def worker():
        suggestions = check_musicbrainz_metadata(metadata_list, msg_queue)
        root.after(0, lambda: musicbrainz_check_complete(suggestions))
    
    threading.Thread(target=worker, daemon=True).start()

def musicbrainz_check_complete(suggestions):
    scan_button.config(state='normal')
    check_mb_button.config(state='normal')
    
    # Update tree with MusicBrainz suggestions
    for suggestion in suggestions:
        # Find matching item in tree
        for item in meta_tree.get_children():
            values = meta_tree.item(item, 'values')
            if values[0] == suggestion['file']['filename']:
                meta_tree.item(item, values=(
                    values[0],  # filename
                    values[1],  # current title
                    values[2],  # current artist
                    values[3],  # current album
                    values[4],  # current year
                    suggestion['musicbrainz']['title'],  # MB title
                    suggestion['musicbrainz']['artist'], # MB artist
                    suggestion['musicbrainz']['album']   # MB album
                ))
                break

def on_metadata_double_click(event):
    """Handle double-click on metadata tree to edit values."""
    item = meta_tree.selection()
    if not item:
        return
    
    # Get current values
    values = meta_tree.item(item[0], 'values')
    
    # Create edit dialog
    edit_window = tk.Toplevel(root)
    edit_window.title(f"Edit Metadata - {values[0]}")
    edit_window.geometry("500x400")
    
    # Current metadata section
    tk.Label(edit_window, text="Current Metadata:", font=("Arial", 10, "bold")).pack(pady=5)
    
    current_frame = tk.Frame(edit_window)
    current_frame.pack(pady=5)
    
    tk.Label(current_frame, text="Title:").grid(row=0, column=0, sticky="w")
    current_title = tk.Entry(current_frame, width=40)
    current_title.insert(0, values[1])
    current_title.grid(row=0, column=1, padx=5)
    
    tk.Label(current_frame, text="Artist:").grid(row=1, column=0, sticky="w")
    current_artist = tk.Entry(current_frame, width=40)
    current_artist.insert(0, values[2])
    current_artist.grid(row=1, column=1, padx=5)
    
    tk.Label(current_frame, text="Album:").grid(row=2, column=0, sticky="w")
    current_album = tk.Entry(current_frame, width=40)
    current_album.insert(0, values[3])
    current_album.grid(row=2, column=1, padx=5)
    
    tk.Label(current_frame, text="Year:").grid(row=3, column=0, sticky="w")
    current_year = tk.Entry(current_frame, width=40)
    current_year.insert(0, values[4])
    current_year.grid(row=3, column=1, padx=5)
    
    # MusicBrainz suggestions section
    tk.Label(edit_window, text="MusicBrainz Suggestions:", font=("Arial", 10, "bold")).pack(pady=5)
    
    mb_frame = tk.Frame(edit_window)
    mb_frame.pack(pady=5)
    
    tk.Label(mb_frame, text="Title:").grid(row=0, column=0, sticky="w")
    mb_title = tk.Entry(mb_frame, width=40)
    mb_title.insert(0, values[5] if len(values) > 5 else "")
    mb_title.grid(row=0, column=1, padx=5)
    
    tk.Label(mb_frame, text="Artist:").grid(row=1, column=0, sticky="w")
    mb_artist = tk.Entry(mb_frame, width=40)
    mb_artist.insert(0, values[6] if len(values) > 6 else "")
    mb_artist.grid(row=1, column=1, padx=5)
    
    tk.Label(mb_frame, text="Album:").grid(row=2, column=0, sticky="w")
    mb_album = tk.Entry(mb_frame, width=40)
    mb_album.insert(0, values[7] if len(values) > 7 else "")
    mb_album.grid(row=2, column=1, padx=5)
    
    # Buttons
    button_frame = tk.Frame(edit_window)
    button_frame.pack(pady=10)
    
    def apply_changes():
        # Update tree with new values
        new_values = (
            values[0],  # filename
            current_title.get(),
            current_artist.get(),
            current_album.get(),
            current_year.get(),
            mb_title.get(),
            mb_artist.get(),
            mb_album.get()
        )
        meta_tree.item(item[0], values=new_values)
        edit_window.destroy()
    
    def use_mb_suggestions():
        current_title.delete(0, tk.END)
        current_title.insert(0, mb_title.get())
        current_artist.delete(0, tk.END)
        current_artist.insert(0, mb_artist.get())
        current_album.delete(0, tk.END)
        current_album.insert(0, mb_album.get())
    
    tk.Button(button_frame, text="Use MB Suggestions", command=use_mb_suggestions).pack(side="left", padx=5)
    tk.Button(button_frame, text="Apply Changes", command=apply_changes).pack(side="left", padx=5)
    tk.Button(button_frame, text="Cancel", command=edit_window.destroy).pack(side="left", padx=5)

def update_selected_metadata():
    """Update the actual audio file metadata."""
    selected = meta_tree.selection()
    if not selected:
        messagebox.showerror("Error", "Please select a file to update")
        return
    
    item = selected[0]
    values = meta_tree.item(item, 'values')
    
    # We need the full file path - for now, we'll need to reconstruct it
    # This is a limitation - we should store the full path in the tree
    folder = meta_folder_entry.get()
    if not folder:
        messagebox.showerror("Error", "Cannot update - folder path not available")
        return
    
    file_path = os.path.join(folder, values[0])
    
    metadata = {
        'title': values[1],
        'artist': values[2],
        'album': values[3],
        'year': values[4]
    }
    
    if update_audio_metadata(file_path, metadata):
        messagebox.showinfo("Success", f"Updated metadata for {values[0]}")
        # Remove from tree to indicate it's been processed
        meta_tree.delete(item)
    else:
        messagebox.showerror("Error", f"Failed to update metadata for {values[0]}")

def skip_selected_metadata():
    """Skip the selected item."""
    selected = meta_tree.selection()
    if selected:
        meta_tree.delete(selected[0])

def clear_metadata_results():
    """Clear all metadata results."""
    for item in meta_tree.get_children():
        meta_tree.delete(item)

# Initialize pygame mixer
pygame.mixer.init()

# Player state variables
current_playlist = []
current_track_index = -1
is_playing = False
is_paused = False
player_volume = 0.7
shuffle_mode = False
repeat_mode = False

# Progress tracking variables
current_track_duration = 0
current_track_position = 0
progress_update_id = None

def load_playlist_from_folder(folder_path):
    """Load all audio files from a folder into a playlist."""
    audio_extensions = ('.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a', '.wma', '.aiff')
    playlist = []
    
    for root, _, files in os.walk(folder_path):
        for file in files:
            if file.lower().endswith(audio_extensions):
                file_path = os.path.join(root, file)
                metadata = get_audio_metadata(file_path)
                if metadata:
                    playlist.append({
                        'file_path': file_path,
                        'title': metadata['title'],
                        'artist': metadata['artist'],
                        'album': metadata['album'],
                        'duration': metadata['duration']
                    })
    
    return playlist

def save_playlist(playlist, filename):
    """Save playlist to JSON file."""
    try:
        with open(filename, 'w') as f:
            json.dump(playlist, f, indent=2)
        return True
    except Exception as e:
        messagebox.showerror("Error", f"Failed to save playlist: {e}")
        return False

def load_playlist(filename):
    """Load playlist from JSON file."""
    try:
        with open(filename, 'r') as f:
            return json.load(f)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to load playlist: {e}")
        return []

def play_track(track_index=None):
    """Play a track from the current playlist."""
    global current_track_index, is_playing, is_paused
    
    if not current_playlist:
        return
    
    if track_index is not None:
        current_track_index = track_index
    
    if 0 <= current_track_index < len(current_playlist):
        track = current_playlist[current_track_index]
        
        try:
            pygame.mixer.music.load(track['file_path'])
            pygame.mixer.music.play()
            pygame.mixer.music.set_volume(player_volume)
            is_playing = True
            is_paused = False
            
            # Get track duration for progress tracking
            try:
                audio = MutagenFile(track['file_path'])
                duration = audio.info.length if audio else 0
                start_progress_tracking(duration)
            except:
                start_progress_tracking(0)  # Unknown duration
            
            # Update UI
            update_player_display()
            
        except Exception as e:
            messagebox.showerror("Playback Error", f"Cannot play {track['title']}: {e}")

def pause_track():
    """Pause or resume current track."""
    global is_paused
    
    if is_playing:
        if is_paused:
            pygame.mixer.music.unpause()
            is_paused = False
        else:
            pygame.mixer.music.pause()
            is_paused = True
        
        update_player_display()

def stop_track():
    """Stop current track."""
    global is_playing, is_paused
    
    pygame.mixer.music.stop()
    is_playing = False
    is_paused = False
    stop_progress_tracking()
    update_player_display()

def next_track():
    """Play next track in playlist."""
    global current_track_index
    
    if not current_playlist:
        return
    
    if shuffle_mode:
        current_track_index = random.randint(0, len(current_playlist) - 1)
    else:
        current_track_index = (current_track_index + 1) % len(current_playlist)
    
    play_track(current_track_index)

def previous_track():
    """Play previous track in playlist."""
    global current_track_index
    
    if not current_playlist:
        return
    
    current_track_index = (current_track_index - 1) % len(current_playlist)
    play_track(current_track_index)

def set_volume(volume):
    """Set player volume (0.0 to 1.0)."""
    global player_volume
    
    player_volume = volume
    pygame.mixer.music.set_volume(volume)

def toggle_shuffle():
    """Toggle shuffle mode."""
    global shuffle_mode
    
    shuffle_mode = not shuffle_mode
    update_player_display()

def toggle_repeat():
    """Toggle repeat mode."""
    global repeat_mode
    
    repeat_mode = not repeat_mode
    update_player_display()

def update_player_display():
    """Update the player UI display."""
    if current_playlist and 0 <= current_track_index < len(current_playlist):
        track = current_playlist[current_track_index]
        current_track_label.config(text=f"{track['title']}")
        current_artist_label.config(text=f"{track['artist']} • {track['album']}")
        
        # Update playlist selection
        for item in playlist_tree.get_children():
            playlist_tree.selection_remove(item)
        
        if playlist_tree.get_children():
            playlist_tree.selection_add(playlist_tree.get_children()[current_track_index])
            playlist_tree.see(playlist_tree.get_children()[current_track_index])
    else:
        current_track_label.config(text="No track selected")
        current_artist_label.config(text="")
    
    # Update button states with better visual feedback
    play_button.config(text="⏸" if is_paused else "▶")
    
    # Update mode buttons with active state styling
    if shuffle_mode:
        shuffle_button.config(style="Player.TButton")
    else:
        shuffle_button.config(style="Modern.TButton")
        
    if repeat_mode:
        repeat_button.config(style="Player.TButton")
    else:
        repeat_button.config(style="Modern.TButton")

def format_time(seconds):
    """Format seconds into MM:SS format."""
    minutes = int(seconds // 60)
    seconds = int(seconds % 60)
    return f"{minutes}:{seconds:02d}"

def update_progress():
    """Update the progress bar and time display."""
    global progress_update_id, current_track_position
    
    if is_playing and not is_paused and current_track_duration > 0:
        try:
            # Get current position from pygame
            current_track_position = pygame.mixer.music.get_pos() / 1000.0
            
            # Update progress bar
            progress = (current_track_position / current_track_duration) * 100
            progress_var.set(min(progress, 100))
            
            # Update time labels
            current_time_label.config(text=format_time(current_track_position))
            total_time_label.config(text=format_time(current_track_duration))
            
        except:
            pass
    
    # Schedule next update
    if is_playing:
        progress_update_id = root.after(1000, update_progress)

def start_progress_tracking(duration):
    """Start tracking progress for a track with given duration."""
    global current_track_duration, current_track_position
    
    current_track_duration = duration
    current_track_position = 0
    
    # Update total time immediately
    total_time_label.config(text=format_time(duration))
    
    # Start progress updates
    if progress_update_id:
        root.after_cancel(progress_update_id)
    update_progress()

def stop_progress_tracking():
    """Stop progress tracking."""
    global progress_update_id
    if progress_update_id:
        root.after_cancel(progress_update_id)
        progress_update_id = None
    
    # Reset progress
    progress_var.set(0)
    current_time_label.config(text="0:00")
    total_time_label.config(text="0:00")

def on_playlist_double_click(event):
    """Handle double-click on playlist to play track."""
    selection = playlist_tree.selection()
    if selection:
        item = selection[0]
        # Get the index of the selected item
        for i, child in enumerate(playlist_tree.get_children()):
            if child == item:
                play_track(i)
                break

def add_folder_to_playlist():
    """Add all audio files from a folder to the playlist."""
    folder = filedialog.askdirectory()
    if folder:
        new_tracks = load_playlist_from_folder(folder)
        current_playlist.extend(new_tracks)
        update_playlist_display()

def add_files_to_playlist():
    """Add selected audio files to the playlist."""
    files = filedialog.askopenfilenames(
        filetypes=[
            ("Audio files", "*.mp3 *.wav *.flac *.aac *.ogg *.m4a *.wma *.aiff"),
            ("All files", "*.*")
        ]
    )
    
    for file_path in files:
        metadata = get_audio_metadata(file_path)
        if metadata:
            current_playlist.append({
                'file_path': file_path,
                'title': metadata['title'],
                'artist': metadata['artist'],
                'album': metadata['album'],
                'duration': metadata['duration']
            })
    
    update_playlist_display()

def remove_from_playlist():
    """Remove selected tracks from playlist."""
    selection = playlist_tree.selection()
    if selection:
        # Remove in reverse order to maintain indices
        indices_to_remove = []
        for item in selection:
            for i, child in enumerate(playlist_tree.get_children()):
                if child == item:
                    indices_to_remove.append(i)
                    break
        
        for i in sorted(indices_to_remove, reverse=True):
            if i < len(current_playlist):
                del current_playlist[i]
        
        update_playlist_display()

def clear_playlist():
    """Clear the entire playlist."""
    global current_playlist, current_track_index, is_playing, is_paused
    
    current_playlist.clear()
    current_track_index = -1
    stop_track()
    update_playlist_display()

def save_playlist_file():
    """Save current playlist to file."""
    if not current_playlist:
        messagebox.showinfo("Empty Playlist", "No tracks to save.")
        return
    
    file_path = filedialog.asksaveasfilename(
        defaultextension=".json",
        filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
    )
    
    if file_path:
        if save_playlist(current_playlist, file_path):
            messagebox.showinfo("Success", f"Playlist saved to {file_path}")

def load_playlist_file():
    """Load playlist from file."""
    file_path = filedialog.askopenfilename(
        filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
    )
    
    if file_path:
        loaded_playlist = load_playlist(file_path)
        if loaded_playlist:
            current_playlist.clear()
            current_playlist.extend(loaded_playlist)
            update_playlist_display()
            messagebox.showinfo("Success", f"Loaded {len(loaded_playlist)} tracks from playlist")

def update_playlist_display():
    """Update the playlist treeview display."""
    # Clear existing items
    for item in playlist_tree.get_children():
        playlist_tree.delete(item)
    
    # Add current playlist items
    for track in current_playlist:
        duration_str = f"{int(track['duration'] // 60)}:{int(track['duration'] % 60):02d}" if track['duration'] else "0:00"
        playlist_tree.insert("", tk.END, values=(
            track['title'],
            track['artist'],
            track['album'],
            duration_str
        ))

def move_track_up():
    """Move selected track up in playlist."""
    selection = playlist_tree.selection()
    if selection:
        item = selection[0]
        for i, child in enumerate(playlist_tree.get_children()):
            if child == item and i > 0:
                # Swap in playlist
                current_playlist[i], current_playlist[i-1] = current_playlist[i-1], current_playlist[i]
                update_playlist_display()
                # Reselect the moved item
                playlist_tree.selection_set(playlist_tree.get_children()[i-1])
                break

def move_track_down():
    """Move selected track down in playlist."""
    selection = playlist_tree.selection()
    if selection:
        item = selection[0]
        children = playlist_tree.get_children()
        for i, child in enumerate(children):
            if child == item and i < len(children) - 1:
                # Swap in playlist
                current_playlist[i], current_playlist[i+1] = current_playlist[i+1], current_playlist[i]
                update_playlist_display()
                # Reselect the moved item
                playlist_tree.selection_set(children[i+1])
                break

def check_music_end():
    """Check if current track has ended and handle next track."""
    if is_playing and not pygame.mixer.music.get_busy() and not is_paused:
        if repeat_mode:
            play_track(current_track_index)  # Repeat current track
        else:
            next_track()  # Play next track
    
    # Schedule next check
    root.after(1000, check_music_end)

def configure_modern_style():
    """Configure Windows 11 inspired modern ttk styling."""
    style = ttk.Style()

    # Configure overall theme - use 'clam' for modern look
    try:
        style.theme_use('clam')
    except:
        pass  # Fallback to default

    # Configure frames with Mica-inspired backgrounds
    style.configure("Card.TFrame",
                   background=CARD_BG,
                   relief="flat",
                   borderwidth=0)
    style.configure("Modern.TFrame",
                   background=FRAME_BG,
                   relief="flat",
                   borderwidth=0)
    style.configure("Player.TFrame",
                   background=FRAME_BG,
                   relief="flat",
                   borderwidth=0)

    # Configure buttons with Windows 11 style
    style.configure("Modern.TButton",
                   font=MODERN_FONT,
                   background=BUTTON_BG,
                   foreground=TEXT_PRIMARY,
                   borderwidth=1,
                   relief="flat",
                   padding=(12, 6))
    style.map("Modern.TButton",
             background=[("active", BUTTON_ACTIVE),
                        ("pressed", BUTTON_ACTIVE),
                        ("hover", BUTTON_HOVER)])

    # Large buttons for player controls
    style.configure("Player.TButton",
                   font=TITLE_FONT,
                   background=BUTTON_BG,
                   foreground=TEXT_PRIMARY,
                   borderwidth=1,
                   relief="flat",
                   padding=(16, 8))
    style.map("Player.TButton",
             background=[("active", BUTTON_ACTIVE),
                        ("pressed", BUTTON_ACTIVE),
                        ("hover", BUTTON_HOVER)])

    # Configure labels
    style.configure("Modern.TLabel",
                   font=MODERN_FONT,
                   background=FRAME_BG,
                   foreground=TEXT_PRIMARY)
    style.configure("Header.TLabel",
                   font=HEADER_FONT,
                   background=FRAME_BG,
                   foreground=PRIMARY_COLOR)
    style.configure("Title.TLabel",
                   font=TITLE_FONT,
                   background=FRAME_BG,
                   foreground=TEXT_PRIMARY)
    style.configure("Muted.TLabel",
                   font=MODERN_FONT,
                   background=FRAME_BG,
                   foreground=TEXT_MUTED)

    # Configure entry fields
    style.configure("Modern.TEntry",
                   font=MODERN_FONT,
                   fieldbackground=FRAME_BG,
                   borderwidth=1,
                   relief="solid",
                   padding=(8, 4))

    # Configure combobox
    style.configure("Modern.TCombobox",
                   font=MODERN_FONT,
                   fieldbackground=FRAME_BG,
                   background=BUTTON_BG,
                   borderwidth=1,
                   relief="solid",
                   padding=(8, 4))

    # Configure treeviews with modern styling
    style.configure("Modern.Treeview",
                   font=MODERN_FONT,
                   background=FRAME_BG,
                   fieldbackground=FRAME_BG,
                   borderwidth=0,
                   relief="flat")
    style.configure("Modern.Treeview.Heading",
                   font=MODERN_FONT_BOLD,
                   background=CARD_BG,
                   foreground=TEXT_PRIMARY,
                   borderwidth=0,
                   relief="flat")

    # Configure notebook with Windows 11 style
    style.configure("Modern.TNotebook",
                   background=BG_COLOR,
                   borderwidth=0,
                   relief="flat")
    style.configure("Modern.TNotebook.Tab",
                   font=MODERN_FONT_BOLD,
                   background=BUTTON_BG,
                   foreground=TEXT_SECONDARY,
                   borderwidth=0,
                   relief="flat",
                   padding=(20, 12))
    style.map("Modern.TNotebook.Tab",
             background=[("selected", FRAME_BG),
                        ("active", BUTTON_HOVER)],
             foreground=[("selected", TEXT_PRIMARY)])

    # Configure scales with modern styling
    style.configure("Modern.Horizontal.TScale",
                   background=FRAME_BG,
                   troughcolor=BORDER_LIGHT,
                   lightcolor=PRIMARY_COLOR,
                   darkcolor=PRIMARY_COLOR,
                   borderwidth=0)

    # Progress bar style for player
    style.configure("Player.Horizontal.TProgressbar",
                   background=PRIMARY_COLOR,
                   troughcolor=BORDER_LIGHT,
                   borderwidth=0,
                   lightcolor=PRIMARY_COLOR,
                   darkcolor=PRIMARY_COLOR)

# GUI setup
root = tk.Tk()
root.title("🎵 Audio Downloader & Duplicate Finder")
root.configure(bg=BG_COLOR)
root.geometry("1300x850")  # Slightly larger for better player display

# Configure modern styling
configure_modern_style()

# Create notebook for tabs
notebook = ttk.Notebook(root, style="Modern.TNotebook")
notebook.pack(fill="both", expand=True, padx=15, pady=15)

# Download tab
download_frame = ttk.Frame(notebook)
notebook.add(download_frame, text="📥 Download Audio")

# URL selection
url_frame = ttk.Frame(download_frame, style="Modern.TFrame")
url_frame.pack(fill="x", padx=10, pady=5)

ttk.Label(url_frame, text="URL:", style="Modern.TLabel").pack(side="left")
url_var = tk.StringVar()
url_combo = ttk.Combobox(url_frame, textvariable=url_var, width=70, style="Modern.TCombobox")
url_combo['values'] = [
    "https://www.dev.dantan.net/aioEpisodes",
    # Users can add more URLs here
]
url_combo.set("https://www.dev.dantan.net/aioEpisodes")  # Default selection
url_combo.pack(side="left", fill="x", expand=True, padx=(5, 0))

# Download folder selection
folder_frame = ttk.Frame(download_frame, style="Modern.TFrame")
folder_frame.pack(fill="x", padx=10, pady=5)

ttk.Label(folder_frame, text="Download Folder:", style="Modern.TLabel").pack(side="left")
download_entry = ttk.Entry(folder_frame, width=50, style="Modern.TEntry")
download_entry.pack(side="left", fill="x", expand=True, padx=(5, 5))
download_entry.insert(0, "aio_downloads")  # Default folder
ttk.Button(folder_frame, text="Browse", command=select_download_folder, style="Modern.TButton").pack(side="left")

# Existing folder selection for duplicate checking
existing_frame = ttk.Frame(download_frame, style="Modern.TFrame")
existing_frame.pack(fill="x", padx=10, pady=5)

ttk.Label(existing_frame, text="Check Against Folder:", style="Modern.TLabel").pack(side="left")
existing_entry = ttk.Entry(existing_frame, width=50, style="Modern.TEntry")
existing_entry.pack(side="left", fill="x", expand=True, padx=(5, 5))
existing_entry.insert(0, "")  # Empty by default (optional)
ttk.Button(existing_frame, text="Browse", command=select_existing_folder, style="Modern.TButton").pack(side="left")

# Help label
help_label = ttk.Label(download_frame, text="Optional: Select a folder to check for duplicates. Files that already exist will be skipped.", 
                      style="Modern.TLabel", foreground="#666666", font=("Segoe UI", 9))
help_label.pack(padx=10, pady=(0, 5))

# Download button
button_frame = ttk.Frame(download_frame, style="Modern.TFrame")
button_frame.pack(pady=10)
download_button = ttk.Button(button_frame, text="Download Audio Files", command=run_download, style="Modern.TButton")
download_button.pack()

# Duplicate Finder tab
duplicate_frame = ttk.Frame(notebook)
notebook.add(duplicate_frame, text="🔍 Find Duplicates")

frame = ttk.Frame(duplicate_frame, style="Modern.TFrame")
frame.pack(padx=10, pady=10)

ttk.Label(frame, text="Folder 1:", style="Modern.TLabel").grid(row=0, column=0, sticky="w", pady=2)
entry1 = ttk.Entry(frame, width=50, style="Modern.TEntry")
entry1.grid(row=0, column=1, pady=2)
ttk.Button(frame, text="Browse", command=lambda: select_folder(entry1), style="Modern.TButton").grid(row=0, column=2, padx=(5, 0), pady=2)

ttk.Label(frame, text="Folder 2:", style="Modern.TLabel").grid(row=1, column=0, sticky="w", pady=2)
entry2 = ttk.Entry(frame, width=50, style="Modern.TEntry")
entry2.grid(row=1, column=1, pady=2)
ttk.Button(frame, text="Browse", command=lambda: select_folder(entry2), style="Modern.TButton").grid(row=1, column=2, padx=(5, 0), pady=2)

button_frame = ttk.Frame(frame, style="Modern.TFrame")
button_frame.grid(row=2, column=0, columnspan=3, pady=10)

ttk.Button(button_frame, text="Check Duplicates", command=run_check, style="Modern.TButton").pack(side="left", padx=(0, 10))
ttk.Button(button_frame, text="Export to CSV", command=export_csv, style="Modern.TButton").pack(side="left")

status_label = ttk.Label(frame, text="", style="Modern.TLabel")
status_label.grid(row=3, column=1)

tree = ttk.Treeview(duplicate_frame, columns=("File1", "File2"), show="headings", style="Modern.Treeview")
tree.heading("File1", text="Duplicate File 1")
tree.heading("File2", text="Duplicate File 2")
tree.pack(fill="both", expand=True, padx=10, pady=10)
tree.bind("<Button-3>", show_menu)

# Metadata tab
metadata_frame = ttk.Frame(notebook)
notebook.add(metadata_frame, text="🏷️ Metadata")

# Metadata folder selection
meta_folder_frame = ttk.Frame(metadata_frame, style="Modern.TFrame")
meta_folder_frame.pack(fill="x", padx=10, pady=10)

ttk.Label(meta_folder_frame, text="Audio Folder:", style="Modern.TLabel").pack(side="left")
meta_folder_entry = ttk.Entry(meta_folder_frame, width=50, style="Modern.TEntry")
meta_folder_entry.pack(side="left", fill="x", expand=True, padx=(5, 5))
ttk.Button(meta_folder_frame, text="Browse", command=lambda: select_meta_folder(), style="Modern.TButton").pack(side="left")

# Metadata buttons
meta_button_frame = ttk.Frame(metadata_frame, style="Modern.TFrame")
meta_button_frame.pack(pady=5)

scan_button = ttk.Button(meta_button_frame, text="Scan Metadata", command=run_metadata_scan, style="Modern.TButton")
scan_button.pack(side="left", padx=5)

check_mb_button = ttk.Button(meta_button_frame, text="Check MusicBrainz", command=run_musicbrainz_check, style="Modern.TButton")
check_mb_button.pack(side="left", padx=5)

# Metadata treeview
meta_tree = ttk.Treeview(metadata_frame, columns=("Filename", "Title", "Artist", "Album", "Year", "MB_Title", "MB_Artist", "MB_Album"), show="headings", height=15, style="Modern.Treeview")
meta_tree.heading("Filename", text="Filename")
meta_tree.heading("Title", text="Current Title")
meta_tree.heading("Artist", text="Current Artist")
meta_tree.heading("Album", text="Current Album")
meta_tree.heading("Year", text="Current Year")
meta_tree.heading("MB_Title", text="MusicBrainz Title")
meta_tree.heading("MB_Artist", text="MusicBrainz Artist")
meta_tree.heading("MB_Album", text="MusicBrainz Album")

# Set column widths
meta_tree.column("Filename", width=150)
meta_tree.column("Title", width=150)
meta_tree.column("Artist", width=120)
meta_tree.column("Album", width=120)
meta_tree.column("Year", width=80)
meta_tree.column("MB_Title", width=150)
meta_tree.column("MB_Artist", width=120)
meta_tree.column("MB_Album", width=120)

meta_tree.pack(fill="both", expand=True, padx=10, pady=5)
meta_tree.bind("<Double-1>", on_metadata_double_click)

# Metadata action buttons
action_frame = ttk.Frame(metadata_frame, style="Modern.TFrame")
action_frame.pack(fill="x", padx=10, pady=5)

ttk.Button(action_frame, text="Update Selected", command=update_selected_metadata, style="Modern.TButton").pack(side="left", padx=5)
ttk.Button(action_frame, text="Skip Selected", command=skip_selected_metadata, style="Modern.TButton").pack(side="left", padx=5)
ttk.Button(action_frame, text="Clear Results", command=clear_metadata_results, style="Modern.TButton").pack(side="right", padx=5)

# Player tab
player_frame = ttk.Frame(notebook)
notebook.add(player_frame, text="🎵 Player")

# Now Playing Section - Eye-catching header
now_playing_frame = ttk.Frame(player_frame, style="Card.TFrame")
now_playing_frame.pack(fill="x", padx=15, pady=(15, 10))

# Album art placeholder (can be enhanced later)
album_art_frame = ttk.Frame(now_playing_frame, style="Card.TFrame")
album_art_frame.pack(side="left", padx=(0, 15), pady=10)

# Placeholder for album art - Windows 11 style
album_art_label = ttk.Label(album_art_frame, text="🎵", font=("Segoe UI", 48), background=CARD_BG)
album_art_label.pack(padx=20, pady=20)

# Track info
track_info_frame = ttk.Frame(now_playing_frame, style="Card.TFrame")
track_info_frame.pack(side="left", fill="both", expand=True, pady=10)

current_track_label = ttk.Label(track_info_frame, text="No track selected", style="Title.TLabel")
current_track_label.pack(anchor="w", pady=(0, 5))

current_artist_label = ttk.Label(track_info_frame, text="", style="Muted.TLabel")
current_artist_label.pack(anchor="w", pady=(0, 10))

# Progress bar and time display
progress_frame = ttk.Frame(track_info_frame, style="Card.TFrame")
progress_frame.pack(fill="x", pady=(0, 10))

# Time labels
time_frame = ttk.Frame(progress_frame, style="Card.TFrame")
time_frame.pack(fill="x", pady=(0, 5))

current_time_label = ttk.Label(time_frame, text="0:00", style="Muted.TLabel")
current_time_label.pack(side="left")

total_time_label = ttk.Label(time_frame, text="0:00", style="Muted.TLabel")
total_time_label.pack(side="right")

# Progress bar
progress_var = tk.DoubleVar()
progress_bar = ttk.Progressbar(progress_frame, variable=progress_var, maximum=100, style="Player.Horizontal.TProgressbar")
progress_bar.pack(fill="x")

# Playback Controls - Large and prominent
controls_frame = ttk.Frame(player_frame, style="Modern.TFrame")
controls_frame.pack(fill="x", padx=15, pady=10)

# Main playback buttons - Windows 11 style
playback_main_frame = ttk.Frame(controls_frame, style="Modern.TFrame")
playback_main_frame.pack(pady=(10, 5))

# Previous track
previous_button = ttk.Button(playback_main_frame, text="⏮", command=previous_track, style="Player.TButton", width=4)
previous_button.pack(side="left", padx=(0, 10))

# Play/Pause - Largest button
play_button = ttk.Button(playback_main_frame, text="▶", command=lambda: play_track() if not is_playing else pause_track(), style="Player.TButton", width=6)
play_button.pack(side="left", padx=10)

# Stop
stop_button = ttk.Button(playback_main_frame, text="⏹", command=stop_track, style="Player.TButton", width=4)
stop_button.pack(side="left", padx=10)

# Next track
next_button = ttk.Button(playback_main_frame, text="⏭", command=next_track, style="Player.TButton", width=4)
next_button.pack(side="left", padx=(10, 0))

# Secondary controls
secondary_frame = ttk.Frame(controls_frame, style="Modern.TFrame")
secondary_frame.pack(pady=(5, 15))

# Volume control with better styling
volume_section = ttk.Frame(secondary_frame, style="Modern.TFrame")
volume_section.pack(side="left", padx=(0, 20))

ttk.Label(volume_section, text="🔊 Volume", style="Modern.TLabel").pack(anchor="w", pady=(0, 5))
volume_scale = ttk.Scale(volume_section, from_=0, to=100, orient="horizontal", command=lambda v: set_volume(float(v)/100), style="Modern.Horizontal.TScale", length=150)
volume_scale.set(70)
volume_scale.pack()

# Mode buttons with better styling
mode_section = ttk.Frame(secondary_frame, style="Modern.TFrame")
mode_section.pack(side="left", padx=(20, 0))

ttk.Label(mode_section, text="Playback Mode", style="Modern.TLabel").pack(anchor="w", pady=(0, 8))

mode_buttons_frame = ttk.Frame(mode_section, style="Modern.TFrame")
mode_buttons_frame.pack()

shuffle_button = ttk.Button(mode_buttons_frame, text="🔀 Shuffle", command=toggle_shuffle, style="Modern.TButton")
shuffle_button.pack(side="left", padx=(0, 10))

repeat_button = ttk.Button(mode_buttons_frame, text="🔁 Repeat", command=toggle_repeat, style="Modern.TButton")
repeat_button.pack(side="left")

# Playlist Management Section
playlist_controls_frame = ttk.Frame(player_frame, style="Card.TFrame")
playlist_controls_frame.pack(fill="x", padx=15, pady=(10, 15))

# Header
ttk.Label(playlist_controls_frame, text="🎼 Playlist Management", style="Header.TLabel").pack(anchor="w", padx=15, pady=(15, 10))

# Action buttons in organized rows
actions_frame = ttk.Frame(playlist_controls_frame, style="Card.TFrame")
actions_frame.pack(fill="x", padx=15, pady=(0, 15))

# Row 1: Add content
add_row = ttk.Frame(actions_frame, style="Card.TFrame")
add_row.pack(fill="x", pady=(0, 8))

ttk.Button(add_row, text="📁 Add Folder", command=add_folder_to_playlist, style="Modern.TButton").pack(side="left", padx=(0, 8))
ttk.Button(add_row, text="🎵 Add Files", command=add_files_to_playlist, style="Modern.TButton").pack(side="left", padx=(0, 8))
ttk.Button(add_row, text="🗑️ Remove Selected", command=remove_from_playlist, style="Modern.TButton").pack(side="left", padx=(0, 8))

# Row 2: Playlist operations
ops_row = ttk.Frame(actions_frame, style="Card.TFrame")
ops_row.pack(fill="x", pady=(0, 8))

ttk.Button(ops_row, text="🧹 Clear Playlist", command=clear_playlist, style="Modern.TButton").pack(side="left", padx=(0, 8))
ttk.Button(ops_row, text="💾 Save Playlist", command=save_playlist_file, style="Modern.TButton").pack(side="left", padx=(0, 8))
ttk.Button(ops_row, text="📂 Load Playlist", command=load_playlist_file, style="Modern.TButton").pack(side="left", padx=(0, 8))

# Row 3: Ordering
order_row = ttk.Frame(actions_frame, style="Card.TFrame")
order_row.pack(fill="x")

ttk.Button(order_row, text="⬆ Move Up", command=move_track_up, style="Modern.TButton").pack(side="left", padx=(0, 8))
ttk.Button(order_row, text="⬇ Move Down", command=move_track_down, style="Modern.TButton").pack(side="left")

# Playlist Display Section
playlist_frame = ttk.Frame(player_frame, style="Card.TFrame")
playlist_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))

# Header
ttk.Label(playlist_frame, text="📋 Current Playlist", style="Header.TLabel").pack(anchor="w", padx=15, pady=(15, 10))

# Playlist treeview with modern styling
playlist_container = ttk.Frame(playlist_frame, style="Card.TFrame")
playlist_container.pack(fill="both", expand=True, padx=15, pady=(0, 15))

playlist_tree = ttk.Treeview(playlist_container, columns=("Title", "Artist", "Album", "Duration"), show="headings", height=12, style="Modern.Treeview")
playlist_tree.heading("Title", text="Title")
playlist_tree.heading("Artist", text="Artist")
playlist_tree.heading("Album", text="Album")
playlist_tree.heading("Duration", text="Duration")

playlist_tree.column("Title", width=250)
playlist_tree.column("Artist", width=150)
playlist_tree.column("Album", width=150)
playlist_tree.column("Duration", width=80)

playlist_tree.pack(fill="both", expand=True)
playlist_tree.bind("<Double-1>", on_playlist_double_click)

text_output = scrolledtext.ScrolledText(root, height=10)
text_output.pack(fill="both", expand=True, padx=10, pady=10)

# Start the music end checker
root.after(1000, check_music_end)

root.mainloop()