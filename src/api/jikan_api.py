"""
Jikan API integration for anime metadata updater.
"""

import time
import requests
import logging
from src.utils.language_utils import clean_title_for_api
import os
import sys

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))


logger = logging.getLogger(__name__)

class JikanAPI:
    """
    Class for handling Jikan API requests with rate limiting.
    
    The Jikan API has the following rate limits:
    - 60 requests per minute
    - 3 requests per second
    """
    
    def __init__(self, stats, options=None):
        """
        Initialize the Jikan API handler.
        
        Args:
            stats: Statistics object for tracking API calls
            options: Options dictionary
        """
        self.jikan_base_url = "https://api.jikan.moe/v4/anime"
        self.jikan_requests = []  # Timestamps of recent requests
        self.jikan_minute_limit = 60  # Max 60 requests per minute
        self.jikan_second_limit = 3   # Max 3 requests per second
        self.stats = stats
        self.options = options or {}
        self.batch_delay = self.options.get('batch_delay', 1.0)  # Default 1 second between batch operations
    
    def _apply_rate_limits(self):
        """Apply rate limiting for Jikan API based on recent requests."""
        current_time = time.time()
        
        # Remove requests older than 1 minute
        self.jikan_requests = [t for t in self.jikan_requests if current_time - t < 60]
        
        # Check if we're over the per-minute limit
        if len(self.jikan_requests) >= self.jikan_minute_limit:
            # Calculate how long to wait
            oldest = min(self.jikan_requests)
            wait_time = 60 - (current_time - oldest) + 0.1  # Add a small buffer
            logger.info(f"Approaching per-minute rate limit, waiting {wait_time:.2f} seconds")
            time.sleep(wait_time)
            # Clear old requests after waiting
            self.jikan_requests = []
            return
        
        # Check if we've made requests in the last 1/3 second (to maintain 3 per second)
        recent_requests = [t for t in self.jikan_requests if current_time - t < (1.0 / self.jikan_second_limit)]
        if recent_requests:
            # Calculate sleep time needed to maintain rate
            wait_time = (1.0 / self.jikan_second_limit) - (current_time - max(recent_requests))
            if wait_time > 0:
                time.sleep(wait_time)
    
    def search_anime(self, title):
        """
        Search for anime by title.
        
        Args:
            title: Anime title to search for
            
        Returns:
            API response data or None if not found
        """
        # Clean title for API query - handle special characters like in "3X3 Eyes"
        clean_title = clean_title_for_api(title)
        params = {'q': clean_title, 'limit': 1}
        logger.debug(f"Searching API with cleaned title: '{clean_title}' (original: '{title}')")
        
        return self.make_request(params)
    
    def make_request(self, params):
        """
        Make a request to the Jikan API with rate limiting.
        
        Args:
            params: Query parameters
            
        Returns:
            JSON response data or None on error
        """
        try:
            # Apply rate limiting
            self._apply_rate_limits()
            
            # Add current request timestamp to the list
            current_time = time.time()
            self.jikan_requests.append(current_time)
            self.stats.increment("jikan_api_calls")
            
            # Check for batch delay if applicable
            if self.options.get('batch_mode', False) and self.batch_delay > 0:
                time.sleep(self.batch_delay)
            
            # Make the request
            response = requests.get(self.jikan_base_url, params=params)
            
            if response.status_code == 429:
                # Rate limited, wait and retry
                logger.warning("Rate limited by Jikan API, waiting 5 seconds")
                time.sleep(5)
                # Remove the failed request timestamp
                if self.jikan_requests and self.jikan_requests[-1] == current_time:
                    self.jikan_requests.pop()
                self.stats.increment("jikan_api_calls", -1)  # Don't count failed requests
                return self.make_request(params)
                
            if response.status_code != 200:
                logger.error(f"Jikan API error: {response.status_code}")
                return None
                
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error: {str(e)}")
            return None
