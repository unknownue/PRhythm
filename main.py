#!/usr/bin/env python3
"""
PRhythm main entry point.
"""

import argparse
import asyncio
import sys
import os
from pathlib import Path

# Add src and tests to path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir / 'src'))
sys.path.insert(0, str(current_dir / 'tests'))

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # dotenv not available, continue with existing environment
    pass

from test_llm_connection import test_llm_connection


async def analyze_pr_workflow(pr_input: str, stop_at: str = None, output_prompt_dir: str = None):
    """Execute PR analysis workflow.
    
    Args:
        pr_input: PR URL or path to local JSON file
        stop_at: Optional node to stop execution at
        output_prompt_dir: Optional directory to save analysis prompt
    """
    try:
        # Import here to avoid circular imports and ensure path is set up
        from core.workflow_manager import WorkflowManager
        from agents.configuration import AgentConfiguration
        
        print("=== PRhythm PR Analysis ===")
        print(f"Input: {pr_input}")
        if stop_at:
            print(f"Stop at: {stop_at}")
        if output_prompt_dir:
            print(f"Prompt output directory: {output_prompt_dir}")
        print("=" * 50)
        
        # Initialize workflow manager
        config = AgentConfiguration()
        manager = WorkflowManager(config)
        
        # Execute analysis
        print("Starting PR analysis workflow...")
        result = await manager.analyze_pr(pr_input, stop_at, output_prompt_dir=output_prompt_dir)
        
        # Display results
        print("\n=== Analysis Results ===")
        print(f"Success: {result['success']}")
        
        if result.get('error'):
            print(f"Error: {result['error']}")
            return 1
        
        if result.get('stopped_at'):
            print(f"Stopped at: {result['stopped_at']}")
        
        if result.get('scheme_used'):
            print(f"Scheme used: {result['scheme_used']}")
        
        if result.get('analysis_prompt_saved'):
            print(f"Analysis prompt saved to: {result['analysis_prompt_saved']}")
        
        if result.get('final_report'):
            print(f"\nFinal Report:\n{result['final_report']}")
        
        if result.get('analysis_metadata'):
            print(f"\nMetadata: {result['analysis_metadata']}")
        
        print("=" * 50)
        return 0
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return 1




def show_sync_status(repo_name: str):
    """Show synchronization status for repository.
    
    Args:
        repo_name: Repository name
    """
    try:
        from core.pr_sync_manager import PRSyncManager
        
        print("=== PRhythm Sync Status ===")
        print(f"Repository: {repo_name}")
        print("=" * 50)
        
        # Initialize sync manager
        sync_manager = PRSyncManager()
        
        # Get sync status
        status = sync_manager.get_sync_status(repo_name)
        
        print(f"Repository: {status['repository']}")
        print(f"Last synced PR: {status['last_synced_pr']}")
        if status.get('last_synced_pr_title'):
            print(f"PR Title: {status['last_synced_pr_title']}")
        print(f"Last sync time: {status['last_sync_time']}")
        print(f"Sync state file: {status['sync_state_file']}")
        print(f"File exists: {status['file_exists']}")
        
        print("=" * 50)
        return 0
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return 1


def init_repo_sync(repo_url: str, pr_number: str):
    """Initialize synchronization for a new repository with a specific PR.
    
    Args:
        repo_url: GitHub repository URL
        pr_number: PR number to use as baseline
    """
    try:
        from core.pr_sync_manager import PRSyncManager
        
        print("=== PRhythm Repository Initialization ===")
        print(f"Repository: {repo_url}")
        print(f"Baseline PR: #{pr_number}")
        print("=" * 50)
        
        # Initialize sync manager
        sync_manager = PRSyncManager()
        
        # Initialize repository sync with specific PR
        initial_state = sync_manager.initialize_repo_sync(repo_url, int(pr_number))
        
        print("=" * 50)
        print("Repository initialization completed.")
        print(f"Repository: {initial_state['repository']}")
        print(f"Baseline PR: {initial_state['last_synced_pr']}")
        print(f"Initialized at: {initial_state['last_sync_time']}")
        return 0
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return 1


def main():
    """Main entry point for PRhythm system."""
    
    parser = argparse.ArgumentParser(
        description="PRhythm - GitHub PR Analysis System",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '--test_llm_connection',
        action='store_true',
        help='Test basic LLM connection with a hello world message'
    )
    
    parser.add_argument(
        '--test_llm_model',
        type=str,
        default=None,
        help='Specify LLM provider for connection test (e.g., openai, anthropic, google, ollama)'
    )
    
    parser.add_argument(
        '--analyze-pr',
        type=str,
        help='Analyze a PR. Provide GitHub PR URL or path to local JSON file containing PR data'
    )
    
    parser.add_argument(
        '--stop-at',
        type=str,
        choices=['initialize_analysis', 'select_scheme', 'collect_data', 'generate_analysis', 'process_report'],
        help='Stop workflow execution at the specified node'
    )
    
    parser.add_argument(
        '--output-prompt-dir',
        type=str,
        help='Directory to save the analysis prompt (used with generate_analysis)'
    )
    
    parser.add_argument(
        '--show-sync-status',
        type=str,
        metavar='REPO_NAME',
        help='Show synchronization status for the specified repository name'
    )
    
    parser.add_argument(
        '--init-repo-sync',
        type=str,
        nargs=2,
        metavar=('REPO_URL', 'PR_NUMBER'),
        help='Initialize synchronization for a new GitHub repository with a specific PR number'
    )
    
    args = parser.parse_args()
    
    # Handle PR analysis
    if getattr(args, 'analyze_pr', None):
        stop_at = getattr(args, 'stop_at', None)
        output_prompt_dir = getattr(args, 'output_prompt_dir', None)
        return asyncio.run(analyze_pr_workflow(args.analyze_pr, stop_at, output_prompt_dir))
    
    # Handle sync status display
    if getattr(args, 'show_sync_status', None):
        return show_sync_status(args.show_sync_status)
    
    # Handle repository initialization
    if getattr(args, 'init_repo_sync', None):
        repo_url, pr_number = args.init_repo_sync
        return init_repo_sync(repo_url, pr_number)
    
    # Handle test LLM connection
    if args.test_llm_connection:
        print("=" * 50)
        print("PRhythm LLM Connection Test")
        print("=" * 50)
        
        success = test_llm_connection(model_override=args.test_llm_model)
        
        print("=" * 50)
        if success:
            print("Test Result: ✅ Success")
            return 0
        else:
            print("Test Result: ❌ Failed")
            return 1
    
    # If no arguments provided, show help
    if len(sys.argv) == 1:
        parser.print_help()
        return 0
    
    return 0


if __name__ == "__main__":
    sys.exit(main())