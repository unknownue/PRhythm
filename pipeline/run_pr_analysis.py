#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Analyze PR information using LLM API and generate a markdown report.
This script takes a PR JSON file path and output language as input,
then sends a request to the configured LLM API to generate an analysis report.

Features:
- Generate PR analysis report in different languages
- Save the PR diff as a separate patch file (using --save-diff flag)
- Analyze codebase architecture and impact of changes
- Extract learning points from the PR
"""

import sys
import argparse
import logging
from pathlib import Path

# Import refactored modules
from utils.config_manager import config_manager
from utils.languages import is_supported_language, get_language_name
from pr_analyzer import PRAnalyzer

# Setup logger
logger = logging.getLogger("analyze_pr")

def parse_arguments():
    """
    Parse command line arguments
        
    Returns:
        argparse.Namespace: Parsed arguments
    """
    parser = argparse.ArgumentParser(description='Analyze PR information using LLM')
    
    # PR identification (either repo+pr or json)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--json', help='Path to PR JSON file')
    group.add_argument('--repo', help='Repository in owner/repo format')
    
    # If using --repo, PR number is required
    parser.add_argument('--pr', help='PR number (required if --repo is used)')
    
    # Other options
    parser.add_argument('--language', default='en', help='Output language code (e.g., en, zh-cn)')
    parser.add_argument('--output-dir', help='Output directory for analysis results')
    parser.add_argument('--config', default='config.json', help='Path to configuration file')
    parser.add_argument('--save-diff', action='store_true', help='Save PR diff as a separate file')
    parser.add_argument('--provider', help='LLM provider to use (overrides config)')
    parser.add_argument('--dry-run', action='store_true', help='Dry run mode (don\'t actually call LLM API)')
    parser.add_argument('--save-prompt', action='store_true', help='Save the full LLM prompt to a file in the logs directory')
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.repo and not args.pr:
        parser.error('--pr is required when using --repo')
    
    return args

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
        # Initialize PR analyzer
        analyzer = PRAnalyzer()
        
        # Set output directory
        output_dir = None
        if args.output_dir:
            output_dir = Path(args.output_dir)
        
        # Analyze PR
        result = None
        if args.json:
            result = analyzer.analyze_pr_from_file(
                args.json, 
                args.language, 
                output_dir, 
                args.save_diff,
                args.dry_run,
                args.save_prompt
            )
        else:
            result = analyzer.analyze_pr_from_repo(
                args.repo, 
                args.pr, 
                args.language, 
                output_dir, 
                args.save_diff,
                args.dry_run,
                args.save_prompt
            )
        
        logger.info(f"Analysis completed successfully")
        
        # Print path to analysis file if available
        if "analysis_path" in result:
            logger.info(f"Analysis saved to: {result['analysis_path']}")
        
    except Exception as e:
        logger.error(f"Error in analyze_pr: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 