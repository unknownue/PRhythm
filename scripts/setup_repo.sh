#!/bin/bash

# PRhythm Repository Setup Script
# Usage: ./setup_repo.sh <github_repo_url>
# Example: ./setup_repo.sh https://github.com/user/example-repo

set -e

# Check if URL is provided
if [ $# -eq 0 ]; then
    echo "Error: Please provide a GitHub repository URL"
    echo "Usage: $0 <github_repo_url>"
    echo "Example: $0 https://github.com/user/example-repo"
    exit 1
fi

GITHUB_URL="$1"

# Extract repository name from URL
# Handles both https://github.com/user/repo and https://github.com/user/repo.git
# Remove trailing slash first, then extract last part
REPO_NAME=$(echo "$GITHUB_URL" | sed 's|/$||' | sed 's|.*/||' | sed 's|\.git$||')

if [ -z "$REPO_NAME" ]; then
    echo "Error: Could not extract repository name from URL: $GITHUB_URL"
    exit 1
fi

echo "Setting up workspace for repository: $REPO_NAME"
echo "GitHub URL: $GITHUB_URL"

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Create workspace directory structure
WORKSPACE_DIR="$PROJECT_ROOT/workspaces/$REPO_NAME"

echo "Creating workspace directory structure..."

# Create main workspace directories
mkdir -p "$WORKSPACE_DIR/repo-previous"
mkdir -p "$WORKSPACE_DIR/repo-merged"
mkdir -p "$WORKSPACE_DIR/reports"
mkdir -p "$WORKSPACE_DIR/temp"

# Create reports subdirectories by year and month
CURRENT_YEAR=$(date +%Y)
CURRENT_MONTH=$(date +%m)
mkdir -p "$WORKSPACE_DIR/reports/$CURRENT_YEAR/$CURRENT_MONTH"

echo "Workspace directories created successfully at: $WORKSPACE_DIR"

# Create initial sync state file for PR tracking
echo "Creating initial sync state file..."

cat > "$WORKSPACE_DIR/sync_state.json" << EOF
{
  "last_synced_pr": null,
  "last_synced_pr_title": null,
  "last_sync_time": null,
  "repository": null
}
EOF

# Create reports index
cat > "$WORKSPACE_DIR/reports/index.json" << EOF
{
  "repository": "$REPO_NAME",
  "reports": [],
  "last_updated": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
}
EOF

echo "Initial files created successfully."

# Create repository configuration template
CONFIG_DIR="$PROJECT_ROOT/config/repositories"
CONFIG_FILE="$CONFIG_DIR/${REPO_NAME}.json"

# Create config directory if it doesn't exist
mkdir -p "$CONFIG_DIR"

if [ ! -f "$CONFIG_FILE" ]; then
    echo "Creating repository configuration template..."
    
    cat > "$CONFIG_FILE" << EOF
{
  "repository": {
    "name": "$REPO_NAME",
    "full_name": "$(echo "$GITHUB_URL" | sed 's|https://github.com/||' | sed 's|/$||' | sed 's|\.git$||')",
    "github_url": "$GITHUB_URL",
    "clone_url": "$GITHUB_URL",
    "default_branch": "main",
    "enabled": true,
    "description": "Auto-generated configuration for $REPO_NAME"
  },
  "analysis": {
    "trigger": {
      "on_pr_merged": true,
      "on_pr_closed": false,
      "specific_branches": ["main", "develop"],
      "exclude_branches": ["feature/*", "hotfix/*"]
    },
    "schemes": {
      "default": "general_review",
      "fallback": "general_review",
      "conditions": [
        {
          "description": "Security review for security-labeled PRs",
          "condition": {
            "type": "label_contains",
            "value": "security"
          },
          "scheme": "security_audit",
          "priority": "high"
        },
        {
          "description": "Performance check for large PRs",
          "condition": {
            "type": "and",
            "conditions": [
              {
                "type": "files_changed",
                "operator": ">",
                "value": 20
              },
              {
                "type": "lines_changed",
                "operator": ">",
                "value": 500
              }
            ]
          },
          "scheme": "performance_check",
          "priority": "medium"
        }
      ]
    }
  },
  "workspace": {
    "previous_dir": "workspaces/$REPO_NAME/repo-previous",
    "merged_dir": "workspaces/$REPO_NAME/repo-merged",
    "reports_dir": "workspaces/$REPO_NAME/reports",
    "temp_dir": "workspaces/$REPO_NAME/temp",
    "cleanup_temp_after_hours": 24
  },
  "custom_config": {
    "exclude_patterns": [
      "*.pyc",
      "__pycache__/",
      ".git/",
      "node_modules/",
      ".pytest_cache/",
      "venv/",
      "env/"
    ]
  },
  "notification": {
    "enabled": true,
    "channels": ["github_comment"],
    "github_comment": {
      "enabled": true,
      "add_summary": true,
      "mention_author": true
    }
  }
}
EOF

    echo "Repository configuration created at: $CONFIG_FILE"
else
    echo "Repository configuration already exists at: $CONFIG_FILE"
fi

# Clone the repository to both directories
echo "Cloning repository..."

if [ ! -d "$WORKSPACE_DIR/repo-previous/.git" ]; then
    echo "Cloning to repo-previous directory..."
    git clone "$GITHUB_URL" "$WORKSPACE_DIR/repo-previous"
else
    echo "Repository already exists in repo-previous, pulling latest changes..."
    cd "$WORKSPACE_DIR/repo-previous"
    git pull origin main || git pull origin master || echo "Warning: Could not pull latest changes"
    cd - > /dev/null
fi

if [ ! -d "$WORKSPACE_DIR/repo-merged/.git" ]; then
    echo "Cloning to repo-merged directory..."
    git clone "$GITHUB_URL" "$WORKSPACE_DIR/repo-merged"
else
    echo "Repository already exists in repo-merged, pulling latest changes..."
    cd "$WORKSPACE_DIR/repo-merged"
    git pull origin main || git pull origin master || echo "Warning: Could not pull latest changes"
    cd - > /dev/null
fi

echo ""
echo "✅ Repository setup completed successfully!"
echo "Repository: $REPO_NAME"
echo "Workspace: $WORKSPACE_DIR"
echo "Configuration: $CONFIG_FILE"
echo ""
echo "Next steps:"
echo "1. Initialize PR synchronization: python main.py --init-repo-sync $GITHUB_URL <PR_NUMBER>"
echo "2. Review and customize the repository configuration at: $CONFIG_FILE"  
echo "3. Check sync status: python main.py --show-sync-status $REPO_NAME"
echo "4. Analyze a PR: python main.py --analyze-pr <PR_URL_OR_FILE>"