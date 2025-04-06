"""
Base Agent class for all PR context extraction agents.
"""

import logging
from typing import Any, Dict, List, Optional
from langchain.agents import AgentExecutor
from langchain.agents.react.base import create_react_agent
from langchain.schema import BasePromptTemplate
from langchain.tools.base import BaseTool

# Setup logger
logger = logging.getLogger("base_agent")

class BaseAgent:
    """Base class for all agents in the PR context extraction system."""
    
    def __init__(self, llm_provider, tools: List[BaseTool], agent_name: str = "BaseAgent"):
        """
        Initialize the agent with an LLM provider and tools.
        
        Args:
            llm_provider: The LLM provider to use for this agent
            tools: List of tools this agent can use
            agent_name: Name of the agent for logging purposes
        """
        self.llm_provider = llm_provider
        self.tools = tools
        self.agent_name = agent_name
        self.agent_executor = None
        self.prompt_template = None
        
        logger.debug(f"Initialized {self.agent_name}")
    
    def setup(self, prompt_template: Optional[BasePromptTemplate] = None) -> None:
        """
        Set up the agent with a prompt template and create the agent executor.
        
        Args:
            prompt_template: Optional prompt template to use for this agent
        """
        if prompt_template:
            self.prompt_template = prompt_template
        
        if not self.prompt_template:
            raise ValueError(f"{self.agent_name} requires a prompt template")
        
        # Create a langchain LLM wrapper from our provider
        # This method should be implemented by concrete agents based on their specific needs
        llm = self._get_langchain_llm()
        
        # Create the agent using the React framework
        agent = create_react_agent(llm, self.tools, self.prompt_template)
        
        # Create the agent executor
        self.agent_executor = AgentExecutor(
            agent=agent,
            tools=self.tools,
            verbose=True,
            max_iterations=10,
            handle_parsing_errors=True
        )
        
        logger.debug(f"Set up {self.agent_name} with {len(self.tools)} tools")
    
    def _get_langchain_llm(self):
        """
        Get a LangChain LLM wrapper for the provider.
        This method must be implemented by concrete agent classes.
        
        Returns:
            A LangChain LLM wrapper
        """
        raise NotImplementedError("Subclasses must implement _get_langchain_llm()")
    
    def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run the agent on the given input data.
        
        Args:
            input_data: Input data for the agent
            
        Returns:
            Dict: The agent's output
            
        Raises:
            RuntimeError: If the agent is not set up or if there's an error running the agent
        """
        if not self.agent_executor:
            raise RuntimeError(f"{self.agent_name} is not set up. Call setup() first.")
        
        try:
            logger.debug(f"Running {self.agent_name} with input: {input_data}")
            result = self.agent_executor.invoke(input_data)
            logger.debug(f"{self.agent_name} completed successfully")
            return result
        except Exception as e:
            logger.error(f"Error running {self.agent_name}: {str(e)}")
            raise RuntimeError(f"Error running {self.agent_name}: {str(e)}") 