"""Agent-1: Scheme Selection Agent for PRhythm."""

import asyncio
from typing import Dict, List, Literal, Optional

from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command

from .configuration import AgentConfiguration
from .state import SchemeState, SchemeSelection
from .tools import analyze_pr_metadata


# Initialize a configurable model for scheme selection
configurable_model = init_chat_model(
    configurable_fields=("model", "max_tokens", "api_key"),
)


async def scheme_selector_agent(
    state: SchemeState, 
    config: RunnableConfig
) -> Command[Literal["evaluate_conditions", "__end__"]]:
    """Main scheme selector agent that analyzes PR data and selects appropriate analysis scheme.
    
    This agent examines PR characteristics including labels, file changes, size, and other
    metadata to determine the most suitable analysis scheme for the PR.
    
    Args:
        state: Current scheme selection state with PR data and available schemes
        config: Runtime configuration with model settings
        
    Returns:
        Command to proceed to condition evaluation or end if no suitable scheme
    """
    # Step 1: Extract PR data and configuration
    pr_data = state["pr_data"]
    repository_config = state["repository_config"]
    available_schemes = state.get("available_schemes", [])
    
    # Get agent configuration
    agent_config = AgentConfiguration.from_runnable_config(config)
    
    # Step 2: Analyze PR metadata using the analysis tool
    try:
        pr_analysis = await analyze_pr_metadata(pr_data, config)
    except Exception as e:
        # If metadata analysis fails, use basic PR data
        pr_analysis = {
            "pr_number": pr_data.get("number"),
            "title": pr_data.get("title", ""),
            "labels": [label.get("name", "") for label in pr_data.get("labels", [])],
            "files_changed": pr_data.get("changed_files", 0),
            "total_changes": pr_data.get("additions", 0) + pr_data.get("deletions", 0)
        }
    
    # Step 3: Configure the scheme selection model
    model_config = {
        "model": agent_config.scheme_selector_model,
        "max_tokens": agent_config.scheme_selector_max_tokens,
        "api_key": agent_config.get_api_key_for_model(agent_config.scheme_selector_model, config),
        "tags": ["langsmith:nostream"]
    }
    
    # Configure model with structured output and retry logic
    selection_model = (
        configurable_model
        .with_structured_output(SchemeSelection)
        .with_retry(stop_after_attempt=agent_config.max_structured_output_retries)
        .with_config(model_config)
    )
    
    # Step 4: Build analysis prompt
    system_prompt = f"""You are a PR analysis scheme selector for the PRhythm system.

Your task is to analyze the provided PR data and select the most appropriate analysis scheme
from the available options. Consider the following factors:

1. PR Labels: Security, performance, documentation, breaking-change, etc.
2. PR Size: Number of files changed and total line changes
3. File Types: Programming languages and file extensions involved
4. PR Description: Keywords and context from title and description
5. Repository-specific Rules: Custom conditions defined in repository configuration

Available Schemes:
{chr(10).join([f"- {scheme}" for scheme in available_schemes])}

Repository Configuration:
- Default Scheme: {repository_config.get('analysis', {}).get('schemes', {}).get('default', 'general_review')}
- Custom Conditions: {len(repository_config.get('analysis', {}).get('schemes', {}).get('conditions', []))} rules defined

Select the scheme that best matches the PR characteristics and explain your reasoning.
Consider confidence in your selection - higher confidence for clear matches, lower for ambiguous cases.
"""
    
    # Create the analysis prompt with PR data
    human_prompt = f"""Analyze this PR and select the appropriate analysis scheme:

PR Information:
- Number: #{pr_analysis.get('pr_number', 'unknown')}
- Title: {pr_analysis.get('title', 'No title')}
- Author: {pr_analysis.get('author', 'unknown')}
- Labels: {', '.join(pr_analysis.get('labels', [])) or 'None'}
- Files Changed: {pr_analysis.get('files_changed', 0)}
- Total Changes: {pr_analysis.get('total_changes', 0)} lines
- Size Category: {pr_analysis.get('size_category', 'unknown')}
- Base Branch: {pr_analysis.get('base_branch', 'unknown')}

PR Description Preview:
{pr_analysis.get('description', 'No description')[:500]}{'...' if len(pr_analysis.get('description', '')) > 500 else ''}

Please select the most appropriate analysis scheme and provide your reasoning."""
    
    # Step 5: Execute scheme selection
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=human_prompt)
    ]
    
    try:
        selection_response = await selection_model.ainvoke(messages)
        
        # Validate selected scheme exists
        if selection_response.scheme_name not in available_schemes:
            # Fall back to default scheme
            default_scheme = repository_config.get('analysis', {}).get('schemes', {}).get('default', 'general_review')
            selection_response.scheme_name = default_scheme
            selection_response.rationale = f"Selected scheme not available, using default: {default_scheme}"
            selection_response.confidence = 0.5
        
        # Check confidence threshold
        if selection_response.confidence < agent_config.scheme_selection_confidence_threshold:
            # Use fallback scheme if confidence too low
            fallback_scheme = repository_config.get('analysis', {}).get('schemes', {}).get('fallback', 'general_review')
            selection_response.scheme_name = fallback_scheme
            selection_response.rationale = f"Low confidence in selection, using fallback: {fallback_scheme}"
        
        return Command(
            goto="evaluate_conditions",
            update={
                "selected_scheme": selection_response.scheme_name,
                "selection_rationale": selection_response.rationale,
                "messages": [HumanMessage(content=f"Selected scheme: {selection_response.scheme_name} (confidence: {selection_response.confidence:.2f})\\n\\nReasoning: {selection_response.rationale}")]
            }
        )
        
    except Exception as e:
        # If scheme selection fails, use default scheme
        default_scheme = repository_config.get('analysis', {}).get('schemes', {}).get('default', 'general_review')
        error_message = f"Scheme selection failed, using default: {default_scheme}. Error: {str(e)}"
        
        return Command(
            goto="evaluate_conditions",
            update={
                "selected_scheme": default_scheme,
                "selection_rationale": error_message,
                "messages": [HumanMessage(content=error_message)]
            }
        )


async def evaluate_conditions(
    state: SchemeState,
    config: RunnableConfig
) -> Command[Literal["__end__"]]:
    """Evaluate repository-specific conditions to potentially override scheme selection.
    
    This function checks if any repository-specific condition rules match the current PR
    and override the initially selected scheme if a higher priority match is found.
    
    Args:
        state: Current scheme state with selected scheme and PR data
        config: Runtime configuration
        
    Returns:
        Command to end with final scheme selection
    """
    # Step 1: Extract current selection and PR data
    selected_scheme = state.get("selected_scheme")
    pr_data = state["pr_data"]
    repository_config = state["repository_config"]
    
    # Step 2: Get condition rules from repository configuration
    scheme_config = repository_config.get('analysis', {}).get('schemes', {})
    conditions = scheme_config.get('conditions', [])
    
    if not conditions:
        # No conditions to evaluate, keep current selection
        return Command(
            goto=END,
            update={
                "messages": [HumanMessage(content=f"Final scheme selection: {selected_scheme} (no conditions to evaluate)")]
            }
        )
    
    # Step 3: Analyze PR metadata for condition evaluation
    try:
        pr_analysis = await analyze_pr_metadata(pr_data, config)
    except Exception:
        # Use basic data if analysis fails
        pr_analysis = {
            "labels": [label.get("name", "") for label in pr_data.get("labels", [])],
            "files_changed": pr_data.get("changed_files", 0),
            "total_changes": pr_data.get("additions", 0) + pr_data.get("deletions", 0),
            "author": pr_data.get("user", {}).get("login", "")
        }
    
    # Step 4: Evaluate conditions by priority
    matching_conditions = []
    
    for condition_rule in conditions:
        if _evaluate_condition(condition_rule.get("condition", {}), pr_analysis, pr_data):
            matching_conditions.append(condition_rule)
    
    # Step 5: Select highest priority matching condition
    if matching_conditions:
        # Sort by priority (high > medium > low)
        priority_order = {"high": 3, "medium": 2, "low": 1}
        matching_conditions.sort(
            key=lambda x: priority_order.get(x.get("priority", "low"), 1),
            reverse=True
        )
        
        # Use the highest priority match
        best_match = matching_conditions[0]
        override_scheme = best_match.get("scheme")
        condition_description = best_match.get("description", "Custom condition matched")
        
        if override_scheme and override_scheme != selected_scheme:
            return Command(
                goto=END,
                update={
                    "selected_scheme": override_scheme,
                    "selection_rationale": f"Overridden by condition: {condition_description}",
                    "messages": [HumanMessage(content=f"Scheme overridden by condition '{condition_description}': {override_scheme}")]
                }
            )
    
    # Step 6: No overrides, keep original selection
    return Command(
        goto=END,
        update={
            "messages": [HumanMessage(content=f"Final scheme selection: {selected_scheme} (conditions evaluated, no overrides)")]
        }
    )


def _evaluate_condition(condition: Dict, pr_analysis: Dict, pr_data: Dict) -> bool:
    """Evaluate a single condition against PR data.
    
    Args:
        condition: Condition definition from repository configuration
        pr_analysis: Analyzed PR metadata
        pr_data: Raw PR data from GitHub
        
    Returns:
        True if condition matches, False otherwise
    """
    condition_type = condition.get("type", "")
    
    if condition_type == "label_contains":
        # Check if PR has a label containing the specified value
        target_value = condition.get("value", "").lower()
        pr_labels = [label.lower() for label in pr_analysis.get("labels", [])]
        return any(target_value in label for label in pr_labels)
    
    elif condition_type == "files_changed":
        # Compare number of files changed
        operator = condition.get("operator", "==")
        target_value = condition.get("value", 0)
        actual_value = pr_analysis.get("files_changed", 0)
        return _compare_values(actual_value, operator, target_value)
    
    elif condition_type == "lines_changed":
        # Compare total lines changed
        operator = condition.get("operator", "==")
        target_value = condition.get("value", 0)
        actual_value = pr_analysis.get("total_changes", 0)
        return _compare_values(actual_value, operator, target_value)
    
    elif condition_type == "files_pattern":
        # Check if any changed files match the pattern
        pattern = condition.get("value", "")
        # This would need file list from git diff, simplified for now
        return False  # TODO: Implement pattern matching with actual file list
    
    elif condition_type == "author":
        # Check if PR author matches
        target_author = condition.get("value", "").lower()
        actual_author = pr_analysis.get("author", "").lower()
        return target_author == actual_author
    
    elif condition_type == "branch":
        # Check if target branch matches
        target_branch = condition.get("value", "")
        actual_branch = pr_analysis.get("base_branch", "")
        return target_branch == actual_branch
    
    elif condition_type == "and":
        # All subconditions must be true
        subconditions = condition.get("conditions", [])
        return all(_evaluate_condition(sub, pr_analysis, pr_data) for sub in subconditions)
    
    elif condition_type == "or":
        # At least one subcondition must be true
        subconditions = condition.get("conditions", [])
        return any(_evaluate_condition(sub, pr_analysis, pr_data) for sub in subconditions)
    
    # Unknown condition type
    return False


def _compare_values(actual: int, operator: str, expected: int) -> bool:
    """Compare two values using the specified operator."""
    if operator == "==":
        return actual == expected
    elif operator == "!=":
        return actual != expected
    elif operator == ">":
        return actual > expected
    elif operator == ">=":
        return actual >= expected
    elif operator == "<":
        return actual < expected
    elif operator == "<=":
        return actual <= expected
    else:
        return False


# Scheme Selector Subgraph Construction
scheme_selector_builder = StateGraph(SchemeState, config_schema=AgentConfiguration)

# Add nodes for scheme selection workflow
scheme_selector_builder.add_node("scheme_selector_agent", scheme_selector_agent)
scheme_selector_builder.add_node("evaluate_conditions", evaluate_conditions)

# Define workflow edges
scheme_selector_builder.add_edge(START, "scheme_selector_agent")

# Compile the scheme selector subgraph
scheme_selector = scheme_selector_builder.compile()