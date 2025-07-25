import json
from datetime import datetime
from typing import Literal, List, Dict, Any
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command
from pydantic import BaseModel, Field

from ..configuration import PRAnalysisConfiguration
from ..state import ReportGeneratorState, PRAnalysisReport
from ..mock_llm import MockLLMService


class PRReportResult(BaseModel):
    """PR report generation result structure."""
    title: str = Field(description="Report title")
    executive_summary: str = Field(description="Executive summary of the analysis")
    repository_overview: str = Field(description="Overview of the repository")
    changes_summary: str = Field(description="Summary of changes in the PR")
    impact_analysis: str = Field(description="Analysis of the impact of changes")
    risk_assessment: str = Field(description="Risk assessment and mitigation strategies")
    recommendations: List[str] = Field(description="Recommendations for reviewers")
    technical_details: Dict[str, Any] = Field(description="Technical details and metrics")
    conclusion: str = Field(description="Final conclusion and recommendation")


# Initialize configurable model
configurable_model = init_chat_model(
    configurable_fields=("model", "max_tokens", "api_key"),
)


REPORT_GENERATOR_SYSTEM_PROMPT = """You are the Report Generator, a specialized agent that synthesizes all PR analysis findings into comprehensive, actionable reports.

Your responsibilities:
1. Synthesize findings from repository analysis, diff analysis, and context gathering
2. Create executive summaries that highlight key insights
3. Provide detailed impact analysis and risk assessment
4. Generate specific, actionable recommendations for reviewers
5. Structure information for easy consumption by different audiences
6. Ensure technical accuracy while maintaining readability

Report structure guidelines:
- Executive Summary: 2-3 sentences capturing the essence of the PR
- Repository Overview: Brief context about the codebase and its purpose
- Changes Summary: What was changed and why (from diff analysis)
- Impact Analysis: Which components are affected and how
- Risk Assessment: Potential risks and mitigation strategies
- Recommendations: Specific actions for reviewers to take
- Technical Details: Metrics, statistics, and detailed findings
- Conclusion: Final assessment and approval recommendation

Risk levels and recommendations:
- LOW RISK: Standard review process, focus on code quality
- MEDIUM RISK: Enhanced review, consider additional testing
- HIGH RISK: Thorough review, security assessment, staged deployment

Target audiences:
- Primary: Code reviewers and maintainers
- Secondary: Project managers and stakeholders
- Technical level: Balance technical depth with accessibility

Current date: {date}
Include code snippets: {include_code_snippets}
Include risk assessment: {include_risk_assessment}
Include recommendations: {include_recommendations}
Report format: {report_format}
"""


async def report_generator(state: ReportGeneratorState, config: RunnableConfig) -> Command[Literal["report_generator_tools"]]:
    """Report Generator agent."""
    
    configurable = PRAnalysisConfiguration.from_runnable_config(config)
    
    # Check if mock LLM should be used
    mock_service = MockLLMService(configurable.mock_llm_mode, configurable.mock_response_delay_seconds)
    if mock_service.should_use_mock_for_agent("report_generator"):
        
        # Prepare analysis data for mock service
        analysis_data = {
            "repository_analysis": state.repository_analysis.model_dump() if state.repository_analysis else {},
            "diff_analysis": state.diff_analysis.model_dump() if state.diff_analysis else {},
            "context_analysis": state.context_analysis.model_dump() if state.context_analysis else {},
            "analysis_request": state.analysis_request.model_dump()
        }
        
        mock_response = await mock_service.generate_report(json.dumps(analysis_data))
        
        return Command(
            goto="report_generator_tools",
            update={
                "generator_messages": [AIMessage(content=mock_response)]
            }
        )
    
    # Use real LLM
    model_config = configurable.get_model_config("report_generator")
    model_config.update({
        "api_key": config.get("api_key") if config else None,
        "tags": ["langsmith:nostream"]
    })
    
    generator_model = configurable_model.with_structured_output(PRReportResult).with_retry(
        stop_after_attempt=configurable.max_structured_output_retries
    ).with_config(model_config)
    
    # Prepare system prompt
    system_prompt = REPORT_GENERATOR_SYSTEM_PROMPT.format(
        date=datetime.now().strftime("%Y-%m-%d"),
        include_code_snippets=configurable.include_code_snippets,
        include_risk_assessment=configurable.include_risk_assessment,
        include_recommendations=configurable.include_recommendations,
        report_format=configurable.report_format
    )
    
    # Prepare comprehensive analysis data
    report_request = f"""
Please generate a comprehensive PR analysis report based on the following findings:

## PR Information
- Repository: {state.analysis_request.repository_url}
- PR Number: {state.analysis_request.pr_number}
- Analysis Depth: {state.analysis_request.analysis_depth}
- Context Included: {state.analysis_request.include_context}

"""
    
    # Add repository analysis
    if state.repository_analysis:
        report_request += f"""
## Repository Analysis
- Summary: {state.repository_analysis.summary}
- Technologies: {', '.join(state.repository_analysis.technologies)}
- Architecture Patterns: {', '.join(state.repository_analysis.architecture_patterns)}
- Key Components: {', '.join(state.repository_analysis.key_components)}
- Complexity Score: {state.repository_analysis.complexity_score}/10

Repository Details:
- Name: {state.repository_analysis.repository.name}
- Language: {state.repository_analysis.repository.language or 'Not specified'}
- Size: {state.repository_analysis.repository.size} KB
- Description: {state.repository_analysis.repository.description or 'No description'}

"""
    
    # Add diff analysis
    if state.diff_analysis:
        report_request += f"""
## Diff Analysis
- Changes Summary: {state.diff_analysis.summary}
- Affected Components: {', '.join(state.diff_analysis.affected_components)}
- Change Types: {', '.join(state.diff_analysis.change_types)}
- Complexity Score: {state.diff_analysis.complexity_score}/10
- Risk Level: {state.diff_analysis.risk_level.upper()}
- Breaking Changes: {len(state.diff_analysis.breaking_changes)} identified

PR Statistics:
- Files Changed: {len(state.diff_analysis.pr_diff.files)}
- Total Additions: {state.diff_analysis.pr_diff.total_additions}
- Total Deletions: {state.diff_analysis.pr_diff.total_deletions}
- Commits: {len(state.diff_analysis.pr_diff.commits)}

Breaking Changes:
{chr(10).join(f"- {change}" for change in state.diff_analysis.breaking_changes) if state.diff_analysis.breaking_changes else "- None identified"}

"""
    
    # Add context analysis
    if state.context_analysis:
        report_request += f"""
## Context Analysis
- Relevant Files Found: {len(state.context_analysis.relevant_files)}
- Dependencies Identified: {len(state.context_analysis.dependencies)}
- Related Features: {len(state.context_analysis.related_features)}
- Test Coverage: {state.context_analysis.test_coverage.get('overall', 'Unknown')}

Key Context Files:
{chr(10).join(f"- {file.file_path} ({file.context_type}, relevance: {file.relevance_score:.1f})" for file in state.context_analysis.relevant_files[:5])}

Dependencies:
{chr(10).join(f"- {dep}" for dep in state.context_analysis.dependencies[:10]) if state.context_analysis.dependencies else "- None identified"}

Related Features:
{chr(10).join(f"- {feature}" for feature in state.context_analysis.related_features[:5]) if state.context_analysis.related_features else "- None identified"}

"""
    
    report_request += """
Please create a comprehensive, well-structured report that:
1. Provides clear executive summary for quick understanding
2. Explains the repository context and what this PR aims to achieve
3. Details the changes and their implications
4. Assesses risks and provides mitigation strategies
5. Offers specific, actionable recommendations for reviewers
6. Concludes with an overall assessment and recommendation

Focus on practical insights that will help reviewers make informed decisions about this PR.
"""
    
    generator_messages = state.generator_messages or []
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=report_request)
    ] + generator_messages
    
    try:
        response = await generator_model.ainvoke(messages)
        
        return Command(
            goto="report_generator_tools",
            update={
                "generator_messages": [AIMessage(content=json.dumps(response.model_dump(), indent=2))]
            }
        )
        
    except Exception as e:
        error_message = f"Error in report generator: {str(e)}"
        return Command(
            goto="report_generator_tools",
            update={
                "generator_messages": [AIMessage(content=error_message)]
            }
        )


async def report_generator_tools(state: ReportGeneratorState, config: RunnableConfig):
    """Process report generator results and create final report."""
    
    configurable = PRAnalysisConfiguration.from_runnable_config(config)
    generator_messages = state.generator_messages or []
    
    if not generator_messages:
        return {
            "generator_messages": [AIMessage(content="No report generation messages to process")]
        }
    
    last_message = generator_messages[-1]
    
    try:
        # Parse the report result
        if hasattr(last_message, 'content') and last_message.content:
            if last_message.content.startswith("Error"):
                # Handle error case - create basic report
                final_report = PRAnalysisReport(
                    pr_number=state.analysis_request.pr_number,
                    repository_url=state.analysis_request.repository_url,
                    title=f"PR #{state.analysis_request.pr_number} Analysis Report",
                    executive_summary="Error occurred during report generation. Manual review recommended.",
                    repository_overview="Repository analysis unavailable due to error.",
                    changes_summary="Change analysis unavailable due to error.",
                    impact_analysis="Impact analysis unavailable due to error.",
                    risk_assessment="Risk assessment unavailable - recommend thorough manual review.",
                    recommendations=["Conduct thorough manual review", "Verify all tests pass", "Check for security implications"],
                    technical_details={"error": last_message.content},
                    conclusion="Unable to complete automated analysis. Manual review required."
                )
            else:
                # Parse successful report generation
                try:
                    report_data = json.loads(last_message.content)
                except json.JSONDecodeError:
                    # If not JSON, create report from available data
                    report_data = _create_fallback_report_data(state)
                
                # Create comprehensive technical details
                technical_details = report_data.get("technical_details", {})
                
                # Add analysis metrics
                if state.repository_analysis:
                    technical_details["repository_complexity"] = state.repository_analysis.complexity_score
                    technical_details["technologies"] = state.repository_analysis.technologies
                
                if state.diff_analysis:
                    technical_details["change_complexity"] = state.diff_analysis.complexity_score
                    technical_details["risk_level"] = state.diff_analysis.risk_level
                    technical_details["files_changed"] = len(state.diff_analysis.pr_diff.files)
                    technical_details["lines_added"] = state.diff_analysis.pr_diff.total_additions
                    technical_details["lines_deleted"] = state.diff_analysis.pr_diff.total_deletions
                
                if state.context_analysis:
                    technical_details["context_files"] = len(state.context_analysis.relevant_files)
                    technical_details["test_coverage"] = state.context_analysis.test_coverage
                
                final_report = PRAnalysisReport(
                    pr_number=state.analysis_request.pr_number,
                    repository_url=state.analysis_request.repository_url,
                    title=report_data.get("title", f"PR #{state.analysis_request.pr_number} Analysis Report"),
                    executive_summary=report_data.get("executive_summary", "PR analysis completed successfully."),
                    repository_overview=report_data.get("repository_overview", "Repository overview not available."),
                    changes_summary=report_data.get("changes_summary", "Changes summary not available."),
                    impact_analysis=report_data.get("impact_analysis", "Impact analysis not available."),
                    risk_assessment=report_data.get("risk_assessment", "Risk assessment not available."),
                    recommendations=report_data.get("recommendations", ["Review code quality", "Verify tests pass"]),
                    technical_details=technical_details,
                    conclusion=report_data.get("conclusion", "PR analysis completed.")
                )
        
        else:
            # No content - create minimal report
            final_report = _create_minimal_report(state)
        
        return {
            "final_report": final_report
        }
        
    except Exception as e:
        # Complete fallback
        final_report = PRAnalysisReport(
            pr_number=state.analysis_request.pr_number,
            repository_url=state.analysis_request.repository_url,
            title=f"PR #{state.analysis_request.pr_number} Analysis Report",
            executive_summary=f"Report generation encountered errors: {str(e)}",
            repository_overview="Unable to generate repository overview.",
            changes_summary="Unable to generate changes summary.",
            impact_analysis="Unable to generate impact analysis.",
            risk_assessment="Manual review recommended due to analysis errors.",
            recommendations=["Conduct thorough manual review", "Verify functionality", "Test thoroughly"],
            technical_details={"generation_error": str(e)},
            conclusion="Automated analysis incomplete. Manual review required."
        )
        
        return {
            "final_report": final_report,
            "generator_messages": generator_messages + [AIMessage(content=f"Error creating report: {str(e)}")]
        }


def _create_fallback_report_data(state: ReportGeneratorState) -> Dict[str, Any]:
    """Create fallback report data from available state information."""
    
    repo_name = "Unknown Repository"
    if state.repository_analysis:
        repo_name = state.repository_analysis.repository.name
    
    change_summary = "Changes analyzed"
    risk_level = "medium"
    if state.diff_analysis:
        change_summary = state.diff_analysis.summary
        risk_level = state.diff_analysis.risk_level
    
    return {
        "title": f"Analysis Report: {repo_name} PR #{state.analysis_request.pr_number}",
        "executive_summary": f"Analysis completed for PR #{state.analysis_request.pr_number}. {change_summary}",
        "repository_overview": f"Repository: {repo_name}",
        "changes_summary": change_summary,
        "impact_analysis": f"Impact level assessed as {risk_level}",
        "risk_assessment": f"Risk level: {risk_level}. Standard review practices recommended.",
        "recommendations": ["Review code changes", "Verify tests", "Check for breaking changes"],
        "conclusion": "Analysis completed with available data."
    }


def _create_minimal_report(state: ReportGeneratorState) -> PRAnalysisReport:
    """Create minimal report when no analysis data is available."""
    
    return PRAnalysisReport(
        pr_number=state.analysis_request.pr_number,
        repository_url=state.analysis_request.repository_url,
        title=f"PR #{state.analysis_request.pr_number} Basic Analysis",
        executive_summary="Basic PR analysis performed. Manual review recommended for comprehensive assessment.",
        repository_overview="Repository information not fully available.",
        changes_summary="Change details not fully analyzed.",
        impact_analysis="Impact assessment requires manual review.",
        risk_assessment="Risk level unknown - recommend standard review process.",
        recommendations=["Perform manual code review", "Run all tests", "Check for security implications"],
        technical_details={"analysis_status": "minimal"},
        conclusion="Basic analysis completed. Enhanced analysis recommended."
    )


def should_continue_report_generation(state: ReportGeneratorState) -> str:
    """Determine if report generation should continue."""
    
    # If we have the final report, we're done
    if state.final_report:
        return "__end__"
    
    # If we have generator messages but no final report, process the tools
    generator_messages = state.generator_messages or []
    if generator_messages:
        return "report_generator_tools"
    
    # Start report generation
    return "report_generator"