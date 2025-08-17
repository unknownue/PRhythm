"""Configuration management for PRhythm agents."""

import os
from enum import Enum
from typing import Any, Dict, List, Optional

from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field


class LogLevel(Enum):
    """Log level enumeration."""
    
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class AgentConfiguration(BaseModel):
    """Main configuration class for PRhythm agents."""
    
    # General Configuration
    max_structured_output_retries: int = Field(
        default=3,
        description="Maximum number of retries for structured output calls"
    )
    
    max_git_command_retries: int = Field(
        default=2,
        description="Maximum number of retries for git command execution"
    )
    
    git_command_timeout_seconds: int = Field(
        default=60,
        description="Timeout for git command execution in seconds"
    )
    
    # Agent Configuration
    scheme_selector_model: str = Field(
        default="ollama:hopephoto/Qwen3-4B-Instruct-2507_q8:latest",
        description="Model for scheme selection agent"
    )
    
    scheme_selector_max_tokens: int = Field(
        default=2000,
        description="Maximum output tokens for scheme selector"
    )
    
    data_collector_model: str = Field(
        default="ollama:hopephoto/Qwen3-4B-Instruct-2507_q8:latest",
        description="Model for data collection agents"
    )
    
    data_collector_max_tokens: int = Field(
        default=4000,
        description="Maximum output tokens for data collectors"
    )
    
    analysis_model: str = Field(
        default="ollama:hopephoto/Qwen3-4B-Instruct-2507_q8:latest",
        description="Model for main PR analysis"
    )
    
    analysis_max_tokens: int = Field(
        default=8000,
        description="Maximum output tokens for analysis model"
    )
    
    report_processor_model: str = Field(
        default="ollama:hopephoto/Qwen3-4B-Instruct-2507_q8:latest",
        description="Model for report processing"
    )
    
    report_processor_max_tokens: int = Field(
        default=4000,
        description="Maximum output tokens for report processor"
    )
    
    # Workspace Configuration
    workspace_base_path: str = Field(
        default="./workspaces",
        description="Base directory for all workspace operations"
    )
    
    cleanup_temp_after_hours: int = Field(
        default=24,
        description="Hours after which to cleanup temporary files"
    )
    
    max_concurrent_agents: int = Field(
        default=2,
        description="Maximum number of agents running concurrently"
    )
    
    # GitHub Configuration
    github_api_timeout_seconds: int = Field(
        default=30,
        description="Timeout for GitHub API requests"
    )
    
    github_api_retry_attempts: int = Field(
        default=3,
        description="Number of retry attempts for GitHub API"
    )
    
    # Logging and Monitoring
    log_level: LogLevel = Field(
        default=LogLevel.INFO,
        description="Logging level"
    )
    
    enable_debug_logs: bool = Field(
        default=False,
        description="Enable detailed debug logging"
    )
    
    log_git_commands: bool = Field(
        default=True,
        description="Log all git command executions"
    )
    
    # Analysis Configuration
    max_file_size_mb: int = Field(
        default=10,
        description="Maximum file size to analyze in MB"
    )
    
    max_diff_lines: int = Field(
        default=5000,
        description="Maximum number of diff lines to process"
    )
    
    include_binary_files: bool = Field(
        default=False,
        description="Whether to include binary files in analysis"
    )
    
    # Scheme Configuration
    default_scheme_name: str = Field(
        default="general_review",
        description="Default analysis scheme to use"
    )
    
    scheme_selection_confidence_threshold: float = Field(
        default=0.7,
        description="Minimum confidence score for scheme selection"
    )
    
    enable_custom_schemes: bool = Field(
        default=True,
        description="Enable repository-specific custom schemes"
    )
    
    # Ollama Server Configuration
    ollama_server_base_url: Optional[str] = Field(
        default="http://192.168.50.209:8090",
        description="Base URL for Ollama server (e.g., http://localhost:11434)"
    )
    
    ollama_server_api_key: Optional[str] = Field(
        default="",
        description="API key for Ollama server authentication"
    )
    
    ollama_server_model: Optional[str] = Field(
        default="hopephoto/Qwen3-4B-Instruct-2507_q8:latest",
        description="Model name for Ollama server"
    )

    @classmethod
    def from_runnable_config(
        cls, config: Optional[RunnableConfig] = None
    ) -> "AgentConfiguration":
        """Create an AgentConfiguration instance from a RunnableConfig."""
        configurable = config.get("configurable", {}) if config else {}
        field_names = list(cls.model_fields.keys())
        
        # Get values from environment variables or configurable dict
        values: Dict[str, Any] = {}
        for field_name in field_names:
            # Special handling for Ollama server configuration with PUB_ prefix
            if field_name.startswith("ollama_server_"):
                env_var_name = f"PUB_{field_name.upper()}"
            else:
                env_var_name = field_name.upper()
            
            env_value = os.environ.get(env_var_name)
            config_value = configurable.get(field_name)
            
            # Prioritize config values over environment variables
            if config_value is not None:
                values[field_name] = config_value
            elif env_value is not None:
                # Handle enum types
                if field_name == "log_level":
                    try:
                        values[field_name] = LogLevel(env_value)
                    except ValueError:
                        pass  # Use default
                else:
                    values[field_name] = env_value
        
        return cls(**{k: v for k, v in values.items() if v is not None})

    def get_workspace_paths(self, repository_name: str) -> Dict[str, str]:
        """Get workspace paths for a specific repository."""
        base_path = os.path.join(self.workspace_base_path, repository_name)
        
        return {
            "base": base_path,
            "repo_previous": os.path.join(base_path, "repo-previous"),
            "repo_merged": os.path.join(base_path, "repo-merged"),
            "reports": os.path.join(base_path, "reports"),
            "temp": os.path.join(base_path, "temp"),
            "metadata": os.path.join(base_path, "metadata")
        }

    def get_api_key_for_model(self, model_name: str, config: Optional[RunnableConfig] = None) -> Optional[str]:
        """Get API key for a specific model."""
        model_name_lower = model_name.lower()
        
        # Check if we should get from config
        should_get_from_config = os.getenv("GET_API_KEYS_FROM_CONFIG", "false").lower() == "true"
        
        if should_get_from_config and config:
            api_keys = config.get("configurable", {}).get("apiKeys", {})
            if model_name_lower.startswith("openai:"):
                return api_keys.get("OPENAI_API_KEY")
            elif model_name_lower.startswith("anthropic:"):
                return api_keys.get("ANTHROPIC_API_KEY")
            elif model_name_lower.startswith(("google:", "gemini:")):
                return api_keys.get("GOOGLE_API_KEY")
            elif model_name_lower.startswith("ollama:"):
                return api_keys.get("OLLAMA_SERVER_API_KEY", "")
        else:
            # Get from environment variables with PUB_ prefix
            if model_name_lower.startswith("openai:"):
                return os.getenv("PUB_OPENAI_API_KEY")
            elif model_name_lower.startswith("anthropic:"):
                return os.getenv("PUB_ANTHROPIC_API_KEY")
            elif model_name_lower.startswith(("google:", "gemini:")):
                return os.getenv("PUB_GOOGLE_API_KEY")
            elif model_name_lower.startswith("ollama:"):
                return os.getenv("PUB_OLLAMA_SERVER_API_KEY", "")  # Default to empty string for Ollama
        
        return None

    def get_ollama_server_config(self) -> Dict[str, Optional[str]]:
        """Get Ollama server configuration."""
        return {
            "base_url": self.ollama_server_base_url,
            "api_key": self.ollama_server_api_key,
            "model": self.ollama_server_model
        }

    class Config:
        """Pydantic configuration."""
        arbitrary_types_allowed = True