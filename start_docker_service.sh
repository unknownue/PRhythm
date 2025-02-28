#!/bin/bash
# start_docker_service.sh - One-click script to start Docker service for PR report updates
# This script performs the following steps:
# 1. Check environment variables
# 2. Build and start Docker container
# 3. Optionally run an immediate update
# 4. Display status and usage information

# Set script to exit on error
set -e

# Script directory
SCRIPT_DIR=$(dirname "$(readlink -f "$0")")
cd "$SCRIPT_DIR"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to display usage
display_usage() {
    echo -e "${YELLOW}Usage:${NC}"
    echo -e "  ./start_docker_service.sh [options]"
    echo -e "\n${YELLOW}Options:${NC}"
    echo -e "  -h, --help       Display this help message"
    echo -e "  -r, --run-now    Run an immediate update after starting the service"
    echo -e "  -f, --force      Force rebuild Docker image"
    echo -e "\n${YELLOW}Environment Variables:${NC}"
    echo -e "  GITHUB_TOKEN     GitHub API token (required)"
    echo -e "  LLM_API_KEY      LLM API key (required)"
    echo -e "  DEEPSEEK_API_KEY DeepSeek API key (if using DeepSeek)"
    echo -e "  NOTION_API_KEY   Notion API key (if using Notion)"
}

# Parse command line arguments
RUN_NOW=false
FORCE_REBUILD=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help)
            display_usage
            exit 0
            ;;
        -r|--run-now)
            RUN_NOW=true
            shift
            ;;
        -f|--force)
            FORCE_REBUILD=true
            shift
            ;;
        *)
            echo -e "${RED}Error: Unknown option $1${NC}"
            display_usage
            exit 1
            ;;
    esac
done

# Check prerequisites
echo -e "${YELLOW}Checking prerequisites...${NC}"

# Check if Docker is installed
if ! command_exists docker; then
    echo -e "${RED}Error: Docker is not installed. Please install Docker first.${NC}"
    exit 1
fi

# Check if Docker Compose is installed
if ! command_exists docker-compose; then
    echo -e "${RED}Error: Docker Compose is not installed. Please install Docker Compose first.${NC}"
    exit 1
fi

# Check if Docker daemon is running
if ! docker info >/dev/null 2>&1; then
    echo -e "${RED}Error: Docker daemon is not running. Please start Docker first.${NC}"
    exit 1
fi

# Check environment variables
echo -e "${YELLOW}Checking environment variables...${NC}"

# Check if .env file exists, if not create it
if [ ! -f .env ]; then
    echo -e "${YELLOW}Creating .env file from .env.example...${NC}"
    if [ -f .env.example ]; then
        cp .env.example .env
        echo -e "${YELLOW}Please edit .env file with your actual values.${NC}"
        exit 1
    else
        echo -e "${RED}Error: .env.example file not found. Please create .env file manually.${NC}"
        exit 1
    fi
fi

# Source .env file
set -a
source .env
set +a

# Check required environment variables
if [ -z "$GITHUB_TOKEN" ]; then
    echo -e "${RED}Error: GITHUB_TOKEN environment variable is not set.${NC}"
    echo -e "${YELLOW}Please set it in .env file or export it.${NC}"
    exit 1
fi

if [ -z "$LLM_API_KEY" ]; then
    echo -e "${RED}Error: LLM_API_KEY environment variable is not set.${NC}"
    echo -e "${YELLOW}Please set it in .env file or export it.${NC}"
    exit 1
fi

# Check if config.yaml exists
if [ ! -f config.yaml ]; then
    echo -e "${YELLOW}Creating config.yaml from config.example.yaml...${NC}"
    if [ -f config.example.yaml ]; then
        cp config.example.yaml config.yaml
        echo -e "${YELLOW}Please edit config.yaml with your actual values.${NC}"
        exit 1
    else
        echo -e "${RED}Error: config.example.yaml file not found. Please create config.yaml file manually.${NC}"
        exit 1
    fi
fi

# Start Docker service
echo -e "${YELLOW}Starting Docker service...${NC}"

# Change to docker directory
cd docker

# Build and start Docker container
if [ "$FORCE_REBUILD" = true ]; then
    echo -e "${YELLOW}Forcing rebuild of Docker image...${NC}"
    docker-compose build --no-cache
fi

docker-compose up -d

# Check if container is running
if [ "$(docker ps -q -f name=prhythm)" ]; then
    echo -e "${GREEN}Docker service started successfully!${NC}"
else
    echo -e "${RED}Error: Failed to start Docker service.${NC}"
    echo -e "${YELLOW}Check Docker logs for more information:${NC}"
    echo -e "  docker logs prhythm"
    exit 1
fi

# Run immediate update if requested
if [ "$RUN_NOW" = true ]; then
    echo -e "${YELLOW}Running immediate update...${NC}"
    docker exec -it prhythm /app/update_pr_reports.sh
fi

# Display status and usage information
echo -e "\n${GREEN}PRhythm Docker service is now running!${NC}"
echo -e "${YELLOW}The service will automatically update PR reports according to the cron schedule.${NC}"
echo -e "\n${YELLOW}Useful commands:${NC}"
echo -e "  ${GREEN}View logs:${NC}"
echo -e "    docker logs -f prhythm"
echo -e "  ${GREEN}Run manual update:${NC}"
echo -e "    docker exec -it prhythm /app/update_pr_reports.sh"
echo -e "  ${GREEN}Stop service:${NC}"
echo -e "    cd docker && docker-compose down"
echo -e "  ${GREEN}View generated reports:${NC}"
echo -e "    ls -la analysis"

echo -e "\n${GREEN}Done!${NC}"