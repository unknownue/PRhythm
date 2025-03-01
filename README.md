# PRhythm - GitHub PR Analysis Tool

## Overview

PRhythm is an automated tool that monitors GitHub repositories for merged Pull Requests, analyzes them using LLM technology, and generates insightful reports. This tool helps teams stay informed about code changes and understand the impact of PRs with minimal manual effort.

## Features

- **Automated PR Monitoring**: Periodically checks specified GitHub repositories for newly merged PRs
- **Comprehensive PR Data Collection**: Gathers PR title, number, description, code diffs, and other relevant information
- **Intelligent Analysis**: Leverages LLM APIs (OpenAI, DeepSeek, etc.) to analyze PR content and generate meaningful reports
- **PR Synchronization Tracking**: Tracks which PRs have been processed and identifies unsynchronized PRs
- **Multi-language Support**: Generate analysis reports in different languages (English, Chinese, etc.)

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
   ```

3. **Start Docker container**:
   ```bash
   cd docker
   docker-compose up -d
   ```

4. **View logs and status**:
   ```bash
   # View container logs
   docker logs -f prhythm
   
   # Check generated reports
   ls -la ../analysis
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
# Using default language and provider
python scripts/analyze_pr.py --json output/repo_name/pr_123_20240228_123456.json

# Specify language and provider
python scripts/analyze_pr.py --json output/repo_name/pr_123_20240228_123456.json --language zh-cn --provider deepseek
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
# Start container
cd docker && docker-compose up -d

# View logs
docker logs -f prhythm

# Run analysis manually (without waiting for scheduled task)
docker exec -it prhythm /app/update_pr_reports.sh

# Stop container
cd docker && docker-compose down
```

### 5. Output Files Explanation

Files generated by PRhythm are saved in the following directories:

- **PR Information**: `output/repo_name/pr_123_20240228_123456.json`
- **Analysis Reports**: `analysis/repo_name/pr_123_zh-cn_20240228_123456.md`
- **Processing Status**: `repos/pr_processing_status.json`

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
