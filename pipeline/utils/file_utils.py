#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
File utilities for PRhythm.
This module provides unified file operations used across the project.
"""

import json
import os
import logging
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, Optional, Union

# Setup logger
logger = logging.getLogger("file_utils")

def ensure_directory(directory_path: Union[str, Path]) -> Path:
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

def get_project_root() -> Path:
    """
    Get project root directory
    
    Returns:
        Path: Project root directory
    """
    script_dir = Path(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    return script_dir

def save_json(data: Any, file_path: Union[str, Path], indent: int = 2) -> Path:
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
    
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=indent, ensure_ascii=False)
        logger.debug(f"Saved JSON data to {file_path}")
        return file_path
    except Exception as e:
        logger.error(f"Error saving JSON file {file_path}: {e}")
        raise

def load_json(file_path: Union[str, Path]) -> Dict[str, Any]:
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
    file_path = Path(file_path)
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        logger.debug(f"Loaded JSON data from {file_path}")
        return data
    except FileNotFoundError:
        logger.error(f"JSON file not found: {file_path}")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in file {file_path}: {e}")
        raise

def save_text(text: str, file_path: Union[str, Path]) -> Path:
    """
    Save text to a file
    
    Args:
        text: Text to save
        file_path: Path to the file
        
    Returns:
        Path: Path to the saved file
    """
    file_path = Path(file_path)
    ensure_directory(file_path.parent)
    
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(text)
        logger.debug(f"Saved text to {file_path}")
        return file_path
    except Exception as e:
        logger.error(f"Error saving text file {file_path}: {e}")
        raise

def read_text(file_path: Union[str, Path]) -> str:
    """
    Read text from a file
    
    Args:
        file_path: Path to the file
        
    Returns:
        str: File contents
        
    Raises:
        FileNotFoundError: If the file doesn't exist
    """
    file_path = Path(file_path)
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            text = f.read()
        logger.debug(f"Read text from {file_path}")
        return text
    except FileNotFoundError:
        logger.error(f"Text file not found: {file_path}")
        raise
    except Exception as e:
        logger.error(f"Error reading text file {file_path}: {e}")
        raise

def generate_output_path(output_dir: Path, repo: str, pr_number: Union[int, str], 
                         extension: str = "json", language: Optional[str] = None) -> Path:
    """
    Generate a standardized output file path
    
    Args:
        output_dir: Base output directory
        repo: Repository name (owner/repo)
        pr_number: PR number
        extension: File extension without dot (default: 'json')
        language: Language code for reports (optional)
        
    Returns:
        Path: Generated file path
    """
    # Extract repo name from owner/repo format
    repo_name = repo.split('/')[-1]
    
    # Get current date for month-based directory and naming
    now = datetime.now()
    month_dir = now.strftime('%Y-%m')  # Format: YYYY-MM
    date_str = now.strftime('%Y%m%d')
    
    # Create repository and month directory structure
    repo_month_dir = output_dir / repo_name / month_dir
    ensure_directory(repo_month_dir)
    
    # Create filename with language suffix if provided
    if language:
        filename = f"pr_{pr_number}_{language}_{date_str}.{extension}"
    else:
        filename = f"pr_{pr_number}_{date_str}.{extension}"
    
    return repo_month_dir / filename

def find_latest_file(directory: Union[str, Path], pattern: str) -> Optional[Path]:
    """
    Find the latest file matching a pattern in a directory
    
    Args:
        directory: Directory to search
        pattern: Glob pattern to match files
        
    Returns:
        Optional[Path]: Path to the latest file or None if no files found
    """
    directory = Path(directory)
    if not directory.exists() or not directory.is_dir():
        return None
        
    matching_files = list(directory.glob(pattern))
    if not matching_files:
        return None
        
    # Sort by modification time, newest first
    return sorted(matching_files, key=lambda x: x.stat().st_mtime, reverse=True)[0]

def find_all_files(directory: Union[str, Path], pattern: str) -> list[Path]:
    """
    Find all files matching a pattern in a directory
    
    Args:
        directory: Directory to search
        pattern: Glob pattern to match files
        
    Returns:
        list[Path]: List of matching file paths
    """
    directory = Path(directory)
    if not directory.exists() or not directory.is_dir():
        return []
        
    return list(directory.glob(pattern))
