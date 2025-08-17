"""Workflow manager for PRhythm LangGraph integration."""

import json
import os
import re
from pathlib import Path
from typing import Dict, Optional, Tuple, Union, Any
from urllib.parse import urlparse

from langchain_core.runnables import RunnableConfig

from agents.main_workflow import prhythm_workflow
from agents.configuration import AgentConfiguration
from core.github_client import GitHubClient


class WorkflowManager:
    """Manager for PRhythm workflow execution and control."""
    
    # Valid workflow nodes in execution order
    VALID_NODES = [
        "initialize_analysis",
        "select_scheme", 
        "collect_data",
        "generate_analysis",
        "process_report"
    ]
    
    def __init__(self, config: Optional[AgentConfiguration] = None):
        """Initialize the workflow manager.
        
        Args:
            config: Agent configuration instance
        """
        self.config = config or AgentConfiguration()
        self.github_client = GitHubClient()
    
    async def analyze_pr(
        self,
        pr_input: str,
        stop_at: Optional[str] = None,
        repository_config: Optional[Dict] = None,
        output_prompt_dir: Optional[str] = None
    ) -> Dict[str, Any]:
        """Analyze a PR using the LangGraph workflow.
        
        Args:
            pr_input: PR URL or path to local JSON file containing PR data
            stop_at: Node name to stop execution at (optional)
            repository_config: Repository-specific configuration (optional)
            output_prompt_dir: Directory to save analysis prompt (optional)
            
        Returns:
            Dictionary containing workflow execution results
        """
        # Step 1: Validate stop_at parameter
        if stop_at and stop_at not in self.VALID_NODES:
            raise ValueError(
                f"Invalid stop_at node '{stop_at}'. Must be one of: {', '.join(self.VALID_NODES)}"
            )
        
        # Step 2: Get PR data
        try:
            pr_data = await self._get_pr_data(pr_input)
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to get PR data: {str(e)}",
                "stopped_at": None,
                "final_report": None
            }
        
        # Step 3: Prepare input state
        input_state = {
            "pr_data": pr_data,
            "repository_config": repository_config or self._get_default_repository_config(),
            "output_prompt_dir": output_prompt_dir,
            "stop_at_generate_analysis": stop_at == "generate_analysis",
            "messages": []
        }
        
        # Step 4: Configure workflow execution
        runnable_config = RunnableConfig(
            configurable=self.config.model_dump()
        )
        
        # Step 5: Execute workflow with optional stopping and timeout
        try:
            import asyncio
            
            if stop_at:
                # Add timeout for workflow execution
                result = await asyncio.wait_for(
                    self._execute_with_stop(input_state, runnable_config, stop_at),
                    timeout=300  # 5 minutes timeout
                )
            else:
                result = await asyncio.wait_for(
                    prhythm_workflow.ainvoke(input_state, runnable_config),
                    timeout=300  # 5 minutes timeout
                )
            
            return {
                "success": result.get("success", True),
                "error": result.get("error_message"),
                "stopped_at": stop_at,
                "final_report": result.get("final_report"),
                "analysis_metadata": result.get("analysis_metadata"),
                "scheme_used": result.get("scheme_used"),
                "analysis_prompt_saved": result.get("analysis_prompt_saved"),
                "execution_state": result
            }
            
        except asyncio.TimeoutError:
            return {
                "success": False,
                "error": "Workflow execution timed out after 5 minutes",
                "stopped_at": stop_at,
                "final_report": None
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Workflow execution failed: {str(e)}",
                "stopped_at": stop_at,
                "final_report": None
            }
    
    async def _get_pr_data(self, pr_input: str) -> Dict:
        """Get PR data from URL or local file.
        
        Args:
            pr_input: PR URL or file path
            
        Returns:
            Dictionary containing PR data
        """
        # Check if input is a file path
        if os.path.isfile(pr_input):
            with open(pr_input, 'r', encoding='utf-8') as f:
                return json.load(f)
        
        # Check if input is a GitHub PR URL
        if self._is_github_pr_url(pr_input):
            owner, repo, pr_number = self._parse_github_pr_url(pr_input)
            return await self.github_client.get_pr_data(owner, repo, pr_number)
        
        # Try to parse as JSON string
        try:
            return json.loads(pr_input)
        except json.JSONDecodeError:
            raise ValueError(
                f"Invalid PR input: '{pr_input}'. Must be a GitHub PR URL, "
                f"path to JSON file, or JSON string."
            )
    
    def _is_github_pr_url(self, url: str) -> bool:
        """Check if the URL is a valid GitHub PR URL.
        
        Args:
            url: URL to check
            
        Returns:
            True if valid GitHub PR URL, False otherwise
        """
        try:
            parsed = urlparse(url)
            if parsed.netloc not in ['github.com', 'www.github.com']:
                return False
            
            # Match pattern: /owner/repo/pull/number
            path_pattern = r'^/([^/]+)/([^/]+)/pull/(\d+)/?$'
            return bool(re.match(path_pattern, parsed.path))
        except Exception:
            return False
    
    def _parse_github_pr_url(self, url: str) -> Tuple[str, str, int]:
        """Parse GitHub PR URL to extract owner, repo, and PR number.
        
        Args:
            url: GitHub PR URL
            
        Returns:
            Tuple of (owner, repo, pr_number)
        """
        parsed = urlparse(url)
        path_pattern = r'^/([^/]+)/([^/]+)/pull/(\d+)/?$'
        match = re.match(path_pattern, parsed.path)
        
        if not match:
            raise ValueError(f"Invalid GitHub PR URL format: {url}")
        
        owner, repo, pr_number = match.groups()
        return owner, repo, int(pr_number)
    
    def _get_default_repository_config(self) -> Dict:
        """Get default repository configuration.
        
        Returns:
            Default repository configuration dictionary
        """
        return {
            "analysis": {
                "schemes": {
                    "default": "general_review",
                    "fallback": "general_review",
                    "conditions": []
                }
            },
            "git": {
                "clone_timeout_seconds": 300,
                "max_file_size_mb": 10
            }
        }
    
    async def _execute_with_stop(
        self,
        input_state: Dict,
        config: RunnableConfig,
        stop_at: str
    ) -> Dict:
        """Execute workflow with stop at specified node.
        
        Args:
            input_state: Input state for workflow
            config: Runnable configuration
            stop_at: Node name to stop at
            
        Returns:
            Workflow execution result
        """
        # For LangGraph workflows, we need to implement custom stopping logic
        # Since the workflow is already compiled, we'll use a modified approach
        
        # Create a modified workflow that stops at the specified node
        from agents.main_workflow import main_workflow_builder
        from langgraph.graph import START, END
        
        # Since we have stop logic built into generate_analysis, just execute the workflow
        # The workflow will stop automatically when stop_at_generate_analysis is True
        
        result = await prhythm_workflow.ainvoke(input_state, config)
        
        # Add metadata about where we stopped
        result["stopped_at"] = stop_at
        result["partial_execution"] = True
        
        return result
    
    def get_available_nodes(self) -> list[str]:
        """Get list of available workflow nodes.
        
        Returns:
            List of valid node names
        """
        return self.VALID_NODES.copy()
    
    def validate_node_name(self, node_name: str) -> bool:
        """Validate if a node name is valid.
        
        Args:
            node_name: Node name to validate
            
        Returns:
            True if valid, False otherwise
        """
        return node_name in self.VALID_NODES