#!/usr/bin/env python3

import os
import sys
import json
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from core.github_client import GitHubClient
from core.config_manager import ConfigManager

def main():
    """Fetch latest merged PR data for bevy repository"""
    
    # Load environment variables
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        # dotenv not available, continue with existing environment
        pass
    
    try:
        # Initialize clients
        github_client = GitHubClient()
        config_manager = ConfigManager()
        
        # Get repository information
        owner, repo = config_manager.get_repo_info('bevy')
        repo_config = config_manager.load_repository_config('bevy')
        target_branch = repo_config['repository']['default_branch']
        
        print(f"Fetching latest merged PR for {owner}/{repo} (branch: {target_branch})")
        
        # Check API rate limit
        rate_limit = github_client.check_rate_limit()
        remaining = rate_limit['rate']['remaining']
        print(f"GitHub API rate limit remaining: {remaining}")
        
        if remaining < 10:
            print("Warning: Low API rate limit remaining")
        
        # Get latest merged PR
        pr_data = github_client.get_latest_merged_pr(owner, repo, target_branch)
        
        if not pr_data:
            print("No merged PRs found")
            return
        
        # Display PR information
        print("\n" + "="*60)
        print(f"Latest Merged PR: #{pr_data['number']}")
        print("="*60)
        print(f"Title: {pr_data['title']}")
        print(f"Author: {pr_data['author']['login']}")
        print(f"Merged: {pr_data['merged_at']}")
        print(f"Merge Commit: {pr_data['merge_commit_sha'][:8] if pr_data['merge_commit_sha'] else 'N/A'}")
        print(f"Files Changed: {pr_data['statistics']['files_changed']}")
        print(f"Lines Changed: {pr_data['statistics']['lines_changed']} (+{pr_data['statistics']['lines_added']} -{pr_data['statistics']['lines_deleted']})")
        print(f"Commits: {pr_data['statistics']['commits_count']}")
        print(f"Labels: {', '.join(pr_data['labels']) if pr_data['labels'] else 'None'}")
        if pr_data['reviewers']:
            print(f"Reviewers: {', '.join(pr_data['reviewers'])}")
        print(f"URL: https://github.com/{owner}/{repo}/pull/{pr_data['number']}")
        
        # Show PR body preview (first 200 characters)
        if pr_data['body']:
            body_preview = pr_data['body'][:200].replace('\n', ' ')
            if len(pr_data['body']) > 200:
                body_preview += "..."
            print(f"Description: {body_preview}")
        
        # Save PR data to workspace
        workspace_dir = Path("workspaces/bevy")
        pr_data_file = workspace_dir / "temp" / f"pr_{pr_data['number']}_data.json"
        
        pr_data_file.parent.mkdir(parents=True, exist_ok=True)
        with open(pr_data_file, 'w', encoding='utf-8') as f:
            json.dump(pr_data, f, indent=2, ensure_ascii=False)
        
        print(f"\nPR data saved to: {pr_data_file}")
        
        # Update last processed PR metadata
        metadata_file = workspace_dir / "metadata" / "last_processed_pr.json"
        last_pr_data = {
            "pr_number": pr_data['number'],
            "pr_id": pr_data['id'],
            "processed_at": datetime.utcnow().isoformat() + "Z",
            "commit_sha": pr_data['merge_commit_sha']
        }
        
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(last_pr_data, f, indent=2)
        
        print(f"Metadata updated: {metadata_file}")
        
        # Update analysis history
        history_file = workspace_dir / "metadata" / "analysis_history.json"
        with open(history_file, 'r', encoding='utf-8') as f:
            history = json.load(f)
        
        history['analyses'].append({
            "pr_number": pr_data['number'],
            "fetched_at": datetime.utcnow().isoformat() + "Z",
            "status": "data_fetched"
        })
        history['last_updated'] = datetime.utcnow().isoformat() + "Z"
        
        with open(history_file, 'w', encoding='utf-8') as f:
            json.dump(history, f, indent=2)
        
        print("Analysis history updated")
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()