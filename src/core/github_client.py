import os
import json
import requests
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

class GitHubClient:
    """GitHub API client for fetching PR data"""
    
    def __init__(self):
        self.token = os.getenv('GITHUB_TOKEN')
        if not self.token:
            raise ValueError("GITHUB_TOKEN environment variable is required")
        
        self.headers = {
            'Authorization': f'token {self.token}',
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'PRhythm-Analyzer'
        }
        self.base_url = 'https://api.github.com'
    
    def get_latest_merged_pr(self, owner: str, repo: str, target_branch: str = 'main') -> Optional[Dict]:
        """Get the latest merged PR for the repository"""
        url = f"{self.base_url}/repos/{owner}/{repo}/pulls"
        params = {
            'state': 'closed',
            'base': target_branch,
            'sort': 'updated',
            'direction': 'desc',
            'per_page': 100
        }
        
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        
        pulls = response.json()
        
        # Find the most recently merged PR
        for pr in pulls:
            if pr.get('merged_at') is not None:
                return self._enrich_pr_data(pr, owner, repo)
        
        return None

    def get_new_merged_prs(
        self, 
        owner: str, 
        repo: str, 
        since_time: str, 
        target_branch: str = 'main'
    ) -> List[Dict]:
        """Get newly merged PRs since the specified time
        
        Args:
            owner: Repository owner
            repo: Repository name
            since_time: ISO format timestamp (e.g., "2025-01-15T10:30:00Z")
            target_branch: Target branch name
            
        Returns:
            List of merged PR data dictionaries, sorted by merge time (newest first)
        """
        url = f"{self.base_url}/repos/{owner}/{repo}/pulls"
        params = {
            'state': 'closed',
            'base': target_branch,
            'sort': 'updated',
            'direction': 'desc',
            'per_page': 100,
            'since': since_time
        }
        
        merged_prs = []
        page = 1
        
        while True:
            params['page'] = page
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            
            pulls = response.json()
            
            if not pulls:
                break
                
            # Filter for actually merged PRs and add to list
            for pr in pulls:
                if pr.get('merged_at') is not None:
                    # Check if merged after since_time
                    merged_at = pr.get('merged_at')
                    if merged_at and merged_at > since_time:
                        enriched_pr = self._enrich_pr_data(pr, owner, repo)
                        merged_prs.append(enriched_pr)
            
            # Stop if we've seen older PRs (since we're sorting by updated desc)
            if any(pr.get('updated_at', '') <= since_time for pr in pulls):
                break
                
            page += 1
            
            # Safety limit to avoid infinite loops
            if page > 10:
                break
        
        # Sort by merged time, newest first
        merged_prs.sort(key=lambda x: x.get('merged_at', ''), reverse=True)
        
        return merged_prs

    def get_pr_data(self, owner: str, repo: str, pr_number: int) -> Dict:
        """Get detailed data for a specific PR
        
        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: PR number
            
        Returns:
            Enriched PR data dictionary
        """
        url = f"{self.base_url}/repos/{owner}/{repo}/pulls/{pr_number}"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        
        pr = response.json()
        return self._enrich_pr_data(pr, owner, repo)
    
    def _enrich_pr_data(self, pr: Dict, owner: str, repo: str) -> Dict:
        """Enrich PR data with additional information"""
        pr_number = pr['number']
        
        # Get PR files
        files_url = f"{self.base_url}/repos/{owner}/{repo}/pulls/{pr_number}/files"
        files_response = requests.get(files_url, headers=self.headers)
        files = files_response.json() if files_response.status_code == 200 else []
        
        # Get PR commits
        commits_url = f"{self.base_url}/repos/{owner}/{repo}/pulls/{pr_number}/commits"
        commits_response = requests.get(commits_url, headers=self.headers)
        commits = commits_response.json() if commits_response.status_code == 200 else []
        
        # Calculate statistics
        files_changed = len(files)
        lines_added = sum(f.get('additions', 0) for f in files)
        lines_deleted = sum(f.get('deletions', 0) for f in files)
        lines_changed = lines_added + lines_deleted
        
        return {
            'id': pr['id'],
            'number': pr['number'],
            'title': pr['title'],
            'body': pr['body'],
            'state': pr['state'],
            'created_at': pr['created_at'],
            'updated_at': pr['updated_at'],
            'merged_at': pr['merged_at'],
            'merge_commit_sha': pr['merge_commit_sha'],
            'author': {
                'login': pr['user']['login'],
                'id': pr['user']['id'],
                'avatar_url': pr['user']['avatar_url']
            },
            'base': {
                'ref': pr['base']['ref'],
                'sha': pr['base']['sha'],
                'repo': pr['base']['repo']['full_name']
            },
            'head': {
                'ref': pr['head']['ref'],
                'sha': pr['head']['sha'],
                'repo': pr['head']['repo']['full_name'] if pr['head']['repo'] else None
            },
            'labels': [label['name'] for label in pr['labels']],
            'assignees': [assignee['login'] for assignee in pr['assignees']],
            'reviewers': self._get_pr_reviewers(owner, repo, pr_number),
            'statistics': {
                'files_changed': files_changed,
                'lines_added': lines_added,
                'lines_deleted': lines_deleted,
                'lines_changed': lines_changed,
                'commits_count': len(commits)
            },
            'files': files,
            'commits': commits
        }
    
    def _get_pr_reviewers(self, owner: str, repo: str, pr_number: int) -> List[str]:
        """Get PR reviewers"""
        url = f"{self.base_url}/repos/{owner}/{repo}/pulls/{pr_number}/reviews"
        response = requests.get(url, headers=self.headers)
        if response.status_code == 200:
            reviews = response.json()
            return list(set(review['user']['login'] for review in reviews))
        return []
    
    def check_rate_limit(self) -> Dict:
        """Check current API rate limit status"""
        url = f"{self.base_url}/rate_limit"
        response = requests.get(url, headers=self.headers)
        return response.json()
    
    def parse_github_url(self, github_url: str) -> Tuple[str, str]:
        """Parse GitHub repository URL to extract owner and repo.
        
        Args:
            github_url: GitHub repository URL
            
        Returns:
            Tuple of (owner, repo)
            
        Raises:
            ValueError: If URL format is invalid
        """
        parsed = urlparse(github_url)
        
        if parsed.netloc not in ['github.com', 'www.github.com']:
            raise ValueError(f"Invalid GitHub URL: {github_url}")
        
        path_parts = parsed.path.strip('/').split('/')
        
        if len(path_parts) < 2:
            raise ValueError(f"Invalid GitHub repository URL format: {github_url}")
        
        owner = path_parts[0]
        repo = path_parts[1]
        
        # Remove .git suffix if present
        if repo.endswith('.git'):
            repo = repo[:-4]
        
        return owner, repo
    
    def get_repo_name_from_url(self, github_url: str) -> str:
        """Extract repository name from GitHub URL.
        
        Args:
            github_url: GitHub repository URL
            
        Returns:
            Repository name for use in workspace paths
        """
        owner, repo = self.parse_github_url(github_url)
        return repo