# Anime Metadata Updater
This script processes a folder of anime series, updates ratings and genres from Jikan API, translates plot/outline text to French using Claude API, and manages MPAA ratings across episode files.

## Requirements

- Python 3.8+
- Required packages: requests, xml.etree.ElementTree, anthropic
- API access to Jikan (https://jikan.moe/) - no authentication required
- Claude API key for translation (optional if only updating metadata)
- YouTube Data API key for trailer search (optional if using Jikan API trailers only)

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


## Configuration

- Store the Claude API key securely (optional if only updating metadata)
- Allow configuration of source folder path via command line arguments
- Provide options to only update ratings or only translate descriptions

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