#!/usr/bin/env python3
"""
Anime Metadata Updater

This script processes a folder of anime series, updates ratings from Jikan API,
and translates plot/outline text to French using Claude API.
"""

import sys
import os
import logging

# Add the parent directory to the Python path to allow imports from 'src'
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.config.configuration import setup_logging, parse_arguments, create_options_dict
from src.core.updater import AnimeMetadataUpdater

# Set up logging
logger = setup_logging()

def main():
    """Main entry point for the script."""
    try:
        # Parse command line arguments
        args = parse_arguments()
        
        # Create options dictionary
        options = create_options_dict(args)
        
        # Create and run the updater
        updater = AnimeMetadataUpdater(
            folder_path=args.folder,
            claude_api_key=args.claude_api_key,
            youtube_api_key=args.youtube_api_key,
            options=options
        )
        
        updater.run()
        
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
