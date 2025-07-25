import json
from typing import Literal
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command
from pydantic import BaseModel, Field

from ..configuration import PRAnalysisConfiguration
from ..state import RepositoryAnalyzerState, RepositoryAnalysis
from ..mock_llm import MockLLMService
from ..github.tools import fetch_repository_info


class RepositoryAnalysisResult(BaseModel):
    """Repository analysis result structure."""
    summary: str = Field(description="High-level summary of the repository")
    technologies: list[str] = Field(description="List of technologies and frameworks used")
    architecture_patterns: list[str] = Field(description="Identified architectural patterns")
    key_components: list[str] = Field(description="Key components and modules")
    complexity_score: int = Field(description="Repository complexity score (1-10)")
    main_features: list[str] = Field(description="Main features or capabilities")
    development_practices: list[str] = Field(description="Development practices observed")


# Initialize configurable model
configurable_model = init_chat_model(
    configurable_fields=("model", "max_tokens", "api_key"),
)


REPOSITORY_ANALYZER_SYSTEM_PROMPT = """You are the Repository Analyzer, a specialized agent focused on understanding GitHub repository structure, architecture, and technologies.

Your responsibilities:
1. Analyze the repository structure and organization
2. Identify technologies, frameworks, and tools used
3. Understand the architectural patterns and design principles
4. Assess the complexity and scale of the codebase
5. Identify key components and their relationships
6. Evaluate development practices and code quality

When analyzing a repository, consider:
- Programming languages and their usage distribution
- Framework and library dependencies
- Directory structure and organization patterns
- Configuration files and their implications
- Documentation quality and coverage
- Testing approaches and coverage
- Build and deployment configurations
- Code organization and modularization

Provide a comprehensive analysis that helps understand:
- What the repository does (purpose and functionality)
- How it's built (architecture and technologies)
- How complex it is (scale and maintainability)
- What are the key areas of functionality

Current date: {date}
Analysis should be thorough but focused on aspects relevant to PR analysis and code review.
"""


async def repository_analyzer(state: RepositoryAnalyzerState, config: RunnableConfig) -> Command[Literal["repository_analyzer_tools"]]:
    """Repository Analyzer agent."""
    
    configurable = PRAnalysisConfiguration.from_runnable_config(config)
    
    # Check if mock LLM should be used
    mock_service = MockLLMService(configurable.mock_llm_mode, configurable.mock_response_delay_seconds)
    if mock_service.should_use_mock_for_agent("repository_analyzer"):
        # Get repository context first
        repo_context = ""
        if state.repository_context:
            repo_context = json.dumps(state.repository_context.model_dump(), indent=2)
        
        mock_response = await mock_service.analyze_repository(
            state.repository_url, 
            repo_context
        )
        
        return Command(
            goto="repository_analyzer_tools",
            update={
                "analyzer_messages": [AIMessage(content=mock_response)]
            }
        )
    
    # Use real LLM
    model_config = configurable.get_model_config("repository_analyzer")
    model_config.update({
        "api_key": config.get("api_key") if config else None,
        "tags": ["langsmith:nostream"]
    })
    
    analyzer_model = configurable_model.with_structured_output(RepositoryAnalysisResult).with_retry(
        stop_after_attempt=configurable.max_structured_output_retries
    ).with_config(model_config)
    
    # Prepare system prompt
    system_prompt = REPOSITORY_ANALYZER_SYSTEM_PROMPT.format(
        date="2024-01-15"  # TODO: Use actual date
    )
    
    # Prepare repository context
    repo_context_str = "Repository context not available"
    if state.repository_context:
        repo_context_str = f"""
Repository Information:
- Name: {state.repository_context.repository.name}
- Full Name: {state.repository_context.repository.full_name}
- Description: {state.repository_context.repository.description or 'No description'}
- Primary Language: {state.repository_context.main_language or 'Not specified'}
- Size: {state.repository_context.repository.size} KB
- Created: {state.repository_context.repository.created_at}
- Last Updated: {state.repository_context.repository.updated_at}

Languages Used:
{json.dumps(state.repository_context.languages, indent=2) if state.repository_context.languages else 'No language data'}

Technologies Detected:
{', '.join(state.repository_context.technologies) if state.repository_context.technologies else 'None detected'}

Key Configuration Files:
{', '.join(state.repository_context.key_files) if state.repository_context.key_files else 'None found'}

README Content (first 1000 chars):
{(state.repository_context.readme_content or 'No README found')[:1000]}
"""
    
    analysis_request = f"""
Please analyze this GitHub repository and provide a comprehensive understanding of its structure, technologies, and architecture.

Repository URL: {state.repository_url}

{repo_context_str}

Focus on:
1. Understanding the purpose and main functionality of the repository
2. Identifying the key technologies, frameworks, and architectural patterns
3. Assessing the complexity and organization of the codebase
4. Identifying key components and their likely relationships
5. Evaluating development practices based on the available information

Provide insights that will be valuable for analyzing pull requests to this repository.
"""
    
    analyzer_messages = state.analyzer_messages or []
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=analysis_request)
    ] + analyzer_messages
    
    try:
        response = await analyzer_model.ainvoke(messages)
        
        return Command(
            goto="repository_analyzer_tools",
            update={
                "analyzer_messages": [AIMessage(content=json.dumps(response.model_dump(), indent=2))]
            }
        )
        
    except Exception as e:
        error_message = f"Error in repository analyzer: {str(e)}"
        return Command(
            goto="repository_analyzer_tools",
            update={
                "analyzer_messages": [AIMessage(content=error_message)]
            }
        )


async def repository_analyzer_tools(state: RepositoryAnalyzerState, config: RunnableConfig):
    """Process repository analyzer results and fetch additional data if needed."""
    
    configurable = PRAnalysisConfiguration.from_runnable_config(config)
    analyzer_messages = state.analyzer_messages or []
    
    # If we don't have repository context yet, fetch it
    if not state.repository_context:
        try:
            repo_info = await fetch_repository_info(state.repository_url)
            repo_context = json.loads(repo_info)
            
            return {
                "repository_context": repo_context,
                "analyzer_messages": [HumanMessage(content="Repository context fetched, ready for analysis")]
            }
        except Exception as e:
            return {
                "analyzer_messages": analyzer_messages + [AIMessage(content=f"Error fetching repository context: {str(e)}")]
            }
    
    # Process the analysis result
    if analyzer_messages:
        last_message = analyzer_messages[-1]
        
        try:
            # Parse the analysis result
            if hasattr(last_message, 'content') and last_message.content:
                if last_message.content.startswith("Error"):
                    # Handle error case
                    analysis_result = RepositoryAnalysis(
                        repository=state.repository_context.repository,
                        context=state.repository_context,
                        summary="Error occurred during repository analysis",
                        technologies=state.repository_context.technologies or [],
                        architecture_patterns=["Unknown"],
                        key_components=["Unable to determine"],
                        complexity_score=5
                    )
                else:
                    # Parse successful analysis
                    try:
                        analysis_data = json.loads(last_message.content)
                    except json.JSONDecodeError:
                        # If not JSON, create basic analysis from context
                        analysis_data = {
                            "summary": "Repository analysis completed with limited data",
                            "technologies": state.repository_context.technologies or [],
                            "architecture_patterns": ["Standard"],
                            "key_components": state.repository_context.key_files or [],
                            "complexity_score": 5,
                            "main_features": ["Core functionality"],
                            "development_practices": ["Standard practices"]
                        }
                    
                    analysis_result = RepositoryAnalysis(
                        repository=state.repository_context.repository,
                        context=state.repository_context,
                        summary=analysis_data.get("summary", "Repository analysis completed"),
                        technologies=analysis_data.get("technologies", state.repository_context.technologies or []),
                        architecture_patterns=analysis_data.get("architecture_patterns", ["Standard"]),
                        key_components=analysis_data.get("key_components", state.repository_context.key_files or []),
                        complexity_score=analysis_data.get("complexity_score", 5)
                    )
                
                return {
                    "analysis_result": analysis_result
                }
        
        except Exception as e:
            # Fallback analysis
            analysis_result = RepositoryAnalysis(
                repository=state.repository_context.repository,
                context=state.repository_context,
                summary=f"Repository analysis completed with errors: {str(e)}",
                technologies=state.repository_context.technologies or [],
                architecture_patterns=["Unknown"],
                key_components=state.repository_context.key_files or [],
                complexity_score=5
            )
            
            return {
                "analysis_result": analysis_result
            }
    
    # No messages to process
    return {
        "analyzer_messages": analyzer_messages + [AIMessage(content="No analysis result to process")]
    }


def should_continue_analysis(state: RepositoryAnalyzerState) -> str:
    """Determine if repository analysis should continue."""
    
    # If we have the final analysis result, we're done
    if state.analysis_result:
        return "__end__"
    
    # If we don't have repository context, we need to fetch it first
    if not state.repository_context:
        return "repository_analyzer_tools"
    
    # If we have context but no analysis messages, start analysis
    analyzer_messages = state.analyzer_messages or []
    if not analyzer_messages:
        return "repository_analyzer"
    
    # If we have messages but no result, process the tools
    return "repository_analyzer_tools"