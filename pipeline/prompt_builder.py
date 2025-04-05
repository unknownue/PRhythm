#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Prompt Builder for PRhythm.
This module handles the construction of prompts for LLM analysis of PRs.
"""

import logging
import os
from pathlib import Path
from typing import Dict, List, Any, Optional, Union

from utils.languages import get_language_name
from utils.file_utils import read_text

# Setup logger
logger = logging.getLogger("prompt_builder")

class PromptBuilder:
    """
    Builds prompts for LLM analysis of PRs.
    This class handles prompt template loading and customization.
    """
    
    def __init__(self, template_dir: Optional[Union[str, Path]] = None):
        """
        Initialize prompt builder
        
        Args:
            template_dir: Directory containing prompt templates (optional)
        """
        if template_dir:
            self.template_dir = Path(template_dir)
        else:
            # Default to project templates directory
            script_dir = Path(os.path.dirname(os.path.abspath(__file__)))
            self.template_dir = script_dir.parent / "templates"
        
        # Ensure template directory exists
        if not self.template_dir.exists():
            logger.warning(f"Template directory not found: {self.template_dir}")
            os.makedirs(self.template_dir, exist_ok=True)
    
    def load_template(self, template_name: str = "pr_analysis") -> str:
        """
        Load prompt template
        
        Args:
            template_name: Template name without extension
            
        Returns:
            str: Prompt template
            
        Raises:
            FileNotFoundError: If template file not found
        """
        # First try to load from prompt directory
        prompt_path = Path(os.path.dirname(os.path.abspath(__file__))).parent / "prompt" / f"{template_name}.prompt"
        
        # Then try project templates directory
        template_path = self.template_dir / f"{template_name}.txt"
        
        if prompt_path.exists():
            return read_text(prompt_path)
        elif template_path.exists():
            return read_text(template_path)
        else:
            # Template file is required
            raise FileNotFoundError(f"Required template file not found at {prompt_path} or {template_path}")
    
    def build_pr_analysis_prompt(self, pr_data: Dict[str, Any], language_code: str = "en") -> str:
        """
        Build PR analysis prompt from PR data
        
        Args:
            pr_data: PR data
            language_code: Output language code
            
        Returns:
            str: Formatted prompt
        """
        # Load template
        template = self.load_template("analyze_pr")
        
        # Extract relevant data
        pr_title = pr_data.get("title", "No title")
        pr_number = pr_data.get("number", "Unknown")
        pr_url = pr_data.get("url", "No URL")
        pr_author = pr_data.get("author", {}).get("login", "Unknown")
        pr_body = pr_data.get("body", "No description")
        pr_repo = pr_data.get("repository", "Unknown")
        pr_state = pr_data.get("state", "Unknown")
        pr_created_at = pr_data.get("createdAt", "Unknown")
        
        # Handle merged information
        pr_merged_at = pr_data.get("mergedAt", "")
        if not pr_merged_at:
            pr_merged_at = "Not merged"
            
        # Handle merged by information
        pr_merged_by = "N/A"
        if pr_data.get("mergedBy"):
            pr_merged_by = pr_data.get("mergedBy", {}).get("login", "Unknown")
            
        # Handle labels
        pr_labels = ", ".join([label.get("name", "") for label in pr_data.get("labels", [])])
        if not pr_labels:
            pr_labels = "None"
        
        # Prepare file changes summary
        file_changes_summary = self._prepare_file_changes_summary(pr_data)
        
        # Prepare architecture context
        architecture_context = self._prepare_architecture_context(pr_data)
        
        # Prepare language context
        language_name = get_language_name(language_code)
        
        # Prepare diff excerpt
        diff_excerpt = self._prepare_diff_excerpt(pr_data)
        
        # Fill template
        prompt = template.format(
            PR_TITLE=pr_title,
            PR_NUMBER=pr_number,
            PR_URL=pr_url,
            PR_AUTHOR=pr_author,
            PR_BODY=pr_body,
            PR_REPOSITORY=pr_repo,
            PR_STATE=pr_state,
            PR_CREATED_AT=pr_created_at,
            PR_MERGED_AT=pr_merged_at,
            PR_MERGED_BY=pr_merged_by,
            PR_LABELS=pr_labels,
            FILE_CHANGES_SUMMARY=file_changes_summary,
            ARCHITECTURE_CONTEXT=architecture_context,
            OUTPUT_LANGUAGE=language_name,
            OUTPUT_LANGUAGE_CODE=language_code,
            DIFF_EXCERPT=diff_excerpt
        )
        
        return prompt
    
    def _prepare_file_changes_summary(self, pr_data: Dict[str, Any]) -> str:
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
            key=lambda x: x.get('changes', x.get('additions', 0) + x.get('deletions', 0)), 
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
    
    def _prepare_architecture_context(self, pr_data: Dict[str, Any]) -> str:
        """
        Prepare architecture context for the prompt
        
        Args:
            pr_data: PR data
            
        Returns:
            str: Architecture context
        """
        # Extract file paths from PR data
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
    
    def _prepare_diff_excerpt(self, pr_data: Dict[str, Any], max_length: int = 2000) -> str:
        """
        Prepare an excerpt of the PR diff
        
        Args:
            pr_data: PR data
            max_length: Maximum length of the excerpt
            
        Returns:
            str: Diff excerpt
        """
        diff = pr_data.get('diff', '')
        
        if not diff:
            return "No diff found in the PR data"
        
        # If diff is too long, truncate it
        if len(diff) > max_length:
            return diff[:max_length] + f"\n\n[Diff truncated, total length: {len(diff)} characters]"
        
        return diff
