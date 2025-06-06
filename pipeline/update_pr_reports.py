#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
update_pr_reports.py - Automatically update PR analysis reports

This script automatically performs the following steps:
1. Check and update repositories
2. Get unsynchronized PRs
3. Get PR detailed information
4. Analyze PRs and generate reports (with code diff saved as patch files)
5. Update processing status

This is a Python equivalent of the update_pr_reports.sh bash script.

Features:
- Automatically fetches and analyzes new PRs
- Generates analysis reports in configured languages
- Saves PR code diffs as separate patch files for easier review
- Supports scheduled execution for continuous monitoring

Usage:
    python update_pr_reports.py                  # Run once
    python update_pr_reports.py --schedule 3600  # Run every hour (3600 seconds)
"""

import sys
import re
import glob
import argparse
import importlib.util
from pathlib import Path
from datetime import datetime
import time
import os
import csv

# Import common utilities
from common import (
    read_config,
    get_project_root,
    setup_logging,
    run_command,
    ensure_directory
)

# Setup logger
logger = setup_logging("update_pr_reports")

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
    parser.add_argument(
        '--config', 
        type=str, 
        default="config.json",
        help='Path to the configuration file'
    )
    return parser.parse_args()

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
        list: Output language codes list (never returns "multilingual")
    """
    if not config or 'output' not in config or 'languages' not in config['output']:
        logger.warning("Output languages not specified in config.json, defaulting to English (en)")
        return ["en"]
    
    languages = config['output']['languages']
    if not languages:
        logger.warning("Empty languages list in config.json, defaulting to English (en)")
        return ["en"]
    
    # Return actual language list rather than "multilingual"
    valid_languages = [lang for lang in languages if lang]
    if not valid_languages:
        logger.warning("No valid languages found in config.json, defaulting to English (en)")
        return ["en"]
        
    logger.info(f"Using output languages from config.json: {', '.join(valid_languages)}")
    return valid_languages

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

def run_script(script_path, *args, timeout=600):
    """
    Run a Python script with arguments and timeout
    
    Args:
        script_path: Path to the script
        *args: Arguments to pass to the script
        timeout: Timeout in seconds for script execution
        
    Returns:
        tuple: (return_code, stdout, stderr)
    """
    import subprocess
    
    cmd = [sys.executable, str(script_path)] + list(args)
    try:
        process = subprocess.Popen(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8'  # Explicitly use UTF-8 encoding
        )
        stdout, stderr = process.communicate(timeout=timeout)
        return process.returncode, stdout, stderr
    except subprocess.TimeoutExpired:
        # Kill the process if it times out
        process.kill()
        _, _ = process.communicate()
        logger.error(f"Script execution timed out after {timeout} seconds: {script_path}")
        return 1, "", f"Execution timed out after {timeout} seconds"

def import_script(script_path):
    """
    Import a Python script as a module
    
    Args:
        script_path: Path to the script
        
    Returns:
        module: Imported module
    """
    script_name = Path(script_path).stem
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
        return sorted(monthly_files, key=lambda f: Path(f).stat().st_mtime, reverse=True)[0]
    
    # If not found in monthly directory, search in main directory
    main_pattern = f"{output_base_dir}/{repo_name}/pr_{pr_number}_*.json"
    main_files = glob.glob(main_pattern)
    
    if main_files:
        # Sort by modification time (newest first)
        return sorted(main_files, key=lambda f: Path(f).stat().st_mtime, reverse=True)[0]
    
    return None

def record_failed_request(repo, pr_number, language, error_message):
    """
    Record failed LLM request to a local file
    
    Args:
        repo: Repository name
        pr_number: PR number
        language: Output language
        error_message: Error message
    """
    # Use logs directory in the project root to store failure records
    project_root = get_project_root()
    logs_dir = project_root / "logs"
    ensure_directory(logs_dir)
    
    # Path to the failed requests log file
    failed_requests_file = logs_dir / "failed_llm_requests.csv"
    
    # Prepare record data
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    record = [timestamp, repo, pr_number, language, error_message]
    
    # Check if file exists, if not create and add header
    file_exists = os.path.isfile(failed_requests_file)
    
    try:
        with open(failed_requests_file, mode='a', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            # If file doesn't exist, write header first
            if not file_exists:
                writer.writerow(['Timestamp', 'Repository', 'PR Number', 'Language', 'Error'])
            # Write the failure record
            writer.writerow(record)
        logger.info(f"Recorded failed LLM request for PR #{pr_number} in {language} to {failed_requests_file}")
    except Exception as e:
        logger.error(f"Failed to record failed LLM request: {str(e)}")

def update_pr_reports():
    """Process PR reports update workflow"""
    # Get project root directory
    project_root = get_project_root()
    
    logger.info("===== PR Analysis Update Started %s =====", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    
    # 1. Check and update repositories
    logger.info("1. Checking and updating repositories...")
    check_pull_repo_script = project_root / "pipeline" / "check_pull_repo.py"
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
    output_languages = get_output_language_from_config(config)
    
    # Get default provider from config
    default_provider = get_provider_from_config(config)
    
    # Process each repository
    for repo in repositories:
        logger.info("===== Processing repository: %s =====", repo)
        
        # 3. Get unsynchronized PRs
        logger.info("3. Getting unsynchronized PRs...")
        track_merged_prs_script = project_root / "pipeline" / "track_merged_prs.py"
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
            fetch_pr_script = project_root / "pipeline" / "fetch_pr_info.py"
            returncode, stdout, stderr = run_script(fetch_pr_script, "--repo", repo, "--pr", pr_number)
            
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
            analysis_success = True
            for output_language in output_languages:
                logger.info("6. Analyzing PR #%s and generating report in %s language using %s provider...", 
                           pr_number, output_language, default_provider)
                analyze_pr_script = project_root / "pipeline" / "run_pr_analysis.py"
                
                # Get analysis directory from config
                analysis_base_dir = config.get('paths', {}).get('analysis_dir', './analysis')
                
                # Ensure analysis directory exists
                analysis_dir = project_root / analysis_base_dir.lstrip('./')
                
                # Handle symlinks in Docker environment
                try:
                    # Check if it's a symlink
                    if os.path.islink(analysis_dir):
                        # Get the target of the symlink
                        link_target = os.readlink(analysis_dir)
                        logger.info("Analysis directory is a symlink pointing to: %s", link_target)
                        
                        # If relative path, make it absolute
                        if not os.path.isabs(link_target):
                            link_target = os.path.normpath(os.path.join(os.path.dirname(str(analysis_dir)), link_target))
                        
                        # Use the target directory instead
                        analysis_dir = Path(link_target)
                        logger.info("Using symlink target as analysis directory: %s", analysis_dir)
                    
                    # Check if path exists but is not a directory
                    if os.path.exists(analysis_dir) and not os.path.isdir(analysis_dir):
                        logger.warning("Path %s exists but is not a directory. Removing it...", analysis_dir)
                        os.remove(analysis_dir)
                    
                    # Create the directory
                    os.makedirs(analysis_dir, exist_ok=True)
                except Exception as e:
                    logger.error("Error handling analysis directory: %s", str(e))
                    # Fallback to a directory we know should work in Docker
                    analysis_dir = Path("/tmp/prhythm_analysis")
                    os.makedirs(analysis_dir, exist_ok=True)
                    logger.warning("Using fallback analysis directory: %s", analysis_dir)
                
                # Run analyze_pr.py with explicit config path
                max_retries = 2  # Maximum retry attempts
                retry_count = 0
                execute_success = False
                
                while retry_count <= max_retries and not execute_success:
                    if retry_count > 0:
                        logger.info("Retry attempt %d for PR #%s in %s language...", 
                                    retry_count, pr_number, output_language)
                    
                    returncode, stdout, stderr = run_script(
                        analyze_pr_script, 
                        "--json", pr_json, 
                        "--language", output_language,
                        "--config", str(config_path),
                        "--save-diff"
                    )
                    
                    # Check if execution was successful
                    if returncode == 0:
                        execute_success = True
                    # Check if it's a timeout error
                    elif "timed out" in stderr.lower():
                        retry_count += 1
                        if retry_count <= max_retries:
                            logger.warning("LLM request timed out. Retrying (%d/%d)...", 
                                           retry_count, max_retries)
                            # Add a short delay before retrying
                            time.sleep(3)
                        else:
                            logger.error("LLM request timed out after %d retries. Giving up.", max_retries)
                            # Record the failed request information
                            record_failed_request(repo, pr_number, output_language, f"Timeout after {max_retries} retries")
                            break
                    else:
                        # Other errors, no retry
                        logger.error("Failed to analyze PR with error: %s", stderr)
                        # Record the failed request information
                        record_failed_request(repo, pr_number, output_language, stderr)
                        break
                
                # Check if analysis was successful
                if execute_success:
                    # Extract the saved report path from stdout
                    report_path_match = re.search(r"Saved analysis report: (.+\.md)", stdout)
                    
                    if report_path_match:
                        report_path = report_path_match.group(1)
                        logger.info("Generated report saved to: %s", report_path)
                else:
                    logger.error("Failed to analyze PR #%s in %s language: %s", pr_number, output_language, stderr)
                    analysis_success = False
            
            # 7. Update processing status (after all languages are processed)
            logger.info("7. Updating PR processing status...")
            if analysis_success:
                returncode, stdout, stderr = run_script(
                    track_merged_prs_script,
                    "--repo", repo,
                    "--update",
                    "--operation", "analysis_complete",
                    "--status", "success"
                )
                logger.info("PR #%s analysis completed", pr_number)
            else:
                logger.error("PR #%s analysis failed for one or more languages", pr_number)
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
    """Main function"""
    args = parse_arguments()
    
    # Get project root directory
    project_root = get_project_root()
    
    # Ensure logs directory exists
    logs_dir = project_root / "logs"
    ensure_directory(logs_dir)
    
    # Configuration file path
    config_path = project_root / args.config
    
    try:
        # Read configuration
        config = read_config(config_path)
        
        if args.schedule:
            logger.info("Running in scheduled mode (interval: %d seconds)", args.schedule)
            
            while True:
                update_pr_reports()
                logger.info("Sleeping for %d seconds before next run...", args.schedule)
                time.sleep(args.schedule)
        else:
            logger.info("Running in single-execution mode")
            update_pr_reports()
            
    except KeyboardInterrupt:
        logger.info("Process interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error("Error in main function: %s", e)
        sys.exit(1)

if __name__ == "__main__":
    main() 