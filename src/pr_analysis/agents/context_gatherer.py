import json
from typing import Literal, List
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command
from pydantic import BaseModel, Field

from ..configuration import PRAnalysisConfiguration
from ..state import ContextGathererState, ContextAnalysis, CodeContext
from ..mock_llm import MockLLMService
from ..github.tools import get_pr_context_files, fetch_file_content


class ContextGatheringResult(BaseModel):
    """Context gathering result structure."""
    relevant_files: List[dict] = Field(description="Relevant code files with metadata")
    dependencies: List[str] = Field(description="Dependencies that might be affected")
    related_features: List[str] = Field(description="Related features or components")
    test_coverage: dict = Field(description="Test coverage information")
    configuration_impact: List[str] = Field(description="Configuration changes or impacts")
    documentation_updates: List[str] = Field(description="Documentation that may need updates")


# Initialize configurable model
configurable_model = init_chat_model(
    configurable_fields=("model", "max_tokens", "api_key"),
)


CONTEXT_GATHERER_SYSTEM_PROMPT = """You are the Context Gatherer, a specialized agent focused on collecting relevant code context and understanding dependencies for GitHub Pull Request analysis.

Your responsibilities:
1. Identify and gather relevant code files that provide context for the PR changes
2. Understand dependencies and interconnections between components
3. Identify related features and functionality that might be affected
4. Assess test coverage and identify testing gaps
5. Identify configuration files and settings that might be impacted
6. Find documentation that may need updates

When gathering context, consider:
- Files in the same directories as changed files
- Import/export relationships and dependencies
- Configuration files that might affect the changed components
- Test files related to the changed functionality
- Documentation files that describe affected features
- Database schemas or migration files if data-related changes
- API specifications if API changes are involved

Context relevance scoring (0-1):
- 1.0: Directly imports/exports changed code
- 0.8: In same module/package as changes
- 0.6: Related functionality or shared dependencies
- 0.4: Same technology stack or layer
- 0.2: General configuration or documentation

Provide comprehensive context that helps reviewers understand:
- How the changes fit into the broader codebase
- What other components might be affected
- What testing and validation should be performed
- What documentation needs to be updated

Current date: {date}
Maximum context files to analyze: {max_context_files}
"""


async def context_gatherer(state: ContextGathererState, config: RunnableConfig) -> Command[Literal["context_gatherer_tools"]]:
    """Context Gatherer agent."""
    
    configurable = PRAnalysisConfiguration.from_runnable_config(config)
    
    # Check if mock LLM should be used
    mock_service = MockLLMService(configurable.mock_llm_mode, configurable.mock_response_delay_seconds)
    if mock_service.should_use_mock_for_agent("context_gatherer"):
        
        changed_files = []
        if state.diff_analysis and state.diff_analysis.pr_diff:
            changed_files = [f.filename for f in state.diff_analysis.pr_diff.files]
        
        mock_response = await mock_service.gather_context(
            state.repository_url, 
            state.pr_number,
            changed_files
        )
        
        return Command(
            goto="context_gatherer_tools",
            update={
                "gatherer_messages": [AIMessage(content=mock_response)]
            }
        )
    
    # Use real LLM
    model_config = configurable.get_model_config("context_gatherer")
    model_config.update({
        "api_key": config.get("api_key") if config else None,
        "tags": ["langsmith:nostream"]
    })
    
    gatherer_model = configurable_model.with_structured_output(ContextGatheringResult).with_retry(
        stop_after_attempt=configurable.max_structured_output_retries
    ).with_config(model_config)
    
    # Prepare system prompt
    system_prompt = CONTEXT_GATHERER_SYSTEM_PROMPT.format(
        date="2024-01-15",  # TODO: Use actual date
        max_context_files=configurable.max_context_files
    )
    
    # Prepare context gathering request
    context_request = f"""
Please gather relevant context for analyzing this Pull Request.

Repository: {state.repository_url}
PR Number: {state.pr_number}
"""
    
    # Add diff analysis information if available
    if state.diff_analysis:
        context_request += f"""

Diff Analysis Summary:
- Changes Summary: {state.diff_analysis.summary}
- Affected Components: {', '.join(state.diff_analysis.affected_components)}
- Change Types: {', '.join(state.diff_analysis.change_types)}
- Risk Level: {state.diff_analysis.risk_level}
- Complexity Score: {state.diff_analysis.complexity_score}/10

Changed Files:
"""
        for i, file in enumerate(state.diff_analysis.pr_diff.files[:15]):  # Limit display
            context_request += f"- {file.filename} ({file.status}: +{file.additions}/-{file.deletions})\n"
        
        if len(state.diff_analysis.pr_diff.files) > 15:
            context_request += f"... and {len(state.diff_analysis.pr_diff.files) - 15} more files\n"
    
    context_request += """

Please identify and prioritize relevant context files that would help understand:
1. Dependencies and imports related to the changed code
2. Configuration files that might affect the changes
3. Test files that should be reviewed or updated
4. Documentation that describes the affected functionality
5. Related components that might be impacted by the changes

Focus on files that provide meaningful context for code review and impact assessment.
"""
    
    gatherer_messages = state.gatherer_messages or []
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=context_request)
    ] + gatherer_messages
    
    try:
        response = await gatherer_model.ainvoke(messages)
        
        return Command(
            goto="context_gatherer_tools",
            update={
                "gatherer_messages": [AIMessage(content=json.dumps(response.model_dump(), indent=2))]
            }
        )
        
    except Exception as e:
        error_message = f"Error in context gatherer: {str(e)}"
        return Command(
            goto="context_gatherer_tools",
            update={
                "gatherer_messages": [AIMessage(content=error_message)]
            }
        )


async def context_gatherer_tools(state: ContextGathererState, config: RunnableConfig):
    """Process context gatherer results and fetch actual context files."""
    
    configurable = PRAnalysisConfiguration.from_runnable_config(config)
    gatherer_messages = state.gatherer_messages or []
    
    # First, try to get context files using the GitHub API
    try:
        context_files_json = await get_pr_context_files(
            state.repository_url,
            state.pr_number,
            configurable.max_context_files
        )
        context_files_data = json.loads(context_files_json)
        
        # Convert to CodeContext objects
        relevant_files = []
        for file_path, file_info in context_files_data.get("context_files", {}).items():
            relevant_files.append(CodeContext(
                file_path=file_path,
                content=file_info["content"],
                relevance_score=0.8 if file_info["type"] == "configuration" else 0.6,
                context_type=file_info["type"]
            ))
        
        # Process LLM analysis if available
        if gatherer_messages:
            last_message = gatherer_messages[-1] 
            
            try:
                if hasattr(last_message, 'content') and last_message.content and not last_message.content.startswith("Error"):
                    try:
                        analysis_data = json.loads(last_message.content)
                        
                        # Create context analysis with both API data and LLM insights
                        context_result = ContextAnalysis(
                            relevant_files=relevant_files,
                            dependencies=analysis_data.get("dependencies", []),
                            related_features=analysis_data.get("related_features", []),
                            test_coverage=analysis_data.get("test_coverage", {"overall": "unknown"})
                        )
                        
                    except json.JSONDecodeError:
                        # Fallback with just API data
                        context_result = ContextAnalysis(
                            relevant_files=relevant_files,
                            dependencies=[],
                            related_features=[],
                            test_coverage={"overall": "unknown"}
                        )
                else:
                    # Error case - use minimal context
                    context_result = ContextAnalysis(
                        relevant_files=relevant_files,
                        dependencies=[],
                        related_features=[],
                        test_coverage={"overall": "unknown"}
                    )
                    
            except Exception as e:
                # Fallback context with API data only
                context_result = ContextAnalysis(
                    relevant_files=relevant_files,
                    dependencies=[],
                    related_features=[],
                    test_coverage={"overall": f"error: {str(e)}"}
                )
        else:
            # No LLM analysis - use API data only
            context_result = ContextAnalysis(
                relevant_files=relevant_files,
                dependencies=[],
                related_features=[],
                test_coverage={"overall": "api_only"}
            )
        
        return {
            "context_result": context_result
        }
        
    except Exception as e:
        # Complete fallback - create minimal context
        error_message = f"Error gathering context: {str(e)}"
        
        context_result = ContextAnalysis(
            relevant_files=[],
            dependencies=[],
            related_features=[],
            test_coverage={"overall": "unavailable", "error": error_message}
        )
        
        return {
            "context_result": context_result,
            "gatherer_messages": gatherer_messages + [AIMessage(content=error_message)]
        }


def should_continue_context_gathering(state: ContextGathererState) -> str:
    """Determine if context gathering should continue."""
    
    # If we have the final context result, we're done
    if state.context_result:
        return "__end__"
    
    # If we have gatherer messages but no result, process the tools
    gatherer_messages = state.gatherer_messages or []
    if gatherer_messages:
        return "context_gatherer_tools"
    
    # Start context gathering
    return "context_gatherer"