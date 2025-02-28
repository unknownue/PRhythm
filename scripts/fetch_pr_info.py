#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Fetch PR information using GitHub CLI (gh) and store it as JSON in the output directory.
This script requires the GitHub CLI to be installed and authenticated.
"""

import json
import sys
import os
import argparse
import subprocess
import re
from pathlib import Path
from datetime import datetime

def ensure_output_dir(project_root, repo):
    """
    Ensure the output directory exists for the specific repository
    
    Args:
        project_root: Project root directory
        repo: Repository name (owner/repo)
        
    Returns:
        Path: Path to the repository-specific output directory
    """
    # Create main output directory if it doesn't exist
    output_dir = project_root / "output"
    output_dir.mkdir(exist_ok=True)
    
    # Extract repo name from owner/repo format
    repo_name = repo.split('/')[-1]
    
    # Create repository-specific directory
    repo_output_dir = output_dir / repo_name
    repo_output_dir.mkdir(exist_ok=True)
    
    return repo_output_dir

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

def fetch_pr_info(repo, pr_number):
    """
    Fetch PR information using GitHub CLI
    
    Args:
        repo: Repository name (owner/repo)
        pr_number: PR number
        
    Returns:
        dict: PR information
    """
    try:
        # Fetch basic PR info
        cmd = f"gh pr view {pr_number} --repo {repo} --json number,title,url,state,author,createdAt,mergedAt,mergedBy,body,commits,files,reviews,comments"
        result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
        pr_data = json.loads(result.stdout)
        
        # Fetch PR diff
        cmd_diff = f"gh pr diff {pr_number} --repo {repo}"
        result_diff = subprocess.run(cmd_diff, shell=True, check=True, capture_output=True, text=True)
        pr_data["diff"] = result_diff.stdout
        
        # Fetch PR checks
        cmd_checks = f"gh pr checks {pr_number} --repo {repo} --json checkSuites,statusCheckRollup"
        try:
            result_checks = subprocess.run(cmd_checks, shell=True, check=True, capture_output=True, text=True)
            pr_data["checks"] = json.loads(result_checks.stdout)
        except subprocess.CalledProcessError:
            # Some PRs might not have checks
            pr_data["checks"] = None
        
        # Add metadata
        pr_data["fetched_at"] = datetime.now().isoformat()
        pr_data["repository"] = repo
        
        return pr_data
    except subprocess.CalledProcessError as e:
        print(f"Error fetching PR information: {e}")
        print(f"Error output: {e.stderr}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)

def save_pr_info(output_dir, repo, pr_number, pr_data):
    """
    Save PR information to a JSON file
    
    Args:
        output_dir: Output directory
        repo: Repository name (owner/repo)
        pr_number: PR number
        pr_data: PR information
        
    Returns:
        Path: Path to the saved file
    """
    # Create a filename without the repo part since it's already in the directory structure
    filename = f"pr_{pr_number}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    file_path = output_dir / filename
    
    try:
        with open(file_path, 'w') as file:
            json.dump(pr_data, file, indent=2)
        return file_path
    except Exception as e:
        print(f"Error saving PR information: {e}")
        sys.exit(1)

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Fetch PR information using GitHub CLI')
    parser.add_argument('--repo', required=True, help='Repository URL or owner/repo format')
    parser.add_argument('--pr', required=True, type=int, help='PR number to fetch')
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
    
    # Ensure repository-specific output directory exists
    output_dir = ensure_output_dir(project_root, repo)
    
    print(f"Fetching information for PR #{args.pr} from repository {repo}...")
    
    # Fetch PR information
    pr_data = fetch_pr_info(repo, args.pr)
    
    # Save PR information
    file_path = save_pr_info(output_dir, repo, args.pr, pr_data)
    
    print(f"PR information saved to: {file_path}")
    print(f"Title: {pr_data.get('title', 'Unknown')}")
    print(f"State: {pr_data.get('state', 'Unknown')}")
    print(f"Author: {pr_data.get('author', {}).get('login', 'Unknown')}")
    
    # Print summary of fetched data
    num_commits = len(pr_data.get('commits', []))
    num_files = len(pr_data.get('files', []))
    num_comments = len(pr_data.get('comments', []))
    
    print(f"Fetched {num_commits} commits, {num_files} files, and {num_comments} comments")

if __name__ == "__main__":
    main() 