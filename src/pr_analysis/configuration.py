from pydantic import BaseModel, Field
from typing import Any, List, Optional
from langchain_core.runnables import RunnableConfig
import os
from enum import Enum


class AnalysisDepth(Enum):
    """Analysis depth options."""
    QUICK = "quick"
    STANDARD = "standard"
    DEEP = "deep"


class MockLLMMode(Enum):
    """Mock LLM mode options."""
    DISABLED = "disabled"
    SIMPLE = "simple"  # Return predefined simple responses
    REALISTIC = "realistic"  # Return more realistic mock responses
    MIXED = "mixed"  # Mix of real and mock responses for testing


class PRAnalysisConfiguration(BaseModel):
    """Configuration for PR analysis system."""
    
    # GitHub Configuration
    github_token: Optional[str] = Field(
        default=None,
        metadata={
            "description": "GitHub API token for accessing repositories and PRs"
        }
    )
    
    # Storage Configuration
    repo_storage_path: str = Field(
        default="./data/repos",
        metadata={
            "description": "Local path for storing cloned repositories"
        }
    )
    analysis_cache_path: str = Field(
        default="./data/analysis", 
        metadata={
            "description": "Path for storing analysis cache and intermediate results"
        }
    )
    report_output_path: str = Field(
        default="./reports",
        metadata={
            "description": "Path for storing generated analysis reports"
        }
    )
    
    # Analysis Configuration
    default_analysis_depth: AnalysisDepth = Field(
        default=AnalysisDepth.STANDARD,
        metadata={
            "description": "Default depth of analysis to perform"
        }
    )
    max_context_files: int = Field(
        default=20,
        metadata={
            "description": "Maximum number of context files to analyze per PR"
        }
    )
    max_file_size_kb: int = Field(
        default=100,
        metadata={
            "description": "Maximum size of individual files to analyze (in KB)"
        }
    )
    include_diff_context: bool = Field(
        default=True,
        metadata={
            "description": "Whether to include surrounding code context for diffs"
        }
    )
    context_lines_before: int = Field(
        default=5,
        metadata={
            "description": "Number of lines to include before changed code"
        }
    )
    context_lines_after: int = Field(
        default=5,
        metadata={
            "description": "Number of lines to include after changed code"
        }
    )
    
    # Agent Configuration  
    max_concurrent_agents: int = Field(
        default=3,
        metadata={
            "description": "Maximum number of agents to run concurrently"
        }
    )
    agent_timeout_seconds: int = Field(
        default=300,
        metadata={
            "description": "Timeout for individual agent operations in seconds"
        }
    )
    max_retries: int = Field(
        default=3,
        metadata={
            "description": "Maximum number of retries for failed operations"
        }
    )
    
    # Model Configuration (extends base Configuration)
    pr_supervisor_model: str = Field(
        default="openai:gpt-4.1",
        metadata={
            "description": "Model for PR supervisor agent (orchestration and decision-making)"
        }
    )
    pr_supervisor_model_max_tokens: int = Field(
        default=8192,
        metadata={
            "description": "Maximum output tokens for PR supervisor model"
        }
    )
    
    repository_analyzer_model: str = Field(
        default="openai:gpt-4.1-mini",
        metadata={
            "description": "Model for repository analysis (understanding codebase structure)"
        }
    )
    repository_analyzer_model_max_tokens: int = Field(
        default=10000,
        metadata={
            "description": "Maximum output tokens for repository analyzer model"
        }
    )
    
    diff_analyzer_model: str = Field(
        default="openai:gpt-4.1",
        metadata={
            "description": "Model for diff analysis (understanding code changes)"
        }
    )
    diff_analyzer_model_max_tokens: int = Field(
        default=12000,
        metadata={
            "description": "Maximum output tokens for diff analyzer model"
        }
    )
    
    context_gatherer_model: str = Field(
        default="openai:gpt-4.1-mini", 
        metadata={
            "description": "Model for context gathering (collecting relevant code)"
        }
    )
    context_gatherer_model_max_tokens: int = Field(
        default=8192,
        metadata={
            "description": "Maximum output tokens for context gatherer model"
        }
    )
    
    report_generator_model: str = Field(
        default="openai:gpt-4.1",
        metadata={
            "description": "Model for report generation (synthesizing final analysis)"
        }
    )
    report_generator_model_max_tokens: int = Field(
        default=15000,
        metadata={
            "description": "Maximum output tokens for report generator model"
        }
    )
    
    # Mock LLM Configuration (for development)
    mock_llm_mode: MockLLMMode = Field(
        default=MockLLMMode.DISABLED,
        metadata={
            "description": "Mock LLM mode for development and testing"
        }
    )
    mock_response_delay_seconds: float = Field(
        default=1.0,
        metadata={
            "description": "Artificial delay for mock LLM responses to simulate real API calls"
        }
    )
    
    # Report Configuration
    include_code_snippets: bool = Field(
        default=True,
        metadata={
            "description": "Whether to include code snippets in the analysis report"
        }
    )
    include_risk_assessment: bool = Field(
        default=True,
        metadata={
            "description": "Whether to include risk assessment in the report"
        }
    )
    include_recommendations: bool = Field(
        default=True,
        metadata={
            "description": "Whether to include recommendations in the report"
        }
    )
    report_format: str = Field(
        default="markdown",
        metadata={
            "description": "Output format for analysis reports (markdown, json, html)"
        }
    )
    
    # General Configuration
    max_structured_output_retries: int = Field(
        default=3,
        metadata={
            "description": "Maximum number of retries for structured output calls"
        }
    )
    enable_caching: bool = Field(
        default=True,
        metadata={
            "description": "Whether to enable caching of analysis results"
        }
    )
    cache_ttl_hours: int = Field(
        default=24,
        metadata={
            "description": "Time-to-live for cached analysis results in hours"
        }
    )
    
    @classmethod
    def from_runnable_config(
        cls, config: Optional[RunnableConfig] = None
    ) -> "PRAnalysisConfiguration":
        """Create a PRAnalysisConfiguration instance from a RunnableConfig."""
        configurable = config.get("configurable", {}) if config else {}
        field_names = list(cls.model_fields.keys())
        values: dict[str, Any] = {
            field_name: os.environ.get(field_name.upper(), configurable.get(field_name))
            for field_name in field_names
        }
        
        # Handle GitHub token from environment
        if not values.get("github_token"):
            values["github_token"] = os.environ.get("GITHUB_TOKEN")
        
        return cls(**{k: v for k, v in values.items() if v is not None})
    
    def get_model_config(self, agent_type: str) -> dict[str, Any]:
        """Get model configuration for a specific agent type."""
        model_configs = {
            "pr_supervisor": {
                "model": self.pr_supervisor_model,
                "max_tokens": self.pr_supervisor_model_max_tokens
            },
            "repository_analyzer": {
                "model": self.repository_analyzer_model,
                "max_tokens": self.repository_analyzer_model_max_tokens
            },
            "diff_analyzer": {
                "model": self.diff_analyzer_model,
                "max_tokens": self.diff_analyzer_model_max_tokens
            },
            "context_gatherer": {
                "model": self.context_gatherer_model,
                "max_tokens": self.context_gatherer_model_max_tokens
            },
            "report_generator": {
                "model": self.report_generator_model,
                "max_tokens": self.report_generator_model_max_tokens
            }
        }
        
        return model_configs.get(agent_type, {
            "model": "openai:gpt-4.1-mini",
            "max_tokens": 8192
        })
    
    class Config:
        arbitrary_types_allowed = True