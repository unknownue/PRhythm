"""Main workflow orchestrating all PRhythm agents."""

import asyncio
import json
from datetime import datetime
from typing import Dict, List, Literal, Optional

from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command, Send

from .configuration import AgentConfiguration
from .state import (
    AgentInputState, 
    AgentState, 
    AnalysisOutputState,
    WorkspaceState
)
from .scheme_selector import scheme_selector
from .data_collector import data_collector
from .report_processor import report_processor
from .utils import setup_workspace, cleanup_workspace, load_scheme_config


# Initialize configurable model for main workflow
configurable_model = init_chat_model(
    configurable_fields=("model", "max_tokens", "api_key"),
)


async def initialize_analysis(
    state: AgentState, 
    config: RunnableConfig
) -> Command[Literal["select_scheme", "__end__"]]:
    """Initialize the PR analysis workflow with workspace setup and validation.
    
    This function validates input data, sets up the necessary workspace directories,
    and prepares the analysis environment for the multi-agent workflow.
    
    Args:
        state: Input state with PR data and repository configuration
        config: Runtime configuration
        
    Returns:
        Command to proceed to scheme selection or end if validation fails
    """
    # Step 1: Validate required input data
    pr_data = state.get("pr_data")
    repository_config = state.get("repository_config")
    
    if not pr_data:
        return Command(
            goto=END,
            update={
                "final_report": "Error: No PR data provided",
                "success": False,
                "error_message": "Missing PR data"
            }
        )
    
    if not repository_config:
        return Command(
            goto=END,
            update={
                "final_report": "Error: No repository configuration provided", 
                "success": False,
                "error_message": "Missing repository configuration"
            }
        )
    
    # Step 2: Extract repository information
    repo_info = pr_data.get('base', {}).get('repo', {})
    repo_name = repo_info.get('name', 'unknown-repo')
    repo_full_name = repo_info.get('full_name', 'unknown/unknown-repo')
    
    # Step 3: Set up workspace
    agent_config = AgentConfiguration.from_runnable_config(config)
    
    try:
        workspace_paths = agent_config.get_workspace_paths(repo_name)
        
        # Initialize workspace state
        workspace_state = WorkspaceState(
            repository_name=repo_name,
            base_path=workspace_paths["base"],
            repo_previous_path=workspace_paths["repo_previous"],
            repo_merged_path=workspace_paths["repo_merged"],
            reports_path=workspace_paths["reports"],
            temp_path=workspace_paths["temp"]
        )
        
        # Set up workspace directories if needed
        await setup_workspace(workspace_state, pr_data, config)
        
        # Step 4: Initialize analysis metadata
        analysis_metadata = {
            "start_time": datetime.now().isoformat(),
            "pr_number": pr_data.get("number"),
            "repository": repo_full_name,
            "pr_title": pr_data.get("title", ""),
            "pr_author": pr_data.get("user", {}).get("login", "unknown"),
            "base_sha": pr_data.get("base", {}).get("sha"),
            "head_sha": pr_data.get("head", {}).get("sha"),
            "workspace_paths": workspace_paths
        }
        
        return Command(
            goto="select_scheme",
            update={
                "workspace_paths": workspace_paths,
                "analysis_metadata": analysis_metadata,
                "messages": [HumanMessage(content=f"Initialized analysis for PR #{pr_data.get('number')} in {repo_full_name}")]
            }
        )
        
    except Exception as e:
        return Command(
            goto=END,
            update={
                "final_report": f"Error: Failed to initialize workspace: {str(e)}",
                "success": False,
                "error_message": f"Workspace initialization failed: {str(e)}"
            }
        )


async def select_scheme(
    state: AgentState,
    config: RunnableConfig
) -> Command[Literal["collect_data", "__end__"]]:
    """Select appropriate analysis scheme for the PR using the scheme selector agent.
    
    Args:
        state: Current agent state with PR data and workspace info
        config: Runtime configuration
        
    Returns:
        Command to proceed to data collection or end if scheme selection fails
    """
    try:
        # Prepare scheme selection state
        scheme_state = {
            "messages": [],
            "pr_data": state["pr_data"],
            "repository_config": state["repository_config"],
            "available_schemes": _get_available_schemes(state["repository_config"])
        }
        
        # Execute scheme selection subgraph
        scheme_result = await scheme_selector.ainvoke(scheme_state, config)
        
        # Extract selected scheme
        selected_scheme = scheme_result.get("selected_scheme")
        if not selected_scheme:
            return Command(
                goto=END,
                update={
                    "final_report": "Error: No scheme selected",
                    "success": False,
                    "error_message": "Scheme selection failed"
                }
            )
        
        # Load scheme configuration
        scheme_config = await load_scheme_config(selected_scheme, state["repository_config"])
        
        return Command(
            goto="collect_data",
            update={
                "selected_scheme": selected_scheme,
                "scheme_config": scheme_config,
                "messages": state.get("messages", []) + scheme_result.get("messages", [])
            }
        )
        
    except Exception as e:
        return Command(
            goto=END,
            update={
                "final_report": f"Error: Scheme selection failed: {str(e)}",
                "success": False,
                "error_message": f"Scheme selection error: {str(e)}"
            }
        )


async def collect_data(
    state: AgentState,
    config: RunnableConfig
) -> Command[Literal["generate_analysis", "__end__"]]:
    """Coordinate data collection from pre-merge and post-merge repositories.
    
    This function orchestrates parallel data collection using the data collector agents
    for both pre-merge and post-merge states if required by the selected scheme.
    
    Args:
        state: Current agent state with scheme and workspace info
        config: Runtime configuration
        
    Returns:
        Command to proceed to analysis generation or end if collection fails
    """
    try:
        scheme_config = state["scheme_config"]
        requirements = scheme_config.get("requirements", {})
        workspace_paths = state["workspace_paths"]
        
        # Determine what data needs to be collected
        collect_pre_merge = requirements.get("pre_merge_data", False)
        collect_post_merge = requirements.get("post_merge_data", False)
        
        collection_tasks = []
        
        # Prepare pre-merge collection if needed
        if collect_pre_merge:
            pre_merge_state = {
                "messages": [],
                "pr_data": state["pr_data"],
                "scheme_config": scheme_config,
                "workspace_path": workspace_paths["repo_previous"],
                "collection_tasks": [],
                "execution_logs": []
            }
            collection_tasks.append(("pre_merge", pre_merge_state))
        
        # Prepare post-merge collection if needed
        if collect_post_merge:
            post_merge_state = {
                "messages": [],
                "pr_data": state["pr_data"],
                "scheme_config": scheme_config,
                "workspace_path": workspace_paths["repo_merged"],
                "collection_tasks": [],
                "execution_logs": []
            }
            collection_tasks.append(("post_merge", post_merge_state))
        
        if not collection_tasks:
            # No data collection required
            return Command(
                goto="generate_analysis",
                update={
                    "pre_merge_data": {},
                    "post_merge_data": {},
                    "messages": state.get("messages", []) + [HumanMessage(content="No data collection required for selected scheme")]
                }
            )
        
        # Execute collection tasks in parallel
        collection_results = []
        for task_type, task_state in collection_tasks:
            try:
                result = await data_collector.ainvoke(task_state, config)
                collection_results.append((task_type, result))
            except Exception as e:
                # Handle individual collection failures
                collection_results.append((task_type, {
                    "collected_data": {},
                    "success": False,
                    "error_message": str(e)
                }))
        
        # Aggregate collection results
        pre_merge_data = {}
        post_merge_data = {}
        collection_messages = []
        
        for task_type, result in collection_results:
            if task_type == "pre_merge":
                pre_merge_data = result.get("collected_data", {})
            elif task_type == "post_merge":
                post_merge_data = result.get("collected_data", {})
            
            # Collect messages from collection results
            collection_messages.extend(result.get("messages", []))
        
        return Command(
            goto="generate_analysis",
            update={
                "pre_merge_data": pre_merge_data,
                "post_merge_data": post_merge_data,
                "messages": state.get("messages", []) + collection_messages
            }
        )
        
    except Exception as e:
        return Command(
            goto=END,
            update={
                "final_report": f"Error: Data collection failed: {str(e)}",
                "success": False,
                "error_message": f"Data collection error: {str(e)}"
            }
        )


async def generate_analysis(
    state: AgentState,
    config: RunnableConfig
) -> Command[Literal["process_report", "__end__"]]:
    """Generate the main PR analysis report using collected data and LLM.
    
    Args:
        state: Current agent state with collected data
        config: Runtime configuration
        
    Returns:
        Command to proceed to report processing or end if analysis fails
    """
    try:
        # Step 1: Aggregate all collected data
        pr_data = state["pr_data"]
        scheme_config = state["scheme_config"]
        pre_merge_data = state.get("pre_merge_data", {})
        post_merge_data = state.get("post_merge_data", {})
        
        # Step 2: Build comprehensive analysis prompt
        analysis_prompt = await _build_analysis_prompt(
            pr_data, scheme_config, pre_merge_data, post_merge_data
        )
        
        # Step 3: Configure analysis model
        agent_config = AgentConfiguration.from_runnable_config(config)
        model_config = {
            "model": agent_config.analysis_model,
            "max_tokens": agent_config.analysis_max_tokens,
            "api_key": agent_config.get_api_key_for_model(agent_config.analysis_model, config),
            "tags": ["langsmith:nostream"]
        }
        
        analysis_model = configurable_model.with_config(model_config)
        
        # Step 4: Generate analysis report
        messages = [HumanMessage(content=analysis_prompt)]
        analysis_response = await analysis_model.ainvoke(messages)
        
        raw_analysis_report = analysis_response.content
        
        return Command(
            goto="process_report",
            update={
                "analysis_prompt": analysis_prompt,
                "raw_analysis_report": raw_analysis_report,
                "messages": state.get("messages", []) + [HumanMessage(content="Generated raw analysis report")]
            }
        )
        
    except Exception as e:
        return Command(
            goto=END,
            update={
                "final_report": f"Error: Analysis generation failed: {str(e)}",
                "success": False,
                "error_message": f"Analysis generation error: {str(e)}"
            }
        )


async def process_report(
    state: AgentState,
    config: RunnableConfig
) -> Command[Literal["__end__"]]:
    """Process and finalize the analysis report using the report processor agent.
    
    Args:
        state: Current agent state with raw analysis report
        config: Runtime configuration
        
    Returns:
        Command to end with final processed report
    """
    try:
        # Prepare report processing state
        processor_state = {
            "messages": [],
            "pr_data": state["pr_data"],
            "raw_report": state["raw_analysis_report"],
            "processing_tasks": [],
            "processing_logs": []
        }
        
        # Execute report processing
        processing_result = await report_processor.ainvoke(processor_state, config)
        
        processed_report = processing_result.get("processed_report", state["raw_analysis_report"])
        
        # Finalize analysis metadata
        analysis_metadata = state.get("analysis_metadata", {})
        analysis_metadata.update({
            "end_time": datetime.now().isoformat(),
            "scheme_used": state.get("selected_scheme"),
            "data_collection_summary": {
                "pre_merge_tasks": len(state.get("pre_merge_data", {})),
                "post_merge_tasks": len(state.get("post_merge_data", {}))
            },
            "processing_logs": processing_result.get("processing_logs", [])
        })
        
        return Command(
            goto=END,
            update={
                "final_report": processed_report,
                "analysis_metadata": analysis_metadata,
                "scheme_used": state.get("selected_scheme"),
                "success": True,
                "messages": state.get("messages", []) + processing_result.get("messages", [])
            }
        )
        
    except Exception as e:
        return Command(
            goto=END,
            update={
                "final_report": state.get("raw_analysis_report", f"Error: Report processing failed: {str(e)}"),
                "success": False,
                "error_message": f"Report processing error: {str(e)}"
            }
        )


def _get_available_schemes(repository_config: Dict) -> List[str]:
    """Get list of available analysis schemes for the repository."""
    # Default schemes available to all repositories
    default_schemes = [
        "general_review",
        "security_audit", 
        "performance_check",
        "documentation_review",
        "breaking_changes"
    ]
    
    # Add custom schemes from repository config
    custom_schemes = []
    scheme_config = repository_config.get("analysis", {}).get("schemes", {})
    conditions = scheme_config.get("conditions", [])
    
    for condition in conditions:
        scheme_name = condition.get("scheme")
        if scheme_name and scheme_name not in default_schemes:
            custom_schemes.append(scheme_name)
    
    return default_schemes + custom_schemes


async def _build_analysis_prompt(
    pr_data: Dict,
    scheme_config: Dict,
    pre_merge_data: Dict,
    post_merge_data: Dict
) -> str:
    """Build comprehensive analysis prompt from all collected data."""
    
    # Extract basic PR information
    pr_info = f"""
PR #{pr_data.get('number', 'unknown')}
Title: {pr_data.get('title', 'No title')}
Author: {pr_data.get('user', {}).get('login', 'unknown')}
Description: {pr_data.get('body', 'No description')[:1000]}
Labels: {', '.join([label.get('name', '') for label in pr_data.get('labels', [])])}
Files Changed: {pr_data.get('changed_files', 0)}
Lines Added: {pr_data.get('additions', 0)}
Lines Deleted: {pr_data.get('deletions', 0)}
"""
    
    # Build data sections
    data_sections = []
    
    if pre_merge_data:
        pre_merge_summary = _summarize_collected_data(pre_merge_data)
        data_sections.append(f"Pre-merge Analysis:\n{pre_merge_summary}")
    
    if post_merge_data:
        post_merge_summary = _summarize_collected_data(post_merge_data)
        data_sections.append(f"Post-merge Analysis:\n{post_merge_summary}")
    
    # Get analysis focus areas from scheme
    focus_areas = scheme_config.get("llm_config", {}).get("analysis_focus", [
        "code_quality", "best_practices", "maintainability"
    ])
    
    # Build comprehensive prompt
    prompt = f"""Analyze this GitHub Pull Request based on the provided data and generate a comprehensive analysis report.

## PR Information:
{pr_info}

## Collected Data:
{chr(10).join(data_sections)}

## Analysis Requirements:
Focus Areas: {', '.join(focus_areas)}
Analysis Type: {scheme_config.get('metadata', {}).get('name', 'General Review')}

## Required Report Structure:
1. Executive Summary
2. Code Quality Assessment
3. Technical Impact Analysis
4. Security and Risk Assessment
5. Recommendations
6. Conclusion

Please provide a detailed, well-structured analysis report in Markdown format.
Consider all the collected data and focus on the specified areas.
Be thorough but concise, highlighting key findings and actionable recommendations.
"""
    
    return prompt


def _summarize_collected_data(data: Dict) -> str:
    """Summarize collected data for inclusion in analysis prompt."""
    summary_parts = []
    
    for task_name, task_data in data.items():
        if not isinstance(task_data, dict):
            continue
            
        task_summary = f"**{task_name}:**"
        
        # Summarize task data
        if task_data.get("success"):
            data_points = task_data.get("data", {})
            task_summary += f" {len(data_points)} data points collected"
            
            # Add key findings if available
            for key, value in data_points.items():
                if isinstance(value, dict) and value.get("stdout"):
                    # Git command output
                    output_preview = str(value["stdout"])[:200]
                    task_summary += f"\n  - {key}: {output_preview}..."
                elif isinstance(value, dict) and "file_path" in value:
                    # File analysis result
                    task_summary += f"\n  - Analyzed: {value['file_path']}"
        else:
            task_summary += " Failed"
            errors = task_data.get("errors", [])
            if errors:
                task_summary += f" (Errors: {', '.join(errors[:2])})"
        
        summary_parts.append(task_summary)
    
    return "\n".join(summary_parts) if summary_parts else "No data collected"


# Main Workflow Graph Construction
main_workflow_builder = StateGraph(
    AgentState,
    input=AgentInputState,
    output=AnalysisOutputState,
    config_schema=AgentConfiguration
)

# Add main workflow nodes
main_workflow_builder.add_node("initialize_analysis", initialize_analysis)
main_workflow_builder.add_node("select_scheme", select_scheme)
main_workflow_builder.add_node("collect_data", collect_data)
main_workflow_builder.add_node("generate_analysis", generate_analysis)
main_workflow_builder.add_node("process_report", process_report)

# Define workflow edges
main_workflow_builder.add_edge(START, "initialize_analysis")

# Compile the main PRhythm workflow
prhythm_workflow = main_workflow_builder.compile()