"""Utility functions for PRhythm agents."""

import os
import json
import shutil
import asyncio
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime

from langchain_core.runnables import RunnableConfig

from .configuration import AgentConfiguration
from .state import WorkspaceState
from .tools import git_clone, git_checkout


async def setup_workspace(
    workspace_state: WorkspaceState,
    pr_data: Dict,
    config: RunnableConfig
) -> None:
    """Set up workspace directories and repositories for PR analysis.
    
    Args:
        workspace_state: Workspace configuration and paths
        pr_data: PR data from GitHub API
        config: Runtime configuration
    """
    # Create base workspace directories
    for path in [
        workspace_state.base_path,
        workspace_state.reports_path,
        workspace_state.temp_path,
        Path(workspace_state.base_path) / "metadata"
    ]:
        Path(path).mkdir(parents=True, exist_ok=True)
    
    # Extract repository information
    repo_info = pr_data.get('base', {}).get('repo', {})
    clone_url = repo_info.get('clone_url', '')
    base_sha = pr_data.get('base', {}).get('sha')
    head_sha = pr_data.get('head', {}).get('sha')
    merge_commit_sha = pr_data.get('merge_commit_sha')
    
    if not clone_url:
        raise ValueError("No clone URL available in PR data")
    
    # Set up repo-previous (pre-merge state)
    await _setup_repository_workspace(
        workspace_state.repo_previous_path,
        clone_url,
        base_sha,
        "pre-merge",
        config
    )
    
    # Set up repo-merged (post-merge state) 
    target_sha = merge_commit_sha or head_sha
    await _setup_repository_workspace(
        workspace_state.repo_merged_path,
        clone_url,
        target_sha,
        "post-merge",
        config
    )
    
    # Update workspace state with commit information
    workspace_state.previous_commit = base_sha
    workspace_state.merged_commit = target_sha
    
    # Save workspace metadata
    await _save_workspace_metadata(workspace_state, pr_data)


async def _setup_repository_workspace(
    workspace_path: str,
    clone_url: str,
    target_sha: str,
    workspace_type: str,
    config: RunnableConfig
) -> None:
    """Set up a single repository workspace.
    
    Args:
        workspace_path: Path where repository should be set up
        clone_url: Git repository clone URL
        target_sha: SHA to checkout after cloning
        workspace_type: Type of workspace (pre-merge/post-merge)
        config: Runtime configuration
    """
    workspace_path_obj = Path(workspace_path)
    
    # Check if workspace already exists and is valid
    if workspace_path_obj.exists() and (workspace_path_obj / ".git").exists():
        # Workspace exists, just checkout the target SHA
        if target_sha:
            checkout_result = await git_checkout(
                repo_path=workspace_path,
                ref=target_sha,
                force=True,
                config=config
            )
            
            if not checkout_result.success:
                # If checkout fails, remove and re-clone
                shutil.rmtree(workspace_path, ignore_errors=True)
            else:
                return  # Successfully checked out
    
    # Clone repository if workspace doesn't exist or checkout failed
    if workspace_path_obj.exists():
        shutil.rmtree(workspace_path, ignore_errors=True)
    
    # Create parent directory
    workspace_path_obj.parent.mkdir(parents=True, exist_ok=True)
    
    # Clone repository
    clone_result = await git_clone(
        repo_url=clone_url,
        target_path=workspace_path,
        config=config
    )
    
    if not clone_result.success:
        raise RuntimeError(f"Failed to clone repository for {workspace_type}: {clone_result.stderr}")
    
    # Checkout target SHA if specified
    if target_sha:
        checkout_result = await git_checkout(
            repo_path=workspace_path,
            ref=target_sha,
            force=True,
            config=config
        )
        
        if not checkout_result.success:
            raise RuntimeError(f"Failed to checkout {target_sha} for {workspace_type}: {checkout_result.stderr}")


async def _save_workspace_metadata(
    workspace_state: WorkspaceState,
    pr_data: Dict
) -> None:
    """Save workspace metadata for tracking and debugging."""
    metadata = {
        "workspace_created": datetime.now().isoformat(),
        "repository_name": workspace_state.repository_name,
        "previous_commit": workspace_state.previous_commit,
        "merged_commit": workspace_state.merged_commit,
        "pr_data": {
            "number": pr_data.get("number"),
            "title": pr_data.get("title"),
            "author": pr_data.get("user", {}).get("login"),
            "created_at": pr_data.get("created_at"),
            "merged_at": pr_data.get("merged_at")
        },
        "workspace_paths": {
            "base": workspace_state.base_path,
            "repo_previous": workspace_state.repo_previous_path,
            "repo_merged": workspace_state.repo_merged_path,
            "reports": workspace_state.reports_path,
            "temp": workspace_state.temp_path
        }
    }
    
    metadata_path = Path(workspace_state.base_path) / "metadata" / "workspace_info.json"
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)


async def cleanup_workspace(
    workspace_state: WorkspaceState,
    keep_reports: bool = True,
    config: Optional[RunnableConfig] = None
) -> None:
    """Clean up workspace files and directories.
    
    Args:
        workspace_state: Workspace configuration
        keep_reports: Whether to preserve generated reports
        config: Runtime configuration
    """
    agent_config = AgentConfiguration.from_runnable_config(config) if config else AgentConfiguration()
    
    # Clean up temporary files
    temp_path = Path(workspace_state.temp_path)
    if temp_path.exists():
        shutil.rmtree(temp_path, ignore_errors=True)
    
    # Optionally clean up repository workspaces (usually keep them for debugging)
    # This would require configuration option or explicit request
    
    # Update cleanup timestamp in metadata
    metadata_path = Path(workspace_state.base_path) / "metadata" / "workspace_info.json"
    if metadata_path.exists():
        try:
            with open(metadata_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            
            metadata["last_cleanup"] = datetime.now().isoformat()
            
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
        except Exception:
            pass  # Ignore metadata update errors


async def load_scheme_config(
    scheme_name: str,
    repository_config: Dict
) -> Dict:
    """Load configuration for the specified analysis scheme.
    
    Args:
        scheme_name: Name of the analysis scheme to load
        repository_config: Repository configuration
        
    Returns:
        Scheme configuration dictionary
    """
    # Default scheme configurations
    default_schemes = {
        "general_review": {
            "metadata": {
                "name": "general_review",
                "description": "Comprehensive general code review",
                "version": "1.0.0"
            },
            "requirements": {
                "pre_merge_data": True,
                "post_merge_data": True,
                "pr_metadata": True
            },
            "agents": {
                "pre_merge_collector": {
                    "enabled": True,
                    "timeout_minutes": 10,
                    "tasks": [
                        {
                            "name": "repository_status",
                            "commands": ["git status", "git log --max-count=5"],
                            "required": True
                        },
                        {
                            "name": "dependency_analysis",
                            "commands": ["find_files requirements.txt", "find_files package.json", "find_files Cargo.toml"],
                            "required": False
                        }
                    ]
                },
                "post_merge_collector": {
                    "enabled": True,
                    "timeout_minutes": 10,
                    "tasks": [
                        {
                            "name": "diff_analysis",
                            "commands": ["git diff --stat HEAD~1 HEAD"],
                            "required": True
                        },
                        {
                            "name": "impact_assessment", 
                            "commands": ["git show --stat", "git changed-files HEAD~1 HEAD"],
                            "required": True
                        }
                    ]
                }
            },
            "llm_config": {
                "analysis_focus": [
                    "code_quality",
                    "best_practices",
                    "maintainability",
                    "documentation_quality"
                ],
                "output_structure": {
                    "summary": "Brief overview of changes",
                    "detailed_analysis": "In-depth technical review",
                    "recommendations": "Specific improvement suggestions",
                    "risk_assessment": "Potential risks and mitigation"
                }
            }
        },
        "security_audit": {
            "metadata": {
                "name": "security_audit",
                "description": "Security-focused PR analysis",
                "version": "1.0.0"
            },
            "requirements": {
                "pre_merge_data": True,
                "post_merge_data": True,
                "pr_metadata": True
            },
            "agents": {
                "pre_merge_collector": {
                    "enabled": True,
                    "tasks": [
                        {
                            "name": "security_baseline",
                            "commands": ["find_files *.py", "find_files *.js", "find_files *.java"],
                            "required": True
                        }
                    ]
                },
                "post_merge_collector": {
                    "enabled": True,
                    "tasks": [
                        {
                            "name": "security_changes",
                            "commands": ["git diff --stat HEAD~1 HEAD", "git changed-files HEAD~1 HEAD"],
                            "required": True
                        }
                    ]
                }
            },
            "llm_config": {
                "analysis_focus": [
                    "security_vulnerabilities",
                    "input_validation",
                    "authentication_authorization",
                    "data_protection",
                    "crypto_usage"
                ]
            }
        },
        "performance_check": {
            "metadata": {
                "name": "performance_check",
                "description": "Performance-focused PR analysis",
                "version": "1.0.0"
            },
            "requirements": {
                "pre_merge_data": False,
                "post_merge_data": True,
                "pr_metadata": True
            },
            "agents": {
                "post_merge_collector": {
                    "enabled": True,
                    "tasks": [
                        {
                            "name": "performance_analysis",
                            "commands": ["git diff --stat HEAD~1 HEAD"],
                            "required": True
                        }
                    ]
                }
            },
            "llm_config": {
                "analysis_focus": [
                    "performance_impact",
                    "algorithmic_complexity",
                    "resource_usage",
                    "scalability_concerns"
                ]
            }
        }
    }
    
    # Try to get scheme from repository config first
    custom_schemes = repository_config.get("custom_schemes", {})
    if scheme_name in custom_schemes:
        return custom_schemes[scheme_name]
    
    # Fall back to default schemes
    if scheme_name in default_schemes:
        return default_schemes[scheme_name]
    
    # If scheme not found, use general_review as fallback
    return default_schemes["general_review"]


def validate_pr_data(pr_data: Dict) -> tuple[bool, Optional[str]]:
    """Validate PR data contains required fields.
    
    Args:
        pr_data: PR data from GitHub API
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    required_fields = [
        "number",
        "title",
        "base",
        "head",
        "user"
    ]
    
    for field in required_fields:
        if field not in pr_data:
            return False, f"Missing required field: {field}"
    
    # Validate nested fields
    base_data = pr_data.get("base", {})
    if "repo" not in base_data or "sha" not in base_data:
        return False, "Invalid base data: missing repo or sha"
    
    head_data = pr_data.get("head", {})
    if "sha" not in head_data:
        return False, "Invalid head data: missing sha"
    
    repo_data = base_data.get("repo", {})
    if "clone_url" not in repo_data:
        return False, "Invalid repo data: missing clone_url"
    
    return True, None


def validate_repository_config(repository_config: Dict) -> tuple[bool, Optional[str]]:
    """Validate repository configuration contains required fields.
    
    Args:
        repository_config: Repository configuration dictionary
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    required_sections = ["repository", "analysis"]
    
    for section in required_sections:
        if section not in repository_config:
            return False, f"Missing required section: {section}"
    
    # Validate repository section
    repo_config = repository_config.get("repository", {})
    if "name" not in repo_config:
        return False, "Repository config missing 'name' field"
    
    # Validate analysis section
    analysis_config = repository_config.get("analysis", {})
    if "schemes" not in analysis_config:
        return False, "Analysis config missing 'schemes' section"
    
    return True, None