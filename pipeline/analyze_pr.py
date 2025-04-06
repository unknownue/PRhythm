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
- Extract relevant context using smart context extraction (using --extract-context flag)
"""

import sys
import argparse
import logging
import os
import json
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
    
    # Context extraction options
    parser.add_argument('--extract-context', action='store_true', help='Use smart context extraction instead of using raw diff')
    parser.add_argument('--save-context', action='store_true', help='Save extracted context to a file')
    parser.add_argument('--context-model', default='gpt-4-turbo', help='Model to use for context extraction (default: gpt-4-turbo)')
    parser.add_argument('--local-repo-path', help='Path to local repository for context extraction')
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.repo and not args.pr:
        parser.error('--pr is required when using --repo')
    
    if args.extract_context and not args.local_repo_path:
        logger.warning('--local-repo-path not specified for context extraction, will try to locate repository')
    
    if args.save_context and not args.extract_context:
        parser.error('--save-context requires --extract-context')
    
    return args

def extract_context(repo_path, pr_number=None, diff_content=None, provider=None, model=None, output_dir=None):
    """
    Extract context from a PR or diff content.
    
    Args:
        repo_path: Path to the local repository
        pr_number: PR number (optional)
        diff_content: PR diff content (optional)
        provider: LLM provider to use
        model: Model to use for context extraction
        output_dir: Output directory for context
        
    Returns:
        dict: Extracted context
    """
    logger.info(f"Extracting context using {'PR #'+str(pr_number) if pr_number else 'diff content'}")
    
    try:
        # Import context extraction modules
        from pipeline.context.context_manager import ContextManager
        from pipeline.agent.llm_providers.openai_provider import OpenAIProvider
        
        # Get OpenAI API key
        api_key = config_manager.get_openai_api_key()
        if not api_key:
            logger.error("OpenAI API key not found in config")
            return None
        
        # Create LLM provider
        llm_provider = OpenAIProvider(api_key=api_key, model=model or "gpt-4-turbo")
        
        # Create context manager
        context_manager = ContextManager(repo_path)
        context_manager.set_provider(llm_provider)
        
        # Extract context
        if pr_number:
            context = context_manager.extract_context_from_pr(pr_number)
        else:
            context = context_manager.extract_context_from_diff(diff_content)
        
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
        # Initialize PR analyzer
        analyzer = PRAnalyzer()
        
        # Set output directory
        output_dir = None
        if args.output_dir:
            output_dir = Path(args.output_dir)
        
        # Get PR data and diff
        pr_data = None
        diff_content = None
        
        if args.json:
            # Load PR data from JSON file
            with open(args.json, 'r') as f:
                pr_data = json.load(f)
                if 'diff' in pr_data:
                    diff_content = pr_data['diff']
        else:
            # Get PR data from repository
            pr_data = analyzer.get_pr_data(args.repo, args.pr)
            if pr_data and 'diff' in pr_data:
                diff_content = pr_data['diff']
        
        # Handle context extraction if enabled
        context = None
        if args.extract_context:
            repo_path = args.local_repo_path or os.path.join(os.getcwd(), 'repos', args.repo.replace('/', '_'))
            
            # Extract context
            context = extract_context(
                repo_path=repo_path,
                pr_number=args.pr if args.repo else None,
                diff_content=diff_content,
                model=args.context_model,
                output_dir=output_dir
            )
            
            # Save context if requested
            if args.save_context and context:
                context_file = None
                if output_dir:
                    if not os.path.exists(output_dir):
                        os.makedirs(output_dir)
                    context_file = os.path.join(output_dir, f"context_{args.pr if args.pr else 'custom'}.json")
                else:
                    # Use default output directory
                    repo_output_dir = os.path.join('output', args.repo.replace('/', '_') if args.repo else 'custom')
                    if not os.path.exists(repo_output_dir):
                        os.makedirs(repo_output_dir)
                    context_file = os.path.join(repo_output_dir, f"context_{args.pr if args.pr else 'custom'}.json")
                
                with open(context_file, 'w') as f:
                    json.dump(context, f, indent=2)
                logger.info(f"Context saved to: {context_file}")
            
            # Update PR data with context
            if context and pr_data:
                pr_data['context'] = context
        
        # Analyze PR
        result = None
        if args.json:
            result = analyzer.analyze_pr_from_file(
                args.json, 
                args.language, 
                output_dir, 
                args.save_diff,
                args.dry_run,
                context=context
            )
        else:
            result = analyzer.analyze_pr_from_repo(
                args.repo, 
                args.pr, 
                args.language, 
                output_dir, 
                args.save_diff,
                args.dry_run,
                context=context
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