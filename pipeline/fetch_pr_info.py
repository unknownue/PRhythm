#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Fetch PR information using GitHub CLI (gh) and store it as JSON in the output directory.
This script requires the GitHub CLI to be installed and authenticated.

Features:
- Fetch PR information including title, number, description, and diff
- Store PR information as JSON for later analysis
- Optionally extract relevant context from PR diff using smart context extraction
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
from providers.provider_factory import get_provider_from_config, get_provider
from providers.openai_provider import OpenAIProvider

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
    
    # Context extraction options
    parser.add_argument('--extract-context', action='store_true', help='Extract relevant context from PR diff')
    parser.add_argument('--local-repo-path', help='Path to local repository for context extraction')
    parser.add_argument('--context-model', default='gpt-4-turbo', help='Model to use for context extraction (default: gpt-4-turbo)')
    parser.add_argument('--provider', default='openai', help='LLM provider to use for context extraction (default: openai)')
    
    return parser.parse_args()

def extract_context(repo_path, pr_number, diff_content, model=None, provider_name='openai'):
    """
    Extract context from a PR.
    
    Args:
        repo_path: Path to the local repository
        pr_number: PR number
        diff_content: PR diff content
        model: Model to use for context extraction
        provider_name: LLM provider name (default: openai)
        
    Returns:
        dict: Extracted context
    """
    logger.info(f"Extracting context from PR #{pr_number} using {provider_name} provider")
    
    try:
        # Import context extraction modules
        from pipeline.context.context_manager import ContextManager
        
        # Get full config
        config = config_manager.get_full_config()
        
        # Create LLM provider
        if provider_name.lower() == 'openai':
            # Get OpenAI API key
            api_key = config_manager.get_openai_api_key()
            if not api_key:
                logger.error("OpenAI API key not found in config")
                return None
            
            # Create OpenAI provider
            llm_provider = get_provider('openai', api_key, model=model or "gpt-4-turbo")
        else:
            # Try to get provider from config
            try:
                llm_provider = get_provider_from_config(config)
                
                # Override model if specified
                if model:
                    llm_provider.model = model
                    
                logger.info(f"Using {llm_provider.get_model_name()} model from {provider_name} provider")
            except Exception as e:
                logger.error(f"Error creating provider from config: {e}")
                return None
        
        # Create context manager
        context_manager = ContextManager(repo_path)
        context_manager.set_provider(llm_provider)
        
        # Extract context
        if diff_content:
            context = context_manager.extract_context_from_diff(diff_content)
        else:
            context = context_manager.extract_context_from_pr(pr_number)
        
        return context
    except Exception as e:
        logger.error(f"Error extracting context: {e}")
        return None

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
        
        # Extract context if requested
        if args.extract_context:
            # Determine repository path
            repo_path = args.local_repo_path
            if not repo_path:
                # Default repository path
                repo_path = os.path.join(os.getcwd(), 'repos', args.repo.replace('/', '_'))
                logger.info(f"Using default repository path: {repo_path}")
            
            # Check if repository exists
            if not os.path.exists(repo_path):
                logger.warning(f"Repository not found at {repo_path}")
                logger.info(f"Looking for cloned repository...")
                
                # Try to find the repository in common locations
                for common_path in ['repos', 'repositories', '.']:
                    potential_path = os.path.join(os.getcwd(), common_path, args.repo.replace('/', '_'))
                    if os.path.exists(potential_path):
                        repo_path = potential_path
                        logger.info(f"Found repository at {repo_path}")
                        break
            
            if os.path.exists(repo_path):
                # Extract context
                diff_content = pr_data.get('diff', '')
                context = extract_context(
                    repo_path, 
                    args.pr, 
                    diff_content, 
                    args.context_model,
                    args.provider
                )
                
                if context:
                    # Add context to PR data
                    pr_data['context'] = context
                    
                    # Save updated PR data
                    output_path = generate_output_path(args.repo, args.pr, output_dir)
                    with open(output_path, 'w') as f:
                        json.dump(pr_data, f, indent=2)
                    
                    logger.info(f"PR information with context saved to {output_path}")
            else:
                logger.error(f"Repository not found. Cannot extract context.")
        
        logger.info(f"Successfully fetched PR information for {args.repo}#{args.pr}")
        
    except Exception as e:
        logger.error(f"Error in fetch_pr_info: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 