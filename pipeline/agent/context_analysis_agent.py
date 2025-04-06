"""
Context analysis agent for PR context extraction.
"""

import logging
import os
from typing import Any, Dict, List, Optional, Union

from pipeline.agent.base_agent import BaseAgent
from pipeline.agent.tools.git_tools import GitTools
from pipeline.agent.tools.vector_tools import vectorstore_search

# Setup logger
logger = logging.getLogger("context_analysis_agent")

class ContextAnalysisAgent(BaseAgent):
    """
    Agent for analyzing PR context.
    """
    
    def __init__(self, llm_provider, config: Dict[str, Any]):
        """
        Initialize the context analysis agent.
        
        Args:
            llm_provider: LLM provider to use
            config: Configuration for the agent
        """
        super().__init__(llm_provider, config)
        self.repo_path = config.get("repo_path", "")
        self.diff_content = config.get("diff_content", "")
        self.git_tools = GitTools(self.repo_path)
        
        logger.debug(f"Initialized ContextAnalysisAgent with repo_path: {self.repo_path}")
    
    def analyze_pr_context(self, task_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze PR context.
        
        Args:
            task_params: Parameters for the task
                - modified_files: List of modified files
                - code_units: List of code units
                - relation_graph: Relation graph
                
        Returns:
            Dict[str, Any]: Analysis results
        """
        logger.debug("Starting PR context analysis")
        
        # Extract parameters
        modified_files = task_params.get("modified_files", [])
        code_units = task_params.get("code_units", [])
        relation_graph = task_params.get("relation_graph", {})
        
        # Analyze the PR
        results = self._analyze_pr(modified_files, code_units, relation_graph)
        
        logger.debug("PR context analysis completed")
        return results
    
    def _analyze_pr(self, modified_files: List[Dict[str, Any]], 
                   code_units: List[Dict[str, Any]], 
                   relation_graph: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze the PR.
        
        Args:
            modified_files: List of modified files
            code_units: List of code units
            relation_graph: Relation graph
            
        Returns:
            Dict[str, Any]: Analysis results
        """
        # Analyze the purpose of the PR
        purpose_analysis = self._analyze_pr_purpose(modified_files, code_units)
        
        # Analyze the scope of the PR
        scope_analysis = self._analyze_pr_scope(modified_files, code_units)
        
        # Analyze potential impacts
        impact_analysis = self._analyze_pr_impact(modified_files, code_units, relation_graph)
        
        # Identify key code units
        key_units = self._identify_key_units(code_units, relation_graph)
        
        # Search for related code
        related_code = self._find_related_code(code_units)
        
        return {
            "purpose": purpose_analysis,
            "scope": scope_analysis,
            "impact": impact_analysis,
            "key_units": key_units,
            "related_code": related_code
        }
    
    def _analyze_pr_purpose(self, modified_files: List[Dict[str, Any]],
                           code_units: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze the purpose of the PR.
        
        Args:
            modified_files: List of modified files
            code_units: List of code units
            
        Returns:
            Dict[str, Any]: Purpose analysis
        """
        logger.debug("Analyzing PR purpose")
        
        # Extract file types and areas of code being modified
        file_types = {}
        code_areas = {}
        
        for file_info in modified_files:
            file_path = file_info.get("file_path", "")
            if file_path:
                # Get file extension
                ext = os.path.splitext(file_path)[1]
                file_types[ext] = file_types.get(ext, 0) + 1
                
                # Get directory (code area)
                directory = os.path.dirname(file_path)
                code_areas[directory] = code_areas.get(directory, 0) + 1
        
        # Use LLM to analyze the purpose based on the modified files and code units
        prompt = f"""
        Analyze the purpose of the PR based on the following:
        
        Modified files: {[f['file_path'] for f in modified_files]}
        File types: {file_types}
        Code areas: {code_areas}
        
        Provide a brief description of what this PR is trying to achieve.
        """
        
        purpose_description = self.llm_provider.generate_text(prompt)
        
        # Determine likely categories
        categories = self._categorize_pr(modified_files, code_units, purpose_description)
        
        return {
            "description": purpose_description,
            "file_types": file_types,
            "code_areas": code_areas,
            "categories": categories
        }
    
    def _categorize_pr(self, modified_files: List[Dict[str, Any]],
                      code_units: List[Dict[str, Any]],
                      purpose_description: str) -> List[str]:
        """
        Categorize the PR.
        
        Args:
            modified_files: List of modified files
            code_units: List of code units
            purpose_description: Description of the PR purpose
            
        Returns:
            List[str]: Categories
        """
        # Use LLM to categorize the PR
        prompt = f"""
        Based on the following information, categorize this PR into one or more of these categories:
        - feature: Adding new functionality
        - bugfix: Fixing a bug
        - refactor: Restructuring code without changing functionality
        - test: Adding or modifying tests
        - docs: Updating documentation
        - style: Formatting, whitespace changes
        - performance: Performance improvements
        - dependency: Updating dependencies
        - security: Fixing security issues
        
        PR purpose: {purpose_description}
        Modified files: {[f['file_path'] for f in modified_files]}
        
        Return a list of applicable categories.
        """
        
        response = self.llm_provider.generate_text(prompt)
        
        # Parse the response to extract categories
        categories = []
        for line in response.split('\n'):
            line = line.strip().lower()
            if line in ["feature", "bugfix", "refactor", "test", "docs", "style", 
                       "performance", "dependency", "security"]:
                categories.append(line)
        
        return categories
    
    def _analyze_pr_scope(self, modified_files: List[Dict[str, Any]],
                         code_units: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze the scope of the PR.
        
        Args:
            modified_files: List of modified files
            code_units: List of code units
            
        Returns:
            Dict[str, Any]: Scope analysis
        """
        logger.debug("Analyzing PR scope")
        
        # Count different file statuses
        status_counts = {"added": 0, "modified": 0, "deleted": 0}
        for file_info in modified_files:
            status = file_info.get("status", "")
            if status in status_counts:
                status_counts[status] += 1
        
        # Count different code unit types
        unit_type_counts = {}
        for unit in code_units:
            unit_type = unit.get("type", "")
            if unit_type:
                unit_type_counts[unit_type] = unit_type_counts.get(unit_type, 0) + 1
        
        # Determine the scope size
        scope_size = self._determine_scope_size(modified_files, code_units)
        
        # Analyze the complexity of the changes
        complexity = self._analyze_complexity(modified_files, code_units)
        
        return {
            "status_counts": status_counts,
            "unit_type_counts": unit_type_counts,
            "scope_size": scope_size,
            "complexity": complexity
        }
    
    def _determine_scope_size(self, modified_files: List[Dict[str, Any]],
                             code_units: List[Dict[str, Any]]) -> str:
        """
        Determine the size of the PR scope.
        
        Args:
            modified_files: List of modified files
            code_units: List of code units
            
        Returns:
            str: Scope size (small, medium, large)
        """
        num_files = len(modified_files)
        num_units = len(code_units)
        
        # Count the number of changes
        num_changes = 0
        for file_info in modified_files:
            num_changes += len(file_info.get("changes", []))
        
        # Determine the scope size based on the number of files, units, and changes
        if num_files <= 3 and num_units <= 10 and num_changes <= 50:
            return "small"
        elif num_files <= 10 and num_units <= 30 and num_changes <= 200:
            return "medium"
        else:
            return "large"
    
    def _analyze_complexity(self, modified_files: List[Dict[str, Any]],
                           code_units: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze the complexity of the PR.
        
        Args:
            modified_files: List of modified files
            code_units: List of code units
            
        Returns:
            Dict[str, Any]: Complexity analysis
        """
        # Count the number of changes
        num_changes = 0
        for file_info in modified_files:
            num_changes += len(file_info.get("changes", []))
        
        # Count the number of files in different directories
        directories = set()
        for file_info in modified_files:
            file_path = file_info.get("file_path", "")
            if file_path:
                directories.add(os.path.dirname(file_path))
        
        # Determine complexity level
        complexity_level = "low"
        if len(directories) >= 3 or num_changes >= 100:
            complexity_level = "medium"
        if len(directories) >= 5 or num_changes >= 200:
            complexity_level = "high"
        
        return {
            "level": complexity_level,
            "num_changes": num_changes,
            "num_directories": len(directories),
            "directories": list(directories)
        }
    
    def _analyze_pr_impact(self, modified_files: List[Dict[str, Any]],
                          code_units: List[Dict[str, Any]],
                          relation_graph: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze the potential impact of the PR.
        
        Args:
            modified_files: List of modified files
            code_units: List of code units
            relation_graph: Relation graph
            
        Returns:
            Dict[str, Any]: Impact analysis
        """
        logger.debug("Analyzing PR impact")
        
        # Identify modified units
        modified_unit_names = set()
        for unit in code_units:
            file_path = unit.get("file_path", "")
            for file_info in modified_files:
                if file_path == file_info.get("file_path", ""):
                    modified_unit_names.add(unit.get("name", ""))
        
        # Find direct dependents
        direct_dependents = set()
        for edge in relation_graph.get("edges", []):
            if edge.get("source") in modified_unit_names:
                direct_dependents.add(edge.get("target"))
            if edge.get("target") in modified_unit_names:
                direct_dependents.add(edge.get("source"))
        
        # Use LLM to assess potential risks
        risk_assessment = self._assess_risks(modified_files, code_units, relation_graph)
        
        return {
            "modified_units": list(modified_unit_names),
            "direct_dependents": list(direct_dependents),
            "risks": risk_assessment
        }
    
    def _assess_risks(self, modified_files: List[Dict[str, Any]],
                     code_units: List[Dict[str, Any]],
                     relation_graph: Dict[str, Any]) -> Dict[str, Any]:
        """
        Assess potential risks of the PR.
        
        Args:
            modified_files: List of modified files
            code_units: List of code units
            relation_graph: Relation graph
            
        Returns:
            Dict[str, Any]: Risk assessment
        """
        # Identify patterns that might indicate risks
        risks = []
        
        # Check for changes in core files
        for file_info in modified_files:
            file_path = file_info.get("file_path", "")
            if "core" in file_path or "base" in file_path:
                risks.append({
                    "type": "core_change",
                    "severity": "medium",
                    "description": f"Changes to core functionality in {file_path}"
                })
        
        # Check for changes to public APIs
        for unit in code_units:
            if unit.get("type") in ["function", "method", "class"]:
                name = unit.get("name", "")
                if not name.startswith("_") and name.islower():  # Heuristic for public API
                    risks.append({
                        "type": "api_change",
                        "severity": "high",
                        "description": f"Changes to public API {name}"
                    })
        
        # Use LLM to assess overall risk level
        prompt = f"""
        Assess the risk level of this PR based on the following:
        
        Modified files: {[f['file_path'] for f in modified_files]}
        Identified risks: {risks}
        
        Return a risk level (low, medium, high) and a brief explanation.
        """
        
        response = self.llm_provider.generate_text(prompt)
        
        # Parse the response to extract risk level and explanation
        risk_level = "medium"  # Default
        explanation = response
        
        if "low" in response.lower():
            risk_level = "low"
        elif "high" in response.lower():
            risk_level = "high"
        
        return {
            "level": risk_level,
            "explanation": explanation,
            "identified_risks": risks
        }
    
    def _identify_key_units(self, code_units: List[Dict[str, Any]],
                           relation_graph: Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Identify key code units in the PR.
        
        Args:
            code_units: List of code units
            relation_graph: Relation graph
            
        Returns:
            List[Dict[str, Any]]: Key code units
        """
        logger.debug("Identifying key code units")
        
        # Create a mapping of unit names to units
        unit_map = {}
        for unit in code_units:
            name = unit.get("name", "")
            if name:
                unit_map[name] = unit
        
        # Count references to each unit
        reference_counts = {}
        for edge in relation_graph.get("edges", []):
            source = edge.get("source", "")
            target = edge.get("target", "")
            
            if source:
                reference_counts[source] = reference_counts.get(source, 0) + 1
            if target:
                reference_counts[target] = reference_counts.get(target, 0) + 1
        
        # Identify units with the most references
        key_unit_names = sorted(reference_counts.keys(), 
                              key=lambda name: reference_counts[name], 
                              reverse=True)[:5]  # Top 5
        
        # Get the key units
        key_units = []
        for name in key_unit_names:
            if name in unit_map:
                unit = unit_map[name]
                key_units.append({
                    "name": name,
                    "type": unit.get("type", ""),
                    "reference_count": reference_counts[name],
                    "file_path": unit.get("file_path", ""),
                    "code": unit.get("code", "")
                })
        
        return key_units
    
    def _find_related_code(self, code_units: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Find related code based on embeddings.
        
        Args:
            code_units: List of code units
            
        Returns:
            List[Dict[str, Any]]: Related code
        """
        logger.debug("Finding related code")
        
        related_code = []
        
        # Get embeddings from units
        for unit in code_units:
            embedding = unit.get("embedding")
            if embedding:
                # Search for related code using the embedding
                search_results = vectorstore_search(embedding)
                
                # Add the results, excluding the unit itself
                for result in search_results:
                    if result.get("name") != unit.get("name"):
                        related_code.append({
                            "unit_name": unit.get("name"),
                            "related_name": result.get("name"),
                            "similarity": result.get("similarity", 0),
                            "file_path": result.get("file_path", ""),
                            "type": result.get("type", "")
                        })
        
        # Sort by similarity and take top results
        related_code = sorted(related_code, key=lambda x: x.get("similarity", 0), reverse=True)[:10]
        
        return related_code 