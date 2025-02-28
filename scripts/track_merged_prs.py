#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Track merged PRs for repositories and maintain a status file
that indicates the latest processed PR number for batch operations.
This script also outputs unsynchronized merged PRs.
"""

import yaml
import sys
import os
import json
import argparse
import requests
import re
from pathlib import Path
from datetime import datetime

# GitHub API rate limits can be an issue, consider using authentication
# if you encounter rate limiting problems
GITHUB_API_BASE = "https://api.github.com"

def read_config(config_path):
    """
    Read configuration file and return its contents
    
    Args:
        config_path: Path to the configuration file
        
    Returns:
        dict: Configuration contents
    """
    try:
        with open(config_path, 'r') as file:
            config = yaml.safe_load(file)
            return config
    except Exception as e:
        print(f"Error reading configuration file: {e}")
        return None

def get_status_file_path(project_root):
    """
    Get the path to the status file
    
    Args:
        project_root: Project root directory
        
    Returns:
        Path: Path to the status file
    """
    status_dir = project_root / "repos"
    status_dir.mkdir(exist_ok=True)
    return status_dir / "pr_processing_status.json"

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
            with open(status_file_path, 'r') as file:
                return json.load(file)
        except Exception as e:
            print(f"Error reading status file: {e}")
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
        
        with open(status_file_path, 'w') as file:
            json.dump(status_data, file, indent=2)
        return True
    except Exception as e:
        print(f"Error writing status file: {e}")
        return False

def validate_repo_url(repo_url):
    """
    Validate and normalize the repository URL
    
    Args:
        repo_url: Repository URL or owner/repo format
        
    Returns:
        str: Repository in owner/repo format
    """
    # If it's already in owner/repo format
    if re.match(r'^[^/]+/[^/]+$', repo_url):
        return repo_url
    
    # Extract owner/repo from GitHub URL
    match = re.search(r'github\.com[:/]([^/]+/[^/]+?)(?:\.git)?/?$', repo_url)
    if match:
        return match.group(1)
    
    raise ValueError(f"Invalid repository format: {repo_url}. Expected format: owner/repo or GitHub URL")

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
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        # Filter to only merged PRs
        merged_prs = [pr for pr in response.json() if pr.get("merged_at")]
        
        if not merged_prs:
            print(f"No merged PRs found for {repo}")
            return []
        
        return merged_prs
    except requests.exceptions.RequestException as e:
        print(f"Error fetching PRs for {repo}: {e}")
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
    parser = argparse.ArgumentParser(description='Track merged PRs and output unsynced PRs')
    parser.add_argument('--repo', required=True, help='Repository URL or owner/repo format')
    parser.add_argument('--token', help='GitHub API token for authentication')
    parser.add_argument('--update', action='store_true', 
                        help='Update the status file with the latest PR')
    parser.add_argument('--operation', help='Name of the batch operation (used with --update)')
    parser.add_argument('--status', choices=['success', 'failure'], default='success',
                        help='Status of the operation (used with --update and --operation)')
    parser.add_argument('--limit', type=int, default=10, 
                        help='Maximum number of PRs to fetch')
    return parser.parse_args()

def main():
    """Main function"""
    # Parse command line arguments
    args = parse_arguments()
    
    # Get project root directory
    script_dir = Path(os.path.dirname(os.path.abspath(__file__)))
    project_root = script_dir.parent
    
    # Validate and normalize repository URL
    try:
        repo = validate_repo_url(args.repo)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)
    
    # Get status file path
    status_file_path = get_status_file_path(project_root)
    
    # Read current status
    status_data = read_status_file(status_file_path)
    
    # Get repository status
    repo_status = get_repo_status(status_data, repo)
    latest_processed_pr = repo_status.get("latest_processed_pr", 0)
    
    print(f"Checking merged PRs for {repo}...")
    print(f"Latest processed PR: #{latest_processed_pr}")
    
    # Get merged PRs
    merged_prs = get_merged_prs(repo, args.token, args.limit)
    
    if not merged_prs:
        print("No merged PRs found.")
        sys.exit(0)
    
    # Find unsynced PRs
    unsynced_prs = find_unsynced_prs(merged_prs, latest_processed_pr)
    
    if not unsynced_prs:
        print("No unsynced PRs found. Repository is up to date.")
        sys.exit(0)
    
    # Output unsynced PRs
    print(f"\nFound {len(unsynced_prs)} unsynced PRs:")
    for pr in unsynced_prs:
        print(f"#{pr['number']} - {pr['title']} (merged by {pr.get('merged_by', {}).get('login', 'Unknown')})")
    
    # If no PRs have been processed yet, output the latest merged PR
    if latest_processed_pr == 0 and merged_prs:
        latest_pr = merged_prs[0]
        print(f"\nNo PRs have been processed yet. Latest merged PR: #{latest_pr['number']} - {latest_pr['title']}")
    
    # Update status file if requested
    if args.update:
        if unsynced_prs:
            # Update with the latest unsynced PR
            latest_unsynced_pr = unsynced_prs[0]
            success = args.status == 'success'
            
            if update_repo_status(status_data, repo, latest_unsynced_pr, args.operation, success):
                print(f"\nUpdated status for {repo} - Latest PR: #{latest_unsynced_pr['number']} - {latest_unsynced_pr['title']}")
                
                if write_status_file(status_file_path, status_data):
                    print(f"Status file updated: {status_file_path}")
                else:
                    print("Failed to update status file")
            else:
                print(f"No updates to status file needed")
        else:
            print("No updates to status file needed")

if __name__ == "__main__":
    main() 