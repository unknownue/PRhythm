#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Report Generator for PRhythm.
This module handles the generation of PR analysis reports.
"""

import logging
import os
import sys
import re
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional, Union

from pr_analyzer import PRAnalyzer
from utils.config_manager import config_manager
from utils.file_utils import ensure_directory, save_text, read_text
from utils.languages import get_language_name, get_supported_languages

# Setup logger
logger = logging.getLogger("report_generator")

class ReportGenerator:
    """
    Generates and manages PR analysis reports.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize report generator
        
        Args:
            config: Configuration dictionary (optional)
        """
        self.config = config or config_manager.get_full_config()
        self.pr_analyzer = PRAnalyzer(self.config)
        
        # Get configured languages
        self.languages = config_manager.get_output_languages()
    
    def generate_report(self, repo: str, pr_number: Union[int, str], 
                       languages: Optional[List[str]] = None,
                       output_dir: Optional[Path] = None,
                       save_diff: bool = False,
                       dry_run: bool = False) -> Dict[str, Any]:
        """
        Generate PR analysis reports in specified languages
        
        Args:
            repo: Repository name
            pr_number: PR number
            languages: List of language codes (default: use configured languages)
            output_dir: Output directory (optional)
            save_diff: Whether to save PR diff as a separate file
            dry_run: If True, don't actually call LLM API
            
        Returns:
            dict: Generation results
        """
        # Use configured languages if not specified
        if not languages:
            languages = self.languages
        
        # Use output directory from config if not provided
        if not output_dir:
            output_dir = config_manager.get_output_dir()
        
        # Prepare results
        results = {
            "repository": repo,
            "pr_number": pr_number,
            "languages": {},
            "success": True
        }
        
        # Generate report for each language
        for language in languages:
            try:
                logger.info(f"Generating {language} report for {repo}#{pr_number}")
                result = self.pr_analyzer.analyze_pr_from_repo(
                    repo, 
                    pr_number, 
                    language, 
                    output_dir, 
                    save_diff,
                    dry_run
                )
                
                # Store result
                results["languages"][language] = {
                    "success": "error" not in result,
                    "language_name": get_language_name(language)
                }
                
                # Add file paths if available
                if "analysis_path" in result:
                    results["languages"][language]["analysis_path"] = result["analysis_path"]
                
                if "diff_path" in result:
                    results["languages"][language]["diff_path"] = result["diff_path"]
                
                # Add error if present
                if "error" in result:
                    results["languages"][language]["error"] = result["error"]
                    results["success"] = False
                
            except Exception as e:
                logger.error(f"Error generating {language} report for {repo}#{pr_number}: {e}")
                results["languages"][language] = {
                    "success": False,
                    "language_name": get_language_name(language),
                    "error": str(e)
                }
                results["success"] = False
        
        return results
    
    def generate_multilingual_report(self, repo: str, pr_number: Union[int, str],
                                    languages: Optional[List[str]] = None,
                                    output_dir: Optional[Path] = None,
                                    save_diff: bool = False) -> Dict[str, Any]:
        """
        Generate a multilingual report combining all language versions
        
        Args:
            repo: Repository name
            pr_number: PR number
            languages: List of language codes (default: use configured languages)
            output_dir: Output directory (optional)
            save_diff: Whether to save PR diff as a separate file
            
        Returns:
            dict: Generation result
        """
        # Use configured languages if not specified
        if not languages:
            languages = self.languages
        
        # Use output directory from config if not provided
        if not output_dir:
            output_dir = config_manager.get_output_dir()
        
        # First generate individual reports
        results = self.generate_report(repo, pr_number, languages, output_dir, save_diff)
        
        # Check if all reports were generated successfully
        if not results["success"]:
            logger.warning("Not all language reports were generated successfully")
        
        # Prepare multilingual report
        multilingual_content = []
        
        # For each language, try to read the analysis
        for language in languages:
            lang_result = results["languages"].get(language, {})
            
            if lang_result.get("success", False) and "analysis_path" in lang_result:
                try:
                    # Read analysis file
                    analysis_path = lang_result["analysis_path"]
                    analysis_content = read_text(analysis_path)
                    
                    # Add to multilingual content
                    multilingual_content.append(analysis_content)
                    multilingual_content.append("\n\n---\n\n")  # Add separator
                except Exception as e:
                    logger.error(f"Error reading analysis file for {language}: {e}")
        
        # If no content, return error
        if not multilingual_content:
            results["multilingual"] = {
                "success": False,
                "error": "No language reports available to combine"
            }
            return results
        
        # Create multilingual report
        multilingual_report = "".join(multilingual_content)
        
        # Save multilingual report
        try:
            # Generate output path
            multilingual_path = self._generate_multilingual_path(output_dir, repo, pr_number)
            
            # Save report
            save_text(multilingual_report, multilingual_path)
            
            # Add to results
            results["multilingual"] = {
                "success": True,
                "report_path": str(multilingual_path)
            }
            
        except Exception as e:
            logger.error(f"Error saving multilingual report: {e}")
            results["multilingual"] = {
                "success": False,
                "error": str(e)
            }
        
        return results
    
    def _generate_multilingual_path(self, output_dir: Path, repo: str, pr_number: Union[int, str]) -> Path:
        """
        Generate path for multilingual report
        
        Args:
            output_dir: Output directory
            repo: Repository name
            pr_number: PR number
            
        Returns:
            Path: Path for multilingual report
        """
        # Extract repo name from owner/repo format
        repo_name = repo.split('/')[-1]
        
        # Find latest month directory
        repo_dir = output_dir / repo_name
        month_dirs = [d for d in repo_dir.iterdir() if d.is_dir()]
        
        if not month_dirs:
            raise FileNotFoundError(f"No month directories found for {repo}")
        
        # Use latest month directory
        latest_month_dir = sorted(month_dirs)[-1]
        
        # Generate filename
        filename = f"pr_{pr_number}_multilingual.md"
        
        return latest_month_dir / filename

def parse_arguments():
    """
    Parse command line arguments
    
    Returns:
        argparse.Namespace: Parsed arguments
    """
    parser = argparse.ArgumentParser(description='Generate PR analysis reports')
    parser.add_argument('--repo', required=True, help='Repository in owner/repo format')
    parser.add_argument('--pr', required=True, help='PR number')
    parser.add_argument('--languages', help='Comma-separated list of language codes (default: use configured languages)')
    parser.add_argument('--output-dir', help='Output directory for reports')
    parser.add_argument('--config', default='config.json', help='Path to configuration file')
    parser.add_argument('--save-diff', action='store_true', help='Save PR diff as a separate file')
    parser.add_argument('--multilingual', action='store_true', help='Generate a combined multilingual report')
    parser.add_argument('--dry-run', action='store_true', help='Dry run mode (don\'t actually call LLM API)')
    
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
        # Initialize report generator
        report_generator = ReportGenerator()
        
        # Set output directory
        output_dir = None
        if args.output_dir:
            output_dir = Path(args.output_dir)
        
        # Parse languages
        languages = None
        if args.languages:
            languages = [lang.strip() for lang in args.languages.split(",")]
        
        # Generate reports
        if args.multilingual:
            results = report_generator.generate_multilingual_report(
                args.repo,
                args.pr,
                languages,
                output_dir,
                args.save_diff
            )
            
            # Print path to multilingual report if available
            if results.get("multilingual", {}).get("success", False):
                logger.info(f"Multilingual report saved to: {results['multilingual']['report_path']}")
        else:
            results = report_generator.generate_report(
                args.repo,
                args.pr,
                languages,
                output_dir,
                args.save_diff,
                args.dry_run
            )
            
            # Print paths to reports
            for language, lang_result in results["languages"].items():
                if lang_result.get("success", False) and "analysis_path" in lang_result:
                    logger.info(f"{lang_result['language_name']} report saved to: {lang_result['analysis_path']}")
        
        # Print overall status
        if results["success"]:
            logger.info("All reports generated successfully")
        else:
            logger.warning("Some reports failed to generate")
            
    except Exception as e:
        logger.error(f"Error in report_generator: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
