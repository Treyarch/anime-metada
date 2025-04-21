"""
Episode NFO file processor module.
"""

import os
import logging
import xml.etree.ElementTree as ET
from src.utils.file_utils import read_xml_file, write_xml_file
from src.utils.language_utils import appears_to_be_french
import os
import sys

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))


logger = logging.getLogger(__name__)

class EpisodeProcessor:
    """
    Class for processing episode NFO files.
    """
    
    def __init__(self, claude_api, stats, options=None):
        """
        Initialize the episode processor.
        
        Args:
            claude_api: ClaudeAPI instance
            stats: Statistics object
            options: Options dictionary
        """
        self.claude_api = claude_api
        self.stats = stats
        self.options = options or {}
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
    
    def process_episode_nfo(self, episode_path):
        """
        Process an episode NFO file to translate title and plot.
        
        Args:
            episode_path: Path to the episode NFO file
            
        Returns:
            True if changes were made, False otherwise
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
                return False
            
            self.stats.increment("episodes_processed")
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
            should_translate = not self.options.get('skip_translate', False) and not self.options.get('rating_only', False) and self.claude_api is not None
            
            if should_translate:
                title_elem = root.find('title')
                if title_elem is not None and title_elem.text and title_elem.text.strip():
                    # Only translate if the title is not already in French
                    if not appears_to_be_french(title_elem.text):
                        logger.info(f"Translating episode title...")
                        translated_title = self.claude_api.translate_text(title_elem.text.strip())
                        if translated_title and translated_title != title_elem.text:
                            title_elem.text = translated_title
                            changes_made = True
                            self.stats.increment("episode_titles_translated")
                            logger.info(f"Translated title: {translated_title}")
                
                # Translate plot if it exists
                plot_elem = root.find('plot')
                if plot_elem is not None and plot_elem.text and plot_elem.text.strip():
                    # Only translate if the plot is not already in French
                    if not appears_to_be_french(plot_elem.text):
                        logger.info(f"Translating episode plot...")
                        translated_plot = self.claude_api.translate_text(plot_elem.text.strip())
                        if translated_plot and translated_plot != plot_elem.text:
                            plot_elem.text = translated_plot
                            changes_made = True
                            self.stats.increment("episode_plots_translated")
                            logger.info(f"Translated plot successfully")
            
            # Write changes if any were made
            if changes_made:
                self.stats.increment("episodes_translated")
                
                # Convert tree to string without the XML declaration (we'll add the exact one we want later)
                xml_string = ET.tostring(root, encoding='utf-8', xml_declaration=False).decode('utf-8')
                
                # Write the file preserving encoding
                write_xml_file(episode_path, xml_string, has_bom)
                
                logger.info(f"Updated episode file: {episode_path}")
            else:
                logger.info(f"No changes needed for episode: {episode_path}")
            
            return changes_made
            
        except Exception as e:
            logger.error(f"Error processing episode NFO {episode_path}: {str(e)}")
            self.stats.increment("errors")
            return False
    
    def _get_mpaa_from_tvshow(self, tvshow_path):
        """
        Extract MPAA rating from tvshow.nfo file.
        
        Args:
            tvshow_path: Path to the tvshow.nfo file
            
        Returns:
            MPAA rating if found, None otherwise
        """
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
