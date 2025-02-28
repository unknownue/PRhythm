# PRhythm Docker Service Starter

This document provides instructions on how to use the `start_docker_service.sh` script to easily start the PRhythm Docker service for automated PR report updates.

## Prerequisites

Before using this script, ensure you have:

1. Docker installed and running
2. Docker Compose installed
3. Required environment variables set (in `.env` file or exported)
4. Configuration file (`config.yaml`) properly set up

## Usage

The script provides a simple way to start the PRhythm Docker service with a single command:

```bash
./start_docker_service.sh [options]
```

### Options

- `-h, --help`: Display help message
- `-r, --run-now`: Run an immediate update after starting the service
- `-f, --force`: Force rebuild Docker image

### Examples

1. Start the service with default settings:
   ```bash
   ./start_docker_service.sh
   ```

2. Start the service and run an immediate update:
   ```bash
   ./start_docker_service.sh --run-now
   ```

3. Force rebuild the Docker image and start the service:
   ```bash
   ./start_docker_service.sh --force
   ```

## Environment Variables

The script requires the following environment variables to be set:

- `GITHUB_TOKEN`: GitHub API token (required)
- `LLM_API_KEY`: LLM API key (required)
- `DEEPSEEK_API_KEY`: DeepSeek API key (if using DeepSeek)
- `NOTION_API_KEY`: Notion API key (if using Notion)

You can set these variables in a `.env` file in the project root directory. If the file doesn't exist, the script will create one from `.env.example`.

## Configuration

The script uses the `config.yaml` file for configuration. If this file doesn't exist, the script will create one from `config.example.yaml`.

### Language Configuration

You can configure the output language for PR analysis reports in the `config.yaml` file:

```yaml
# Output configuration
output:
  language: "en"  # Output language for analysis reports: "en" (English), "zh-cn" (Chinese), etc.
```

Supported language codes include:
- `en`: English
- `zh-cn`: Chinese (Simplified)
- `ja`: Japanese
- `ko`: Korean
- `fr`: French
- `de`: German
- `es`: Spanish
- And more, depending on the LLM provider's capabilities

The script will automatically use the language specified in the configuration file.

## Useful Commands

After starting the service, you can use the following commands:

- View logs:
  ```bash
  docker logs -f prhythm
  ```

- Run manual update:
  ```bash
  docker exec -it prhythm /app/update_pr_reports.sh
  ```

- Stop service:
  ```bash
  cd docker && docker-compose down
  ```

- View generated reports:
  ```bash
  ls -la analysis
  ```

## Troubleshooting

If you encounter issues:

1. Check if Docker is running
2. Verify that all required environment variables are set
3. Check Docker logs for error messages:
   ```bash
   docker logs prhythm
   ```
4. Ensure your `config.yaml` is properly configured

## Notes

- The service will automatically update PR reports according to the cron schedule defined in the Docker configuration
- Reports are generated in the language specified in the `config.yaml` file
- All generated reports are stored in the `analysis` directory 