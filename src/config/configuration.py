"""
Configuration module for anime metadata updater.
Handles loading environment variables and command line arguments.
"""

import os
import sys
import argparse
import logging
from dotenv import load_dotenv
import os
import sys

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))


# Set up logging
def setup_logging():
    """Configure logging for the application."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('anime_metadata_updater.log')
        ]
    )
    return logging.getLogger(__name__)

# Create logger
logger = setup_logging()

def load_environment():
    """
    Load environment variables from .env file.
    
    Returns:
        Dictionary containing environment variables
    """
    # Load environment variables
    load_dotenv()
    
    # Get environment variables
    env_folder = os.getenv('ANIME_FOLDER')
    env_claude_api_key = os.getenv('CLAUDE_API_KEY')
    env_youtube_api_key = os.getenv('YOUTUBE_API_KEY')
    env_claude_model = os.getenv('CLAUDE_MODEL', 'claude-3-5-haiku-latest')  # Default model if not specified
    
    # Parse boolean options from environment
    env_skip_translate = os.getenv('SKIP_TRANSLATE', '').lower() == 'true'
    env_rating_only = os.getenv('RATING_ONLY', '').lower() == 'true'
    env_sync_mpaa = os.getenv('SYNC_MPAA', '').lower() == 'true'
    env_force_update = os.getenv('FORCE_UPDATE', '').lower() == 'true'
    env_remove_mpaa = os.getenv('REMOVE_MPAA', '').lower() == 'true'
    env_translate_episodes = os.getenv('TRANSLATE_EPISODES', '').lower() == 'true'
    env_episodes_only = os.getenv('EPISODES_ONLY', '').lower() == 'true'
    env_batch_mode = os.getenv('BATCH_MODE', '').lower() == 'true'
    
    # Parse numeric options
    try:
        env_batch_delay = float(os.getenv('BATCH_DELAY', '1.0'))
    except (ValueError, TypeError):
        env_batch_delay = 1.0
        
    try:
        env_max_folders = int(os.getenv('MAX_FOLDERS', '0'))
    except (ValueError, TypeError):
        env_max_folders = 0
        
    try:
        env_folder_offset = int(os.getenv('FOLDER_OFFSET', '0'))
    except (ValueError, TypeError):
        env_folder_offset = 0
    
    return {
        'folder': env_folder,
        'claude_api_key': env_claude_api_key,
        'youtube_api_key': env_youtube_api_key,
        'claude_model': env_claude_model,
        'skip_translate': env_skip_translate,
        'rating_only': env_rating_only,
        'sync_mpaa': env_sync_mpaa,
        'force_update': env_force_update,
        'remove_mpaa': env_remove_mpaa,
        'translate_episodes': env_translate_episodes,
        'episodes_only': env_episodes_only,
        'batch_mode': env_batch_mode,
        'batch_delay': env_batch_delay,
        'max_folders': env_max_folders,
        'folder_offset': env_folder_offset
    }

def parse_arguments():
    """
    Parse command line arguments with defaults from environment variables.
    
    Returns:
        Parsed arguments
    """
    # Load environment variables first
    env_vars = load_environment()
    
    parser = argparse.ArgumentParser(description="Anime Metadata Updater")
    
    parser.add_argument("--folder", default=env_vars['folder'],
                        help="Path to the anime collection folder")
    parser.add_argument("--claude-api-key", default=env_vars['claude_api_key'],
                        help="API key for Claude (required for translation)")
    parser.add_argument("--youtube-api-key", default=env_vars['youtube_api_key'],
                        help="API key for YouTube Data API (required for trailer search)")
    parser.add_argument("--claude-model", default=env_vars['claude_model'],
                        help="Claude model to use for translation (default: claude-3-5-haiku-latest)")
    parser.add_argument("--translate-only", action="store_true",
                        help="Only translate descriptions, skip rating updates")
    parser.add_argument("--rating-only", action="store_true", default=env_vars['rating_only'],
                        help="Only update ratings, skip translations")
    parser.add_argument("--skip-translate", action="store_true", default=env_vars['skip_translate'],
                        help="Skip translation of descriptions")
    parser.add_argument("--force-update", action="store_true", default=env_vars['force_update'],
                        help="Force update of ratings and MPAA values even if they already exist")
    parser.add_argument("--sync-mpaa", action="store_true", default=env_vars['sync_mpaa'],
                        help="Sync MPAA rating from tvshow.nfo to all episode NFO files")
    parser.add_argument("--remove-mpaa", action="store_true", default=env_vars['remove_mpaa'],
                        help="Remove MPAA rating from all episode NFO files")
    parser.add_argument("--translate-episodes", action="store_true", default=env_vars['translate_episodes'],
                        help="Translate plot and title in episode NFO files")
    parser.add_argument("--episodes-only", action="store_true", default=env_vars['episodes_only'],
                        help="Only process episode files, skip tvshow.nfo")
    parser.add_argument("--batch-mode", action="store_true", default=env_vars['batch_mode'],
                        help="Enable batch processing mode with configurable delays between operations")
    parser.add_argument("--batch-delay", type=float, default=env_vars['batch_delay'],
                        help="Delay in seconds between batch operations (default: 1.0)")
    parser.add_argument("--max-folders", type=int, default=env_vars['max_folders'],
                        help="Maximum number of subfolders to process (0 means process all, default: 0)")
    parser.add_argument("--folder-offset", type=int, default=env_vars['folder_offset'],
                        help="Number of folders to skip before starting processing (default: 0)")
    
    args = parser.parse_args()
    
    # Validate that folder path is provided
    if not args.folder:
        parser.error("No folder path provided. Use --folder argument or set ANIME_FOLDER in .env file")
    
    # Validate that Claude API key is provided if translation is needed
    translations_needed = (not args.rating_only and not args.skip_translate and 
                          not args.sync_mpaa and not args.remove_mpaa) or args.translate_episodes
    
    if translations_needed and not args.claude_api_key:
        parser.error("Claude API key is required for translation. Use --claude-api-key argument or set CLAUDE_API_KEY in .env file, "
                     "or use --rating-only, --skip-translate options")
    
    # Validate that sync-mpaa and remove-mpaa are not used together
    if args.sync_mpaa and args.remove_mpaa:
        parser.error("--sync-mpaa and --remove-mpaa cannot be used together")
    
    return args

def create_options_dict(args):
    """
    Create options dictionary from parsed arguments.
    
    Args:
        args: Parsed command line arguments
    
    Returns:
        Options dictionary
    """
    return {
        "translate_only": args.translate_only,
        "rating_only": args.rating_only,
        "skip_translate": args.skip_translate,
        "force_update": args.force_update,
        "sync_mpaa": args.sync_mpaa,
        "remove_mpaa": args.remove_mpaa,
        "translate_episodes": args.translate_episodes,
        "episodes_only": args.episodes_only,
        "claude_model": args.claude_model,
        "batch_mode": args.batch_mode,
        "batch_delay": args.batch_delay,
        "max_folders": args.max_folders,
        "folder_offset": args.folder_offset
    }
