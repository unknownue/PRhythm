# PRhythm Project Guide for LLMs

This document provides a technical overview of the PRhythm project, intended to help Large Language Models (LLMs) understand its structure, workflow, and key components.

## 1. Project Goal

PRhythm automates the process of monitoring GitHub repositories for merged Pull Requests (PRs), fetching their details, analyzing the changes using LLMs, and generating technical reports in specified languages. The primary goal is to provide concise, insightful summaries of code changes for engineering teams.

## 2. Core Workflow

The main operational flow of PRhythm involves several stages executed sequentially, primarily orchestrated by `pipeline/update_pr_reports.py`:

1.  **Repository Check (`pipeline/check_pull_repo.py`)**: Initializes local directory structures for each configured repository under the `output/` directory. Ensures that necessary folders exist before processing.
2.  **Track Merged PRs (`pipeline/track_merged_prs.py`)**: Connects to the GitHub API (via `pipeline/github_client.py` and `pipeline/pr_fetcher.py`) to find recently merged PRs in the configured repositories that haven't been processed yet. It identifies new PRs to be analyzed.
3.  **Fetch PR Information (`pipeline/fetch_pr_info.py`)**: For each newly identified merged PR, this script fetches detailed information from GitHub, including metadata (title, author, labels, dates), the PR description (body), file changes, and the code diff. This data is saved as a JSON file (e.g., `output/repo_name/YYYY-MM/pr_123_timestamp.json`). `pipeline/github_client.py` handles the actual API communication.
4.  **Analyze PR (`pipeline/analyze_pr.py` & `pipeline/pr_analyzer.py`)**: This is the core LLM interaction step.
    *   `analyze_pr.py`: Acts as the command-line interface. It locates the relevant PR JSON file.
    *   `pr_analyzer.py`: Orchestrates the analysis.
        *   It uses `pipeline/prompt_builder.py` to construct a detailed prompt based on the data in the PR JSON file and the `prompt/analyze_pr.prompt` template. The prompt includes PR metadata, description, code diff excerpts, file change summaries, and instructions for the LLM.
        *   It interacts with the configured LLM provider (e.g., OpenAI, DeepSeek) via classes in `pipeline/providers/` (using `provider_factory.py`) to send the prompt and receive the generated analysis.
        *   The generated analysis is intended to follow the structure defined in `prompt/analyze_pr.prompt`.
5.  **Generate Report (`pipeline/report_generator.py`)**: Saves the LLM-generated analysis text into a Markdown file (e.g., `output/repo_name/YYYY-MM/analysis_pr_123_lang.md`). It handles multiple languages if configured.

## 3. Key Components and Scripts (`pipeline/`)

*   **`update_pr_reports.py`**: The main orchestrator script. Runs the entire workflow (check -> track -> fetch -> analyze -> report) either once or on a schedule.
*   **`check_pull_repo.py`**: Initializes repository directories in `output/`.
*   **`track_merged_prs.py`**: Identifies merged PRs that need processing by comparing GitHub data with existing JSON/analysis files. Uses `pr_fetcher.py`.
*   **`pr_fetcher.py`**: Contains logic to query GitHub for merged PRs within a specific timeframe. Uses `github_client.py`.
*   **`fetch_pr_info.py`**: Fetches detailed data for a specific PR (metadata, diff, files) and saves it as JSON. Uses `github_client.py`.
*   **`github_client.py`**: A dedicated client for interacting with the GitHub GraphQL API to fetch repository and PR data.
*   **`analyze_pr.py`**: CLI entry point for analyzing a specific PR (using its JSON data). Calls `pr_analyzer.py`.
*   **`pr_analyzer.py`**: Core analysis class. Manages prompt building, LLM interaction, and saving results. Uses `prompt_builder.py` and `providers/`.
*   **`prompt_builder.py`**: Constructs the detailed prompt for the LLM using the `prompt/analyze_pr.prompt` template and data from the PR JSON file.
*   **`report_generator.py`**: Saves the generated analysis text to Markdown files.
*   **`common.py`**: Contains shared utilities and data structures used across multiple pipeline scripts.
*   **`providers/`**: Directory containing modules for different LLM providers (e.g., `openai_provider.py`, `deepseek_provider.py`). `provider_factory.py` selects the appropriate provider based on configuration.
*   **`utils/`**: Directory containing helper modules for configuration (`config_manager.py`), file operations (`file_utils.py`), language support (`languages.py`), etc.

## 4. LLM Interaction (`pr_analyzer.py` & `prompt_builder.py`)

*   **Prompt Template**: The primary instructions for the LLM are defined in `prompt/analyze_pr.prompt`. This template specifies the desired output format (Markdown report) and the analysis dimensions (Basic Info, Description Translation, Narrative Story, Visual Representation, Key Files Changed, Further Reading).
*   **Prompt Construction**: `prompt_builder.py` populates the `analyze_pr.prompt` template with dynamic data extracted from the specific PR's JSON file (`{PR_TITLE}`, `{PR_BODY}`, `{FILE_CHANGES_SUMMARY}`, `{ARCHITECTURE_CONTEXT}`, etc.). It also prepares context like diff excerpts and file summaries.
*   **API Call**: `pr_analyzer.py` sends the fully constructed prompt to the selected LLM API endpoint (configured in `config.json`) using the appropriate provider class from `pipeline/providers/`.
*   **Output**: The LLM's response is expected to be a Markdown-formatted technical report adhering to the structure requested in the prompt.

## 5. Configuration (`config.json`)

*   Specifies GitHub repositories to monitor, API tokens (`github.token`, LLM keys like `llm.providers.openai.api_key`), the LLM provider to use (`llm.provider`, e.g., "openai", "deepseek"), model details (`llm.providers.deepseek.model`), temperature, and output languages (`output.languages`).
*   Managed by `pipeline/utils/config_manager.py`.

## 6. Data Flow

1.  **Input**: Configuration (`config.json`), GitHub PR events.
2.  **Intermediate Data**: Detailed PR information stored in JSON files (`output/repo/YYYY-MM/pr_*.json`).
3.  **LLM Input**: Dynamically generated prompt string (based on `analyze_pr.prompt` and PR JSON).
4.  **LLM Output**: Markdown analysis text.
5.  **Final Output**: Analysis reports saved as Markdown files (`output/repo/YYYY-MM/analysis_*.md`), organized by repository and month. Diff files (`.patch`) can optionally be saved alongside analysis files.

## 7. Key Goal for LLM Analysis

The core task for the LLM is to synthesize the information provided in the prompt (PR description, diff, file changes, metadata) into a narrative technical report as outlined in `prompt/analyze_pr.prompt`, focusing on explaining the "what, why, and how" of the changes in the specified `OUTPUT_LANGUAGE`. 