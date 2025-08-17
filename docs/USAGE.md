# PRhythm Usage Guide

## Repository Setup

```bash
./scripts/setup_repo.sh https://github.com/user/repo-name
```

Creates workspace directories and configuration template for a GitHub repository. Clones the repository to analysis directories for PR processing.

## PR Analysis

### Analyze PR from GitHub URL

```bash
python main.py --analyze-pr https://github.com/owner/repo/pull/123
```

### Analyze PR from Local JSON File

```bash
python main.py --analyze-pr workspaces/repo-name/temp/pr_123_data.json
```

### Stop at Specific Stage

```bash
# Stop after scheme selection
python main.py --analyze-pr PR_URL --stop-at select_scheme

# Stop after data collection
python main.py --analyze-pr PR_URL --stop-at collect_data

# Stop after analysis generation (before report processing)
python main.py --analyze-pr PR_URL --stop-at generate_analysis
```

Available stop points: `initialize_analysis`, `select_scheme`, `collect_data`, `generate_analysis`, `process_report`

### Save Analysis Prompt to File

```bash
python main.py --analyze-pr PR_URL --output-prompt-dir ./analysis_prompts --stop-at generate_analysis
```

This will save the generated analysis prompt to `./analysis_prompts/pr_{number}_prompt.md`

### Complete Example

```bash
# Analyze a PR, save the prompt, and stop at generate_analysis stage
python main.py \
  --analyze-pr workspaces/bevy/temp/pr_20604_data.json \
  --output-prompt-dir workspaces/bevy/analysis_prompt \
  --stop-at generate_analysis
```

## Environment Configuration

Create a `.env` file in the project root:

```bash
# Ollama Server Configuration
PUB_OLLAMA_SERVER_BASE_URL=http://192.168.50.209:8090
PUB_OLLAMA_SERVER_API_KEY=""
PUB_OLLAMA_SERVER_MODEL=hopephoto/Qwen3-4B-Instruct-2507_q8:latest

# Alternative LLM Providers
PUB_OPENAI_API_KEY=your_openai_key
PUB_ANTHROPIC_API_KEY=your_anthropic_key
PUB_GOOGLE_API_KEY=your_google_key
```

## Test LLM Connection

```bash
python tests/test_llm_connection.py

# Test specific provider
python tests/test_llm_connection.py --provider ollama
```

## Sync Status

```bash
# Check sync status for a repository
python main.py --show-sync-status repo-name
```
