"""
TVShow NFO file processor module.
"""

import re
import os
import sys
import logging
import xml.etree.ElementTree as ET

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.utils.file_utils import read_xml_file, write_xml_file
from src.utils.language_utils import appears_to_be_french

logger = logging.getLogger(__name__)

class NFOProcessor:
    """
    Class for processing tvshow.nfo files.
    """
    
    def __init__(self, jikan_api, claude_api, youtube_api, stats, options=None):
        """
        Initialize the NFO processor.
        
        Args:
            jikan_api: JikanAPI instance
            claude_api: ClaudeAPI instance
            youtube_api: YouTubeAPI instance
            stats: Statistics object
            options: Options dictionary
        """
        self.jikan_api = jikan_api
        self.claude_api = claude_api
        self.youtube_api = youtube_api
        self.stats = stats
        self.options = options or {}
    
    def process_nfo_file(self, nfo_path):
        """
        Process a single tvshow.nfo file.
        
        Args:
            nfo_path: Path to the NFO file
            
        Returns:
            True if changes were made, False otherwise
        """
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
                return False
                
            title = title_elem.text.strip()
            logger.info(f"Found anime: {title}")
            
            # Update changes flag
            changes_made = False
            
            # Update rating and genres if needed
            if not self.options.get('translate_only', False):
                metadata_updated = self._update_metadata(root, title)
                if metadata_updated:
                    changes_made = True
                    # Increment genre update stats
                    self.stats.increment("updated_genres")
                    # We're also likely updating ratings in the same call
                    if root.find('rating') is not None:
                        self.stats.increment("updated_ratings")
            
            # Translate plot and outline if needed
            should_translate = (not self.options.get('rating_only', False) and 
                               not self.options.get('skip_translate', False) and 
                               self.claude_api is not None)
            
            if should_translate:
                translations_updated = self._translate_descriptions(root)
                if translations_updated:
                    changes_made = True
                    self.stats.increment("translated_plots")
            
            # Write back changes if any were made
            if changes_made:
                # Convert tree to string manually
                xml_string = ET.tostring(root, encoding='utf-8', xml_declaration=False).decode('utf-8')
                
                # Write the file preserving encoding
                write_xml_file(nfo_path, xml_string, has_bom)
                
                logger.info(f"Updated file: {nfo_path}")
            else:
                logger.info(f"No changes needed for: {nfo_path}")
            
            self.stats.increment("processed_files")
            return changes_made
            
        except ET.ParseError:
            logger.error(f"Failed to parse XML file: {nfo_path}")
            self.stats.increment("errors")
            return False
    
    def _update_metadata(self, root, title):
        """
        Update the anime rating, genres, tags, and trailer using Jikan API.
        
        Args:
            root: XML root element
            title: Anime title
            
        Returns:
            True if changes were made, False otherwise
        """
        try:
            # Check if we already have a rating
            rating_elem = root.find('rating')
            has_rating = rating_elem is not None and rating_elem.text and float(rating_elem.text) > 0
            
            force_update = self.options.get('force_update', False)
            if has_rating and not force_update:
                logger.info(f"Rating already exists for {title}, checking genres and themes")
            
            # Search for the anime using Jikan API
            response = self.jikan_api.search_anime(title)
            
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
                    self.stats.increment("updated_tags")
                    changes_made = True
                else:
                    logger.info(f"Tags already up to date for {title}")
            else:
                logger.info(f"No theme data available for anime: {title}")
            
            # Get trailer information from API
            trailer_data = anime_data.get('trailer', {})
            youtube_id = None
            trailer_source = "Jikan API"
            
            # Try to extract Youtube ID from Jikan API trailer data
            if self.youtube_api:
                youtube_id = self.youtube_api.extract_youtube_id(trailer_data)
            
                # If no trailer found in API, try YouTube search as fallback
                if not youtube_id:
                    logger.info(f"No trailer found in Jikan API for {title}, searching YouTube...")
                    youtube_id = self.youtube_api.search_trailer(title)
                    trailer_source = "YouTube search"
            
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
                    self.stats.increment("updated_trailers")
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
    
    def _translate_descriptions(self, root):
        """
        Translate plot and outline to French using Claude API.
        
        Args:
            root: XML root element
            
        Returns:
            True if changes were made, False otherwise
        """
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
                if not appears_to_be_french(the_plot):
                    french_plot = self.claude_api.translate_text(the_plot)
                    if french_plot:
                        plot_elem.text = french_plot
                        changes_made = True
                        logger.info("Translated plot successfully")
                else:
                    logger.info("Plot already appears to be in French, skipping translation")
            
            # Translate outline if it exists
            if outline_elem is not None and outline_elem.text:
                the_outline = outline_elem.text.strip()
                if not appears_to_be_french(the_outline):
                    french_outline = self.claude_api.translate_text(the_outline)
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
