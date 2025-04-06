"""
Git tools for PR context extraction agents.
These tools help agents interact with Git repositories.
"""

import logging
import os
import subprocess
import re
from typing import Any, Dict, List, Optional
from langchain.tools import BaseTool, tool

# Setup logger
logger = logging.getLogger("git_tools")

@tool
def get_pr_diff(pr_number: int, repo_path: Optional[str] = None) -> str:
    """
    Get the diff for a specific PR.
    
    Args:
        pr_number: The PR number
        repo_path: Optional path to the repository root
        
    Returns:
        str: PR diff content
    """
    logger.debug(f"Getting diff for PR #{pr_number}")
    
    try:
        # Change directory to repo path if provided
        current_dir = os.getcwd()
        if repo_path:
            os.chdir(repo_path)
        
        # In a real implementation, this would use GitHub API or git commands
        # For the purpose of this implementation, we'll simulate it
        # This is placeholder logic
        
        # Try to fetch PR info
        command = ["git", "fetch", "origin", f"pull/{pr_number}/head:pr-{pr_number}"]
        subprocess.run(command, capture_output=True, check=True)
        
        # Get PR head ref
        pr_branch = f"pr-{pr_number}"
        
        # Get base branch (assuming main/master)
        try:
            # Try to get the base branch from config
            base_command = ["git", "config", "prhythm.base-branch"]
            base_result = subprocess.run(base_command, capture_output=True, text=True)
            base_branch = base_result.stdout.strip()
            if not base_branch:
                # Try main, then master
                for default_base in ["main", "master"]:
                    try:
                        check_command = ["git", "rev-parse", "--verify", f"origin/{default_base}"]
                        subprocess.run(check_command, capture_output=True, check=True)
                        base_branch = f"origin/{default_base}"
                        break
                    except subprocess.CalledProcessError:
                        continue
        except Exception:
            # Default to main
            base_branch = "origin/main"
        
        # Get diff
        diff_command = ["git", "diff", f"{base_branch}...{pr_branch}"]
        diff_result = subprocess.run(diff_command, capture_output=True, text=True, check=True)
        
        # Go back to original directory
        if repo_path:
            os.chdir(current_dir)
        
        return diff_result.stdout
    except subprocess.CalledProcessError as e:
        logger.error(f"Error getting PR diff: {str(e)}")
        
        # Go back to original directory
        if repo_path:
            os.chdir(current_dir)
        
        # Try an alternative approach if available
        try:
            # This requires the GitHub CLI (gh)
            gh_command = ["gh", "pr", "diff", str(pr_number)]
            gh_result = subprocess.run(gh_command, capture_output=True, text=True, check=True)
            return gh_result.stdout
        except Exception as gh_error:
            logger.error(f"Failed fallback to GitHub CLI: {str(gh_error)}")
            raise RuntimeError(f"Could not get PR diff: {e.stderr}")
    except Exception as e:
        logger.error(f"Error getting PR diff: {str(e)}")
        
        # Go back to original directory
        if repo_path:
            os.chdir(current_dir)
        
        raise RuntimeError(f"Could not get PR diff: {str(e)}")

@tool
def parse_diff(diff_content: str) -> Dict[str, Any]:
    """
    Parse a Git diff into a structured format.
    
    Args:
        diff_content: The diff content to parse
        
    Returns:
        Dict[str, Any]: Parsed diff information
    """
    logger.debug("Parsing diff content")
    
    try:
        # Parse the diff content
        # This is a simplified implementation
        
        files = []
        current_file = None
        hunks = []
        current_hunk = None
        before_lines = []
        after_lines = []
        
        lines = diff_content.split('\n')
        for line in lines:
            # Check for file headers
            file_header_match = re.match(r'^diff --git a/(.*) b/(.*)$', line)
            if file_header_match:
                # Save the previous file if it exists
                if current_file:
                    current_file["hunks"] = hunks
                    files.append(current_file)
                    hunks = []
                
                # Start a new file
                current_file = {
                    "old_path": file_header_match.group(1),
                    "new_path": file_header_match.group(2),
                    "hunks": []
                }
                continue
            
            # Check for hunk headers
            hunk_header_match = re.match(r'^@@ -(\d+),(\d+) \+(\d+),(\d+) @@(.*)$', line)
            if hunk_header_match:
                # Save the previous hunk if it exists
                if current_hunk:
                    hunks.append(current_hunk)
                
                # Start a new hunk
                current_hunk = {
                    "old_start": int(hunk_header_match.group(1)),
                    "old_lines": int(hunk_header_match.group(2)),
                    "new_start": int(hunk_header_match.group(3)),
                    "new_lines": int(hunk_header_match.group(4)),
                    "content": line,
                    "changes": []
                }
                continue
            
            # Process lines within a hunk
            if current_hunk:
                if line.startswith('-'):
                    current_hunk["changes"].append({"type": "removal", "content": line[1:]})
                    before_lines.append(line[1:])
                elif line.startswith('+'):
                    current_hunk["changes"].append({"type": "addition", "content": line[1:]})
                    after_lines.append(line[1:])
                elif line.startswith(' '):
                    current_hunk["changes"].append({"type": "context", "content": line[1:]})
                    before_lines.append(line[1:])
                    after_lines.append(line[1:])
        
        # Save the last file and hunk if they exist
        if current_hunk:
            hunks.append(current_hunk)
        if current_file:
            current_file["hunks"] = hunks
            files.append(current_file)
        
        return {
            "files": files,
            "before_lines": before_lines,
            "after_lines": after_lines
        }
    except Exception as e:
        logger.error(f"Error parsing diff: {str(e)}")
        return {
            "error": str(e),
            "files": [],
            "before_lines": [],
            "after_lines": []
        }

def get_git_tools(repo_path: str = None) -> List[BaseTool]:
    """
    Get a list of Git tools.
    
    Args:
        repo_path: Path to the repository root
        
    Returns:
        List[BaseTool]: List of Git tools
    """
    tools = [
        get_pr_diff,
        parse_diff
    ]
    
    return tools 