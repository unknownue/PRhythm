#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Provider factory for PRhythm.
This module provides a factory for creating LLM provider instances.
"""

import logging
from typing import Dict, Any, Optional, Type

from .base_provider import BaseProvider
from .openai_provider import OpenAIProvider
from .deepseek_provider import DeepSeekProvider

# Setup logger
logger = logging.getLogger("provider_factory")

# Provider registry
PROVIDER_REGISTRY = {
    "openai": OpenAIProvider,
    "deepseek": DeepSeekProvider
}

def get_provider(provider_name: str, api_key: str, **kwargs) -> BaseProvider:
    """
    Get a provider instance
    
    Args:
        provider_name: Provider name (e.g., "openai", "deepseek")
        api_key: API key for the provider
        **kwargs: Additional provider-specific parameters
        
    Returns:
        BaseProvider: Provider instance
        
    Raises:
        ValueError: If the provider is not supported
    """
    # Normalize provider name
    provider_name = provider_name.lower().strip()
    
    # Check if provider is supported
    if provider_name not in PROVIDER_REGISTRY:
        supported_providers = ", ".join(PROVIDER_REGISTRY.keys())
        raise ValueError(f"Unsupported provider: {provider_name}. Supported providers: {supported_providers}")
    
    # Get provider class
    provider_class = PROVIDER_REGISTRY[provider_name]
    
    # Create and return provider instance
    logger.debug(f"Creating provider instance for {provider_name}")
    return provider_class(api_key, **kwargs)

def register_provider(provider_name: str, provider_class: Type[BaseProvider]) -> None:
    """
    Register a new provider
    
    Args:
        provider_name: Provider name
        provider_class: Provider class
        
    Raises:
        ValueError: If the provider name is already registered
    """
    # Normalize provider name
    provider_name = provider_name.lower().strip()
    
    # Check if provider is already registered
    if provider_name in PROVIDER_REGISTRY:
        raise ValueError(f"Provider already registered: {provider_name}")
    
    # Register provider
    PROVIDER_REGISTRY[provider_name] = provider_class
    logger.debug(f"Registered provider: {provider_name}")

def get_provider_from_config(config: Dict[str, Any]) -> BaseProvider:
    """
    Get a provider instance from configuration
    
    Args:
        config: Configuration dictionary
        
    Returns:
        BaseProvider: Provider instance
        
    Raises:
        ValueError: If the provider is not supported
        RuntimeError: If the provider configuration is invalid
    """
    if not config or "llm" not in config:
        raise RuntimeError("LLM configuration not found")
    
    llm_config = config["llm"]
    
    # Get provider name from config
    provider_name = llm_config.get("provider", "openai")
    
    # Get provider-specific configuration
    providers_config = llm_config.get("providers", {})
    provider_config = providers_config.get(provider_name, {})
    
    # Get API key
    api_key = provider_config.get("api_key", "")
    
    # Check for environment variables in system
    if not api_key:
        import os
        env_var_name = f"{provider_name.upper()}_API_KEY"
        api_key = os.environ.get(env_var_name, "")
    
    # Create provider parameters
    params = {
        "base_url": provider_config.get("base_url"),
        "model": provider_config.get("model"),
        "temperature": llm_config.get("temperature", 0.7),
        "max_tokens": provider_config.get("max_tokens", 4096)
    }
    
    # Add any additional parameters from provider config
    for key, value in provider_config.items():
        if key not in ["api_key", "base_url", "model", "max_tokens"]:
            params[key] = value
    
    # Create and return provider instance
    return get_provider(provider_name, api_key, **params)
