"""
Coordinator Agent for PR context extraction.
This agent manages the overall context extraction process.
"""

import logging
import json
from typing import Any, Dict, List
from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI

from .base_agent import BaseAgent

# Setup logger
logger = logging.getLogger("coordinator_agent")

# Define the coordinator agent prompt template
COORDINATOR_PROMPT = """
You are the Coordinator Agent responsible for managing the PR context extraction process.
Your goal is to analyze a PR diff, plan tasks for specialized agents, and coordinate their work.

The PR diff is provided as context for your analysis.

For this task, you need to:
1. Analyze the PR diff to understand the changes
2. Plan tasks for specialized agents
3. Delegate tasks to appropriate agents
4. Collect and validate their outputs
5. Produce a final context representation

Think step by step about what needs to be done and which agents should handle each task.

Question: {question}

{format_instructions}
"""

class CoordinatorAgent(BaseAgent):
    """
    Coordinator Agent that manages the PR context extraction process.
    This agent analyzes the PR diff, plans tasks, and coordinates other agents.
    """
    
    def __init__(self, llm_provider, tools, repo_path, pr_diff):
        """
        Initialize the coordinator agent.
        
        Args:
            llm_provider: LLM provider to use
            tools: List of tools this agent can use
            repo_path: Path to the repository
            pr_diff: PR diff content
        """
        super().__init__(llm_provider, tools, "CoordinatorAgent")
        self.repo_path = repo_path
        self.pr_diff = pr_diff
        
        # Create prompt template
        self.prompt_template = PromptTemplate(
            template=COORDINATOR_PROMPT,
            input_variables=["question"],
            partial_variables={"format_instructions": ""}
        )
    
    def _get_langchain_llm(self):
        """Get a LangChain LLM wrapper for the provider."""
        # Convert the PRhythm provider to a LangChain LLM
        # For example, for OpenAI provider:
        return ChatOpenAI(
            model=self.llm_provider.model,
            temperature=self.llm_provider.temperature,
            api_key=self.llm_provider.api_key,
            base_url=self.llm_provider.base_url
        )
    
    def plan_tasks(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Plan tasks for specialized agents based on the PR diff.
        
        Returns:
            Dict[str, List[Dict[str, Any]]]: Dictionary of tasks for each agent
        """
        logger.debug("Planning tasks based on PR diff")
        
        # Use the agent to analyze the PR diff and plan tasks
        question = f"Analyze this PR diff and plan tasks for specialized agents:\n{self.pr_diff[:2000]}..."
        if len(self.pr_diff) > 2000:
            question += f"\n[Diff truncated, total length: {len(self.pr_diff)} characters]"
        
        result = self.run({"question": question})
        
        # Extract tasks from the result
        tasks = {
            "code_analysis_tasks": [],
            "relationship_extraction_tasks": [],
            "context_extraction_tasks": []
        }
        
        # Try to parse the result and extract tasks
        try:
            # This will depend on the specific output format of your agent
            # For now, we'll assume the agent returns a structured JSON string or a dict
            if isinstance(result.get("output"), str):
                # Try to parse as JSON
                try:
                    parsed_result = json.loads(result["output"])
                    if "tasks" in parsed_result:
                        tasks = parsed_result["tasks"]
                except json.JSONDecodeError:
                    # If not JSON, try to parse the text (simplified approach)
                    if "code_analysis" in result["output"]:
                        tasks["code_analysis_tasks"].append({"description": "Analyze code structure"})
                    if "relationship" in result["output"]:
                        tasks["relationship_extraction_tasks"].append({"description": "Extract relationships"})
                    if "context" in result["output"]:
                        tasks["context_extraction_tasks"].append({"description": "Extract context"})
            elif isinstance(result.get("output"), dict):
                if "tasks" in result["output"]:
                    tasks = result["output"]["tasks"]
        except Exception as e:
            logger.error(f"Error parsing agent result: {str(e)}")
            # Fall back to default tasks
        
        # Ensure we have at least default tasks if parsing failed
        if not any(tasks.values()):
            logger.warning("Could not parse specific tasks, using default tasks")
            tasks = {
                "code_analysis_tasks": [{"description": "Analyze all changed code structures"}],
                "relationship_extraction_tasks": [{"description": "Extract relationships for all changed entities"}],
                "context_extraction_tasks": [{"description": "Extract context for all changes"}]
            }
        
        logger.debug(f"Planned tasks: {tasks}")
        return tasks
    
    def delegate_task(self, agent_name: str, task_description: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Delegate a task to a specialized agent.
        
        Args:
            agent_name: Name of the agent to delegate to
            task_description: Description of the task
            context: Additional context for the task
            
        Returns:
            Dict[str, Any]: Result from the agent
            
        Raises:
            ValueError: If the agent is not recognized
        """
        logger.debug(f"Delegating task to {agent_name}: {task_description}")
        
        # The actual delegation would need access to other agents
        # For now, this is a placeholder - in a real implementation, 
        # this would interact with AgentFactory to get the appropriate agent
        
        # Create context for the delegation
        delegation_context = {
            "task": task_description,
            "pr_diff": self.pr_diff,
            "repo_path": self.repo_path,
            **context
        }
        
        # Return placeholder result
        delegation_result = {
            "status": "delegated",
            "agent": agent_name,
            "task": task_description,
            "context": delegation_context
        }
        
        logger.debug(f"Delegated task to {agent_name}")
        return delegation_result
    
    def collect_and_validate_outputs(self, outputs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Collect and validate outputs from specialized agents.
        
        Args:
            outputs: List of outputs from specialized agents
            
        Returns:
            Dict[str, Any]: Validated and integrated outputs
        """
        logger.debug(f"Collecting and validating {len(outputs)} outputs")
        
        # Simple validation: check if all outputs have required fields
        validated_outputs = []
        for output in outputs:
            if "status" in output and output["status"] == "completed":
                validated_outputs.append(output)
            else:
                logger.warning(f"Invalid output: {output}")
        
        # Return collection of validated outputs
        return {
            "validated_outputs": validated_outputs,
            "total_outputs": len(outputs),
            "valid_outputs": len(validated_outputs)
        }
    
    def extract_context(self) -> Dict[str, Any]:
        """
        Run the full context extraction process.
        
        Returns:
            Dict[str, Any]: Extracted context
        """
        logger.debug("Starting context extraction process")
        
        # 1. Plan tasks
        tasks = self.plan_tasks()
        
        # 2-4. For full implementation, this would:
        #    - Create specialized agents
        #    - Delegate tasks to them
        #    - Collect and validate their outputs
        #    - Synthesize a final context representation
        
        # For now, return the planned tasks as a placeholder
        return {
            "status": "planning_completed",
            "planned_tasks": tasks,
            "message": "Full context extraction requires integration with other agents"
        } 