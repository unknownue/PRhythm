# PRhythm - GitHub PR Analysis Tool

A sophisticated multi-agent system for analyzing GitHub Pull Requests using LangChain and LangGraph.

## 🎯 Overview

PRhythm uses specialized AI agents to provide comprehensive analysis of GitHub Pull Requests, helping developers and reviewers understand:

- **Repository Context**: Understanding the codebase structure and technologies
- **Change Impact**: Analyzing what was changed and potential implications  
- **Risk Assessment**: Identifying potential risks and breaking changes
- **Code Context**: Gathering relevant files and dependencies
- **Actionable Recommendations**: Specific guidance for reviewers

## 🏗️ Architecture

### Multi-Agent System

```
PR Analysis Request
    ↓
┌─────────────────┐
│ PR Supervisor   │ ← Orchestrates the workflow
└─────────────────┘
    ↓
┌─────────────────┬─────────────────┐
│ Repository      │ Diff Analyzer   │ ← Parallel analysis
│ Analyzer        │                 │
└─────────────────┴─────────────────┘
    ↓
┌─────────────────┐
│ Context         │ ← Gathers relevant code
│ Gatherer        │
└─────────────────┘
    ↓
┌─────────────────┐
│ Report          │ ← Synthesizes findings
│ Generator       │
└─────────────────┘
    ↓
Comprehensive Analysis Report
```

### Agent Roles

1. **PR Supervisor**: Orchestrates the analysis workflow and coordinates between agents
2. **Repository Analyzer**: Understands repository structure, technologies, and architecture
3. **Diff Analyzer**: Analyzes specific changes made in the PR
4. **Context Gatherer**: Collects relevant code context and dependencies
5. **Report Generator**: Synthesizes all findings into a comprehensive report

## 🚀 Quick Start

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd PRhythm

# Install dependencies
uv pip install -r pyproject.toml

# Set up environment variables
export GITHUB_TOKEN="your_github_token_here"
```

### Basic Usage

```python
import asyncio
from src.pr_analysis import analyze_pr

async def main():
    result = await analyze_pr(
        repository_url="https://github.com/owner/repo",
        pr_number=123,
        analysis_depth="standard"
    )
    
    print(result.analysis_report)

asyncio.run(main())
```

### Command Line Interface

```bash
# Basic analysis
python -m src.pr_analysis.cli https://github.com/owner/repo 123

# Deep analysis with output file
python -m src.pr_analysis.cli https://github.com/owner/repo 123 \
  --depth deep --output analysis_report.md

# Quick analysis for CI/CD
python -m src.pr_analysis.cli https://github.com/owner/repo 123 \
  --depth quick --format json --no-context
```

## 📖 Usage Examples

### Example 1: Basic Analysis

```python
import asyncio
from src.pr_analysis import analyze_pr, AnalysisDepth, MockLLMMode

async def analyze_typescript_pr():
    result = await analyze_pr(
        repository_url="https://github.com/microsoft/TypeScript",
        pr_number=50000,
        analysis_depth="standard",
        config={
            "configurable": {
                "mock_llm_mode": MockLLMMode.REALISTIC,  # For demo
                "github_token": "your_token_here"
            }
        }
    )
    
    # Parse the report
    import json
    report = json.loads(result.analysis_report)
    
    print("Executive Summary:", report["executive_summary"])
    print("Risk Level:", report["risk_assessment"])
    print("Recommendations:", report["recommendations"])

asyncio.run(analyze_typescript_pr())
```

### Example 2: Custom Configuration

```python
from src.pr_analysis import PRAnalysisConfiguration, AnalysisDepth, MockLLMMode

# Create custom configuration
config = PRAnalysisConfiguration(
    # Analysis settings
    default_analysis_depth=AnalysisDepth.DEEP,
    max_context_files=20,
    include_code_snippets=True,
    include_risk_assessment=True,
    
    # Development settings
    mock_llm_mode=MockLLMMode.DISABLED,  # Use real LLMs
    
    # Model assignments
    pr_supervisor_model="openai:gpt-4",
    repository_analyzer_model="openai:gpt-4-mini",
    diff_analyzer_model="openai:gpt-4",
    report_generator_model="openai:gpt-4"
)

# Use with analysis
result = await analyze_pr(
    repository_url="https://github.com/owner/repo",
    pr_number=123,
    config={"configurable": config.model_dump()}
)
```

## 🔧 Configuration

### Analysis Depth Options

- **`quick`**: High-level analysis, minimal context gathering
- **`standard`**: Comprehensive analysis with moderate context
- **`deep`**: Thorough analysis including security and performance implications

### Mock LLM Modes (for Development)

- **`disabled`**: Use real LLM API calls
- **`simple`**: Basic mock responses for testing
- **`realistic`**: Detailed mock responses that simulate real analysis
- **`mixed`**: Random mix of real and mock responses

### Key Configuration Options

```python
PRAnalysisConfiguration(
    # GitHub API
    github_token="your_token",
    
    # Analysis behavior
    max_context_files=20,
    max_file_size_kb=100,
    include_code_snippets=True,
    include_risk_assessment=True,
    
    # Storage paths
    repo_storage_path="./data/repos",
    analysis_cache_path="./data/analysis",
    report_output_path="./reports",
    
    # Model configuration
    pr_supervisor_model="openai:gpt-4",
    repository_analyzer_model="openai:gpt-4-mini",
    # ... other model assignments
)
```

## 📊 Analysis Report Structure

The generated reports include:

### Executive Summary
- High-level overview of the PR and its significance
- Key findings and overall assessment

### Repository Overview  
- Understanding of the codebase and its purpose
- Technologies and architectural patterns identified

### Changes Summary
- Detailed analysis of what was changed
- Types of changes (feature, bugfix, refactor, etc.)

### Impact Analysis
- Components and systems affected
- Potential ripple effects and dependencies

### Risk Assessment
- Risk level (Low/Medium/High)
- Potential breaking changes
- Security and performance implications

### Recommendations
- Specific actions for reviewers
- Testing strategies
- Areas requiring special attention

### Technical Details
- Metrics and statistics
- File change summaries  
- Configuration impacts

## 🔍 Features

### GitHub Integration
- ✅ Full GitHub API integration with rate limiting
- ✅ Support for private and public repositories
- ✅ Comprehensive PR data extraction (diffs, commits, files)
- ✅ Repository context analysis (languages, structure, dependencies)

### Multi-Agent Analysis
- ✅ Specialized agents for different analysis aspects
- ✅ Parallel processing where possible for performance
- ✅ Coordinated workflow with supervisor agent
- ✅ Robust error handling and fallback mechanisms

### Flexible Configuration
- ✅ Multiple analysis depth options
- ✅ Configurable model assignments
- ✅ Mock LLM support for development and testing
- ✅ Extensive customization options

### Output Formats
- ✅ Markdown reports (default)
- ✅ JSON output for programmatic use
- ✅ HTML reports for web viewing
- ✅ Command-line interface

### Development Features
- ✅ Mock LLM service for testing without API costs
- ✅ Comprehensive test coverage
- ✅ Detailed logging and debugging support
- ✅ Modular architecture for easy extension

## 🛠️ Development

### Project Structure

```
src/pr_analysis/
├── __init__.py              # Main API exports
├── pr_analyzer.py           # Main workflow orchestration
├── configuration.py         # Configuration management
├── state.py                 # State models for LangGraph
├── mock_llm.py             # Mock LLM service for development
├── cli.py                  # Command-line interface
├── github/                 # GitHub integration
│   ├── client.py           # GitHub API client
│   ├── models.py           # Data models
│   └── tools.py            # LangChain tools
└── agents/                 # Specialized agents
    ├── supervisor.py       # PR supervisor agent
    ├── repository_analyzer.py
    ├── diff_analyzer.py
    ├── context_gatherer.py
    └── report_generator.py
```

### Adding New Agents

1. Create agent file in `src/pr_analysis/agents/`
2. Define agent function and tools processing
3. Add state models to `state.py`
4. Integrate into main workflow in `pr_analyzer.py`

### Testing

```bash
# Run with mock LLM (no API costs)
python example_pr_analysis.py

# Test CLI interface
python -m src.pr_analysis.cli https://github.com/owner/repo 123 --mock realistic

# Run existing tests
python tests/run_test.py --agent pr_analysis
```

## 🔒 Security & Privacy

- **API Keys**: Store GitHub tokens securely using environment variables
- **Rate Limiting**: Built-in GitHub API rate limiting to respect quotas
- **Data Privacy**: No code content is stored permanently; only temporary analysis cache
- **Access Control**: Respects repository permissions through GitHub API

## 🤝 Integration with Existing Framework

The PR analysis system is built on top of the existing Open Deep Research framework:

- **Extends Configuration**: Builds upon existing configuration patterns
- **Reuses Utilities**: Leverages existing HTTP client and utility functions
- **Compatible Models**: Works with the same LLM model configuration system
- **Shared Dependencies**: Uses the same core dependencies (LangChain, LangGraph)

### Migration from Legacy System

The legacy multi-agent system in `src/legacy/multi_agent.py` provides patterns that were adapted for PR analysis:

- Supervisor-researcher coordination model
- Parallel agent execution
- Tool-based LLM interactions
- State management with LangGraph

## 📈 Performance

- **Parallel Processing**: Repository and diff analysis run concurrently
- **Caching**: Analysis results can be cached to avoid repeated work
- **Rate Limiting**: Efficient GitHub API usage with built-in rate limiting
- **Mock Mode**: Fast development and testing without API calls

## 🐛 Troubleshooting

### Common Issues

1. **GitHub API Rate Limits**
   ```
   Error: GitHub API rate limit exceeded
   Solution: Check your rate limit status, use authentication token
   ```

2. **Missing GitHub Token**
   ```
   Error: GitHub token is required
   Solution: Set GITHUB_TOKEN environment variable
   ```

3. **Repository Not Found**
   ```
   Error: Resource not found
   Solution: Verify repository URL and access permissions
   ```

### Debug Mode

```bash
# Enable verbose output
python -m src.pr_analysis.cli https://github.com/owner/repo 123 --verbose

# Use mock mode for testing
python -m src.pr_analysis.cli https://github.com/owner/repo 123 --mock realistic
```

## 🗺️ Roadmap

### Phase 1 (Current) ✅
- [x] Core multi-agent framework
- [x] GitHub API integration
- [x] Basic analysis capabilities
- [x] Mock LLM for development
- [x] CLI interface

### Phase 2 (Planned)
- [ ] Advanced code context analysis
- [ ] Security vulnerability detection
- [ ] Performance impact assessment
- [ ] Integration with CI/CD systems

### Phase 3 (Future)
- [ ] Web interface
- [ ] GitHub App integration
- [ ] Advanced metrics and analytics
- [ ] Team collaboration features

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙋 Support

For questions, issues, or contributions:

1. Check the existing issues in the repository
2. Create a new issue with detailed description
3. Include steps to reproduce for bugs
4. Provide example repository and PR number for analysis issues

---

**Built with ❤️ using LangChain, LangGraph, and the power of multi-agent AI systems.**