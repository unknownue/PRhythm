import json
import os
from pathlib import Path
from typing import Dict, Optional

class ConfigManager:
    """Configuration manager for PRhythm system"""
    
    def __init__(self, config_dir: str = "config"):
        self.config_dir = Path(config_dir)
        if not self.config_dir.exists():
            raise FileNotFoundError(f"Configuration directory not found: {config_dir}")
    
    def load_global_config(self) -> Optional[Dict]:
        """Load global configuration"""
        config_path = self.config_dir / "global.json"
        if not config_path.exists():
            return None
        
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def load_repository_config(self, repo_name: str) -> Optional[Dict]:
        """Load repository configuration"""
        config_path = self.config_dir / "repositories" / f"{repo_name}.json"
        if not config_path.exists():
            return None
        
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def get_repo_info(self, repo_name: str) -> tuple:
        """Get owner and repo name from configuration"""
        config = self.load_repository_config(repo_name)
        if not config:
            raise ValueError(f"Repository configuration not found: {repo_name}")
        
        full_name = config['repository']['full_name']
        if '/' not in full_name:
            raise ValueError(f"Invalid repository full_name format: {full_name}")
        
        owner, repo = full_name.split('/', 1)
        return owner, repo
    
    def get_repo_config_value(self, repo_name: str, key_path: str, default=None):
        """Get a specific configuration value using dot notation"""
        config = self.load_repository_config(repo_name)
        if not config:
            return default
        
        # Navigate through nested keys (e.g., "repository.default_branch")
        current = config
        for key in key_path.split('.'):
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default
        
        return current
    
    def list_repositories(self) -> list:
        """List all configured repositories"""
        repos_dir = self.config_dir / "repositories"
        if not repos_dir.exists():
            return []
        
        repos = []
        for config_file in repos_dir.glob("*.json"):
            if config_file.name.startswith('_'):  # Skip template files
                continue
            repo_name = config_file.stem
            repos.append(repo_name)
        
        return repos
    
    def is_repository_enabled(self, repo_name: str) -> bool:
        """Check if repository is enabled for analysis"""
        return self.get_repo_config_value(repo_name, "repository.enabled", False)