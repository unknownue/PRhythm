from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class GitHubUser(BaseModel):
    """GitHub user model."""
    login: str
    id: int
    node_id: str
    avatar_url: str
    html_url: str
    type: str


class GitHubRepository(BaseModel):
    """GitHub repository model."""
    id: int
    node_id: str
    name: str
    full_name: str
    owner: GitHubUser
    private: bool
    html_url: str
    description: Optional[str] = None
    language: Optional[str] = None
    languages_url: str
    size: int
    default_branch: str
    created_at: datetime
    updated_at: datetime
    clone_url: str
    ssh_url: str


class GitHubFile(BaseModel):
    """GitHub file change model."""
    filename: str
    status: str  # "added", "modified", "removed", "renamed"
    additions: int
    deletions: int
    changes: int
    blob_url: str
    patch: Optional[str] = None
    previous_filename: Optional[str] = None


class GitHubCommit(BaseModel):
    """GitHub commit model."""
    sha: str
    message: str
    author: Dict[str, Any]
    committer: Dict[str, Any]
    timestamp: datetime
    html_url: str


class PullRequest(BaseModel):
    """GitHub Pull Request model."""
    id: int
    node_id: str
    number: int
    title: str
    body: Optional[str] = None
    state: str  # "open", "closed", "merged"
    user: GitHubUser
    created_at: datetime
    updated_at: datetime
    closed_at: Optional[datetime] = None
    merged_at: Optional[datetime] = None
    merge_commit_sha: Optional[str] = None
    head: Dict[str, Any]  # head branch info
    base: Dict[str, Any]  # base branch info
    html_url: str
    diff_url: str
    patch_url: str
    commits: int
    additions: int
    deletions: int
    changed_files: int
    mergeable: Optional[bool] = None
    mergeable_state: Optional[str] = None


class PRDiff(BaseModel):
    """Pull Request diff model."""
    pr_number: int
    repository: str
    files: List[GitHubFile]
    total_additions: int
    total_deletions: int
    total_changes: int
    commits: List[GitHubCommit]


class RepositoryContext(BaseModel):
    """Repository context model for analysis."""
    repository: GitHubRepository
    languages: Dict[str, int]  # language -> bytes count
    main_language: Optional[str] = None
    readme_content: Optional[str] = None
    structure: Dict[str, Any]  # directory structure
    key_files: List[str]  # important files like package.json, requirements.txt, etc.
    technologies: List[str]  # detected technologies/frameworks


class PRAnalysisRequest(BaseModel):
    """PR analysis request model."""
    repository_url: str = Field(description="GitHub repository URL")
    pr_number: int = Field(description="Pull request number")
    include_context: bool = Field(default=True, description="Whether to gather code context")
    analysis_depth: str = Field(default="standard", description="Analysis depth: quick, standard, deep")


class PRAnalysisResult(BaseModel):
    """PR analysis result model."""
    pr: PullRequest
    repository_context: RepositoryContext
    diff: PRDiff
    analysis_report: str
    metadata: Dict[str, Any]
    generated_at: datetime