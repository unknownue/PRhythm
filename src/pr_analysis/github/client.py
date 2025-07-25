import asyncio
import aiohttp
import json
import os
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from urllib.parse import urlparse
import base64

from .models import (
    PullRequest, GitHubRepository, GitHubUser, GitHubFile, 
    GitHubCommit, PRDiff, RepositoryContext
)


class GitHubRateLimiter:
    """Rate limiter for GitHub API calls."""
    
    def __init__(self, requests_per_hour: int = 5000):
        self.requests_per_hour = requests_per_hour
        self.requests_made = 0
        self.hour_start = datetime.now()
        self.lock = asyncio.Lock()
    
    async def acquire(self):
        """Acquire permission to make a request."""
        async with self.lock:
            now = datetime.now()
            if now - self.hour_start >= timedelta(hours=1):
                self.requests_made = 0
                self.hour_start = now
            
            if self.requests_made >= self.requests_per_hour:
                sleep_time = 3600 - (now - self.hour_start).total_seconds()
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                    self.requests_made = 0
                    self.hour_start = datetime.now()
            
            self.requests_made += 1


class GitHubAPIClient:
    """Async GitHub API client with rate limiting and error handling."""
    
    def __init__(self, token: Optional[str] = None):
        self.token = token or os.getenv("GITHUB_TOKEN")
        if not self.token:
            raise ValueError("GitHub token is required. Set GITHUB_TOKEN environment variable.")
        
        self.base_url = "https://api.github.com"
        self.rate_limiter = GitHubRateLimiter()
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession(
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "PRhythm-Analyzer/1.0"
            },
            timeout=aiohttp.ClientTimeout(total=30)
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
    
    async def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make an API request with rate limiting and error handling."""
        await self.rate_limiter.acquire()
        
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        for attempt in range(3):  # Retry up to 3 times
            try:
                async with self.session.request(method, url, **kwargs) as response:
                    if response.status == 200:
                        return await response.json()
                    elif response.status == 404:
                        raise ValueError(f"Resource not found: {url}")
                    elif response.status == 403:
                        raise ValueError("GitHub API rate limit exceeded or insufficient permissions")
                    elif response.status >= 500:
                        if attempt < 2:  # Retry on server errors
                            await asyncio.sleep(2 ** attempt)
                            continue
                        raise ValueError(f"GitHub API server error: {response.status}")
                    else:
                        error_text = await response.text()
                        raise ValueError(f"GitHub API error {response.status}: {error_text}")
            except aiohttp.ClientError as e:
                if attempt < 2:
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise ValueError(f"Network error: {str(e)}")
        
        raise ValueError("Max retries exceeded")
    
    def _parse_repo_url(self, repo_url: str) -> tuple[str, str]:
        """Parse repository URL to extract owner and repo name."""
        if repo_url.startswith("https://github.com/"):
            path = urlparse(repo_url).path.strip("/")
            parts = path.split("/")
            if len(parts) >= 2:
                return parts[0], parts[1]
        raise ValueError(f"Invalid GitHub repository URL: {repo_url}")
    
    async def get_repository(self, repo_url: str) -> GitHubRepository:
        """Get repository information."""
        owner, repo = self._parse_repo_url(repo_url)
        data = await self._make_request("GET", f"/repos/{owner}/{repo}")
        
        return GitHubRepository(
            id=data["id"],
            node_id=data["node_id"],
            name=data["name"],
            full_name=data["full_name"],
            owner=GitHubUser(**data["owner"]),
            private=data["private"],
            html_url=data["html_url"],
            description=data.get("description"),
            language=data.get("language"),
            languages_url=data["languages_url"],
            size=data["size"],
            default_branch=data["default_branch"],
            created_at=datetime.fromisoformat(data["created_at"].replace("Z", "+00:00")),
            updated_at=datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00")),
            clone_url=data["clone_url"],
            ssh_url=data["ssh_url"]
        )
    
    async def get_pull_request(self, repo_url: str, pr_number: int) -> PullRequest:
        """Get pull request information."""
        owner, repo = self._parse_repo_url(repo_url)
        data = await self._make_request("GET", f"/repos/{owner}/{repo}/pulls/{pr_number}")
        
        return PullRequest(
            id=data["id"],
            node_id=data["node_id"],
            number=data["number"],
            title=data["title"],
            body=data.get("body"),
            state=data["state"],
            user=GitHubUser(**data["user"]),
            created_at=datetime.fromisoformat(data["created_at"].replace("Z", "+00:00")),
            updated_at=datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00")),
            closed_at=datetime.fromisoformat(data["closed_at"].replace("Z", "+00:00")) if data.get("closed_at") else None,
            merged_at=datetime.fromisoformat(data["merged_at"].replace("Z", "+00:00")) if data.get("merged_at") else None,
            merge_commit_sha=data.get("merge_commit_sha"),
            head=data["head"],
            base=data["base"],
            html_url=data["html_url"],
            diff_url=data["diff_url"],
            patch_url=data["patch_url"],
            commits=data["commits"],
            additions=data["additions"],
            deletions=data["deletions"],
            changed_files=data["changed_files"],
            mergeable=data.get("mergeable"),
            mergeable_state=data.get("mergeable_state")
        )
    
    async def get_pr_files(self, repo_url: str, pr_number: int) -> List[GitHubFile]:
        """Get files changed in a pull request."""
        owner, repo = self._parse_repo_url(repo_url)
        data = await self._make_request("GET", f"/repos/{owner}/{repo}/pulls/{pr_number}/files")
        
        files = []
        for file_data in data:
            files.append(GitHubFile(
                filename=file_data["filename"],
                status=file_data["status"],
                additions=file_data["additions"],
                deletions=file_data["deletions"],
                changes=file_data["changes"],
                blob_url=file_data["blob_url"],
                patch=file_data.get("patch"),
                previous_filename=file_data.get("previous_filename")
            ))
        
        return files
    
    async def get_pr_commits(self, repo_url: str, pr_number: int) -> List[GitHubCommit]:
        """Get commits in a pull request."""
        owner, repo = self._parse_repo_url(repo_url)
        data = await self._make_request("GET", f"/repos/{owner}/{repo}/pulls/{pr_number}/commits")
        
        commits = []
        for commit_data in data:
            commit = commit_data["commit"]
            commits.append(GitHubCommit(
                sha=commit_data["sha"],
                message=commit["message"],
                author=commit["author"],
                committer=commit["committer"],
                timestamp=datetime.fromisoformat(commit["author"]["date"].replace("Z", "+00:00")),
                html_url=commit_data["html_url"]
            ))
        
        return commits
    
    async def get_repository_languages(self, repo_url: str) -> Dict[str, int]:
        """Get repository languages."""
        owner, repo = self._parse_repo_url(repo_url)
        return await self._make_request("GET", f"/repos/{owner}/{repo}/languages")
    
    async def get_file_content(self, repo_url: str, file_path: str, ref: str = "main") -> Optional[str]:
        """Get content of a specific file."""
        try:
            owner, repo = self._parse_repo_url(repo_url)
            data = await self._make_request("GET", f"/repos/{owner}/{repo}/contents/{file_path}?ref={ref}")
            
            if data.get("encoding") == "base64":
                content = base64.b64decode(data["content"]).decode("utf-8")
                return content
            return data.get("content")
        except ValueError:
            return None
    
    async def get_pr_diff(self, repo_url: str, pr_number: int) -> PRDiff:
        """Get complete PR diff information."""
        files = await self.get_pr_files(repo_url, pr_number)
        commits = await self.get_pr_commits(repo_url, pr_number)
        
        total_additions = sum(f.additions for f in files)
        total_deletions = sum(f.deletions for f in files)
        total_changes = sum(f.changes for f in files)
        
        return PRDiff(
            pr_number=pr_number,
            repository=repo_url,
            files=files,
            total_additions=total_additions,
            total_deletions=total_deletions,
            total_changes=total_changes,
            commits=commits
        )
    
    async def get_repository_context(self, repo_url: str) -> RepositoryContext:
        """Get comprehensive repository context for analysis."""
        repository = await self.get_repository(repo_url)
        languages = await self.get_repository_languages(repo_url)
        
        # Get README content
        readme_content = None
        for readme_name in ["README.md", "README.rst", "README.txt", "README"]:
            content = await self.get_file_content(repo_url, readme_name, repository.default_branch)
            if content:
                readme_content = content
                break
        
        # Determine main language
        main_language = max(languages.items(), key=lambda x: x[1])[0] if languages else repository.language
        
        # Detect key files and technologies
        key_files = []
        technologies = []
        
        config_files = [
            "package.json", "requirements.txt", "Cargo.toml", "go.mod", 
            "pom.xml", "build.gradle", "composer.json", "Gemfile"
        ]
        
        for config_file in config_files:
            content = await self.get_file_content(repo_url, config_file, repository.default_branch)
            if content:
                key_files.append(config_file)
                
                # Detect technologies based on config files
                if config_file == "package.json":
                    technologies.extend(["Node.js", "JavaScript/TypeScript"])
                elif config_file == "requirements.txt":
                    technologies.append("Python")
                elif config_file == "Cargo.toml":
                    technologies.append("Rust")
                elif config_file == "go.mod":
                    technologies.append("Go")
                elif config_file in ["pom.xml", "build.gradle"]:
                    technologies.append("Java")
                elif config_file == "composer.json":
                    technologies.append("PHP")
                elif config_file == "Gemfile":
                    technologies.append("Ruby")
        
        return RepositoryContext(
            repository=repository,
            languages=languages,
            main_language=main_language,
            readme_content=readme_content,
            structure={},  # TODO: Implement directory structure parsing
            key_files=key_files,
            technologies=list(set(technologies))
        )