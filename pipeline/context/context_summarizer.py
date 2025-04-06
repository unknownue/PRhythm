"""
Context summarizer module for PR context extraction.
This module generates summaries from extracted PR context.
"""

import logging
from typing import Any, Dict, List, Optional, Union

from pipeline.agent.llm_providers.base_provider import LLMProvider

# Setup logger
logger = logging.getLogger("context_summarizer")

class ContextSummarizer:
    """
    Generates summaries from PR context.
    """
    
    def __init__(self, llm_provider: Optional[LLMProvider] = None):
        """
        Initialize the context summarizer.
        
        Args:
            llm_provider: LLM provider to use
        """
        self.llm_provider = llm_provider
        logger.debug("Initialized ContextSummarizer")
    
    def set_llm_provider(self, llm_provider: LLMProvider):
        """
        Set the LLM provider.
        
        Args:
            llm_provider: LLM provider to use
        """
        self.llm_provider = llm_provider
        logger.debug("Set LLM provider")
    
    def generate_summary(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a summary from context.
        
        Args:
            context: PR context
            
        Returns:
            Dict[str, Any]: Summary
        """
        logger.debug("Generating summary from context")
        
        if not self.llm_provider:
            raise ValueError("LLM provider is required for summary generation")
        
        # Extract key information from context
        modified_files = context.get("modified_files", [])
        code_units = context.get("code_units", [])
        relation_graph = context.get("relation_graph", {})
        pr_analysis = context.get("pr_analysis", {})
        
        # Generate different summary components
        summary = {
            "overview": self._generate_overview(pr_analysis),
            "key_changes": self._generate_key_changes_summary(modified_files, code_units, pr_analysis),
            "technical_details": self._generate_technical_details(code_units, relation_graph, pr_analysis),
            "impact_assessment": self._generate_impact_assessment(pr_analysis)
        }
        
        # Generate a concise overall summary
        summary["concise_summary"] = self._generate_concise_summary(summary)
        
        logger.debug("Summary generation completed")
        return summary
    
    def _generate_overview(self, pr_analysis: Dict[str, Any]) -> str:
        """
        Generate an overview summary.
        
        Args:
            pr_analysis: PR analysis
            
        Returns:
            str: Overview summary
        """
        logger.debug("Generating overview summary")
        
        purpose = pr_analysis.get("purpose", {})
        scope = pr_analysis.get("scope", {})
        
        purpose_description = purpose.get("description", "No description available")
        categories = purpose.get("categories", [])
        scope_size = scope.get("scope_size", "unknown")
        complexity = scope.get("complexity", {}).get("level", "unknown")
        
        # Create a prompt for the LLM
        prompt = f"""
        Generate a concise overview of this pull request based on the following information:
        
        Purpose: {purpose_description}
        Categories: {', '.join(categories) if categories else 'None'}
        Scope size: {scope_size}
        Complexity: {complexity}
        
        Your overview should be 2-3 sentences that summarize what this PR does, why it matters, 
        and its general scope/complexity. Use a professional, technical tone.
        """
        
        overview = self.llm_provider.generate_text(prompt)
        return overview
    
    def _generate_key_changes_summary(self, modified_files: List[Dict[str, Any]],
                                     code_units: List[Dict[str, Any]],
                                     pr_analysis: Dict[str, Any]) -> str:
        """
        Generate a summary of key changes.
        
        Args:
            modified_files: Modified files
            code_units: Code units
            pr_analysis: PR analysis
            
        Returns:
            str: Key changes summary
        """
        logger.debug("Generating key changes summary")
        
        # Get key units from PR analysis
        key_units = pr_analysis.get("key_units", [])
        
        # Get file status counts
        scope = pr_analysis.get("scope", {})
        status_counts = scope.get("status_counts", {})
        
        # Prepare information for the prompt
        file_summary = []
        for status, count in status_counts.items():
            if count > 0:
                file_summary.append(f"{count} {status}")
        
        modified_file_paths = [f['file_path'] for f in modified_files]
        
        # Create a prompt for the LLM
        prompt = f"""
        Summarize the key changes in this pull request based on the following information:
        
        Files: {', '.join(file_summary) if file_summary else 'None'}
        Modified file paths: {modified_file_paths}
        
        Key code units:
        {[{'name': unit.get('name'), 'type': unit.get('type')} for unit in key_units]}
        
        Your summary should be a bulleted list of the most important changes, focusing on what was added, 
        modified, or removed. Prioritize mention of key components, APIs, and significant functionality changes.
        Limit to 5-7 bullet points maximum.
        """
        
        key_changes = self.llm_provider.generate_text(prompt)
        return key_changes
    
    def _generate_technical_details(self, code_units: List[Dict[str, Any]],
                                   relation_graph: Dict[str, Any],
                                   pr_analysis: Dict[str, Any]) -> str:
        """
        Generate technical details summary.
        
        Args:
            code_units: Code units
            relation_graph: Relation graph
            pr_analysis: PR analysis
            
        Returns:
            str: Technical details summary
        """
        logger.debug("Generating technical details summary")
        
        # Get related code from PR analysis
        related_code = pr_analysis.get("related_code", [])
        
        # Count relationship types
        relation_type_counts = {}
        for edge in relation_graph.get("edges", []):
            rel_type = edge.get("type", "unknown")
            relation_type_counts[rel_type] = relation_type_counts.get(rel_type, 0) + 1
        
        # Select a subset of code units to avoid overwhelming the LLM
        selected_code_units = []
        for unit in code_units[:10]:  # Limit to 10 units
            selected_code_units.append({
                "name": unit.get("name", ""),
                "type": unit.get("type", ""),
                "file_path": unit.get("file_path", "")
            })
        
        # Create a prompt for the LLM
        prompt = f"""
        Provide technical details about this PR based on the following information:
        
        Code units: {selected_code_units}
        
        Relationships between code:
        {relation_type_counts}
        
        Related code:
        {[{'unit_name': rel.get('unit_name'), 'related_name': rel.get('related_name')} for rel in related_code[:5]]}
        
        Your technical summary should explain:
        1. The main components or modules being modified
        2. Key code relationships (inheritance, calls, etc.)
        3. The technical approach being used
        4. Any design patterns or architectural changes
        
        Keep it concise and professional, focusing on information that would help a developer understand 
        the technical aspects of the PR.
        """
        
        technical_details = self.llm_provider.generate_text(prompt)
        return technical_details
    
    def _generate_impact_assessment(self, pr_analysis: Dict[str, Any]) -> str:
        """
        Generate an impact assessment.
        
        Args:
            pr_analysis: PR analysis
            
        Returns:
            str: Impact assessment
        """
        logger.debug("Generating impact assessment")
        
        # Get impact info from PR analysis
        impact = pr_analysis.get("impact", {})
        modified_units = impact.get("modified_units", [])
        direct_dependents = impact.get("direct_dependents", [])
        risks = impact.get("risks", {})
        
        risk_level = risks.get("level", "unknown")
        risk_explanation = risks.get("explanation", "No description available")
        identified_risks = risks.get("identified_risks", [])
        
        # Create a prompt for the LLM
        prompt = f"""
        Assess the impact and risks of this PR based on the following information:
        
        Modified units: {modified_units}
        Direct dependents: {direct_dependents}
        Risk level: {risk_level}
        Risk explanation: {risk_explanation}
        
        Identified risks:
        {[{'type': risk.get('type'), 'severity': risk.get('severity'), 'description': risk.get('description')} for risk in identified_risks]}
        
        Your impact assessment should include:
        1. What parts of the codebase might be affected by these changes
        2. Potential risks or side effects
        3. Areas that should be carefully tested
        4. Any backward compatibility concerns
        
        Be specific and actionable in your assessment.
        """
        
        impact_assessment = self.llm_provider.generate_text(prompt)
        return impact_assessment
    
    def _generate_concise_summary(self, summary: Dict[str, str]) -> str:
        """
        Generate a concise overall summary.
        
        Args:
            summary: Summary components
            
        Returns:
            str: Concise summary
        """
        logger.debug("Generating concise overall summary")
        
        # Create a prompt for the LLM
        prompt = f"""
        Based on the detailed summaries below, create a very concise (3-5 sentences) executive summary 
        of this pull request. Focus on the most important information a reviewer or stakeholder would need to know.
        
        Overview:
        {summary.get("overview", "")}
        
        Key Changes:
        {summary.get("key_changes", "")}
        
        Technical Details:
        {summary.get("technical_details", "")}
        
        Impact Assessment:
        {summary.get("impact_assessment", "")}
        
        Your concise summary should be accessible to both technical and non-technical audiences.
        """
        
        concise_summary = self.llm_provider.generate_text(prompt)
        return concise_summary 