from typing import List, Dict, Any, Optional, Annotated
from pydantic import BaseModel, Field
from langchain_core.messages import BaseMessage
from langgraph.graph import MessagesState
import operator

from .github.models import (
    PullRequest, GitHubRepository, PRDiff, RepositoryContext,
    PRAnalysisRequest, PRAnalysisResult
)


class RepositoryAnalysis(BaseModel):
    """Repository analysis result."""
    repository: GitHubRepository
    context: RepositoryContext
    summary: str = Field(description="Summary of repository purpose and structure")
    technologies: List[str] = Field(description="List of technologies and frameworks used")
    architecture_patterns: List[str] = Field(description="Identified architectural patterns")
    key_components: List[str] = Field(description="Key components and modules")
    complexity_score: int = Field(description="Repository complexity score (1-10)")


class DiffAnalysis(BaseModel):
    """Diff analysis result."""
    pr_diff: PRDiff
    summary: str = Field(description="Summary of changes made in the PR")
    affected_components: List[str] = Field(description="Components affected by changes")
    change_types: List[str] = Field(description="Types of changes (feature, bugfix, refactor, etc.)")
    complexity_score: int = Field(description="Change complexity score (1-10)")
    risk_level: str = Field(description="Risk level: low, medium, high")
    breaking_changes: List[str] = Field(description="Potential breaking changes identified")


class CodeContext(BaseModel):
    """Code context information."""
    file_path: str
    content: str
    relevance_score: float = Field(description="Relevance score (0-1)")
    context_type: str = Field(description="Type: configuration, source, test, documentation")


class ContextAnalysis(BaseModel):
    """Context gathering result."""
    relevant_files: List[CodeContext] = Field(description="Relevant code files and content")
    dependencies: List[str] = Field(description="Dependencies that might be affected")
    related_features: List[str] = Field(description="Related features or components")
    test_coverage: Dict[str, Any] = Field(description="Test coverage information")


class PRAnalysisReport(BaseModel):
    """Final PR analysis report."""
    pr_number: int
    repository_url: str
    title: str = Field(description="Report title")
    executive_summary: str = Field(description="Executive summary of the analysis")
    repository_overview: str = Field(description="Overview of the repository")
    changes_summary: str = Field(description="Summary of changes in the PR")
    impact_analysis: str = Field(description="Analysis of the impact of changes")
    risk_assessment: str = Field(description="Risk assessment and mitigation strategies")
    recommendations: List[str] = Field(description="Recommendations for reviewers")
    technical_details: Dict[str, Any] = Field(description="Technical details and metrics")
    conclusion: str = Field(description="Final conclusion and recommendation")


# LangGraph State Models

class PRAnalysisInputState(MessagesState):
    """Input state for PR analysis workflow."""
    analysis_request: PRAnalysisRequest


class PRAnalysisState(MessagesState):
    """Main state for PR analysis workflow."""
    # Input
    analysis_request: PRAnalysisRequest
    
    # Intermediate results
    repository_analysis: Optional[RepositoryAnalysis] = None
    diff_analysis: Optional[DiffAnalysis] = None
    context_analysis: Optional[ContextAnalysis] = None
    
    # Agent coordination
    active_agents: Annotated[List[str], operator.add] = Field(default_factory=list)
    completed_agents: Annotated[List[str], operator.add] = Field(default_factory=list)
    agent_results: Annotated[Dict[str, Any], operator.add] = Field(default_factory=dict)
    
    # Final output
    analysis_report: Optional[PRAnalysisReport] = None
    raw_analysis_data: Dict[str, Any] = Field(default_factory=dict)


class PRAnalysisOutputState(MessagesState):
    """Output state for PR analysis workflow."""
    analysis_report: PRAnalysisReport
    raw_analysis_data: Dict[str, Any]


# Agent-Specific States

class SupervisorState(MessagesState):
    """State for PR supervisor agent."""
    analysis_request: PRAnalysisRequest
    supervisor_messages: Annotated[List[BaseMessage], operator.add]
    analysis_plan: Optional[Dict[str, Any]] = None
    agent_assignments: Dict[str, List[str]] = Field(default_factory=dict)
    coordination_iterations: int = 0


class RepositoryAnalyzerState(MessagesState):
    """State for repository analyzer agent."""
    repository_url: str
    analyzer_messages: Annotated[List[BaseMessage], operator.add]
    repository_context: Optional[RepositoryContext] = None
    analysis_result: Optional[RepositoryAnalysis] = None


class DiffAnalyzerState(MessagesState):
    """State for diff analyzer agent."""
    pr_diff: PRDiff
    repository_context: Optional[RepositoryContext] = None
    analyzer_messages: Annotated[List[BaseMessage], operator.add]
    analysis_result: Optional[DiffAnalysis] = None


class ContextGathererState(MessagesState):
    """State for context gatherer agent."""
    repository_url: str
    pr_number: int
    diff_analysis: Optional[DiffAnalysis] = None
    gatherer_messages: Annotated[List[BaseMessage], operator.add]
    context_result: Optional[ContextAnalysis] = None


class ReportGeneratorState(MessagesState):
    """State for report generator agent."""
    analysis_request: PRAnalysisRequest
    repository_analysis: Optional[RepositoryAnalysis] = None
    diff_analysis: Optional[DiffAnalysis] = None
    context_analysis: Optional[ContextAnalysis] = None
    generator_messages: Annotated[List[BaseMessage], operator.add]
    final_report: Optional[PRAnalysisReport] = None


# Output States for Sub-agents

class RepositoryAnalyzerOutputState(BaseModel):
    """Output state for repository analyzer."""
    analysis_result: RepositoryAnalysis


class DiffAnalyzerOutputState(BaseModel):
    """Output state for diff analyzer."""
    analysis_result: DiffAnalysis


class ContextGathererOutputState(BaseModel):
    """Output state for context gatherer."""
    context_result: ContextAnalysis


class ReportGeneratorOutputState(BaseModel):
    """Output state for report generator."""
    final_report: PRAnalysisReport


# Tool Models

class AnalyzePRTool(BaseModel):
    """Tool for analyzing a PR."""
    repository_url: str = Field(description="GitHub repository URL")
    pr_number: int = Field(description="Pull request number")
    analysis_depth: str = Field(default="standard", description="Analysis depth")


class AnalyzeRepositoryTool(BaseModel):
    """Tool for analyzing repository structure."""
    repository_url: str = Field(description="GitHub repository URL")


class AnalyzeDiffTool(BaseModel):
    """Tool for analyzing PR diff."""
    pr_diff_data: str = Field(description="PR diff data as JSON string")
    repository_context: Optional[str] = Field(default=None, description="Repository context as JSON string")


class GatherContextTool(BaseModel):
    """Tool for gathering code context."""
    repository_url: str = Field(description="GitHub repository URL")
    pr_number: int = Field(description="Pull request number")
    changed_files: List[str] = Field(description="List of changed file paths")


class GenerateReportTool(BaseModel):
    """Tool for generating final report."""
    analysis_data: str = Field(description="Combined analysis data as JSON string")


# Mock LLM Response Models

class MockAnalysisResponse(BaseModel):
    """Mock response for analysis operations."""
    agent_type: str
    analysis_summary: str
    key_findings: List[str]
    confidence_score: float
    processing_time_ms: int