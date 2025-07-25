import asyncio
import json
from typing import Literal, Dict, Any, List
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command
from pydantic import BaseModel, Field

from ..configuration import PRAnalysisConfiguration, MockLLMMode
from ..state import SupervisorState, PRAnalysisState
from ..mock_llm import MockLLMService
from ..github.tools import GITHUB_TOOLS


class AnalysisPlan(BaseModel):
    """Analysis plan structure."""
    workflow_description: str = Field(description="Description of the analysis workflow")
    agent_sequence: List[str] = Field(description="Sequence of agents to execute")
    parallel_agents: List[List[str]] = Field(description="Groups of agents that can run in parallel")
    estimated_duration_minutes: int = Field(description="Estimated duration in minutes")
    analysis_depth: str = Field(description="Depth of analysis to perform")


class AgentAssignment(BaseModel):
    """Agent assignment with specific tasks."""
    agent_name: str = Field(description="Name of the agent")
    tasks: List[str] = Field(description="List of specific tasks for the agent")
    priority: int = Field(description="Priority level (1-5, 5 being highest)")
    dependencies: List[str] = Field(description="List of agents this agent depends on")


class SupervisorDecision(BaseModel):
    """Supervisor decision structure."""
    decision_type: str = Field(description="Type of decision: plan, execute, coordinate, finalize")
    analysis_plan: AnalysisPlan = Field(description="Analysis plan to execute")
    agent_assignments: List[AgentAssignment] = Field(description="Detailed agent assignments")
    next_action: str = Field(description="Next action to take")


# Initialize configurable model
configurable_model = init_chat_model(
    configurable_fields=("model", "max_tokens", "api_key"),
)


SUPERVISOR_SYSTEM_PROMPT = """You are the PR Analysis Supervisor, responsible for orchestrating the analysis of GitHub Pull Requests.

Your role is to:
1. Understand the PR analysis request and determine the appropriate analysis workflow
2. Create a detailed analysis plan that coordinates multiple specialized agents
3. Assign specific tasks to each agent based on their capabilities
4. Monitor the progress and coordinate between agents
5. Ensure comprehensive coverage of all analysis aspects

Available specialized agents:
- Repository Analyzer: Understands repository structure, technologies, and architecture
- Diff Analyzer: Analyzes the specific changes made in the PR
- Context Gatherer: Collects relevant code context and dependencies
- Report Generator: Synthesizes all findings into a comprehensive report

Analysis workflow patterns:
- For QUICK analysis: Focus on high-level changes and immediate impact
- For STANDARD analysis: Comprehensive analysis of changes, context, and implications
- For DEEP analysis: Thorough examination including security, performance, and architectural impact

Current date: {date}
Analysis depth requested: {analysis_depth}
Maximum concurrent agents: {max_concurrent_agents}

You must create a structured analysis plan that efficiently utilizes available agents while ensuring thorough coverage of the PR analysis requirements."""


async def pr_supervisor(state: SupervisorState, config: RunnableConfig) -> Command[Literal["supervisor_tools"]]:
    """PR Supervisor agent for orchestrating the analysis workflow."""
    
    configurable = PRAnalysisConfiguration.from_runnable_config(config)
    
    # Check if mock LLM should be used
    mock_service = MockLLMService(configurable.mock_llm_mode, configurable.mock_response_delay_seconds)
    if mock_service.should_use_mock_for_agent("pr_supervisor"):
        # Use mock response
        mock_response = await mock_service.coordinate_analysis(
            json.dumps(state.analysis_request.model_dump())
        )
        
        return Command(
            goto="supervisor_tools",
            update={
                "supervisor_messages": [AIMessage(content=mock_response)],
                "coordination_iterations": state.coordination_iterations + 1
            }
        )
    
    # Use real LLM
    model_config = configurable.get_model_config("pr_supervisor")
    model_config.update({
        "api_key": config.get("api_key") if config else None,
        "tags": ["langsmith:nostream"]
    })
    
    supervisor_model = configurable_model.with_structured_output(SupervisorDecision).with_retry(
        stop_after_attempt=configurable.max_structured_output_retries
    ).with_config(model_config)
    
    # Prepare system prompt
    system_prompt = SUPERVISOR_SYSTEM_PROMPT.format(
        date="2024-01-15",  # TODO: Use actual date
        analysis_depth=state.analysis_request.analysis_depth,
        max_concurrent_agents=configurable.max_concurrent_agents
    )
    
    # Prepare messages
    supervisor_messages = state.supervisor_messages or []
    
    # Create analysis request summary for the supervisor
    analysis_summary = f"""
PR Analysis Request:
- Repository: {state.analysis_request.repository_url}
- PR Number: {state.analysis_request.pr_number}
- Analysis Depth: {state.analysis_request.analysis_depth}
- Include Context: {state.analysis_request.include_context}

Please create a comprehensive analysis plan for this PR that coordinates the available specialized agents effectively.
"""
    
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=analysis_summary)
    ] + supervisor_messages
    
    try:
        response = await supervisor_model.ainvoke(messages)
        
        return Command(
            goto="supervisor_tools",
            update={
                "supervisor_messages": [AIMessage(content=json.dumps(response.model_dump(), indent=2))],
                "analysis_plan": response.analysis_plan.model_dump(),
                "agent_assignments": {
                    assignment.agent_name: assignment.tasks 
                    for assignment in response.agent_assignments
                },
                "coordination_iterations": state.coordination_iterations + 1
            }
        )
        
    except Exception as e:
        error_message = f"Error in PR supervisor: {str(e)}"
        return Command(
            goto="supervisor_tools",
            update={
                "supervisor_messages": [AIMessage(content=error_message)],
                "coordination_iterations": state.coordination_iterations + 1
            }
        )


async def supervisor_tools(state: SupervisorState, config: RunnableConfig) -> Command[Literal["execute_agents", "__end__"]]:
    """Process supervisor decisions and coordinate agent execution."""
    
    configurable = PRAnalysisConfiguration.from_runnable_config(config)
    supervisor_messages = state.supervisor_messages or []
    
    if not supervisor_messages:
        return Command(goto="__end__", update={"error": "No supervisor messages to process"})
    
    last_message = supervisor_messages[-1]
    
    # Check if we've exceeded maximum coordination iterations
    if state.coordination_iterations >= 3:
        return Command(
            goto="execute_agents",
            update={
                "analysis_plan": state.analysis_plan or {
                    "workflow_description": "Standard PR analysis workflow",
                    "agent_sequence": ["repository_analyzer", "diff_analyzer", "context_gatherer", "report_generator"],
                    "parallel_agents": [["repository_analyzer", "diff_analyzer"], ["context_gatherer"], ["report_generator"]],
                    "estimated_duration_minutes": 10,
                    "analysis_depth": state.analysis_request.analysis_depth
                }
            }
        )
    
    try:
        # Parse the supervisor's response
        if hasattr(last_message, 'content') and last_message.content:
            try:
                supervisor_decision = json.loads(last_message.content)
            except json.JSONDecodeError:
                # If not JSON, treat as analysis plan description
                supervisor_decision = {
                    "decision_type": "execute",
                    "next_action": "execute_agents"
                }
            
            # If we have a valid analysis plan, proceed to agent execution
            if state.analysis_plan or "analysis_plan" in supervisor_decision:
                return Command(
                    goto="execute_agents",
                    update={}
                )
            else:
                # Need more coordination
                return Command(
                    goto="pr_supervisor",
                    update={
                        "supervisor_messages": [HumanMessage(
                            content="Please provide a more detailed analysis plan with specific agent assignments."
                        )]
                    }
                )
        
        return Command(goto="execute_agents", update={})
        
    except Exception as e:
        return Command(
            goto="__end__",
            update={"error": f"Error processing supervisor tools: {str(e)}"}
        )


def should_continue_coordination(state: SupervisorState) -> str:
    """Determine if coordination should continue."""
    
    if state.coordination_iterations >= 3:
        return "supervisor_tools"
    
    if state.analysis_plan:
        return "supervisor_tools"
    
    supervisor_messages = state.supervisor_messages or []
    if not supervisor_messages:
        return "pr_supervisor"
    
    last_message = supervisor_messages[-1]
    
    # Check if the last message indicates completion
    if hasattr(last_message, 'content') and "execute_agents" in str(last_message.content).lower():
        return "supervisor_tools"
    
    return "pr_supervisor"