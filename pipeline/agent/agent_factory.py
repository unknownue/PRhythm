"""
Agent factory for creating different agent instances.
"""

import logging
from typing import Dict, Any, List, Optional

from .base_agent import BaseAgent
from .coordinator_agent import CoordinatorAgent
from .code_analyzer_agent import CodeAnalyzerAgent
from .relationship_extractor_agent import RelationshipExtractorAgent
from .context_extraction_agent import ContextExtractionAgent
from .context_synthesizer_agent import ContextSynthesizerAgent

from .tools.code_tools import get_code_tools
from .tools.git_tools import get_git_tools
from .tools.repo_tools import get_repo_tools
from .tools.vector_tools import get_vector_tools

# Setup logger
logger = logging.getLogger("agent_factory")

class AgentFactory:
    """Agent factory for creating various agent instances based on needs."""
    
    @staticmethod
    def create_coordinator_agent(llm_provider, repo_path: str, pr_diff: str) -> CoordinatorAgent:
        """
        Create a coordinator agent.
        
        Args:
            llm_provider: The LLM provider to use
            repo_path: Path to the repository
            pr_diff: PR diff content
            
        Returns:
            CoordinatorAgent: The coordinator agent
        """
        logger.debug("Creating coordinator agent")
        
        # Get tools for the coordinator
        tools = []
        tools.extend(get_git_tools(repo_path))
        tools.extend(get_code_tools(repo_path))
        
        # Create and setup coordinator agent
        agent = CoordinatorAgent(llm_provider, tools, repo_path, pr_diff)
        agent.setup()
        
        return agent
    
    @staticmethod
    def create_code_analyzer_agent(llm_provider, repo_path: str) -> CodeAnalyzerAgent:
        """
        Create a code analyzer agent.
        
        Args:
            llm_provider: The LLM provider to use
            repo_path: Path to the repository
            
        Returns:
            CodeAnalyzerAgent: The code analyzer agent
        """
        logger.debug("Creating code analyzer agent")
        
        # Get tools for the code analyzer
        tools = []
        tools.extend(get_code_tools(repo_path))
        
        # Create and setup code analyzer agent
        agent = CodeAnalyzerAgent(llm_provider, tools, repo_path)
        agent.setup()
        
        return agent
    
    @staticmethod
    def create_relationship_extractor_agent(llm_provider, repo_path: str) -> RelationshipExtractorAgent:
        """
        Create a relationship extractor agent.
        
        Args:
            llm_provider: The LLM provider to use
            repo_path: Path to the repository
            
        Returns:
            RelationshipExtractorAgent: The relationship extractor agent
        """
        logger.debug("Creating relationship extractor agent")
        
        # Get tools for the relationship extractor
        tools = []
        tools.extend(get_code_tools(repo_path))
        tools.extend(get_repo_tools(repo_path))
        
        # Create and setup relationship extractor agent
        agent = RelationshipExtractorAgent(llm_provider, tools, repo_path)
        agent.setup()
        
        return agent
    
    @staticmethod
    def create_context_extraction_agent(llm_provider, repo_path: str) -> ContextExtractionAgent:
        """
        Create a context extraction agent.
        
        Args:
            llm_provider: The LLM provider to use
            repo_path: Path to the repository
            
        Returns:
            ContextExtractionAgent: The context extraction agent
        """
        logger.debug("Creating context extraction agent")
        
        # Get tools for the context extraction
        tools = []
        tools.extend(get_code_tools(repo_path))
        tools.extend(get_repo_tools(repo_path))
        tools.extend(get_vector_tools())
        
        # Create and setup context extraction agent
        agent = ContextExtractionAgent(llm_provider, tools, repo_path)
        agent.setup()
        
        return agent
    
    @staticmethod
    def create_context_synthesizer_agent(llm_provider) -> ContextSynthesizerAgent:
        """
        Create a context synthesizer agent.
        
        Args:
            llm_provider: The LLM provider to use
            
        Returns:
            ContextSynthesizerAgent: The context synthesizer agent
        """
        logger.debug("Creating context synthesizer agent")
        
        # Create and setup context synthesizer agent (no external tools needed)
        agent = ContextSynthesizerAgent(llm_provider, [])
        agent.setup()
        
        return agent
    
    @staticmethod
    def create_all_agents(llm_provider, repo_path: str, pr_diff: str) -> Dict[str, BaseAgent]:
        """
        Create all necessary agents for PR context extraction.
        
        Args:
            llm_provider: The LLM provider to use
            repo_path: Path to the repository
            pr_diff: PR diff content
            
        Returns:
            Dict[str, BaseAgent]: Dictionary of all created agents
        """
        logger.debug("Creating all agents")
        
        agents = {
            "coordinator": AgentFactory.create_coordinator_agent(llm_provider, repo_path, pr_diff),
            "code_analyzer": AgentFactory.create_code_analyzer_agent(llm_provider, repo_path),
            "relationship_extractor": AgentFactory.create_relationship_extractor_agent(llm_provider, repo_path),
            "context_extraction": AgentFactory.create_context_extraction_agent(llm_provider, repo_path),
            "context_synthesizer": AgentFactory.create_context_synthesizer_agent(llm_provider)
        }
        
        logger.debug(f"Created {len(agents)} agents")
        return agents 