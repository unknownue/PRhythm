#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
update_pr_reports.py - Automatically update PR analysis reports

This script automatically performs the following steps:
1. Check and update repositories
2. Get unsynchronized PRs
3. Get PR detailed information
4. Analyze PRs and generate reports
5. Update processing status

This is a Python equivalent of the update_pr_reports.sh bash script.

Usage:
    python update_pr_reports.py                  # Run once
    python update_pr_reports.py --schedule 3600  # Run every hour (3600 seconds)
"""

import os
import sys
import json
import time
import subprocess
import re
import glob
import argparse
from pathlib import Path
from datetime import datetime
import importlib.util
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    datefmt='%H:%M:%S',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('update_pr_reports.log')
    ]
)
logger = logging.getLogger('update_pr_reports')

def parse_arguments():
    """
    Parse command line arguments
    
    Returns:
        argparse.Namespace: Parsed arguments
    """
    parser = argparse.ArgumentParser(description='Update PR reports automatically')
    parser.add_argument(
        '--schedule', 
        type=int, 
        help='Schedule interval in seconds. If provided, the script will run periodically at this interval. If not provided, the script will run once and exit.'
    )
    return parser.parse_args()

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
            config = json.load(file)
            return config
    except Exception as e:
        logger.error(f"Error reading configuration file: {e}")
        return None

def get_repositories_from_config(config):
    """
    Extract repository list from configuration
    
    Args:
        config: Configuration dictionary
        
    Returns:
        list: List of repositories
    """
    if not config or 'github' not in config or 'repositories' not in config['github']:
        logger.error("No repositories found in configuration")
        return []
    
    return config['github']['repositories']

def get_output_language_from_config(config):
    """
    Get output language from configuration
    
    Args:
        config: Configuration dictionary
        
    Returns:
        str: Output language code or "multilingual" if multiple languages are configured
    """
    if not config or 'output' not in config or 'languages' not in config['output']:
        logger.warning("Output languages not specified in config.json, defaulting to English (en)")
        return "en"
    
    languages = config['output']['languages']
    if not languages:
        logger.warning("Empty languages list in config.json, defaulting to English (en)")
        return "en"
    
    if len(languages) > 1:
        logger.info(f"Multiple languages configured in config.json: {', '.join(languages)}")
        return "multilingual"
    else:
        language = languages[0]
        logger.info(f"Using output language from config.json: {language}")
        return language

def get_provider_from_config(config):
    """
    Get LLM provider from configuration
    
    Args:
        config: Configuration dictionary
        
    Returns:
        str: Provider name
    """
    if not config or 'llm' not in config or 'provider' not in config['llm']:
        logger.warning("LLM provider not specified in config.json, defaulting to DeepSeek")
        return "deepseek"
    
    provider = config['llm']['provider']
    logger.info(f"Using LLM provider from config.json: {provider}")
    return provider

def run_script(script_path, *args):
    """
    Run a Python script with arguments
    
    Args:
        script_path: Path to the script
        *args: Arguments to pass to the script
        
    Returns:
        tuple: (return_code, stdout, stderr)
    """
    cmd = [sys.executable, str(script_path)] + list(args)
    process = subprocess.Popen(
        cmd, 
        stdout=subprocess.PIPE, 
        stderr=subprocess.PIPE,
        text=True
    )
    stdout, stderr = process.communicate()
    return process.returncode, stdout, stderr

def import_script(script_path):
    """
    Import a Python script as a module
    
    Args:
        script_path: Path to the script
        
    Returns:
        module: Imported module
    """
    script_name = os.path.basename(script_path).replace('.py', '')
    spec = importlib.util.spec_from_file_location(script_name, script_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def extract_pr_numbers(output):
    """
    Extract PR numbers from track_merged_prs.py output
    
    Args:
        output: Output string from track_merged_prs.py
        
    Returns:
        list: List of PR numbers
    """
    pr_numbers = []
    for line in output.splitlines():
        match = re.match(r'^#(\d+) - ', line)
        if match:
            pr_numbers.append(match.group(1))
    return pr_numbers

def find_pr_json_file(repo_name, pr_number, config):
    """
    Find the latest PR JSON file for a given PR number
    
    Args:
        repo_name: Repository name
        pr_number: PR number
        config: Configuration dictionary
        
    Returns:
        str: Path to the PR JSON file or None if not found
    """
    # Get output directory from config or use default
    output_base_dir = config.get('paths', {}).get('output_dir', './output')
    
    # Remove leading ./ if present
    if output_base_dir.startswith('./'):
        output_base_dir = output_base_dir[2:]
    
    # Get current year-month
    current_month = datetime.now().strftime("%Y-%m")
    
    # First search in the monthly directory
    monthly_pattern = f"{output_base_dir}/{repo_name}/{current_month}/pr_{pr_number}_*.json"
    monthly_files = glob.glob(monthly_pattern)
    
    if monthly_files:
        # Sort by modification time (newest first)
        return sorted(monthly_files, key=os.path.getmtime, reverse=True)[0]
    
    # If not found in monthly directory, search in main directory
    main_pattern = f"{output_base_dir}/{repo_name}/pr_{pr_number}_*.json"
    main_files = glob.glob(main_pattern)
    
    if main_files:
        # Sort by modification time (newest first)
        return sorted(main_files, key=os.path.getmtime, reverse=True)[0]
    
    return None

def update_pr_reports():
    """Process PR reports update workflow"""
    # Get project root directory
    project_root = Path(__file__).resolve().parent.parent
    os.chdir(project_root)
    
    logger.info("===== PR Analysis Update Started %s =====", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    
    # 1. Check and update repositories
    logger.info("1. Checking and updating repositories...")
    check_pull_repo_script = project_root / "scripts" / "check_pull_repo.py"
    returncode, stdout, stderr = run_script(check_pull_repo_script)
    if returncode != 0:
        logger.error("Failed to check and update repositories: %s", stderr)
        return 1
    
    # 2. Read configuration
    config_path = project_root / "config.json"
    config = read_config(config_path)
    if not config:
        logger.error("Failed to read configuration")
        return 1
    
    # Get repositories from config
    logger.info("2. Getting configured repository list...")
    repositories = get_repositories_from_config(config)
    if not repositories:
        logger.error("No repositories found in configuration")
        return 1
    
    # Get output language from config
    output_language = get_output_language_from_config(config)
    
    # Get default provider from config
    default_provider = get_provider_from_config(config)
    
    # Process each repository
    for repo in repositories:
        logger.info("===== Processing repository: %s =====", repo)
        
        # 3. Get unsynchronized PRs
        logger.info("3. Getting unsynchronized PRs...")
        track_merged_prs_script = project_root / "scripts" / "track_merged_prs.py"
        returncode, stdout, stderr = run_script(track_merged_prs_script, "--repo", repo)
        
        if returncode != 0:
            logger.error("Failed to get unsynchronized PRs: %s", stderr)
            continue
        
        # Extract PR numbers
        pr_numbers = extract_pr_numbers(stdout)
        logger.info("Found %d unsynchronized PRs", len(pr_numbers))
        
        if not pr_numbers:
            logger.info("No PRs to process, continuing to next repository")
            continue
        
        # 4. Process each unsynchronized PR
        for pr_number in pr_numbers:
            if not pr_number:
                continue
                
            logger.info("")
            logger.info("===== Processing PR #%s =====", pr_number)
            
            # 5. Get PR information
            logger.info("5. Getting PR detailed information...")
            fetch_pr_info_script = project_root / "scripts" / "fetch_pr_info.py"
            returncode, stdout, stderr = run_script(fetch_pr_info_script, "--repo", repo, "--pr", pr_number)
            
            if returncode != 0:
                logger.error("Failed to fetch PR information: %s", stderr)
                continue
            
            # Get the latest PR information JSON file
            repo_name = repo.split("/")[1] if "/" in repo else repo
            pr_json = find_pr_json_file(repo_name, pr_number, config)
            
            if not pr_json:
                logger.error("Error: Cannot find JSON file for PR #%s, skipping analysis", pr_number)
                continue
            
            logger.info("Found PR information file: %s", pr_json)
            
            # 6. Analyze PR using configured language and provider
            logger.info("6. Analyzing PR #%s and generating report in %s language using %s provider...", 
                       pr_number, output_language, default_provider)
            analyze_pr_script = project_root / "scripts" / "analyze_pr.py"
            returncode, stdout, stderr = run_script(
                analyze_pr_script, 
                "--json", pr_json, 
                "--language", output_language,
                "--provider", default_provider
            )
            
            # Check if analysis was successful
            if returncode == 0:
                # 7. Update processing status
                logger.info("7. Updating PR processing status...")
                returncode, stdout, stderr = run_script(
                    track_merged_prs_script,
                    "--repo", repo,
                    "--update",
                    "--operation", "analysis_complete",
                    "--status", "success"
                )
                logger.info("PR #%s analysis completed", pr_number)
            else:
                logger.error("PR #%s analysis failed: %s", pr_number, stderr)
                returncode, stdout, stderr = run_script(
                    track_merged_prs_script,
                    "--repo", repo,
                    "--update",
                    "--operation", "analysis_complete",
                    "--status", "failure"
                )
            
            # Optional: Add delay to avoid API rate limits
            logger.info("Waiting 5 seconds before processing next PR...")
            logger.info("")
            time.sleep(5)
    
    logger.info("===== PR Analysis Update Completed %s =====", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    return 0

def main():
    """Main function to update PR reports"""
    args = parse_arguments()
    
    if args.schedule:
        logger.info("Running in scheduled mode with interval of %d seconds", args.schedule)
        try:
            while True:
                update_pr_reports()
                logger.info("Waiting for next scheduled run in %d seconds...", args.schedule)
                time.sleep(args.schedule)
        except KeyboardInterrupt:
            logger.info("Scheduled updates interrupted by user")
            return 0
    else:
        logger.info("Running in one-time mode")
        return update_pr_reports()

if __name__ == "__main__":
    sys.exit(main()) 