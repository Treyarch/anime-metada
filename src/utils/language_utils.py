"""
Language detection and text processing utility functions.
"""

import logging
import os
import sys

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))


logger = logging.getLogger(__name__)

def appears_to_be_french(text):
    """
    Simple heuristic to check if text appears to be in French already.
    This is not foolproof but helps avoid unnecessary translations.
    
    Args:
        text: Text to check
        
    Returns:
        True if the text appears to be in French
    """
    if not text:
        return False
        
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

def clean_title_for_api(title):
    """
    Clean anime title for API query - handle special characters.
    
    Args:
        title: Original title
    
    Returns:
        Cleaned title suitable for API queries
    """
    return title.replace(':', ' ').replace('×', 'x').strip()
