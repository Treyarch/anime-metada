# Installation and Usage Guide

## Installation

1. Make sure you have Python 3.8 or higher installed.

2. Install the required packages:

```bash
pip install -r requirements.txt
```

3. Get your Claude API key from Anthropic. You'll need this to use the translation functionality.

## Usage

The basic command to run the script is:

```bash
python src/anime_metadata_updater.py --folder "/path/to/anime/collection" --claude-api-key "your-api-key"
```

### Command Line Options

- `--folder`: (Required) Path to your anime collection folder
- `--claude-api-key`: Your API key for Claude (required only if you want to translate descriptions)
- `--translate-only`: Only translate descriptions, skip rating updates
- `--rating-only`: Only update ratings, skip translations
- `--skip-translate`: Skip translation of descriptions entirely
- `--force-update`: Force update of ratings even if they already exist

### Examples

1. Update both ratings and genres, and translate descriptions:

```bash
python src/anime_metadata_updater.py --folder "D:\anime\collection" --claude-api-key "your-api-key"
```

2. Only update ratings and genres (no translation):

```bash
python src/anime_metadata_updater.py --folder "D:\anime\collection" --claude-api-key "your-api-key" --rating-only
```

3. Only translate descriptions (no rating updates):

```bash
python src/anime_metadata_updater.py --folder "D:\anime\collection" --claude-api-key "your-api-key" --translate-only
```

4. Only update ratings and genres and skip translation entirely (no need for Claude API key):

```bash
python src/anime_metadata_updater.py --folder "D:\anime\collection" --skip-translate
```

5. Process a specific anime folder:

```bash
python src/anime_metadata_updater.py --folder "D:\anime\collection\Attack on Titan" --claude-api-key "your-api-key"
```

## Test with Example

You can test the script with the included example:

```bash
python src/anime_metadata_updater.py --folder "D:\www\anime-metadata\example" --claude-api-key "your-api-key"
```

## Logging

The script generates log output to both the console and a file named `anime_metadata_updater.log`. Check this file for detailed information about the script's execution.
