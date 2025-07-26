# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PRhythm is a GitHub Pull Request analysis tool built using a multi-agent system with LangChain and LangGraph. The project extends from the Open Deep Research framework but focuses specifically on PR analysis functionality.

**Important**: The `src/open_deep_research/` and `src/legacy/` directories contain reference code from the original framework and will be removed in future iterations. The main development focus is on `src/pr_analysis/`.

**For usage instructions and development commands**, see [docs/usage-guide.md](docs/usage-guide.md).

## Development Guidelines

### Communication and Documentation
- Always respond to users in Chinese using short sentences
- Write all code, comments, and documentation in pure English
- Use concise but comprehensive comments covering code blocks, function purposes, and property definitions
- Include critical processing details in comments

## Architecture

### Multi-Agent System Concept
The system uses a supervisor-coordinator pattern with specialized agents:

1. **PR Supervisor**: Orchestrates workflow and coordinates between agents
2. **Repository Analyzer**: Understands codebase structure and technologies  
3. **Diff Analyzer**: Analyzes specific changes and their impact
4. **Context Gatherer**: Collects relevant code context and dependencies
5. **Report Generator**: Synthesizes all findings into comprehensive reports

### Agent Execution Flow
```
PR Request → Initialize → PR Supervisor → [Repository + Diff Analysis] (parallel) 
→ Context Gathering → Report Generation → Final Output
```

### Key Components
- **Main Workflow** (`pr_analyzer.py`): LangGraph state machine coordinating all agents
- **Configuration System** (`configuration.py`): Model assignments and behavior settings
- **State Management** (`state.py`): Pydantic models for agent communication
- **GitHub Integration** (`github/`): API client with rate limiting and data models
- **Mock LLM Service** (`mock_llm.py`): Development service for testing without API costs

## Development Patterns

### Configuration System
- Uses `PRAnalysisConfiguration` class extending base framework patterns
- Supports different models for different agent types (e.g., gpt-4 for analysis, gpt-4-mini for processing)
- Environment variable support (e.g., `GITHUB_TOKEN`)
- Mock LLM modes for development: `DISABLED`, `SIMPLE`, `REALISTIC`, `MIXED`

### Agent Development Pattern
When adding new agents:
1. Create agent file in `src/pr_analysis/agents/`  
2. Implement three functions: main agent, tools handler, continuation condition
3. Add corresponding state model in `state.py`
4. Integrate into main workflow in `pr_analyzer.py`
5. Add model configuration in `configuration.py`

### State Management
- Each agent has its own state model inheriting from LangGraph MessagesState
- State transitions are handled through the main workflow graph
- Agents communicate through structured state updates

### Testing Strategy
- Use Mock LLM service for development (set `mock_llm_mode=MockLLMMode.REALISTIC`)
- Mock responses are defined with realistic structure matching real LLM outputs
- Enables full workflow testing without API costs
- Switch to real LLMs by setting `mock_llm_mode=MockLLMMode.DISABLED`

## File Structure

```
src/pr_analysis/
├── pr_analyzer.py           # Main workflow orchestration
├── configuration.py         # Configuration management  
├── state.py                 # LangGraph state models
├── mock_llm.py             # Mock LLM for development
├── cli.py                  # Command-line interface
├── github/                 # GitHub API integration
│   ├── client.py           # API client with rate limiting
│   ├── models.py           # Pydantic data models
│   └── tools.py            # LangChain tool definitions
└── agents/                 # Specialized analysis agents
    ├── supervisor.py       # Workflow coordinator
    ├── repository_analyzer.py
    ├── diff_analyzer.py  
    ├── context_gatherer.py
    └── report_generator.py
```

## Development Notes

### Model Assignment Strategy
- **Supervisor & Diff Analyzer**: Use reasoning-heavy models (gpt-4) for complex analysis
- **Repository Analyzer & Context Gatherer**: Can use efficient models (gpt-4-mini) for processing
- **Report Generator**: Uses high-quality model (gpt-4) for final synthesis

### GitHub API Integration
- Built-in rate limiting respects GitHub API quotas
- Supports both public and private repositories
- Comprehensive data extraction (PRs, diffs, repository context)
- Error handling for common GitHub API issues

### Parallel Processing
- Repository analysis and diff analysis run concurrently for performance
- Context gathering depends on diff analysis results
- Report generation synthesizes all previous agent outputs

### Extension Points
The system is designed for extensibility:
- New agents can be added following the established pattern
- Configuration system supports new model types and parameters  
- State models can be extended for new data requirements
- GitHub tools can be enhanced with additional API endpoints

### Integration with Framework
- Extends existing Open Deep Research configuration patterns
- Reuses LangChain/LangGraph infrastructure
- Compatible with existing model initialization system
- Follows established error handling and logging patterns