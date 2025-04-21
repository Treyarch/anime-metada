"""
Claude API integration for anime metadata updater.
"""

import time
import logging
import os
import sys

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))


logger = logging.getLogger(__name__)

class ClaudeAPI:
    """
    Class for handling Claude API requests with rate limiting.
    """
    
    def __init__(self, claude_client, stats, options=None):
        """
        Initialize the Claude API handler.
        
        Args:
            claude_client: Initialized Anthropic client
            stats: Statistics object for tracking API calls
            options: Options dictionary
        """
        self.claude_client = claude_client
        self.stats = stats
        self.options = options or {}
        
        # Rate limiting for Claude API
        self.claude_requests = []  # Timestamps of Claude API requests
        self.claude_minute_limit = 50  # Conservative limit for Claude API
        self.claude_second_limit = 2   # Conservative limit for Claude API
        self.batch_delay = self.options.get('batch_delay', 1.0)  # Default 1 second between batch operations
    
    def _apply_rate_limits(self):
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
    
    def translate_text(self, text):
        """
        Use Claude API to translate text from English to French.
        
        Args:
            text: Text to translate
            
        Returns:
            Translated text or None on error
        """
        if not text or self.claude_client is None:
            return None
            
        try:
            # Apply rate limiting
            self._apply_rate_limits()
            
            # Add current request timestamp to the list
            current_time = time.time()
            self.claude_requests.append(current_time)
            self.stats.increment("claude_api_calls")
            
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
