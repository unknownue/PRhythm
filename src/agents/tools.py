"""Git and file system tools for PRhythm agents."""

import asyncio
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Annotated, Any, Dict, List, Optional, Union

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import InjectedToolArg, tool, ToolException
from pydantic import BaseModel, Field

from .configuration import AgentConfiguration


###################
# Tool Models
###################

class GitCommandResult(BaseModel):
    """Result of a git command execution."""
    
    command: str
    exit_code: int
    stdout: str
    stderr: str
    success: bool
    execution_time_seconds: float


class FileAnalysisResult(BaseModel):
    """Result of file analysis operations."""
    
    file_path: str
    exists: bool
    size_bytes: Optional[int] = None
    is_binary: Optional[bool] = None
    content_preview: Optional[str] = None
    error_message: Optional[str] = None


class DirectoryInfo(BaseModel):
    """Information about a directory."""
    
    path: str
    exists: bool
    file_count: Optional[int] = None
    total_size_bytes: Optional[int] = None
    files: Optional[List[str]] = None


###################
# Helper Functions
###################

def _safe_get_author(pr_data: Dict) -> str:
    """Safely extract author information from PR data."""
    try:
        # Try author field first
        author_info = pr_data.get("author")
        if isinstance(author_info, dict):
            return author_info.get("login", "unknown")
        elif isinstance(author_info, str):
            return author_info
        
        # Fall back to user field
        user_info = pr_data.get("user")
        if isinstance(user_info, dict):
            return user_info.get("login", "unknown")
        elif isinstance(user_info, str):
            return user_info
        
        return "unknown"
    except Exception:
        return "unknown"


###################
# Git Tools
###################

@tool(description="Execute git status command and return repository status")
async def git_status(
    repo_path: str,
    config: Annotated[RunnableConfig, InjectedToolArg] = None
) -> GitCommandResult:
    """Execute git status command in the specified repository.
    
    Args:
        repo_path: Path to the git repository
        config: Runtime configuration for timeouts and retries
        
    Returns:
        GitCommandResult with status information
    """
    return await _execute_git_command(
        command="git status --porcelain --branch",
        repo_path=repo_path,
        config=config
    )


@tool(description="Execute git diff command to show changes between commits")
async def git_diff(
    repo_path: str,
    base_ref: str = "HEAD~1",
    target_ref: str = "HEAD",
    include_stats: bool = True,
    config: Annotated[RunnableConfig, InjectedToolArg] = None
) -> GitCommandResult:
    """Execute git diff command to show changes between commits.
    
    Args:
        repo_path: Path to the git repository
        base_ref: Base reference for diff (default: HEAD~1)
        target_ref: Target reference for diff (default: HEAD)
        include_stats: Whether to include diff statistics
        config: Runtime configuration for timeouts and retries
        
    Returns:
        GitCommandResult with diff information
    """
    # Build diff command with options
    command_parts = ["git", "diff"]
    if include_stats:
        command_parts.append("--stat")
    command_parts.extend([base_ref, target_ref])
    
    command = " ".join(command_parts)
    return await _execute_git_command(command, repo_path, config)


@tool(description="Execute git log command to show commit history")
async def git_log(
    repo_path: str,
    max_count: int = 10,
    format_string: str = "oneline",
    since: Optional[str] = None,
    config: Annotated[RunnableConfig, InjectedToolArg] = None
) -> GitCommandResult:
    """Execute git log command to show commit history.
    
    Args:
        repo_path: Path to the git repository
        max_count: Maximum number of commits to show
        format_string: Git log format (oneline, short, medium, full)
        since: Show commits since specified date/time
        config: Runtime configuration for timeouts and retries
        
    Returns:
        GitCommandResult with commit history
    """
    # Build log command with options
    command_parts = ["git", "log", f"--max-count={max_count}", f"--pretty={format_string}"]
    if since:
        command_parts.extend(["--since", f'"{since}"'])
    
    command = " ".join(command_parts)
    return await _execute_git_command(command, repo_path, config)


@tool(description="Execute git checkout command to switch to a specific commit or branch")
async def git_checkout(
    repo_path: str,
    ref: str,
    create_branch: bool = False,
    force: bool = False,
    config: Annotated[RunnableConfig, InjectedToolArg] = None
) -> GitCommandResult:
    """Execute git checkout command to switch to a specific commit or branch.
    
    Args:
        repo_path: Path to the git repository
        ref: Reference to checkout (commit hash, branch name, tag)
        create_branch: Create a new branch if it doesn't exist
        force: Force checkout even if there are uncommitted changes
        config: Runtime configuration for timeouts and retries
        
    Returns:
        GitCommandResult with checkout result
    """
    # Build checkout command with options
    command_parts = ["git", "checkout"]
    if force:
        command_parts.append("--force")
    if create_branch:
        command_parts.append("-b")
    command_parts.append(ref)
    
    command = " ".join(command_parts)
    return await _execute_git_command(command, repo_path, config)


@tool(description="Execute git show command to display information about a commit")
async def git_show(
    repo_path: str,
    ref: str = "HEAD",
    show_stats: bool = True,
    show_files: bool = False,
    config: Annotated[RunnableConfig, InjectedToolArg] = None
) -> GitCommandResult:
    """Execute git show command to display commit information.
    
    Args:
        repo_path: Path to the git repository
        ref: Reference to show (commit hash, branch name, tag)
        show_stats: Include diff statistics
        show_files: Include changed file names
        config: Runtime configuration for timeouts and retries
        
    Returns:
        GitCommandResult with commit information
    """
    # Build show command with options
    command_parts = ["git", "show"]
    if show_stats:
        command_parts.append("--stat")
    if show_files:
        command_parts.append("--name-only")
    command_parts.append(ref)
    
    command = " ".join(command_parts)
    return await _execute_git_command(command, repo_path, config)


@tool(description="Get list of files changed in a commit or between commits")
async def git_changed_files(
    repo_path: str,
    base_ref: str = "HEAD~1",
    target_ref: str = "HEAD",
    config: Annotated[RunnableConfig, InjectedToolArg] = None
) -> GitCommandResult:
    """Get list of files changed between commits.
    
    Args:
        repo_path: Path to the git repository
        base_ref: Base reference for comparison
        target_ref: Target reference for comparison
        config: Runtime configuration for timeouts and retries
        
    Returns:
        GitCommandResult with list of changed files
    """
    command = f"git diff --name-only {base_ref} {target_ref}"
    return await _execute_git_command(command, repo_path, config)


@tool(description="Clone a git repository to a specified path")
async def git_clone(
    repo_url: str,
    target_path: str,
    branch: Optional[str] = None,
    depth: Optional[int] = None,
    config: Annotated[RunnableConfig, InjectedToolArg] = None
) -> GitCommandResult:
    """Clone a git repository to the specified path.
    
    Args:
        repo_url: URL of the git repository to clone
        target_path: Local path where repository should be cloned
        branch: Specific branch to clone
        depth: Create a shallow clone with specified depth
        config: Runtime configuration for timeouts and retries
        
    Returns:
        GitCommandResult with clone operation result
    """
    # Build clone command with options
    command_parts = ["git", "clone"]
    if branch:
        command_parts.extend(["--branch", branch])
    if depth:
        command_parts.extend(["--depth", str(depth)])
    command_parts.extend([repo_url, target_path])
    
    command = " ".join(command_parts)
    
    # Clone operations don't have a working directory initially
    return await _execute_git_command(
        command=command,
        repo_path=None,  # No working directory for clone
        config=config
    )


###################
# File System Tools
###################

@tool(description="Analyze a file and return information about its content")
async def analyze_file(
    file_path: str,
    include_preview: bool = True,
    max_preview_chars: int = 1000,
    config: Annotated[RunnableConfig, InjectedToolArg] = None
) -> FileAnalysisResult:
    """Analyze a file and return information about its content.
    
    Args:
        file_path: Path to the file to analyze
        include_preview: Whether to include a content preview
        max_preview_chars: Maximum number of characters in preview
        config: Runtime configuration
        
    Returns:
        FileAnalysisResult with file information
    """
    try:
        path = Path(file_path)
        
        if not path.exists():
            return FileAnalysisResult(
                file_path=file_path,
                exists=False
            )
        
        # Get file size
        size_bytes = path.stat().st_size
        
        # Check if file is binary
        is_binary = _is_binary_file(path)
        
        # Get content preview if requested and file is not binary
        content_preview = None
        if include_preview and not is_binary and size_bytes > 0:
            try:
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    content_preview = f.read(max_preview_chars)
                    if len(content_preview) == max_preview_chars:
                        content_preview += "... (truncated)"
            except Exception as e:
                content_preview = f"Error reading file: {str(e)}"
        
        return FileAnalysisResult(
            file_path=file_path,
            exists=True,
            size_bytes=size_bytes,
            is_binary=is_binary,
            content_preview=content_preview
        )
        
    except Exception as e:
        return FileAnalysisResult(
            file_path=file_path,
            exists=False,
            error_message=str(e)
        )


@tool(description="Get information about a directory")
async def analyze_directory(
    directory_path: str,
    include_files: bool = False,
    max_files: int = 100,
    config: Annotated[RunnableConfig, InjectedToolArg] = None
) -> DirectoryInfo:
    """Analyze a directory and return information about its contents.
    
    Args:
        directory_path: Path to the directory to analyze
        include_files: Whether to include list of files
        max_files: Maximum number of files to include in list
        config: Runtime configuration
        
    Returns:
        DirectoryInfo with directory information
    """
    try:
        path = Path(directory_path)
        
        if not path.exists() or not path.is_dir():
            return DirectoryInfo(
                path=directory_path,
                exists=False
            )
        
        # Count files and calculate total size
        file_count = 0
        total_size = 0
        files_list = []
        
        for item in path.rglob("*"):
            if item.is_file():
                file_count += 1
                total_size += item.stat().st_size
                
                # Add to files list if requested
                if include_files and len(files_list) < max_files:
                    files_list.append(str(item.relative_to(path)))
        
        return DirectoryInfo(
            path=directory_path,
            exists=True,
            file_count=file_count,
            total_size_bytes=total_size,
            files=files_list if include_files else None
        )
        
    except Exception as e:
        return DirectoryInfo(
            path=directory_path,
            exists=False
        )


@tool(description="Search for files matching specific patterns")
async def find_files(
    search_path: str,
    pattern: str = "*",
    include_hidden: bool = False,
    max_results: int = 50,
    config: Annotated[RunnableConfig, InjectedToolArg] = None
) -> List[str]:
    """Search for files matching a specific pattern.
    
    Args:
        search_path: Path to search in
        pattern: File pattern to match (e.g., "*.py", "test_*")
        include_hidden: Whether to include hidden files
        max_results: Maximum number of results to return
        config: Runtime configuration
        
    Returns:
        List of matching file paths
    """
    try:
        path = Path(search_path)
        if not path.exists():
            raise ToolException(f"Search path does not exist: {search_path}")
        
        results = []
        for item in path.rglob(pattern):
            if item.is_file():
                # Skip hidden files unless requested
                if not include_hidden and any(part.startswith('.') for part in item.parts):
                    continue
                
                results.append(str(item))
                
                # Limit results
                if len(results) >= max_results:
                    break
        
        return results
        
    except Exception as e:
        raise ToolException(f"Error searching files: {str(e)}")


###################
# PR Analysis Tools
###################

@tool(description="Extract and analyze PR metadata from GitHub data")
async def analyze_pr_metadata(
    pr_data: Dict[str, Any],
    config: Annotated[RunnableConfig, InjectedToolArg] = None
) -> Dict[str, Any]:
    """Analyze PR metadata and extract key information for analysis.
    
    Args:
        pr_data: Raw PR data from GitHub API
        config: Runtime configuration
        
    Returns:
        Structured PR analysis metadata
    """
    try:
        # Extract basic PR information
        analysis = {
            "pr_number": pr_data.get("number"),
            "title": pr_data.get("title", ""),
            "description": pr_data.get("body", ""),
            "author": _safe_get_author(pr_data),
            "state": pr_data.get("state", "unknown"),
            "created_at": pr_data.get("created_at"),
            "updated_at": pr_data.get("updated_at"),
            "merged_at": pr_data.get("merged_at"),
            "base_branch": pr_data.get("base", {}).get("ref", "unknown"),
            "head_branch": pr_data.get("head", {}).get("ref", "unknown"),
            "base_sha": pr_data.get("base", {}).get("sha"),
            "head_sha": pr_data.get("head", {}).get("sha"),
            "merge_commit_sha": pr_data.get("merge_commit_sha")
        }
        
        # Extract labels
        labels = []
        for label in pr_data.get("labels", []):
            if isinstance(label, str):
                labels.append(label)
            else:
                labels.append(label.get("name", ""))
        analysis["labels"] = labels
        
        # Extract file change statistics
        statistics = pr_data.get("statistics", {})
        analysis["files_changed"] = statistics.get("files_changed", pr_data.get("changed_files", 0))
        analysis["additions"] = statistics.get("lines_added", pr_data.get("additions", 0))
        analysis["deletions"] = statistics.get("lines_deleted", pr_data.get("deletions", 0))
        analysis["total_changes"] = analysis["additions"] + analysis["deletions"]
        
        # Extract reviewer information
        reviewers = []
        for reviewer in pr_data.get("requested_reviewers", []):
            reviewers.append(reviewer.get("login", ""))
        analysis["reviewers"] = reviewers
        
        # Extract assignee information
        assignees = []
        for assignee in pr_data.get("assignees", []):
            assignees.append(assignee.get("login", ""))
        analysis["assignees"] = assignees
        
        # Calculate PR age and complexity metrics
        if analysis["created_at"] and analysis["merged_at"]:
            from datetime import datetime
            created = datetime.fromisoformat(analysis["created_at"].replace('Z', '+00:00'))
            merged = datetime.fromisoformat(analysis["merged_at"].replace('Z', '+00:00'))
            analysis["pr_age_hours"] = (merged - created).total_seconds() / 3600
        
        # Categorize PR size
        if analysis["total_changes"] < 50:
            analysis["size_category"] = "small"
        elif analysis["total_changes"] < 300:
            analysis["size_category"] = "medium"
        elif analysis["total_changes"] < 1000:
            analysis["size_category"] = "large"
        else:
            analysis["size_category"] = "xlarge"
        
        return analysis
        
    except Exception as e:
        raise ToolException(f"Error analyzing PR metadata: {str(e)}")


###################
# Helper Functions
###################

async def _execute_git_command(
    command: str,
    repo_path: Optional[str],
    config: Optional[RunnableConfig]
) -> GitCommandResult:
    """Execute a git command with proper error handling and timeout."""
    import time
    
    # Get configuration
    agent_config = AgentConfiguration.from_runnable_config(config) if config else AgentConfiguration()
    
    start_time = time.time()
    
    try:
        # Prepare command execution environment
        env = os.environ.copy()
        cwd = repo_path if repo_path else None
        
        # Execute command with timeout
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
            env=env
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=agent_config.git_command_timeout_seconds
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            raise ToolException(f"Git command timed out after {agent_config.git_command_timeout_seconds} seconds: {command}")
        
        # Decode output
        stdout_str = stdout.decode('utf-8', errors='ignore') if stdout else ""
        stderr_str = stderr.decode('utf-8', errors='ignore') if stderr else ""
        
        execution_time = time.time() - start_time
        
        # Log command if configured
        if agent_config.log_git_commands:
            print(f"Git command executed: {command} (exit code: {process.returncode}, time: {execution_time:.2f}s)")
        
        return GitCommandResult(
            command=command,
            exit_code=process.returncode,
            stdout=stdout_str,
            stderr=stderr_str,
            success=process.returncode == 0,
            execution_time_seconds=execution_time
        )
        
    except Exception as e:
        execution_time = time.time() - start_time
        
        return GitCommandResult(
            command=command,
            exit_code=-1,
            stdout="",
            stderr=str(e),
            success=False,
            execution_time_seconds=execution_time
        )


def _is_binary_file(file_path: Path) -> bool:
    """Check if a file is binary."""
    try:
        with open(file_path, 'rb') as f:
            chunk = f.read(8192)
            return b'\x00' in chunk
    except Exception:
        return True  # Assume binary if we can't read it