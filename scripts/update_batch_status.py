#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Update the PR processing status file after batch operations.
This script should be called after batch operations to update the status.
"""

import json
import sys
import os
import argparse
from pathlib import Path
from datetime import datetime

def get_status_file_path(project_root):
    """
    Get the path to the status file
    
    Args:
        project_root: Project root directory
        
    Returns:
        Path: Path to the status file
    """
    status_dir = project_root / "repos"
    status_dir.mkdir(exist_ok=True)
    return status_dir / "pr_processing_status.json"

def read_status_file(status_file_path):
    """
    Read the status file or create a new one if it doesn't exist
    
    Args:
        status_file_path: Path to the status file
        
    Returns:
        dict: Status information
    """
    if status_file_path.exists():
        try:
            with open(status_file_path, 'r') as file:
                return json.load(file)
        except Exception as e:
            print(f"Error reading status file: {e}")
            # Return a new status object if there's an error
    
    # Default status structure
    return {
        "repositories": {},
        "last_updated": datetime.now().isoformat(),
        "batch_operations": []
    }

def write_status_file(status_file_path, status_data):
    """
    Write status information to the status file
    
    Args:
        status_file_path: Path to the status file
        status_data: Status information to write
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Update the last updated timestamp
        status_data["last_updated"] = datetime.now().isoformat()
        
        with open(status_file_path, 'w') as file:
            json.dump(status_data, file, indent=2)
        return True
    except Exception as e:
        print(f"Error writing status file: {e}")
        return False

def update_batch_status(status_data, repo, pr_number, operation_name, success=True):
    """
    Update the batch operation status for a repository
    
    Args:
        status_data: Current status data
        repo: Repository name
        pr_number: PR number that was processed
        operation_name: Name of the batch operation
        success: Whether the operation was successful
        
    Returns:
        bool: True if status was updated, False otherwise
    """
    # Initialize repository entry if it doesn't exist
    if repo not in status_data["repositories"]:
        status_data["repositories"][repo] = {
            "latest_processed_pr": 0,
            "last_updated": None
        }
    
    repo_status = status_data["repositories"][repo]
    
    # Update the latest processed PR number if higher
    if pr_number > repo_status["latest_processed_pr"]:
        repo_status["latest_processed_pr"] = pr_number
        repo_status["last_updated"] = datetime.now().isoformat()
    
    # Add batch operation record
    batch_operation = {
        "timestamp": datetime.now().isoformat(),
        "repository": repo,
        "pr_number": pr_number,
        "operation": operation_name,
        "success": success
    }
    
    if "batch_operations" not in status_data:
        status_data["batch_operations"] = []
    
    status_data["batch_operations"].append(batch_operation)
    
    # Keep only the last 100 batch operations to prevent the file from growing too large
    if len(status_data["batch_operations"]) > 100:
        status_data["batch_operations"] = status_data["batch_operations"][-100:]
    
    return True

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Update PR processing status after batch operations')
    parser.add_argument('--repo', required=True, help='Repository name (owner/repo)')
    parser.add_argument('--pr', required=True, type=int, help='PR number that was processed')
    parser.add_argument('--operation', required=True, help='Name of the batch operation')
    parser.add_argument('--status', choices=['success', 'failure'], default='success',
                        help='Status of the operation (success/failure)')
    return parser.parse_args()

def main():
    """Main function"""
    # Parse command line arguments
    args = parse_arguments()
    
    # Get project root directory
    script_dir = Path(os.path.dirname(os.path.abspath(__file__)))
    project_root = script_dir.parent
    
    # Get status file path
    status_file_path = get_status_file_path(project_root)
    
    # Read current status
    status_data = read_status_file(status_file_path)
    
    # Update batch status
    success = args.status == 'success'
    if update_batch_status(status_data, args.repo, args.pr, args.operation, success):
        print(f"Updated batch status for {args.repo} PR #{args.pr} - Operation: {args.operation} - Status: {args.status}")
    
    # Write status file
    if write_status_file(status_file_path, status_data):
        print(f"Status file updated: {status_file_path}")
    else:
        print("Failed to update status file")
        sys.exit(1)

if __name__ == "__main__":
    main() 