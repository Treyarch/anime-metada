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
    
    def __init__(self, folder_path, claude_api_key=None, options=None):
        """Initialize the updater with folder path and API keys."""
        self.folder_path = os.path.abspath(folder_path)
        # Initialize Claude client without proxy settings
        if claude_api_key:
            self.claude_client = Anthropic(api_key=claude_api_key)
        else:
            self.claude_client = None
        self.options = options or {}
        self.jikan_base_url = "https://api.jikan.moe/v4/anime"
        
        # Rate limiting for Jikan API
        self.jikan_requests = []  # Timestamps of recent requests
        self.jikan_minute_limit = 60  # Max 60 requests per minute
        self.jikan_second_limit = 3   # Max 3 requests per second
        
        self.stats = {
            "processed_files": 0,
            "updated_ratings": 0,
            "updated_genres": 0,
            "translated_plots": 0,
            "episodes_processed": 0,
            "episodes_translated": 0,
            "episode_titles_translated": 0,
            "episode_plots_translated": 0,
            "episodes_updated": 0,  # Added this key to fix the issue
            "errors": 0
        }
        
        # Ensure the folder exists
        if not os.path.isdir(self.folder_path):
            raise ValueError(f"The specified folder does not exist: {self.folder_path}")
            
        logger.info(f"Initializing with folder: {self.folder_path}")
        logger.info(f"Options: {self.options}")
        logger.info(f"Translation {'enabled' if self.claude_client else 'disabled'}")
    
    def run(self):
        """Main method to run the updater."""
        logger.info("Starting anime metadata update process")
        
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
                    self._process_nfo_file(nfo_path)
                except Exception as e:
                    logger.error(f"Error processing {nfo_path}: {str(e)}")
                    self.stats["errors"] += 1
            
            # Check if we need to process episode files
            if self.options.get('translate_episodes', False) or episodes_only:
                # Get all episode NFO files in this folder
                episode_files = [f for f in files if f.endswith('.nfo') and f != 'tvshow.nfo']
                
                if episode_files:
                    logger.info(f"Found {len(episode_files)} episode NFO files in {root}")
                    
                    for episode_file in episode_files:
                        episode_path = os.path.join(root, episode_file)
                        try:
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
        """Update the anime rating and genres using Jikan API."""
        try:
            # Check if we already have a rating
            rating_elem = root.find('rating')
            has_rating = rating_elem is not None and rating_elem.text and float(rating_elem.text) > 0
            
            force_update = self.options.get('force_update', False)
            if has_rating and not force_update:
                logger.info(f"Rating already exists for {title}, checking genres")
            
            # Search for the anime using Jikan API
            params = {'q': title, 'limit': 1}
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
            
            return changes_made
            
        except Exception as e:
            logger.error(f"Error updating metadata for {title}: {str(e)}")
            return False
    
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
            
            # Make the request
            response = requests.get(self.jikan_base_url, params=params)
            
            if response.status_code == 429:
                # Rate limited, wait and retry
                logger.warning("Rate limited by Jikan API, waiting 5 seconds")
                time.sleep(5)
                # Remove the failed request timestamp
                if self.jikan_requests and self.jikan_requests[-1] == current_time:
                    self.jikan_requests.pop()
                return self._make_jikan_request(params)
                
            if response.status_code != 200:
                logger.error(f"Jikan API error: {response.status_code}")
                return None
                
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error: {str(e)}")
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
                french_plot = self._translate_text(the_plot)
                if french_plot:
                    plot_elem.text = french_plot
                    changes_made = True
                    logger.info("Translated plot successfully")
            
            # Translate outline if it exists
            if outline_elem is not None and outline_elem.text:
                the_outline = outline_elem.text.strip()
                french_outline = self._translate_text(the_outline)
                if french_outline:
                    outline_elem.text = french_outline
                    changes_made = True
                    logger.info("Translated outline successfully")
            
            return changes_made
            
        except Exception as e:
            logger.error(f"Error translating descriptions: {str(e)}")
            return False
    
    def _translate_text(self, text):
        """Use Claude API to translate text from English to French."""
        if not text or self.claude_client is None:
            return None
            
        try:
            # Add a short delay to respect API rate limits
            time.sleep(0.5)
            
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
            
            # Translate title if it exists
            title_elem = root.find('title')
            if title_elem is not None and title_elem.text and title_elem.text.strip():
                # Only translate if the title is not already in French
                # This is a simple heuristic - you might want to improve it
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
                logger.info(f"No translation changes needed for episode: {episode_path}")
            
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
            # Make sure we have "episodes_updated" in our stats when using MPAA operations
            logger.info(f"Episode NFO files updated: {self.stats['episodes_updated']}")
        else:
            logger.info(f"TV Show files processed: {self.stats['processed_files']}")
            logger.info(f"Ratings updated: {self.stats['updated_ratings']}")
            logger.info(f"Genres updated: {self.stats['updated_genres']}")
            logger.info(f"TV Show descriptions translated: {self.stats['translated_plots']}")
            
            if self.options.get('translate_episodes', False) or self.options.get('episodes_only', False):
                logger.info(f"Episode files processed: {self.stats['episodes_processed']}")
                logger.info(f"Episode files with translations: {self.stats['episodes_translated']}")
                logger.info(f"Episode titles translated: {self.stats['episode_titles_translated']}")
                logger.info(f"Episode plots translated: {self.stats['episode_plots_translated']}")
            
        logger.info(f"Errors encountered: {self.stats['errors']}")
        logger.info("=" * 50)


def load_environment():
    """Load environment variables from .env file."""
    # Load environment variables
    load_dotenv()
    
    # Get environment variables
    env_folder = os.getenv('ANIME_FOLDER')
    env_claude_api_key = os.getenv('CLAUDE_API_KEY')
    env_claude_model = os.getenv('CLAUDE_MODEL', 'claude-3-5-haiku-latest')  # Default model if not specified
    
    # Parse boolean options from environment
    env_skip_translate = os.getenv('SKIP_TRANSLATE', '').lower() == 'true'
    env_rating_only = os.getenv('RATING_ONLY', '').lower() == 'true'
    env_sync_mpaa = os.getenv('SYNC_MPAA', '').lower() == 'true'
    env_force_update = os.getenv('FORCE_UPDATE', '').lower() == 'true'
    env_remove_mpaa = os.getenv('REMOVE_MPAA', '').lower() == 'true'
    env_translate_episodes = os.getenv('TRANSLATE_EPISODES', '').lower() == 'true'
    env_episodes_only = os.getenv('EPISODES_ONLY', '').lower() == 'true'
    
    return {
        'folder': env_folder,
        'claude_api_key': env_claude_api_key,
        'claude_model': env_claude_model,
        'skip_translate': env_skip_translate,
        'rating_only': env_rating_only,
        'sync_mpaa': env_sync_mpaa,
        'force_update': env_force_update,
        'remove_mpaa': env_remove_mpaa,
        'translate_episodes': env_translate_episodes,
        'episodes_only': env_episodes_only
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
    parser.add_argument("--claude-model", default=env_vars['claude_model'],
                        help="Claude model to use for translation (default: claude-3-haiku-20240307)")
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
    parser.add_argument("--translate-episodes", action="store_true", 
                        help="Translate plot and title in episode NFO files")
    parser.add_argument("--episodes-only", action="store_true",
                        help="Only process episode files, skip tvshow.nfo")
    
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
            "claude_model": args.claude_model
        }
        
        updater = AnimeMetadataUpdater(
            folder_path=args.folder,
            claude_api_key=args.claude_api_key,
            options=options
        )
        
        updater.run()
        
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
