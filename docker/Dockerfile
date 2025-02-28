FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Update apt repositories
RUN apt-get update

# Install system dependencies
RUN apt-get install -y --no-install-recommends \
    curl \
    gnupg \
    ca-certificates \
    git \
    cron \
    jq

# Install GitHub CLI
RUN curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg \
    && chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | tee /etc/apt/sources.list.d/github-cli.list > /dev/null \
    && apt-get update \
    && apt-get install -y gh

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create necessary directories
RUN mkdir -p /app/output /app/analysis /app/repos

# Keep root user to be able to set up cron jobs
# Note: In production environments, consider security implications, may need more complex setup

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Default command
CMD ["bash"]
