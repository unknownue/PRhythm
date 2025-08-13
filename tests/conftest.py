"""
Pytest configuration and fixtures for PRhythm tests.
"""

import pytest
import tempfile
import subprocess
from pathlib import Path


@pytest.fixture
def temp_workspace():
    """Create a temporary workspace directory for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        workspace_path = Path(temp_dir) / "test-workspace"
        workspace_path.mkdir(parents=True)
        yield str(workspace_path)


@pytest.fixture
def sample_git_repo():
    """Create a sample git repository for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        repo_path = Path(temp_dir) / "test-git-repo"
        repo_path.mkdir()
        
        # Initialize git repository
        subprocess.run(["git", "init"], cwd=repo_path, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_path, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_path, check=True)
        
        # Create initial files and commits
        (repo_path / "README.md").write_text("# Test Repository\n\nThis is a test repository.")
        (repo_path / "main.py").write_text("print('Hello, World!')\n")
        
        subprocess.run(["git", "add", "."], cwd=repo_path, check=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_path, check=True)
        
        # Create a feature branch and some changes
        subprocess.run(["git", "checkout", "-b", "feature-branch"], cwd=repo_path, check=True)
        (repo_path / "feature.py").write_text("def new_feature():\n    return 'New feature!'\n")
        (repo_path / "main.py").write_text("print('Hello, World!')\nprint('Updated!')\n")
        
        subprocess.run(["git", "add", "."], cwd=repo_path, check=True)
        subprocess.run(["git", "commit", "-m", "Add new feature"], cwd=repo_path, check=True)
        
        # Switch back to main and create merge commit
        subprocess.run(["git", "checkout", "main"], cwd=repo_path, check=True)
        subprocess.run(["git", "merge", "feature-branch", "--no-ff", "-m", "Merge feature branch"], cwd=repo_path, check=True)
        
        yield str(repo_path)


@pytest.fixture
def sample_pr_data():
    """Sample PR data for testing."""
    return {
        "number": 123,
        "title": "Add new feature implementation",
        "body": "This PR implements a new feature that improves user experience.\n\n## Changes\n- Added new feature module\n- Updated main application\n- Added tests",
        "user": {
            "login": "developer123",
            "avatar_url": "https://github.com/avatars/developer123"
        },
        "labels": [
            {"name": "feature"},
            {"name": "enhancement"}
        ],
        "assignees": [],
        "requested_reviewers": [{"login": "reviewer1"}],
        "created_at": "2024-01-15T10:30:00Z",
        "updated_at": "2024-01-15T14:20:00Z", 
        "merged_at": "2024-01-15T15:45:00Z",
        "changed_files": 3,
        "additions": 25,
        "deletions": 5,
        "base": {
            "repo": {
                "name": "test-repository",
                "full_name": "testorg/test-repository",
                "clone_url": "https://github.com/testorg/test-repository.git",
                "html_url": "https://github.com/testorg/test-repository"
            },
            "ref": "main",
            "sha": "abc123def456789"
        },
        "head": {
            "repo": {
                "name": "test-repository",
                "full_name": "testorg/test-repository"
            },
            "ref": "feature-new-implementation",
            "sha": "def456ghi789abc"
        },
        "merge_commit_sha": "ghi789abc123def"
    }


@pytest.fixture
def sample_repository_config():
    """Sample repository configuration for testing."""
    return {
        "repository": {
            "name": "test-repository",
            "full_name": "testorg/test-repository",
            "github_url": "https://github.com/testorg/test-repository",
            "clone_url": "https://github.com/testorg/test-repository.git",
            "default_branch": "main",
            "enabled": True,
            "description": "Test repository for PRhythm"
        },
        "analysis": {
            "trigger": {
                "on_pr_merged": True,
                "on_pr_closed": False,
                "specific_branches": ["main", "develop"],
                "exclude_branches": []
            },
            "schemes": {
                "default": "general_review",
                "fallback": "general_review",
                "conditions": [
                    {
                        "description": "Security review for security-labeled PRs",
                        "condition": {
                            "type": "label_contains",
                            "value": "security"
                        },
                        "scheme": "security_audit",
                        "priority": "high"
                    },
                    {
                        "description": "Performance check for large PRs",
                        "condition": {
                            "type": "and",
                            "conditions": [
                                {
                                    "type": "files_changed",
                                    "operator": ">",
                                    "value": 10
                                },
                                {
                                    "type": "lines_changed",
                                    "operator": ">",
                                    "value": 200
                                }
                            ]
                        },
                        "scheme": "performance_check",
                        "priority": "medium"
                    }
                ]
            }
        },
        "workspace": {
            "cleanup_temp_after_hours": 24
        },
        "custom_config": {
            "exclude_patterns": [
                "*.pyc",
                "__pycache__/",
                ".git/",
                "node_modules/"
            ]
        },
        "notification": {
            "enabled": True,
            "channels": ["github_comment"]
        }
    }


@pytest.fixture
def mock_llm_response():
    """Mock LLM response for testing."""
    return {
        "content": """# PR Analysis Report

## Executive Summary

This PR introduces a new feature implementation that enhances the user experience. The changes are well-structured and follow best practices.

## Code Quality Assessment

- **Code Style**: Consistent with project standards
- **Documentation**: Adequate inline comments and docstrings
- **Error Handling**: Proper exception handling implemented
- **Testing**: Unit tests included for new functionality

## Technical Impact Analysis

### Changed Files
- `main.py`: Updated main application logic
- `feature.py`: New feature module implementation
- `test_feature.py`: Comprehensive test coverage

### Performance Considerations
- No significant performance impact expected
- New feature uses efficient algorithms
- Memory usage remains within acceptable limits

## Security and Risk Assessment

- No security vulnerabilities identified
- Input validation properly implemented
- No sensitive data exposure risks

## Recommendations

1. Consider adding integration tests
2. Update documentation to reflect new feature
3. Monitor performance metrics after deployment

## Conclusion

This PR is well-implemented and ready for deployment. The code quality is high and the changes align with project standards.

**Overall Score: 8.5/10**
""",
        "metadata": {
            "model": "test-model",
            "tokens_used": 150
        }
    }


@pytest.fixture(autouse=True)
def setup_test_environment(monkeypatch):
    """Set up test environment variables."""
    # Mock API keys for testing
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-key")
    monkeypatch.setenv("GITHUB_TOKEN", "test-github-token")
    
    # Set test-specific configuration
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("ENABLE_DEBUG_LOGS", "true")


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "integration: mark test as integration test")
    config.addinivalue_line("markers", "slow: mark test as slow running")
    config.addinivalue_line("markers", "requires_git: mark test as requiring git")


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers based on test names."""
    for item in items:
        # Add integration marker to integration tests
        if "integration" in item.nodeid.lower():
            item.add_marker(pytest.mark.integration)
        
        # Add slow marker to tests that might be slow
        if any(keyword in item.name.lower() for keyword in ["workflow", "end_to_end", "full"]):
            item.add_marker(pytest.mark.slow)
        
        # Add git marker to tests that require git
        if any(keyword in item.name.lower() for keyword in ["git", "clone", "checkout", "repo"]):
            item.add_marker(pytest.mark.requires_git)