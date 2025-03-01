#!/bin/bash
# stop_docker_service.sh - Simple script to stop PRhythm Docker service

# Set color output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR=$(dirname "$(readlink -f "$0")")
cd "$SCRIPT_DIR"

# Display usage
display_usage() {
    echo -e "${YELLOW}Usage:${NC}"
    echo -e "  ./stop_docker_service.sh [options]"
    echo -e "\n${YELLOW}Options:${NC}"
    echo -e "  -h, --help    Display this help message"
    echo -e "  -r, --remove  Remove container and volumes after stopping"
}

# Parse command line arguments
REMOVE_CONTAINER=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help)
            display_usage
            exit 0
            ;;
        -r|--remove)
            REMOVE_CONTAINER=true
            shift
            ;;
        *)
            echo -e "${RED}Error: Unknown option $1${NC}"
            display_usage
            exit 1
            ;;
    esac
done

# Check if Docker is running
if ! docker info >/dev/null 2>&1; then
    echo -e "${RED}Error: Docker is not running. Cannot stop service.${NC}"
    exit 1
fi

# Check if container is running
if ! docker ps -q -f name=prhythm >/dev/null 2>&1; then
    echo -e "${YELLOW}PRhythm container is not running. Nothing to stop.${NC}"
    
    # Check if container exists but is stopped
    if docker ps -a -q -f name=prhythm >/dev/null 2>&1 && [ "$REMOVE_CONTAINER" = true ]; then
        echo -e "${YELLOW}Removing stopped container...${NC}"
        cd docker && docker-compose rm -f
        echo -e "${GREEN}Container successfully removed.${NC}"
    fi
    
    exit 0
fi

# Get current viewer port (for display information)
VIEWER_PORT=$(docker inspect --format='{{range $p, $conf := .NetworkSettings.Ports}}{{if eq $p "9090/tcp"}}{{(index $conf 0).HostPort}}{{end}}{{end}}' prhythm 2>/dev/null || echo "9090")
if [ -z "$VIEWER_PORT" ]; then
    VIEWER_PORT="9090"
fi

# Stop Docker service
echo -e "${YELLOW}Stopping Docker service...${NC}"

# Change to docker directory
cd docker

# Stop Docker container
if [ "$REMOVE_CONTAINER" = true ]; then
    echo -e "${YELLOW}Stopping and removing container...${NC}"
    docker-compose down -v
else
    docker-compose down
fi

# Check if container is stopped
if ! docker ps -q -f name=prhythm >/dev/null 2>&1; then
    echo -e "${GREEN}Docker service successfully stopped!${NC}"
else
    echo -e "${RED}Error: Failed to stop Docker service.${NC}"
    exit 1
fi

# Display status information
echo -e "\n${GREEN}PRhythm Docker service has been stopped.${NC}"
echo -e "${YELLOW}The Markdown viewer at http://localhost:${VIEWER_PORT} is no longer available.${NC}"

if [ "$REMOVE_CONTAINER" = true ]; then
    echo -e "${YELLOW}Container and volumes have been removed.${NC}"
else
    echo -e "\n${YELLOW}Useful commands:${NC}"
    echo -e "  ${GREEN}Start service again:${NC}"
    echo -e "    ./start_docker_service.sh"
    echo -e "  ${GREEN}View generated reports:${NC}"
    echo -e "    ls -la analysis"
fi

echo -e "\n${GREEN}Done!${NC}" 