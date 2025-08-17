"""State definitions for PRhythm agents."""

import operator
from typing import Annotated, Dict, List, Optional, TypedDict

from langchain_core.messages import MessageLikeRepresentation
from langgraph.graph import MessagesState
from pydantic import BaseModel, Field


###################
# Structured Outputs
###################

class SchemeSelection(BaseModel):
    """Scheme selection result with rationale."""
    
    scheme_name: str = Field(
        description="The selected analysis scheme name"
    )
    rationale: str = Field(
        description="Explanation for why this scheme was selected"
    )
    confidence: float = Field(
        description="Confidence score for the selection (0.0-1.0)",
        ge=0.0,
        le=1.0
    )


class DataCollectionTask(BaseModel):
    """Data collection task definition."""
    
    task_name: str = Field(
        description="Name of the data collection task"
    )
    commands: List[str] = Field(
        description="List of commands to execute for data collection"
    )
    required: bool = Field(
        description="Whether this task is required for the analysis"
    )


class AnalysisComplete(BaseModel):
    """Signal that analysis is complete."""
    
    summary: str = Field(
        description="Brief summary of the analysis performed"
    )


class ReportProcessingTask(BaseModel):
    """Report processing task definition."""
    
    task_type: str = Field(
        description="Type of processing task (e.g., 'fix_links', 'format_markdown')"
    )
    parameters: Dict = Field(
        description="Task-specific parameters",
        default_factory=dict
    )


###################
# State Definitions
###################

def override_reducer(current_value, new_value):
    """Reducer function that allows overriding values in state."""
    if isinstance(new_value, dict) and new_value.get("type") == "override":
        return new_value.get("value", new_value)
    else:
        return operator.add(current_value, new_value)


class AgentInputState(MessagesState):
    """Input state containing PR data and configuration."""
    
    pr_data: Optional[Dict] = None  # GitHub PR metadata
    repository_config: Optional[Dict] = None  # Repository-specific configuration


class AgentState(MessagesState):
    """Main agent state for PR analysis workflow."""
    
    # Input data
    pr_data: Optional[Dict] = None
    repository_config: Optional[Dict] = None
    output_prompt_dir: Optional[str] = None
    stop_at_generate_analysis: Optional[bool] = None
    
    # Analysis configuration
    selected_scheme: Optional[str] = None
    scheme_config: Optional[Dict] = None
    
    # Collected data
    pre_merge_data: Optional[Dict] = None
    post_merge_data: Optional[Dict] = None
    
    # Processing state
    analysis_prompt: Optional[str] = None
    analysis_prompt_saved: Optional[str] = None
    raw_analysis_report: Optional[str] = None
    final_report: Optional[str] = None
    
    # Metadata
    workspace_paths: Optional[Dict] = None  # Paths to repo-previous and repo-merged
    analysis_metadata: Optional[Dict] = None  # Analysis timing, iterations, etc.


class SchemeState(TypedDict):
    """State for scheme selection agent."""
    
    messages: Annotated[List[MessageLikeRepresentation], operator.add]
    pr_data: Dict
    repository_config: Dict
    available_schemes: List[str]
    selected_scheme: Optional[str]
    selection_rationale: Optional[str]


class CollectorState(TypedDict):
    """State for data collection agents (pre/post merge)."""
    
    messages: Annotated[List[MessageLikeRepresentation], operator.add]
    pr_data: Dict
    scheme_config: Dict
    workspace_path: str  # Path to the specific repo directory
    collection_tasks: List[Dict]
    collected_data: Optional[Dict]
    execution_logs: Annotated[List[str], operator.add]


class ProcessorState(TypedDict):
    """State for report processor agent."""
    
    messages: Annotated[List[MessageLikeRepresentation], operator.add]
    pr_data: Dict
    raw_report: str
    processing_tasks: List[Dict]
    processed_report: Optional[str]
    processing_logs: Annotated[List[str], operator.add]


class WorkspaceState(BaseModel):
    """Workspace state management."""
    
    repository_name: str
    base_path: str
    repo_previous_path: str
    repo_merged_path: str
    reports_path: str
    temp_path: str
    
    # Git state tracking
    previous_commit: Optional[str] = None
    merged_commit: Optional[str] = None
    
    class Config:
        """Pydantic configuration."""
        arbitrary_types_allowed = True


###################
# Output States
###################

class CollectorOutputState(BaseModel):
    """Output state from data collection agents."""
    
    collected_data: Dict
    execution_logs: List[str]
    success: bool
    error_message: Optional[str] = None


class ProcessorOutputState(BaseModel):
    """Output state from report processor."""
    
    processed_report: str
    processing_logs: List[str]
    success: bool
    error_message: Optional[str] = None


class AnalysisOutputState(BaseModel):
    """Final output state from the complete analysis workflow."""
    
    final_report: str
    analysis_metadata: Dict
    scheme_used: str
    success: bool
    error_message: Optional[str] = None
    
    # For debugging and monitoring
    pre_merge_data_summary: Optional[str] = None
    post_merge_data_summary: Optional[str] = None
    processing_time_seconds: Optional[float] = None