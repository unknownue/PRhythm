#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Fetch PR information using GitHub CLI (gh) and store it as JSON in the output directory.
This script requires the GitHub CLI to be installed and authenticated.
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

# Import common utilities
from common import (
    read_config,
    ensure_directory,
    run_command,
    get_project_root,
    setup_logging,
    validate_repo_url,
    save_json,
    retry_operation
)

# Setup logger
logger = setup_logging("fetch_pr_info")

def ensure_output_dir(project_root, repo, config):
    """
    Ensure the output directory exists for the specific repository
    
    Args:
        project_root: Project root directory
        repo: Repository name (owner/repo)
        config: Configuration dictionary
        
    Returns:
        Path: Path to the repository-specific output directory
    """
    # Get output directory from config or use default
    output_base_dir = config.get('paths', {}).get('output_dir', './output')
    
    # Convert relative path to absolute if needed
    if output_base_dir.startswith('./') or output_base_dir.startswith('../'):
        output_dir = project_root / output_base_dir.lstrip('./')
    else:
        output_dir = Path(output_base_dir)
    
    # Create main output directory if it doesn't exist
    ensure_directory(output_dir)
    
    # Extract repo name from owner/repo format
    repo_name = repo.split('/')[-1]
    
    # Get current date for month-based directory
    month_dir = datetime.now().strftime('%Y-%m')  # Format: YYYY-MM
    
    # Create repository-specific directory with month subdirectory
    repo_output_dir = output_dir / repo_name / month_dir
    ensure_directory(repo_output_dir)
    
    return repo_output_dir

def fetch_pr_info(repo, pr_number):
    """
    Fetch PR information using GitHub CLI
    
    Args:
        repo: Repository name (owner/repo)
        pr_number: PR number
        
    Returns:
        dict: PR information
    """
    try:
        # Fetch basic PR info - removed commits and comments from the JSON fields
        cmd = f"gh pr view {pr_number} --repo {repo} --json number,title,url,state,author,createdAt,mergedAt,mergedBy,body,files,reviews"
        result = run_command(cmd)
        pr_data = json.loads(result.stdout)
        
        # Remove content from reviews fields, set to empty list
        if 'reviews' in pr_data:
            pr_data['reviews'] = []
        
        # Fetch PR diff
        cmd_diff = f"gh pr diff {pr_number} --repo {repo}"
        result_diff = run_command(cmd_diff)
        pr_data["diff"] = result_diff.stdout
        
        # Fetch PR checks
        cmd_checks = f"gh pr checks {pr_number} --repo {repo} --json checkSuites,statusCheckRollup"
        try:
            result_checks = run_command(cmd_checks)
            pr_data["checks"] = json.loads(result_checks.stdout)
        except Exception:
            # Some PRs might not have checks
            pr_data["checks"] = None
        
        # Add metadata
        pr_data["fetched_at"] = datetime.now().isoformat()
        pr_data["repository"] = repo
        
        return pr_data
    except Exception as e:
        logger.error(f"Error fetching PR information: {e}")
        raise

def save_pr_info(output_dir, repo, pr_number, pr_data):
    """
    Save PR information to a JSON file
    
    Args:
        output_dir: Output directory
        repo: Repository name
        pr_number: PR number
        pr_data: PR information
        
    Returns:
        Path: Path to the saved file
    """
    # Get current date for consistent timestamp
    current_date = datetime.now()
    date_str = current_date.strftime('%Y%m%d')
    
    # Create a base filename without the repo part since it's already in the directory structure
    base_filename = f"pr_{pr_number}_{date_str}"
    
    # Check if files with the base name already exist
    existing_files = list(output_dir.glob(f"{base_filename}*.json"))
    
    if not existing_files:
        # First file - use base filename
        filename = f"{base_filename}.json"
    else:
        # Subsequent files - add number starting from 1
        next_number = 1
        filename = f"{base_filename}_{next_number}.json"
        
        # Find a unique filename
        while output_dir / filename in existing_files:
            next_number += 1
            filename = f"{base_filename}_{next_number}.json"
    
    file_path = output_dir / filename
    
    return save_json(pr_data, file_path)

def analyze_key_commits(pr_data):
    """
    Analyze key commits in the PR
    
    Args:
        pr_data: PR data
        
    Returns:
        str: Key commit analysis
    """
    # We no longer fetch commits data, so return a simple message
    return "Commit information is not available as commits data is not fetched."

def fetch_module_context(pr_data, repo_path=None):
    """
    Fetch relevant code from affected modules to provide context for LLM analysis
    
    Args:
        pr_data: PR data
        repo_path: Path to local repository clone (optional)
        
    Returns:
        dict: Module context information
    """
    # Extract file paths to understand affected modules
    file_paths = [file.get('filename', file.get('path', '')) for file in pr_data.get('files', [])]
    
    # Group files by directory to identify modules
    modules = {}
    for path in file_paths:
        if not path:
            continue
        parts = path.split('/')
        if len(parts) > 1:
            module = parts[0]
            if module not in modules:
                modules[module] = []
            modules[module].append(path)
    
    # If no modules identified, return empty context
    if not modules:
        return {"modules": {}, "summary": "No clear module structure identified"}
    
    # Prepare context for each module
    module_context = {"modules": {}}
    
    for module, files in modules.items():
        # Skip if module is common non-code directories
        if module.lower() in ['docs', 'tests', 'test', 'examples', '.github']:
            continue
            
        # Get key files from the module (not modified in this PR)
        key_files = fetch_key_module_files(module, files, repo_path, pr_data)
        
        # Get module structure
        module_structure = analyze_module_structure(module, key_files, repo_path)
        
        # Store module context
        module_context["modules"][module] = {
            "modified_files": files,
            "key_files": key_files,
            "structure": module_structure
        }
    
    # Generate summary
    module_context["summary"] = f"Fetched context for {len(module_context['modules'])} modules: " + \
                               ", ".join(module_context["modules"].keys())
    
    return module_context

def fetch_key_module_files(module, modified_files, repo_path, pr_data):
    """
    Fetch key files from a module to provide context
    
    Args:
        module: Module name
        modified_files: Files modified in the PR
        repo_path: Path to local repository clone
        pr_data: PR data
        
    Returns:
        dict: Key files with their content
    """
    key_files = {}
    repo = pr_data.get('repository', '')
    
    # Try to find key files in the module
    try:
        # If repo_path is provided, use local filesystem
        if repo_path:
            module_path = Path(repo_path) / module
            if module_path.exists() and module_path.is_dir():
                # Look for key files like __init__.py, README.md, etc.
                for key_file in ['__init__.py', 'README.md', 'main.py', 'index.js', 'setup.py']:
                    file_path = module_path / key_file
                    if file_path.exists() and file_path.is_file():
                        with open(file_path, 'r') as f:
                            key_files[f"{module}/{key_file}"] = f.read()
        
        # If no repo_path or no files found, try using GitHub API via gh CLI
        if not key_files and repo:
            # Try to get __init__.py or similar key files
            for key_file in ['__init__.py', 'README.md', 'main.py', 'index.js', 'setup.py']:
                file_path = f"{module}/{key_file}"
                try:
                    cmd = f"gh api repos/{repo}/contents/{file_path} --jq .content | base64 -d"
                    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                    if result.returncode == 0 and result.stdout:
                        key_files[file_path] = result.stdout
                except:
                    pass
            
            # If still no files found, try to list directory and get a few files
            if not key_files:
                try:
                    cmd = f"gh api repos/{repo}/contents/{module} --jq '.[].name'"
                    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                    if result.returncode == 0 and result.stdout:
                        files = result.stdout.strip().split('\n')
                        # Filter for likely code files
                        code_files = [f for f in files if f.endswith(('.py', '.js', '.ts', '.java', '.c', '.cpp', '.go'))]
                        # Take up to 2 code files
                        for file in code_files[:2]:
                            file_path = f"{module}/{file}"
                            try:
                                cmd = f"gh api repos/{repo}/contents/{file_path} --jq .content | base64 -d"
                                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                                if result.returncode == 0 and result.stdout:
                                    key_files[file_path] = result.stdout
                            except:
                                pass
                except:
                    pass
    except Exception as e:
        print(f"Warning: Error fetching key files for module {module}: {e}")
    
    return key_files

def analyze_module_structure(module, key_files, repo_path):
    """
    Analyze the structure of a module
    
    Args:
        module: Module name
        key_files: Key files in the module
        repo_path: Path to local repository clone
        
    Returns:
        dict: Module structure information
    """
    # Extract imports and dependencies from key files
    imports = []
    classes = []
    functions = []
    
    for file_path, content in key_files.items():
        # Extract imports
        import_matches = re.findall(r'^(?:import|from)\s+([^\s;]+)', content, re.MULTILINE)
        imports.extend(import_matches)
        
        # Extract classes
        class_matches = re.findall(r'^class\s+([^\s(:]+)', content, re.MULTILINE)
        classes.extend(class_matches)
        
        # Extract functions
        function_matches = re.findall(r'^def\s+([^\s(]+)', content, re.MULTILINE)
        functions.extend(function_matches)
    
    # Remove duplicates
    imports = list(set(imports))
    classes = list(set(classes))
    functions = list(set(functions))
    
    return {
        "imports": imports[:10],  # Limit to top 10
        "classes": classes[:10],  # Limit to top 10
        "functions": functions[:10],  # Limit to top 10
    }

def format_module_context(module_context):
    """
    Format module context for inclusion in the prompt
    
    Args:
        module_context: Module context information
        
    Returns:
        str: Formatted module context
    """
    if not module_context or not module_context.get('modules'):
        return "No module context available."
    
    formatted_sections = []
    
    for module_name, module_data in module_context.get('modules', {}).items():
        section = [f"### Module: {module_name}"]
        
        # Add structure information
        structure = module_data.get('structure', {})
        if structure:
            if structure.get('classes'):
                section.append(f"**Classes**: {', '.join(structure.get('classes', []))}")
            if structure.get('functions'):
                section.append(f"**Functions**: {', '.join(structure.get('functions', []))}")
            if structure.get('imports'):
                section.append(f"**Dependencies**: {', '.join(structure.get('imports', []))}")
        
        # Add key file snippets (limited to keep prompt size reasonable)
        key_files = module_data.get('key_files', {})
        if key_files:
            section.append("\n**Key Files:**")
            for file_path, content in list(key_files.items())[:2]:  # Limit to 2 files
                # Truncate content if too long
                if len(content) > 500:
                    content = content[:500] + "...\n[content truncated]"
                section.append(f"\n`{file_path}`:\n```\n{content}\n```")
        
        formatted_sections.append("\n".join(section))
    
    return "\n\n".join(formatted_sections)

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Fetch PR information using GitHub CLI')
    parser.add_argument('--repo', type=str, required=True, 
                        help='Repository name in owner/repo format or GitHub URL')
    parser.add_argument('--pr', type=int, required=True, 
                        help='PR number')
    parser.add_argument('--config', type=str, default="config.json",
                        help='Path to the configuration file')
    parser.add_argument('--repo-path', type=str, 
                        help='Path to local repository clone (optional)')
    parser.add_argument('--skip-context', action='store_true', 
                        help='Skip fetching module context and file contents')
    return parser.parse_args()

def get_repo_path(repo, config=None):
    """
    Get the default repository path
    
    Args:
        repo: Repository URL
        config: Configuration data
        
    Returns:
        Path: Default repository path
    """
    # Get project root directory for repos path
    script_dir = Path(os.path.dirname(os.path.abspath(__file__)))
    project_root = script_dir.parent
    
    # Get repos directory from config or use default
    if config:
        repos_base_dir = config.get('paths', {}).get('repos_dir', './repos')
        # Convert relative path to absolute if needed
        if repos_base_dir.startswith('./') or repos_base_dir.startswith('../'):
            repos_dir = project_root / repos_base_dir.lstrip('./')
        else:
            repos_dir = Path(repos_base_dir)
    else:
        repos_dir = project_root / "repos"
    
    # Extract repo name from owner/repo format
    repo_name = repo.split('/')[-1]
    return repos_dir / repo_name

def fetch_repo_content(repo, pr_number, repo_path=None, config=None):
    """
    Fetch repository content for the PR
    
    Args:
        repo: Repository name (owner/repo)
        pr_number: PR number
        repo_path: Path to the repository (default: None)
        config: Configuration (default: None)
        
    Returns:
        dict: Repository data
    """
    default_repo_path = get_repo_path(repo, config)
    current_branch = None
    stashed_changes = False
    pr_branch_created = False
    
    try:
        # Use the existing repository if it exists
        if default_repo_path.exists():
            print(f"Using existing repository at {default_repo_path}")
            
            # Change to repository directory
            os.chdir(default_repo_path)
            
            # Get current branch
            current_branch_cmd = "git rev-parse --abbrev-ref HEAD"
            current_branch_result = subprocess.run(current_branch_cmd, shell=True, capture_output=True, text=True)
            if current_branch_result.returncode == 0:
                current_branch = current_branch_result.stdout.strip()
                print(f"Current branch before PR operations: {current_branch}")
            
            # Stash any changes if there are any
            stash_cmd = "git stash"
            stash_result = subprocess.run(stash_cmd, shell=True, capture_output=True, text=True)
            if "No local changes to save" not in stash_result.stdout and "No local changes to save" not in stash_result.stderr:
                stashed_changes = True
            
            # Try to update from remote
            update_cmd = "git fetch origin"
            update_result = subprocess.run(update_cmd, shell=True, capture_output=True, text=True)
            
            # Try to fetch the specific PR
            force_fetch = False
            try:
                # First, make sure we don't have a local PR branch with the same name
                branch_exists_cmd = f"git branch | grep pr_{pr_number}"
                branch_exists_result = subprocess.run(branch_exists_cmd, shell=True, capture_output=True)
                
                if branch_exists_result.returncode == 0:
                    # If the branch exists, check if we're already on it
                    current_branch_cmd = "git rev-parse --abbrev-ref HEAD"
                    current_branch_result = subprocess.run(current_branch_cmd, shell=True, capture_output=True, text=True)
                    
                    if current_branch_result.stdout.strip() == f"pr_{pr_number}":
                        # We're already on the PR branch, just reset it to the PR's HEAD
                        print(f"Already on PR branch pr_{pr_number}, fetching latest changes")
                        force_fetch = True
                    else:
                        # Delete the existing branch
                        delete_cmd = f"git branch -D pr_{pr_number}"
                        delete_result = subprocess.run(delete_cmd, shell=True, capture_output=True)
                
                # Fetch the PR
                if force_fetch:
                    # If we're already on the PR branch, try to fetch and reset
                    pr_fetch_cmd = f"git fetch origin pull/{pr_number}/head:pr_{pr_number} -f"
                    pr_fetch_result = subprocess.run(pr_fetch_cmd, shell=True, capture_output=True, text=True)
                    
                    if pr_fetch_result.returncode == 0:
                        # Reset to the fetched head
                        reset_cmd = "git reset --hard HEAD"
                        reset_result = subprocess.run(reset_cmd, shell=True, capture_output=True)
                    else:
                        # If force fetch failed, we'll continue with the current state
                        print("Force fetch failed, continuing with current branch state")
                else:
                    # Create a new branch for the PR
                    pr_fetch_cmd = f"git fetch origin pull/{pr_number}/head:pr_{pr_number}"
                    pr_fetch_result = subprocess.run(pr_fetch_cmd, shell=True, capture_output=True, text=True)
                    
                    if pr_fetch_result.returncode == 0:
                        pr_branch_created = True
                    else:
                        # Check for common errors
                        if "Authentication failed" in pr_fetch_result.stderr:
                            print("This appears to be an authentication issue. Please check your credentials.")
                            print("Try running 'git fetch' manually to verify authentication works.")
                        elif "Could not resolve host" in pr_fetch_result.stderr:
                            print("This appears to be a network connectivity issue.")
                        elif "couldn't find remote ref" in pr_fetch_result.stderr:
                            print(f"The PR #{pr_number} may not exist or you don't have access to it.")
                        
                        raise Exception(f"Git fetch failed with exit code: {pr_fetch_result.returncode}")
            except Exception as e:
                # If we're on the target PR branch already and force fetch failed
                if force_fetch:
                    print("Force fetch failed, but we're already on the PR branch")
                    print("Continuing with the current branch state...")
                    # We can continue since we're already on the branch
                else:
                    # Check if auth error
                    if "Authentication failed" in pr_fetch_result.stderr:
                        print("This appears to be an authentication issue. Please check your credentials.")
                        print("Try running 'git fetch' manually to verify authentication works.")
                    # Check if network error
                    elif "Could not resolve host" in pr_fetch_result.stderr:
                        print("This appears to be a network connectivity issue.")
                    # Check if ref doesn't exist
                    elif "couldn't find remote ref" in pr_fetch_result.stderr:
                        print(f"The PR #{pr_number} may not exist or you don't have access to it.")
                    
                    raise Exception(f"Git fetch failed: {str(e)}")
            
            # If we're not already on the PR branch, switch to it
            if not force_fetch:
                cmd = f"git checkout pr_{pr_number}"
                checkout_result = subprocess.run(cmd, shell=True, check=False, capture_output=True, text=True)
                if checkout_result.returncode != 0:
                    print(f"Error checking out PR branch: {checkout_result.stderr}")
                    raise Exception(f"Failed to checkout PR branch: {checkout_result.stderr}")
            
            print(f"Successfully pulled PR #{pr_number} content to {default_repo_path}")
            
            repo_data = {
                "repo_path": str(default_repo_path)
            }
            
            return repo_data
        else:
            raise Exception(f"Repository not found at {default_repo_path}")
    except Exception as e:
        print(f"Error: Failed to use existing repository at {default_repo_path}: {e}")
        raise e
    finally:
        # Always clean up, regardless of whether there was an error
        try:
            # Only restore original branch if we changed branches and know the original branch
            if current_branch and not force_fetch:
                print(f"Restoring original branch: {current_branch}")
                restore_cmd = f"git checkout {current_branch}"
                subprocess.run(restore_cmd, shell=True, capture_output=True)
            
            # Pop the stash if we created one
            if stashed_changes:
                print("Restoring stashed changes")
                pop_cmd = "git stash pop"
                subprocess.run(pop_cmd, shell=True, capture_output=True)
            
            # Delete the PR branch if we created it
            if pr_branch_created:
                print(f"Cleaning up: Deleting PR branch pr_{pr_number}")
                delete_cmd = f"git branch -D pr_{pr_number}"
                delete_result = subprocess.run(delete_cmd, shell=True, capture_output=True, text=True)
                if delete_result.returncode != 0:
                    print(f"Warning: Failed to delete PR branch: {delete_result.stderr}")
                else:
                    print(f"Successfully deleted PR branch pr_{pr_number}")
        except Exception as cleanup_error:
            print(f"Warning: Error during cleanup: {cleanup_error}")

def fetch_modified_file_contents(pr_data, repo_path):
    """
    Fetch the content of modified files to provide as code background
    
    Args:
        pr_data: PR data containing file information
        repo_path: Path to local repository clone
        
    Returns:
        dict: Dictionary mapping file paths to their content
    """
    file_contents = {}
    
    # Get list of modified files
    files = pr_data.get('files', [])
    
    for file in files:
        # Get file path
        file_path = file.get('filename', file.get('path', ''))
        if not file_path:
            continue
            
        # Skip binary files, large files, and certain file types
        if file_path.endswith(('.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico', '.woff', '.ttf', '.eot', '.bin', '.exe', '.dll', '.so', '.dylib')):
            continue
            
        # Get file content from local repository
        try:
            full_path = Path(repo_path) / file_path
            if full_path.exists() and full_path.is_file():
                # Check file size - skip if too large
                if full_path.stat().st_size > 100 * 1024:  # Skip files larger than 100KB
                    file_contents[file_path] = "File too large to include in context"
                    continue
                    
                # Read file content
                with open(full_path, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read()
                    file_contents[file_path] = content
            else:
                file_contents[file_path] = "File not found in repository"
        except Exception as e:
            file_contents[file_path] = f"Error reading file: {str(e)}"
    
    return file_contents

def main():
    """Main function"""
    # Parse command line arguments
    args = parse_arguments()
    
    # Get project root directory
    project_root = get_project_root()
    
    # Configuration file path
    config_path = project_root / args.config
    
    try:
        # Read configuration
        config = read_config(config_path)
        
        # Validate and normalize repository URL
        repo = validate_repo_url(args.repo)
        
        # Ensure output directory exists
        output_dir = ensure_output_dir(project_root, repo, config)
        
        # Fetch PR information
        logger.info(f"Fetching PR information for {repo}#{args.pr}")
        pr_data = fetch_pr_info(repo, args.pr)
        
        # Fetch repository content if necessary
        if not args.skip_context:
            # Fetch repository content for context
            repo_path = args.repo_path
            logger.info(f"Fetching repository content from {repo_path if repo_path else 'GitHub API'}")
            
            # Use retry for fetching content from remote repositories
            try:
                # Use retry operation but catch any exceptions
                repo_data = retry_operation(
                    lambda: fetch_repo_content(repo, args.pr, repo_path, config)
                )
                # Update PR data with repository content
                pr_data.update(repo_data)
                
                # add logic to fetch file contents
                if "repo_path" in pr_data and pr_data["repo_path"]:
                    logger.info(f"Fetching modified file contents from local repository")
                    try:
                        modified_file_contents = fetch_modified_file_contents(pr_data, pr_data["repo_path"])
                        pr_data["modified_file_contents"] = modified_file_contents
                        logger.info(f"Successfully fetched content for {len(modified_file_contents)} modified files")
                    except Exception as e:
                        logger.warning(f"Unable to fetch modified file contents: {e}")
                        logger.warning("Continuing without file contents")
            except Exception as e:
                logger.warning(f"Unable to fetch repository content: {e}")
                logger.warning("Continuing without repository context")
                # Make sure repo_path is at least defined in pr_data to avoid further errors
                if "repo_path" not in pr_data:
                    pr_data["repo_path"] = None
        
        # Save PR information
        file_path = save_pr_info(output_dir, repo, args.pr, pr_data)
        logger.info(f"PR information saved to {file_path}")
        
        # Print the path to the saved file for use by other scripts
        print(file_path)
        
    except Exception as e:
        logger.error(f"Error processing PR: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 