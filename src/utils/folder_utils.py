"""
Folder-related utility functions for anime metadata updater.
"""

import os
import logging
import os
import sys

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))


logger = logging.getLogger(__name__)

def get_anime_folders(base_folder):
    """
    Get a list of all anime folders (folders containing tvshow.nfo).
    
    Args:
        base_folder: Root folder to search from
    
    Returns:
        A list of folder paths sorted alphabetically
    """
    anime_folders = []
    
    for root, dirs, files in os.walk(base_folder):
        if 'tvshow.nfo' in files:
            anime_folders.append(root)
    
    # Sort folders alphabetically for consistent processing order
    anime_folders.sort()
    return anime_folders

def get_folder_subset(folders, offset=0, max_folders=0):
    """
    Get a subset of folders based on offset and max_folders.
    
    Args:
        folders: List of all folders
        offset: Number of folders to skip from the beginning
        max_folders: Maximum number of folders to return (0 for all)
    
    Returns:
        A tuple containing (selected folders, skipped offset count, skipped limit count)
    """
    total_folders = len(folders)
    
    # Apply offset
    start_index = min(offset, total_folders)
    skipped_offset = start_index
    
    # Apply limit if specified
    if max_folders > 0:
        end_index = min(start_index + max_folders, total_folders)
        skipped_limit = total_folders - end_index
    else:
        end_index = total_folders
        skipped_limit = 0
    
    # Get the slice of folders to process
    return folders[start_index:end_index], skipped_offset, skipped_limit

def get_episode_files(folder_path):
    """
    Get all episode NFO files in a folder (excluding tvshow.nfo).
    
    Args:
        folder_path: Path to the folder
    
    Returns:
        List of episode NFO file paths
    """
    files = [f for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f))]
    episode_files = [f for f in files if f.endswith('.nfo') and f != 'tvshow.nfo']
    return episode_files
