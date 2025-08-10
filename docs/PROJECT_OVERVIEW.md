# PRhythm Project Overview

## Objective
The goal of this project is to analyze Pull Requests (PRs) for a specified GitHub repository and generate detailed analysis reports.

## Workflow

### Initial Setup
1.  The user configures the target GitHub repository, GitHub API key, LLM API key, and the output directory for reports.
2.  The system clones the repository locally into two separate directories: `repo-previous` and `repo-merged`.

### PR Analysis Trigger
The PR analysis process is initiated whenever a new PR is merged into the target repository.

### PR Analysis Process
1.  **Data Retrieval**: Utilize the GitHub API to fetch data for the newly merged PR.
2.  **Agent Orchestration**: Create multiple specialized LLM agents to handle different stages of the analysis.
3.  **Scheme Selection**: `agent-1` analyzes the PR content and selects an appropriate predefined PR analysis scheme to execute.
4.  **Pre-merge Data Collection (Conditional)**: If the selected analysis scheme requires data from the state *before* the PR was merged:
    *   `agent-2` operates within the `repo-previous` directory.
    *   It checks out the commit immediately preceding the PR merge.
    *   It collects the necessary pre-merge code environment data.
5.  **Post-merge Data Collection (Conditional)**: If the selected analysis scheme requires data from the state *after* the PR was merged:
    *   `agent-3` operates within the `repo-merged` directory.
    *   It checks out the commit representing the state after the PR merge.
    *   It collects the necessary post-merge code environment data.
6.  **Data Aggregation & Prompt Construction**: `agent-3` (or potentially a dedicated agent) consolidates the collected pre-merge data, post-merge data, and the original PR data (if applicable). It then populates a comprehensive prompt template for PR analysis.
7.  **LLM Analysis**: The constructed analysis prompt is sent to a remote LLM service to generate the core PR analysis report.
8.  **Report Post-processing**: `agent-4` takes the raw analysis report and performs post-processing tasks based on the PR data. This may include correcting formatting issues, fixing broken links, etc.
9.  **Output**: The finalized analysis report is saved to the user-configured output directory.

## PR Analysis Schemes

PR Analysis Schemes define specific types of analysis that can be performed on a PR. The system provides a set of default, generic schemes applicable to any repository. Additionally, a repository can define its own custom schemes tailored to its specific needs, coding standards, or analysis goals.

The system will first look for a scheme definition within the target repository's configuration. If a matching scheme for the PR is found there, it will be used. If not, the system falls back to the built-in default schemes.

*   **Default Scheme Placeholder 1**: A generic analysis type provided by the system. (e.g., General Code Review)
    *   **Requires**: Pre-merge data, Post-merge data, PR metadata
    *   **Focus**: A broad review covering code changes, potential issues, and summary based on all available data.
*   **Default Scheme Placeholder 2**: Another generic analysis type. (e.g., Changelog Generation)
    *   **Requires**: Post-merge data, PR metadata
    *   **Focus**: Generating a user-friendly changelog entry based on the PR's impact and description.
*   **Repo-Specific Scheme Example**: A custom scheme defined within a specific repository's configuration.
    *   **Requires**: As defined by the repository's scheme configuration.
    *   **Focus**: As defined by the repository's scheme configuration (e.g., checking adherence to a specific internal guideline or framework usage).
