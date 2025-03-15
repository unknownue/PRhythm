#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Check and clone tracked repositories from config.json to output directories
"""

import sys
import argparse
from pathlib import Path

# Import common utilities
from common import (
    read_config, 
    ensure_directory, 
    run_command, 
    get_project_root,
    setup_logging
)

# Setup logger
logger = setup_logging("check_pull_repo")

def create_output_dirs(project_root, repositories, config):
    """
    Create output directories for each tracked repository
    
    Args:
        project_root: Project root directory
        repositories: List of repositories to track
        config: Configuration dictionary
        
    Returns:
        dict: Mapping of repository names to their output directories
    """
    # Get repos directory from config or use default
    repos_base_dir = config.get('paths', {}).get('repos_dir', './repos')
    
    # Convert relative path to absolute if needed
    if repos_base_dir.startswith('./') or repos_base_dir.startswith('../'):
        repos_dir = project_root / repos_base_dir.lstrip('./')
    else:
        repos_dir = Path(repos_base_dir)
    
    # Create main output directory if it doesn't exist
    ensure_directory(repos_dir)
    
    # Create directories for each repository
    repo_dirs = {}
    for repo in repositories:
        # Extract repo name from owner/repo format
        repo_name = repo.split('/')[-1]
        
        # Create repository-specific directory
        repo_dir = repos_dir / repo_name
        ensure_directory(repo_dir)
        
        repo_dirs[repo] = repo_dir
    
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
        logger.info(f"Skipping clone/pull for repository: {repo}")
        return True
        
    try:
        if repo_dir.exists() and (repo_dir / ".git").exists():
            # Repository already exists, pull latest changes
            logger.info(f"Updating existing repository: {repo}")
            cmd = f"cd {repo_dir} && git pull"
            run_command(cmd)
        else:
            # Clone the repository
            logger.info(f"Cloning repository: {repo}")
            cmd = f"git clone https://github.com/{repo}.git {repo_dir}"
            run_command(cmd, timeout=300)  # Longer timeout for cloning
        
        return True
    except TimeoutError as e:
        logger.error(f"Timeout error with repository {repo}: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error with repository {repo}: {e}")
        return False

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Check and clone tracked repositories')
    parser.add_argument('--skip-clone', action='store_true', 
                        help='Skip cloning repositories, only create directories')
    parser.add_argument('--config', type=str, default="config.json",
                        help='Path to the configuration file')
    return parser.parse_args()

def main():
    """Main function"""
    # Parse command line arguments
    args = parse_arguments()
    
    # Get project root directory
    project_root = get_project_root()
    
    # Configuration file path
    config_path = project_root / args.config
    
    # Read configuration
    try:
        config = read_config(config_path)
    except Exception as e:
        logger.error(f"Failed to read configuration: {e}")
        sys.exit(1)
    
    # Get repositories list
    if 'github' not in config or 'repositories' not in config['github']:
        logger.error("No GitHub repository information found in configuration file")
        sys.exit(1)
    
    repositories = config['github']['repositories']
    
    if not repositories:
        logger.error("No GitHub repositories configured")
        sys.exit(1)
    
    # Print tracked repositories
    logger.info("Tracked PR repositories:")
    for repo in repositories:
        logger.info(f"- {repo}")
    
    # Create output directories
    repo_dirs = create_output_dirs(project_root, repositories, config)
    
    # Clone/pull repositories
    success_count = 0
    for repo, repo_dir in repo_dirs.items():
        if clone_repository(repo, repo_dir, args.skip_clone):
            success_count += 1
    
    logger.info(f"\nSuccessfully processed {success_count} out of {len(repositories)} repositories")

if __name__ == "__main__":
    main() 