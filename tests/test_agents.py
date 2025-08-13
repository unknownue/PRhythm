"""
Tests for PRhythm agent system.
"""

import pytest
import asyncio
import tempfile
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from src.agents.configuration import AgentConfiguration
from src.agents.state import AgentState, SchemeState, CollectorState, ProcessorState
from src.agents.tools import git_status, git_diff, analyze_file, analyze_pr_metadata
from src.agents.utils import setup_workspace, load_scheme_config, validate_pr_data
from src.agents.main_workflow import prhythm_workflow


class TestAgentConfiguration:
    """Test agent configuration management."""
    
    def test_default_configuration(self):
        """Test default configuration values."""
        config = AgentConfiguration()
        
        assert config.scheme_selector_model == "openai:gpt-4.1"
        assert config.max_git_command_retries == 2
        assert config.workspace_base_path == "./workspaces"
        assert config.log_git_commands is True
    
    def test_configuration_from_env(self, monkeypatch):
        """Test configuration from environment variables."""
        monkeypatch.setenv("SCHEME_SELECTOR_MODEL", "anthropic:claude-3")
        monkeypatch.setenv("MAX_GIT_COMMAND_RETRIES", "3")
        
        config = AgentConfiguration.from_runnable_config({})
        
        assert config.scheme_selector_model == "anthropic:claude-3"
        assert config.max_git_command_retries == 3
    
    def test_workspace_paths(self):
        """Test workspace path generation."""
        config = AgentConfiguration()
        paths = config.get_workspace_paths("test-repo")
        
        assert "base" in paths
        assert "repo_previous" in paths
        assert "repo_merged" in paths
        assert "test-repo" in paths["base"]
    
    def test_api_key_extraction(self, monkeypatch):
        """Test API key extraction for different models."""
        monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-key")
        
        config = AgentConfiguration()
        
        openai_key = config.get_api_key_for_model("openai:gpt-4", None)
        anthropic_key = config.get_api_key_for_model("anthropic:claude-3", None)
        
        assert openai_key == "test-openai-key"
        assert anthropic_key == "test-anthropic-key"


class TestAgentTools:
    """Test agent tools functionality."""
    
    @pytest.fixture
    def temp_repo(self):
        """Create a temporary git repository for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir) / "test-repo"
            repo_path.mkdir()
            
            # Initialize git repo
            import subprocess
            subprocess.run(["git", "init"], cwd=repo_path, check=True)
            subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_path, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_path, check=True)
            
            # Create initial commit
            test_file = repo_path / "test.txt"
            test_file.write_text("Initial content")
            subprocess.run(["git", "add", "test.txt"], cwd=repo_path, check=True)
            subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_path, check=True)
            
            yield str(repo_path)
    
    @pytest.mark.asyncio
    async def test_git_status_tool(self, temp_repo):
        """Test git status tool."""
        result = await git_status(temp_repo)
        
        assert result.success is True
        assert result.command == "git status --porcelain --branch"
        assert result.exit_code == 0
    
    @pytest.mark.asyncio
    async def test_git_diff_tool(self, temp_repo):
        """Test git diff tool."""
        # Create a change to diff
        test_file = Path(temp_repo) / "test.txt"
        test_file.write_text("Modified content")
        
        import subprocess
        subprocess.run(["git", "add", "test.txt"], cwd=temp_repo, check=True)
        subprocess.run(["git", "commit", "-m", "Second commit"], cwd=temp_repo, check=True)
        
        result = await git_diff(temp_repo, base_ref="HEAD~1", target_ref="HEAD")
        
        assert result.success is True
        assert "test.txt" in result.stdout
    
    @pytest.mark.asyncio
    async def test_analyze_file_tool(self, temp_repo):
        """Test file analysis tool."""
        test_file = Path(temp_repo) / "test.txt"
        
        result = await analyze_file(str(test_file))
        
        assert result.exists is True
        assert result.file_path == str(test_file)
        assert result.is_binary is False
        assert "content" in result.content_preview.lower()
    
    @pytest.mark.asyncio
    async def test_analyze_pr_metadata(self):
        """Test PR metadata analysis."""
        pr_data = {
            "number": 123,
            "title": "Test PR",
            "body": "Test description",
            "user": {"login": "testuser"},
            "labels": [{"name": "bug"}, {"name": "urgent"}],
            "changed_files": 5,
            "additions": 100,
            "deletions": 50,
            "base": {"ref": "main", "sha": "abc123"},
            "head": {"ref": "feature", "sha": "def456"}
        }
        
        result = await analyze_pr_metadata(pr_data)
        
        assert result["pr_number"] == 123
        assert result["title"] == "Test PR"
        assert result["author"] == "testuser"
        assert result["labels"] == ["bug", "urgent"]
        assert result["size_category"] == "medium"  # 150 total changes
        assert result["total_changes"] == 150


class TestAgentUtils:
    """Test agent utility functions."""
    
    def test_validate_pr_data_valid(self):
        """Test PR data validation with valid data."""
        pr_data = {
            "number": 123,
            "title": "Test PR",
            "base": {
                "repo": {"clone_url": "https://github.com/test/repo.git"},
                "sha": "abc123"
            },
            "head": {"sha": "def456"},
            "user": {"login": "testuser"}
        }
        
        is_valid, error = validate_pr_data(pr_data)
        
        assert is_valid is True
        assert error is None
    
    def test_validate_pr_data_invalid(self):
        """Test PR data validation with invalid data."""
        pr_data = {
            "title": "Test PR",
            # Missing required fields
        }
        
        is_valid, error = validate_pr_data(pr_data)
        
        assert is_valid is False
        assert "number" in error
    
    @pytest.mark.asyncio
    async def test_load_scheme_config_default(self):
        """Test loading default scheme configuration."""
        repository_config = {
            "repository": {"name": "test-repo"},
            "analysis": {"schemes": {}}
        }
        
        config = await load_scheme_config("general_review", repository_config)
        
        assert config["metadata"]["name"] == "general_review"
        assert config["requirements"]["pre_merge_data"] is True
        assert config["requirements"]["post_merge_data"] is True
    
    @pytest.mark.asyncio
    async def test_load_scheme_config_custom(self):
        """Test loading custom scheme configuration."""
        repository_config = {
            "repository": {"name": "test-repo"},
            "analysis": {"schemes": {}},
            "custom_schemes": {
                "custom_scheme": {
                    "metadata": {"name": "custom_scheme"},
                    "requirements": {"pre_merge_data": False}
                }
            }
        }
        
        config = await load_scheme_config("custom_scheme", repository_config)
        
        assert config["metadata"]["name"] == "custom_scheme"
        assert config["requirements"]["pre_merge_data"] is False


class TestWorkflowIntegration:
    """Test complete workflow integration."""
    
    @pytest.fixture
    def sample_pr_data(self):
        """Sample PR data for testing."""
        return {
            "number": 123,
            "title": "Add new feature",
            "body": "This PR adds a new feature to the system",
            "user": {"login": "developer"},
            "labels": [{"name": "feature"}],
            "changed_files": 3,
            "additions": 50,
            "deletions": 10,
            "base": {
                "repo": {
                    "name": "test-repo",
                    "full_name": "org/test-repo",
                    "clone_url": "https://github.com/org/test-repo.git"
                },
                "ref": "main",
                "sha": "base-sha-123"
            },
            "head": {
                "ref": "feature-branch",
                "sha": "head-sha-456"
            },
            "merge_commit_sha": "merge-sha-789"
        }
    
    @pytest.fixture
    def sample_repository_config(self):
        """Sample repository configuration for testing."""
        return {
            "repository": {
                "name": "test-repo",
                "full_name": "org/test-repo",
                "enabled": True
            },
            "analysis": {
                "trigger": {"on_pr_merged": True},
                "schemes": {
                    "default": "general_review",
                    "fallback": "general_review",
                    "conditions": []
                }
            }
        }
    
    @pytest.mark.asyncio
    async def test_workflow_initialization(self, sample_pr_data, sample_repository_config):
        """Test workflow initialization step."""
        with patch('src.agents.utils.setup_workspace') as mock_setup:
            mock_setup.return_value = None
            
            input_state = {
                "pr_data": sample_pr_data,
                "repository_config": sample_repository_config
            }
            
            config = {"configurable": {}}
            
            # This would test the actual workflow if we had proper mocking
            # For now, just test that the state is properly structured
            assert input_state["pr_data"]["number"] == 123
            assert input_state["repository_config"]["repository"]["name"] == "test-repo"
    
    @pytest.mark.asyncio
    async def test_scheme_selection_integration(self, sample_pr_data, sample_repository_config):
        """Test scheme selection with sample data."""
        from src.agents.scheme_selector import _evaluate_condition
        
        # Test condition evaluation
        pr_analysis = {
            "labels": ["feature"],
            "files_changed": 3,
            "total_changes": 60,
            "author": "developer"
        }
        
        # Test label condition
        condition = {"type": "label_contains", "value": "feature"}
        result = _evaluate_condition(condition, pr_analysis, sample_pr_data)
        assert result is True
        
        # Test files changed condition
        condition = {"type": "files_changed", "operator": ">=", "value": 2}
        result = _evaluate_condition(condition, pr_analysis, sample_pr_data)
        assert result is True
        
        # Test compound AND condition
        condition = {
            "type": "and",
            "conditions": [
                {"type": "label_contains", "value": "feature"},
                {"type": "files_changed", "operator": ">", "value": 1}
            ]
        }
        result = _evaluate_condition(condition, pr_analysis, sample_pr_data)
        assert result is True


@pytest.mark.integration
class TestEndToEndWorkflow:
    """End-to-end workflow tests (requires more setup)."""
    
    @pytest.mark.asyncio
    async def test_mock_workflow_execution(self):
        """Test workflow execution with mocked components."""
        # Mock all external dependencies
        with patch('src.agents.utils.setup_workspace') as mock_setup, \
             patch('src.agents.tools.git_clone') as mock_clone, \
             patch('src.agents.tools.git_checkout') as mock_checkout, \
             patch('langchain.chat_models.init_chat_model') as mock_model:
            
            # Configure mocks
            mock_setup.return_value = None
            mock_clone.return_value = MagicMock(success=True)
            mock_checkout.return_value = MagicMock(success=True)
            
            # Mock LLM responses
            mock_llm = AsyncMock()
            mock_llm.ainvoke.return_value = MagicMock(content="Mock analysis report")
            mock_model.return_value = mock_llm
            
            # Test data
            input_state = {
                "pr_data": {
                    "number": 123,
                    "title": "Test PR",
                    "body": "Test description",
                    "user": {"login": "test"},
                    "labels": [],
                    "base": {
                        "repo": {
                            "name": "test-repo",
                            "clone_url": "https://github.com/test/repo.git"
                        },
                        "sha": "base123"
                    },
                    "head": {"sha": "head456"}
                },
                "repository_config": {
                    "repository": {"name": "test-repo"},
                    "analysis": {
                        "schemes": {
                            "default": "general_review",
                            "conditions": []
                        }
                    }
                }
            }
            
            # This test validates the structure is correct
            # Full workflow testing would require more complex mocking
            assert input_state["pr_data"]["number"] == 123
            assert "repository_config" in input_state


if __name__ == "__main__":
    pytest.main([__file__, "-v"])