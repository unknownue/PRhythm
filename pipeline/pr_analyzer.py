#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
PR Analyzer for PRhythm.
This module analyzes PR content using LLM and generates reports.
"""

import logging
import os
import sys
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional, Union

from providers.provider_factory import get_provider_from_config
from utils.config_manager import config_manager
from utils.file_utils import load_json, save_text, generate_output_path
from utils.languages import is_supported_language, get_language_name
from prompt_builder import PromptBuilder

# Setup logger
logger = logging.getLogger("pr_analyzer")

class PRAnalyzer:
    """
    Analyzes PR content using LLM and generates reports.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize PR analyzer
        
        Args:
            config: Configuration dictionary (optional)
        """
        self.config = config or config_manager.get_full_config()
        self.prompt_builder = PromptBuilder()
        
        # Initialize LLM provider
        self.provider = get_provider_from_config(self.config)
        
        # Get configured languages
        self.languages = config_manager.get_output_languages()
    
    def analyze_pr(self, pr_data: Dict[str, Any], language: str = "en", 
                  output_dir: Optional[Path] = None, save_diff: bool = False,
                  dry_run: bool = False) -> Dict[str, Any]:
        """
        Analyze PR and generate report
        
        Args:
            pr_data: PR data
            language: Output language code
            output_dir: Output directory (optional, for PR data and diff)
            save_diff: Whether to save PR diff as a separate file
            dry_run: If True, don't actually call LLM API
            
        Returns:
            dict: Analysis result
        """
        # Validate language
        if not is_supported_language(language):
            logger.warning(f"Unsupported language: {language}. Defaulting to English.")
            language = "en"
        
        # Extract PR info
        repo = pr_data.get("repository")
        pr_number = pr_data.get("number")
        
        if not repo or not pr_number:
            raise ValueError("PR data missing repository or number")
        
        # Build prompt
        prompt = self.prompt_builder.build_pr_analysis_prompt(pr_data, language)
        
        # Prepare result structure
        result = {
            "repository": repo,
            "pr_number": pr_number,
            "language": language,
            "language_name": get_language_name(language),
            "prompt": prompt
        }
        
        # In dry run mode, just return the prompt without calling API
        if dry_run:
            logger.info(f"Dry run mode: Not calling LLM API for {repo}#{pr_number} in {language}")
            result["analysis"] = f"# {get_language_name(language)}\n\n[Dry run mode: This is a placeholder for the actual analysis]"
            return result
        
        # Call LLM API to generate analysis
        logger.info(f"Generating analysis for {repo}#{pr_number} in {language}")
        try:
            analysis = self.provider.get_completion(prompt)
            result["analysis"] = analysis
            
            # Get analysis directory for saving MD files
            analysis_dir = config_manager.get_analysis_dir()
            
            # Save analysis to file if output directory is provided
            if output_dir:
                # Save analysis as markdown file in analysis_dir
                analysis_path = generate_output_path(analysis_dir, repo, pr_number, "md", language)
                save_text(analysis, analysis_path)
                result["analysis_path"] = str(analysis_path)
                
                # Save diff if requested (in analysis_dir instead of output_dir)
                if save_diff:
                    diff = pr_data.get("diff", "")
                    if diff:
                        diff_path = generate_output_path(analysis_dir, repo, pr_number, "patch", language)
                        save_text(diff, diff_path)
                        result["diff_path"] = str(diff_path)
            
            return result
            
        except Exception as e:
            logger.error(f"Error generating analysis: {e}")
            result["error"] = str(e)
            return result
    
    def analyze_pr_from_file(self, json_file_path: Union[str, Path], language: str = "en",
                            output_dir: Optional[Path] = None, save_diff: bool = False,
                            dry_run: bool = False) -> Dict[str, Any]:
        """
        Analyze PR from a JSON file
        
        Args:
            json_file_path: Path to PR JSON file
            language: Output language code
            output_dir: Output directory (optional)
            save_diff: Whether to save PR diff as a separate file
            dry_run: If True, don't actually call LLM API
            
        Returns:
            dict: Analysis result
        """
        # Load PR data from file
        try:
            pr_data = load_json(json_file_path)
        except Exception as e:
            logger.error(f"Error loading PR data from {json_file_path}: {e}")
            raise
        
        # Use output directory from file path if not provided
        if not output_dir:
            file_path = Path(json_file_path)
            output_dir = file_path.parent
        
        # Analyze PR
        return self.analyze_pr(pr_data, language, output_dir, save_diff, dry_run)
    
    def analyze_pr_from_repo(self, repo: str, pr_number: Union[int, str], language: str = "en",
                            output_dir: Optional[Path] = None, save_diff: bool = False,
                            dry_run: bool = False) -> Dict[str, Any]:
        """
        Analyze PR from repository and PR number
        
        Args:
            repo: Repository name
            pr_number: PR number
            language: Output language code
            output_dir: Output directory (optional)
            save_diff: Whether to save PR diff as a separate file
            dry_run: If True, don't actually call LLM API
            
        Returns:
            dict: Analysis result
        """
        # Use output directory from config if not provided
        if not output_dir:
            output_dir = config_manager.get_output_dir()
        
        # Find PR JSON file
        pr_json_file = self._find_pr_json_file(output_dir, repo, pr_number)
        
        if not pr_json_file:
            raise FileNotFoundError(f"PR JSON file not found for {repo}#{pr_number}")
        
        # Analyze PR from file
        return self.analyze_pr_from_file(pr_json_file, language, output_dir, save_diff, dry_run)
    
    def _find_pr_json_file(self, base_dir: Path, repo: str, pr_number: Union[int, str]) -> Optional[Path]:
        """
        Find the latest PR JSON file for a given PR number
        
        Args:
            base_dir: Base output directory
            repo: Repository name
            pr_number: PR number
            
        Returns:
            Optional[Path]: Path to the PR JSON file or None if not found
        """
        # Extract repo name from owner/repo format
        repo_name = repo.split('/')[-1]
        
        # Look in all month directories
        repo_dir = base_dir / repo_name
        if not repo_dir.exists():
            return None
        
        # Find all month directories
        month_dirs = [d for d in repo_dir.iterdir() if d.is_dir()]
        
        # Search each month directory from newest to oldest
        for month_dir in sorted(month_dirs, reverse=True):
            # Look for PR JSON files
            json_files = list(month_dir.glob(f"pr_{pr_number}_*.json"))
            
            if json_files:
                # Sort by file modification time, newest first
                return sorted(json_files, key=lambda x: x.stat().st_mtime, reverse=True)[0]
        
        return None

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
                args.dry_run
            )
        else:
            result = analyzer.analyze_pr_from_repo(
                args.repo, 
                args.pr, 
                args.language, 
                output_dir, 
                args.save_diff,
                args.dry_run
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
