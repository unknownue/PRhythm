# PRhythm Usage Guide

PRhythm is a GitHub Pull Request analysis tool built on a multi-agent system that provides comprehensive PR analysis reports for developers and code reviewers.

## 🚀 Quick Start

### Environment Setup

1. **Install Dependencies**
```bash
# Clone the project
git clone <repository-url>
cd PRhythm

# Install dependencies
uv pip install -r pyproject.toml
```

2. **Configure GitHub Token**
```bash
# Set environment variable
export GITHUB_TOKEN="your_github_token_here"

# Or create .env file
echo "GITHUB_TOKEN=your_github_token_here" > .env
```

### Basic Usage

#### 1. Python API

```python
import asyncio
from src.pr_analysis import analyze_pr

async def main():
    # Basic analysis
    result = await analyze_pr(
        repository_url="https://github.com/owner/repo",
        pr_number=123,
        analysis_depth="standard"
    )
    
    print("Analysis Report:")
    print(result.analysis_report)

asyncio.run(main())
```

#### 2. Command Line Interface

```bash
# Basic PR analysis
python -m src.pr_analysis.cli https://github.com/owner/repo 123

# Deep analysis with output file
python -m src.pr_analysis.cli https://github.com/owner/repo 123 \
  --depth deep --output report.md

# Quick analysis for CI/CD
python -m src.pr_analysis.cli https://github.com/owner/repo 123 \
  --depth quick --format json
```

#### 3. Development Mode (Mock LLM)

```bash
# Test with mock LLM (no API costs)
python example_pr_analysis.py

# CLI with mock mode
python -m src.pr_analysis.cli https://github.com/owner/repo 123 --mock realistic
```

## 📊 Analysis Configuration

### Analysis Depths

- **`quick`**: Fast analysis suitable for CI/CD
  - High-level overview
  - Basic risk assessment  
  - Minimal context gathering

- **`standard`**: Comprehensive analysis (recommended)
  - Full code change analysis
  - Moderate context gathering
  - Detailed impact assessment

- **`deep`**: Thorough analysis
  - Most comprehensive analysis
  - Security and performance implications
  - Maximum context gathering

### Mock LLM Modes (Development)

- **`disabled`**: Use real LLM APIs
- **`simple`**: Basic mock responses
- **`realistic`**: Detailed mock responses (recommended for development)
- **`mixed`**: Random mix of real and mock responses

## 🔧 Advanced Configuration

### Custom Configuration Example

```python
from src.pr_analysis import PRAnalysisConfiguration, AnalysisDepth, MockLLMMode

# Create custom configuration
config = PRAnalysisConfiguration(
    # Analysis settings
    default_analysis_depth=AnalysisDepth.DEEP,
    max_context_files=25,
    include_code_snippets=True,
    include_risk_assessment=True,
    
    # Model assignments
    pr_supervisor_model="openai:gpt-4",
    repository_analyzer_model="openai:gpt-4-mini",
    diff_analyzer_model="openai:gpt-4",
    report_generator_model="openai:gpt-4",
    
    # Development settings
    mock_llm_mode=MockLLMMode.REALISTIC,
    
    # Storage paths
    repo_storage_path="./data/repos",
    analysis_cache_path="./data/analysis",
    report_output_path="./reports"
)

# Use custom configuration
result = await analyze_pr(
    repository_url="https://github.com/owner/repo",
    pr_number=123,
    config={"configurable": config.model_dump()}
)
```

### Command Line Options

```bash
python -m src.pr_analysis.cli [OPTIONS] REPOSITORY_URL PR_NUMBER

Arguments:
  REPOSITORY_URL    GitHub repository URL
  PR_NUMBER         Pull request number

Options:
  --depth [quick|standard|deep]     Analysis depth (default: standard)
  --format [markdown|json|html]     Output format (default: markdown)
  --output PATH                     Output file path
  --mock [simple|realistic|mixed]   Use Mock LLM mode
  --no-context                      Skip context gathering
  --verbose                         Verbose output mode
  --help                           Show help message
```

## 📋 Analysis Report Structure

Generated analysis reports include:

### 1. Executive Summary
- High-level PR overview and significance
- Key findings and overall assessment

### 2. Repository Overview
- Codebase structure and purpose understanding
- Identified technologies and architectural patterns

### 3. Changes Summary
- Detailed change analysis
- Change type classification (feature, bugfix, refactor, etc.)

### 4. Impact Analysis
- Affected components and systems
- Potential ripple effects and dependencies

### 5. Risk Assessment
- Risk level (Low/Medium/High)
- Potential breaking changes
- Security and performance implications

### 6. Recommendations
- Specific actionable advice for reviewers
- Testing strategies
- Areas requiring special attention

### 7. Technical Details
- Metrics and statistics
- File change summaries
- Configuration impacts

## 🛠️ Usage Scenarios

### Scenario 1: Daily Code Review

```python
# Standard analysis for team PRs
async def review_team_pr():
    result = await analyze_pr(
        "https://github.com/myteam/project",
        456,
        analysis_depth="standard"
    )
    
    # Parse report
    import json
    report = json.loads(result.analysis_report)
    
    # Output key information
    print(f"Risk Level: {report.get('risk_assessment', {}).get('risk_level')}")
    print(f"Recommendations: {report.get('recommendations', [])}")
```

### Scenario 2: CI/CD Integration

```bash
#!/bin/bash
# Use quick analysis in CI
python -m src.pr_analysis.cli https://github.com/owner/repo $PR_NUMBER \
  --depth quick \
  --format json \
  --output pr_analysis.json

# Check risk level
RISK_LEVEL=$(cat pr_analysis.json | jq -r '.risk_assessment.risk_level')
if [ "$RISK_LEVEL" = "high" ]; then
  echo "High risk PR detected, requiring additional review"
  exit 1
fi
```

### Scenario 3: Open Source Contribution Review

```python
# Analyze open source project contributions
config = PRAnalysisConfiguration(
    default_analysis_depth=AnalysisDepth.DEEP,
    include_risk_assessment=True,
    include_recommendations=True,
    max_context_files=30  # More context for open source projects
)

result = await analyze_pr(
    "https://github.com/popular/opensource-project",
    789,
    config={"configurable": config.model_dump()}
)
```

## 🔍 Output Formats

### Markdown Format (default)
```bash
python -m src.pr_analysis.cli https://github.com/owner/repo 123 --output report.md
```

### JSON Format (programmatic processing)
```bash
python -m src.pr_analysis.cli https://github.com/owner/repo 123 --format json --output report.json
```

### HTML Format (web viewing)
```bash
python -m src.pr_analysis.cli https://github.com/owner/repo 123 --format html --output report.html
```

## 🚨 Troubleshooting

### Common Issues

1. **GitHub API Rate Limits**
   ```
   Error: GitHub API rate limit exceeded
   Solution: Check rate limit status, use authentication token
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

4. **Model API Errors**
   ```
   Error: OpenAI API error
   Solution: Check API keys and model availability, or use Mock mode
   ```

### Debug Mode

```bash
# Enable verbose output
python -m src.pr_analysis.cli https://github.com/owner/repo 123 --verbose

# Use mock mode for testing
python -m src.pr_analysis.cli https://github.com/owner/repo 123 --mock realistic

# Check configuration
python -c "from src.pr_analysis import PRAnalysisConfiguration; print(PRAnalysisConfiguration().model_dump_json(indent=2))"
```

## 📈 Performance Optimization

### Caching
- Enable analysis result caching to avoid repeated work
- Cache duration configurable via `cache_ttl_hours`

### Parallel Processing
- Repository and diff analysis run concurrently
- Control concurrency with `max_concurrent_agents`

### API Efficiency
- Built-in GitHub API rate limiting
- Support for private and public repositories

## 🔒 Security and Privacy

- **API Keys**: Store GitHub tokens securely using environment variables
- **Rate Limiting**: Built-in GitHub API rate limiting to respect quotas
- **Data Privacy**: No permanent code storage, only temporary analysis cache
- **Access Control**: Respects repository permissions through GitHub API

## 💡 Best Practices

1. **Production**: Use `standard` or `deep` analysis depth
2. **CI/CD**: Use `quick` analysis depth for speed
3. **Development**: Use `MockLLMMode.REALISTIC` to avoid API costs
4. **Large PRs**: Increase `max_context_files` for comprehensive analysis
5. **Team Usage**: Configure different models to balance cost and quality