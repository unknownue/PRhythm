#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Analyze PR information using LLM API and generate a markdown report.
This script takes a PR JSON file path and output language as input,
then sends a request to the configured LLM API to generate an analysis report.

Features:
- Generate PR analysis report in different languages
- Save the PR diff as a separate patch file (using --save-diff flag)
- Analyze codebase architecture and impact of changes
- Extract learning points from the PR
"""

import sys
import argparse
import requests
import re
from pathlib import Path
from datetime import datetime
import os
import logging
import json

# Import common utilities
from common import (
    read_config,
    get_project_root,
    setup_logging,
    load_json,
    save_json,
    ensure_directory,
)

# Import fetch_module_context from fetch_pr_info
from fetch_pr_info import fetch_module_context

# Import get_provider_from_config from update_pr_reports
from update_pr_reports import get_provider_from_config

# Setup logger
logger = setup_logging("analyze_pr")

# Define language markers (both English and native names)
LANGUAGE_MARKERS = {
    'en': ['# English Version', '# English'],
    'zh-cn': ['# 中文版本', '# Chinese Version', '# 中文版本 (Chinese Version)', '# Chinese'],
    'ja': ['# 日本語版', '# Japanese Version', '# 日本語版 (Japanese Version)', '# Japanese'],
    'ko': ['# 한국어 버전', '# Korean Version', '# 한국어 버전 (Korean Version)', '# Korean'],
    'fr': ['# Version Française', '# French Version', '# Version Française (French Version)', '# French', '# Français'],
    'de': ['# Deutsche Version', '# German Version', '# Deutsche Version (German Version)', '# German', '# Deutsch'],
    'es': ['# Versión en Español', '# Spanish Version', '# Versión en Español (Spanish Version)', '# Spanish', '# Español']
}

# Map language codes to language names
LANGUAGE_NAMES = {
    'en': 'English',
    'zh-cn': '中文 (Chinese)',
    'ja': '日本語 (Japanese)',
    'ko': '한국어 (Korean)',
    'fr': 'Français (French)',
    'de': 'Deutsch (German)',
    'es': 'Español (Spanish)'
}

def read_pr_data(json_file_path):
    """
    Read PR data from a JSON file
    
    Args:
        json_file_path: Path to the PR JSON file
        
    Returns:
        dict: PR data
    """
    try:
        return load_json(json_file_path)
    except Exception as e:
        logger.error(f"Error reading PR JSON file: {e}")
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
        with open(prompt_path, 'r', encoding='utf-8') as file:
            prompt_template = file.read()
            return prompt_template
    except Exception as e:
        logger.error(f"Error reading prompt template file: {e}")
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

def generate_architecture_context(pr_data):
    """
    Generate architecture context based on PR data
    
    Args:
        pr_data: PR data
        
    Returns:
        str: Architecture context
    """
    # Extract file paths to understand project structure
    file_paths = [file.get('filename', file.get('path', '')) for file in pr_data.get('files', [])]
    
    # Group files by directory to identify modules
    modules = {}
    for path in file_paths:
        if not path:
            continue
        parts = path.split('/')
        if len(parts) > 1:
            module = parts[0]
            if module not in modules:
                modules[module] = []
            modules[module].append(path)
    
    # Generate module summary
    module_summary = []
    for module, files in modules.items():
        module_summary.append(f"- **{module}**: {len(files)} files modified")
    
    # If no modules identified, provide a generic message
    if not module_summary:
        return "No clear module structure identified from the PR changes."
    
    return "The PR affects the following modules:\n" + "\n".join(module_summary)

def analyze_key_commits(pr_data):
    """
    Analyze key commits in the PR
    
    Args:
        pr_data: PR data
        
    Returns:
        str: Key commit analysis
    """
    # This function has been moved to fetch_pr_info.py
    # Return the pre-computed analysis if available
    if 'commit_analysis' in pr_data:
        return pr_data['commit_analysis']
    
    # For backward compatibility, return a warning message if commit_analysis is not available
    return "Commit analysis not available. Please run fetch_pr_info.py first to generate commit analysis."

def format_code_references(pr_data):
    """
    Format code references from PR diff
    
    Args:
        pr_data: PR data
        
    Returns:
        str: Formatted code references
    """
    diff = pr_data.get('diff', '')
    if not diff:
        return "No code diff available."
    
    # Extract code snippets from diff
    snippets = []
    current_file = None
    current_section = []
    section_header = None
    
    for line in diff.split('\n'):
        if line.startswith('diff --git'):
            # Save previous section if exists
            if current_file and current_section:
                snippets.append({
                    'file': current_file,
                    'header': section_header,
                    'code': '\n'.join(current_section)
                })
                current_section = []
            
            # Extract new file name
            parts = line.split()
            if len(parts) >= 3:
                current_file = parts[-1][2:]  # Remove 'b/' prefix
        
        elif line.startswith('@@'):
            # Save previous section if exists
            if current_file and current_section:
                snippets.append({
                    'file': current_file,
                    'header': section_header,
                    'code': '\n'.join(current_section)
                })
                current_section = []
            
            # Extract line numbers
            section_header = line
        
        elif current_file and section_header:
            # Add line to current section
            if line.startswith('+') or line.startswith('-'):
                current_section.append(line)
    
    # Add the last section if exists
    if current_file and current_section:
        snippets.append({
            'file': current_file,
            'header': section_header,
            'code': '\n'.join(current_section)
        })
    
    # Format snippets (limit to top 3 most significant)
    formatted_snippets = []
    for i, snippet in enumerate(snippets[:3]):
        formatted_snippets.append(f"**Code Snippet {i+1}** - `{snippet['file']}` {snippet['header']}:\n```\n{snippet['code']}\n```")
    
    if not formatted_snippets:
        return "No significant code changes identified."
    
    return "\n\n".join(formatted_snippets)

def generate_impact_matrix(pr_data):
    """
    Generate code impact matrix
    
    Args:
        pr_data: PR data
        
    Returns:
        str: Impact matrix in markdown table format
    """
    files = pr_data.get('files', [])
    if not files:
        return "| No files changed | - | - | - | - |"
    
    # Sort files by impact (additions + deletions)
    sorted_files = sorted(
        files, 
        key=lambda x: x.get('additions', 0) + x.get('deletions', 0), 
        reverse=True
    )
    
    # Take top 5 files for analysis
    top_files = sorted_files[:5]
    
    # Generate matrix rows
    rows = []
    for file in top_files:
        filename = file.get('filename', file.get('path', 'Unknown file'))
        additions = file.get('additions', 0)
        deletions = file.get('deletions', 0)
        
        # Analyze file impact
        impact = analyze_file_impact(filename, additions, deletions, pr_data)
        
        rows.append(f"| `{filename}` | +{additions}/-{deletions} | {impact['functionality']} | {impact['modules']} | {impact['risk']} |")
    
    return "\n".join(rows)

def analyze_file_impact(filename, additions, deletions, pr_data):
    """
    Analyze the impact of changes to a specific file
    
    Args:
        filename: File name
        additions: Number of lines added
        deletions: Number of lines deleted
        pr_data: PR data
        
    Returns:
        dict: Impact analysis with functionality, modules, and risk
    """
    # Default impact analysis
    impact = {
        'functionality': 'Unknown',
        'modules': 'Unknown',
        'risk': 'Low'
    }
    
    # Determine file type and potential functionality
    if filename.endswith('.py'):
        impact['functionality'] = 'Python Logic'
    elif filename.endswith('.js') or filename.endswith('.ts'):
        impact['functionality'] = 'Frontend Logic'
    elif filename.endswith('.html') or filename.endswith('.css'):
        impact['functionality'] = 'UI/Presentation'
    elif filename.endswith('.md') or filename.endswith('.txt'):
        impact['functionality'] = 'Documentation'
    elif filename.endswith('.json') or filename.endswith('.yaml') or filename.endswith('.yml'):
        impact['functionality'] = 'Configuration'
    elif filename.endswith('.sql'):
        impact['functionality'] = 'Database'
    elif filename.endswith('.sh'):
        impact['functionality'] = 'Build/Deployment'
    
    # Determine module based on directory structure
    parts = filename.split('/')
    if len(parts) > 1:
        impact['modules'] = parts[0]
    
    # Determine risk based on changes
    total_changes = additions + deletions
    if total_changes > 100:
        impact['risk'] = 'High'
    elif total_changes > 30:
        impact['risk'] = 'Medium'
    else:
        impact['risk'] = 'Low'
    
    # Adjust risk based on file type
    if 'test' in filename.lower():
        impact['risk'] = 'Low'  # Test changes are generally lower risk
    elif 'core' in filename.lower() or 'main' in filename.lower():
        impact['risk'] = 'High'  # Core functionality changes are higher risk
    
    return impact

def identify_learning_points(pr_data):
    """
    Identify key learning points from the PR
    
    Args:
        pr_data: PR data
        
    Returns:
        str: Learning points in markdown format
    """
    # Extract key information
    files = pr_data.get('files', [])
    
    if not files:
        return "No files changed, no learning points identified."
    
    # Identify most significant file
    sorted_files = sorted(
        files, 
        key=lambda x: x.get('additions', 0) + x.get('deletions', 0), 
        reverse=True
    )
    main_file = sorted_files[0]
    main_filename = main_file.get('filename', main_file.get('path', 'Unknown file'))
    
    # Identify potential patterns based on file types
    patterns = []
    
    # Check file extensions to guess patterns
    if any(file.get('filename', '').endswith(('.py', '.js', '.ts', '.java', '.c', '.cpp')) for file in files):
        patterns.append("Implementation techniques")
    
    if any(file.get('filename', '').endswith(('test.py', 'test.js', 'Test.java', '_test.go')) for file in files):
        patterns.append("Testing strategies")
    
    if any(file.get('filename', '').endswith(('.md', '.txt', '.rst', '.adoc')) for file in files):
        patterns.append("Documentation practices")
    
    if not patterns:
        patterns.append("Implementation techniques")
    
    # Generate learning path
    learning_path = [
        f"1. Start by understanding the purpose of `{main_filename}`",
        f"2. Examine the changes to identify the {patterns[0]} used",
        "3. Look for related test files to understand validation approach"
    ]
    
    # Format output
    output = [
        "## Key Learning Points",
        "",
        f"- **Main File**: `{main_filename}` (+{main_file.get('additions', 0)}/-{main_file.get('deletions', 0)})",
        f"- **Technical Concepts**: {', '.join(patterns)}",
        "",
        "## Suggested Learning Path",
        "",
        "\n".join(learning_path)
    ]
    
    return "\n".join(output)

def format_module_context(module_context):
    """
    Format module context for inclusion in the prompt
    
    Args:
        module_context: Module context information
        
    Returns:
        str: Formatted module context
    """
    # This function has been moved to fetch_pr_info.py
    # Return the pre-computed module context if available
    if not module_context or not module_context.get('modules'):
        return "No module context available."
    
    formatted_sections = []
    
    for module_name, module_data in module_context.get('modules', {}).items():
        section = [f"### Module: {module_name}"]
        
        # Add structure information
        structure = module_data.get('structure', {})
        if structure:
            if structure.get('classes'):
                section.append(f"**Classes**: {', '.join(structure.get('classes', []))}")
            if structure.get('functions'):
                section.append(f"**Functions**: {', '.join(structure.get('functions', []))}")
            if structure.get('imports'):
                section.append(f"**Dependencies**: {', '.join(structure.get('imports', []))}")
        
        # Add key file snippets (limited to keep prompt size reasonable)
        key_files = module_data.get('key_files', {})
        if key_files:
            section.append("\n**Key Files:**")
            for file_path, content in list(key_files.items())[:2]:  # Limit to 2 files
                # Truncate content if too long
                if len(content) > 500:
                    content = content[:500] + "...\n[content truncated]"
                section.append(f"\n`{file_path}`:\n```\n{content}\n```")
        
        formatted_sections.append("\n".join(section))
    
    return "\n\n".join(formatted_sections)

def format_modified_file_contents(pr_data):
    """
    Format the content of modified files for inclusion in the prompt
    
    Args:
        pr_data: PR data containing modified file contents
        
    Returns:
        str: Formatted modified file contents in markdown format
    """
    modified_file_contents = pr_data.get('modified_file_contents', {})
    
    if not modified_file_contents:
        return "No modified file contents available."
    
    # Sort files by path for consistent output
    sorted_files = sorted(modified_file_contents.items())
    
    # Limit the number of files to include (max 10 files)
    max_files = 10
    if len(sorted_files) > max_files:
        sorted_files = sorted_files[:max_files]
        
    # Set a total character limit for all file contents combined
    total_char_limit = 30000
    current_total = 0
    
    formatted_sections = []
    
    for file_path, content in sorted_files:
        # Determine language for syntax highlighting
        extension = file_path.split('.')[-1] if '.' in file_path else ''
        language = ''
        
        if extension in ['py', 'python']:
            language = 'python'
        elif extension in ['js', 'javascript']:
            language = 'javascript'
        elif extension in ['ts', 'typescript']:
            language = 'typescript'
        elif extension in ['java']:
            language = 'java'
        elif extension in ['c', 'cpp', 'h', 'hpp']:
            language = 'cpp'
        elif extension in ['go']:
            language = 'go'
        elif extension in ['rs']:
            language = 'rust'
        elif extension in ['html']:
            language = 'html'
        elif extension in ['css']:
            language = 'css'
        elif extension in ['json']:
            language = 'json'
        elif extension in ['yaml', 'yml']:
            language = 'yaml'
        elif extension in ['md', 'markdown']:
            language = 'markdown'
        elif extension in ['sh', 'bash']:
            language = 'bash'
        
        # Set a character limit per file (3000 characters)
        char_limit_per_file = 3000
        
        # If content is too large, truncate it
        if len(content) > char_limit_per_file:
            content = content[:char_limit_per_file] + "\n...\n[content truncated]"
        
        # Check if adding this file would exceed the total character limit
        if current_total + len(content) > total_char_limit:
            # If we already have some files, just stop adding more
            if formatted_sections:
                formatted_sections.append("\n### [Additional files omitted due to size constraints]")
                break
            else:
                # If this is the first file, truncate it further to fit within limits
                content = content[:total_char_limit - 100] + "\n...\n[content severely truncated]"
        
        # Format the section
        section = f"### File: `{file_path}`\n\n```{language}\n{content}\n```\n"
        formatted_sections.append(section)
        
        # Update the total character count
        current_total += len(content)
    
    return "\n".join(formatted_sections)

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
    
    # Fetch module context if not already present
    if 'module_context' not in pr_data:
        pr_data['module_context'] = fetch_module_context(pr_data)
    
    # Generate new enhanced context elements
    architecture_context = generate_architecture_context(pr_data)
    commit_analysis = analyze_key_commits(pr_data)
    code_references = format_code_references(pr_data)
    impact_matrix = generate_impact_matrix(pr_data)
    learning_points = identify_learning_points(pr_data)
    module_context_summary = format_module_context(pr_data['module_context'])
    
    # Format modified file contents
    modified_file_contents = format_modified_file_contents(pr_data)
    
    # Ensure only PR description is used, not comments
    # If comments or reviews fields exist, set them to empty lists
    if 'comments' in pr_data:
        pr_data['comments'] = []
    
    if 'reviews' in pr_data:
        pr_data['reviews'] = []
    
    # Prepare language-specific instructions
    language_instruction = prepare_language_instruction(output_language)
    
    # Create a context dictionary with all variables needed for the prompt
    context = {
        'pr_data': pr_data,
        'output_language': output_language,
        'file_changes_summary': file_changes_summary,
        'architecture_context': architecture_context,
        'commit_analysis': commit_analysis,
        'code_references': code_references,
        'impact_matrix': impact_matrix,
        'learning_points': learning_points,
        'module_context_summary': module_context_summary,
        'modified_file_contents': modified_file_contents,
        'multilingual_instruction': language_instruction,
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
    
    # Replace new context variables
    prompt = prompt.replace("{architecture_context}", architecture_context)
    prompt = prompt.replace("{commit_analysis}", commit_analysis)
    prompt = prompt.replace("{code_references}", code_references)
    prompt = prompt.replace("{impact_matrix}", impact_matrix)
    prompt = prompt.replace("{learning_points}", learning_points)
    prompt = prompt.replace("{module_context_summary}", module_context_summary)
    prompt = prompt.replace("{modified_file_contents}", modified_file_contents)
    prompt = prompt.replace("{multilingual_instruction}", language_instruction)
    
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
    
    # Replace "# Title" with "# #{pr number} {pr_title}"
    pr_number = pr_data.get('number', '')
    pr_title = pr_data.get('title', '')
    
    # Ensure exact match for the title line - look for a line that is exactly "# Title"
    lines = prompt.split('\n')
    for i, line in enumerate(lines):
        if line.strip() == "# Title":
            lines[i] = f"# #{pr_number} {pr_title}"
    prompt = '\n'.join(lines)
    
    # Replace PR body
    if 'body' in pr_data:
        # Find the position to replace the body
        body_placeholder = "{pr_data['body']}"
        if body_placeholder in prompt:
            prompt = prompt.replace(body_placeholder, pr_data['body'] or "No description provided")
    
    # Remove any remaining placeholders
    prompt = prompt.replace("{multilingual_format}", "")
    
    return prompt

def prepare_language_instruction(output_language):
    """
    Prepare language-specific instruction for the analysis
    
    Args:
        output_language: Output language code (e.g., 'en', 'zh-cn') or 'multilingual'
        
    Returns:
        str: Language-specific instruction
    """
    if output_language == "multilingual":
        # For backward compatibility, return a message indicating multilingual is no longer supported directly
        return """
Multilingual mode is now handled by making separate API calls for each language.
This instruction is for backward compatibility and should not be used directly.
"""
    else:
        # Get the language name from the mapping
        language_name = LANGUAGE_NAMES.get(output_language, output_language)
        
        # Special handling for English
        if output_language == "en":
            return f"""
Generate your analysis in {language_name}.
1. Use {language_name} for all content except code and technical terms
2. For the "Description Translation" section, simply include the original PR description verbatim without adding any notes like "(Original English description preserved per instructions)"
3. Never translate code snippets, variable names, function names, or code comments
"""
        else:
            return f"""
Generate your analysis in {language_name}.
1. Use {language_name} for all content except code and technical terms
2. Keep widely recognized technical terms in English
3. For other terms, provide translation with English in parentheses
4. For complex concepts, explain in both languages for clarity
5. Never translate code snippets, variable names, function names, or code comments
"""

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
    
    # Factor 3: Description length
    description_length = len(pr_data.get('body', '')) if pr_data.get('body') else 0
    if description_length > 2000:
        complexity += 2
    elif description_length > 1000:
        complexity += 1
    
    # Calculate recommended parameters based on complexity
    max_tokens = 4000  # Default
    if complexity >= 6:
        max_tokens = 8000
    elif complexity >= 3:
        max_tokens = 6000
    
    temperature = 0.3  # Default
    if complexity >= 6:
        temperature = 0.2  # More deterministic for complex PRs
    elif complexity <= 2:
        temperature = 0.4  # More creative for simple PRs
    
    # Calculate top_p based on complexity
    top_p = 0.95 if complexity >= 3 else 0.9
    
    # Calculate frequency_penalty based on complexity
    frequency_penalty = 0.1 if complexity >= 3 else 0.0
    
    return {
        'complexity_score': complexity,
        'max_tokens': max_tokens,
        'temperature': temperature,
        'top_p': top_p,
        'frequency_penalty': frequency_penalty
    }

def call_llm_api(prompt, config, provider=None, dry_run=False):
    """
    Call LLM API to generate an analysis report
    
    Args:
        prompt: Prepared prompt
        config: Configuration data
        provider: LLM provider to use (optional, defaults to config.llm.provider)
        dry_run: If True, only save the prompt without making API calls
        
    Returns:
        str: Generated analysis report or message indicating dry run
    """
    # Save prompt to logs directory first
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    
    # Generate a timestamp and filename for the prompt log
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Extract PR number from prompt if available for better filename
    import re
    pr_number_match = re.search(r'PR #(\d+)', prompt)
    pr_number = pr_number_match.group(1) if pr_number_match else "unknown"
    
    prompt_file = logs_dir / f"prompt_pr{pr_number}_{timestamp}.txt"
    
    # Save the prompt to file
    with open(prompt_file, "w", encoding="utf-8") as f:
        f.write(prompt)
    
    print(f"Prompt saved to: {prompt_file}")
    
    # If dry run, return early with a message
    if dry_run:
        return f"DRY RUN: Prompt saved to {prompt_file}. No API call was made."
    
    # Get provider from argument or config
    if not provider:
        provider = config.get('llm', {}).get('provider', 'openai')
    
    # Get provider-specific configuration
    provider_config = config.get('llm', {}).get('providers', {}).get(provider, {})
    
    # Get API key from provider config
    api_key = provider_config.get('api_key', '')
    if not api_key:
        # Try to get from environment variable
        env_var_name = f"{provider.upper()}_API_KEY"
        api_key = os.environ.get(env_var_name, '')
        
        # Fall back to default LLM API key
        if not api_key:
            api_key = os.environ.get('LLM_API_KEY', '')
    
    if not api_key:
        print(f"Error: API key for provider '{provider}' not found in configuration or environment variables")
        print(f"Please set {provider.upper()}_API_KEY environment variable or configure it in config.json")
        sys.exit(1)
    
    # Get model from provider config
    model = provider_config.get('model', '')
    if not model:
        print(f"Error: Model for provider '{provider}' not found in configuration")
        print(f"Please configure model in config.json under llm.providers.{provider}")
        sys.exit(1)

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
    
    # Calculate prompt length to adjust max_tokens
    prompt_length = len(prompt)
    
    # Dynamically adjust max_tokens based on prompt length
    # The longer the prompt, the more tokens we need for the response
    base_max_tokens = complexity_params.get('max_tokens', 4000)
    
    # Adjust max_tokens based on prompt length
    if prompt_length > 100000:
        max_tokens = min(16000, int(base_max_tokens * 2))  # Double the tokens for very large prompts
    elif prompt_length > 50000:
        max_tokens = min(12000, int(base_max_tokens * 1.5))  # 1.5x tokens for large prompts
    elif prompt_length > 20000:
        max_tokens = min(8000, int(base_max_tokens * 1.2))  # 1.2x tokens for medium prompts
    else:
        max_tokens = base_max_tokens  # Use base tokens for small prompts
    
    # Ensure max_tokens doesn't exceed model limits
    if model.startswith('gpt-4'):
        max_tokens = min(max_tokens, 16000)  # GPT-4 limit
    elif model.startswith('gpt-3.5'):
        max_tokens = min(max_tokens, 4000)  # GPT-3.5 limit
    
    # Override default parameters with complexity-based ones
    temperature = complexity_params.get('temperature', temperature)
    top_p = complexity_params.get('top_p', 0.95)
    frequency_penalty = complexity_params.get('frequency_penalty', 0.0)
    
    # Print complexity information
    print(f"PR Complexity Score: {complexity_params.get('complexity_score', 'N/A')}")
    print(f"Prompt Length: {prompt_length} characters")
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
            content = result['choices'][0]['message']['content']
            
            # Remove ```markdown tags from the beginning and end of the content
            if content.startswith("```markdown"):
                content = content[len("```markdown"):].lstrip()
            if content.endswith("```"):
                content = content[:-3].rstrip()
                
            return content
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
    
    # Get current date for month-based directory
    current_date = datetime.now()
    month_dir = current_date.strftime('%Y-%m')  # Format: YYYY-MM
    date_str = current_date.strftime('%Y%m%d')
    
    # Create repository-specific directory
    repo_output_dir = output_dir / repo_name / month_dir
    
    # Ensure directory exists with proper permissions
    ensure_directory(repo_output_dir)
    
    # Get PR number
    pr_number = pr_data.get('number', 'unknown')
    
    # Ensure we're using a valid language code
    language_code = output_language
    
    # Validate the language code against our known languages
    if language_code not in LANGUAGE_MARKERS:
        if language_code == 'multilingual':
            print(f"Warning: 'multilingual' is not a valid output language. Using 'en' as default in filename.")
            language_code = 'en'
        else:
            # Make sure we never use 'unknown' as a language code in the filename
            print(f"Warning: Unknown language code '{language_code}'. Defaulting to 'en' for filename.")
            language_code = 'en'
    
    # Create a base filename
    base_filename = f"pr_{pr_number}_{language_code}_{date_str}"
    
    # Check if files with the base name already exist
    existing_files = list(repo_output_dir.glob(f"{base_filename}*.md"))
    
    if not existing_files:
        # First file - use base filename
        filename = f"{base_filename}.md"
    else:
        # Subsequent files - add number starting from 1
        next_number = 1
        filename = f"{base_filename}_{next_number}.md"
        
        # Find a unique filename
        while repo_output_dir / filename in existing_files:
            next_number += 1
            filename = f"{base_filename}_{next_number}.md"
    
    file_path = repo_output_dir / filename
    
    # Convert to absolute path for better logging
    abs_file_path = os.path.abspath(file_path)
    
    try:
        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(report)
        
        print(f"Saved analysis report: {abs_file_path}")
        return file_path
    except Exception as e:
        logger.error(f"Error saving analysis report: {e}")
        raise

def save_diff_patch(pr_data, output_dir, filename_prefix):
    """
    Save PR diff as a patch file
    
    Args:
        pr_data: PR data containing diff information
        output_dir: Output directory
        filename_prefix: Prefix for the patch file name
        
    Returns:
        Path: Path to the saved patch file or None if no diff is available
    """
    # Get diff from PR data
    diff = pr_data.get('diff', '')
    if not diff:
        logger.warning("No diff available in PR data, cannot create patch file")
        return None
    
    # Create patch file name with timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    patch_filename = f"{filename_prefix}.patch"
    patch_file_path = output_dir / patch_filename
    
    # Ensure directory exists
    ensure_directory(output_dir)
    
    try:
        # Write diff to patch file with explicit UTF-8 encoding
        with open(patch_file_path, 'w', encoding='utf-8') as file:
            file.write(diff)
        
        logger.info(f"Saved diff patch file: {patch_file_path}")
        return patch_file_path
    except Exception as e:
        logger.error(f"Error saving diff patch file: {e}")
        return None

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Analyze PR and generate a report')
    parser.add_argument('--json', required=False, help='Path to the PR JSON file')
    parser.add_argument('--pr', type=str, help='PR number to analyze')
    parser.add_argument('--repo', type=str, help='Repository name (owner/repo format)')
    parser.add_argument('--language', default='en', help='Output language code (default: en)')
    parser.add_argument('--config', type=str, default="config.json", help='Path to the configuration file')
    parser.add_argument('--dry-run', action='store_true', help='Only save prompt without making actual API calls')
    parser.add_argument('--save-diff', action='store_true', help='Save PR diff as a separate patch file')
    args = parser.parse_args()
    
    # Check that either --json or --pr is provided
    if not args.json and not args.pr:
        parser.error("Either --json or --pr must be provided")
    
    return args

def find_pr_json_file(pr_number, repo_name=None, project_root=None, config=None):
    """
    Find the most recent JSON file for a PR
    
    Args:
        pr_number: PR number
        repo_name: Repository name (optional)
        project_root: Project root directory (optional)
        config: Configuration dictionary (optional)
        
    Returns:
        Path: Path to the PR JSON file
    """
    if project_root is None:
        project_root = get_project_root()
    
    if config is None:
        config_path = project_root / "config.json"
        config = read_config(config_path)
    
    # Get output directory from config or use default
    output_base_dir = config.get('paths', {}).get('output_dir', './output')
    
    # Convert relative path to absolute if needed
    if output_base_dir.startswith('./') or output_base_dir.startswith('../'):
        output_dir = project_root / output_base_dir.lstrip('./')
    else:
        output_dir = Path(output_base_dir)
    
    # List of files that match
    matching_files = []
    
    # If repository name is specified, only search in that directory
    if repo_name:
        # Extract repo name from owner/repo format if needed
        if '/' in repo_name:
            repo_name = repo_name.split('/')[-1]
        
        repo_dir = output_dir / repo_name
        if repo_dir.exists():
            # Check all month directories
            for month_dir in [d for d in repo_dir.iterdir() if d.is_dir()]:
                # Get files matching the PR pattern
                pr_files = list(month_dir.glob(f"pr_{pr_number}_*.json"))
                matching_files.extend(pr_files)
    else:
        # Search all repository directories
        repo_dirs = [d for d in output_dir.iterdir() if d.is_dir()]
        for repo_dir in repo_dirs:
            # Check all month directories
            for month_dir in [d for d in repo_dir.iterdir() if d.is_dir()]:
                # Get files matching the PR pattern
                pr_files = list(month_dir.glob(f"pr_{pr_number}_*.json"))
                matching_files.extend(pr_files)
    
    if not matching_files:
        repo_str = f" in repository '{repo_name}'" if repo_name else ""
        raise FileNotFoundError(f"No JSON files found for PR #{pr_number}{repo_str}")
    
    # Sort by modification time (newest first)
    matching_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
    
    # Return the most recent file
    return matching_files[0]

def main():
    """Main function"""
    # Parse command line arguments
    args = parse_arguments()
    
    # Get project root directory
    project_root = get_project_root()
    
    # Configuration file path
    config_path = project_root / args.config
    
    try:
        # Read configuration
        config = read_config(config_path)
        
        # Get analysis directory from config
        analysis_base_dir = config.get('paths', {}).get('analysis_dir', './analysis')
        # Convert relative path to absolute if needed
        if analysis_base_dir.startswith('./') or analysis_base_dir.startswith('../'):
            analysis_dir = project_root / analysis_base_dir.lstrip('./')
        else:
            analysis_dir = Path(analysis_base_dir)
        
        # Determine JSON file path
        if args.json:
            json_file_path = Path(args.json)
        elif args.pr:
            try:
                json_file_path = find_pr_json_file(args.pr, args.repo, project_root, config)
                logger.info(f"Found JSON file for PR #{args.pr}: {json_file_path}")
            except FileNotFoundError as e:
                logger.error(str(e))
                sys.exit(1)
        
        logger.info(f"Reading PR data from {json_file_path}")
        pr_data = read_pr_data(json_file_path)
        
        # Get output language
        output_language = args.language
        logger.info(f"Output language: {output_language} ({LANGUAGE_NAMES.get(output_language, 'Unknown')})")
        
        # Read prompt template
        prompt_path = project_root / "prompt" / "analyze_pr.prompt"
        prompt_template = read_prompt_template(prompt_path)
        
        # Prepare prompt
        logger.info("Preparing prompt for LLM API")
        prompt = prepare_prompt(pr_data, prompt_template, output_language)
        
        # Save diff as patch file if requested
        if args.save_diff:
            logger.info("Saving PR diff as patch file")
            # Extract repository name and PR number for filename prefix
            repo = pr_data.get('repository', 'unknown')
            repo_name = repo.split('/')[-1]
            pr_number = pr_data.get('number', 'unknown')
            filename_prefix = f"pr_{pr_number}"
            
            # Use the same directory structure as for analysis reports
            current_date = datetime.now()
            month_dir = current_date.strftime('%Y-%m')  # Format: YYYY-MM
            diff_output_dir = analysis_dir / repo_name / month_dir
            
            # Save diff patch
            diff_file_path = save_diff_patch(pr_data, diff_output_dir, filename_prefix)
            if diff_file_path:
                print(f"Diff patch file saved to: {diff_file_path}")
        
        # Call LLM API
        if args.dry_run:
            logger.info("Dry run mode: Saving prompt without making API call")
        else:
            logger.info("Calling LLM API to generate analysis")
        
        provider = get_provider_from_config(config)
        response = call_llm_api(prompt, config, provider, dry_run=args.dry_run)
        
        # If dry run, just print the response and exit
        if args.dry_run:
            logger.info(response)
            print(response)
            return
        
        # Save analysis report
        logger.info("Saving analysis report")
        output_path = save_analysis_report(response, pr_data, analysis_dir, output_language)
        logger.info(f"Analysis report saved to {output_path}")
        
        # Print report path
        print(f"Analysis report saved to: {output_path}")
        
    except Exception as e:
        logger.error(f"Error analyzing PR: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 