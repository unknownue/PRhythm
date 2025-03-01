#!/bin/bash
# PRhythm Docker Entrypoint Script
# This script handles the container startup process

set -e

# Initial setup
python scripts/check_pull_repo.py --skip-clone

# Make script executable
chmod +x /app/update_pr_reports.sh

# Install cron (with sudo to avoid permission issues)
apt-get update || true
apt-get install -y cron jq || true

# Create cron job
echo '0 * * * * cd /app && ./update_pr_reports.sh >> /app/cron.log 2>&1' > /etc/cron.d/prhythm-cron
chmod 0644 /etc/cron.d/prhythm-cron
crontab /etc/cron.d/prhythm-cron

# Use default port 9090 if not specified
export VIEWER_PORT=${VIEWER_PORT:-9090}

# Start the Markdown viewer
cd /app/viewer && python app.py &

# Start cron and keep container running
service cron start || cron
tail -f /dev/null 