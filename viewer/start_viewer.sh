#!/bin/bash

# Start the Markdown viewer
# This script can be used to start the viewer independently

# Change to the viewer directory
cd "$(dirname "$0")"

# Check if Python is installed
if ! command -v python &> /dev/null; then
    echo "Error: Python is not installed or not in PATH"
    exit 1
fi

# Check if required packages are installed
python -c "import flask, markdown, pygments, yaml" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "Installing required packages..."
    pip install flask markdown pygments pyyaml
fi

# Generate Pygments CSS if it doesn't exist
if [ ! -f "static/pygments.css" ]; then
    echo "Generating Pygments CSS..."
    mkdir -p static
    python -c "from pygments.formatters import HtmlFormatter; open('static/pygments.css', 'w').write(HtmlFormatter(style='default').get_style_defs('.codehilite'))"
fi

# Get port from config.yaml if available
CONFIG_FILE="../config.yaml"
if [ -f "$CONFIG_FILE" ] && command -v python &> /dev/null; then
    # Extract port from config.yaml using Python
    PORT=$(python -c "
import yaml
try:
    with open('$CONFIG_FILE', 'r') as f:
        config = yaml.safe_load(f)
    if 'viewer' in config and 'port' in config['viewer']:
        print(config['viewer']['port'])
    else:
        print('9090')
except Exception:
    print('9090')
")
else
    # Default port if config.yaml is not available
    PORT=9090
fi

# Check if port is already in use
if command -v lsof >/dev/null 2>&1; then
    if lsof -i:"$PORT" > /dev/null 2>&1; then
        echo "Error: Port $PORT is already in use."
        echo "Please specify a different port with VIEWER_PORT environment variable."
        echo "Example: VIEWER_PORT=8888 $0"
        exit 1
    fi
fi

# Allow override via environment variable
export VIEWER_PORT=${VIEWER_PORT:-$PORT}

# Set analysis directory path
if [ -z "$ANALYSIS_DIR" ]; then
    # Default to project root/analysis
    export ANALYSIS_DIR="$(cd .. && pwd)/analysis"
    echo "Using default analysis directory: $ANALYSIS_DIR"
else
    echo "Using specified analysis directory: $ANALYSIS_DIR"
fi

# Start the Flask application
echo "Starting Markdown viewer on http://localhost:${VIEWER_PORT}"
python app.py 