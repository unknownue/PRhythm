"""
Context Manager for PR context extraction.
This module provides the main entry point for PR context extraction.
"""

import logging
import json
import os
from typing import Any, Dict, List, Optional, Union

from pipeline.agent.llm_providers.base_provider import LLMProvider
from pipeline.agent.llm_providers.provider_factory import get_provider_from_config
from pipeline.context.context_coordinator import ContextExtractor
from pipeline.context.context_summarizer import ContextSummarizer
from pipeline.agent.tools.git_tools import GitTools

# Setup logger
logger = logging.getLogger("context_manager")

class ContextManager:
    """
    Context Manager that orchestrates the PR context extraction process.
    """
    
    def __init__(self, repo_path: str, config: Dict[str, Any] = None):
        """
        Initialize the context manager.
        
        Args:
            repo_path: Path to the repository
            config: Configuration dictionary
        """
        self.repo_path = repo_path
        self.config = config or {}
        self.llm_provider = None
        
        # Initialize the LLM provider
        if self.config:
            self.llm_provider = get_provider_from_config(self.config)
        
        # Initialize tools
        self.git_tools = GitTools(repo_path)
        
        # Initialize the context extractor and summarizer
        self.context_extractor = ContextExtractor(repo_path, self.llm_provider)
        self.context_summarizer = ContextSummarizer(self.llm_provider)
        
        logger.debug(f"Initialized ContextManager for repo: {repo_path}")
    
    def set_provider(self, llm_provider: LLMProvider):
        """
        Set the LLM provider manually.
        
        Args:
            llm_provider: LLM provider instance
        """
        self.llm_provider = llm_provider
        self.context_extractor.set_llm_provider(llm_provider)
        self.context_summarizer.set_llm_provider(llm_provider)
        logger.debug("Set LLM provider")
    
    def extract_context_from_pr(self, pr_number: int) -> Dict[str, Any]:
        """
        Extract context for a PR.
        
        Args:
            pr_number: PR number
            
        Returns:
            Dict[str, Any]: Extracted context
            
        Raises:
            RuntimeError: If the LLM provider is not configured
        """
        logger.debug(f"Extracting context for PR #{pr_number}")
        
        if not self.llm_provider:
            raise RuntimeError("LLM provider not configured. Use set_provider() or provide config in constructor.")
        
        # Get the PR diff
        diff_content = self._get_pr_diff(pr_number)
        if not diff_content:
            raise RuntimeError(f"Could not get diff for PR #{pr_number}")
        
        # Extract context from the diff
        context = self.context_extractor.extract_context_from_diff(diff_content)
        
        # Add PR metadata
        context["metadata"]["pr_number"] = pr_number
        
        return context
    
    def extract_context_from_diff(self, diff_content: str) -> Dict[str, Any]:
        """
        Extract context from a diff.
        
        Args:
            diff_content: Content of the diff
            
        Returns:
            Dict[str, Any]: Extracted context
            
        Raises:
            RuntimeError: If the LLM provider is not configured
        """
        logger.debug("Extracting context from diff")
        
        if not self.llm_provider:
            raise RuntimeError("LLM provider not configured. Use set_provider() or provide config in constructor.")
        
        # Extract context using the context extractor
        context = self.context_extractor.extract_context_from_diff(diff_content)
        
        return context
    
    def _get_pr_diff(self, pr_number: int) -> str:
        """
        Get the diff for a PR.
        
        Args:
            pr_number: PR number
            
        Returns:
            str: PR diff content
        """
        logger.debug(f"Getting diff for PR #{pr_number}")
        
        try:
            diff = self.git_tools.get_pr_diff(pr_number)
            return diff
        except Exception as e:
            logger.error(f"Error getting PR diff: {str(e)}")
            return ""
    
    def generate_summary(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a summary of the context.
        
        Args:
            context: Extracted context
            
        Returns:
            Dict[str, Any]: Summary of the context
        """
        logger.debug("Generating summary")
        
        if not self.llm_provider:
            raise RuntimeError("LLM provider not configured. Use set_provider() or provide config in constructor.")
        
        # Generate summary using the context summarizer
        summary = self.context_summarizer.generate_summary(context)
        
        return summary
    
    def save_context_to_file(self, context: Dict[str, Any], output_path: str) -> None:
        """
        Save extracted context to a file.
        
        Args:
            context: Extracted context
            output_path: Path to save the context to
        """
        logger.debug(f"Saving context to {output_path}")
        
        try:
            # Create the directory if it doesn't exist
            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
            
            with open(output_path, 'w') as f:
                json.dump(context, f, indent=2)
            logger.debug(f"Context saved to {output_path}")
        except Exception as e:
            logger.error(f"Error saving context: {str(e)}")
            raise RuntimeError(f"Could not save context to {output_path}: {str(e)}")
    
    def load_context_from_file(self, input_path: str) -> Dict[str, Any]:
        """
        Load context from a file.
        
        Args:
            input_path: Path to load the context from
            
        Returns:
            Dict[str, Any]: Loaded context
        """
        logger.debug(f"Loading context from {input_path}")
        
        try:
            with open(input_path, 'r') as f:
                context = json.load(f)
            logger.debug(f"Context loaded from {input_path}")
            return context
        except Exception as e:
            logger.error(f"Error loading context: {str(e)}")
            raise RuntimeError(f"Could not load context from {input_path}: {str(e)}")
    
    def save_summary_to_file(self, summary: Dict[str, Any], output_path: str) -> None:
        """
        Save summary to a file.
        
        Args:
            summary: Context summary
            output_path: Path to save the summary to
        """
        logger.debug(f"Saving summary to {output_path}")
        
        try:
            # Create the directory if it doesn't exist
            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
            
            with open(output_path, 'w') as f:
                json.dump(summary, f, indent=2)
            logger.debug(f"Summary saved to {output_path}")
        except Exception as e:
            logger.error(f"Error saving summary: {str(e)}")
            raise RuntimeError(f"Could not save summary to {output_path}: {str(e)}")
    
    def extract_and_summarize(self, pr_number: int = None, diff_content: str = None) -> Dict[str, Any]:
        """
        Extract context and generate a summary.
        
        Args:
            pr_number: PR number (optional)
            diff_content: Diff content (optional)
            
        Returns:
            Dict[str, Any]: Dictionary with context and summary
            
        Raises:
            ValueError: If neither pr_number nor diff_content is provided
        """
        logger.debug("Extracting context and generating summary")
        
        if not pr_number and not diff_content:
            raise ValueError("Either pr_number or diff_content must be provided")
        
        # Extract context
        if pr_number:
            context = self.extract_context_from_pr(pr_number)
        else:
            context = self.extract_context_from_diff(diff_content)
        
        # Generate summary
        summary = self.generate_summary(context)
        
        return {
            "context": context,
            "summary": summary
        } 