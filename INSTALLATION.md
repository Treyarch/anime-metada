# Installation and Usage Guide

## Installation

1. Make sure you have Python 3.8 or higher installed.

2. Install the required packages:

```bash
pip install -r requirements.txt
```

3. Get your Claude API key from Anthropic. You'll need this to use the translation functionality.

4. Get a YouTube Data API key from Google Cloud Console. This is required for finding trailers when not available in Jikan API.

5. Set up your environment:
   - Copy the `.env.template` file and rename it to `.env`
   - Edit the `.env` file and set your anime folder path, Claude API key, and YouTube API key:
     ```
     ANIME_FOLDER=D:/path/to/your/anime/collection
     CLAUDE_API_KEY=your_claude_api_key
     YOUTUBE_API_KEY=your_youtube_api_key
     ```
   - Optionally, you can enable default settings in the `.env` file:
     ```
     SKIP_TRANSLATE=true
     RATING_ONLY=true
     SYNC_MPAA=true
     FORCE_UPDATE=true
     REMOVE_MPAA=true
     ```

## Project Structure

The codebase has been organized into a modular structure for better maintainability:

```
├── anime_metadata_updater.py   # Entry point script (run this)
├── src/                        # Source code package
│   ├── __init__.py             # Package initialization
│   ├── main.py                 # Main implementation script
│   ├── config/                 # Configuration handling
│   ├── core/                   # Core functionality
│   ├── utils/                  # Utility functions
│   ├── api/                    # API integrations
│   └── processors/             # File processors
└── tests/                      # Test directory
```

This modular design makes the code easier to understand, test, and extend.

## Usage

The basic command to run the script is:

```bash
python anime_metadata_updater.py
```

With the `.env` file set up, you don't need to specify command-line arguments unless you want to override the defaults.

### Command Line Options

- `--folder`: Path to your anime collection folder (overrides ANIME_FOLDER in .env)
- `--claude-api-key`: Your API key for Claude (overrides CLAUDE_API_KEY in .env)
- `--youtube-api-key`: Your API key for YouTube Data API (overrides YOUTUBE_API_KEY in .env)
- `--translate-only`: Only translate descriptions, skip rating updates
- `--rating-only`: Only update ratings, skip translations
- `--skip-translate`: Skip translation of descriptions entirely
- `--force-update`: Force update of ratings and MPAA values even if they already exist
- `--sync-mpaa`: Sync MPAA rating from tvshow.nfo to all episode NFO files
- `--remove-mpaa`: Remove MPAA rating from all episode NFO files
- `--batch-mode`: Enable batch processing mode with configurable delays between API operations
- `--batch-delay`: Set the delay in seconds between batch operations (default: 1.0)
- `--max-folders`: Set maximum number of subfolders to process (0 means process all, default: 0)
- `--folder-offset`: Number of folders to skip before starting processing (default: 0)

Command-line options take precedence over the settings in the `.env` file.

### Examples

1. Update ratings, genres, tags, trailers, and translate descriptions:

```bash
python anime_metadata_updater.py
```

2. Only update ratings, genres, and tags (no translation):

```bash
python anime_metadata_updater.py --rating-only
```

3. Only translate descriptions (no rating updates):

```bash
python anime_metadata_updater.py --translate-only
```

4. Only update ratings and genres and skip translation entirely (no need for Claude API key):

```bash
python anime_metadata_updater.py --skip-translate
```

5. Process a specific anime folder (overriding the ANIME_FOLDER in .env):

```bash
python anime_metadata_updater.py --folder "D:\anime\collection\Attack on Titan"
```

6. Sync MPAA ratings from tvshow.nfo to all episode NFO files:

```bash
python anime_metadata_updater.py --sync-mpaa
```

7. Force update MPAA ratings from tvshow.nfo to all episode NFO files (updates even if they already match):

```bash
python anime_metadata_updater.py --sync-mpaa --force-update
```

8. Remove MPAA ratings from all episode NFO files:

```bash
python anime_metadata_updater.py --remove-mpaa
```

9. Process with batch mode to respect API rate limits (useful for large collections):

```bash
python anime_metadata_updater.py --batch-mode --batch-delay 2.0
```

10. Process only a limited number of subfolders (useful for testing or large collections):

```bash
python anime_metadata_updater.py --max-folders 5
```

11. Skip the first 20 folders and process the next 10 (useful for continuing a previous run):

```bash
python anime_metadata_updater.py --folder-offset 20 --max-folders 10
```

## Test with Example

You can test the script with the included example:

```bash
# Test MPAA sync functionality
python anime_metadata_updater.py --folder "D:\www\anime-metadata\example" --sync-mpaa

# Test MPAA removal functionality
python anime_metadata_updater.py --folder "D:\www\anime-metadata\example" --remove-mpaa

# Test normal functionality
python anime_metadata_updater.py --folder "D:\www\anime-metadata\example" --skip-translate
```

## Environment Variables

The following environment variables can be set in the `.env` file:

- `ANIME_FOLDER`: Path to your anime collection folder
- `CLAUDE_API_KEY`: Your Claude API key
- `YOUTUBE_API_KEY`: Your YouTube Data API key
- `CLAUDE_MODEL`: Claude model to use (default: "claude-3-5-haiku-latest")
- `SKIP_TRANSLATE`: Set to "true" to skip translation
- `RATING_ONLY`: Set to "true" to only update ratings
- `SYNC_MPAA`: Set to "true" to sync MPAA ratings
- `FORCE_UPDATE`: Set to "true" to force update existing values
- `REMOVE_MPAA`: Set to "true" to remove MPAA ratings
- `BATCH_MODE`: Set to "true" to enable batch processing mode
- `BATCH_DELAY`: Set a delay in seconds between API operations (default: 1.0)
- `MAX_FOLDERS`: Set maximum number of subfolders to process (0 means process all)
- `FOLDER_OFFSET`: Number of folders to skip before starting processing (default: 0)

## Logging

The script generates log output to both the console and a file named `anime_metadata_updater.log`. Check this file for detailed information about the script's execution.

## Development

To extend the functionality:

1. **API Modules**: Add new API integrations in the `src/api/` directory
2. **Processors**: Add new file processors in the `src/processors/` directory
3. **Utilities**: Add shared utility functions in the `src/utils/` directory

The modular structure makes it easy to add new features or modify existing behavior without changing the entire codebase.

### Running from Source Directory

If you prefer to run the module directly from the source directory, use:

```bash
python -m src.main
```

This alternative method ensures proper Python module resolution.