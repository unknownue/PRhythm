"""Agent-2 & Agent-3: Data Collection Agents for PRhythm."""

import asyncio
import json
import os
from typing import Dict, List, Literal, Optional, Union

from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command

from .configuration import AgentConfiguration
from .state import CollectorState, CollectorOutputState, DataCollectionTask, AnalysisComplete
from .tools import (
    git_checkout, git_diff, git_log, git_show, git_changed_files, git_status,
    analyze_file, analyze_directory, find_files
)


# Initialize configurable model for data collection
configurable_model = init_chat_model(
    configurable_fields=("model", "max_tokens", "api_key"),
)


async def data_collector_agent(
    state: CollectorState,
    config: RunnableConfig
) -> Command[Literal["execute_collection_tasks", "__end__"]]:
    """Main data collection agent that plans and coordinates data collection tasks.
    
    This agent analyzes the PR data and scheme configuration to determine what data
    needs to be collected from the git repository. It creates a plan of collection
    tasks that will be executed by the task executor.
    
    Args:
        state: Current collector state with PR data and workspace info
        config: Runtime configuration with model settings
        
    Returns:
        Command to proceed to task execution or end if no tasks needed
    """
    # Step 1: Extract state information
    pr_data = state["pr_data"]
    scheme_config = state["scheme_config"]
    workspace_path = state["workspace_path"]
    
    # Get agent configuration
    agent_config = AgentConfiguration.from_runnable_config(config)
    
    # Step 2: Determine collection requirements based on scheme
    requirements = scheme_config.get("requirements", {})
    is_pre_merge = "repo-previous" in workspace_path
    is_post_merge = "repo-merged" in workspace_path
    
    # Check if this agent should collect data
    should_collect = False
    if is_pre_merge and requirements.get("pre_merge_data", False):
        should_collect = True
    elif is_post_merge and requirements.get("post_merge_data", False):
        should_collect = True
    
    if not should_collect:
        return Command(
            goto=END,
            update={
                "collected_data": {},
                "execution_logs": ["No data collection required for this agent"],
                "messages": [HumanMessage(content="No data collection required for this workspace")]
            }
        )
    
    # Step 3: Configure the planning model
    model_config = {
        "model": agent_config.data_collector_model,
        "max_tokens": agent_config.data_collector_max_tokens,
        "api_key": agent_config.get_api_key_for_model(agent_config.data_collector_model, config),
        "tags": ["langsmith:nostream"]
    }
    
    planning_model = (
        configurable_model
        .bind_tools([DataCollectionTask, AnalysisComplete])
        .with_retry(stop_after_attempt=agent_config.max_structured_output_retries)
        .with_config(model_config)
    )
    
    # Step 4: Create planning prompt
    workspace_type = "pre-merge" if is_pre_merge else "post-merge"
    
    system_prompt = f"""You are a data collection agent for PR analysis in the PRhythm system.

Your role is to plan data collection tasks for {workspace_type} analysis.

Workspace: {workspace_path}
PR Information:
- PR #{pr_data.get('number', 'unknown')}
- Title: {pr_data.get('title', 'No title')}
- Base SHA: {pr_data.get('base', {}).get('sha', 'unknown')}
- Head SHA: {pr_data.get('head', {}).get('sha', 'unknown')}
- Files Changed: {pr_data.get('changed_files', 0)}

Analysis Scheme Requirements:
- Pre-merge data needed: {requirements.get('pre_merge_data', False)}
- Post-merge data needed: {requirements.get('post_merge_data', False)}
- PR metadata needed: {requirements.get('pr_metadata', False)}

Agent Tasks for {workspace_type.title()} Collection:
{json.dumps(scheme_config.get('agents', {}).get(f'{"pre" if is_pre_merge else "post"}_merge_collector', {}).get('tasks', []), indent=2)}

Create a plan of data collection tasks that will gather the necessary information
for this analysis scheme. Each task should specify the commands to run and whether
it's required for the analysis.

Common {workspace_type} tasks include:
- Repository state analysis (git status, git log)
- Code structure analysis (file counts, directory structure)
- Dependency analysis (package files, configuration)
- Diff analysis (changes, impact assessment)
- File content analysis (specific files of interest)

Plan your tasks strategically and call DataCollectionTask for each task you want to execute.
Call AnalysisComplete when you've planned all necessary tasks.
"""
    
    human_prompt = f"""Plan the data collection tasks for {workspace_type} analysis of PR #{pr_data.get('number', 'unknown')}.

Consider:
1. What information is needed for the selected analysis scheme?
2. What git commands will provide that information?
3. Which files or directories should be analyzed?
4. What are the priorities (required vs optional tasks)?

Create a comprehensive plan that will gather all necessary data efficiently."""
    
    # Step 5: Execute planning
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=human_prompt)
    ]
    
    try:
        planning_response = await planning_model.ainvoke(messages)
        
        return Command(
            goto="execute_collection_tasks",
            update={
                "messages": [planning_response],
                "execution_logs": ["Data collection planning completed"]
            }
        )
        
    except Exception as e:
        # Fallback: create basic collection tasks
        basic_tasks = _create_basic_collection_tasks(is_pre_merge, pr_data)
        
        return Command(
            goto="execute_collection_tasks",
            update={
                "collection_tasks": basic_tasks,
                "execution_logs": [f"Planning failed, using basic tasks: {str(e)}"],
                "messages": [HumanMessage(content=f"Using fallback collection tasks due to planning error: {str(e)}")]
            }
        )


async def execute_collection_tasks(
    state: CollectorState,
    config: RunnableConfig
) -> Command[Literal["data_collector_agent", "__end__"]]:
    """Execute the planned data collection tasks and gather repository data.
    
    This function processes tool calls from the planning agent and executes the
    corresponding git commands and file analysis operations. It handles errors
    gracefully and aggregates results.
    
    Args:
        state: Current collector state with planned tasks
        config: Runtime configuration
        
    Returns:
        Command to continue planning or end with collected data
    """
    # Step 1: Extract current state
    messages = state.get("messages", [])
    workspace_path = state["workspace_path"]
    pr_data = state["pr_data"]
    execution_logs = list(state.get("execution_logs", []))
    
    if not messages:
        return Command(goto=END, update={"collected_data": {}, "execution_logs": execution_logs})
    
    last_message = messages[-1]
    
    # Step 2: Check if planning is complete
    if not hasattr(last_message, 'tool_calls') or not last_message.tool_calls:
        return Command(goto=END, update={"collected_data": {}, "execution_logs": execution_logs})
    
    # Step 3: Process tool calls
    tool_responses = []
    collected_data = {}
    analysis_complete = False
    
    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]
        tool_id = tool_call["id"]
        
        try:
            if tool_name == "DataCollectionTask":
                # Execute a data collection task
                task_result = await _execute_data_collection_task(
                    task_name=tool_args["task_name"],
                    commands=tool_args["commands"],
                    required=tool_args["required"],
                    workspace_path=workspace_path,
                    config=config
                )
                
                # Store results
                collected_data[tool_args["task_name"]] = task_result
                execution_logs.append(f"Executed task: {tool_args['task_name']}")
                
                tool_responses.append(ToolMessage(
                    content=f"Task '{tool_args['task_name']}' completed successfully. Collected {len(task_result.get('data', {}))} data points.",
                    name="DataCollectionTask",
                    tool_call_id=tool_id
                ))
                
            elif tool_name == "AnalysisComplete":
                # Planning is complete
                analysis_complete = True
                execution_logs.append("Data collection planning completed")
                
                tool_responses.append(ToolMessage(
                    content=f"Data collection complete: {tool_args['summary']}",
                    name="AnalysisComplete",
                    tool_call_id=tool_id
                ))
                
        except Exception as e:
            # Handle tool execution errors
            error_msg = f"Error executing {tool_name}: {str(e)}"
            execution_logs.append(error_msg)
            
            tool_responses.append(ToolMessage(
                content=error_msg,
                name=tool_name,
                tool_call_id=tool_id
            ))
    
    # Step 4: Decide next action
    if analysis_complete:
        # All tasks planned and some executed, finish collection
        return Command(
            goto=END,
            update={
                "collected_data": collected_data,
                "execution_logs": execution_logs,
                "messages": tool_responses
            }
        )
    else:
        # Continue planning more tasks
        return Command(
            goto="data_collector_agent",
            update={
                "collected_data": collected_data,
                "execution_logs": execution_logs,
                "messages": tool_responses
            }
        )


async def _execute_data_collection_task(
    task_name: str,
    commands: List[str],
    required: bool,
    workspace_path: str,
    config: RunnableConfig
) -> Dict:
    """Execute a single data collection task with the specified commands.
    
    Args:
        task_name: Name of the task being executed
        commands: List of commands to execute
        required: Whether this task is required for analysis
        workspace_path: Path to the git repository workspace
        config: Runtime configuration
        
    Returns:
        Dictionary containing task execution results and collected data
    """
    results = {
        "task_name": task_name,
        "required": required,
        "success": True,
        "data": {},
        "errors": []
    }
    
    # Execute each command in the task
    for command in commands:
        try:
            if command.startswith("git "):
                # Execute git command
                result = await _execute_git_command_for_task(command, workspace_path, config)
                results["data"][f"git_command_{len(results['data'])}"] = result
                
            elif command.startswith("analyze_file "):
                # Analyze specific file
                file_path = command.replace("analyze_file ", "").strip()
                full_path = os.path.join(workspace_path, file_path)
                result = await analyze_file(full_path, config=config)
                results["data"][f"file_analysis_{file_path}"] = result.dict()
                
            elif command.startswith("analyze_directory "):
                # Analyze directory structure
                dir_path = command.replace("analyze_directory ", "").strip()
                full_path = os.path.join(workspace_path, dir_path)
                result = await analyze_directory(full_path, include_files=True, config=config)
                results["data"][f"directory_analysis_{dir_path}"] = result.dict()
                
            elif command.startswith("find_files "):
                # Find files matching pattern
                pattern = command.replace("find_files ", "").strip()
                result = await find_files(workspace_path, pattern=pattern, config=config)
                results["data"][f"file_search_{pattern}"] = result
                
            else:
                # Unknown command type
                results["errors"].append(f"Unknown command type: {command}")
                
        except Exception as e:
            error_msg = f"Error executing command '{command}': {str(e)}"
            results["errors"].append(error_msg)
            
            # Mark task as failed if it's required
            if required:
                results["success"] = False
    
    return results


async def _execute_git_command_for_task(
    command: str,
    workspace_path: str,
    config: RunnableConfig
) -> Dict:
    """Execute a git command and return structured results.
    
    Args:
        command: Git command to execute
        workspace_path: Repository workspace path
        config: Runtime configuration
        
    Returns:
        Dictionary with command execution results
    """
    # Parse git command and execute appropriate tool
    command_parts = command.split()
    git_subcommand = command_parts[1] if len(command_parts) > 1 else ""
    
    try:
        if git_subcommand == "status":
            result = await git_status(workspace_path, config=config)
        elif git_subcommand == "log":
            result = await git_log(workspace_path, config=config)
        elif git_subcommand == "diff":
            result = await git_diff(workspace_path, config=config)
        elif git_subcommand == "show":
            result = await git_show(workspace_path, config=config)
        elif git_subcommand == "ls-files" or "changed" in command:
            result = await git_changed_files(workspace_path, config=config)
        else:
            # Generic git command execution would go here
            # For now, return placeholder
            result = GitCommandResult(
                command=command,
                exit_code=0,
                stdout="Command not implemented",
                stderr="",
                success=False,
                execution_time_seconds=0.0
            )
        
        return result.dict()
        
    except Exception as e:
        return {
            "command": command,
            "success": False,
            "error": str(e)
        }


def _create_basic_collection_tasks(is_pre_merge: bool, pr_data: Dict) -> List[Dict]:
    """Create basic fallback collection tasks when planning fails.
    
    Args:
        is_pre_merge: Whether this is for pre-merge collection
        pr_data: PR data from GitHub
        
    Returns:
        List of basic collection task definitions
    """
    if is_pre_merge:
        return [
            {
                "task_name": "repository_status",
                "commands": ["git status", "git log --max-count=5"],
                "required": True
            },
            {
                "task_name": "code_structure",
                "commands": ["find_files *.py", "find_files *.js", "find_files *.java"],
                "required": False
            }
        ]
    else:
        return [
            {
                "task_name": "diff_analysis",
                "commands": ["git diff --stat HEAD~1 HEAD", "git changed-files HEAD~1 HEAD"],
                "required": True
            },
            {
                "task_name": "merge_analysis", 
                "commands": ["git show --stat", "git log --max-count=1"],
                "required": True
            }
        ]


# Data Collector Subgraph Construction
data_collector_builder = StateGraph(
    CollectorState,
    output=CollectorOutputState,
    config_schema=AgentConfiguration
)

# Add nodes for data collection workflow
data_collector_builder.add_node("data_collector_agent", data_collector_agent)
data_collector_builder.add_node("execute_collection_tasks", execute_collection_tasks)

# Define workflow edges
data_collector_builder.add_edge(START, "data_collector_agent")

# Compile the data collector subgraph
data_collector = data_collector_builder.compile()