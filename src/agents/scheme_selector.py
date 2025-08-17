"""Agent-1: Scheme Selection Agent for PRhythm."""

import asyncio
import os
from pathlib import Path
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


def _load_prompt_template(template_name: str) -> str:
    """Load prompt template from file.
    
    Args:
        template_name: Name of the template file (without .txt extension)
        
    Returns:
        Template content as string
    """
    # Get the project root directory (assumes this file is in src/agents/)
    current_file = Path(__file__)
    project_root = current_file.parent.parent.parent
    prompt_file = project_root / "prompts" / f"{template_name}.txt"
    
    try:
        with open(prompt_file, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except FileNotFoundError:
        # Fallback to default prompt if file not found
        if template_name == "scheme_selector_system":
            return """You are a PR analysis scheme selector for the PRhythm system.
For now, always select "general_review" as the analysis scheme regardless of the PR characteristics.
This is a simplified version while the system is being developed.
Please respond with "general_review" and provide a brief explanation for the selection."""
        elif template_name == "scheme_selector_human":
            return """Please select "general_review" as the analysis scheme and provide a brief explanation."""
        else:
            return "Template not found."


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
    
    # Step 2: Use simplified PR data analysis (skip tool call to avoid hanging)
    labels = []
    for label in pr_data.get("labels", []):
        if isinstance(label, str):
            labels.append(label)
        else:
            labels.append(label.get("name", ""))
    
    statistics = pr_data.get("statistics", {})
    pr_analysis = {
        "pr_number": pr_data.get("number"),
        "title": pr_data.get("title", ""),
        "labels": labels,
        "files_changed": statistics.get("files_changed", pr_data.get("changed_files", 0)),
        "total_changes": statistics.get("lines_changed", pr_data.get("additions", 0) + pr_data.get("deletions", 0))
    }
    
    
    # Step 3: Configure the scheme selection model
    model_name = agent_config.scheme_selector_model
    
    # Special handling for Ollama models
    if model_name.startswith("ollama:"):
        from langchain_ollama import ChatOllama
        
        ollama_config = agent_config.get_ollama_server_config()
        base_url = ollama_config.get("base_url")
        actual_model = ollama_config.get("model")
        
        # Use simple ChatOllama without structured output for compatibility
        selection_model = ChatOllama(
            model=actual_model,
            base_url=base_url,
            timeout=120
        )
    else:
        model_config = {
            "model": model_name,
            "max_tokens": agent_config.scheme_selector_max_tokens,
            "api_key": agent_config.get_api_key_for_model(model_name, config),
            "tags": ["langsmith:nostream"]
        }
        
        # Configure model with structured output and retry logic
        selection_model = (
            configurable_model
            .with_structured_output(SchemeSelection)
            .with_retry(stop_after_attempt=agent_config.max_structured_output_retries)
            .with_config(model_config)
        )
    
    # Step 4: Build analysis prompt from templates
    system_template = _load_prompt_template("scheme_selector_system")
    
    # Format system prompt with available data
    available_schemes_list = chr(10).join([f"- {str(scheme)}" for scheme in available_schemes])
    default_scheme = repository_config.get('analysis', {}).get('schemes', {}).get('default', 'general_review')
    
    system_prompt = system_template.format(
        available_schemes=available_schemes_list,
        default_scheme=default_scheme
    )
    
    # Create the analysis prompt with PR data
    # Safely handle labels to ensure they are strings
    labels_str = ', '.join(str(label) for label in pr_analysis.get('labels', [])) or 'None'
    
    # Safely get author information
    author_info = pr_data.get('author', {})
    if isinstance(author_info, dict):
        author = author_info.get('login', 'unknown')
    else:
        author = str(author_info) if author_info else 'unknown'
    
    # Safely get description
    description = pr_data.get('description') or pr_data.get('body', 'No description')
    if description:
        description_preview = description[:500]
        if len(description) > 500:
            description_preview += '...'
    else:
        description_preview = 'No description'
    
    # Load and format human prompt template
    human_template = _load_prompt_template("scheme_selector_human")
    
    human_prompt = human_template.format(
        pr_number=pr_analysis.get('pr_number', 'unknown'),
        title=pr_analysis.get('title', 'No title'),
        author=author,
        labels=labels_str,
        files_changed=pr_analysis.get('files_changed', 0),
        total_changes=pr_analysis.get('total_changes', 0),
        description_preview=description_preview
    )
    
    # Step 5: Execute scheme selection
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=human_prompt)
    ]
    
    try:
        # Add timeout to the actual call (increased timeout)
        selection_response = await asyncio.wait_for(
            selection_model.ainvoke(messages),
            timeout=60
        )
        
        # Handle different response types based on model
        if model_name.startswith("ollama:"):
            # For ollama, parse response content and create default selection
            response_text = selection_response.content
            
            # Simple scheme selection based on response content
            selected_scheme = "general_review"  # Default
            confidence = 0.8
            rationale = f"Selected general_review scheme based on Ollama response: {response_text[:100]}..."
            
            # Try to extract scheme from response if it mentions specific schemes
            for scheme in available_schemes:
                if scheme.lower() in response_text.lower():
                    selected_scheme = scheme
                    rationale = f"Selected {scheme} scheme based on Ollama analysis"
                    break
        else:
            # For structured output models
            selected_scheme = selection_response.scheme_name
            confidence = selection_response.confidence
            rationale = selection_response.rationale
        
        # Validate selected scheme exists
        if selected_scheme not in available_schemes:
            # Fall back to default scheme
            default_scheme = repository_config.get('analysis', {}).get('schemes', {}).get('default', 'general_review')
            selected_scheme = default_scheme
            rationale = f"Selected scheme not available, using default: {default_scheme}"
            confidence = 0.5
        
        # Check confidence threshold
        if confidence < agent_config.scheme_selection_confidence_threshold:
            # Use fallback scheme if confidence too low
            fallback_scheme = repository_config.get('analysis', {}).get('schemes', {}).get('fallback', 'general_review')
            selected_scheme = fallback_scheme
            rationale = f"Low confidence in selection, using fallback: {fallback_scheme}"
        
        return Command(
            goto=END,
            update={
                "selected_scheme": selected_scheme,
                "selection_rationale": rationale,
                "messages": [HumanMessage(content=f"Selected scheme: {selected_scheme} (confidence: {confidence:.2f})\\n\\nReasoning: {rationale}")]
            }
        )
        
    except Exception as e:
        # If scheme selection fails, use default scheme
        default_scheme = repository_config.get('analysis', {}).get('schemes', {}).get('default', 'general_review')
        error_message = f"Scheme selection failed, using default: {default_scheme}. Error: {str(e)}"
        
        return Command(
            goto=END,
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
    
    # Step 3: Use simplified PR data (skip tool call to avoid hanging)
    labels = []
    for label in pr_data.get("labels", []):
        if isinstance(label, str):
            labels.append(label)
        else:
            labels.append(label.get("name", ""))
    
    statistics = pr_data.get("statistics", {})
    pr_analysis = {
        "labels": labels,
        "files_changed": statistics.get("files_changed", pr_data.get("changed_files", 0)),
        "total_changes": statistics.get("lines_changed", pr_data.get("additions", 0) + pr_data.get("deletions", 0)),
        "author": pr_data.get("author", {}).get("login", pr_data.get("user", {}).get("login", ""))
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