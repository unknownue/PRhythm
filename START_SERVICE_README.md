# PRhythm Docker Service Starter

This document provides instructions on how to use the `start_docker_service.py` script to easily start the PRhythm Docker service for automated PR report updates.

## Prerequisites

Before using this script, ensure you have:

1. Docker installed and running
2. Docker Compose installed
3. Python 3.6+ installed
4. Required environment variables set (in `.env` file or exported)
5. Configuration file (`config.json`) properly set up

## Usage

The script provides a simple way to start the PRhythm Docker service with a single command:

```bash
python start_docker_service.py [options]
```

Or if you've made the script executable:

```bash
./start_docker_service.py [options]
```

### Options

- `-h, --help`: Display help message
- `-r, --run-now`: Run an immediate update after starting the service
- `-f, --force`: Force rebuild Docker image
- `-p, --port PORT`: Specify a custom port for the Markdown viewer
- `-s, --schedule SECONDS`: Set interval in seconds for scheduled PR updates
- `-g, --github-token TOKEN`: Specify GitHub token directly
- `-l, --llm-key KEY`: Specify LLM API key directly
- `-d, --deepseek-key KEY`: Specify DeepSeek API key directly

### Examples

1. Start the service with default settings:
   ```bash
   python start_docker_service.py
   ```

2. Start the service and run an immediate update:
   ```bash
   python start_docker_service.py --run-now
   ```

3. Force rebuild the Docker image and start the service:
   ```bash
   python start_docker_service.py --force
   ```

4. Start the service with a custom port:
   ```bash
   python start_docker_service.py --port 8080
   ```

5. Start the service with scheduled updates (every hour):
   ```bash
   python start_docker_service.py --schedule 3600
   ```

6. Combine multiple options:
   ```bash
   python start_docker_service.py --port 8080 --schedule 3600 --run-now
   ```

## Environment Variables

The script requires the following environment variables to be set:

- `GITHUB_TOKEN`: GitHub API token (required)
- `LLM_API_KEY`: LLM API key (required)
- `DEEPSEEK_API_KEY`: DeepSeek API key (if using DeepSeek)
- `VIEWER_PORT`: Port for the Markdown viewer (optional, defaults to 9090)

You can set these variables in your environment or in the `config.json` file. The script will check both locations.

## Configuration

The script uses the `config.json` file for configuration. If this file doesn't exist, the script will create one from `config.example.json`.

### Token Configuration

You can configure API tokens in the `config.json` file:

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

### Language Configuration

You can configure the output language for PR analysis reports in the `config.json` file:

```json
{
  "output": {
    "primary_language": "en",
    "multilingual": false,
    "languages": [
      "en",
      "zh-cn"
    ]
  }
}
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

## Stopping the Service

To stop the PRhythm Docker service, use the companion script:

```bash
python stop_docker_service.py [options]
```

Options:
- `-h, --help`: Display help message
- `-r, --remove`: Remove container and volumes after stopping

## Useful Commands

After starting the service, you can use the following commands:

- View logs:
  ```bash
  docker logs -f prhythm
  ```

- Run manual update:
  ```bash
  docker exec -it prhythm python /app/scripts/update_pr_reports.py
  ```

- Run scheduled updates (every hour):
  ```bash
  docker exec -it prhythm python /app/scripts/update_pr_reports.py --schedule 3600
  ```

- Stop service:
  ```bash
  python stop_docker_service.py
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
4. Ensure your `config.json` is properly configured
5. Check if the port is already in use (the script will notify you if it is)

## Notes

- You can run updates manually or schedule them using the `--schedule` option
- Reports are generated in the language specified in the `config.json` file
- All generated reports are stored in the `analysis` directory
- The Markdown viewer is available at `http://localhost:9090` (or your custom port) 