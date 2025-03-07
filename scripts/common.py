#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Common utilities for PRhythm scripts.
This module contains shared functionality used across multiple scripts in the PRhythm project.
"""

import json
import os
import sys
import logging
import subprocess
import time
import re
from pathlib import Path
from datetime import datetime

# Setup global logger
logger = logging.getLogger("PRhythm")

def setup_logging(script_name, log_level=logging.INFO, log_to_file=True):
    """
    Setup standardized logging for scripts
    
    Args:
        script_name: Name of the script (used for the logger and log file name)
        log_level: Logging level (default: INFO)
        log_to_file: Whether to log to a file (default: True)
        
    Returns:
        logger: Configured logger
    """
    logger = logging.getLogger(script_name)
    logger.setLevel(log_level)
    
    # Clear existing handlers
    if logger.hasHandlers():
        logger.handlers.clear()
    
    # Create formatters
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler (optional)
    if log_to_file:
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / f"{script_name}_{datetime.now().strftime('%Y%m%d')}.log"
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger

def read_config(config_path):
    """
    Read configuration file and return its contents
    
    Args:
        config_path: Path to the configuration file
        
    Returns:
        dict: Configuration data
        
    Raises:
        RuntimeError: If the configuration file cannot be read
    """
    try:
        with open(config_path, 'r') as file:
            config = json.load(file)
            return config
    except Exception as e:
        raise RuntimeError(f"Error reading configuration file: {e}")

def get_project_root():
    """
    Get project root directory
    
    Returns:
        Path: Project root directory
    """
    script_dir = Path(os.path.dirname(os.path.abspath(__file__)))
    return script_dir.parent

def ensure_directory(directory_path):
    """
    Ensure that a directory exists, creating it if necessary
    
    Args:
        directory_path: Path to the directory
        
    Returns:
        Path: Path to the directory
    """
    directory = Path(directory_path)
    directory.mkdir(parents=True, exist_ok=True)
    return directory

def run_command(cmd, timeout=60, check=True, capture_output=True):
    """
    Run a shell command with timeout
    
    Args:
        cmd: Command to run (string or list)
        timeout: Timeout in seconds (default: 60)
        check: Raise exception if command fails (default: True)
        capture_output: Capture stdout and stderr (default: True)
        
    Returns:
        CompletedProcess: Result of subprocess.run
        
    Raises:
        TimeoutError: If the command times out
        RuntimeError: If the command fails and check=True
    """
    try:
        return subprocess.run(
            cmd, 
            shell=isinstance(cmd, str),
            check=check, 
            capture_output=capture_output, 
            text=True,
            timeout=timeout
        )
    except subprocess.TimeoutExpired:
        raise TimeoutError(f"Command timed out after {timeout} seconds: {cmd}")
    except subprocess.CalledProcessError as e:
        if check:
            raise RuntimeError(f"Command failed with exit code {e.returncode}: {e.stderr}")
        return e

def retry_operation(operation, max_retries=3, retry_delay=5, exceptions=(Exception,)):
    """
    Retry an operation with exponential backoff
    
    Args:
        operation: Function to call
        max_retries: Maximum number of retries (default: 3)
        retry_delay: Initial retry delay in seconds (default: 5)
        exceptions: Exceptions to catch and retry (default: all exceptions)
        
    Returns:
        Result of the operation
        
    Raises:
        The last exception if all retries fail
    """
    for attempt in range(max_retries):
        try:
            return operation()
        except exceptions as e:
            if attempt == max_retries - 1:
                raise
            wait_time = retry_delay * (2 ** attempt)
            logger.warning(f"Operation failed: {e}. Retrying in {wait_time} seconds...")
            time.sleep(wait_time)

def validate_repo_url(repo_url):
    """
    Validate and normalize repository URL to owner/repo format
    
    Args:
        repo_url: Repository URL or owner/repo string
        
    Returns:
        str: Repository in owner/repo format
        
    Raises:
        ValueError: If the repository URL is invalid
    """
    if re.match(r'^[^/]+/[^/]+$', repo_url):
        return repo_url
    
    match = re.search(r'github\.com[:/]([^/]+/[^/]+?)(?:\.git)?/?$', repo_url)
    if match:
        return match.group(1)
    
    raise ValueError(f"Invalid repository format: {repo_url}. Expected format: owner/repo or GitHub URL")

def get_path_from_config(config, path_key, default_path, project_root=None):
    """
    Get absolute path from config, handling relative paths
    
    Args:
        config: Configuration dictionary
        path_key: Key in the config paths section
        default_path: Default path if not found in config
        project_root: Project root directory (default: current project root)
        
    Returns:
        Path: Absolute path
    """
    if project_root is None:
        project_root = get_project_root()
        
    path_str = config.get('paths', {}).get(path_key, default_path)
    
    path = Path(path_str)
    if not path.is_absolute():
        path = project_root / path
        
    return path

def save_json(data, file_path, indent=2):
    """
    Save data to a JSON file
    
    Args:
        data: Data to save
        file_path: Path to the file
        indent: JSON indentation (default: 2)
        
    Returns:
        Path: Path to the saved file
    """
    file_path = Path(file_path)
    ensure_directory(file_path.parent)
    
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=indent)
        
    return file_path

def load_json(file_path):
    """
    Load data from a JSON file
    
    Args:
        file_path: Path to the file
        
    Returns:
        dict: Loaded data
        
    Raises:
        FileNotFoundError: If the file doesn't exist
        json.JSONDecodeError: If the file contains invalid JSON
    """
    with open(file_path, 'r') as f:
        return json.load(f) 