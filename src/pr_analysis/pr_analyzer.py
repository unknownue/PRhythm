"""
Main PR Analysis workflow integrating all specialized agents.
"""
import asyncio
import json
from datetime import datetime
from typing import Dict, Any, Optional
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command

from .configuration import PRAnalysisConfiguration
from .state import (
    PRAnalysisState, PRAnalysisInputState, PRAnalysisOutputState,
    SupervisorState, RepositoryAnalyzerState, DiffAnalyzerState,
    ContextGathererState, ReportGeneratorState
)
from .github.client import GitHubAPIClient
from .github.models import PRAnalysisRequest, PRAnalysisResult
from .agents.supervisor import pr_supervisor, supervisor_tools, should_continue_coordination
from .agents.repository_analyzer import (
    repository_analyzer, repository_analyzer_tools, should_continue_analysis
)
from .agents.diff_analyzer import (
    diff_analyzer, diff_analyzer_tools, should_continue_diff_analysis
)
from .agents.context_gatherer import (
    context_gatherer, context_gatherer_tools, should_continue_context_gathering
)
from .agents.report_generator import (
    report_generator, report_generator_tools, should_continue_report_generation
)


async def initialize_pr_analysis(state: PRAnalysisState, config: RunnableConfig) -> Command:
    """Initialize PR analysis by fetching basic PR and repository data."""
    
    configurable = PRAnalysisConfiguration.from_runnable_config(config)
    analysis_request = state.analysis_request
    
    try:
        async with GitHubAPIClient() as client:
            # Fetch PR information
            pr = await client.get_pull_request(
                analysis_request.repository_url, 
                analysis_request.pr_number
            )
            
            # Fetch repository context
            repo_context = await client.get_repository_context(analysis_request.repository_url)
            
            # Fetch PR diff
            pr_diff = await client.get_pr_diff(
                analysis_request.repository_url, 
                analysis_request.pr_number
            )
            
            return Command(
                goto="pr_supervisor",
                update={
                    "raw_analysis_data": {
                        "pr_info": pr.model_dump(),
                        "repository_context": repo_context.model_dump(),
                        "pr_diff": pr_diff.model_dump(),
                        "initialization_timestamp": datetime.now().isoformat()
                    }
                }
            )
            
    except Exception as e:
        error_msg = f"Failed to initialize PR analysis: {str(e)}"
        return Command(
            goto="finalize_analysis",
            update={
                "raw_analysis_data": {
                    "error": error_msg,
                    "initialization_failed": True
                }
            }
        )


async def execute_agents(state: PRAnalysisState, config: RunnableConfig) -> Command:
    """Execute specialized agents based on supervisor plan."""
    
    configurable = PRAnalysisConfiguration.from_runnable_config(config)
    raw_data = state.raw_analysis_data
    
    if raw_data.get("initialization_failed"):
        return Command(goto="finalize_analysis")
    
    try:
        # Extract data for agents
        repo_context = raw_data.get("repository_context")
        pr_diff = raw_data.get("pr_diff")
        
        # Execute agents in parallel where possible
        agent_tasks = []
        
        # Repository Analyzer
        repo_analyzer_state = RepositoryAnalyzerState(
            repository_url=state.analysis_request.repository_url,
            analyzer_messages=[],
            repository_context=repo_context
        )
        
        # Diff Analyzer  
        diff_analyzer_state = DiffAnalyzerState(
            pr_diff=pr_diff,
            repository_context=repo_context,
            analyzer_messages=[]
        )
        
        # Run repository and diff analysis in parallel
        repo_task = run_repository_analyzer(repo_analyzer_state, config)
        diff_task = run_diff_analyzer(diff_analyzer_state, config)
        
        repo_result, diff_result = await asyncio.gather(repo_task, diff_task)
        
        # Context Gatherer (depends on diff analysis)
        context_gatherer_state = ContextGathererState(
            repository_url=state.analysis_request.repository_url,
            pr_number=state.analysis_request.pr_number,
            diff_analysis=diff_result,
            gatherer_messages=[]
        )
        
        context_result = await run_context_gatherer(context_gatherer_state, config)
        
        # Report Generator (depends on all previous analyses)
        report_generator_state = ReportGeneratorState(
            analysis_request=state.analysis_request,
            repository_analysis=repo_result,
            diff_analysis=diff_result,
            context_analysis=context_result,
            generator_messages=[]
        )
        
        final_report = await run_report_generator(report_generator_state, config)
        
        return Command(
            goto="finalize_analysis",
            update={
                "repository_analysis": repo_result,
                "diff_analysis": diff_result, 
                "context_analysis": context_result,
                "analysis_report": final_report,
                "completed_agents": ["repository_analyzer", "diff_analyzer", "context_gatherer", "report_generator"]
            }
        )
        
    except Exception as e:
        error_msg = f"Error executing agents: {str(e)}"
        return Command(
            goto="finalize_analysis",
            update={
                "raw_analysis_data": {
                    **raw_data,
                    "execution_error": error_msg
                }
            }
        )


async def finalize_analysis(state: PRAnalysisState, config: RunnableConfig):
    """Finalize the PR analysis and prepare output."""
    
    configurable = PRAnalysisConfiguration.from_runnable_config(config)
    
    # Create final analysis result
    if state.analysis_report:
        # Successful analysis
        analysis_result = PRAnalysisResult(
            pr=state.raw_analysis_data.get("pr_info", {}),
            repository_context=state.raw_analysis_data.get("repository_context", {}),
            diff=state.raw_analysis_data.get("pr_diff", {}),
            analysis_report=state.analysis_report.model_dump_json(),
            metadata={
                "analysis_depth": state.analysis_request.analysis_depth,
                "agents_completed": state.completed_agents,
                "analysis_timestamp": datetime.now().isoformat(),
                "configuration": {
                    "mock_llm_mode": configurable.mock_llm_mode.value,
                    "max_context_files": configurable.max_context_files
                }
            },
            generated_at=datetime.now()
        )
    else:
        # Failed analysis
        analysis_result = PRAnalysisResult(
            pr={},
            repository_context={},
            diff={},
            analysis_report=json.dumps({
                "error": "Analysis failed",
                "details": state.raw_analysis_data
            }),
            metadata={
                "analysis_failed": True,
                "error_timestamp": datetime.now().isoformat()
            },
            generated_at=datetime.now()
        )
    
    return {
        "analysis_report": state.analysis_report,
        "raw_analysis_data": {
            **state.raw_analysis_data,
            "final_result": analysis_result.model_dump()
        }
    }


# Helper functions for running individual agents

async def run_repository_analyzer(state: RepositoryAnalyzerState, config: RunnableConfig):
    """Run the repository analyzer agent."""
    
    # Build and run the repository analyzer graph
    builder = StateGraph(RepositoryAnalyzerState)
    builder.add_node("repository_analyzer", repository_analyzer)
    builder.add_node("repository_analyzer_tools", repository_analyzer_tools)
    
    builder.add_edge(START, "repository_analyzer")
    builder.add_conditional_edges(
        "repository_analyzer",
        should_continue_analysis,
        ["repository_analyzer_tools", END]
    )
    builder.add_conditional_edges(
        "repository_analyzer_tools", 
        should_continue_analysis,
        ["repository_analyzer", END]
    )
    
    graph = builder.compile()
    result = await graph.ainvoke(state, config)
    
    return result.get("analysis_result")


async def run_diff_analyzer(state: DiffAnalyzerState, config: RunnableConfig):
    """Run the diff analyzer agent."""
    
    # Build and run the diff analyzer graph
    builder = StateGraph(DiffAnalyzerState)
    builder.add_node("diff_analyzer", diff_analyzer)
    builder.add_node("diff_analyzer_tools", diff_analyzer_tools)
    
    builder.add_edge(START, "diff_analyzer")
    builder.add_conditional_edges(
        "diff_analyzer",
        should_continue_diff_analysis,
        ["diff_analyzer_tools", END]
    )
    builder.add_conditional_edges(
        "diff_analyzer_tools",
        should_continue_diff_analysis, 
        ["diff_analyzer", END]
    )
    
    graph = builder.compile()
    result = await graph.ainvoke(state, config)
    
    return result.get("analysis_result")


async def run_context_gatherer(state: ContextGathererState, config: RunnableConfig):
    """Run the context gatherer agent."""
    
    # Build and run the context gatherer graph
    builder = StateGraph(ContextGathererState)
    builder.add_node("context_gatherer", context_gatherer)
    builder.add_node("context_gatherer_tools", context_gatherer_tools)
    
    builder.add_edge(START, "context_gatherer")
    builder.add_conditional_edges(
        "context_gatherer",
        should_continue_context_gathering,
        ["context_gatherer_tools", END]
    )
    builder.add_conditional_edges(
        "context_gatherer_tools",
        should_continue_context_gathering,
        ["context_gatherer", END]
    )
    
    graph = builder.compile()
    result = await graph.ainvoke(state, config)
    
    return result.get("context_result")


async def run_report_generator(state: ReportGeneratorState, config: RunnableConfig):
    """Run the report generator agent."""
    
    # Build and run the report generator graph
    builder = StateGraph(ReportGeneratorState)
    builder.add_node("report_generator", report_generator)
    builder.add_node("report_generator_tools", report_generator_tools)
    
    builder.add_edge(START, "report_generator")
    builder.add_conditional_edges(
        "report_generator",
        should_continue_report_generation,
        ["report_generator_tools", END]
    )
    builder.add_conditional_edges(
        "report_generator_tools",
        should_continue_report_generation,
        ["report_generator", END]
    )
    
    graph = builder.compile()
    result = await graph.ainvoke(state, config)
    
    return result.get("final_report")


# Main PR Analysis Graph

def build_pr_analysis_graph():
    """Build the main PR analysis graph."""
    
    builder = StateGraph(PRAnalysisState, input=PRAnalysisInputState, output=PRAnalysisOutputState)
    
    # Add nodes
    builder.add_node("initialize_pr_analysis", initialize_pr_analysis)
    builder.add_node("pr_supervisor", pr_supervisor) 
    builder.add_node("supervisor_tools", supervisor_tools)
    builder.add_node("execute_agents", execute_agents)
    builder.add_node("finalize_analysis", finalize_analysis)
    
    # Add edges
    builder.add_edge(START, "initialize_pr_analysis")
    builder.add_conditional_edges(
        "initialize_pr_analysis",
        lambda state: "pr_supervisor" if not state.raw_analysis_data.get("initialization_failed") else "finalize_analysis"
    )
    builder.add_conditional_edges(
        "pr_supervisor",
        should_continue_coordination,
        ["supervisor_tools", "execute_agents"]
    )
    builder.add_conditional_edges(
        "supervisor_tools", 
        lambda state: "execute_agents" if state.analysis_plan else "pr_supervisor"
    )
    builder.add_edge("execute_agents", "finalize_analysis")
    builder.add_edge("finalize_analysis", END)
    
    return builder.compile()


# Main entry point
pr_analysis_graph = build_pr_analysis_graph()


async def analyze_pr(
    repository_url: str,
    pr_number: int,
    analysis_depth: str = "standard",
    include_context: bool = True,
    config: Optional[RunnableConfig] = None
) -> PRAnalysisResult:
    """
    Analyze a GitHub Pull Request.
    
    Args:
        repository_url: GitHub repository URL
        pr_number: Pull request number
        analysis_depth: Analysis depth (quick, standard, deep)
        include_context: Whether to include code context
        config: LangGraph configuration
    
    Returns:
        PRAnalysisResult with comprehensive analysis
    """
    
    analysis_request = PRAnalysisRequest(
        repository_url=repository_url,
        pr_number=pr_number,
        analysis_depth=analysis_depth,
        include_context=include_context
    )
    
    input_state = PRAnalysisInputState(
        analysis_request=analysis_request,
        messages=[]
    )
    
    result = await pr_analysis_graph.ainvoke(input_state, config)
    
    # Extract the final result from raw_analysis_data
    final_result_data = result.raw_analysis_data.get("final_result", {})
    
    if final_result_data:
        return PRAnalysisResult(**final_result_data)
    else:
        # Fallback result
        return PRAnalysisResult(
            pr={},
            repository_context={},
            diff={},
            analysis_report=json.dumps({"error": "Analysis failed to complete"}),
            metadata={"analysis_failed": True},
            generated_at=datetime.now()
        )