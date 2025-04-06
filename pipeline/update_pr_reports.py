#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
update_pr_reports.py - Automatically update PR analysis reports

This script automatically performs the following steps:
1. Check and update repositories
2. Get unsynchronized PRs
3. Get PR detailed information using GitHub CLI
4. Extract relevant context from local repository
5. Analyze PRs and generate reports with extracted context
6. Update processing status

This is a Python equivalent of the update_pr_reports.sh bash script.

Features:
- Automatically fetches and analyzes new PRs
- Extracts relevant code context to improve analysis quality and reduce token usage
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
import json

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
    parser.add_argument(
        '--disable-context-extraction',
        action='store_true',
        help='Disable smart context extraction (enabled by default)'
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

def extract_context_from_pr(pr_json_path, repo_path, project_root, config):
    """
    Extract context from PR using extract_context.py
    
    Args:
        pr_json_path: Path to PR JSON file
        repo_path: Path to local repository
        project_root: Project root directory
        config: Configuration dictionary
        
    Returns:
        dict: Extracted context or None if extraction failed
    """
    logger.info("🔍 Extracting context from PR...")
    
    try:
        # Load PR JSON
        with open(pr_json_path, 'r') as f:
            pr_data = json.load(f)
        
        # Get PR number and diff
        pr_number = pr_data.get('number')
        diff_content = pr_data.get('diff')
        
        if not pr_number or not diff_content:
            logger.error("❌ PR JSON file missing number or diff")
            return None
        
        # Get provider information from config
        provider_name = config.get('llm', {}).get('provider', 'openai')
        provider_config = config.get('llm', {}).get('providers', {}).get(provider_name, {})
        model = provider_config.get('model', 'gpt-4-turbo')
        logger.info(f"Using {provider_name} provider with {model} model for context extraction")
        
        # Prepare temp file for diff
        import tempfile
        temp_diff_file = tempfile.NamedTemporaryFile(mode='w+', suffix='.diff', delete=False)
        try:
            # Write diff content to temp file
            temp_diff_file.write(diff_content)
            temp_diff_file.close()
            
            # Run extract_context.py
            extract_context_script = project_root / "pipeline" / "extract_context.py"
            
            # Set arguments
            args = [
                "--repo-path", str(repo_path),
                "--diff-file", temp_diff_file.name,
                "--context-only",
                "--provider", provider_name
            ]
            
            # Add model if specified
            if model:
                args.extend(["--model", model])
            
            # Run the script
            returncode, stdout, stderr = run_script(extract_context_script, *args, timeout=300)
            
            if returncode != 0:
                logger.error(f"❌ Context extraction failed: {stderr}")
                return None
            
            # Parse output to find context file path
            context_file_match = re.search(r'Context saved to (.+\.json)', stdout)
            if not context_file_match:
                logger.error("❌ Could not find context file path in output")
                return None
            
            context_file = context_file_match.group(1)
            logger.info(f"📄 Context extracted to: {context_file}")
            
            # Load context
            with open(context_file, 'r') as f:
                context = json.load(f)
            
            return context
        finally:
            # Delete temp file
            try:
                os.unlink(temp_diff_file.name)
            except:
                pass
    except Exception as e:
        logger.error(f"❌ Error extracting context: {str(e)}")
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

def update_pr_reports(enable_context_extraction=False):
    """Process PR reports update workflow"""
    # Get project root directory
    project_root = get_project_root()
    
    logger.info("🚀 ===== PR Analysis Update Started %s =====", datetime.now().strftime("%m-%d %H:%M"))
    
    # 1. Check and update repositories
    logger.info("📂 Checking repositories...")
    check_pull_repo_script = project_root / "pipeline" / "check_pull_repo.py"
    returncode, stdout, stderr = run_script(check_pull_repo_script)
    if returncode != 0:
        logger.error("❌ Repository check failed: %s", stderr)
        return 1
    
    # 2. Read configuration
    config_path = project_root / "config.json"
    config = read_config(config_path)
    if not config:
        logger.error("❌ Config not found")
        return 1
    
    # Get repositories from config
    logger.info("📋 Loading repository list...")
    repositories = get_repositories_from_config(config)
    if not repositories:
        logger.error("❌ No repositories in config")
        return 1
    
    # Get output language from config
    output_languages = get_output_language_from_config(config)
    
    # Get default provider from config
    default_provider = get_provider_from_config(config)
    
    # Process each repository
    for repo in repositories:
        logger.info("🔍 Processing repo: %s", repo)
        
        # 3. Get unsynchronized PRs
        logger.info("🔄 Fetching unsync PRs...")
        track_merged_prs_script = project_root / "pipeline" / "track_merged_prs.py"
        returncode, stdout, stderr = run_script(track_merged_prs_script, "--repo", repo)
        
        if returncode != 0:
            logger.error("❌ Failed to get PRs: %s", stderr)
            continue
        
        # Extract PR numbers
        pr_numbers = extract_pr_numbers(stdout)
        logger.info("📊 Found %d PRs to process", len(pr_numbers))
        
        if not pr_numbers:
            logger.info("ℹ️ No PRs to process")
            continue
        
        # Determine repository path for context extraction
        repo_name = repo.split("/")[1] if "/" in repo else repo
        repo_path = os.path.join(os.getcwd(), 'repos', repo.replace('/', '_'))
        
        # Check if repository exists (needed for context extraction)
        repo_exists = os.path.exists(repo_path) and os.path.isdir(repo_path)
        if enable_context_extraction and not repo_exists:
            logger.warning("⚠️ Local repository not found at %s, context extraction may fail", repo_path)
            # Try to find it in common locations
            for common_path in ['repositories', '.']:
                potential_path = os.path.join(os.getcwd(), common_path, repo.replace('/', '_'))
                if os.path.exists(potential_path) and os.path.isdir(potential_path):
                    repo_path = potential_path
                    repo_exists = True
                    logger.info("✅ Found repository at %s", repo_path)
                    break
        
        # 4. Process each unsynchronized PR
        for pr_number in pr_numbers:
            if not pr_number:
                continue
                
            logger.info("")
            logger.info("🔎 PR #%s", pr_number)
            
            # 5. Fetch PR information
            logger.info("📥 Fetching PR details...")
            fetch_pr_info_script = project_root / "pipeline" / "fetch_pr_info.py"
            returncode, stdout, stderr = run_script(fetch_pr_info_script, "--repo", repo, "--pr", pr_number)
            
            if returncode != 0:
                logger.error("❌ PR info fetch failed: %s", stderr)
                continue
            
            # Get the latest PR information JSON file
            pr_json = find_pr_json_file(repo_name, pr_number, config)
            
            if not pr_json:
                logger.error("❌ PR JSON file not found for #%s", pr_number)
                continue
            
            logger.info("📄 PR info: %s", pr_json)
            
            # 6. Extract context if enabled
            context = None
            if enable_context_extraction and repo_exists:
                logger.info("🧩 Extracting PR context...")
                context = extract_context_from_pr(pr_json, repo_path, project_root, config)
                
                if context:
                    logger.info("✅ Context extraction successful")
                    
                    # Update PR JSON with extracted context
                    try:
                        with open(pr_json, 'r') as f:
                            pr_data = json.load(f)
                        
                        # Add context to PR data
                        pr_data['context'] = context
                        
                        # Save updated PR data
                        with open(pr_json, 'w') as f:
                            json.dump(pr_data, f, indent=2)
                            
                        logger.info("✅ PR JSON updated with context")
                    except Exception as e:
                        logger.error(f"❌ Error updating PR JSON with context: {str(e)}")
                else:
                    logger.warning("⚠️ Context extraction failed, proceeding without context")
            
            # 7. Analyze PR using configured language and provider
            analysis_success = True
            for output_language in output_languages:
                logger.info("🔬 Analyzing PR #%s and generating report in %s language using %s provider...", 
                           pr_number, output_language, default_provider)
                analyze_pr_script = project_root / "pipeline" / "analyze_pr.py"
                
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
                
                # Prepare analyze_pr.py arguments
                analyze_args = [
                    "--json", pr_json, 
                    "--language", output_language,
                    "--config", str(config_path),
                    "--save-diff"
                ]
                
                # Add context extraction args if context was successfully extracted
                if enable_context_extraction and context:
                    analyze_args.append("--extract-context")
                    if repo_exists:
                        analyze_args.extend(["--local-repo-path", str(repo_path)])
                
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
                        *analyze_args
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
                    report_path_match = re.search(r"Analysis saved to: (.+\.md)", stdout)
                    
                    if report_path_match:
                        report_path = report_path_match.group(1)
                        logger.info("Generated report saved to: %s", report_path)
                else:
                    logger.error("Failed to analyze PR #%s in %s language: %s", pr_number, output_language, stderr)
                    analysis_success = False
            
            # 8. Update processing status (after all languages are processed)
            logger.info("✅ Updating PR status...")
            if analysis_success:
                returncode, stdout, stderr = run_script(
                    track_merged_prs_script,
                    "--repo", repo,
                    "--update",
                    "--operation", "analysis_complete",
                    "--status", "success"
                )
                logger.info("✨ PR #%s analysis completed", pr_number)
            else:
                logger.error("❌ PR #%s analysis failed", pr_number)
                returncode, stdout, stderr = run_script(
                    track_merged_prs_script,
                    "--repo", repo,
                    "--update",
                    "--operation", "analysis_complete",
                    "--status", "failure"
                )
            
            # Optional: Add delay to avoid API rate limits
            logger.info("⏱️ Waiting 5s before next PR...")
            logger.info("")
            time.sleep(5)
    
    logger.info("🏁 ===== PR Analysis Completed %s =====", datetime.now().strftime("%m-%d %H:%M"))
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
        
        # Check if context extraction is disabled via command line flag
        enable_context_extraction = True  # Default enabled
        if args.disable_context_extraction:
            enable_context_extraction = False
            logger.info("⚠️ Smart context extraction disabled via command line flag")
        else:
            logger.info("🧩 Smart context extraction enabled (default)")
        
        if args.schedule:
            logger.info("🔄 Running in scheduled mode: %ds", args.schedule)
            
            while True:
                update_pr_reports(enable_context_extraction)
                logger.info("💤 Sleeping for %ds...", args.schedule)
                time.sleep(args.schedule)
        else:
            logger.info("▶️ Running in single mode")
            update_pr_reports(enable_context_extraction)
            
    except KeyboardInterrupt:
        logger.info("🛑 Process interrupted")
        sys.exit(0)
    except Exception as e:
        logger.error("💥 Error: %s", e)
        sys.exit(1)

if __name__ == "__main__":
    main() 