"""Agent-4: Report Processor Agent for PRhythm."""

import re
import json
from typing import Dict, List, Literal, Optional
from urllib.parse import urljoin, urlparse

from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command

from .configuration import AgentConfiguration
from .state import ProcessorState, ProcessorOutputState, ReportProcessingTask, AnalysisComplete


# Initialize configurable model for report processing
configurable_model = init_chat_model(
    configurable_fields=("model", "max_tokens", "api_key"),
)


async def report_processor_agent(
    state: ProcessorState,
    config: RunnableConfig
) -> Command[Literal["execute_processing_tasks", "__end__"]]:
    """Main report processor agent that plans post-processing tasks for the analysis report.
    
    This agent examines the raw analysis report and determines what post-processing
    tasks are needed to improve formatting, fix links, validate content, and ensure
    the report meets quality standards.
    
    Args:
        state: Current processor state with raw report and PR data
        config: Runtime configuration with model settings
        
    Returns:
        Command to proceed to task execution or end if no processing needed
    """
    # Step 1: Extract state information
    pr_data = state["pr_data"]
    raw_report = state["raw_report"]
    
    # Get agent configuration
    agent_config = AgentConfiguration.from_runnable_config(config)
    
    # Step 2: Analyze raw report for processing needs
    if not raw_report or len(raw_report.strip()) == 0:
        return Command(
            goto=END,
            update={
                "processed_report": "Error: No raw report provided for processing",
                "processing_logs": ["No raw report available"],
                "messages": [HumanMessage(content="No raw report to process")]
            }
        )
    
    # Step 3: Configure the planning model
    model_config = {
        "model": agent_config.report_processor_model,
        "max_tokens": agent_config.report_processor_max_tokens,
        "api_key": agent_config.get_api_key_for_model(agent_config.report_processor_model, config),
        "tags": ["langsmith:nostream"]
    }
    
    planning_model = (
        configurable_model
        .bind_tools([ReportProcessingTask, AnalysisComplete])
        .with_retry(stop_after_attempt=agent_config.max_structured_output_retries)
        .with_config(model_config)
    )
    
    # Step 4: Create planning prompt
    system_prompt = f"""You are a report post-processing agent for PR analysis in the PRhythm system.

Your role is to analyze the raw analysis report and plan processing tasks to improve its quality.

PR Information:
- PR #{pr_data.get('number', 'unknown')}
- Repository: {pr_data.get('base', {}).get('repo', {}).get('full_name', 'unknown')}
- Title: {pr_data.get('title', 'No title')}

Raw Report Length: {len(raw_report)} characters
Raw Report Preview:
{raw_report[:1000]}{'...' if len(raw_report) > 1000 else ''}

Common post-processing tasks include:
1. fix_relative_links - Fix relative GitHub links to absolute URLs
2. format_markdown - Ensure proper Markdown formatting
3. validate_structure - Check report structure and sections
4. fix_code_blocks - Ensure code blocks are properly formatted
5. generate_toc - Generate table of contents if needed
6. validate_citations - Check and fix source citations
7. clean_formatting - Remove extra whitespace and fix formatting issues
8. add_metadata - Add analysis metadata and timestamps

Analyze the raw report and create processing tasks to improve its quality.
Each task should specify the type of processing and any parameters needed.

Call ReportProcessingTask for each processing task you want to execute.
Call AnalysisComplete when you've planned all necessary tasks.
"""
    
    human_prompt = f"""Analyze the raw PR analysis report and plan post-processing tasks to improve its quality.

Consider:
1. Are there broken or relative links that need fixing?
2. Is the Markdown formatting correct and consistent?
3. Are code blocks properly formatted?
4. Is the report structure clear and well-organized?
5. Are there any formatting issues or inconsistencies?
6. Does the report need a table of contents?
7. Are sources and citations properly formatted?

Create a comprehensive processing plan to ensure the final report is high-quality and well-formatted."""
    
    # Step 5: Execute planning
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=human_prompt)
    ]
    
    try:
        planning_response = await planning_model.ainvoke(messages)
        
        return Command(
            goto="execute_processing_tasks",
            update={
                "messages": [planning_response],
                "processing_logs": ["Report processing planning completed"]
            }
        )
        
    except Exception as e:
        # Fallback: create basic processing tasks
        basic_tasks = _create_basic_processing_tasks(raw_report, pr_data)
        
        return Command(
            goto="execute_processing_tasks",
            update={
                "processing_tasks": basic_tasks,
                "processing_logs": [f"Planning failed, using basic tasks: {str(e)}"],
                "messages": [HumanMessage(content=f"Using fallback processing tasks due to planning error: {str(e)}")]
            }
        )


async def execute_processing_tasks(
    state: ProcessorState,
    config: RunnableConfig
) -> Command[Literal["report_processor_agent", "__end__"]]:
    """Execute the planned report processing tasks to improve report quality.
    
    This function processes tool calls from the planning agent and executes the
    corresponding post-processing operations on the raw report.
    
    Args:
        state: Current processor state with planned tasks
        config: Runtime configuration
        
    Returns:
        Command to continue planning or end with processed report
    """
    # Step 1: Extract current state
    messages = state.get("messages", [])
    raw_report = state["raw_report"]
    pr_data = state["pr_data"]
    processing_logs = list(state.get("processing_logs", []))
    
    # Start with the raw report
    current_report = raw_report
    
    if not messages:
        return Command(
            goto=END,
            update={
                "processed_report": current_report,
                "processing_logs": processing_logs
            }
        )
    
    last_message = messages[-1]
    
    # Step 2: Check if planning is complete
    if not hasattr(last_message, 'tool_calls') or not last_message.tool_calls:
        return Command(
            goto=END,
            update={
                "processed_report": current_report,
                "processing_logs": processing_logs
            }
        )
    
    # Step 3: Process tool calls
    tool_responses = []
    processing_complete = False
    
    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]
        tool_id = tool_call["id"]
        
        try:
            if tool_name == "ReportProcessingTask":
                # Execute a processing task
                task_type = tool_args["task_type"]
                parameters = tool_args.get("parameters", {})
                
                processed_content, log_message = await _execute_processing_task(
                    current_report, task_type, parameters, pr_data
                )
                
                current_report = processed_content
                processing_logs.append(log_message)
                
                tool_responses.append(ToolMessage(
                    content=f"Processing task '{task_type}' completed: {log_message}",
                    name="ReportProcessingTask",
                    tool_call_id=tool_id
                ))
                
            elif tool_name == "AnalysisComplete":
                # Processing is complete
                processing_complete = True
                processing_logs.append("Report processing completed")
                
                tool_responses.append(ToolMessage(
                    content=f"Report processing complete: {tool_args['summary']}",
                    name="AnalysisComplete",
                    tool_call_id=tool_id
                ))
                
        except Exception as e:
            # Handle task execution errors
            error_msg = f"Error executing {tool_name}: {str(e)}"
            processing_logs.append(error_msg)
            
            tool_responses.append(ToolMessage(
                content=error_msg,
                name=tool_name,
                tool_call_id=tool_id
            ))
    
    # Step 4: Decide next action
    if processing_complete:
        # All tasks completed, return final report
        return Command(
            goto=END,
            update={
                "processed_report": current_report,
                "processing_logs": processing_logs,
                "messages": tool_responses
            }
        )
    else:
        # Continue planning more tasks
        return Command(
            goto="report_processor_agent",
            update={
                "processed_report": current_report,
                "processing_logs": processing_logs,
                "messages": tool_responses
            }
        )


async def _execute_processing_task(
    report_content: str,
    task_type: str,
    parameters: Dict,
    pr_data: Dict
) -> tuple[str, str]:
    """Execute a single report processing task.
    
    Args:
        report_content: Current report content to process
        task_type: Type of processing task to execute
        parameters: Task-specific parameters
        pr_data: PR data for context
        
    Returns:
        Tuple of (processed_content, log_message)
    """
    if task_type == "fix_relative_links":
        return _fix_relative_links(report_content, pr_data)
    
    elif task_type == "format_markdown":
        return _format_markdown(report_content, parameters)
    
    elif task_type == "validate_structure":
        return _validate_structure(report_content, parameters)
    
    elif task_type == "fix_code_blocks":
        return _fix_code_blocks(report_content, parameters)
    
    elif task_type == "generate_toc":
        return _generate_toc(report_content, parameters)
    
    elif task_type == "validate_citations":
        return _validate_citations(report_content, parameters)
    
    elif task_type == "clean_formatting":
        return _clean_formatting(report_content, parameters)
    
    elif task_type == "add_metadata":
        return _add_metadata(report_content, pr_data, parameters)
    
    else:
        return report_content, f"Unknown task type: {task_type}"


def _fix_relative_links(report_content: str, pr_data: Dict) -> tuple[str, str]:
    """Fix relative GitHub links to make them absolute."""
    repo_info = pr_data.get('base', {}).get('repo', {})
    repo_url = repo_info.get('html_url', '')
    
    if not repo_url:
        return report_content, "No repository URL available for link fixing"
    
    # Pattern to match relative links
    relative_link_pattern = r'\[([^\]]+)\]\((?!http)([^)]+)\)'
    
    def fix_link(match):
        link_text = match.group(1)
        relative_path = match.group(2)
        
        # Skip anchor links and other special cases
        if relative_path.startswith('#') or relative_path.startswith('mailto:'):
            return match.group(0)
        
        # Convert to absolute URL
        absolute_url = urljoin(repo_url + '/', relative_path)
        return f'[{link_text}]({absolute_url})'
    
    processed_content = re.sub(relative_link_pattern, fix_link, report_content)
    
    # Count fixes made
    original_matches = len(re.findall(relative_link_pattern, report_content))
    new_matches = len(re.findall(relative_link_pattern, processed_content))
    fixes_made = original_matches - new_matches
    
    return processed_content, f"Fixed {fixes_made} relative links"


def _format_markdown(report_content: str, parameters: Dict) -> tuple[str, str]:
    """Ensure proper Markdown formatting."""
    processed = report_content
    changes = []
    
    # Fix heading spacing
    processed = re.sub(r'^(#{1,6})\s*(.+)$', r'\1 \2', processed, flags=re.MULTILINE)
    if processed != report_content:
        changes.append("heading spacing")
    
    # Ensure blank lines around headers
    processed = re.sub(r'\n(#{1,6}\s+.+)\n', r'\n\n\1\n\n', processed)
    processed = re.sub(r'\n\n\n+', r'\n\n', processed)  # Remove excessive blank lines
    if processed != report_content:
        changes.append("header spacing")
    
    # Fix list formatting
    processed = re.sub(r'^(\s*)([\*\-\+])\s*(.+)$', r'\1\2 \3', processed, flags=re.MULTILINE)
    if processed != report_content:
        changes.append("list formatting")
    
    log_message = f"Applied formatting fixes: {', '.join(changes)}" if changes else "No formatting issues found"
    return processed, log_message


def _validate_structure(report_content: str, parameters: Dict) -> tuple[str, str]:
    """Validate and fix report structure."""
    lines = report_content.split('\n')
    issues = []
    
    # Check for main title (H1)
    has_h1 = any(line.strip().startswith('# ') for line in lines)
    if not has_h1:
        issues.append("missing main title")
    
    # Check for section headers (H2)
    h2_count = sum(1 for line in lines if line.strip().startswith('## '))
    if h2_count == 0:
        issues.append("no section headers")
    
    # Check for conclusion section
    has_conclusion = any('conclusion' in line.lower() for line in lines if line.strip().startswith('## '))
    if not has_conclusion:
        issues.append("no conclusion section")
    
    # For now, just report issues without fixing
    log_message = f"Structure validation: {', '.join(issues)}" if issues else "Report structure is valid"
    return report_content, log_message


def _fix_code_blocks(report_content: str, parameters: Dict) -> tuple[str, str]:
    """Fix code block formatting."""
    processed = report_content
    changes = []
    
    # Ensure code blocks are properly fenced
    # Fix inline code that might need to be blocks
    inline_code_pattern = r'`([^`\n]{50,})`'
    if re.search(inline_code_pattern, processed):
        processed = re.sub(inline_code_pattern, r'\n```\n\1\n```\n', processed)
        changes.append("converted long inline code to blocks")
    
    # Ensure proper spacing around code blocks
    processed = re.sub(r'\n```', r'\n\n```', processed)
    processed = re.sub(r'```\n', r'```\n\n', processed)
    processed = re.sub(r'\n\n\n+', r'\n\n', processed)  # Remove excessive blank lines
    
    log_message = f"Code block fixes: {', '.join(changes)}" if changes else "Code blocks are properly formatted"
    return processed, log_message


def _generate_toc(report_content: str, parameters: Dict) -> tuple[str, str]:
    """Generate table of contents."""
    lines = report_content.split('\n')
    headers = []
    
    # Extract headers
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('#'):
            level = len(stripped) - len(stripped.lstrip('#'))
            title = stripped.lstrip('#').strip()
            if level >= 2:  # Skip H1 (main title)
                headers.append((level, title))
    
    if not headers:
        return report_content, "No headers found for TOC generation"
    
    # Generate TOC
    toc_lines = ["## Table of Contents", ""]
    for level, title in headers:
        indent = "  " * (level - 2)
        # Create anchor link
        anchor = title.lower().replace(' ', '-').replace(',', '').replace('.', '')
        toc_lines.append(f"{indent}- [{title}](#{anchor})")
    
    toc_lines.append("")
    
    # Insert TOC after the first H1
    new_lines = []
    toc_inserted = False
    
    for line in lines:
        new_lines.append(line)
        if not toc_inserted and line.strip().startswith('# '):
            new_lines.append("")
            new_lines.extend(toc_lines)
            toc_inserted = True
    
    processed_content = '\n'.join(new_lines)
    return processed_content, f"Generated TOC with {len(headers)} entries"


def _validate_citations(report_content: str, parameters: Dict) -> tuple[str, str]:
    """Validate and fix source citations."""
    # Look for common citation patterns
    citation_patterns = [
        r'\[(\d+)\]',  # [1], [2], etc.
        r'\(Source:([^)]+)\)',  # (Source: ...)
        r'\*\*Source:\*\*([^*]+)',  # **Source:**...
    ]
    
    citations_found = 0
    for pattern in citation_patterns:
        citations_found += len(re.findall(pattern, report_content))
    
    log_message = f"Found {citations_found} citations in report"
    return report_content, log_message


def _clean_formatting(report_content: str, parameters: Dict) -> tuple[str, str]:
    """Clean up general formatting issues."""
    processed = report_content
    changes = []
    
    # Remove trailing whitespace
    lines = [line.rstrip() for line in processed.split('\n')]
    processed = '\n'.join(lines)
    changes.append("removed trailing whitespace")
    
    # Fix multiple consecutive blank lines
    processed = re.sub(r'\n\n\n+', r'\n\n', processed)
    changes.append("fixed excessive blank lines")
    
    # Ensure file ends with newline
    if not processed.endswith('\n'):
        processed += '\n'
        changes.append("added final newline")
    
    log_message = f"Formatting cleanup: {', '.join(changes)}"
    return processed, log_message


def _add_metadata(report_content: str, pr_data: Dict, parameters: Dict) -> tuple[str, str]:
    """Add metadata to the report."""
    from datetime import datetime
    
    # Create metadata section
    metadata_lines = [
        "---",
        f"# PR Analysis Report",
        f"**PR Number:** #{pr_data.get('number', 'unknown')}",
        f"**Repository:** {pr_data.get('base', {}).get('repo', {}).get('full_name', 'unknown')}",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}",
        f"**Analysis System:** PRhythm",
        "---",
        ""
    ]
    
    # Prepend metadata to report
    processed_content = '\n'.join(metadata_lines) + report_content
    
    return processed_content, "Added report metadata header"


def _create_basic_processing_tasks(raw_report: str, pr_data: Dict) -> List[Dict]:
    """Create basic fallback processing tasks when planning fails."""
    return [
        {
            "task_type": "fix_relative_links",
            "parameters": {}
        },
        {
            "task_type": "format_markdown",
            "parameters": {}
        },
        {
            "task_type": "clean_formatting",
            "parameters": {}
        },
        {
            "task_type": "add_metadata",
            "parameters": {}
        }
    ]


# Report Processor Subgraph Construction
report_processor_builder = StateGraph(
    ProcessorState,
    output=ProcessorOutputState,
    config_schema=AgentConfiguration
)

# Add nodes for report processing workflow
report_processor_builder.add_node("report_processor_agent", report_processor_agent)
report_processor_builder.add_node("execute_processing_tasks", execute_processing_tasks)

# Define workflow edges
report_processor_builder.add_edge(START, "report_processor_agent")

# Compile the report processor subgraph
report_processor = report_processor_builder.compile()