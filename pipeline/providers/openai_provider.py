#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
OpenAI provider for PRhythm.
This module implements the OpenAI LLM provider.
"""

import logging
import time
import requests
from typing import Dict, List, Any, Optional

from .base_provider import BaseProvider

# Setup logger
logger = logging.getLogger("openai_provider")

class OpenAIProvider(BaseProvider):
    """
    OpenAI API provider implementation.
    Supports GPT-3.5 and GPT-4 models.
    """
    
    def _setup_provider(self) -> None:
        """
        Setup OpenAI-specific configuration
        """
        # Set default base URL if not provided
        if not self.base_url:
            self.base_url = "https://api.openai.com/v1"
            
        # Set default model if not provided
        if not self.model:
            self.model = "gpt-4"
        
        # Setup API headers
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
    
    def get_completion(self, prompt: str, **kwargs) -> str:
        """
        Get completion from OpenAI API
        
        Args:
            prompt: Prompt to send to OpenAI
            **kwargs: Additional parameters
            
        Returns:
            str: Completion text
            
        Raises:
            RuntimeError: If there is an error getting the completion
        """
        if not self.validate_configuration():
            raise RuntimeError("OpenAI provider not properly configured")
        
        # Override parameters with kwargs if provided
        temperature = kwargs.get("temperature", self.temperature)
        max_tokens = kwargs.get("max_tokens", self.max_tokens)
        
        # Prepare request payload
        payload = {
            "model": self.model,
            "prompt": prompt,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": kwargs.get("top_p", 1.0),
            "frequency_penalty": kwargs.get("frequency_penalty", 0.0),
            "presence_penalty": kwargs.get("presence_penalty", 0.0)
        }
        
        # Add any additional parameters
        for key, value in kwargs.items():
            if key not in payload and key not in ["temperature", "max_tokens"]:
                payload[key] = value
        
        # Make API request with retry
        return self._make_api_request("completions", payload)
    
    def get_chat_completion(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """
        Get chat completion from OpenAI API
        
        Args:
            messages: List of message dictionaries (role, content)
            **kwargs: Additional parameters
            
        Returns:
            str: Chat completion text
            
        Raises:
            RuntimeError: If there is an error getting the chat completion
        """
        if not self.validate_configuration():
            raise RuntimeError("OpenAI provider not properly configured")
        
        # Override parameters with kwargs if provided
        temperature = kwargs.get("temperature", self.temperature)
        max_tokens = kwargs.get("max_tokens", self.max_tokens)
        
        # Prepare request payload
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": kwargs.get("top_p", 1.0),
            "frequency_penalty": kwargs.get("frequency_penalty", 0.0),
            "presence_penalty": kwargs.get("presence_penalty", 0.0)
        }
        
        # Add any additional parameters
        for key, value in kwargs.items():
            if key not in payload and key not in ["temperature", "max_tokens"]:
                payload[key] = value
        
        # Make API request with retry
        return self._make_api_request("chat/completions", payload)
    
    def _make_api_request(self, endpoint: str, payload: Dict[str, Any], 
                          max_retries: int = 3, retry_delay: float = 2.0) -> str:
        """
        Make API request to OpenAI with retry logic
        
        Args:
            endpoint: API endpoint (e.g., completions, chat/completions)
            payload: Request payload
            max_retries: Maximum number of retries (default: 3)
            retry_delay: Initial retry delay in seconds (default: 2.0)
            
        Returns:
            str: API response text
            
        Raises:
            RuntimeError: If the API request fails after retries
        """
        url = f"{self.base_url}/{endpoint}"
        
        for attempt in range(max_retries):
            try:
                logger.debug(f"Making OpenAI API request to {endpoint}")
                response = requests.post(url, headers=self.headers, json=payload, timeout=60)
                response.raise_for_status()
                
                # Parse response
                response_json = response.json()
                
                # Extract completion text based on endpoint
                if endpoint == "chat/completions":
                    return response_json["choices"][0]["message"]["content"]
                else:  # regular completions
                    return response_json["choices"][0]["text"]
                
            except requests.exceptions.RequestException as e:
                # Handle rate limiting
                if hasattr(e.response, 'status_code') and e.response.status_code == 429:
                    retry_after = float(e.response.headers.get("retry-after", retry_delay * (attempt + 1)))
                    logger.warning(f"Rate limited by OpenAI. Retrying after {retry_after} seconds")
                    time.sleep(retry_after)
                # Handle other errors
                elif attempt < max_retries - 1:
                    wait_time = retry_delay * (2 ** attempt)
                    logger.warning(f"OpenAI API request failed: {e}. Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"OpenAI API request failed after {max_retries} attempts: {e}")
                    if hasattr(e, 'response') and hasattr(e.response, 'text'):
                        logger.error(f"Response: {e.response.text}")
                    raise RuntimeError(f"Failed to get completion from OpenAI: {e}")
            
        # This should not be reached due to the raise in the loop
        raise RuntimeError("Unexpected error in OpenAI API request")
