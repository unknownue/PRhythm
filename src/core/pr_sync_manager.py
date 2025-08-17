"""PR synchronization manager for PRhythm."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from .github_client import GitHubClient


class PRSyncManager:
    """Manager for PR synchronization with GitHub repositories."""
    
    def __init__(self, workspace_base_path: str = "./workspaces"):
        """Initialize the PR sync manager.
        
        Args:
            workspace_base_path: Base path for workspace directories
        """
        self.workspace_base_path = Path(workspace_base_path)
        self.github_client = GitHubClient()
    
    def get_sync_state_path(self, repo_name: str) -> Path:
        """Get the path to sync state file for a repository.
        
        Args:
            repo_name: Repository name (e.g., "bevy", "test-repo")
            
        Returns:
            Path to the sync_state.json file
        """
        repo_workspace = self.workspace_base_path / repo_name
        return repo_workspace / "sync_state.json"
    
    def load_sync_state(self, repo_name: str) -> Dict:
        """Load sync state for a repository.
        
        Args:
            repo_name: Repository name
            
        Returns:
            Sync state dictionary with keys: last_synced_pr, last_sync_time, repository
        """
        sync_state_path = self.get_sync_state_path(repo_name)
        
        if not sync_state_path.exists():
            # Return default state if file doesn't exist
            return {
                "last_synced_pr": None,
                "last_sync_time": None,
                "repository": None
            }
        
        try:
            with open(sync_state_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Failed to load sync state from {sync_state_path}: {e}")
            return {
                "last_synced_pr": None,
                "last_sync_time": None,
                "repository": None
            }
    
    def save_sync_state(self, repo_name: str, sync_state: Dict) -> None:
        """Save sync state for a repository.
        
        Args:
            repo_name: Repository name
            sync_state: Sync state dictionary to save
        """
        sync_state_path = self.get_sync_state_path(repo_name)
        
        # Ensure the directory exists
        sync_state_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            with open(sync_state_path, 'w', encoding='utf-8') as f:
                json.dump(sync_state, f, indent=2, ensure_ascii=False)
        except IOError as e:
            print(f"Error: Failed to save sync state to {sync_state_path}: {e}")
            raise
    
    
    def sync_latest_prs(
        self, 
        github_url: str, 
        target_branch: str = 'main',
        max_prs: int = 10
    ) -> List[Dict]:
        """Synchronize latest PRs from a GitHub repository.
        
        Args:
            github_url: GitHub repository URL
            target_branch: Target branch name
            max_prs: Maximum number of PRs to sync
            
        Returns:
            List of newly discovered PR data
        """
        # Parse repository information
        owner, repo = self.github_client.parse_github_url(github_url)
        repo_name = self.github_client.get_repo_name_from_url(github_url)
        repo_full_name = f"{owner}/{repo}"
        
        print(f"Syncing PRs for repository: {repo_full_name}")
        
        # Load current sync state
        sync_state = self.load_sync_state(repo_name)
        last_sync_time = sync_state.get("last_sync_time")
        
        # Determine time range for PR query
        if last_sync_time:
            print(f"Finding PRs merged after: {last_sync_time}")
            new_prs = self.github_client.get_new_merged_prs(
                owner, repo, last_sync_time, target_branch
            )
        else:
            print("First-time sync: getting latest merged PR")
            latest_pr = self.github_client.get_latest_merged_pr(owner, repo, target_branch)
            new_prs = [latest_pr] if latest_pr else []
        
        # Limit the number of PRs to process
        if len(new_prs) > max_prs:
            print(f"Found {len(new_prs)} new PRs, limiting to {max_prs} most recent")
            new_prs = new_prs[:max_prs]
        
        # Update sync state with the latest PR and current time
        current_time = datetime.now(timezone.utc).isoformat()
        
        if new_prs:
            latest_pr = new_prs[0]  # Most recent PR
            updated_sync_state = {
                "last_synced_pr": latest_pr["number"],
                "last_synced_pr_title": latest_pr["title"],
                "last_sync_time": current_time,
                "repository": repo_full_name
            }
            
            print(f"Found {len(new_prs)} new merged PR(s)")
            for pr in new_prs:
                print(f"  - PR #{pr['number']}: {pr['title']}")
        else:
            # Update sync time even if no new PRs
            updated_sync_state = sync_state.copy()
            updated_sync_state["last_sync_time"] = current_time
            updated_sync_state["repository"] = repo_full_name
            
            print("No new merged PRs found")
        
        # Save updated sync state
        self.save_sync_state(repo_name, updated_sync_state)
        
        return new_prs
    
    def get_sync_status(self, repo_name: str) -> Dict:
        """Get synchronization status for a repository.
        
        Args:
            repo_name: Repository name
            
        Returns:
            Dictionary containing sync status information
        """
        sync_state = self.load_sync_state(repo_name)
        sync_state_path = self.get_sync_state_path(repo_name)
        
        return {
            "repository": sync_state.get("repository", "Unknown"),
            "last_synced_pr": sync_state.get("last_synced_pr"),
            "last_synced_pr_title": sync_state.get("last_synced_pr_title"),
            "last_sync_time": sync_state.get("last_sync_time"),
            "sync_state_file": str(sync_state_path),
            "file_exists": sync_state_path.exists()
        }
    
    def initialize_repo_sync(
        self, 
        github_url: str, 
        pr_number: Optional[int] = None,
        target_branch: str = 'main'
    ) -> Dict:
        """Initialize synchronization for a new repository.
        
        Args:
            github_url: GitHub repository URL
            pr_number: Optional specific PR number to use as baseline
            target_branch: Target branch name
            
        Returns:
            Initial sync state
        """
        owner, repo = self.github_client.parse_github_url(github_url)
        repo_name = self.github_client.get_repo_name_from_url(github_url)
        repo_full_name = f"{owner}/{repo}"
        
        print(f"Initializing sync for repository: {repo_full_name}")
        
        current_time = datetime.now(timezone.utc).isoformat()
        
        if pr_number:
            # Use specific PR number
            print(f"Using PR #{pr_number} as baseline")
            try:
                pr_data = self.github_client.get_pr_data(owner, repo, pr_number)
                initial_sync_state = {
                    "last_synced_pr": pr_data["number"],
                    "last_synced_pr_title": pr_data["title"],
                    "last_sync_time": current_time,
                    "repository": repo_full_name
                }
                print(f"Baseline established with PR #{pr_data['number']}: {pr_data['title']}")
                
                # Save initial sync state
                self.save_sync_state(repo_name, initial_sync_state)
                
                # Save PR data to workspace (reuse already fetched data)
                self._save_pr_data_to_workspace(repo_name, initial_sync_state, pr_data)
                
                return initial_sync_state
                
            except Exception as e:
                raise ValueError(f"Error: PR #{pr_number} not found in repository {repo_full_name}. {str(e)}")
        else:
            # Get the latest merged PR to establish baseline
            latest_pr = self.github_client.get_latest_merged_pr(owner, repo, target_branch)
            
            if latest_pr:
                initial_sync_state = {
                    "last_synced_pr": latest_pr["number"],
                    "last_synced_pr_title": latest_pr["title"],
                    "last_sync_time": current_time,
                    "repository": repo_full_name
                }
                print(f"Baseline established with PR #{latest_pr['number']}: {latest_pr['title']}")
                
                # Save initial sync state
                self.save_sync_state(repo_name, initial_sync_state)
                
                # Save PR data to workspace (reuse already fetched data)
                self._save_pr_data_to_workspace(repo_name, initial_sync_state, latest_pr)
                
            else:
                initial_sync_state = {
                    "last_synced_pr": None,
                    "last_synced_pr_title": None,
                    "last_sync_time": current_time,
                    "repository": repo_full_name
                }
                print("No merged PRs found, starting with empty baseline")
                
                # Save initial sync state
                self.save_sync_state(repo_name, initial_sync_state)
        
        return initial_sync_state

    def _save_pr_data_to_workspace(self, repo_name: str, sync_state: Dict, pr_data: Optional[Dict] = None) -> None:
        """Save PR data to workspace temp directory.
        
        Args:
            repo_name: Repository name
            sync_state: Current sync state containing PR information
            pr_data: Optional PR data to save (if None, will fetch from API)
        """
        try:
            pr_number = sync_state.get("last_synced_pr")
            repository = sync_state.get("repository")
            
            if not pr_number or not repository:
                return
            
            # Use provided PR data or fetch from API
            if pr_data is None:
                # Parse repository owner and name
                owner, repo = repository.split('/')
                # Get detailed PR data
                pr_data = self.github_client.get_pr_data(owner, repo, pr_number)
            
            # Save to workspace temp directory
            workspace_temp_path = self.workspace_base_path / repo_name / "temp"
            workspace_temp_path.mkdir(parents=True, exist_ok=True)
            
            pr_file_path = workspace_temp_path / f"pr_{pr_number}_data.json"
            
            with open(pr_file_path, 'w', encoding='utf-8') as f:
                json.dump(pr_data, f, indent=2, ensure_ascii=False)
            
            print(f"PR data saved to: {pr_file_path}")
            
        except Exception as e:
            print(f"Warning: Failed to save PR data to workspace: {str(e)}")

