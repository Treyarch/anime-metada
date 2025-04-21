# Anime Metadata Updater
This script processes a folder of anime series, updates ratings and genres from Jikan API, translates plot/outline text to French using Claude API, and manages MPAA ratings across episode files.

## Requirements

- Python 3.8+
- Required packages: requests, xml.etree.ElementTree, anthropic
- API access to Jikan (https://jikan.moe/) - no authentication required
- Claude API key for translation (optional if only updating metadata)
- YouTube Data API key for trailer search (optional if using Jikan API trailers only)

## Code Structure

The codebase is organized into the following modules and packages:

```
├── anime_metadata_updater.py   # Entry point script (run this)
├── src/                        # Source code package
│   ├── __init__.py             # Package initialization
│   ├── main.py                 # Main implementation script
│   ├── config/                 # Configuration handling
│   │   ├── __init__.py
│   │   └── configuration.py    # Command line and environment config
│   ├── core/                   # Core functionality
│   │   ├── __init__.py
│   │   ├── updater.py          # Main AnimeMetadataUpdater class
│   │   └── stats.py            # Statistics tracking
│   ├── utils/                  # Utility functions
│   │   ├── __init__.py
│   │   ├── file_utils.py       # File operations (read/write XML)
│   │   ├── folder_utils.py     # Folder traversal and management
│   │   └── language_utils.py   # Language detection and text processing
│   ├── api/                    # API integrations
│   │   ├── __init__.py
│   │   ├── jikan_api.py        # Jikan API with rate limiting
│   │   ├── claude_api.py       # Claude API for translation
│   │   └── youtube_api.py      # YouTube API for trailers
│   └── processors/             # File processors
│       ├── __init__.py
│       ├── nfo_processor.py    # Processing for tvshow.nfo files
│       ├── episode_processor.py # Processing for episode NFO files
│       └── mpaa_processor.py   # MPAA tag management
└── tests/                      # Test directory
```

## Script Functionality

1. Folder Traversal

- Script recursively walks through the main anime folder and all subfolders
- Looks for "tvshow.nfo" files which contain metadata for each anime series
- Can also process episode NFO files for MPAA rating management


2. Metadata Extraction

- Parses each tvshow.nfo file using XML parsing
- Extracts the title, current plot, and outline information


3. Jikan API Integration

- Uses the extracted title to search the Jikan API
- Endpoint: https://api.jikan.moe/v4/anime?q={title}
- Retrieves community score/rating, genres, themes, and trailer information for the anime


4. Metadata Update

- Updates the <rating> tag in the tvshow.nfo file with the score from Jikan
- Replaces all <genre> tags with genres from the Jikan API
- Updates <tag> elements with theme data from the Jikan API
- Updates <trailer> element with YouTube trailer links in Kodi-compatible format
- Uses YouTube Data API to find official trailers when not available in Jikan API
- Retrieves the most viewed trailers using the API's viewCount sorting
- Provides clean and reliable trailer links without relying on web scraping
- Handles cases where anime titles might not match exactly


5. Plot Translation (Optional)

- Uses Claude API to translate <plot> and <outline> tags from English to French
- Preserves formatting and special characters in the translation
- Can be skipped with --skip-translate or --rating-only options


6. MPAA Rating Management (Optional)

- Can sync MPAA ratings from tvshow.nfo to all episode NFO files in the series folder
- Can remove MPAA ratings from all episode NFO files
- Works with files named like "3X3 Eyes S02E03 [BDRIP][1080p x264 Multi].nfo"


7. Error Handling

- Implements robust error handling for API failures
- Logs issues with specific files or API responses
- Continues processing other files if one fails


8. File Writing

- Writes the modified XML back to the original tvshow.nfo file
- Maintains original file structure and encoding


9. Rate Limiting

- Respects Jikan API rate limits (60 requests per minute, 3 requests per second)
- Implements sophisticated rate limiting mechanism to prevent API throttling
- Tracks request timestamps to ensure compliance with API limits


10. Progress Reporting

- Displays progress information during execution
- Generates a summary of changes made upon completion


## Quick Start

1. Install dependencies: `pip install -r requirements.txt`
2. Set up your .env file with API keys and folder path
3. Run the script: `python anime_metadata_updater.py`

For detailed installation and configuration instructions, see [INSTALLATION.md](INSTALLATION.md).

## Usage Example

```bash 
python anime_metadata_updater.py --folder "/path/to/anime/collection" --claude-api-key "your-api-key"
```

## Skip Translation Example

```bash
python anime_metadata_updater.py --folder "/path/to/anime/collection" --skip-translate
```

## MPAA Management Examples

```bash
# Sync MPAA ratings from tvshow.nfo to episode files
python anime_metadata_updater.py --folder "/path/to/anime/collection" --sync-mpaa

# Force-update MPAA ratings from tvshow.nfo to episode files
python anime_metadata_updater.py --folder "/path/to/anime/collection" --sync-mpaa --force-update

# Remove MPAA ratings from all episode files
python anime_metadata_updater.py --folder "/path/to/anime/collection" --remove-mpaa
```

## Batch Processing Examples

```bash
# Enable batch mode with default 1-second delay between operations
python anime_metadata_updater.py --folder "/path/to/anime/collection" --batch-mode

# Set a custom delay of 2.5 seconds between operations
python anime_metadata_updater.py --folder "/path/to/anime/collection" --batch-mode --batch-delay 2.5

# Combine batch mode with other options
python anime_metadata_updater.py --folder "/path/to/anime/collection" --batch-mode --batch-delay 1.5 --skip-translate
```

## Folder Limit and Offset Examples

```bash
# Process only the first 5 anime folders in alphabetical order
python anime_metadata_updater.py --folder "/path/to/anime/collection" --max-folders 5

# Process 10 folders with batch mode enabled
python anime_metadata_updater.py --folder "/path/to/anime/collection" --max-folders 10 --batch-mode

# Process a limited number of folders with MPAA sync
python anime_metadata_updater.py --folder "/path/to/anime/collection" --max-folders 20 --sync-mpaa

# Skip the first 30 folders and process the next 10
python anime_metadata_updater.py --folder "/path/to/anime/collection" --folder-offset 30 --max-folders 10

# Process all folders after the first 50
python anime_metadata_updater.py --folder "/path/to/anime/collection" --folder-offset 50
```