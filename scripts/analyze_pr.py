#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Analyze PR information using LLM API and generate a markdown report.
This script takes a PR JSON file path and output language as input,
then sends a request to the configured LLM API to generate an analysis report.
"""

import json
import sys
import os
import argparse
import requests
import yaml
from pathlib import Path
from datetime import datetime

def read_config(config_path):
    """
    Read configuration file and return its contents
    
    Args:
        config_path: Path to the configuration file
        
    Returns:
        dict: Configuration contents
    """
    try:
        with open(config_path, 'r') as file:
            config = yaml.safe_load(file)
            return config
    except Exception as e:
        print(f"Error reading configuration file: {e}")
        sys.exit(1)

def read_pr_data(json_file_path):
    """
    Read PR data from a JSON file
    
    Args:
        json_file_path: Path to the PR JSON file
        
    Returns:
        dict: PR data
    """
    try:
        with open(json_file_path, 'r') as file:
            pr_data = json.load(file)
            return pr_data
    except Exception as e:
        print(f"Error reading PR JSON file: {e}")
        sys.exit(1)

def read_prompt_template(prompt_path):
    """
    Read the prompt template from a file
    
    Args:
        prompt_path: Path to the prompt template file
        
    Returns:
        str: Prompt template
    """
    try:
        with open(prompt_path, 'r') as file:
            prompt_template = file.read()
            return prompt_template
    except Exception as e:
        print(f"Error reading prompt template file: {e}")
        sys.exit(1)

def prepare_file_changes_summary(pr_data):
    """
    Prepare a summary of file changes for the prompt
    
    Args:
        pr_data: PR data
        
    Returns:
        str: Summary of file changes
    """
    # Sort files by the sum of additions and deletions
    sorted_files = sorted(
        pr_data.get('files', []), 
        key=lambda x: x.get('additions', 0) + x.get('deletions', 0), 
        reverse=True
    )
    
    # Take the top 5 files
    top_files = sorted_files[:5]
    
    # Format the summary
    summary_lines = []
    for file in top_files:
        # Try different field names for filename
        filename = file.get('filename', file.get('path', 'Unknown file'))
        additions = file.get('additions', 0)
        deletions = file.get('deletions', 0)
        summary_lines.append(f"- `{filename}` (+{additions}/-{deletions})")
    
    # If no files found, add a note
    if not summary_lines:
        summary_lines.append("- No file changes found in the PR data")
    
    return "\n".join(summary_lines)

def prepare_prompt(pr_data, prompt_template, output_language):
    """
    Prepare the prompt for LLM API
    
    Args:
        pr_data: PR data
        prompt_template: Prompt template
        output_language: Output language
        
    Returns:
        str: Prepared prompt
    """
    # Prepare file changes summary
    file_changes_summary = prepare_file_changes_summary(pr_data)
    
    # Create a context dictionary with all variables needed for the prompt
    context = {
        'pr_data': pr_data,
        'output_language': output_language,
        'file_changes_summary': file_changes_summary,
        'len': len  # Include len function for use in the template
    }
    
    # Format the prompt template with the context
    prompt = prompt_template
    
    # Replace Python expressions in the template
    import re
    
    # Handle len() expressions
    len_pattern = r'{len\(pr_data\[\'([^\']+)\'\]\)}'
    for match in re.finditer(len_pattern, prompt):
        key = match.group(1)
        if key in pr_data and isinstance(pr_data[key], list):
            replacement = str(len(pr_data[key]))
            prompt = prompt.replace(match.group(0), replacement)
    
    # Handle conditional expressions (for merged status)
    merged_pattern = r'{pr_data\[\'mergedAt\'\] if pr_data\[\'mergedAt\'\] else "Not merged"}'
    replacement = pr_data.get('mergedAt') if pr_data.get('mergedAt') else "Not merged"
    prompt = prompt.replace(merged_pattern, replacement)
    
    # Handle conditional expressions (for merged by)
    merged_by_pattern = r'{pr_data\[\'mergedBy\'\]\[\'login\'\] if pr_data\[\'mergedBy\'\] else "N/A"}'
    merged_by = pr_data.get('mergedBy')
    if merged_by and isinstance(merged_by, dict) and 'login' in merged_by:
        replacement = merged_by['login']
    else:
        replacement = "N/A"
    prompt = prompt.replace(merged_by_pattern, replacement)
    
    # Replace simple variable references
    for key in pr_data:
        if isinstance(pr_data[key], (str, int, float, bool)):
            pattern = f"{{pr_data['{key}']}}"
            prompt = prompt.replace(pattern, str(pr_data[key]))
        elif isinstance(pr_data[key], dict) and 'login' in pr_data[key]:
            pattern = f"{{pr_data['{key}']['login']}}"
            prompt = prompt.replace(pattern, pr_data[key]['login'])
    
    # Replace repository reference
    if 'repository' in pr_data:
        prompt = prompt.replace("{pr_data['repository']}", pr_data['repository'])
    
    # Replace output language
    prompt = prompt.replace("{output_language}", output_language)
    
    # Replace file changes summary
    prompt = prompt.replace("{file_changes_summary}", file_changes_summary)
    
    # Replace PR body
    if 'body' in pr_data:
        # Find the position to replace the body
        body_placeholder = "{pr_data['body']}"
        if body_placeholder in prompt:
            prompt = prompt.replace(body_placeholder, pr_data['body'] or "No description provided")
    
    return prompt

def calculate_pr_complexity(pr_data):
    """
    Calculate the complexity of a PR based on various factors
    
    Args:
        pr_data: PR data
        
    Returns:
        dict: Complexity metrics and recommended model parameters
    """
    # Initialize complexity score
    complexity = 0
    
    # Factor 1: Number of files changed
    files_changed = len(pr_data.get('files', []))
    if files_changed > 20:
        complexity += 3
    elif files_changed > 10:
        complexity += 2
    elif files_changed > 5:
        complexity += 1
    
    # Factor 2: Total lines changed (additions + deletions)
    total_lines_changed = sum(
        file.get('additions', 0) + file.get('deletions', 0) 
        for file in pr_data.get('files', [])
    )
    if total_lines_changed > 1000:
        complexity += 3
    elif total_lines_changed > 500:
        complexity += 2
    elif total_lines_changed > 100:
        complexity += 1
    
    # Factor 3: Number of comments (indicates discussion complexity)
    comments = len(pr_data.get('comments', []))
    if comments > 20:
        complexity += 3
    elif comments > 10:
        complexity += 2
    elif comments > 5:
        complexity += 1
    
    # Factor 4: Description length
    description_length = len(pr_data.get('body', '')) if pr_data.get('body') else 0
    if description_length > 2000:
        complexity += 2
    elif description_length > 1000:
        complexity += 1
    
    # Calculate recommended parameters based on complexity
    max_tokens = 4000  # Default
    if complexity >= 8:
        max_tokens = 8000
    elif complexity >= 5:
        max_tokens = 6000
    
    temperature = 0.3  # Default
    if complexity >= 8:
        temperature = 0.2  # More deterministic for complex PRs
    elif complexity <= 2:
        temperature = 0.4  # More creative for simple PRs
    
    # Calculate top_p based on complexity
    top_p = 0.95 if complexity >= 5 else 0.9
    
    # Calculate frequency_penalty based on complexity
    frequency_penalty = 0.1 if complexity >= 5 else 0.0
    
    return {
        'complexity_score': complexity,
        'max_tokens': max_tokens,
        'temperature': temperature,
        'top_p': top_p,
        'frequency_penalty': frequency_penalty
    }

def call_llm_api(prompt, config, provider=None):
    """
    Call LLM API to generate an analysis report
    
    Args:
        prompt: Prepared prompt
        config: Configuration data
        provider: LLM provider to use (optional, defaults to config.llm.provider)
        
    Returns:
        str: Generated analysis report
    """
    # Get provider from argument or config
    if not provider:
        provider = config.get('llm', {}).get('provider', 'openai')
    
    # Get provider-specific configuration
    provider_config = config.get('llm', {}).get('providers', {}).get(provider, {})
    
    # Get API key from provider config or fall back to default
    api_key = provider_config.get('api_key', '')
    if not api_key:
        # Try to get from environment variable
        env_var_name = f"{provider.upper()}_API_KEY"
        api_key = os.environ.get(env_var_name, '')
        
        # Fall back to default LLM API key
        if not api_key:
            api_key = config.get('llm', {}).get('api_key', '')
            if not api_key:
                api_key = os.environ.get('LLM_API_KEY', '')
    
    if not api_key:
        print(f"Error: API key for provider '{provider}' not found in configuration or environment variables")
        sys.exit(1)
    
    # Get model from provider config or fall back to default
    model = provider_config.get('model', config.get('llm', {}).get('model', 'gpt-4'))
    
    # Get base URL from provider config
    base_url = provider_config.get('base_url', '')
    if not base_url:
        if provider == 'openai':
            base_url = 'https://api.openai.com/v1'
        elif provider == 'deepseek':
            base_url = 'https://api.deepseek.com'
        else:
            print(f"Error: Base URL for provider '{provider}' not found in configuration")
            sys.exit(1)
    
    # Get temperature from config
    temperature = config.get('llm', {}).get('temperature', 0.3)
    
    # Call the appropriate API based on the provider
    if provider in ['openai', 'deepseek']:
        return call_openai_compatible_api(prompt, api_key, model, base_url, temperature, config)
    else:
        print(f"Error: Unsupported provider '{provider}'")
        sys.exit(1)

def call_openai_compatible_api(prompt, api_key, model, base_url, temperature, config):
    """
    Call OpenAI-compatible API (works for OpenAI, DeepSeek, etc.)
    
    Args:
        prompt: Prepared prompt
        api_key: API key
        model: Model name
        base_url: Base URL for the API
        temperature: Temperature parameter
        config: Configuration data
        
    Returns:
        str: Generated analysis report
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # Extract PR data from the prompt to calculate complexity
    # This is a simplified approach - in a real implementation, 
    # you would pass the PR data directly
    import re
    pr_number_match = re.search(r'PR #(\d+)', prompt)
    pr_number = pr_number_match.group(1) if pr_number_match else "unknown"
    
    # Get PR data from config for complexity calculation
    pr_data = {}
    for repo in config.get('github', {}).get('repositories', []):
        repo_data = config.get('github', {}).get('data', {}).get(repo, {})
        if pr_number in repo_data:
            pr_data = repo_data[pr_number]
            break
    
    # Calculate complexity and get recommended parameters
    complexity_params = calculate_pr_complexity(pr_data)
    
    # Override default parameters with complexity-based ones
    max_tokens = complexity_params.get('max_tokens', 4000)
    temperature = complexity_params.get('temperature', temperature)
    top_p = complexity_params.get('top_p', 0.95)
    frequency_penalty = complexity_params.get('frequency_penalty', 0.0)
    
    # Print complexity information
    print(f"PR Complexity Score: {complexity_params.get('complexity_score', 'N/A')}")
    print(f"Using parameters: max_tokens={max_tokens}, temperature={temperature}, top_p={top_p}")
    
    data = {
        "model": model,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "top_p": top_p,
        "frequency_penalty": frequency_penalty
    }
    
    try:
        # Construct the endpoint URL
        # For OpenAI and DeepSeek, the endpoint is /v1/chat/completions
        endpoint = "/v1/chat/completions"
        
        # If base_url already ends with /v1, don't add it again
        if base_url.endswith('/v1'):
            endpoint = "/chat/completions"
        
        response = requests.post(
            f"{base_url}{endpoint}",
            headers=headers,
            json=data
        )
        
        if response.status_code == 200:
            result = response.json()
            return result['choices'][0]['message']['content']
        else:
            print(f"Error calling API: {response.status_code}")
            print(f"Response: {response.text}")
            sys.exit(1)
    except Exception as e:
        print(f"Error calling API: {e}")
        sys.exit(1)

def save_analysis_report(report, pr_data, output_dir, output_language):
    """
    Save the analysis report to a file
    
    Args:
        report: Analysis report
        pr_data: PR data
        output_dir: Output directory
        output_language: Output language
        
    Returns:
        Path: Path to the saved file
    """
    # Extract repository name from owner/repo format
    repo = pr_data.get('repository', 'unknown')
    repo_name = repo.split('/')[-1]
    
    # Create repository-specific directory
    repo_output_dir = output_dir / repo_name
    repo_output_dir.mkdir(exist_ok=True, parents=True)
    
    # Create a filename
    pr_number = pr_data.get('number', 'unknown')
    filename = f"pr_{pr_number}_{output_language}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    file_path = repo_output_dir / filename
    
    try:
        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(report)
        return file_path
    except Exception as e:
        print(f"Error saving analysis report: {e}")
        sys.exit(1)

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Analyze PR information using LLM API')
    parser.add_argument('--json', required=True, help='Path to the PR JSON file')
    parser.add_argument('--language', default='en', help='Output language (e.g., en, zh-cn)')
    parser.add_argument('--config', default='config.yaml', help='Path to the configuration file')
    parser.add_argument('--provider', help='LLM provider to use (overrides config)')
    parser.add_argument('--dry-run', action='store_true', help='Only print the prompt without sending the request')
    return parser.parse_args()

def main():
    """Main function"""
    # Parse command line arguments
    args = parse_arguments()
    
    # Get project root directory
    script_dir = Path(os.path.dirname(os.path.abspath(__file__)))
    project_root = script_dir.parent
    
    # Read configuration
    config_path = project_root / args.config
    config = read_config(config_path)
    
    # Read PR data
    json_file_path = Path(args.json)
    if not json_file_path.is_absolute():
        json_file_path = project_root / json_file_path
    pr_data = read_pr_data(json_file_path)
    
    # Read prompt template
    prompt_path = project_root / "prompt" / "analyze_pr.prompt"
    prompt_template = read_prompt_template(prompt_path)
    
    # Prepare prompt
    prompt = prepare_prompt(pr_data, prompt_template, args.language)
    
    print(f"Analyzing PR #{pr_data.get('number', 'unknown')} from repository {pr_data.get('repository', 'unknown')}...")
    
    # If dry run, just print the prompt and exit
    if args.dry_run:
        print("\n=== PROMPT ===\n")
        print(prompt)
        print("\n=== END OF PROMPT ===\n")
        return
    
    # Add PR data to config for complexity calculation
    if 'github' not in config:
        config['github'] = {}
    if 'data' not in config['github']:
        config['github']['data'] = {}
    
    repo = pr_data.get('repository', 'unknown')
    if repo not in config['github']['data']:
        config['github']['data'][repo] = {}
    
    pr_number = str(pr_data.get('number', 'unknown'))
    config['github']['data'][repo][pr_number] = pr_data
    
    # Call LLM API
    report = call_llm_api(prompt, config, args.provider)
    
    # Create output directory
    output_dir = project_root / "analysis"
    output_dir.mkdir(exist_ok=True)
    
    # Save analysis report
    file_path = save_analysis_report(report, pr_data, output_dir, args.language)
    
    print(f"Analysis report saved to: {file_path}")

if __name__ == "__main__":
    main() 