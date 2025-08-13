"""
Tests for PRhythm agent tools.
"""

import pytest
import asyncio
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.agents.tools import (
    git_status, git_diff, git_log, git_checkout, git_show, git_changed_files, git_clone,
    analyze_file, analyze_directory, find_files, analyze_pr_metadata,
    GitCommandResult, FileAnalysisResult, DirectoryInfo
)


class TestGitTools:
    """Test git-related tools."""
    
    @pytest.mark.asyncio
    @pytest.mark.requires_git
    async def test_git_status_success(self, sample_git_repo):
        """Test successful git status execution."""
        result = await git_status(sample_git_repo)
        
        assert isinstance(result, GitCommandResult)
        assert result.success is True
        assert result.exit_code == 0
        assert "git status" in result.command
        assert result.execution_time_seconds > 0
    
    @pytest.mark.asyncio
    async def test_git_status_invalid_repo(self):
        """Test git status on invalid repository."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Non-git directory
            result = await git_status(temp_dir)
            
            assert result.success is False
            assert result.exit_code != 0
            assert "not a git repository" in result.stderr.lower() or result.exit_code != 0
    
    @pytest.mark.asyncio
    @pytest.mark.requires_git
    async def test_git_diff(self, sample_git_repo):
        """Test git diff functionality."""
        result = await git_diff(
            repo_path=sample_git_repo,
            base_ref="HEAD~2",  # Before merge
            target_ref="HEAD~1",  # After merge
            include_stats=True
        )
        
        assert isinstance(result, GitCommandResult)
        assert result.success is True
        # Should show changes from the merge
    
    @pytest.mark.asyncio
    @pytest.mark.requires_git
    async def test_git_log(self, sample_git_repo):
        """Test git log functionality."""
        result = await git_log(
            repo_path=sample_git_repo,
            max_count=3,
            format_string="oneline"
        )
        
        assert result.success is True
        assert result.stdout.strip()  # Should have commit output
        lines = result.stdout.strip().split('\n')
        assert len(lines) <= 3  # Respects max_count
    
    @pytest.mark.asyncio
    @pytest.mark.requires_git 
    async def test_git_checkout(self, sample_git_repo):
        """Test git checkout functionality."""
        # First, get the main branch commit
        log_result = await git_log(sample_git_repo, max_count=2)
        commits = log_result.stdout.strip().split('\n')
        if len(commits) >= 2:
            # Get commit hash from second commit
            commit_hash = commits[1].split()[0]
            
            result = await git_checkout(
                repo_path=sample_git_repo,
                ref=commit_hash,
                force=True
            )
            
            assert result.success is True
            assert "HEAD is now at" in result.stdout or result.exit_code == 0
    
    @pytest.mark.asyncio
    @pytest.mark.requires_git
    async def test_git_show(self, sample_git_repo):
        """Test git show functionality."""
        result = await git_show(
            repo_path=sample_git_repo,
            ref="HEAD",
            show_stats=True
        )
        
        assert result.success is True
        assert result.stdout.strip()  # Should have commit details
    
    @pytest.mark.asyncio
    @pytest.mark.requires_git
    async def test_git_changed_files(self, sample_git_repo):
        """Test getting changed files."""
        result = await git_changed_files(
            repo_path=sample_git_repo,
            base_ref="HEAD~2",
            target_ref="HEAD"
        )
        
        assert result.success is True
        # Should list changed files
    
    @pytest.mark.asyncio
    async def test_git_clone_mock(self):
        """Test git clone with mocked subprocess."""
        with patch('asyncio.create_subprocess_shell') as mock_subprocess:
            # Mock successful clone
            mock_process = MagicMock()
            mock_process.communicate.return_value = asyncio.coroutine(lambda: (b'', b''))()
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process
            
            result = await git_clone(
                repo_url="https://github.com/test/repo.git",
                target_path="/tmp/test-repo"
            )
            
            assert result.success is True
            mock_subprocess.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_git_command_timeout(self):
        """Test git command timeout handling."""
        with patch('asyncio.create_subprocess_shell') as mock_subprocess:
            # Mock process that hangs
            mock_process = MagicMock()
            mock_process.communicate.side_effect = asyncio.TimeoutError()
            mock_process.kill = MagicMock()
            mock_process.wait.return_value = asyncio.coroutine(lambda: 0)()
            mock_subprocess.return_value = mock_process
            
            with tempfile.TemporaryDirectory() as temp_dir:
                result = await git_status(temp_dir, config={"configurable": {"git_command_timeout_seconds": 1}})
                
                assert result.success is False
                assert "timed out" in result.stderr.lower()


class TestFileSystemTools:
    """Test file system analysis tools."""
    
    @pytest.mark.asyncio
    async def test_analyze_file_existing(self, temp_workspace):
        """Test analyzing an existing file."""
        # Create test file
        test_file = Path(temp_workspace) / "test.py"
        test_content = "def hello():\n    print('Hello, World!')\n"
        test_file.write_text(test_content)
        
        result = await analyze_file(
            str(test_file),
            include_preview=True,
            max_preview_chars=50
        )
        
        assert isinstance(result, FileAnalysisResult)
        assert result.exists is True
        assert result.file_path == str(test_file)
        assert result.is_binary is False
        assert result.size_bytes == len(test_content)
        assert "def hello" in result.content_preview
    
    @pytest.mark.asyncio
    async def test_analyze_file_nonexistent(self):
        """Test analyzing a non-existent file."""
        result = await analyze_file("/non/existent/file.txt")
        
        assert result.exists is False
        assert result.file_path == "/non/existent/file.txt"
        assert result.size_bytes is None
        assert result.content_preview is None
    
    @pytest.mark.asyncio
    async def test_analyze_file_binary(self, temp_workspace):
        """Test analyzing a binary file."""
        # Create binary file
        binary_file = Path(temp_workspace) / "test.bin"
        binary_content = b'\x00\x01\x02\x03\x04\xFF\xFE\xFD'
        binary_file.write_bytes(binary_content)
        
        result = await analyze_file(str(binary_file))
        
        assert result.exists is True
        assert result.is_binary is True
        assert result.content_preview is None  # No preview for binary files
    
    @pytest.mark.asyncio
    async def test_analyze_directory(self, temp_workspace):
        """Test analyzing a directory."""
        workspace = Path(temp_workspace)
        
        # Create some files
        (workspace / "file1.txt").write_text("Content 1")
        (workspace / "file2.py").write_text("print('Hello')")
        (workspace / "subdir").mkdir()
        (workspace / "subdir" / "file3.md").write_text("# Title")
        
        result = await analyze_directory(
            str(workspace),
            include_files=True,
            max_files=10
        )
        
        assert isinstance(result, DirectoryInfo)
        assert result.exists is True
        assert result.file_count == 3  # Three files total
        assert result.total_size_bytes > 0
        assert len(result.files) == 3
    
    @pytest.mark.asyncio
    async def test_analyze_directory_nonexistent(self):
        """Test analyzing a non-existent directory."""
        result = await analyze_directory("/non/existent/directory")
        
        assert result.exists is False
        assert result.path == "/non/existent/directory"
    
    @pytest.mark.asyncio
    async def test_find_files(self, temp_workspace):
        """Test finding files with patterns."""
        workspace = Path(temp_workspace)
        
        # Create various files
        (workspace / "test.py").write_text("print('test')")
        (workspace / "main.py").write_text("print('main')")
        (workspace / "data.txt").write_text("data")
        (workspace / "README.md").write_text("# README")
        
        # Find Python files
        py_files = await find_files(str(workspace), pattern="*.py")
        
        assert len(py_files) == 2
        assert any("test.py" in f for f in py_files)
        assert any("main.py" in f for f in py_files)
        
        # Find all files
        all_files = await find_files(str(workspace), pattern="*")
        assert len(all_files) == 4
    
    @pytest.mark.asyncio
    async def test_find_files_with_limit(self, temp_workspace):
        """Test find_files with result limit."""
        workspace = Path(temp_workspace)
        
        # Create many files
        for i in range(10):
            (workspace / f"file{i}.txt").write_text(f"Content {i}")
        
        # Limit results to 5
        files = await find_files(str(workspace), pattern="*.txt", max_results=5)
        
        assert len(files) == 5


class TestPRAnalysisTools:
    """Test PR-specific analysis tools."""
    
    @pytest.mark.asyncio
    async def test_analyze_pr_metadata_comprehensive(self, sample_pr_data):
        """Test comprehensive PR metadata analysis."""
        result = await analyze_pr_metadata(sample_pr_data)
        
        # Check basic fields
        assert result["pr_number"] == 123
        assert result["title"] == "Add new feature implementation"
        assert result["author"] == "developer123"
        assert result["base_branch"] == "main"
        assert result["head_branch"] == "feature-new-implementation"
        
        # Check extracted labels
        assert "feature" in result["labels"]
        assert "enhancement" in result["labels"]
        
        # Check calculated fields
        assert result["files_changed"] == 3
        assert result["total_changes"] == 30  # 25 + 5
        assert result["size_category"] == "small"  # < 50 total changes
        
        # Check commits
        assert result["base_sha"] == "abc123def456789"
        assert result["head_sha"] == "def456ghi789abc"
    
    @pytest.mark.asyncio
    async def test_analyze_pr_metadata_minimal(self):
        """Test PR metadata analysis with minimal data."""
        minimal_pr = {
            "number": 456,
            "title": "Fix bug",
            "user": {"login": "fixer"},
            "labels": [],
            "changed_files": 1,
            "additions": 5,
            "deletions": 2
        }
        
        result = await analyze_pr_metadata(minimal_pr)
        
        assert result["pr_number"] == 456
        assert result["title"] == "Fix bug"
        assert result["author"] == "fixer"
        assert result["labels"] == []
        assert result["total_changes"] == 7
        assert result["size_category"] == "small"
    
    @pytest.mark.asyncio
    async def test_analyze_pr_metadata_size_categories(self):
        """Test PR size categorization."""
        test_cases = [
            ({"additions": 10, "deletions": 5}, "small"),    # 15 total
            ({"additions": 100, "deletions": 50}, "medium"), # 150 total
            ({"additions": 500, "deletions": 200}, "large"), # 700 total
            ({"additions": 800, "deletions": 300}, "xlarge") # 1100 total
        ]
        
        for changes, expected_category in test_cases:
            pr_data = {
                "number": 1,
                "title": "Test",
                "user": {"login": "test"},
                "labels": [],
                **changes
            }
            
            result = await analyze_pr_metadata(pr_data)
            assert result["size_category"] == expected_category
    
    @pytest.mark.asyncio
    async def test_analyze_pr_metadata_missing_fields(self):
        """Test PR metadata analysis with missing fields."""
        incomplete_pr = {
            "number": 789,
            "title": "Incomplete PR"
            # Missing user, labels, etc.
        }
        
        result = await analyze_pr_metadata(incomplete_pr)
        
        assert result["pr_number"] == 789
        assert result["author"] == "unknown"
        assert result["labels"] == []
        assert result["files_changed"] == 0
    
    @pytest.mark.asyncio 
    async def test_pr_age_calculation(self):
        """Test PR age calculation."""
        pr_data = {
            "number": 123,
            "title": "Test PR",
            "user": {"login": "test"},
            "labels": [],
            "created_at": "2024-01-15T10:00:00Z",
            "merged_at": "2024-01-15T14:00:00Z"  # 4 hours later
        }
        
        result = await analyze_pr_metadata(pr_data)
        
        assert "pr_age_hours" in result
        assert result["pr_age_hours"] == 4.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])