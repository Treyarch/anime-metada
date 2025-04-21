"""
Statistics tracking for anime metadata updater.
"""

import logging
import os
import sys

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))


logger = logging.getLogger(__name__)

class UpdaterStats:
    """Class for tracking statistics during the update process."""
    
    def __init__(self):
        """Initialize statistics counters."""
        self.stats = {
            "processed_files": 0,
            "updated_ratings": 0,
            "updated_genres": 0,
            "updated_tags": 0,
            "updated_trailers": 0,
            "translated_plots": 0,
            "episodes_processed": 0,
            "episodes_translated": 0,
            "episode_titles_translated": 0,
            "episode_plots_translated": 0,
            "episodes_updated": 0,
            "batch_operations": 0,
            "batch_skipped": 0,
            "folders_processed": 0,
            "folders_skipped_limit": 0,
            "folders_skipped_offset": 0,
            "jikan_api_calls": 0,
            "claude_api_calls": 0,
            "youtube_api_calls": 0,
            "errors": 0
        }
    
    def increment(self, stat_name, amount=1):
        """
        Increment a statistic counter.
        
        Args:
            stat_name: Name of the statistic to increment
            amount: Amount to increment by (default: 1)
        """
        if stat_name in self.stats:
            self.stats[stat_name] += amount
    
    def set(self, stat_name, value):
        """
        Set a statistic value.
        
        Args:
            stat_name: Name of the statistic to set
            value: Value to set
        """
        if stat_name in self.stats:
            self.stats[stat_name] = value
    
    def get(self, stat_name):
        """
        Get a statistic value.
        
        Args:
            stat_name: Name of the statistic to get
            
        Returns:
            Current value of the statistic
        """
        return self.stats.get(stat_name, 0)
    
    def print_summary(self, options):
        """
        Print a summary of the changes made.
        
        Args:
            options: Options dictionary from configuration
        """
        logger.info("=" * 50)
        logger.info("PROCESSING COMPLETE")
        logger.info("=" * 50)
        
        # Folder processing statistics
        logger.info("FOLDER PROCESSING STATISTICS")
        logger.info(f"Folders processed: {self.stats['folders_processed']}")
        
        if self.stats['folders_skipped_offset'] > 0:
            logger.info(f"Folders skipped due to offset: {self.stats['folders_skipped_offset']}")
            logger.info(f"Folder offset: {options.get('folder_offset', 0)}")
            
        if self.stats['folders_skipped_limit'] > 0:
            logger.info(f"Folders skipped due to limit: {self.stats['folders_skipped_limit']}")
            logger.info(f"Folder limit: {options.get('max_folders', 0)}")
            
        logger.info("-" * 50)
        
        if options.get('sync_mpaa', False) or options.get('remove_mpaa', False):
            logger.info(f"Episode NFO files updated: {self.stats['episodes_updated']}")
        else:
            logger.info(f"TV Show files processed: {self.stats['processed_files']}")
            logger.info(f"Ratings updated: {self.stats['updated_ratings']}")
            logger.info(f"Genres updated: {self.stats['updated_genres']}")
            logger.info(f"Tags updated: {self.stats['updated_tags']}")
            logger.info(f"Trailers updated: {self.stats['updated_trailers']}")
            logger.info(f"TV Show descriptions translated: {self.stats['translated_plots']}")
            
            if options.get('translate_episodes', False) or options.get('episodes_only', False):
                logger.info(f"Episode files processed: {self.stats['episodes_processed']}")
                logger.info(f"Episode files with translations: {self.stats['episodes_translated']}")
                logger.info(f"Episode titles translated: {self.stats['episode_titles_translated']}")
                logger.info(f"Episode plots translated: {self.stats['episode_plots_translated']}")
        
        # API call statistics
        logger.info("-" * 50)
        logger.info("API CALL STATISTICS")
        logger.info(f"Jikan API calls: {self.stats['jikan_api_calls']}")
        logger.info(f"Claude API calls: {self.stats['claude_api_calls']}")
        logger.info(f"YouTube API calls: {self.stats['youtube_api_calls']}")
        
        # Batch mode statistics if enabled
        if options.get('batch_mode', False):
            logger.info("-" * 50)
            logger.info("BATCH PROCESSING STATISTICS")
            logger.info(f"Batch operations: {self.stats['batch_operations']}")
            logger.info(f"Batch delay: {options.get('batch_delay', 1.0)} seconds")
            
        logger.info("-" * 50)
        logger.info(f"Errors encountered: {self.stats['errors']}")
        logger.info("=" * 50)
