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

def ensure_output_dir(project_root, repo):
    """
    Ensure the output directory exists for the specific repository
    
    Args:
        project_root: Project root directory
        repo: Repository name (owner/repo)
        
    Returns:
        Path: Path to the repository-specific output directory
    """
    # Create main output directory if it doesn't exist
    output_dir = project_root / "output"
    output_dir.mkdir(exist_ok=True)
    
    # Extract repo name from owner/repo format
    repo_name = repo.split('/')[-1]
    
    # Create repository-specific directory
    repo_output_dir = output_dir / repo_name
    repo_output_dir.mkdir(exist_ok=True)
    
    return repo_output_dir

def validate_repo_url(repo_url):
    """
    Validate and normalize the repository URL
    
    Args:
        repo_url: Repository URL or owner/repo format
        
    Returns:
        str: Repository in owner/repo format
    """
    # If it's already in owner/repo format
    if re.match(r'^[^/]+/[^/]+$', repo_url):
        return repo_url
    
    # Extract owner/repo from GitHub URL
    match = re.search(r'github\.com[:/]([^/]+/[^/]+?)(?:\.git)?/?$', repo_url)
    if match:
        return match.group(1)
    
    raise ValueError(f"Invalid repository format: {repo_url}. Expected format: owner/repo or GitHub URL")

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
        result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
        pr_data = json.loads(result.stdout)
        
        # Remove content from reviews fields, set to empty list
        if 'reviews' in pr_data:
            pr_data['reviews'] = []
        
        # Fetch PR diff
        cmd_diff = f"gh pr diff {pr_number} --repo {repo}"
        result_diff = subprocess.run(cmd_diff, shell=True, check=True, capture_output=True, text=True)
        pr_data["diff"] = result_diff.stdout
        
        # Fetch PR checks
        cmd_checks = f"gh pr checks {pr_number} --repo {repo} --json checkSuites,statusCheckRollup"
        try:
            result_checks = subprocess.run(cmd_checks, shell=True, check=True, capture_output=True, text=True)
            pr_data["checks"] = json.loads(result_checks.stdout)
        except subprocess.CalledProcessError:
            # Some PRs might not have checks
            pr_data["checks"] = None
        
        # Add metadata
        pr_data["fetched_at"] = datetime.now().isoformat()
        pr_data["repository"] = repo
        
        return pr_data
    except subprocess.CalledProcessError as e:
        print(f"Error fetching PR information: {e}")
        print(f"Error output: {e.stderr}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)

def save_pr_info(output_dir, repo, pr_number, pr_data):
    """
    Save PR information to a JSON file
    
    Args:
        output_dir: Output directory
        repo: Repository name (owner/repo)
        pr_number: PR number
        pr_data: PR information
        
    Returns:
        Path: Path to the saved file
    """
    # Create a filename without the repo part since it's already in the directory structure
    filename = f"pr_{pr_number}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    file_path = output_dir / filename
    
    try:
        with open(file_path, 'w') as file:
            json.dump(pr_data, file, indent=2)
        return file_path
    except Exception as e:
        print(f"Error saving PR information: {e}")
        sys.exit(1)

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
    parser.add_argument('--repo', required=True, help='Repository URL or owner/repo format')
    parser.add_argument('--pr', required=True, type=int, help='PR number to fetch')
    parser.add_argument('--repo-path', help='Path to local repository clone (optional, for better context)')
    return parser.parse_args()

def fetch_repo_content(repo, pr_number, repo_path=None):
    """
    Pull repository content to ensure we're analyzing the current version of the PR
    
    Args:
        repo: Repository name (owner/repo)
        pr_number: PR number
        repo_path: Local repository path (optional)
        
    Returns:
        str: Repository path used for analysis
    """
    # Get project root directory for repos path
    script_dir = Path(os.path.dirname(os.path.abspath(__file__)))
    project_root = script_dir.parent
    repos_dir = project_root / "repos"
    
    # Extract repo name from owner/repo format
    repo_name = repo.split('/')[-1]
    default_repo_path = repos_dir / repo_name
    
    # If a specific repo_path is provided, use it
    if repo_path:
        try:
            # Verify the repository exists
            if not os.path.exists(repo_path):
                print(f"Error: Repository path {repo_path} does not exist")
                sys.exit(1)
                
            # Change to the repository directory
            os.chdir(repo_path)
            
            # Get current branch
            cmd = "git branch --show-current"
            current_branch = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True).stdout.strip()
            
            # Save current state
            cmd = "git stash -u"
            subprocess.run(cmd, shell=True, capture_output=True)
            
            # Pull latest content
            cmd = "git fetch origin"
            subprocess.run(cmd, shell=True, check=True, capture_output=True)
            
            # Get PR reference
            cmd = f"git fetch origin pull/{pr_number}/head:pr_{pr_number}"
            subprocess.run(cmd, shell=True, check=True, capture_output=True)
            
            # Switch to PR branch
            cmd = f"git checkout pr_{pr_number}"
            subprocess.run(cmd, shell=True, check=True, capture_output=True)
            
            print(f"Successfully pulled PR #{pr_number} content to {repo_path}")
            return repo_path
        except Exception as e:
            print(f"Error: Failed to pull PR content to existing repo: {e}")
            sys.exit(1)
    
    # Assume repository already exists in the repos directory
    # No need to check if it exists or clone it again
    try:
        print(f"Using existing repository at {default_repo_path}")
        
        # Change to the repository directory
        os.chdir(default_repo_path)
        
        # Get current branch
        cmd = "git branch --show-current"
        current_branch = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True).stdout.strip()
        
        # Save current state
        cmd = "git stash -u"
        subprocess.run(cmd, shell=True, capture_output=True)
        
        # Pull latest content
        cmd = "git fetch origin"
        subprocess.run(cmd, shell=True, check=True, capture_output=True)
        
        # Get PR reference
        cmd = f"git fetch origin pull/{pr_number}/head:pr_{pr_number}"
        subprocess.run(cmd, shell=True, check=True, capture_output=True)
        
        # Switch to PR branch
        cmd = f"git checkout pr_{pr_number}"
        subprocess.run(cmd, shell=True, check=True, capture_output=True)
        
        print(f"Successfully pulled PR #{pr_number} content to {default_repo_path}")
        return default_repo_path
    except Exception as e:
        print(f"Error: Failed to use existing repository at {default_repo_path}: {e}")
        sys.exit(1)

def main():
    """Main function"""
    # Parse command line arguments
    args = parse_arguments()
    
    # Get project root directory
    script_dir = Path(os.path.dirname(os.path.abspath(__file__)))
    project_root = script_dir.parent
    
    # Validate and normalize repository URL
    try:
        repo = validate_repo_url(args.repo)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)
    
    # Ensure repository-specific output directory exists
    output_dir = ensure_output_dir(project_root, repo)
    
    print(f"Fetching information for PR #{args.pr} from repository {repo}...")
    
    # Pull repository content - this will exit if repository doesn't exist
    repo_path = fetch_repo_content(repo, args.pr, args.repo_path)
    
    # Fetch PR information
    pr_data = fetch_pr_info(repo, args.pr)
    
    # Fetch module context and add to PR data
    print(f"Fetching module context using repository at {repo_path}...")
    pr_data['module_context'] = fetch_module_context(pr_data, repo_path)
    
    # No need to clean up temporary directory as we're using existing repos
    
    # Analyze key commits and add to PR data
    print("Adding commit analysis placeholder...")
    pr_data['commit_analysis'] = analyze_key_commits(pr_data)
    
    # Save PR information
    file_path = save_pr_info(output_dir, repo, args.pr, pr_data)
    
    print(f"PR information saved to: {file_path}")
    print(f"Title: {pr_data.get('title', 'Unknown')}")
    print(f"State: {pr_data.get('state', 'Unknown')}")
    print(f"Author: {pr_data.get('author', {}).get('login', 'Unknown')}")
    
    # Print summary of fetched data
    num_files = len(pr_data.get('files', []))
    
    print(f"Fetched {num_files} files")

if __name__ == "__main__":
    main() 