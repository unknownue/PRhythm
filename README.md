# PRhythm - GitHub PR Analysis & Publishing Tool

## Overview

PRhythm is an automated tool that monitors GitHub repositories for merged Pull Requests, analyzes them using LLM technology, and publishes insightful reports to your preferred platform. This tool helps teams stay informed about code changes, understand the impact of PRs, and maintain a comprehensive changelog with minimal manual effort.

## Features

- **Automated PR Monitoring**: Periodically checks specified GitHub repositories for newly merged PRs
- **Comprehensive PR Data Collection**: Gathers PR title, number, description, code diffs, and other relevant information
- **Intelligent Analysis**: Leverages LLM APIs (OpenAI, DeepSeek, etc.) to analyze PR content and generate meaningful reports
- **Flexible Publishing Options**: Publishes analysis reports to platforms like Notion, custom blogs, or other documentation systems
- **PR Synchronization Tracking**: Tracks which PRs have been processed and identifies unsynchronized PRs
- **Multi-language Support**: Generate analysis reports in different languages (English, Chinese, etc.)

## Architecture

The system follows a four-step workflow:

1. **Monitor**: Watches configured GitHub repositories for newly merged PRs
2. **Collect**: Uses GitHub CLI to extract detailed information about the merged PRs
3. **Analyze**: Processes PR data through LLM APIs with specialized prompts to generate insights
4. **Publish**: Distributes the analysis reports to configured publishing platforms

## Prerequisites

- Docker and Docker Compose (for containerized deployment)
- GitHub CLI (`gh`) authenticated with appropriate permissions
- Access to an LLM API service (OpenAI, Anthropic, etc.)
- API access to your publishing platform (Notion, WordPress, etc.)

## Installation

### Using Docker (Recommended)

```bash
# Clone the repository
git clone https://github.com/yourusername/PRhythm.git
cd PRhythm

# Create configuration file
cp config.example.yaml config.yaml
# Edit config.yaml with your settings

# Authenticate GitHub CLI (if not already done)
gh auth login

# Build and start the container
cd docker && docker-compose up -d
```

### Manual Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/PRhythm.git
cd PRhythm

# Install dependencies
pip install -r requirements.txt

# Configure the application
cp config.example.yaml config.yaml
# Edit config.yaml with your settings
```

## Configuration

Create a `config.yaml` file with the following structure:

```yaml
github:
  repositories:
    - owner/repo1
    - owner/repo2
  check_interval: 3600  # in seconds

llm:
  # Default provider configuration
  provider: "openai"  # or "deepseek", "anthropic", etc.
  api_key: "your-api-key"  # Set via environment variable LLM_API_KEY
  model: "gpt-4"  # or "claude-3-opus", etc.
  temperature: 0.3
  
  # Provider-specific configurations
  providers:
    openai:
      base_url: "https://api.openai.com/v1"
      # model and api_key will be inherited from the default settings if not specified
    
    deepseek:
      base_url: "https://api.deepseek.com"
      api_key: ""  # Set via environment variable DEEPSEEK_API_KEY
      model: "deepseek-chat"  # Available models: deepseek-chat (DeepSeek-V3), deepseek-reasoner (DeepSeek-R1)
  
publishing:
  platform: "notion"  # or "wordpress", "custom", etc.
  api_key: "your-publishing-platform-api-key"
  target_page_id: "your-notion-page-id"  # if using Notion
```

## Usage

### Running with Docker

```bash
# Start the service
cd docker && docker-compose up -d

# View logs
cd docker && docker-compose logs -f

# Run a one-time analysis of a specific PR
cd docker && docker-compose run --rm prhythm python -m prhythm.analyze --repo owner/repo --pr-number 123

# Stop the service
cd docker && docker-compose down
```

### Running Manually

```bash
# Start the monitoring service
python -m prhythm.monitor

# Or run as a background service
nohup python -m prhythm.monitor > prhythm.log 2>&1 &

# Analyze a specific PR
python -m prhythm.analyze --repo owner/repo --pr-number 123

# Publish the latest analysis
python -m prhythm.publish --report-path ./reports/latest.md

# Check and clone tracked repositories
python scripts/check_pull_repo.py

# Create directories without cloning repositories
python scripts/check_pull_repo.py --skip-clone
```

### Tracking Merged PRs

The `track_merged_prs.py` script allows you to track which PRs have been processed and identify unsynchronized PRs:

```bash
# Check for unsynchronized PRs in a repository
python scripts/track_merged_prs.py --repo "owner/repo"

# Check with GitHub token for higher API rate limits
python scripts/track_merged_prs.py --repo "owner/repo" --token "your-github-token"

# Limit the number of PRs to fetch (default is 10)
python scripts/track_merged_prs.py --repo "owner/repo" --limit 20

# Update the status file with the latest PR
python scripts/track_merged_prs.py --repo "owner/repo" --update

# Update with a specific operation name
python scripts/track_merged_prs.py --repo "owner/repo" --update --operation "analysis_complete"

# Update with operation status (success or failure)
python scripts/track_merged_prs.py --repo "owner/repo" --update --operation "analysis_complete" --status "success"
```

The script maintains a status file at `repos/pr_processing_status.json` that tracks:
- The latest processed PR number for each repository
- Timestamp of the last update
- Title and URL of the latest processed PR
- History of batch operations (limited to the last 100 operations)

### Fetching PR Information

The `fetch_pr_info.py` script allows you to fetch detailed information about a specific PR:

```bash
# Fetch information for a specific PR
python scripts/fetch_pr_info.py --repo "owner/repo" --pr 123
```

The script will:
- Fetch detailed PR information using GitHub CLI
- Store the information in a repository-specific directory under `output/`
- Include PR metadata, commits, files, comments, reviews, and diff

### Analyzing PR Information

The `analyze_pr.py` script allows you to analyze PR information using various LLM providers (OpenAI, DeepSeek, etc.):

```bash
# Analyze PR information using the default LLM provider (specified in config.yaml)
python scripts/analyze_pr.py --json output/repo/pr_123_20240228_123456.json --language en

# Analyze PR information using a specific LLM provider
python scripts/analyze_pr.py --json output/repo/pr_123_20240228_123456.json --language zh-cn --provider deepseek

# Specify a different configuration file
python scripts/analyze_pr.py --json output/repo/pr_123_20240228_123456.json --config custom_config.yaml
```

The script will:
- Read the PR information from the JSON file
- Use the specified LLM provider to analyze the PR
- Generate a markdown report in the specified language
- Save the report to the `analysis/repo_name/` directory

## Development

### Docker Image Details

The Docker image is built on Python 3.10-slim and includes:
- GitHub CLI for PR data collection
- Python dependencies for LLM API integration and publishing
- Minimal footprint with no desktop environment

### Adding a New Publishing Platform

To add support for a new publishing platform:

1. Create a new file in `prhythm/publishers/`
2. Implement the `Publisher` interface
3. Register your publisher in `prhythm/publisher.py`

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgements

- GitHub CLI for providing an excellent command-line interface
- OpenAI/Anthropic for their powerful LLM APIs
- All contributors who help improve this tool
