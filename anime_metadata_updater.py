#!/usr/bin/env python3
"""
Anime Metadata Updater - Entry Point

This script serves as the main entry point for the Anime Metadata Updater tool.
It makes running the tool simpler by allowing users to execute it from the project root.
"""

import sys
import os

# Add the project root to the Python path to allow imports from 'src'
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Import and run the main function from the actual implementation
from src.main import main

if __name__ == "__main__":
    main()
