"""
YouTube API integration for anime metadata updater.
"""

import re
import time
import requests
import logging
import os
import sys

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))


logger = logging.getLogger(__name__)

class YouTubeAPI:
    """
    Class for handling YouTube API requests for trailer searches.
    """
    
    def __init__(self, youtube_api_key, stats, options=None):
        """
        Initialize the YouTube API handler.
        
        Args:
            youtube_api_key: YouTube Data API key
            stats: Statistics object for tracking API calls
            options: Options dictionary
        """
        self.youtube_api_key = youtube_api_key
        self.stats = stats
        self.options = options or {}
        self.batch_delay = self.options.get('batch_delay', 1.0)
    
    def extract_youtube_id(self, trailer_data):
        """
        Extract YouTube video ID from Jikan API trailer data.
        
        Args:
            trailer_data: Trailer data from Jikan API
            
        Returns:
            YouTube video ID if found, None otherwise
        """
        youtube_id = None
        
        if trailer_data and isinstance(trailer_data, dict):
            # First try the direct youtube_id field
            youtube_id = trailer_data.get('youtube_id')
            
            # If not available, try to extract from embed_url
            if not youtube_id:
                embed_url = trailer_data.get('embed_url', '')
                if embed_url and isinstance(embed_url, str):
                    youtube_match = re.search(r'(?:youtube\.com\/embed\/|youtu.be\/)([a-zA-Z0-9_-]+)', embed_url)
                    if youtube_match:
                        youtube_id = youtube_match.group(1)
            
            # If still not found, try to extract from url
            if not youtube_id:
                url = trailer_data.get('url', '')
                if url and isinstance(url, str):
                    youtube_match = re.search(r'(?:youtube\.com\/watch\?v=|youtu.be\/)([a-zA-Z0-9_-]+)', url)
                    if youtube_match:
                        youtube_id = youtube_match.group(1)
        
        return youtube_id
    
    def search_trailer(self, title):
        """
        Search YouTube for an official trailer of the anime using YouTube Data API.
        Uses the API to get the top results ordered by view count.
        
        Args:
            title: The anime title to search for
            
        Returns:
            A YouTube video ID if found, None otherwise
        """
        if not self.youtube_api_key:
            logger.warning("No YouTube API key provided, skipping trailer search")
            return None
            
        try:
            # Clean and prepare the search query
            search_query = f"{title} official trailer anime"
            
            # Construct the YouTube Data API URL
            api_url = "https://www.googleapis.com/youtube/v3/search"
            
            # Set up the API parameters as requested
            params = {
                'part': 'snippet',
                'maxResults': 5,
                'q': search_query,
                'type': 'video',  # Only get videos, not playlists or channels
                'order': 'viewCount',  # Sort by view count
                'key': self.youtube_api_key
            }
            
            # Check for batch delay if applicable
            if self.options.get('batch_mode', False) and self.batch_delay > 0:
                time.sleep(self.batch_delay)
            
            # Make the API request
            logger.info(f"Searching YouTube API for '{title}' trailer")
            self.stats.increment("youtube_api_calls")
            response = requests.get(api_url, params=params, timeout=10)
            
            # Check for API errors
            if response.status_code != 200:
                logger.warning(f"YouTube API error: {response.status_code} - {response.text}")
                return None
                
            # Parse the response
            data = response.json()
            
            # Check if we got any results
            if not data.get('items'):
                logger.warning(f"No YouTube videos found for {title}")
                return None
                
            # Get the first result (highest view count)
            top_video = data['items'][0]
            video_id = top_video['id']['videoId']
            video_title = top_video['snippet']['title']
            
            logger.info(f"Found YouTube trailer via API for {title}: {video_id} - '{video_title}'")
            return video_id
            
        except Exception as e:
            logger.error(f"Error searching YouTube API for {title}: {str(e)}")
            return None
