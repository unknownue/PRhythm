# PRhythm Project Overview

## Objective
The goal of this project is to analyze Pull Requests (PRs) for a specified GitHub repository and generate detailed analysis reports.

## Workflow

### System Architecture

```mermaid
graph TB
    A[User Input: PR URL/JSON] --> B[main.py Entry Point]
    B --> C[WorkflowManager]
    C --> D[LangGraph PRhythm Workflow]
    
    D --> E[initialize_analysis]
    E --> F[select_scheme]
    F --> G[collect_data]
    G --> H[generate_analysis]
    H --> I[process_report]
    I --> J[Final Report Output]
    
    %% Subgraph for scheme selection
    F --> K[scheme_selector Agent]
    K --> L[evaluate_conditions]
    L --> M[Selected Scheme]
    
    %% Subgraph for data collection
    G --> N[data_collector Agent]
    N --> O[execute_collection_tasks]
    O --> P[Collected Data]
    
    %% Subgraph for report processing
    I --> Q[report_processor Agent]
    Q --> R[execute_processing_tasks]
    R --> S[Processed Report]
    
    %% External dependencies
    T[GitHub Client] --> C
    U[Git Repository Workspaces] --> N
    V[LLM Models] --> K
    V --> N
    V --> H
    V --> Q
```

### PR Analysis Process Flow

```mermaid
sequenceDiagram
    participant User
    participant Main as main.py
    participant WM as WorkflowManager
    participant WF as PRhythm Workflow
    participant GH as GitHub Client
    participant A1 as Scheme Selector
    participant A2 as Data Collector
    participant A3 as Report Processor
    participant LLM as LLM Service

    User->>Main: --analyze-pr [PR_URL]
    Main->>WM: analyze_pr(pr_input)
    WM->>GH: get_pr_data(owner, repo, pr_number)
    GH-->>WM: PR Data
    WM->>WF: Execute workflow with PR data
    
    WF->>WF: initialize_analysis
    Note over WF: Setup workspace, validate input
    
    WF->>A1: select_scheme
    A1->>LLM: Analyze PR characteristics
    LLM-->>A1: Suggested scheme
    A1-->>WF: Selected analysis scheme
    
    WF->>A2: collect_data (parallel execution)
    Note over A2: Pre-merge & Post-merge collectors
    A2->>A2: Plan collection tasks
    A2->>A2: Execute git commands
    A2->>A2: Analyze files/directories
    A2-->>WF: Collected data
    
    WF->>LLM: generate_analysis
    Note over LLM: Generate analysis report using<br/>PR data + collected data
    LLM-->>WF: Raw analysis report
    
    WF->>A3: process_report
    A3->>A3: Fix formatting, links
    A3->>A3: Add metadata, TOC
    A3-->>WF: Processed report
    
    WF-->>WM: Analysis results
    WM-->>Main: Final report
    Main-->>User: Display results
```

### Component Architecture

```mermaid
graph LR
    subgraph "Core Components"
        WM[WorkflowManager]
        GH[GitHubClient] 
        PS[PRSyncManager]
        AC[AgentConfiguration]
    end
    
    subgraph "LangGraph Workflow"
        MW[Main Workflow]
        SS[Scheme Selector]
        DC[Data Collector]
        RP[Report Processor]
    end
    
    subgraph "Tools & Utilities"
        GT[Git Tools]
        AT[Analysis Tools]
        FT[File Tools]
    end
    
    subgraph "External Services"
        GA[GitHub API]
        LM[LLM Services]
        WS[Workspace Storage]
    end
    
    WM --> MW
    MW --> SS
    MW --> DC
    MW --> RP
    
    SS --> LM
    DC --> GT
    DC --> AT
    DC --> FT
    RP --> LM
    
    GH --> GA
    PS --> WS
    GT --> WS
    AT --> WS
```

### Data Flow

1. **Input Processing**: User provides PR URL or JSON file containing PR data
2. **Workspace Setup**: System initializes workspace directories for pre-merge and post-merge analysis
3. **Scheme Selection**: Agent-1 analyzes PR characteristics to select appropriate analysis scheme
4. **Data Collection**: Agent-2 (pre-merge) and Agent-3 (post-merge) collect repository data based on scheme requirements
5. **Analysis Generation**: Main workflow aggregates all data and sends to LLM for comprehensive analysis
6. **Report Processing**: Agent-4 post-processes the raw report for better formatting and presentation
7. **Output**: Final processed report is returned to user

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
