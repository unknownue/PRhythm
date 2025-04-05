#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
GitHub client for PRhythm.
This module provides functions for interacting with GitHub API and CLI.
"""

import json
import logging
import subprocess
import requests
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Tuple

from utils.file_utils import ensure_directory

# Setup logger
logger = logging.getLogger("github_client")

class GitHubClient:
    """
    Client for interacting with GitHub API and CLI.
    This class provides methods for fetching PR information, diffs, and more.
    """
    
    def __init__(self, token: Optional[str] = None):
        """
        Initialize GitHub client
        
        Args:
            token: GitHub API token (optional)
        """
        self.token = token
        self.api_base_url = "https://api.github.com"
        self.headers = {}
        
        if token:
            self.headers["Authorization"] = f"token {token}"
    
    def validate_repo_url(self, repo_url: str) -> str:
        """
        Validate and normalize repository URL to owner/repo format
        
        Args:
            repo_url: Repository URL or owner/repo string
            
        Returns:
            str: Repository in owner/repo format
            
        Raises:
            ValueError: If the repository URL is invalid
        """
        if re.match(r'^[^/]+/[^/]+$', repo_url):
            return repo_url
        
        match = re.search(r'github\.com[:/]([^/]+/[^/]+?)(?:\.git)?/?$', repo_url)
        if match:
            return match.group(1)
        
        raise ValueError(f"Invalid repository format: {repo_url}. Expected format: owner/repo or GitHub URL")
    
    def run_gh_command(self, command: str, timeout: int = 60) -> Tuple[int, str, str]:
        """
        Run a GitHub CLI command
        
        Args:
            command: Command to run
            timeout: Timeout in seconds
            
        Returns:
            tuple: (return_code, stdout, stderr)
            
        Raises:
            subprocess.TimeoutExpired: If the command times out
            subprocess.CalledProcessError: If the command fails
        """
        try:
            # Execute command
            process = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8'
            )
            
            # Wait for process to complete with timeout
            stdout, stderr = process.communicate(timeout=timeout)
            return process.returncode, stdout, stderr
            
        except subprocess.TimeoutExpired:
            process.kill()
            raise
    
    def fetch_pr_info(self, repo: str, pr_number: Union[int, str]) -> Dict[str, Any]:
        """
        Fetch PR information using GitHub CLI
        
        Args:
            repo: Repository name (owner/repo)
            pr_number: PR number
            
        Returns:
            dict: PR information
            
        Raises:
            RuntimeError: If there is an error fetching the PR information
        """
        try:
            # Validate repository format
            repo = self.validate_repo_url(repo)
            
            # Fetch basic PR info - removed commits and comments from the JSON fields
            logger.info(f"Fetching PR information for {repo}#{pr_number}")
            
            cmd = f"gh pr view {pr_number} --repo {repo} --json number,title,url,state,author,createdAt,mergedAt,mergedBy,body,files,reviews,labels"
            returncode, stdout, stderr = self.run_gh_command(cmd)
            
            if returncode != 0:
                raise RuntimeError(f"Error fetching PR information: {stderr}")
            
            pr_data = json.loads(stdout)
            
            # Remove content from reviews fields, set to empty list
            if 'reviews' in pr_data:
                pr_data['reviews'] = []
            
            # Add metadata
            pr_data["repository"] = repo
            
            return pr_data
        except Exception as e:
            logger.error(f"Error fetching PR information: {e}")
            raise RuntimeError(f"Failed to fetch PR information: {e}")
    
    def fetch_pr_diff(self, repo: str, pr_number: Union[int, str]) -> str:
        """
        Fetch PR diff using GitHub CLI
        
        Args:
            repo: Repository name (owner/repo)
            pr_number: PR number
            
        Returns:
            str: PR diff
            
        Raises:
            RuntimeError: If there is an error fetching the PR diff
        """
        try:
            # Validate repository format
            repo = self.validate_repo_url(repo)
            
            # Fetch PR diff
            logger.info(f"Fetching PR diff for {repo}#{pr_number}")
            
            cmd = f"gh pr diff {pr_number} --repo {repo}"
            returncode, stdout, stderr = self.run_gh_command(cmd)
            
            if returncode != 0:
                raise RuntimeError(f"Error fetching PR diff: {stderr}")
            
            return stdout
        except Exception as e:
            logger.error(f"Error fetching PR diff: {e}")
            raise RuntimeError(f"Failed to fetch PR diff: {e}")
    
    def get_merged_prs(self, repo: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get a list of merged PRs for a repository using GitHub API
        
        Args:
            repo: Repository name (owner/repo)
            limit: Maximum number of PRs to fetch
            
        Returns:
            list: List of merged PR information
        """
        try:
            # Validate repository format
            repo = self.validate_repo_url(repo)
            
            # Fetch merged PRs
            logger.info(f"Fetching merged PRs for {repo} (limit: {limit})")
            
            url = f"{self.api_base_url}/repos/{repo}/pulls?state=closed&sort=updated&direction=desc&per_page={limit}"
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            
            # Filter to only merged PRs
            merged_prs = [pr for pr in response.json() if pr.get("merged_at")]
            
            if not merged_prs:
                logger.info(f"No merged PRs found for {repo}")
                return []
            
            return merged_prs
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching merged PRs for {repo}: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error fetching merged PRs for {repo}: {e}")
            return []
    
    def clone_repository(self, repo: str, target_dir: Union[str, Path], skip_clone: bool = False) -> bool:
        """
        Clone or pull a repository
        
        Args:
            repo: Repository name (owner/repo)
            target_dir: Directory to clone the repository into
            skip_clone: If True, skip the actual clone/pull operation
            
        Returns:
            bool: True if successful, False otherwise
        """
        if skip_clone:
            logger.info(f"Skipping clone/pull for repository: {repo}")
            return True
            
        try:
            # Validate repository format
            repo = self.validate_repo_url(repo)
            
            # Ensure target directory exists
            target_dir = Path(target_dir)
            ensure_directory(target_dir.parent)
            
            if target_dir.exists() and (target_dir / ".git").exists():
                # Repository already exists, pull latest changes
                logger.info(f"Updating existing repository: {repo}")
                cmd = f"cd {target_dir} && git pull"
            else:
                # Clone the repository
                logger.info(f"Cloning repository: {repo}")
                cmd = f"git clone https://github.com/{repo}.git {target_dir}"
            
            # Run command
            returncode, stdout, stderr = self.run_gh_command(cmd, timeout=300)
            
            if returncode != 0:
                logger.error(f"Error with repository {repo}: {stderr}")
                return False
            
            return True
        except subprocess.TimeoutExpired:
            logger.error(f"Timeout error with repository {repo}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error with repository {repo}: {e}")
            return False
