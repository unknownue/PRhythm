#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Track merged PRs for repositories and maintain a status file
that indicates the latest processed PR number for batch operations.
This script also outputs unsynchronized merged PRs.
"""

import sys
import argparse
import requests
from pathlib import Path
from datetime import datetime

# Import common utilities
from common import (
    read_config,
    get_project_root,
    setup_logging,
    validate_repo_url,
    ensure_directory,
    save_json,
    load_json
)

# Setup logger
logger = setup_logging("track_merged_prs")

# GitHub API rate limits can be an issue, consider using authentication
# if you encounter rate limiting problems
GITHUB_API_BASE = "https://api.github.com"

def get_status_file_path(project_root, config):
    """
    Get the path to the status file
    
    Args:
        project_root: Project root directory
        config: Configuration dictionary
        
    Returns:
        Path: Path to the status file
    """
    # Get repos directory from config or use default
    repos_base_dir = config.get('paths', {}).get('repos_dir', './repos')
    
    # Convert relative path to absolute if needed
    if repos_base_dir.startswith('./') or repos_base_dir.startswith('../'):
        repos_dir = project_root / repos_base_dir.lstrip('./')
    else:
        repos_dir = Path(repos_base_dir)
    
    # Create directory if it doesn't exist
    ensure_directory(repos_dir)
    
    return repos_dir / "pr_processing_status.json"

def read_status_file(status_file_path):
    """
    Read the status file or create a new one if it doesn't exist
    
    Args:
        status_file_path: Path to the status file
        
    Returns:
        dict: Status information
    """
    if status_file_path.exists():
        try:
            return load_json(status_file_path)
        except Exception as e:
            logger.error(f"Error reading status file: {e}")
            # Return a new status object if there's an error
    
    # Default status structure
    return {
        "repositories": {},
        "last_updated": datetime.now().isoformat(),
        "batch_operations": []
    }

def write_status_file(status_file_path, status_data):
    """
    Write status information to the status file
    
    Args:
        status_file_path: Path to the status file
        status_data: Status information to write
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Update the last updated timestamp
        status_data["last_updated"] = datetime.now().isoformat()
        
        save_json(status_data, status_file_path)
        return True
    except Exception as e:
        logger.error(f"Error writing status file: {e}")
        return False

def get_merged_prs(repo, token=None, limit=10):
    """
    Get a list of merged PRs for a repository
    
    Args:
        repo: Repository name (owner/repo)
        token: GitHub API token (optional)
        limit: Maximum number of PRs to fetch
        
    Returns:
        list: List of merged PR information
    """
    headers = {}
    if token:
        headers["Authorization"] = f"token {token}"
    
    url = f"{GITHUB_API_BASE}/repos/{repo}/pulls?state=closed&sort=updated&direction=desc&per_page={limit}"
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        # Filter to only merged PRs
        merged_prs = [pr for pr in response.json() if pr.get("merged_at")]
        
        if not merged_prs:
            logger.info(f"No merged PRs found for {repo}")
            return []
        
        return merged_prs
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching PRs for {repo}: {e}")
        return []

def get_repo_status(status_data, repo):
    """
    Get the status information for a repository
    
    Args:
        status_data: Current status data
        repo: Repository name
        
    Returns:
        dict: Repository status information
    """
    # Initialize repository entry if it doesn't exist
    if repo not in status_data["repositories"]:
        status_data["repositories"][repo] = {
            "latest_processed_pr": 0,
            "last_updated": None
        }
    
    return status_data["repositories"][repo]

def update_repo_status(status_data, repo, pr_info, operation_name=None, success=True):
    """
    Update the status information for a repository
    
    Args:
        status_data: Current status data
        repo: Repository name
        pr_info: PR information
        operation_name: Name of the batch operation (optional)
        success: Whether the operation was successful
        
    Returns:
        bool: True if status was updated, False otherwise
    """
    if not pr_info:
        return False
    
    repo_status = get_repo_status(status_data, repo)
    current_pr_number = pr_info["number"]
    
    # Update only if the new PR number is higher
    if current_pr_number > repo_status["latest_processed_pr"]:
        repo_status["latest_processed_pr"] = current_pr_number
        repo_status["last_updated"] = datetime.now().isoformat()
        repo_status["latest_pr_title"] = pr_info["title"]
        repo_status["latest_pr_url"] = pr_info["html_url"]
        
        # Add batch operation record if operation name is provided
        if operation_name:
            batch_operation = {
                "timestamp": datetime.now().isoformat(),
                "repository": repo,
                "pr_number": current_pr_number,
                "operation": operation_name,
                "success": success
            }
            
            if "batch_operations" not in status_data:
                status_data["batch_operations"] = []
            
            status_data["batch_operations"].append(batch_operation)
            
            # Keep only the last 100 batch operations to prevent the file from growing too large
            if len(status_data["batch_operations"]) > 100:
                status_data["batch_operations"] = status_data["batch_operations"][-100:]
        
        return True
    
    return False

def find_unsynced_prs(merged_prs, latest_processed_pr):
    """
    Find PRs that have been merged but not yet processed
    
    Args:
        merged_prs: List of merged PRs
        latest_processed_pr: Latest processed PR number
        
    Returns:
        list: List of unsynced PR information
    """
    return [pr for pr in merged_prs if pr["number"] > latest_processed_pr]

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Track merged PRs for repositories')
    parser.add_argument('--repo', help='Repository name in owner/repo format or GitHub URL')
    parser.add_argument('--token', help='GitHub API token (optional)')
    parser.add_argument('--limit', type=int, default=10, help='Maximum number of PRs to fetch (default: 10)')
    parser.add_argument('--config', type=str, default="config.json", help='Path to the configuration file')
    return parser.parse_args()

def main():
    """Main function"""
    # Parse command line arguments
    args = parse_arguments()
    
    # Get project root directory
    project_root = get_project_root()
    
    # Configuration file path
    config_path = project_root / args.config
    
    try:
        # Read configuration
        config = read_config(config_path)
        
        # Get repositories list from arguments or config
        if args.repo:
            repositories = [validate_repo_url(args.repo)]
        else:
            if not config or 'github' not in config or 'repositories' not in config['github']:
                logger.error("No repositories found in configuration")
                sys.exit(1)
            
            repositories = config['github']['repositories']
        
        # Get status file path
        status_file_path = get_status_file_path(project_root, config)
        
        # Read status file
        status_data = read_status_file(status_file_path)
        
        # Process each repository
        updated = False
        for repo in repositories:
            # Get repository status
            repo_status = get_repo_status(status_data, repo)
            latest_processed_pr = repo_status["latest_processed_pr"]
            
            # Get merged PRs
            logger.info(f"Fetching merged PRs for {repo}...")
            merged_prs = get_merged_prs(repo, args.token, args.limit)
            
            # Find unsynced PRs
            unsynced_prs = find_unsynced_prs(merged_prs, latest_processed_pr)
            
            if unsynced_prs:
                logger.info(f"Found {len(unsynced_prs)} unsynced PR(s) for {repo}")
                for pr in unsynced_prs:
                    print(f"#{pr['number']} - {pr['title']} ({pr['html_url']})")
                    
                # Update repository status with the latest PR
                if update_repo_status(status_data, repo, unsynced_prs[0], "track_merged_prs"):
                    updated = True
            else:
                logger.info(f"No unsynced PRs found for {repo}")
        
        # Write status file if updated
        if updated:
            write_status_file(status_file_path, status_data)
            logger.info(f"Status file updated: {status_file_path}")
        
    except Exception as e:
        logger.error(f"Error processing PRs: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 