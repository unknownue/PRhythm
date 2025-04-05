#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
PR fetcher for PRhythm.
This module handles fetching and processing PR information.
"""

import json
import sys
import os
import logging
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, Union

from github_client import GitHubClient
from utils.config_manager import config_manager
from utils.file_utils import ensure_directory, save_json, generate_output_path

# Setup logger
logger = logging.getLogger("pr_fetcher")

class PRFetcher:
    """
    Fetches and processes PR information.
    This class handles all PR data fetching and preprocessing.
    """
    
    def __init__(self, github_token: Optional[str] = None):
        """
        Initialize PR fetcher
        
        Args:
            github_token: GitHub API token (optional)
        """
        self.github_client = GitHubClient(github_token)
    
    def fetch_pr_info(self, repo: str, pr_number: Union[int, str], output_dir: Optional[Path] = None) -> Dict[str, Any]:
        """
        Fetch PR information and save it to file
        
        Args:
            repo: Repository name (owner/repo)
            pr_number: PR number
            output_dir: Output directory (optional)
            
        Returns:
            dict: PR information
        """
        logger.info(f"Fetching PR information for {repo}#{pr_number}")
        
        try:
            # Fetch basic PR info
            pr_data = self.github_client.fetch_pr_info(repo, pr_number)
            
            # Fetch PR diff
            pr_data["diff"] = self.github_client.fetch_pr_diff(repo, pr_number)
            
            # Add metadata
            pr_data["fetched_at"] = datetime.now().isoformat()
            pr_data["repository"] = repo
            
            # Pre-sort files by the sum of additions and deletions
            if "files" in pr_data:
                files = pr_data["files"]
                for file in files:
                    # Calculate total changes if not already present
                    if "changes" not in file:
                        file["changes"] = file.get("additions", 0) + file.get("deletions", 0)
                
                # Sort files by total changes
                pr_data["files"] = sorted(
                    files,
                    key=lambda x: x.get("changes", 0),
                    reverse=True
                )
            
            # Analyze key commits
            pr_data["commit_analysis"] = self._analyze_key_commits(pr_data)
            
            # Save to file if output directory is provided
            if output_dir:
                return self.save_pr_info(pr_data, output_dir)
            
            return pr_data
            
        except Exception as e:
            logger.error(f"Error fetching PR information: {e}")
            raise
    
    def save_pr_info(self, pr_data: Dict[str, Any], output_dir: Optional[Path] = None) -> Dict[str, Any]:
        """
        Save PR information to a JSON file
        
        Args:
            pr_data: PR information
            output_dir: Output directory (optional)
            
        Returns:
            dict: PR information with file path added
        """
        # Ensure we have repository and PR number
        repo = pr_data.get("repository")
        pr_number = pr_data.get("number")
        
        if not repo or not pr_number:
            raise ValueError("PR data missing repository or number")
        
        # Use provided output directory or get from config
        if not output_dir:
            output_dir = config_manager.get_output_dir()
        
        # Generate output file path
        file_path = generate_output_path(output_dir, repo, pr_number, "json")
        
        # Save to file
        save_json(pr_data, file_path)
        logger.info(f"Saved PR information to {file_path}")
        
        # Add file path to PR data
        pr_data["file_path"] = str(file_path)
        
        return pr_data
    
    def _analyze_key_commits(self, pr_data: Dict[str, Any]) -> str:
        """
        Analyze key commits in the PR
        
        Args:
            pr_data: PR data
            
        Returns:
            str: Key commit analysis
        """
        # We no longer fetch commits data, so return a simple message
        return "Commit information is not available as commits data is not fetched."

def parse_arguments():
    """
    Parse command line arguments
    
    Returns:
        argparse.Namespace: Parsed arguments
    """
    parser = argparse.ArgumentParser(description='Fetch PR information using GitHub CLI')
    parser.add_argument('--repo', required=True, help='Repository in owner/repo format')
    parser.add_argument('--pr', required=True, help='PR number')
    parser.add_argument('--config', default='config.json', help='Path to configuration file')
    parser.add_argument('--output-dir', help='Output directory for PR information')
    return parser.parse_args()

def main():
    """
    Main function for command line usage
    """
    # Parse arguments
    args = parse_arguments()
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        # Get GitHub token from config or environment
        github_token = config_manager.get_github_token()
        
        # Initialize PR fetcher
        pr_fetcher = PRFetcher(github_token)
        
        # Set output directory
        output_dir = None
        if args.output_dir:
            output_dir = Path(args.output_dir)
        else:
            output_dir = config_manager.get_output_dir()
        
        # Fetch PR information
        pr_data = pr_fetcher.fetch_pr_info(args.repo, args.pr, output_dir)
        
        logger.info(f"Successfully fetched PR information for {args.repo}#{args.pr}")
        
    except Exception as e:
        logger.error(f"Error in fetch_pr_info: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
