"""
MPAA rating processor module.
"""

import os
import time
import logging
import xml.etree.ElementTree as ET
from src.utils.file_utils import read_xml_file, write_xml_file
from src.utils.folder_utils import get_anime_folders, get_folder_subset, get_episode_files
import os
import sys

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))


logger = logging.getLogger(__name__)

class MPAAProcessor:
    """
    Class for processing MPAA ratings in episode NFO files.
    """
    
    def __init__(self, stats, options=None):
        """
        Initialize the MPAA processor.
        
        Args:
            stats: Statistics object
            options: Options dictionary
        """
        self.stats = stats
        self.options = options or {}
        self.batch_delay = self.options.get('batch_delay', 1.0)
    
    def process_mpaa_tags(self, folder_path):
        """
        Process MPAA tags in episode NFO files based on tvshow.nfo.
        
        Args:
            folder_path: Base folder path
        """
        logger.info("Starting MPAA tag processing with folder limit")
        
        # Get anime folders if we have a limit or offset
        if self.options.get('max_folders', 0) > 0 or self.options.get('folder_offset', 0) > 0:
            all_folders = get_anime_folders(folder_path)
            total_folders = len(all_folders)
            logger.info(f"Found {total_folders} total anime folders")
            
            # Get the subset of folders to process
            folders_to_process, skipped_offset, skipped_limit = get_folder_subset(
                all_folders, 
                self.options.get('folder_offset', 0),
                self.options.get('max_folders', 0)
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
                self._process_mpaa_for_folder(folder)
                self.stats.increment("folders_processed")
        else:
            # No limit, process all folders
            for root, dirs, files in os.walk(folder_path):
                if 'tvshow.nfo' in files:
                    self.stats.increment("folders_processed")
                    self._process_mpaa_for_folder(root)
    
    def _process_mpaa_for_folder(self, folder_path):
        """
        Process MPAA tags for a single folder.
        
        Args:
            folder_path: Folder path to process
        """
        logger.info(f"Processing MPAA tags for folder: {folder_path}")
        
        # Check if there's a tvshow.nfo file
        tvshow_path = os.path.join(folder_path, 'tvshow.nfo')
        if not os.path.exists(tvshow_path):
            logger.warning(f"No tvshow.nfo found in {folder_path}, skipping")
            return
        
        if self.options.get('sync_mpaa', False):
            # Get the MPAA rating from tvshow.nfo
            mpaa_value = self._get_mpaa_from_tvshow(tvshow_path)
            if not mpaa_value:
                logger.warning(f"No MPAA tag found in {tvshow_path}, skipping folder")
                return
            
            logger.info(f"Found MPAA rating '{mpaa_value}' in {tvshow_path}")
        
        # Find all episode NFO files in this folder
        episode_nfos = get_episode_files(folder_path)
        
        if not episode_nfos:
            logger.info(f"No episode NFO files found in {folder_path}")
            return
        
        logger.info(f"Found {len(episode_nfos)} episode NFO files in {folder_path}")
        
        # Process each episode NFO file
        for episode_file in episode_nfos:
            episode_path = os.path.join(folder_path, episode_file)
            try:
                # Track batch operations
                if self.options.get('batch_mode', False):
                    self.stats.increment("batch_operations")
                    # Apply batch delay if configured
                    if self.batch_delay > 0:
                        time.sleep(self.batch_delay)
                
                if self.options.get('sync_mpaa', False):
                    self._add_mpaa_to_episode(episode_path, mpaa_value)
                elif self.options.get('remove_mpaa', False):
                    self._remove_mpaa_from_episode(episode_path)
            except Exception as e:
                logger.error(f"Error processing episode {episode_path}: {str(e)}")
                self.stats.increment("errors")
    
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
    
    def _add_mpaa_to_episode(self, episode_path, mpaa_value):
        """
        Add or update MPAA tag in episode NFO file.
        
        Args:
            episode_path: Path to the episode NFO file
            mpaa_value: MPAA rating value to set
            
        Returns:
            True if changes were made, False otherwise
        """
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
                self.stats.increment("episodes_updated")
                return True
            else:
                logger.info(f"MPAA already set to '{mpaa_value}' in {episode_path}")
                return False
                
        except Exception as e:
            logger.error(f"Error adding MPAA to {episode_path}: {str(e)}")
            self.stats.increment("errors")
            return False
    
    def _remove_mpaa_from_episode(self, episode_path):
        """
        Remove MPAA tag from episode NFO file if it exists.
        
        Args:
            episode_path: Path to the episode NFO file
            
        Returns:
            True if changes were made, False otherwise
        """
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
            
            # Find and remove MPAA tag if it exists
            mpaa_elem = root.find('mpaa')
            if mpaa_elem is not None:
                root.remove(mpaa_elem)
                
                # Convert tree to string without the XML declaration (we'll add the exact one we want later)
                xml_string = ET.tostring(root, encoding='utf-8', xml_declaration=False).decode('utf-8')
                
                # Write the file preserving encoding
                write_xml_file(episode_path, xml_string, has_bom)
                
                logger.info(f"Removed MPAA rating from {episode_path}")
                self.stats.increment("episodes_updated")
                return True
            else:
                logger.info(f"No MPAA tag found in {episode_path}")
                return False
                
        except Exception as e:
            logger.error(f"Error removing MPAA from {episode_path}: {str(e)}")
            self.stats.increment("errors")
            return False
