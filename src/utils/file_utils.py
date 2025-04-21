"""
File utility functions for anime metadata updater.
"""

import codecs
import xml.etree.ElementTree as ET
import logging
import os
import sys

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))


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

def parse_xml_content(xml_content):
    """
    Parse XML content while preserving formatting.
    
    Args:
        xml_content: String containing XML content
    
    Returns:
        ElementTree root object
    """
    parser = ET.XMLParser(encoding='utf-8')
    return ET.fromstring(xml_content.encode('utf-8'), parser=parser)
