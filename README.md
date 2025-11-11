# Audio Downloader & Duplicate Finder - Combined Application

## Changes Made

### 1. Combined Functionality
- Merged the audio downloader script (`import requests.py`) with the duplicate finder (`audio_duplicate_finder.py`)
- Created a tabbed interface with four main sections:
  - **Download Audio**: Download audio files from websites with duplicate checking
  - **Find Duplicates**: Compare audio files between folders to find duplicates
  - **Metadata**: Scan and update audio file metadata using MusicBrainz
  - **Player**: Full-featured audio player with playlist management

### 2. New Features Added

#### Download Tab:
- **URL Dropdown**: Dropdown combo box with your original URL pre-populated
  - Default: "https://www.dev.dantan.net/aioEpisodes"
  - Users can select from dropdown or type in a custom URL
- **Download Folder**: Specify where to save downloaded files (defaults to "aio_downloads")
- **Check Against Folder**: Optional - Select a folder to check for existing files/duplicates
  - The app will scan this folder and subfolders for audio files
  - Downloads will be skipped if duplicates are found (based on file content fingerprinting)
  - Helps avoid re-downloading files you already have
- **Progress Logging**: Real-time status updates in the message area
- **Duplicate Detection**: Shows how many files were skipped as duplicates

#### Enhanced GUI:
- **Tabbed Interface**: Separate tabs for downloading and duplicate checking
- **Better Organization**: Cleaner layout with organized sections
- **Status Updates**: Better progress reporting for both operations

### 3. Technical Improvements
- Replaced `pydub` audio analysis with file-based fingerprinting for Python 3.13 compatibility
- Fast duplicate detection using file size + partial content hashing
- Added required imports: `requests`, `BeautifulSoup`, `re`
- Threaded operations to prevent GUI freezing
- Comprehensive error handling for network operations
- File integrity checks during downloads
- Intelligent duplicate checking that works across different folder structures

### 4. Metadata Management Features
- **MusicBrainz Integration**: Query online database for accurate metadata
- **Batch Metadata Scanning**: Read metadata from all audio files in a folder
- **Interactive Editing**: Double-click to edit metadata with MusicBrainz suggestions
- **Smart Updates**: Only suggest changes when metadata differs from MusicBrainz
- **Direct File Updates**: Save metadata changes directly to audio files

### 5. Audio Player & Playlist Management Features
- **Full Audio Playback**: Support for MP3, WAV, FLAC, AAC, OGG, M4A, WMA, AIFF formats
- **Playlist Management**: Create, save, load, and edit playlists with visual interface
- **Playback Controls**: Play, pause, stop, next, previous with volume control
- **Shuffle & Repeat Modes**: Toggle random and repeat playback
- **Auto-Advance**: Automatically advance to next track when current ends
- **File Operations**: Add entire folders or individual files to playlists
- **Track Reordering**: Move tracks up/down in playlist with visual feedback

### 6. Files Created/Modified

#### New Files:
- `requirements.txt` - Lists all Python dependencies
- `build_exe.bat` - Automated build script for creating the executable
- `import_requests_backup.py` - Backup of original download script

#### Modified Files:
- `audio_duplicate_finder.py` - Main application with combined functionality
- `audio_duplicate_finder.spec` - Updated PyInstaller spec with new dependencies
- `run_audio_finder.bat` - Updated to run the new executable

#### Generated:
#### Generated:
- `dist/audio_duplicate_finder.exe` - Windowed executable (21.6MB) with all functionality

## How to Use

### Download Audio Files:
1. Run the application
2. Go to "Download Audio" tab
3. Select or enter a URL in the dropdown
4. Choose a download folder (or use default "aio_downloads")
5. **Optional**: Select a "Check Against Folder" to avoid downloading duplicates
   - This can be any folder containing your existing audio collection
   - The app will scan all subfolders for audio files
   - Files that match existing ones (by content, not just filename) will be skipped
6. Click "Download Audio Files"
7. Monitor progress in the message area
8. Review summary showing downloads and duplicates skipped

### Metadata Management:
1. Go to "Metadata" tab
2. Select an audio folder to scan
3. Click "Scan Metadata" to read existing metadata from all audio files
4. Click "Check MusicBrainz" to compare with online database and find potential updates
5. Review suggestions in the table (current vs MusicBrainz data)
6. Double-click any row to edit metadata manually
7. Use "Use MB Suggestions" to apply MusicBrainz recommendations
8. Click "Update Selected" to save changes to the actual audio file
9. Use "Skip Selected" to ignore suggestions for specific files

## Building the Executable

To rebuild the executable after making changes:

1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

2. Build with PyInstaller:
   ```
   pyinstaller audio_duplicate_finder.spec
   ```

Or simply run: `build_exe.bat`

The executable will be windowed (no console window appears when running) and placed in the `dist/` folder.

## File Cleanup

The following files have been removed as they are no longer needed:
- `import_requests_backup.py` - Old separate download script (now integrated)
- `AudioDuplicateFinder.exe` - Old executable
- `build/` directory - Temporary build artifacts (regenerated on build)

## Dependencies
- `requests` - For downloading files from websites
- `beautifulsoup4` - For parsing HTML and finding audio links
- `mutagen` - For reading and writing audio file metadata
- `musicbrainzngs` - For querying MusicBrainz database
- `pygame` - For audio playback and player functionality
- `tkinter` - For the GUI (built into Python)
- `pyinstaller` - For creating the executable

The executable is self-contained and includes all audio processing and playback libraries.