#!/bin/bash
# PRhythm Docker Entrypoint Script
# This script handles the container startup process

set -e

echo "Starting PRhythm service with context extraction support..."

# Create logs directory if it doesn't exist
mkdir -p /app/logs

# Initial setup
python pipeline/check_pull_repo.py --skip-clone

# Use default port 9090 if not specified
export VIEWER_PORT=${VIEWER_PORT:-9090}

# Start the Markdown viewer
cd /app/viewer && python app.py &

# Keep container running
tail -f /dev/null 