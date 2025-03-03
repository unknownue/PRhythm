# PRhythm - GitHub PR Analysis Tool

## Overview

PRhythm is an automated tool that monitors GitHub repositories for merged Pull Requests, analyzes them using LLM technology, and generates insightful reports. This tool helps teams stay informed about code changes and understand the impact of PRs with minimal manual effort.

## Features

- **Automated PR Monitoring**: Periodically checks specified GitHub repositories for newly merged PRs
- **Comprehensive PR Data Collection**: Gathers PR title, number, description, code diffs, and other relevant information
- **Intelligent Analysis**: Leverages LLM APIs (OpenAI, DeepSeek, etc.) to analyze PR content and generate meaningful reports
- **PR Synchronization Tracking**: Tracks which PRs have been processed and identifies unsynchronized PRs
- **Multi-language Support**: Generate analysis reports in different languages (English, Chinese, etc.)
- **Built-in Markdown Viewer**: Web-based interface to browse and read generated PR analysis reports

## Quick Start

PRhythm offers two deployment methods: Docker containerized deployment and local direct deployment. Choose the one that best suits your needs.

### Method 1: Using Docker (Recommended)

Docker deployment provides an isolated environment and simplified setup process, particularly suitable for team use or server deployment.

1. **Clone the repository and prepare configuration**:
   ```bash
   # Clone the repository
   git clone https://github.com/yourusername/PRhythm.git
   cd PRhythm
   
   # Create and edit configuration file
   cp config.example.json config.json
   # Edit config.json with your preferred editor
   # Set your API tokens in config.json:
   # - github.token: Your GitHub API token
   # - llm.api_key: Your LLM API key
   # - llm.providers.deepseek.api_key: Your DeepSeek API key (if using DeepSeek)
   ```

2. **Set API tokens (choose one method)**:
   
   **Option A: Set in config.json (recommended)**
   ```json
   {
     "github": {
       "token": "your-github-token-here"
     },
     "llm": {
       "api_key": "your-llm-api-key-here",
       "providers": {
         "deepseek": {
           "api_key": "your-deepseek-api-key-here"
         }
       }
     }
   }
   ```
   
   **Option B: Set as environment variables**
   ```bash
   # Export environment variables
   export GITHUB_TOKEN="your-github-token"
   export LLM_API_KEY="your-llm-api-key"
   export DEEPSEEK_API_KEY="your-deepseek-api-key"  # If using DeepSeek
   export VIEWER_PORT="9090"  # Optional: Set custom port for Markdown viewer
   ```

3. **Start Docker container using the convenience script**:
   ```bash
   # Start with default settings
   python start_docker_service.py
   
   # Or start with custom port
   python start_docker_service.py --port 8080
   
   # Or start and run an immediate update
   python start_docker_service.py --run-now
   
   # Or start with scheduled updates (every 3600 seconds)
   python start_docker_service.py --schedule 3600
   
   # Or combine options
   python start_docker_service.py --port 8080 --schedule 3600 --run-now
   ```

4. **Access the Markdown Viewer**:
   ```bash
   # Open in your browser
   http://localhost:9090  # Or your custom port
   ```

5. **Stop Docker container when needed**:
   ```bash
   # Stop the service
   python stop_docker_service.py
   
   # Or stop and remove container
   python stop_docker_service.py --remove
   ```

### Method 2: Local Direct Deployment

If you prefer running in your local environment or need more customization control, you can choose local deployment.

1. **Clone the repository and install dependencies**:
   ```bash
   # Clone the repository
   git clone https://github.com/yourusername/PRhythm.git
   cd PRhythm
   
   # Install dependencies
   pip install -r requirements.txt
   ```

2. **Prepare configuration**:
   ```bash
   # Create and edit configuration file
   cp config.example.json config.json
   # Edit config.json with your preferred editor
   # Set your API tokens in config.json:
   # - github.token: Your GitHub API token
   # - llm.api_key: Your LLM API key
   # - llm.providers.deepseek.api_key: Your DeepSeek API key (if using DeepSeek)
   ```

3. **Set API tokens (choose one method)**:
   
   **Option A: Set in config.json (recommended)**
   ```json
   {
     "github": {
       "token": "your-github-token-here"
     },
     "llm": {
       "api_key": "your-llm-api-key-here",
       "providers": {
         "deepseek": {
           "api_key": "your-deepseek-api-key-here"
         }
       }
     }
   }
   ```
   
   **Option B: Set as environment variables**
   ```bash
   # Export environment variables
   export GITHUB_TOKEN="your-github-token"
   export LLM_API_KEY="your-llm-api-key"
   export DEEPSEEK_API_KEY="your-deepseek-api-key"  # If using DeepSeek
   export VIEWER_PORT="9090"  # Optional: Set custom port for Markdown viewer
   ```

4. **Initialize directory structure and run the tool**:
   ```bash
   # Initialize repositories
   python scripts/check_pull_repo.py
   
   # Run analysis script
   python scripts/update_pr_reports.py
   
   # Start the viewer application
   cd viewer
   python app.py
   ```

## Configuration and Usage

### Configuration File

`config.json` is the core configuration file for PRhythm, containing the following main sections:

```json
{
  "github": {
    "repositories": [
      "owner/repo1",
      "owner/repo2"
    ],
    "check_interval": 3600,
    "token": ""
  },
  "llm": {
    "provider": "deepseek",
    "api_key": "",
    "model": "deepseek-reasoner",
    "temperature": 0.3,
    "providers": {
      "deepseek": {
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-reasoner"
      }
    }
  },
  "output": {
    "languages": ["en"]
  }
}
```

### Common Commands

#### Check Repository Status
```bash
python scripts/check_pull_repo.py
```

#### Find Unsynchronized PRs
```bash
python scripts/track_merged_prs.py --repo "owner/repo"
```

#### Get Information for a Specific PR
```bash
python scripts/fetch_pr_info.py --repo "owner/repo" --pr 123
```

#### Analyze PR and Generate Report
```bash
# Automatically find the latest PR JSON file
python scripts/analyze_pr.py --repo "owner/repo" --pr 123

# Specify language and provider
python scripts/analyze_pr.py --repo "owner/repo" --pr 123 --language zh-cn --provider deepseek
```

#### One Command PR Fetch and Analysis
```bash
# Fetch PR info and analyze in one command with Chinese report
python scripts/fetch_pr_info.py --repo "owner/repo" --pr 123 && python scripts/analyze_pr.py --repo "owner/repo" --pr 123 --language zh-cn
```

#### Run Complete Workflow
```bash
# Run once
python scripts/update_pr_reports.py

# Run periodically (every hour)
python scripts/update_pr_reports.py --schedule 3600
```

### Docker Commands

```bash
# Start container with convenience script
python start_docker_service.py [--port PORT] [--run-now] [--force] [--schedule SECONDS]

# View logs
docker logs -f prhythm

# Run analysis manually
docker exec -it prhythm python /app/scripts/update_pr_reports.py

# Stop container
python stop_docker_service.py [--remove]
```

### Output Files

Files generated by PRhythm are saved in the following directories with monthly organization:

- **PR Information**: `output/repo_name/YYYY-MM/pr_123_20240228_123456.json`
- **Analysis Reports**: `analysis/repo_name/YYYY-MM/pr_123_zh-cn_20240228_123456.md`
- **Processing Status**: `repos/pr_processing_status.json`

The monthly directory structure (`YYYY-MM` format) helps organize files chronologically, making it easier to manage and locate reports over time.

## Markdown Viewer

PRhythm includes a built-in web-based Markdown viewer that allows you to browse and read the generated PR analysis reports in a user-friendly interface.

### Features

- **Repository Organization**: Reports are organized by repository for easy navigation
- **Responsive Design**: Works well on both desktop and mobile devices
- **Code Highlighting**: Proper syntax highlighting for code blocks in various languages
- **Line Numbers**: Displays line numbers for code blocks to improve readability
- **Copy Functionality**: One-click copy button for code blocks
- **Language Detection**: Automatically detects and labels code block languages

### Accessing the Viewer

The Markdown viewer is automatically started when you run PRhythm using Docker. For local deployment, you need to start it manually:

```bash
# Start the viewer (from the project root)
cd viewer
python app.py

# Or with a custom port
VIEWER_PORT=8080 python app.py
```

By default, the viewer is accessible at:
- Docker deployment: `http://localhost:9090` (or your custom port)
- Local deployment: `http://localhost:9090` (or your custom port)

### Customizing the Viewer

You can customize the viewer by modifying the following files:
- **Port Configuration**: Set the `VIEWER_PORT` environment variable
- **Styling**: Edit `viewer/static/style.css` to change the appearance
- **Templates**: Modify files in `viewer/templates/` to change the layout

### Viewer Configuration Options

The Markdown viewer supports the following configuration options through environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `VIEWER_PORT` | Port on which the viewer will be accessible | 9090 |
| `VIEWER_HOST` | Host address to bind the viewer | 0.0.0.0 |
| `VIEWER_DEBUG` | Enable debug mode for development | False |

Example of setting custom configuration:
```bash
# For Docker deployment, add to .env file:
VIEWER_PORT=8080

# For local deployment:
export VIEWER_PORT=8080
cd viewer && python app.py
```

## Advanced Configuration

### Customizing Analysis Prompt Template

You can customize the analysis prompt template by editing the `prompt/analyze_pr.prompt` file. The template supports various variable substitutions, such as `{pr_data['title']}`, `{output_language}`, etc.

### Adding New LLM Providers

To add a new LLM provider, add the corresponding configuration to the `llm.providers` section in `config.json`:

```json
{
  "llm": {
    "providers": {
      "new_provider": {
        "base_url": "https://api.new-provider.com",
        "api_key": "",
        "model": "model-name"
      }
    }
  }
}
``` 