#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Check and clone tracked repositories from config.yaml to output directories
"""

import yaml
import sys
import os
import subprocess
import argparse
from pathlib import Path

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

def create_output_dirs(project_root, repositories):
    """
    Create output directories for each tracked repository
    
    Args:
        project_root: Project root directory
        repositories: List of repositories to track
        
    Returns:
        dict: Mapping of repository names to their output directories
    """
    # Create main output directory if it doesn't exist
    output_dir = project_root / "repos"
    output_dir.mkdir(exist_ok=True)
    
    # Create directories for each repository
    repo_dirs = {}
    for repo in repositories:
        # Extract owner and repo name
        parts = repo.split('/')
        if len(parts) != 2:
            print(f"Invalid repository format: {repo}. Expected format: owner/repo")
            continue
        
        owner, repo_name = parts
        
        # Create directory structure: repos/repo_name
        repo_dir = output_dir / repo_name
        if not repo_dir.exists():
            repo_dir.mkdir(exist_ok=True)
            
        repo_dirs[repo] = repo_dir
        
        print(f"Created output directory for {repo}: {repo_dir}")
    
    return repo_dirs

def clone_repository(repo, repo_dir, skip_clone=False):
    """
    Clone or pull the repository
    
    Args:
        repo: Repository name (owner/repo)
        repo_dir: Directory to clone the repository into
        skip_clone: If True, skip the actual clone/pull operation
        
    Returns:
        bool: True if successful, False otherwise
    """
    if skip_clone:
        print(f"Skipping clone/pull for repository: {repo}")
        return True
        
    try:
        if repo_dir.exists() and (repo_dir / ".git").exists():
            # Repository already exists, pull latest changes
            print(f"Updating existing repository: {repo}")
            cmd = f"cd {repo_dir} && git pull"
            subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
        else:
            # Clone the repository
            print(f"Cloning repository: {repo}")
            cmd = f"git clone https://github.com/{repo}.git {repo_dir}"
            subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
        
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error cloning/pulling repository {repo}: {e}")
        print(f"Error output: {e.stderr}")
        return False
    except Exception as e:
        print(f"Unexpected error with repository {repo}: {e}")
        return False

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Check and clone tracked repositories')
    parser.add_argument('--skip-clone', action='store_true', 
                        help='Skip cloning repositories, only create directories')
    return parser.parse_args()

def main():
    """Main function"""
    # Parse command line arguments
    args = parse_arguments()
    
    # Get project root directory
    script_dir = Path(os.path.dirname(os.path.abspath(__file__)))
    project_root = script_dir.parent
    
    # Configuration file path
    config_path = project_root / "config.yaml"
    
    # Read configuration
    config = read_config(config_path)
    
    if not config:
        sys.exit(1)
    
    # Get repositories list
    if 'github' not in config or 'repositories' not in config['github']:
        print("No GitHub repository information found in configuration file")
        sys.exit(1)
    
    repositories = config['github']['repositories']
    
    if not repositories:
        print("No GitHub repositories configured")
        sys.exit(1)
    
    # Print tracked repositories
    print("Tracked PR repositories:")
    for repo in repositories:
        print(f"- {repo}")
    
    # Create output directories
    repo_dirs = create_output_dirs(project_root, repositories)
    
    # Clone/pull repositories
    success_count = 0
    for repo, repo_dir in repo_dirs.items():
        if clone_repository(repo, repo_dir, args.skip_clone):
            success_count += 1
    
    print(f"\nSuccessfully processed {success_count} out of {len(repositories)} repositories")

if __name__ == "__main__":
    main() 