#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Configuration manager for PRhythm.
This module provides a centralized way to handle configuration across the project.
"""

import json
import os
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# Setup logger
logger = logging.getLogger("config_manager")

class ConfigManager:
    """
    Configuration manager for the PRhythm project.
    Provides a central location for accessing configuration settings.
    """
    
    def __init__(self, config_path: Union[str, Path] = "config.json"):
        """
        Initialize the configuration manager
        
        Args:
            config_path: Path to the configuration file (default: config.json in project root)
        """
        self.config_path = self._resolve_config_path(config_path)
        self.config = self._load_config()
        
        # Cache common config sections
        self._github_config = self.config.get("github", {})
        self._llm_config = self.config.get("llm", {})
        self._output_config = self.config.get("output", {})
        self._paths_config = self.config.get("paths", {})
        
    def _resolve_config_path(self, config_path: Union[str, Path]) -> Path:
        """
        Resolve the configuration file path
        
        Args:
            config_path: Path to the configuration file
            
        Returns:
            Path: Resolved path to the configuration file
        """
        path = Path(config_path)
        if not path.is_absolute():
            # Get project root directory
            script_dir = Path(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            path = script_dir / path
        return path
    
    def _load_config(self) -> Dict[str, Any]:
        """
        Load configuration from file
        
        Returns:
            dict: Configuration data
            
        Raises:
            RuntimeError: If the configuration file cannot be read
        """
        try:
            if not self.config_path.exists():
                logger.warning(f"Configuration file not found: {self.config_path}")
                return {}
                
            with open(self.config_path, 'r') as file:
                config = json.load(file)
                return config
        except Exception as e:
            logger.error(f"Error reading configuration file: {e}")
            return {}
    
    def get_github_token(self) -> str:
        """
        Get GitHub API token from config or environment variable
        
        Returns:
            str: GitHub API token
        """
        # Try environment variable first
        env_token = os.environ.get("GITHUB_TOKEN")
        if env_token:
            return env_token
            
        # Fall back to config file
        return self._github_config.get("token", "")
    
    def get_repositories(self) -> List[str]:
        """
        Get list of tracked repositories
        
        Returns:
            list: List of repository names in owner/repo format
        """
        return self._github_config.get("repositories", [])
    
    def get_check_interval(self) -> int:
        """
        Get repository check interval in seconds
        
        Returns:
            int: Check interval in seconds (default: 3600)
        """
        return self._github_config.get("check_interval", 3600)
    
    def get_llm_provider(self) -> str:
        """
        Get the configured LLM provider
        
        Returns:
            str: Provider name (default: "openai")
        """
        return self._llm_config.get("provider", "openai")
    
    def get_llm_temperature(self) -> float:
        """
        Get LLM temperature setting
        
        Returns:
            float: Temperature value (default: 0.7)
        """
        return self._llm_config.get("temperature", 0.7)
    
    def get_provider_config(self, provider: Optional[str] = None) -> Dict[str, Any]:
        """
        Get configuration for a specific LLM provider
        
        Args:
            provider: Provider name (default: use configured provider)
            
        Returns:
            dict: Provider-specific configuration
        """
        if provider is None:
            provider = self.get_llm_provider()
            
        providers_config = self._llm_config.get("providers", {})
        return providers_config.get(provider, {})
    
    def get_provider_api_key(self, provider: Optional[str] = None) -> str:
        """
        Get API key for a specific LLM provider from config or environment variable
        
        Args:
            provider: Provider name (default: use configured provider)
            
        Returns:
            str: API key
        """
        if provider is None:
            provider = self.get_llm_provider()
            
        # Try environment variable first (e.g., OPENAI_API_KEY, DEEPSEEK_API_KEY)
        env_var_name = f"{provider.upper()}_API_KEY"
        env_api_key = os.environ.get(env_var_name)
        if env_api_key:
            return env_api_key
            
        # Fall back to config file
        provider_config = self.get_provider_config(provider)
        return provider_config.get("api_key", "")
    
    def get_output_languages(self) -> List[str]:
        """
        Get configured output languages
        
        Returns:
            list: List of language codes (default: ["en"])
        """
        languages = self._output_config.get("languages", ["en"])
        if not languages:
            return ["en"]
        return languages
    
    def get_path(self, path_key: str, default_path: str) -> Path:
        """
        Get a path from configuration, resolving relative paths
        
        Args:
            path_key: Key in the paths section
            default_path: Default path if not found in config
            
        Returns:
            Path: Resolved path
        """
        path_str = self._paths_config.get(path_key, default_path)
        path = Path(path_str)
        
        if not path.is_absolute():
            # Convert to absolute path relative to project root
            script_dir = Path(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            path = script_dir / path_str
            
        return path
    
    def get_repos_dir(self) -> Path:
        """
        Get repositories directory path
        
        Returns:
            Path: Repositories directory path
        """
        return self.get_path("repos_dir", "./repos")
    
    def get_output_dir(self) -> Path:
        """
        Get output directory path
        
        Returns:
            Path: Output directory path
        """
        return self.get_path("output_dir", "./output")
    
    def get_analysis_dir(self) -> Path:
        """
        Get analysis directory path
        
        Returns:
            Path: Analysis directory path
        """
        return self.get_path("analysis_dir", "./analysis")
    
    def get_full_config(self) -> Dict[str, Any]:
        """
        Get the full configuration
        
        Returns:
            dict: Complete configuration
        """
        return self.config

# Create a singleton instance
config_manager = ConfigManager()
