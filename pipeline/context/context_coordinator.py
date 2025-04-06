"""
Context coordinator module for PR context extraction.
This module coordinates the extraction of context from PRs.
"""

import logging
import os
import json
from typing import Any, Dict, List, Optional, Union

from pipeline.agent.agent_manager import AgentManager
from pipeline.agent.llm_providers.base_provider import LLMProvider
from pipeline.agent.tools.git_tools import GitTools
from pipeline.context.code_units import CodeUnitExtractor
from pipeline.context.code_relations import RelationDetector
from pipeline.context.embeddings.code_embeddings import CodeEmbeddings

# Setup logger
logger = logging.getLogger("context_coordinator")

class ContextExtractor:
    """
    Coordinates the extraction of context from PRs.
    """
    
    def __init__(self, repo_path: str, llm_provider: Optional[LLMProvider] = None):
        """
        Initialize the context extractor.
        
        Args:
            repo_path: Path to the repository
            llm_provider: LLM provider to use
        """
        self.repo_path = repo_path
        self.llm_provider = llm_provider
        
        self.code_unit_extractor = CodeUnitExtractor()
        self.relation_detector = RelationDetector()
        self.git_tools = GitTools(repo_path)
        
        self.agent_manager = None
        if llm_provider:
            self.agent_manager = AgentManager(llm_provider)
        
        # Initialize embeddings generator
        self.embedding_model = CodeEmbeddings()
        
        logger.debug(f"Initialized ContextExtractor with repo_path: {repo_path}")
    
    def set_llm_provider(self, llm_provider: LLMProvider):
        """
        Set the LLM provider.
        
        Args:
            llm_provider: LLM provider to use
        """
        self.llm_provider = llm_provider
        self.agent_manager = AgentManager(llm_provider)
        logger.debug("Set LLM provider")
    
    def extract_context_from_diff(self, diff_content: str) -> Dict[str, Any]:
        """
        Extract context from a diff.
        
        Args:
            diff_content: Diff content
            
        Returns:
            Dict[str, Any]: Extracted context
        """
        logger.debug("Starting context extraction from diff")
        
        if not self.llm_provider:
            raise ValueError("LLM provider is required for context extraction")
        
        # Parse the diff to get modified files
        modified_files = self._parse_diff(diff_content)
        
        # Extract context
        return self._extract_context(modified_files, diff_content)
    
    def _parse_diff(self, diff_content: str) -> List[Dict[str, Any]]:
        """
        Parse a diff to extract modified files.
        
        Args:
            diff_content: Diff content
            
        Returns:
            List[Dict[str, Any]]: List of modified files
        """
        logger.debug("Parsing diff")
        
        # Simple diff parser to extract added, modified, and deleted files
        modified_files = []
        current_file = None
        
        for line in diff_content.split('\n'):
            if line.startswith('diff --git '):
                # Extract the file path
                parts = line.split(' ')
                if len(parts) >= 3:
                    file_path = parts[2][2:]  # Remove 'a/' prefix
                    current_file = {
                        "file_path": file_path,
                        "status": "modified",
                        "changes": []
                    }
                    modified_files.append(current_file)
            
            elif line.startswith('new file mode'):
                if current_file:
                    current_file["status"] = "added"
            
            elif line.startswith('deleted file mode'):
                if current_file:
                    current_file["status"] = "deleted"
            
            elif line.startswith('+++') or line.startswith('---'):
                # Skip these lines
                continue
            
            elif line.startswith('+') or line.startswith('-'):
                # Record the change
                if current_file:
                    current_file["changes"].append(line)
        
        return modified_files
    
    def _extract_context(self, modified_files: List[Dict[str, Any]], diff_content: str) -> Dict[str, Any]:
        """
        Extract context from modified files.
        
        Args:
            modified_files: List of modified files
            diff_content: Diff content
            
        Returns:
            Dict[str, Any]: Extracted context
        """
        logger.debug(f"Extracting context from {len(modified_files)} modified files")
        
        # Collect code units from modified files
        all_code_units = []
        
        for file_info in modified_files:
            file_path = file_info["file_path"]
            status = file_info["status"]
            
            logger.debug(f"Processing {status} file: {file_path}")
            
            # Skip deleted files
            if status == "deleted":
                continue
            
            # Get the full file path
            full_path = os.path.join(self.repo_path, file_path)
            
            # If the file exists, extract code units
            if os.path.exists(full_path):
                file_units = self.code_unit_extractor.extract_units_from_file(full_path)
                all_code_units.extend(file_units)
        
        # Detect relations between code units
        relation_graph = self.relation_detector.build_relation_graph(all_code_units)
        
        # Generate embeddings for code units
        embedded_units = self.embedding_model.embed_code_units(all_code_units)
        
        # Analyze the PR using agents if available
        pr_analysis = {}
        if self.agent_manager:
            # Create an analysis agent
            analysis_agent = self.agent_manager.create_agent(
                "ContextAnalysisAgent",
                {
                    "repo_path": self.repo_path,
                    "diff_content": diff_content
                }
            )
            
            # Run the analysis
            pr_analysis = analysis_agent.execute_task("analyze_pr_context", {
                "modified_files": modified_files,
                "code_units": embedded_units,
                "relation_graph": relation_graph
            })
        
        # Combine all extracted information
        context = {
            "modified_files": modified_files,
            "code_units": embedded_units,
            "relation_graph": relation_graph,
            "pr_analysis": pr_analysis,
            "metadata": {
                "repo_path": self.repo_path,
                "extraction_time": self.git_tools.get_current_time()
            }
        }
        
        logger.debug("Context extraction completed")
        return context 