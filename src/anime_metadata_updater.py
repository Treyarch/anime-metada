#!/usr/bin/env python3
"""
Anime Metadata Updater

This script processes a folder of anime series, updates ratings from Jikan API,
and translates plot/outline text to French using Claude API.
"""

import os
import sys
import time
import argparse
import logging
import re
import xml.etree.ElementTree as ET
import codecs
import requests
from anthropic import Anthropic
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('anime_metadata_updater.log')
    ]
)
logger = logging.getLogger(__name__)

def read_xml_file(file_path):
    """
    Read an XML file preserving encoding and return the content and encoding info.
    """
    # Check for BOM
    with open(file_path, 'rb') as f:
        first_bytes = f.read(4)
        has_bom = first_bytes.startswith(b'\xef\xbb\xbf')
    
    # Read file with proper encoding
    if has_bom:
        with codecs.open(file_path, 'r', encoding='utf-8-sig') as f:
            content = f.read()
    else:
        with codecs.open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    
    return content, has_bom

def write_xml_file(file_path, xml_string, has_bom=False):
    """
    Write XML content to file with proper encoding.
    Preserves BOM if it was in the original file.
    Ensures the XML declaration is exactly: <?xml version="1.0" encoding="utf-8" standalone="yes"?>
    """
    # Ensure xml_string is a string, not bytes
    if isinstance(xml_string, bytes):
        xml_string = xml_string.decode('utf-8')
    
    # Ensure the XML declaration is exactly what we want
    # First, remove any XML declaration that might be there
    if xml_string.startswith('<?xml'):
        xml_string = xml_string[xml_string.find('?>')+2:].lstrip()
    
    # Add the exact XML declaration we want
    xml_string = '<?xml version="1.0" encoding="utf-8" standalone="yes"?>\n' + xml_string
        
    # Add BOM if the original had it
    if has_bom:
        with open(file_path, 'wb') as f:
            f.write(b'\xef\xbb\xbf')
            f.write(xml_string.encode('utf-8'))
    else:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(xml_string)


class AnimeMetadataUpdater:
    """Main class for updating anime metadata."""
    
    def __init__(self, folder_path, claude_api_key=None, youtube_api_key=None, options=None):
        """Initialize the updater with folder path and API keys."""
        self.folder_path = os.path.abspath(folder_path)
        # Initialize Claude client without proxy settings
        if claude_api_key:
            self.claude_client = Anthropic(api_key=claude_api_key)
        else:
            self.claude_client = None
        
        # Store the YouTube API key
        self.youtube_api_key = youtube_api_key
        
        self.options = options or {}
        self.jikan_base_url = "https://api.jikan.moe/v4/anime"
        
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
        
        # Rate limiting for Jikan API
        self.jikan_requests = []  # Timestamps of recent requests
        self.jikan_minute_limit = 60  # Max 60 requests per minute
        self.jikan_second_limit = 3   # Max 3 requests per second
        
        # Rate limiting for Claude API and general batch processing
        self.claude_requests = []  # Timestamps of Claude API requests
        self.claude_minute_limit = 50  # Conservative limit for Claude API
        self.claude_second_limit = 2   # Conservative limit for Claude API
        self.batch_delay = self.options.get('batch_delay', 1.0)  # Default 1 second between batch operations
        
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
            "jikan_api_calls": 0,
            "claude_api_calls": 0,
            "youtube_api_calls": 0,
            "errors": 0
        }
        
        # Ensure the folder exists
        if not os.path.isdir(self.folder_path):
            raise ValueError(f"The specified folder does not exist: {self.folder_path}")
            
        logger.info(f"Initializing with folder: {self.folder_path}")
        logger.info(f"Options: {self.options}")
        if self.is_default_mode:
            logger.info("Running in default mode - processing all content types")
        logger.info(f"Translation {'enabled' if self.claude_client else 'disabled'}")
        logger.info(f"YouTube API {'enabled' if self.youtube_api_key else 'disabled - trailer search will fall back to Jikan API'}")
    
    def run(self):
        """Main method to run the updater."""
        logger.info("Starting anime metadata update process")
        
        # Log batch mode if enabled
        if self.options.get('batch_mode', False):
            logger.info(f"Batch mode enabled with {self.batch_delay}s delay between operations")
        
        # Check if we are only handling MPAA tags
        if self.options.get('sync_mpaa', False) or self.options.get('remove_mpaa', False):
            self._process_mpaa_tags()
            self._print_summary()
            return
        
        # Check if we're only processing episode files
        episodes_only = self.options.get('episodes_only', False)
        if episodes_only:
            logger.info("Processing episode files only (skipping tvshow.nfo files)")
        
        # Process folders
        for root, dirs, files in os.walk(self.folder_path):
            # Process tvshow.nfo if not in episodes-only mode
            if not episodes_only and 'tvshow.nfo' in files:
                nfo_path = os.path.join(root, 'tvshow.nfo')
                try:
                    # Track batch operations
                    if self.options.get('batch_mode', False):
                        self.stats["batch_operations"] += 1
                        
                    self._process_nfo_file(nfo_path)
                    
                except Exception as e:
                    logger.error(f"Error processing {nfo_path}: {str(e)}")
                    self.stats["errors"] += 1
            
            # Check if we need to process episode files
            # Added default mode processing for episode files
            if self.options.get('translate_episodes', False) or episodes_only or self.is_default_mode:
                # Get all episode NFO files in this folder
                episode_files = [f for f in files if f.endswith('.nfo') and f != 'tvshow.nfo']
                
                if episode_files:
                    logger.info(f"Found {len(episode_files)} episode NFO files in {root}")
                    
                    for episode_file in episode_files:
                        episode_path = os.path.join(root, episode_file)
                        try:
                            # Track batch operations
                            if self.options.get('batch_mode', False):
                                self.stats["batch_operations"] += 1
                                
                            self._process_episode_nfo(episode_path)
                            
                        except Exception as e:
                            logger.error(f"Error processing episode {episode_path}: {str(e)}")
                            self.stats["errors"] += 1
        
        self._print_summary()
    
    def _process_mpaa_tags(self):
        """Process MPAA tags in episode NFO files based on tvshow.nfo."""
        logger.info("Starting MPAA tag processing")
        
        for root, dirs, files in os.walk(self.folder_path):
            # Check if there's a tvshow.nfo file
            tvshow_path = os.path.join(root, 'tvshow.nfo')
            if not os.path.exists(tvshow_path):
                continue
            
            if self.options.get('sync_mpaa', False):
                # Get the MPAA rating from tvshow.nfo
                mpaa_value = self._get_mpaa_from_tvshow(tvshow_path)
                if not mpaa_value:
                    logger.warning(f"No MPAA tag found in {tvshow_path}, skipping folder")
                    continue
                
                logger.info(f"Found MPAA rating '{mpaa_value}' in {tvshow_path}")
            
            # Find all episode NFO files in this folder
            episode_nfos = []
            for file in files:
                if file.endswith('.nfo') and file != 'tvshow.nfo':
                    episode_nfos.append(file)
            
            if not episode_nfos:
                logger.info(f"No episode NFO files found in {root}")
                continue
            
            logger.info(f"Found {len(episode_nfos)} episode NFO files in {root}")
            
            # Process each episode NFO file
            for episode_file in episode_nfos:
                episode_path = os.path.join(root, episode_file)
                try:
                    # Track batch operations
                    if self.options.get('batch_mode', False):
                        self.stats["batch_operations"] += 1
                        # Apply batch delay if configured
                        if self.batch_delay > 0:
                            time.sleep(self.batch_delay)
                    
                    if self.options.get('sync_mpaa', False):
                        self._add_mpaa_to_episode(episode_path, mpaa_value)
                    elif self.options.get('remove_mpaa', False):
                        self._remove_mpaa_from_episode(episode_path)
                except Exception as e:
                    logger.error(f"Error processing episode {episode_path}: {str(e)}")
                    self.stats["errors"] += 1
    
    def _get_mpaa_from_tvshow(self, tvshow_path):
        """Extract MPAA rating from tvshow.nfo file."""
        try:
            # Read the file content preserving encoding
            xml_content, _ = read_xml_file(tvshow_path)
            
            # Parse the XML while preserving formatting
            parser = ET.XMLParser(encoding='utf-8')
            root = ET.fromstring(xml_content.encode('utf-8'), parser=parser)
            
            mpaa_elem = root.find('mpaa')
            if mpaa_elem is not None and mpaa_elem.text:
                return mpaa_elem.text.strip()
            
            return None
            
        except Exception as e:
            logger.error(f"Error reading MPAA from {tvshow_path}: {str(e)}")
            return None
    
    def _add_mpaa_to_episode(self, episode_path, mpaa_value):
        """Add or update MPAA tag in episode NFO file."""
        try:
            # Read the file content preserving encoding
            xml_content, has_bom = read_xml_file(episode_path)
            
            # Parse the XML while preserving formatting
            parser = ET.XMLParser(encoding='utf-8')
            root = ET.fromstring(xml_content.encode('utf-8'), parser=parser)
            tree = ET.ElementTree(root)
            
            # Check if it's an episode XML format
            if root.tag != 'episodedetails':
                logger.warning(f"File {episode_path} is not an episode NFO, skipping")
                return
            
            # Check if MPAA tag already exists
            mpaa_elem = root.find('mpaa')
            if mpaa_elem is None:
                # Create new MPAA element
                mpaa_elem = ET.SubElement(root, 'mpaa')
                
            # Update the MPAA value
            force_update = self.options.get('force_update', False)
            if mpaa_elem.text != mpaa_value or force_update:
                mpaa_elem.text = mpaa_value
                
                # Convert tree to string without the XML declaration (we'll add the exact one we want later)
                xml_string = ET.tostring(root, encoding='utf-8', xml_declaration=False).decode('utf-8')
                
                # Write the file preserving encoding
                write_xml_file(episode_path, xml_string, has_bom)
                
                log_message = "Updated MPAA rating" if mpaa_elem.text != mpaa_value else "Force-updated MPAA rating"
                logger.info(f"{log_message} to '{mpaa_value}' in {episode_path}")
                self.stats["episodes_updated"] += 1
            else:
                logger.info(f"MPAA already set to '{mpaa_value}' in {episode_path}")
                
        except Exception as e:
            logger.error(f"Error adding MPAA to {episode_path}: {str(e)}")
            self.stats["errors"] += 1
    
    def _remove_mpaa_from_episode(self, episode_path):
        """Remove MPAA tag from episode NFO file if it exists."""
        try:
            # Read the file content preserving encoding
            xml_content, has_bom = read_xml_file(episode_path)
            
            # Parse the XML while preserving formatting
            parser = ET.XMLParser(encoding='utf-8')
            root = ET.fromstring(xml_content.encode('utf-8'), parser=parser)
            tree = ET.ElementTree(root)
            
            # Check if it's an episode XML format
            if root.tag != 'episodedetails':
                logger.warning(f"File {episode_path} is not an episode NFO, skipping")
                return
            
            # Find and remove MPAA tag if it exists
            mpaa_elem = root.find('mpaa')
            if mpaa_elem is not None:
                root.remove(mpaa_elem)
                
                # Convert tree to string without the XML declaration (we'll add the exact one we want later)
                xml_string = ET.tostring(root, encoding='utf-8', xml_declaration=False).decode('utf-8')
                
                # Write the file preserving encoding
                write_xml_file(episode_path, xml_string, has_bom)
                
                logger.info(f"Removed MPAA rating from {episode_path}")
                self.stats["episodes_updated"] += 1
            else:
                logger.info(f"No MPAA tag found in {episode_path}")
                
        except Exception as e:
            logger.error(f"Error removing MPAA from {episode_path}: {str(e)}")
            self.stats["errors"] += 1
            
    def _process_nfo_file(self, nfo_path):
        """Process a single tvshow.nfo file."""
        logger.info(f"Processing: {nfo_path}")
        
        try:
            # Read the file content preserving encoding
            xml_content, has_bom = read_xml_file(nfo_path)
            
            # Parse the XML while preserving formatting
            parser = ET.XMLParser(encoding='utf-8')
            root = ET.fromstring(xml_content.encode('utf-8'), parser=parser)
            tree = ET.ElementTree(root)
            
            # Extract title and other info
            title_elem = root.find('title')
            if title_elem is None or not title_elem.text:
                logger.warning(f"No title found in {nfo_path}, skipping")
                return
                
            title = title_elem.text.strip()
            logger.info(f"Found anime: {title}")
            
            # Update changes flag
            changes_made = False
            
            # Update rating and genres if needed
            if not self.options.get('translate_only', False):
                metadata_updated = self._update_rating(root, title)
                if metadata_updated:
                    changes_made = True
                    # Increment genre update stats
                    self.stats["updated_genres"] += 1 
                    # We're also likely updating ratings in the same call
                    if root.find('rating') is not None:
                        self.stats["updated_ratings"] += 1
            
            # Translate plot and outline if needed
            should_translate = (not self.options.get('rating_only', False) and 
                               not self.options.get('skip_translate', False) and 
                               self.claude_client is not None)
            
            if should_translate:
                translations_updated = self._translate_descriptions(root)
                if translations_updated:
                    changes_made = True
                    self.stats["translated_plots"] += 1
            
            # Write back changes if any were made
            if changes_made:
                # Convert tree to string manually
                xml_string = ET.tostring(root, encoding='utf-8', xml_declaration=True).decode('utf-8')
                
                # Write the file preserving encoding
                write_xml_file(nfo_path, xml_string, has_bom)
                
                logger.info(f"Updated file: {nfo_path}")
            else:
                logger.info(f"No changes needed for: {nfo_path}")
            
            self.stats["processed_files"] += 1
            
        except ET.ParseError:
            logger.error(f"Failed to parse XML file: {nfo_path}")
            self.stats["errors"] += 1
    
    def _update_rating(self, root, title):
        """Update the anime rating, genres, and tags using Jikan API."""
        try:
            # Check if we already have a rating
            rating_elem = root.find('rating')
            has_rating = rating_elem is not None and rating_elem.text and float(rating_elem.text) > 0
            
            force_update = self.options.get('force_update', False)
            if has_rating and not force_update:
                logger.info(f"Rating already exists for {title}, checking genres and themes")
            
            # Search for the anime using Jikan API
            # Clean title for API query - handle special characters like in "3X3 Eyes"
            clean_title = title.replace(':', ' ').replace('×', 'x').strip()
            params = {'q': clean_title, 'limit': 1}
            logger.debug(f"Searching API with cleaned title: '{clean_title}' (original: '{title}')")
            response = self._make_jikan_request(params)
            
            if not response or not response.get('data') or len(response['data']) == 0:
                logger.warning(f"No results found for anime: {title}")
                return False
            
            anime_data = response['data'][0]
            changes_made = False
            
            # Update rating if needed
            score = anime_data.get('score')
            if score:
                if rating_elem is None:
                    rating_elem = ET.SubElement(root, 'rating')
                
                if rating_elem.text != str(score) or force_update:
                    rating_elem.text = str(score)
                    logger.info(f"Updated rating for {title}: {score}")
                    changes_made = True
            else:
                logger.warning(f"No score available for anime: {title}")
            
            # Update genres
            genres_data = anime_data.get('genres', [])
            if genres_data:
                # Remove all existing genre tags
                for genre_elem in root.findall('genre'):
                    root.remove(genre_elem)
                
                # Add new genre tags
                for genre_obj in genres_data:
                    genre_name = genre_obj.get('name')
                    if genre_name:
                        genre_elem = ET.SubElement(root, 'genre')
                        genre_elem.text = genre_name
                
                logger.info(f"Updated genres for {title}: {[g.get('name') for g in genres_data]}")
                changes_made = True
            else:
                logger.warning(f"No genres available for anime: {title}")
            
            # Get themes from API
            themes_data = anime_data.get('themes', [])
            if themes_data:
                # Get existing tags to compare
                existing_tags = {tag_elem.text for tag_elem in root.findall('tag') if tag_elem.text}
                theme_names = {t.get('name') for t in themes_data if t.get('name')}
                
                # Only proceed if there are differences or force update is enabled
                if existing_tags != theme_names or force_update:
                    # Remove existing tag elements
                    for tag_elem in root.findall('tag'):
                        root.remove(tag_elem)
                    
                    # Add new tag elements for themes
                    for theme_obj in themes_data:
                        theme_name = theme_obj.get('name')
                        if theme_name:
                            tag_elem = ET.SubElement(root, 'tag')
                            tag_elem.text = theme_name
                    
                    logger.info(f"Updated tags for {title}: {[t.get('name') for t in themes_data]}")
                    self.stats["updated_tags"] += 1
                    changes_made = True
                else:
                    logger.info(f"Tags already up to date for {title}")
            else:
                logger.info(f"No theme data available for anime: {title}")
            
            # Get trailer information from API
            try:
                trailer_data = anime_data.get('trailer', {})
                youtube_id = None
                trailer_source = "Jikan API"
                
                # Try to get the youtube_id from the trailer data
                if trailer_data and isinstance(trailer_data, dict):
                    # First try the direct youtube_id field
                    youtube_id = trailer_data.get('youtube_id')
                    
                    # If not available, try to extract from embed_url or url
                    if not youtube_id:
                        embed_url = trailer_data.get('embed_url', '')
                        if embed_url and isinstance(embed_url, str):
                            youtube_match = re.search(r'(?:youtube\.com\/embed\/|youtu.be\/)([a-zA-Z0-9_-]+)', embed_url)
                            if youtube_match:
                                youtube_id = youtube_match.group(1)
                    
                    if not youtube_id:
                        url = trailer_data.get('url', '')
                        if url and isinstance(url, str):
                            youtube_match = re.search(r'(?:youtube\.com\/watch\?v=|youtu.be\/)([a-zA-Z0-9_-]+)', url)
                            if youtube_match:
                                youtube_id = youtube_match.group(1)
                
                # If no trailer found in API, try YouTube search as fallback
                if not youtube_id:
                    logger.info(f"No trailer found in Jikan API for {title}, searching YouTube...")
                    youtube_id = self._search_youtube_trailer(title)
                    trailer_source = "YouTube search"
                
            except Exception as e:
                logger.error(f"Error extracting trailer for {title}: {str(e)}")
                youtube_id = None
            
            if youtube_id:
                # Format the trailer URL according to requirements
                trailer_url = f"plugin://plugin.video.youtube/play/?video_id={youtube_id}"
                
                # Get existing trailer element
                trailer_elem = root.find('trailer')
                trailer_updated = False
                
                if trailer_elem is None:
                    # Create new trailer element
                    trailer_elem = ET.SubElement(root, 'trailer')
                    trailer_elem.text = trailer_url
                    trailer_updated = True
                elif trailer_elem.text != trailer_url or force_update:
                    # Update existing trailer element
                    trailer_elem.text = trailer_url
                    trailer_updated = True
                
                if trailer_updated:
                    logger.info(f"Updated trailer for {title} from {trailer_source}: {trailer_url}")
                    self.stats["updated_trailers"] += 1
                    changes_made = True
                else:
                    logger.info(f"Trailer already up to date for {title}")
            else:
                logger.info(f"No trailer information available for anime: {title}")
            
            return changes_made
            
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            logger.error(f"Error updating metadata for {title}: {str(e)}")
            logger.debug(f"Detailed traceback for {title}: {error_details}")
            return False
    
    def _search_youtube_trailer(self, title):
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
            self.stats["youtube_api_calls"] += 1
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
    
    def _apply_jikan_rate_limits(self):
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
    
    def _make_jikan_request(self, params):
        """Make a request to the Jikan API with rate limiting.
        
        Implements Jikan API rate limits:
        - 60 requests per minute
        - 3 requests per second
        """
        try:
            # Apply rate limiting
            self._apply_jikan_rate_limits()
            
            # Add current request timestamp to the list
            current_time = time.time()
            self.jikan_requests.append(current_time)
            self.stats["jikan_api_calls"] += 1
            
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
                self.stats["jikan_api_calls"] -= 1  # Don't count failed requests
                return self._make_jikan_request(params)
                
            if response.status_code != 200:
                logger.error(f"Jikan API error: {response.status_code}")
                return None
                
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error: {str(e)}")
            return None
    
    def _translate_descriptions(self, root):
        """Translate plot and outline to French using Claude API."""
        try:
            plot_elem = root.find('plot')
            outline_elem = root.find('outline')
            
            if (plot_elem is None or not plot_elem.text) and (outline_elem is None or not outline_elem.text):
                logger.warning("No plot or outline to translate")
                return False
            
            changes_made = False
            
            # Translate plot if it exists
            if plot_elem is not None and plot_elem.text:
                the_plot = plot_elem.text.strip()
                if not self._appears_to_be_french(the_plot):
                    french_plot = self._translate_text(the_plot)
                    if french_plot:
                        plot_elem.text = french_plot
                        changes_made = True
                        logger.info("Translated plot successfully")
                else:
                    logger.info("Plot already appears to be in French, skipping translation")
            
            # Translate outline if it exists
            if outline_elem is not None and outline_elem.text:
                the_outline = outline_elem.text.strip()
                if not self._appears_to_be_french(the_outline):
                    french_outline = self._translate_text(the_outline)
                    if french_outline:
                        outline_elem.text = french_outline
                        changes_made = True
                        logger.info("Translated outline successfully")
                else:
                    logger.info("Outline already appears to be in French, skipping translation")
            
            return changes_made
            
        except Exception as e:
            logger.error(f"Error translating descriptions: {str(e)}")
            return False
    
    def _apply_claude_rate_limits(self):
        """Apply rate limiting for Claude API based on recent requests."""
        current_time = time.time()
        
        # Remove requests older than 1 minute
        self.claude_requests = [t for t in self.claude_requests if current_time - t < 60]
        
        # Check if we're over the per-minute limit
        if len(self.claude_requests) >= self.claude_minute_limit:
            # Calculate how long to wait
            oldest = min(self.claude_requests)
            wait_time = 60 - (current_time - oldest) + 0.1  # Add a small buffer
            logger.info(f"Approaching Claude API per-minute rate limit, waiting {wait_time:.2f} seconds")
            time.sleep(wait_time)
            # Clear old requests after waiting
            self.claude_requests = []
            return
        
        # Check if we've made requests in the last 1/n second (to maintain n per second)
        recent_requests = [t for t in self.claude_requests if current_time - t < (1.0 / self.claude_second_limit)]
        if recent_requests:
            # Calculate sleep time needed to maintain rate
            wait_time = (1.0 / self.claude_second_limit) - (current_time - max(recent_requests))
            if wait_time > 0:
                time.sleep(wait_time)
        
        # Check for batch delay if applicable
        if self.options.get('batch_mode', False) and self.batch_delay > 0:
            time.sleep(self.batch_delay)
            
    def _translate_text(self, text):
        """Use Claude API to translate text from English to French."""
        if not text or self.claude_client is None:
            return None
            
        try:
            # Apply rate limiting
            self._apply_claude_rate_limits()
            
            # Add current request timestamp to the list
            current_time = time.time()
            self.claude_requests.append(current_time)
            self.stats["claude_api_calls"] += 1
            
            # Get the model from options, with a default fallback
            model = self.options.get('claude_model', 'claude-3-5-haiku-latest')
            logger.debug(f"Using Claude model: {model}")
            
            response = self.claude_client.messages.create(
                model=model,
                max_tokens=1024,
                messages=[
                    {
                        "role": "user",
                        "content": f"""Translate the following text from English or Japanese to French.

IMPORTANT: Respond ONLY with the direct translation without commentary, explanation, or notes. Do not include phrases like 'Here is the translation' or 'I apologize'.

If the text is already in French, simply return it unchanged (no comments please).

Here's the text to translate:
{text}"""
                    }
                ]
            )
            
            return response.content[0].text.strip()
            
        except Exception as e:
            logger.error(f"Translation error: {str(e)}")
            return None
    
    def _process_episode_nfo(self, episode_path):
        """
        Process an episode NFO file to translate title and plot.
        
        Args:
            episode_path: Path to the episode NFO file
        """
        logger.info(f"Processing episode: {episode_path}")
        
        try:
            # Read the file content preserving encoding
            xml_content, has_bom = read_xml_file(episode_path)
            
            # Parse the XML while preserving formatting
            parser = ET.XMLParser(encoding='utf-8')
            root = ET.fromstring(xml_content.encode('utf-8'), parser=parser)
            
            # Check if it's an episode XML format
            if root.tag != 'episodedetails':
                logger.warning(f"File {episode_path} is not an episode NFO, skipping")
                return
            
            self.stats["episodes_processed"] += 1
            changes_made = False
            
            # Get MPAA from show if in default mode
            if self.is_default_mode:
                # Try to find parent tvshow.nfo
                episode_dir = os.path.dirname(episode_path)
                tvshow_path = os.path.join(episode_dir, 'tvshow.nfo')
                
                if os.path.exists(tvshow_path):
                    mpaa_value = self._get_mpaa_from_tvshow(tvshow_path)
                    if mpaa_value:
                        # Check if MPAA tag already exists
                        mpaa_elem = root.find('mpaa')
                        if mpaa_elem is None:
                            # Create new MPAA element
                            mpaa_elem = ET.SubElement(root, 'mpaa')
                            mpaa_elem.text = mpaa_value
                            changes_made = True
                            logger.info(f"Added MPAA rating '{mpaa_value}' to episode from tvshow.nfo")
                        elif mpaa_elem.text != mpaa_value:
                            mpaa_elem.text = mpaa_value
                            changes_made = True
                            logger.info(f"Updated MPAA rating to '{mpaa_value}' in episode from tvshow.nfo")
            
            # Translate title if it exists (only when translation is enabled)
            should_translate = not self.options.get('skip_translate', False) and not self.options.get('rating_only', False) and self.claude_client is not None
            
            if should_translate:
                title_elem = root.find('title')
                if title_elem is not None and title_elem.text and title_elem.text.strip():
                    # Only translate if the title is not already in French
                    if not self._appears_to_be_french(title_elem.text):
                        logger.info(f"Translating episode title...")
                        translated_title = self._translate_text(title_elem.text.strip())
                        if translated_title and translated_title != title_elem.text:
                            title_elem.text = translated_title
                            changes_made = True
                            self.stats["episode_titles_translated"] += 1
                            logger.info(f"Translated title: {translated_title}")
                
                # Translate plot if it exists
                plot_elem = root.find('plot')
                if plot_elem is not None and plot_elem.text and plot_elem.text.strip():
                    # Only translate if the plot is not already in French
                    if not self._appears_to_be_french(plot_elem.text):
                        logger.info(f"Translating episode plot...")
                        translated_plot = self._translate_text(plot_elem.text.strip())
                        if translated_plot and translated_plot != plot_elem.text:
                            plot_elem.text = translated_plot
                            changes_made = True
                            self.stats["episode_plots_translated"] += 1
                            logger.info(f"Translated plot successfully")
            
            # Write changes if any were made
            if changes_made:
                self.stats["episodes_translated"] += 1
                
                # Convert tree to string without the XML declaration (we'll add the exact one we want later)
                xml_string = ET.tostring(root, encoding='utf-8', xml_declaration=False).decode('utf-8')
                
                # Write the file preserving encoding
                write_xml_file(episode_path, xml_string, has_bom)
                
                logger.info(f"Updated episode file: {episode_path}")
            else:
                logger.info(f"No changes needed for episode: {episode_path}")
            
        except Exception as e:
            logger.error(f"Error processing episode NFO {episode_path}: {str(e)}")
            raise
    
    def _appears_to_be_french(self, text):
        """
        Simple heuristic to check if text appears to be in French already.
        This is not foolproof but helps avoid unnecessary translations.
        
        Args:
            text: Text to check
            
        Returns:
            True if the text appears to be in French
        """
        # Simple check for common French words/patterns
        french_indicators = [
            ' le ', ' la ', ' les ', ' des ', ' un ', ' une ', ' du ', ' de la ', ' à ', ' est ',
            'ç', 'é', 'è', 'ê', 'â', 'ô', 'î', 'û', 'ë', 'ï', 'ü'
        ]
        
        # Check for French indicators
        text_lower = text.lower()
        french_indicators_found = sum(1 for indicator in french_indicators if indicator in text_lower)
        
        # Heuristic: if more than 2 French indicators are found, consider it French
        return french_indicators_found > 2
    
    def _print_summary(self):
        """Print a summary of the changes made."""
        logger.info("=" * 50)
        logger.info("PROCESSING COMPLETE")
        logger.info("=" * 50)
        
        if self.options.get('sync_mpaa', False) or self.options.get('remove_mpaa', False):
            logger.info(f"Episode NFO files updated: {self.stats['episodes_updated']}")
        else:
            logger.info(f"TV Show files processed: {self.stats['processed_files']}")
            logger.info(f"Ratings updated: {self.stats['updated_ratings']}")
            logger.info(f"Genres updated: {self.stats['updated_genres']}")
            logger.info(f"Tags updated: {self.stats['updated_tags']}")
            logger.info(f"Trailers updated: {self.stats['updated_trailers']}")
            logger.info(f"TV Show descriptions translated: {self.stats['translated_plots']}")
            
            if self.options.get('translate_episodes', False) or self.options.get('episodes_only', False) or self.is_default_mode:
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
        if self.options.get('batch_mode', False):
            logger.info("-" * 50)
            logger.info("BATCH PROCESSING STATISTICS")
            logger.info(f"Batch operations: {self.stats['batch_operations']}")
            logger.info(f"Batch delay: {self.batch_delay} seconds")
            
        logger.info("-" * 50)
        logger.info(f"Errors encountered: {self.stats['errors']}")
        logger.info("=" * 50)


def load_environment():
    """Load environment variables from .env file."""
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
        'batch_delay': env_batch_delay
    }


def parse_arguments():
    """Parse command line arguments with defaults from environment variables."""
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


def main():
    """Main entry point for the script."""
    try:
        args = parse_arguments()
        
        options = {
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
            "batch_delay": args.batch_delay
        }
        
        # Log batch mode settings if enabled
        if args.batch_mode:
            logger.info(f"Batch mode enabled with delay: {args.batch_delay} seconds between operations")
        
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
