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
import re
import subprocess
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
    
    # Prepare multilingual instructions and format
    multilingual_instruction = prepare_multilingual_instruction(output_language)
    multilingual_format = prepare_multilingual_format(output_language)
    
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
        'multilingual_instruction': multilingual_instruction,
        'multilingual_format': multilingual_format,
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
    prompt = prompt.replace("{multilingual_instruction}", multilingual_instruction)
    prompt = prompt.replace("{multilingual_format}", multilingual_format)
    
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

def prepare_multilingual_instruction(output_language):
    """
    Prepare multilingual instruction based on output language
    
    Args:
        output_language: Output language
        
    Returns:
        str: Multilingual instruction
    """
    if output_language == "multilingual":
        return """
Generate your analysis in multiple languages. For each language section:
1. Use the appropriate language for all content except code and technical terms
2. Maintain consistent structure across all language versions
3. Ensure each language version is complete and standalone
"""
    else:
        return f"""
Generate your analysis in {output_language}.
"""

def prepare_multilingual_format(output_language):
    """
    Prepare multilingual format based on output language
    
    Args:
        output_language: Output language
        
    Returns:
        str: Multilingual format
    """
    if output_language == "multilingual":
        return """
# English Version
[Complete English analysis here]

---

# 中文版本 (Chinese Version)
[Complete Chinese analysis here]

---

# [Additional language versions as specified in the configuration]
[Complete analysis in additional languages here]
"""
    else:
        return ""  # Empty string for single language output

def save_multilingual_reports(report, pr_data, output_dir, languages):
    """
    Save multilingual reports to separate files
    
    Args:
        report: Analysis report (containing multiple language versions)
        pr_data: PR data
        output_dir: Output directory
        languages: List of languages
        
    Returns:
        list: Paths to the saved files
    """
    # Extract repository name from owner/repo format
    repo = pr_data.get('repository', 'unknown')
    repo_name = repo.split('/')[-1]
    
    # Get current date for month-based directory
    current_date = datetime.now()
    month_dir = current_date.strftime('%Y-%m')  # Format: YYYY-MM
    
    # Create repository-specific directory
    repo_output_dir = output_dir / repo_name / month_dir
    repo_output_dir.mkdir(exist_ok=True, parents=True)
    
    # Get PR number
    pr_number = pr_data.get('number', 'unknown')
    
    # Base timestamp for all files
    timestamp = current_date.strftime('%Y%m%d_%H%M%S')
    
    # Split the report into language sections
    language_sections = split_multilingual_report(report, languages)
    
    saved_files = []
    
    # Save each language section to a separate file
    for lang, content in language_sections.items():
        filename = f"pr_{pr_number}_{lang}_{timestamp}.md"
        file_path = repo_output_dir / filename
        
        try:
            with open(file_path, 'w', encoding='utf-8') as file:
                file.write(content)
            saved_files.append(file_path)
        except Exception as e:
            print(f"Error saving {lang} analysis report: {e}")
    
    return saved_files

def split_multilingual_report(report, languages):
    """
    Split a multilingual report into separate language sections
    
    Args:
        report: Multilingual report
        languages: List of languages
        
    Returns:
        dict: Language sections
    """
    # Define language markers
    language_markers = {
        'en': ['# English Version', '# English'],
        'zh-cn': ['# 中文版本', '# Chinese Version', '# 中文版本 (Chinese Version)'],
        'ja': ['# 日本語版', '# Japanese Version', '# 日本語版 (Japanese Version)'],
        'ko': ['# 한국어 버전', '# Korean Version', '# 한국어 버전 (Korean Version)'],
        'fr': ['# Version Française', '# French Version', '# Version Française (French Version)'],
        'de': ['# Deutsche Version', '# German Version', '# Deutsche Version (German Version)'],
        'es': ['# Versión en Español', '# Spanish Version', '# Versión en Español (Spanish Version)']
    }
    
    # Initialize result dictionary
    result = {}
    
    # If the report doesn't contain language markers, it's a single language report
    if not any(marker in report for markers in language_markers.values() for marker in markers):
        # Assume it's in the primary language (first in the list)
        if languages:
            result[languages[0]] = report
        else:
            result['en'] = report  # Default to English
        return result
    
    # Split the report by language markers
    lines = report.split('\n')
    current_lang = None
    current_content = []
    
    for line in lines:
        # Check if this line is a language marker
        found_marker = False
        for lang, markers in language_markers.items():
            if any(marker in line for marker in markers):
                # Save previous language content if exists
                if current_lang and current_content:
                    result[current_lang] = '\n'.join(current_content)
                
                # Start new language section
                current_lang = lang
                current_content = [line]
                found_marker = True
                break
        
        if not found_marker and current_lang:
            current_content.append(line)
    
    # Save the last language section
    if current_lang and current_content:
        result[current_lang] = '\n'.join(current_content)
    
    return result

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
        
        # Fall back to default LLM API key only if using the default provider
        if not api_key and provider.lower() == config.get('llm', {}).get('provider', 'openai').lower():
            api_key = config.get('llm', {}).get('api_key', '')
            if not api_key:
                api_key = os.environ.get('LLM_API_KEY', '')
    
    if not api_key:
        print(f"Error: API key for provider '{provider}' not found in configuration or environment variables")
        print(f"Please set {provider.upper()}_API_KEY environment variable or configure it in config.yaml")
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
    
    # Create repository-specific directory
    repo_output_dir = output_dir / repo_name / month_dir
    repo_output_dir.mkdir(exist_ok=True, parents=True)
    
    # Create a filename
    pr_number = pr_data.get('number', 'unknown')
    filename = f"pr_{pr_number}_{output_language}_{current_date.strftime('%Y%m%d_%H%M%S')}.md"
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
    parser.add_argument('--json', help='Path to the PR JSON file')
    parser.add_argument('--repo', help='Repository name (owner/repo) - used to find the latest PR JSON file if --json is not specified')
    parser.add_argument('--pr', type=int, help='PR number - used to find the latest PR JSON file if --json is not specified')
    parser.add_argument('--language', default='', help='Output language (e.g., en, zh-cn, multilingual)')
    parser.add_argument('--config', default='config.yaml', help='Path to the configuration file')
    parser.add_argument('--provider', help='LLM provider to use (overrides config)')
    parser.add_argument('--dry-run', action='store_true', help='Only print the prompt without sending the request')
    parser.add_argument('--repo-path', help='Path to local repository clone (optional, for better context)')
    return parser.parse_args()

def find_latest_pr_json(project_root, repo, pr_number):
    """
    Find the latest PR JSON file for a given repository and PR number
    
    Args:
        project_root: Project root directory
        repo: Repository name (owner/repo)
        pr_number: PR number
        
    Returns:
        Path: Path to the latest PR JSON file, or None if not found
    """
    # Extract repo name from owner/repo format
    repo_name = repo.split('/')[-1]
    
    # Base output directory for fetch_pr_info.py
    output_dir = project_root / "output" / repo_name
    
    if not output_dir.exists():
        return None
    
    # First try to find in all month directories
    # Find all month directories (format: YYYY-MM)
    month_dirs = sorted([d for d in output_dir.iterdir() if d.is_dir() and re.match(r'\d{4}-\d{2}', d.name)], reverse=True)
    
    # First search in month directories
    for month_dir in month_dirs:
        # Find all JSON files for the specified PR in this month directory
        pr_files = list(month_dir.glob(f"pr_{pr_number}_*.json"))
        
        # Sort by modification time (newest first)
        if pr_files:
            pr_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            return pr_files[0]
    
    # If not found in month directories, search in main directory
    pr_files = list(output_dir.glob(f"pr_{pr_number}_*.json"))
    # Sort by modification time (newest first)
    if pr_files:
        pr_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        return pr_files[0]
    
    return None

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
    
    # Determine JSON file path
    json_file_path = None
    
    if args.json:
        # User specified a JSON file path
        json_file_path = Path(args.json)
        if not json_file_path.is_absolute():
            json_file_path = project_root / json_file_path
    elif args.repo and args.pr:
        # Try to find the latest PR JSON file
        json_file_path = find_latest_pr_json(project_root, args.repo, args.pr)
        if not json_file_path:
            print(f"Error: Could not find PR JSON file for repository {args.repo} and PR #{args.pr}")
            print("Please run fetch_pr_info.py first or specify the JSON file path using --json")
            sys.exit(1)
        print(f"Using latest PR JSON file: {json_file_path}")
    else:
        print("Error: Either --json or both --repo and --pr must be specified")
        sys.exit(1)
    
    # Read PR data
    pr_data = read_pr_data(json_file_path)
    
    # Check if module context is already in PR data
    if 'module_context' not in pr_data:
        print("Warning: Module context not found in PR data. Please run fetch_pr_info.py first.")
        print("Continuing with limited context...")
    else:
        print(f"Using pre-computed module context for {len(pr_data['module_context'].get('modules', {}))} modules")
    
    # Check if commit analysis is already in PR data
    if 'commit_analysis' not in pr_data:
        print("Warning: Commit analysis not found in PR data. Please run fetch_pr_info.py first.")
        print("Continuing with limited analysis...")
    else:
        print("Using pre-computed commit analysis")
    
    # Read prompt template
    prompt_path = project_root / "prompt" / "analyze_pr.prompt"
    prompt_template = read_prompt_template(prompt_path)
    
    # Determine output language
    output_language = args.language
    if not output_language:
        # Use configuration setting if not specified in command line
        if config.get('output', {}).get('multilingual', False):
            output_language = "multilingual"
        else:
            output_language = config.get('output', {}).get('primary_language', 'en')
    
    # Prepare prompt
    prompt = prepare_prompt(pr_data, prompt_template, output_language)
    
    print(f"Analyzing PR #{pr_data.get('number', 'unknown')} from repository {pr_data.get('repository', 'unknown')}...")
    print(f"Output language: {output_language}")
    
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
    
    # Save analysis report(s)
    if output_language == "multilingual":
        # Get languages from config
        languages = config.get('output', {}).get('languages', ['en', 'zh-cn'])
        
        # Save multilingual reports
        file_paths = save_multilingual_reports(report, pr_data, output_dir, languages)
        
        print(f"Multilingual analysis reports saved to:")
        for path in file_paths:
            print(f"- {path}")
    else:
        # Save single language report
        file_path = save_analysis_report(report, pr_data, output_dir, output_language)
        print(f"Analysis report saved to: {file_path}")

if __name__ == "__main__":
    main() 