#!/usr/bin/env python3

import argparse
import subprocess
import sys


def run_docker_command(command: str) -> None:
    """
    Run a docker command and handle its execution
    
    Args:
        command (str): The docker command to execute
    
    Raises:
        subprocess.CalledProcessError: If the docker command fails
    """
    try:
        subprocess.run(command, shell=True, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error executing docker command: {e}", file=sys.stderr)
        sys.exit(1)

def main():
    # Setup command line argument parser with examples
    parser = argparse.ArgumentParser(
        description='Fetch and analyze PR information',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
    # Analyze a PR from Bevy repository in Chinese
    python manual_update.py --pr 18144 --language zh-cn --repo "bevyengine/bevy"
    
    # Analyze a PR from another repository in English
    python manual_update.py --pr 1234 --language en --repo "username/repository"
    
    # Dry run mode
    python manual_update.py --pr 1234 --language en --repo "username/repository" --dry-run
    '''
    )
    
    parser.add_argument('--pr', required=True, help='PR number to analyze')
    parser.add_argument('--language', required=True, help='Language code (e.g., zh-cn, en)')
    parser.add_argument('--repo', required=True, help='Repository name in format "owner/repo" (e.g., "bevyengine/bevy")')
    parser.add_argument('--dry-run', action='store_true', help='Run in dry-run mode without making changes')
    parser.add_argument('--save-prompt', action='store_true', help='Save the full LLM prompt to a file in the logs directory')
    
    args = parser.parse_args()
    
    # Commands to execute
    fetch_cmd = f'docker exec -it prhythm python3 pipeline/fetch_pr_info.py --repo "{args.repo}" --pr "{args.pr}"'
    analyze_cmd = f'docker exec -it prhythm python3 pipeline/run_pr_analysis.py --repo "{args.repo}" --pr "{args.pr}" --language "{args.language}" --save-diff'
    
    # Add dry-run flag if specified
    if args.dry_run:
        analyze_cmd += ' --dry-run'
    
    # Add save-prompt flag if specified
    if args.save_prompt:
        analyze_cmd += ' --save-prompt'
    
    # Execute commands
    print("Fetching PR information...")
    run_docker_command(fetch_cmd)
    
    print("Analyzing PR...")
    run_docker_command(analyze_cmd)


if __name__ == '__main__':
    main() 