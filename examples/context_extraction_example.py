#!/usr/bin/env python
"""
Example script demonstrating the PR context extraction functionality.
"""

import os
import sys
import argparse
import logging
import json
from typing import Dict, Any

# Add parent directory to path to allow importing the pipeline
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.context.context_manager import ContextManager
from pipeline.agent.llm_providers.openai_provider import OpenAIProvider

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="PR Context Extraction Example")
    
    # Required arguments
    parser.add_argument("--repo-path", required=True, help="Path to the repository")
    
    # Context source (PR or diff file)
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--pr-number", type=int, help="PR number to analyze")
    source_group.add_argument("--diff-file", help="Path to diff file to analyze")
    
    # LLM provider settings
    parser.add_argument("--api-key", required=True, help="API key for the LLM provider")
    parser.add_argument("--model", default="gpt-4-turbo", help="Model to use (default: gpt-4-turbo)")
    
    # Output settings
    parser.add_argument("--output-dir", default="./output", help="Directory to save outputs (default: ./output)")
    parser.add_argument("--context-only", action="store_true", help="Extract context only (no summary)")
    
    return parser.parse_args()

def setup_output_dir(output_dir: str) -> None:
    """Create output directory if it doesn't exist."""
    os.makedirs(output_dir, exist_ok=True)
    logger.info(f"Output will be saved to {output_dir}")

def extract_context(args) -> Dict[str, Any]:
    """Extract context from PR or diff file."""
    # Create the LLM provider
    llm_provider = OpenAIProvider(api_key=args.api_key, model=args.model)
    
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
    """Extract context and generate summary from PR or diff file."""
    # Create the LLM provider
    llm_provider = OpenAIProvider(api_key=args.api_key, model=args.model)
    
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
    """Save outputs to files."""
    # Create timestamp-based filename prefix
    import datetime
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
    """Main function."""
    # Parse arguments
    args = parse_args()
    
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
        logger.error(f"Error during PR context extraction: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main() 