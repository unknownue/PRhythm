import json
from typing import Literal, List
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command
from pydantic import BaseModel, Field

from ..configuration import PRAnalysisConfiguration
from ..state import DiffAnalyzerState, DiffAnalysis
from ..mock_llm import MockLLMService
from ..github.tools import fetch_pr_diff, analyze_pr_impact


class DiffAnalysisResult(BaseModel):
    """Diff analysis result structure."""
    summary: str = Field(description="Summary of changes made in the PR")
    affected_components: List[str] = Field(description="Components affected by changes")
    change_types: List[str] = Field(description="Types of changes (feature, bugfix, refactor, etc.)")
    complexity_score: int = Field(description="Change complexity score (1-10)")
    risk_level: str = Field(description="Risk level: low, medium, high")
    breaking_changes: List[str] = Field(description="Potential breaking changes identified")
    security_implications: List[str] = Field(description="Security-related implications")
    performance_impact: str = Field(description="Potential performance impact")
    testing_requirements: List[str] = Field(description="Testing requirements for these changes")


# Initialize configurable model
configurable_model = init_chat_model(
    configurable_fields=("model", "max_tokens", "api_key"),
)


DIFF_ANALYZER_SYSTEM_PROMPT = """You are the Diff Analyzer, a specialized agent focused on analyzing code changes in GitHub Pull Requests.

Your responsibilities:
1. Analyze the specific changes made in the PR (additions, deletions, modifications)
2. Understand the purpose and scope of the changes
3. Identify affected components and systems
4. Assess the complexity and risk level of changes
5. Identify potential breaking changes or compatibility issues
6. Evaluate security and performance implications
7. Determine testing requirements

When analyzing PR diffs, consider:
- File types and their significance (source code, configuration, tests, documentation)
- Scale of changes (lines added/removed, files affected)
- Critical areas affected (authentication, database, API endpoints, core logic)
- Dependencies and interconnections between changed components
- Potential side effects and ripple impacts
- Code patterns and quality of changes

Risk assessment criteria:
- LOW: Minor changes, isolated components, good test coverage
- MEDIUM: Moderate changes, some integration points, potential for side effects
- HIGH: Major changes, critical systems, security-related, breaking changes

Provide analysis that helps reviewers understand:
- What was changed and why
- What components are affected
- What risks need to be considered
- What testing should be prioritized

Current date: {date}
Focus on practical insights that support effective code review and risk management.
"""


async def diff_analyzer(state: DiffAnalyzerState, config: RunnableConfig) -> Command[Literal["diff_analyzer_tools"]]:
    """Diff Analyzer agent."""
    
    configurable = PRAnalysisConfiguration.from_runnable_config(config)
    
    # Check if mock LLM should be used
    mock_service = MockLLMService(configurable.mock_llm_mode, configurable.mock_response_delay_seconds)
    if mock_service.should_use_mock_for_agent("diff_analyzer"):
        
        pr_diff_data = json.dumps(state.pr_diff.model_dump(), indent=2) if state.pr_diff else "{}"
        repo_context = json.dumps(state.repository_context.model_dump(), indent=2) if state.repository_context else None
        
        mock_response = await mock_service.analyze_diff(pr_diff_data, repo_context)
        
        return Command(
            goto="diff_analyzer_tools",
            update={
                "analyzer_messages": [AIMessage(content=mock_response)]
            }
        )
    
    # Use real LLM
    model_config = configurable.get_model_config("diff_analyzer")
    model_config.update({
        "api_key": config.get("api_key") if config else None,
        "tags": ["langsmith:nostream"]
    })
    
    analyzer_model = configurable_model.with_structured_output(DiffAnalysisResult).with_retry(
        stop_after_attempt=configurable.max_structured_output_retries
    ).with_config(model_config)
    
    # Prepare system prompt
    system_prompt = DIFF_ANALYZER_SYSTEM_PROMPT.format(
        date="2024-01-15"  # TODO: Use actual date
    )
    
    # Prepare diff analysis request
    diff_summary = "No diff data available"
    if state.pr_diff:
        diff_summary = f"""
PR Diff Information:
- PR Number: {state.pr_diff.pr_number}
- Repository: {state.pr_diff.repository}
- Total Files Changed: {len(state.pr_diff.files)}
- Total Additions: {state.pr_diff.total_additions}
- Total Deletions: {state.pr_diff.total_deletions}
- Total Changes: {state.pr_diff.total_changes}
- Commits: {len(state.pr_diff.commits)}

File Changes:
"""
        for i, file in enumerate(state.pr_diff.files[:10]):  # Limit to first 10 files
            diff_summary += f"""
{i+1}. {file.filename}
   - Status: {file.status}
   - Changes: +{file.additions}/-{file.deletions} ({file.changes} total)
   - Type: {file.filename.split('.')[-1] if '.' in file.filename else 'no extension'}
"""
            if file.patch and len(file.patch) < 1000:  # Include small patches
                diff_summary += f"   - Patch preview: {file.patch[:500]}...\n"
        
        if len(state.pr_diff.files) > 10:
            diff_summary += f"\n... and {len(state.pr_diff.files) - 10} more files"
        
        # Add commit information
        diff_summary += f"""

Recent Commits:
"""
        for i, commit in enumerate(state.pr_diff.commits[-3:]):  # Last 3 commits
            diff_summary += f"""
{i+1}. {commit.sha[:8]}: {commit.message[:100]}
   - Author: {commit.author.get('name', 'Unknown')}
   - Date: {commit.timestamp}
"""
    
    # Include repository context if available
    repo_context_summary = ""
    if state.repository_context:
        repo_context_summary = f"""

Repository Context:
- Main Language: {state.repository_context.main_language}
- Technologies: {', '.join(state.repository_context.technologies) if state.repository_context.technologies else 'Not specified'}
- Key Files: {', '.join(state.repository_context.key_files) if state.repository_context.key_files else 'None identified'}
"""
    
    analysis_request = f"""
Please analyze this PR diff and provide a comprehensive understanding of the changes, their impact, and associated risks.

{diff_summary}
{repo_context_summary}

Focus on:
1. Understanding what functionality is being changed or added
2. Identifying which components and systems are affected
3. Assessing the complexity and risk level of the changes
4. Identifying potential breaking changes or compatibility issues
5. Evaluating security and performance implications
6. Determining appropriate testing strategies

Provide insights that will help reviewers understand the scope and implications of these changes.
"""
    
    analyzer_messages = state.analyzer_messages or []
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=analysis_request)
    ] + analyzer_messages
    
    try:
        response = await analyzer_model.ainvoke(messages)
        
        return Command(
            goto="diff_analyzer_tools",
            update={
                "analyzer_messages": [AIMessage(content=json.dumps(response.model_dump(), indent=2))]
            }
        )
        
    except Exception as e:
        error_message = f"Error in diff analyzer: {str(e)}"
        return Command(
            goto="diff_analyzer_tools",
            update={
                "analyzer_messages": [AIMessage(content=error_message)]
            }
        )


async def diff_analyzer_tools(state: DiffAnalyzerState, config: RunnableConfig):
    """Process diff analyzer results."""
    
    configurable = PRAnalysisConfiguration.from_runnable_config(config)
    analyzer_messages = state.analyzer_messages or []
    
    # If we don't have PR diff data yet, we can't proceed
    if not state.pr_diff:
        return {
            "analyzer_messages": analyzer_messages + [AIMessage(content="Error: No PR diff data available for analysis")]
        }
    
    # Process the analysis result
    if analyzer_messages:
        last_message = analyzer_messages[-1]
        
        try:
            # Parse the analysis result
            if hasattr(last_message, 'content') and last_message.content:
                if last_message.content.startswith("Error"):
                    # Handle error case
                    analysis_result = DiffAnalysis(
                        pr_diff=state.pr_diff,
                        summary="Error occurred during diff analysis",
                        affected_components=["Unknown"],
                        change_types=["unknown"],
                        complexity_score=5,
                        risk_level="medium",
                        breaking_changes=[]
                    )
                else:
                    # Parse successful analysis
                    try:
                        analysis_data = json.loads(last_message.content)
                    except json.JSONDecodeError:
                        # If not JSON, create basic analysis from diff data
                        analysis_data = {
                            "summary": f"Changes to {len(state.pr_diff.files)} files with {state.pr_diff.total_changes} total modifications",
                            "affected_components": [f.filename.split('/')[0] if '/' in f.filename else f.filename for f in state.pr_diff.files[:5]],
                            "change_types": ["modification"],
                            "complexity_score": min(10, max(1, len(state.pr_diff.files) + (state.pr_diff.total_changes // 100))),
                            "risk_level": "low" if state.pr_diff.total_changes < 50 else "medium" if state.pr_diff.total_changes < 200 else "high",
                            "breaking_changes": [],
                            "security_implications": [],
                            "performance_impact": "minimal",
                            "testing_requirements": ["unit tests", "integration tests"]
                        }
                    
                    analysis_result = DiffAnalysis(
                        pr_diff=state.pr_diff,
                        summary=analysis_data.get("summary", "Diff analysis completed"),
                        affected_components=analysis_data.get("affected_components", ["Unknown"]),
                        change_types=analysis_data.get("change_types", ["modification"]),
                        complexity_score=analysis_data.get("complexity_score", 5),
                        risk_level=analysis_data.get("risk_level", "medium"),
                        breaking_changes=analysis_data.get("breaking_changes", [])
                    )
                
                return {
                    "analysis_result": analysis_result
                }
        
        except Exception as e:
            # Fallback analysis
            analysis_result = DiffAnalysis(
                pr_diff=state.pr_diff,
                summary=f"Diff analysis completed with errors: {str(e)}",
                affected_components=[f.filename for f in state.pr_diff.files[:3]],
                change_types=["unknown"],
                complexity_score=5,
                risk_level="medium",
                breaking_changes=[]
            )
            
            return {
                "analysis_result": analysis_result
            }
    
    # No messages to process
    return {
        "analyzer_messages": analyzer_messages + [AIMessage(content="No analysis result to process")]
    }


def should_continue_diff_analysis(state: DiffAnalyzerState) -> str:
    """Determine if diff analysis should continue."""
    
    # If we have the final analysis result, we're done
    if state.analysis_result:
        return "__end__"
    
    # If we don't have PR diff data, we can't proceed
    if not state.pr_diff:
        return "__end__"
    
    # If we have diff data but no analysis messages, start analysis
    analyzer_messages = state.analyzer_messages or []
    if not analyzer_messages:
        return "diff_analyzer"
    
    # If we have messages but no result, process the tools
    return "diff_analyzer_tools"