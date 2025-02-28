# PRhythm - GitHub PR Analysis & Publishing Tool

## Overview

PRhythm is an automated tool that monitors GitHub repositories for merged Pull Requests, analyzes them using LLM technology, and publishes insightful reports to your preferred platform. This tool helps teams stay informed about code changes, understand the impact of PRs, and maintain a comprehensive changelog with minimal manual effort.

## Features

- **Automated PR Monitoring**: Periodically checks specified GitHub repositories for newly merged PRs
- **Comprehensive PR Data Collection**: Gathers PR title, number, description, code diffs, and other relevant information
- **Intelligent Analysis**: Leverages LLM APIs to analyze PR content and generate meaningful reports
- **Flexible Publishing Options**: Publishes analysis reports to platforms like Notion, custom blogs, or other documentation systems

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
docker-compose up -d
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
  provider: "openai"  # or "anthropic", etc.
  api_key: "your-api-key"
  model: "gpt-4"  # or "claude-3-opus", etc.
  
publishing:
  platform: "notion"  # or "wordpress", "custom", etc.
  api_key: "your-publishing-platform-api-key"
  target_page_id: "your-notion-page-id"  # if using Notion
```

## Usage

### Running with Docker

```bash
# Start the service
docker-compose up -d

# View logs
docker-compose logs -f

# Run a one-time analysis of a specific PR
docker-compose run --rm prhythm python -m prhythm.analyze --repo owner/repo --pr-number 123

# Stop the service
docker-compose down
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
```

## Development

### Project Structure

```
PRhythm/
├── prhythm/
│   ├── __init__.py
│   ├── monitor.py      # PR monitoring logic
│   ├── collector.py    # GitHub data collection
│   ├── analyzer.py     # LLM-based analysis
│   ├── publisher.py    # Publishing to platforms
│   └── utils.py        # Utility functions
├── config.yaml         # Configuration file
├── requirements.txt    # Dependencies
├── Dockerfile          # Docker image definition
├── docker-compose.yml  # Docker Compose configuration
└── README.md           # This file
```

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
