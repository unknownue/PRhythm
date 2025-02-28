#!/bin/bash
# update_pr_reports.sh - Automatically update PR analysis reports
# This script automatically performs the following steps:
# 1. Check and update repositories
# 2. Get unsynchronized PRs
# 3. Get PR detailed information
# 4. Analyze PRs and generate reports
# 5. Update processing status

# Set environment variables (recommended to set via environment variables rather than hardcoding in the script)
# export GITHUB_TOKEN="your-github-token"
# export LLM_API_KEY="your-llm-api-key"
# export DEEPSEEK_API_KEY="your-deepseek-api-key"

# Project root directory
PROJECT_ROOT=$(dirname "$(readlink -f "$0")")
cd $PROJECT_ROOT

echo "===== PR Analysis Update Started $(date) ====="

# 1. Check and update repositories
echo "1. Checking and updating repositories..."
python scripts/check_pull_repo.py

# 2. Iterate through all configured repositories
echo "2. Getting configured repository list..."
REPOS=$(grep -A 100 "repositories:" config.yaml | grep -E "^\s*-\s+" | sed -E 's/\s*-\s+(.*)/\1/' | head -n 100)

# Get output language from config.yaml
OUTPUT_LANGUAGE=$(grep -A 3 "output:" config.yaml | grep "language:" | sed -E 's/.*language:\s*"([^"]+)".*/\1/' | head -1)
# Default to English if not specified
if [ -z "$OUTPUT_LANGUAGE" ]; then
  OUTPUT_LANGUAGE="en"
  echo "Output language not specified in config.yaml, defaulting to English (en)"
else
  echo "Using output language from config.yaml: $OUTPUT_LANGUAGE"
fi

# Get default provider from config.yaml
DEFAULT_PROVIDER=$(grep -A 3 "provider:" config.yaml | head -1 | sed -E 's/.*provider:\s*"([^"]+)".*/\1/' | head -1)
# Default to deepseek if not specified
if [ -z "$DEFAULT_PROVIDER" ]; then
  DEFAULT_PROVIDER="deepseek"
  echo "LLM provider not specified in config.yaml, defaulting to DeepSeek"
else
  echo "Using LLM provider from config.yaml: $DEFAULT_PROVIDER"
fi

for REPO in $REPOS; do
  echo "===== Processing repository: $REPO ====="
  
  # 3. Get unsynchronized PRs
  echo "3. Getting unsynchronized PRs..."
  # Extract PR numbers only, format: #NUMBER - TITLE
  UNSYNCED_PRS_OUTPUT=$(python scripts/track_merged_prs.py --repo "$REPO")
  # Use grep to get PR number lines, then sed to extract just the numbers
  UNSYNCED_PRS=$(echo "$UNSYNCED_PRS_OUTPUT" | grep -E "^#[0-9]+ - " | sed -E 's/^#([0-9]+) - .*/\1/')
  
  # Check if there are unsynchronized PRs
  PR_COUNT=$(echo "$UNSYNCED_PRS" | grep -v "^$" | wc -l)
  echo "Found $PR_COUNT unsynchronized PRs"
  
  if [ "$PR_COUNT" -eq "0" ]; then
    echo "No PRs to process, continuing to next repository"
    continue
  fi
  
  # 4. Process each unsynchronized PR
  echo "$UNSYNCED_PRS" | while read -r PR_NUMBER; do
    # 跳过空行
    if [ -z "$PR_NUMBER" ]; then
      continue
    fi
    
    echo "===== Processing PR #$PR_NUMBER ====="
    
    # 5. Get PR information
    echo "5. Getting PR detailed information..."
    python scripts/fetch_pr_info.py --repo "$REPO" --pr $PR_NUMBER
    
    # Get the latest PR information JSON file
    REPO_NAME=$(echo $REPO | cut -d'/' -f2)
    PR_JSON=$(ls -t output/$REPO_NAME/pr_${PR_NUMBER}_*.json 2>/dev/null | head -1)
    
    if [ -z "$PR_JSON" ]; then
      echo "Error: Cannot find JSON file for PR #$PR_NUMBER, skipping analysis"
      continue
    fi
    
    echo "Found PR information file: $PR_JSON"
    
    # 6. Analyze PR using configured language and provider
    echo "6. Analyzing PR and generating report in $OUTPUT_LANGUAGE language using $DEFAULT_PROVIDER provider..."
    python scripts/analyze_pr.py --json "$PR_JSON" --language "$OUTPUT_LANGUAGE" --provider "$DEFAULT_PROVIDER"
    
    # Check if analysis was successful
    if [ $? -eq 0 ]; then
      # 7. Update processing status
      echo "7. Updating PR processing status..."
      python scripts/track_merged_prs.py --repo "$REPO" --update --operation "analysis_complete" --status "success"
      echo "PR #$PR_NUMBER analysis completed"
    else
      echo "PR #$PR_NUMBER analysis failed"
      python scripts/track_merged_prs.py --repo "$REPO" --update --operation "analysis_complete" --status "failure"
    fi
    
    # Optional: Add delay to avoid API rate limits
    echo "Waiting 5 seconds before processing next PR..."
    sleep 5
  done
done

echo "===== PR Analysis Update Completed $(date) =====" 