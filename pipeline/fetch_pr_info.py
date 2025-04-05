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
import time
import logging

# Import refactored modules
from utils.config_manager import config_manager
from utils.file_utils import ensure_directory, generate_output_path
from pr_fetcher import PRFetcher
from github_client import GitHubClient

# Setup logger
logger = logging.getLogger("fetch_pr_info")

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