#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Base LLM provider for PRhythm.
This module defines the base class for LLM providers.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

# Setup logger
logger = logging.getLogger("base_provider")

class BaseProvider(ABC):
    """
    Abstract base class for LLM providers.
    All provider implementations should inherit from this class.
    """
    
    def __init__(self, api_key: str, **kwargs):
        """
        Initialize the provider
        
        Args:
            api_key: API key for the provider
            **kwargs: Additional provider-specific parameters
        """
        self.api_key = api_key
        self.is_configured = bool(api_key)
        self.base_url = kwargs.get("base_url")
        self.model = kwargs.get("model")
        self.max_tokens = kwargs.get("max_tokens", 4096)
        self.temperature = kwargs.get("temperature", 0.7)
        
        # Additional configuration parameters
        self.additional_params = kwargs
        
        # Setup provider-specific configuration
        self._setup_provider()
    
    @abstractmethod
    def _setup_provider(self) -> None:
        """
        Setup provider-specific configuration
        This method should be implemented by each provider
        """
        pass
    
    @abstractmethod
    def get_completion(self, prompt: str, **kwargs) -> str:
        """
        Get completion from the provider
        
        Args:
            prompt: Prompt to send to the provider
            **kwargs: Additional parameters
            
        Returns:
            str: Completion text
            
        Raises:
            RuntimeError: If there is an error getting the completion
        """
        pass
    
    @abstractmethod
    def get_chat_completion(self, messages: list, **kwargs) -> str:
        """
        Get chat completion from the provider
        
        Args:
            messages: List of messages
            **kwargs: Additional parameters
            
        Returns:
            str: Chat completion text
            
        Raises:
            RuntimeError: If there is an error getting the chat completion
        """
        pass
    
    def validate_configuration(self) -> bool:
        """
        Validate the provider configuration
        
        Returns:
            bool: True if the provider is properly configured, False otherwise
        """
        if not self.is_configured:
            logger.warning(f"Provider not configured: API key not provided")
            return False
            
        if not self.model:
            logger.warning(f"Provider not configured: model not specified")
            return False
            
        return True
    
    def get_provider_info(self) -> Dict[str, Any]:
        """
        Get information about the provider
        
        Returns:
            dict: Provider information
        """
        return {
            "name": self.__class__.__name__,
            "is_configured": self.is_configured,
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature
        }
    
    def get_model_name(self) -> str:
        """
        Get the provider model name
        
        Returns:
            str: Model name
        """
        return self.model or "unknown"
