"""
Main updater class for anime metadata.
"""

import os
import time
import logging
import sys
from anthropic import Anthropic

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.core.stats import UpdaterStats
from src.api.jikan_api import JikanAPI
from src.api.claude_api import ClaudeAPI
from src.api.youtube_api import YouTubeAPI
from src.processors.nfo_processor import NFOProcessor
from src.processors.episode_processor import EpisodeProcessor
from src.processors.mpaa_processor import MPAAProcessor
from src.utils.folder_utils import get_anime_folders, get_folder_subset, get_episode_files

logger = logging.getLogger(__name__)

class AnimeMetadataUpdater:
    """Main class for updating anime metadata."""
    
    def __init__(self, folder_path, claude_api_key=None, youtube_api_key=None, options=None):
        """
        Initialize the updater with folder path and API keys.
        
        Args:
            folder_path: Path to the anime collection folder
            claude_api_key: API key for Claude translation
            youtube_api_key: API key for YouTube Data API
            options: Options dictionary
        """
        self.folder_path = os.path.abspath(folder_path)
        self.options = options or {}
        
        # Initialize statistics
        self.stats = UpdaterStats()
        
        # Initialize API clients
        
        # Initialize Claude client if API key is provided
        if claude_api_key:
            anthropic_client = Anthropic(api_key=claude_api_key)
            self.claude_api = ClaudeAPI(anthropic_client, self.stats, self.options)
        else:
            self.claude_api = None
            anthropic_client = None
        
        # Initialize Jikan API client
        self.jikan_api = JikanAPI(self.stats, self.options)
        
        # Initialize YouTube API client if API key is provided
        if youtube_api_key:
            self.youtube_api = YouTubeAPI(youtube_api_key, self.stats, self.options)
        else:
            self.youtube_api = None
        
        # Initialize processors
        self.nfo_processor = NFOProcessor(self.jikan_api, self.claude_api, self.youtube_api, self.stats, self.options)
        self.episode_processor = EpisodeProcessor(self.claude_api, self.stats, self.options)
        self.mpaa_processor = MPAAProcessor(self.stats, self.options)
        
        # Check if no specific processing flags were set - "default mode"
        # In default mode, we'll process everything
        self.is_default_mode = (
            not self.options.get('translate_only', False) and
            not self.options.get('rating_only', False) and
            not self.options.get('skip_translate', False) and
            not self.options.get('sync_mpaa', False) and
            not self.options.get('remove_mpaa', False) and
            not self.options.get('translate_episodes', False) and
            not self.options.get('episodes_only', False) and
            not self.options.get('batch_mode', False)
        )
        
        # If we're in default mode, enable episode processing
        if self.is_default_mode:
            self.options['translate_episodes'] = True
        
        # Folder processing limits
        self.max_folders = self.options.get('max_folders', 0)  # 0 means process all folders
        self.folder_offset = self.options.get('folder_offset', 0)  # 0 means start from the beginning
        
        # Ensure the folder exists
        if not os.path.isdir(self.folder_path):
            raise ValueError(f"The specified folder does not exist: {self.folder_path}")
            
        self._log_initialization()
    
    def _log_initialization(self):
        """Log initialization information."""
        logger.info(f"Initializing with folder: {self.folder_path}")
        logger.info(f"Options: {self.options}")
        
        if self.is_default_mode:
            logger.info("Running in default mode - processing all content types")
            
        logger.info(f"Translation {'enabled' if self.claude_api else 'disabled'}")
        logger.info(f"YouTube API {'enabled' if self.youtube_api else 'disabled - trailer search will fall back to Jikan API'}")
        
        if self.options.get('batch_mode', False):
            logger.info(f"Batch mode enabled with {self.options.get('batch_delay', 1.0)}s delay between operations")
        
        if self.max_folders > 0:
            logger.info(f"Folder limit set: processing up to {self.max_folders} folders")
            
        if self.folder_offset > 0:
            logger.info(f"Folder offset set: skipping first {self.folder_offset} folders")
    
    def run(self):
        """
        Main method to run the updater.
        """
        logger.info("Starting anime metadata update process")
        
        # Check if we are only handling MPAA tags
        if self.options.get('sync_mpaa', False) or self.options.get('remove_mpaa', False):
            self.mpaa_processor.process_mpaa_tags(self.folder_path)
            self.stats.print_summary(self.options)
            return
        
        # Check if we're only processing episode files
        episodes_only = self.options.get('episodes_only', False)
        if episodes_only:
            logger.info("Processing episode files only (skipping tvshow.nfo files)")
        
        # Get a list of all subfolders first if we have a folder limit or offset
        if self.max_folders > 0 or self.folder_offset > 0:
            self._process_with_folder_limits(episodes_only)
        else:
            # No limit - process everything using os.walk
            self._process_all_folders(episodes_only)
        
        # Print summary
        self.stats.print_summary(self.options)
    
    def _process_with_folder_limits(self, episodes_only=False):
        """
        Process folders with limit and offset.
        
        Args:
            episodes_only: Whether to process only episode files
        """
        all_folders = get_anime_folders(self.folder_path)
        total_folders = len(all_folders)
        logger.info(f"Found {total_folders} total anime folders")
        
        # Get the subset of folders to process
        folders_to_process, skipped_offset, skipped_limit = get_folder_subset(
            all_folders, 
            self.folder_offset,
            self.max_folders
        )
        
        # Update stats
        self.stats.set("folders_skipped_offset", skipped_offset)
        self.stats.set("folders_skipped_limit", skipped_limit)
        
        # Log info
        if skipped_offset > 0:
            logger.info(f"Skipping first {skipped_offset} folders due to offset")
            
        logger.info(f"Will process {len(folders_to_process)} folders")
        
        # Process each selected folder
        for folder in folders_to_process:
            self._process_single_folder(folder, episodes_only)
            self.stats.increment("folders_processed")
    
    def _process_all_folders(self, episodes_only=False):
        """
        Process all folders without limit.
        
        Args:
            episodes_only: Whether to process only episode files
        """
        for root, dirs, files in os.walk(self.folder_path):
            # If this folder contains a tvshow.nfo, consider it an anime folder
            if 'tvshow.nfo' in files:
                self.stats.increment("folders_processed")
                
                # Process tvshow.nfo if not in episodes-only mode
                if not episodes_only:
                    nfo_path = os.path.join(root, 'tvshow.nfo')
                    try:
                        # Track batch operations
                        if self.options.get('batch_mode', False):
                            self.stats.increment("batch_operations")
                            
                        self.nfo_processor.process_nfo_file(nfo_path)
                        
                    except Exception as e:
                        logger.error(f"Error processing {nfo_path}: {str(e)}")
                        self.stats.increment("errors")
            
                # Check if we need to process episode files
                if self.options.get('translate_episodes', False) or episodes_only or self.is_default_mode:
                    # Get all episode NFO files in this folder
                    episode_files = get_episode_files(root)
                    
                    if episode_files:
                        logger.info(f"Found {len(episode_files)} episode NFO files in {root}")
                        
                        for episode_file in episode_files:
                            episode_path = os.path.join(root, episode_file)
                            try:
                                # Track batch operations
                                if self.options.get('batch_mode', False):
                                    self.stats.increment("batch_operations")
                                    
                                self.episode_processor.process_episode_nfo(episode_path)
                                
                            except Exception as e:
                                logger.error(f"Error processing episode {episode_path}: {str(e)}")
                                self.stats.increment("errors")
    
    def _process_single_folder(self, folder_path, episodes_only=False):
        """
        Process a single anime folder (both tvshow.nfo and episode files).
        
        Args:
            folder_path: Path to the folder
            episodes_only: Whether to process only episode files
        """
        logger.info(f"Processing folder: {folder_path}")
        
        # Process tvshow.nfo if not in episodes-only mode
        if not episodes_only and os.path.exists(os.path.join(folder_path, 'tvshow.nfo')):
            nfo_path = os.path.join(folder_path, 'tvshow.nfo')
            try:
                # Track batch operations
                if self.options.get('batch_mode', False):
                    self.stats.increment("batch_operations")
                    
                self.nfo_processor.process_nfo_file(nfo_path)
                
            except Exception as e:
                logger.error(f"Error processing {nfo_path}: {str(e)}")
                self.stats.increment("errors")
        
        # Check if we need to process episode files
        if self.options.get('translate_episodes', False) or episodes_only or self.is_default_mode:
            # Get all episode NFO files in this folder
            episode_files = get_episode_files(folder_path)
            
            if episode_files:
                logger.info(f"Found {len(episode_files)} episode NFO files in {folder_path}")
                
                for episode_file in episode_files:
                    episode_path = os.path.join(folder_path, episode_file)
                    try:
                        # Track batch operations
                        if self.options.get('batch_mode', False):
                            self.stats.increment("batch_operations")
                            
                        self.episode_processor.process_episode_nfo(episode_path)
                        
                    except Exception as e:
                        logger.error(f"Error processing episode {episode_path}: {str(e)}")
                        self.stats.increment("errors")
