import os
import json
import requests
from datetime import datetime
from typing import Dict, List, Optional

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