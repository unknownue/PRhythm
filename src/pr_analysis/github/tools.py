from typing import Dict, Any, Optional
import json
import asyncio
from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, Field

from .client import GitHubAPIClient
from .models import (
    PullRequest, GitHubRepository, PRDiff, RepositoryContext, 
    PRAnalysisRequest
)


class FetchPRInfoInput(BaseModel):
    """Input for fetching PR information."""
    repository_url: str = Field(description="GitHub repository URL (e.g., https://github.com/owner/repo)")
    pr_number: int = Field(description="Pull request number")


class FetchRepositoryInfoInput(BaseModel):
    """Input for fetching repository information."""
    repository_url: str = Field(description="GitHub repository URL (e.g., https://github.com/owner/repo)")


class FetchPRDiffInput(BaseModel):
    """Input for fetching PR diff information."""
    repository_url: str = Field(description="GitHub repository URL (e.g., https://github.com/owner/repo)")
    pr_number: int = Field(description="Pull request number")


class FetchFileContentInput(BaseModel):
    """Input for fetching file content."""
    repository_url: str = Field(description="GitHub repository URL (e.g., https://github.com/owner/repo)")
    file_path: str = Field(description="Path to the file in the repository")
    ref: str = Field(default="main", description="Git reference (branch, tag, or commit SHA)")


@tool
async def fetch_pr_info(
    repository_url: str,
    pr_number: int
) -> str:
    """
    Fetch comprehensive information about a GitHub Pull Request.
    
    Args:
        repository_url: GitHub repository URL (e.g., https://github.com/owner/repo)
        pr_number: Pull request number
    
    Returns:
        JSON string containing PR information including title, description, author, 
        creation date, merge status, and change statistics.
    """
    try:
        async with GitHubAPIClient() as client:
            pr = await client.get_pull_request(repository_url, pr_number)
            return json.dumps(pr.model_dump(), indent=2, default=str)
    except Exception as e:
        return f"Error fetching PR information: {str(e)}"


@tool
async def fetch_repository_info(repository_url: str) -> str:
    """
    Fetch comprehensive information about a GitHub repository.
    
    Args:
        repository_url: GitHub repository URL (e.g., https://github.com/owner/repo)
    
    Returns:
        JSON string containing repository information including description, 
        main language, size, creation date, and technologies detected.
    """
    try:
        async with GitHubAPIClient() as client:
            repo_context = await client.get_repository_context(repository_url)
            return json.dumps(repo_context.model_dump(), indent=2, default=str)
    except Exception as e:
        return f"Error fetching repository information: {str(e)}"


@tool
async def fetch_pr_diff(
    repository_url: str,
    pr_number: int
) -> str:
    """
    Fetch detailed diff information for a GitHub Pull Request.
    
    Args:
        repository_url: GitHub repository URL (e.g., https://github.com/owner/repo)
        pr_number: Pull request number
    
    Returns:
        JSON string containing diff information including changed files, 
        additions, deletions, and commit details.
    """
    try:
        async with GitHubAPIClient() as client:
            diff = await client.get_pr_diff(repository_url, pr_number)
            return json.dumps(diff.model_dump(), indent=2, default=str)
    except Exception as e:
        return f"Error fetching PR diff: {str(e)}"


@tool
async def fetch_file_content(
    repository_url: str,
    file_path: str,
    ref: str = "main"
) -> str:
    """
    Fetch the content of a specific file from a GitHub repository.
    
    Args:
        repository_url: GitHub repository URL (e.g., https://github.com/owner/repo)
        file_path: Path to the file in the repository
        ref: Git reference (branch, tag, or commit SHA), defaults to "main"
    
    Returns:
        File content as string, or error message if file not found.
    """
    try:
        async with GitHubAPIClient() as client:
            content = await client.get_file_content(repository_url, file_path, ref)
            if content is None:
                return f"File not found: {file_path} at ref {ref}"
            return content
    except Exception as e:
        return f"Error fetching file content: {str(e)}"


@tool
async def analyze_pr_impact(
    repository_url: str,
    pr_number: int
) -> str:
    """
    Analyze the impact and scope of changes in a GitHub Pull Request.
    
    Args:
        repository_url: GitHub repository URL (e.g., https://github.com/owner/repo)
        pr_number: Pull request number
    
    Returns:
        JSON string containing impact analysis including affected components,
        change complexity, and potential risk areas.
    """
    try:
        async with GitHubAPIClient() as client:
            pr = await client.get_pull_request(repository_url, pr_number)
            diff = await client.get_pr_diff(repository_url, pr_number)
            
            # Analyze impact
            impact_analysis = {
                "pr_number": pr_number,
                "total_files_changed": len(diff.files),
                "total_lines_changed": diff.total_changes,
                "additions": diff.total_additions,
                "deletions": diff.total_deletions,
                "commits": len(diff.commits),
                "file_types": {},
                "complexity_score": 0,
                "risk_areas": []
            }
            
            # Analyze file types and complexity
            for file in diff.files:
                file_ext = file.filename.split('.')[-1] if '.' in file.filename else 'no_extension'
                if file_ext not in impact_analysis["file_types"]:
                    impact_analysis["file_types"][file_ext] = 0
                impact_analysis["file_types"][file_ext] += 1
                
                # Add to complexity score based on changes
                if file.changes > 100:
                    impact_analysis["complexity_score"] += 3
                elif file.changes > 50:
                    impact_analysis["complexity_score"] += 2
                else:
                    impact_analysis["complexity_score"] += 1
                
                # Identify risk areas
                if any(keyword in file.filename.lower() for keyword in ['config', 'setting', 'env']):
                    impact_analysis["risk_areas"].append(f"Configuration file: {file.filename}")
                if any(keyword in file.filename.lower() for keyword in ['database', 'migration', 'schema']):
                    impact_analysis["risk_areas"].append(f"Database-related file: {file.filename}")
                if any(keyword in file.filename.lower() for keyword in ['security', 'auth', 'permission']):
                    impact_analysis["risk_areas"].append(f"Security-related file: {file.filename}")
            
            return json.dumps(impact_analysis, indent=2)
    except Exception as e:
        return f"Error analyzing PR impact: {str(e)}"


@tool 
async def get_pr_context_files(
    repository_url: str,
    pr_number: int,
    max_files: int = 10
) -> str:
    """
    Get relevant context files that may be related to the PR changes.
    
    Args:
        repository_url: GitHub repository URL (e.g., https://github.com/owner/repo)
        pr_number: Pull request number
        max_files: Maximum number of context files to retrieve
    
    Returns:
        JSON string containing relevant context files and their content.
    """
    try:
        async with GitHubAPIClient() as client:
            repo_context = await client.get_repository_context(repository_url)
            diff = await client.get_pr_diff(repository_url, pr_number)
            
            context_files = {}
            
            # Always include key configuration files
            for key_file in repo_context.key_files[:max_files//2]:
                content = await client.get_file_content(repository_url, key_file)
                if content:
                    context_files[key_file] = {
                        "type": "configuration",
                        "content": content[:2000] if len(content) > 2000 else content  # Truncate large files
                    }
            
            # Include related files based on changed file paths
            changed_dirs = set()
            for file in diff.files:
                if '/' in file.filename:
                    changed_dirs.add('/'.join(file.filename.split('/')[:-1]))
            
            # Look for related files in the same directories
            related_files = []
            for changed_dir in list(changed_dirs)[:3]:  # Limit to 3 directories
                for ext in ['.md', '.txt', '.json', '.yaml', '.yml']:
                    for filename in [f"README{ext}", f"CONFIG{ext}", f"CHANGELOG{ext}"]:
                        file_path = f"{changed_dir}/{filename}" if changed_dir else filename
                        if len(related_files) < max_files//2:
                            related_files.append(file_path)
            
            # Fetch related files
            for file_path in related_files:
                if len(context_files) >= max_files:
                    break
                content = await client.get_file_content(repository_url, file_path)
                if content:
                    context_files[file_path] = {
                        "type": "related",
                        "content": content[:1000] if len(content) > 1000 else content
                    }
            
            return json.dumps({
                "repository": repository_url,
                "pr_number": pr_number,
                "context_files": context_files,
                "total_files": len(context_files)
            }, indent=2)
    except Exception as e:
        return f"Error getting PR context files: {str(e)}"


# List of all GitHub tools for easy import
GITHUB_TOOLS = [
    fetch_pr_info,
    fetch_repository_info, 
    fetch_pr_diff,
    fetch_file_content,
    analyze_pr_impact,
    get_pr_context_files
]