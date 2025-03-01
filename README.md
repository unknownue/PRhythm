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
   cp config.example.yaml config.yaml
   # Edit config.yaml with your preferred editor
   ```

2. **Set environment variables**:
   ```bash
   # Create .env file or export environment variables directly
   echo "GITHUB_TOKEN=your-github-token" > .env
   echo "LLM_API_KEY=your-llm-api-key" >> .env
   echo "DEEPSEEK_API_KEY=your-deepseek-api-key" >> .env
   # Optionally set custom port for the Markdown viewer
   echo "VIEWER_PORT=9090" >> .env
   ```

3. **Start Docker container using the convenience script**:
   ```bash
   # Start with default settings
   ./start_docker_service.sh
   
   # Or start with custom port
   ./start_docker_service.sh --port 8080
   
   # Or start and run an immediate update
   ./start_docker_service.sh --run-now
   ```

4. **View logs and status**:
   ```bash
   # View container logs
   docker logs -f prhythm
   
   # Check generated reports
   ls -la analysis
   ```

5. **Access the Markdown Viewer**:
   ```bash
   # Open in your browser
   http://localhost:9090  # Or your custom port
   ```

6. **Stop Docker container when needed**:
   ```bash
   # Stop the service
   ./stop_docker_service.sh
   
   # Or stop and remove container
   ./stop_docker_service.sh --remove
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
   cp config.example.yaml config.yaml
   # Edit config.yaml with your preferred editor
   ```

3. **Set environment variables**:
   ```bash
   # Set necessary environment variables
   export GITHUB_TOKEN="your-github-token"
   export LLM_API_KEY="your-llm-api-key"
   export DEEPSEEK_API_KEY="your-deepseek-api-key"  # If using DeepSeek
   export VIEWER_PORT="9090"  # Optional: Set custom port for Markdown viewer
   ```

4. **Initialize directory structure**:
   ```bash
   python scripts/check_pull_repo.py
   ```

5. **Run automation script**:
   ```bash
   # Make script executable
   chmod +x update_pr_reports.sh
   
   # Run script
   ./update_pr_reports.sh
   ```

6. **Set up scheduled task** (optional):
   ```bash
   # Edit crontab
   crontab -e
   
   # Add the following line (runs hourly)
   0 * * * * /path/to/prhythm/update_pr_reports.sh >> /path/to/prhythm/cron.log 2>&1
   ```

7. **Start the Markdown Viewer**:
   ```bash
   # Start the viewer application
   cd viewer
   python app.py
   
   # Access in your browser
   http://localhost:9090
   ```

## Detailed Usage Guide

Regardless of which deployment method you choose, PRhythm provides a complete set of scripts to implement an automated workflow. Here are the detailed usage steps:

### 1. Configuration File Explanation

`config.yaml` is the core configuration file for PRhythm, containing the following main sections:

```yaml
github:
  repositories:
    - owner/repo1
    - owner/repo2
  check_interval: 3600  # Check interval in seconds
  token: ""  # Recommended to set via GITHUB_TOKEN environment variable

llm:
  provider: "deepseek"  # Options: openai, deepseek, etc.
  api_key: ""  # Recommended to set via environment variable
  model: "deepseek-reasoner"  # Or gpt-4, deepseek-chat, etc.
  temperature: 0.3
  
  providers:
    deepseek:
      base_url: "https://api.deepseek.com"
      model: "deepseek-reasoner"  # Available models: deepseek-chat, deepseek-reasoner

# Output configuration
output:
  language: "en"  # Output language for analysis reports: "en" (English), "zh-cn" (Chinese), etc.
```

### 2. Manually Running Individual Steps

If you want to understand the entire process or run certain steps individually, you can follow these methods:

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
# Method 1: Specify JSON file path directly
python scripts/analyze_pr.py --json output/repo_name/2024-03/pr_123_20240228_123456.json

# Method 2: Automatically find the latest PR JSON file (recommended)
python scripts/analyze_pr.py --repo "owner/repo" --pr 123

# Specify language and provider
python scripts/analyze_pr.py --repo "owner/repo" --pr 123 --language zh-cn --provider deepseek

# Dry run (only print the prompt without sending to LLM API)
python scripts/analyze_pr.py --repo "owner/repo" --pr 123 --dry-run
```

#### One-Command PR Fetch and Analysis

```bash
# Fetch PR info and analyze in one command (English report)
python scripts/fetch_pr_info.py --repo "owner/repo" --pr 123 && python scripts/analyze_pr.py --repo "owner/repo" --pr 123

# Fetch PR info and analyze with Chinese report
python scripts/fetch_pr_info.py --repo "owner/repo" --pr 123 && python scripts/analyze_pr.py --repo "owner/repo" --pr 123 --language zh-cn

# Fetch PR info and analyze with specific provider
python scripts/fetch_pr_info.py --repo "owner/repo" --pr 123 && python scripts/analyze_pr.py --repo "owner/repo" --pr 123 --provider deepseek
```

#### Update PR Processing Status

```bash
python scripts/track_merged_prs.py --repo "owner/repo" --update --operation "analysis_complete" --status "success"
```

### 3. Automation Script Explanation

The `update_pr_reports.sh` script automatically executes the complete PR analysis workflow:

1. Check and update configured repositories
2. Get unsynchronized PRs for each repository
3. Get detailed information for each PR
4. Use LLM to analyze PRs and generate reports
5. Update PR processing status

You can run this script directly or set it up as a scheduled task:

```bash
# Run directly
./update_pr_reports.sh

# Or set up as a scheduled task
crontab -e
# Add: 0 * * * * /path/to/prhythm/update_pr_reports.sh >> /path/to/prhythm/cron.log 2>&1
```

### 4. Docker Environment Explanation

If using Docker deployment, PRhythm will automatically set up a scheduled task to check for new PRs hourly. You can manage the Docker container with these commands:

```bash
# Start container with convenience script
./start_docker_service.sh [--port PORT] [--run-now] [--force]

# View logs
docker logs -f prhythm

# Run analysis manually (without waiting for scheduled task)
docker exec -it prhythm /app/update_pr_reports.sh

# Stop container
./stop_docker_service.sh [--remove]
```

The convenience scripts provide additional features:

- **start_docker_service.sh**: 
  - `--port PORT`: Specify a custom port for the Markdown viewer
  - `--run-now`: Run an immediate update after starting the service
  - `--force`: Force rebuild Docker image

- **stop_docker_service.sh**:
  - `--remove`: Remove container and volumes after stopping

### 5. Output Files Explanation

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

To add a new LLM provider, add the corresponding configuration to the `llm.providers` section in `config.yaml`:

```yaml
llm:
  providers:
    new_provider:
      base_url: "https://api.new-provider.com"
      api_key: ""  # Recommended to set via environment variable
      model: "model-name"
```

### Customizing Docker Configuration

You can customize the Docker configuration by editing `docker/docker-compose.yml` and `docker/Dockerfile`, such as changing the scheduled task frequency, adding additional environment variables, etc.

## Troubleshooting

### Common Issues

1. **GitHub API Rate Limits**: Ensure you've set a valid `GITHUB_TOKEN` environment variable
2. **LLM API Errors**: Check if your API key is correct and you have sufficient quota
3. **Docker Permission Issues**: Ensure Docker has access to the mounted directories

### Log Files

- Docker environment: Logs are saved in `/app/cron.log` inside the container
- Local environment: Logs are saved in script output or redirected files

## Contributing

Contributions are welcome! Feel free to submit a Pull Request.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgements

- GitHub CLI for providing an excellent command-line interface
- OpenAI/DeepSeek for their powerful LLM APIs
- All contributors who help improve this tool 