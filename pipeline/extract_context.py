#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Extract context from a PR or diff file.
This script demonstrates the PR context extraction functionality.

Features:
- Extract context from PR number or diff file
- Generate summary of the extracted context
- Save context and summary to files
"""

import os
import sys
import argparse
import logging
import json
import datetime
from typing import Dict, Any
from pathlib import Path

# Add parent directory to path if needed
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import context extraction modules
from pipeline.context.context_manager import ContextManager
from providers.provider_factory import get_provider, get_provider_from_config
from providers.openai_provider import OpenAIProvider
from utils.config_manager import config_manager

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("extract_context")

def parse_arguments():
    """
    Parse command line arguments
    
    Returns:
        argparse.Namespace: Parsed arguments
    """
    parser = argparse.ArgumentParser(description='Extract context from a PR or diff file')
    
    # Required arguments
    parser.add_argument('--repo-path', required=True, help='Path to the repository')
    
    # Context source (PR or diff file)
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument('--pr-number', type=int, help='PR number to analyze')
    source_group.add_argument('--diff-file', help='Path to diff file to analyze')
    
    # LLM provider settings
    parser.add_argument('--api-key', help='API key for the LLM provider (default: from config)')
    parser.add_argument('--model', default='gpt-4-turbo', help='Model to use (default: gpt-4-turbo)')
    parser.add_argument('--provider', default='openai', help='LLM provider to use (default: openai)')
    
    # Output settings
    parser.add_argument('--output-dir', default='./output', help='Directory to save outputs (default: ./output)')
    parser.add_argument('--context-only', action='store_true', help='Extract context only (no summary)')
    parser.add_argument('--output-format', choices=['json', 'text'], default='json', help='Output format (default: json)')
    
    return parser.parse_args()

def setup_output_dir(output_dir: str) -> None:
    """
    Create output directory if it doesn't exist
    
    Args:
        output_dir: Output directory path
    """
    os.makedirs(output_dir, exist_ok=True)
    logger.info(f"Output will be saved to {output_dir}")

def get_llm_provider(args):
    """
    Get LLM provider based on command arguments
    
    Args:
        args: Command line arguments
        
    Returns:
        BaseProvider: LLM provider instance
    """
    provider_name = args.provider.lower()
    
    # Get API key from args or config
    api_key = args.api_key
    if not api_key:
        if provider_name == 'openai':
            api_key = config_manager.get_openai_api_key()
        else:
            # Try to get API key from config or environment
            config = config_manager.get_full_config()
            try:
                api_key = config.get('llm', {}).get('providers', {}).get(provider_name, {}).get('api_key', '')
            except:
                api_key = ''
                
            # Try environment variable
            if not api_key:
                import os
                env_var_name = f"{provider_name.upper()}_API_KEY"
                api_key = os.environ.get(env_var_name, '')
    
    if not api_key:
        logger.error(f"No API key provided for {provider_name} provider and none found in config or environment")
        sys.exit(1)
    
    # Create the LLM provider
    try:
        if provider_name == 'openai':
            llm_provider = get_provider('openai', api_key, model=args.model)
        else:
            # Try to get provider from registry
            llm_provider = get_provider(provider_name, api_key, model=args.model)
    except Exception as e:
        logger.error(f"Error creating {provider_name} provider: {e}")
        logger.info("Falling back to OpenAI provider...")
        # Fallback to OpenAI
        openai_api_key = config_manager.get_openai_api_key()
        if not openai_api_key:
            logger.error("No OpenAI API key found in config, cannot create fallback provider")
            sys.exit(1)
        llm_provider = get_provider('openai', openai_api_key, model=args.model)
    
    logger.info(f"Using {llm_provider.get_model_name()} model from {provider_name} provider")
    return llm_provider

def extract_context(args) -> Dict[str, Any]:
    """
    Extract context from PR or diff file
    
    Args:
        args: Command line arguments
        
    Returns:
        Dict[str, Any]: Extracted context
    """
    # Get LLM provider
    llm_provider = get_llm_provider(args)
    
    # Create the context manager
    context_manager = ContextManager(args.repo_path)
    context_manager.set_provider(llm_provider)
    
    # Extract context
    if args.pr_number:
        logger.info(f"Extracting context from PR #{args.pr_number}")
        context = context_manager.extract_context_from_pr(args.pr_number)
    else:
        logger.info(f"Extracting context from diff file: {args.diff_file}")
        with open(args.diff_file, 'r') as f:
            diff_content = f.read()
        context = context_manager.extract_context_from_diff(diff_content)
    
    return context

def extract_and_summarize(args) -> Dict[str, Any]:
    """
    Extract context and generate summary from PR or diff file
    
    Args:
        args: Command line arguments
        
    Returns:
        Dict[str, Any]: Dictionary with context and summary
    """
    # Get LLM provider
    llm_provider = get_llm_provider(args)
    
    # Create the context manager
    context_manager = ContextManager(args.repo_path)
    context_manager.set_provider(llm_provider)
    
    # Extract context and summarize
    if args.pr_number:
        logger.info(f"Extracting and summarizing PR #{args.pr_number}")
        result = context_manager.extract_and_summarize(pr_number=args.pr_number)
    else:
        logger.info(f"Extracting and summarizing diff file: {args.diff_file}")
        with open(args.diff_file, 'r') as f:
            diff_content = f.read()
        result = context_manager.extract_and_summarize(diff_content=diff_content)
    
    return result

def save_outputs(result: Dict[str, Any], args) -> None:
    """
    Save outputs to files
    
    Args:
        result: Extracted context and/or summary
        args: Command line arguments
    """
    # Create timestamp-based filename prefix
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    
    if args.pr_number:
        prefix = f"{timestamp}_pr{args.pr_number}"
    else:
        diff_filename = os.path.basename(args.diff_file)
        prefix = f"{timestamp}_{diff_filename.split('.')[0]}"
    
    # Save context
    context_file = os.path.join(args.output_dir, f"{prefix}_context.json")
    with open(context_file, 'w') as f:
        json.dump(result["context"], f, indent=2)
    logger.info(f"Context saved to {context_file}")
    
    # Save summary if available
    if "summary" in result:
        summary_file = os.path.join(args.output_dir, f"{prefix}_summary.json")
        with open(summary_file, 'w') as f:
            json.dump(result["summary"], f, indent=2)
        logger.info(f"Summary saved to {summary_file}")
        
        # Save concise summary to text file for easy reading
        concise_summary = result["summary"].get("concise_summary", "No concise summary available")
        concise_file = os.path.join(args.output_dir, f"{prefix}_concise_summary.txt")
        with open(concise_file, 'w') as f:
            f.write(concise_summary)
        logger.info(f"Concise summary saved to {concise_file}")

def main():
    """
    Main function for command line usage
    """
    # Parse arguments
    args = parse_arguments()
    
    # Setup output directory
    setup_output_dir(args.output_dir)
    
    try:
        # Extract context (and summary)
        if args.context_only:
            context = extract_context(args)
            result = {"context": context}
        else:
            result = extract_and_summarize(args)
        
        # Save outputs
        save_outputs(result, args)
        
        logger.info("PR context extraction completed successfully")
    except Exception as e:
        logger.error(f"Error during PR context extraction: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main() 