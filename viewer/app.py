#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Markdown Viewer for PR Analysis Reports
---------------------------------------
A simple Flask application to view Markdown files in the analysis directory.
This viewer supports code highlighting, image display, and navigation between files.

Configuration:
- All settings are read from config.yaml in the 'viewer' section
- Environment variables can override config.yaml settings
- Command line arguments can be passed via start_docker_service.sh
"""

from flask import Flask, render_template, abort, send_from_directory
import markdown
from markdown.extensions.codehilite import CodeHiliteExtension
import os
import pygments
from pygments.formatters import HtmlFormatter
import datetime
import json
import re

app = Flask(__name__)

# Path to the analysis directory
ANALYSIS_DIR = os.environ.get('ANALYSIS_DIR', os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'analysis'))

# Check if we're running in Docker
if os.path.exists('/app/analysis'):
    ANALYSIS_DIR = '/app/analysis'

print(f"Using analysis directory: {ANALYSIS_DIR}")

# Load configuration
def load_config():
    """Load configuration from config.json file."""
    config_path = os.path.join('/app', 'config.json')
    default_config = {
        'viewer': {
            'enabled': True,
            'port': 9090,
            'debug': False,
            'analysis_dir': './analysis'
        }
    }
    
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            # Ensure viewer config exists
            if 'viewer' not in config:
                config['viewer'] = default_config['viewer']
            elif 'analysis_dir' not in config['viewer']:
                config['viewer']['analysis_dir'] = default_config['viewer']['analysis_dir']
                
            # Update ANALYSIS_DIR from config if specified
            global ANALYSIS_DIR
            config_analysis_dir = config['viewer'].get('analysis_dir')
            if config_analysis_dir:
                # Handle relative paths
                if not os.path.isabs(config_analysis_dir):
                    if os.path.exists('/app'):  # Docker environment
                        config_analysis_dir = os.path.join('/app', config_analysis_dir)
                    else:
                        config_analysis_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), config_analysis_dir)
                
                if os.path.exists(config_analysis_dir):
                    ANALYSIS_DIR = config_analysis_dir
                    print(f"Using analysis directory from config: {ANALYSIS_DIR}")
                
            return config
        except Exception as e:
            print(f"Error loading config: {e}")
            return default_config
    else:
        print(f"Config file not found at {config_path}, using defaults")
        return default_config

# Configure Markdown extensions with improved code block handling
markdown_extensions = [
    'markdown.extensions.fenced_code',  # Support for fenced code blocks
    CodeHiliteExtension(
        guess_lang=False,        # Disable language guessing
        use_pygments=True,       # Use Pygments for syntax highlighting
        css_class='codehilite',  # CSS class for code blocks
        pygments_style='default' # Pygments style
    ),
    'markdown.extensions.tables',       # Support for tables
    'markdown.extensions.toc'           # Table of contents
]

# Function to preprocess Markdown content
def preprocess_markdown(content):
    """
    Preprocess Markdown content to fix common issues with code blocks.
    """
    # Remove leading ```markdown if present at the beginning of the file
    content = re.sub(r'^```markdown\s*\n', '', content)
    
    # Fix code blocks with language specifiers
    # Replace ```rust\n with ```rust\n to ensure proper language detection
    content = re.sub(r'```(\w+)\s*\n', r'```\1\n', content)
    
    # Ensure code blocks are properly closed
    # Count opening and closing code fences
    opens = len(re.findall(r'```\w*\s*\n', content))
    closes = len(re.findall(r'```\s*\n', content))
    
    # Add missing closing fences if needed
    if opens > closes:
        content += '\n```\n' * (opens - closes)
    
    return content

@app.route('/')
def index():
    """Display a list of all available Markdown files in the analysis directory."""
    files = []
    
    # Walk through the analysis directory and its subdirectories
    for root, dirs, filenames in os.walk(ANALYSIS_DIR):
        for filename in filenames:
            if filename.endswith('.md'):
                # Calculate relative path from ANALYSIS_DIR
                rel_path = os.path.relpath(os.path.join(root, filename), ANALYSIS_DIR)
                # Get last modification time
                mod_time = os.path.getmtime(os.path.join(root, filename))
                # Format the modification time
                mod_time_str = datetime.datetime.fromtimestamp(mod_time).strftime('%Y-%m-%d %H:%M:%S')
                
                # Parse path components
                path_parts = rel_path.split('/')
                
                # Get repository name and month from path
                repo_name = path_parts[0] if len(path_parts) > 0 else 'unknown'
                month_dir = path_parts[1] if len(path_parts) > 1 and re.match(r'\d{4}-\d{2}', path_parts[1]) else None
                
                files.append({
                    'path': rel_path,
                    'name': filename,
                    'repo': repo_name,
                    'month': month_dir,
                    'modified': mod_time,
                    'modified_str': mod_time_str
                })
    
    # Sort files by modification time (newest first)
    files.sort(key=lambda x: x['modified'], reverse=True)
    
    # Group files by repository and month
    repos = {}
    for file in files:
        repo = file['repo']
        month = file['month'] or 'other'
        
        if repo not in repos:
            repos[repo] = {}
        
        if month not in repos[repo]:
            repos[repo][month] = []
            
        repos[repo][month].append(file)
    
    return render_template('index.html', files=files, repos=repos, grouped=True)

@app.route('/view/<path:file_path>')
def view_file(file_path):
    """Render a specific Markdown file as HTML."""
    full_path = os.path.join(ANALYSIS_DIR, file_path)
    
    # Check if file exists
    if not os.path.exists(full_path) or not os.path.isfile(full_path):
        abort(404)
    
    try:
        # Read the Markdown file
        with open(full_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Preprocess the Markdown content
        content = preprocess_markdown(content)
            
        # Render Markdown to HTML
        html_content = markdown.markdown(content, extensions=markdown_extensions)
        
        # Get file list for navigation sidebar
        files = []
        for root, dirs, filenames in os.walk(ANALYSIS_DIR):
            for filename in filenames:
                if filename.endswith('.md'):
                    rel_path = os.path.relpath(os.path.join(root, filename), ANALYSIS_DIR)
                    # Get repository name from path
                    repo_name = rel_path.split('/')[0] if '/' in rel_path else 'unknown'
                    
                    files.append({
                        'path': rel_path,
                        'name': filename,
                        'repo': repo_name,
                        'active': rel_path == file_path
                    })
        
        # Group files by repository
        repos = {}
        for file in files:
            repo = file['repo']
            if repo not in repos:
                repos[repo] = []
            repos[repo].append(file)
        
        return render_template('view.html', 
                              content=html_content, 
                              file_path=file_path,
                              repos=repos)
    except Exception as e:
        return f"Error rendering file: {str(e)}", 500

@app.route('/images/<path:image_path>')
def serve_image(image_path):
    """Serve image files from the analysis directory."""
    image_dir = os.path.join(ANALYSIS_DIR, os.path.dirname(image_path))
    filename = os.path.basename(image_path)
    return send_from_directory(image_dir, filename)

@app.route('/static/<path:path>')
def serve_static(path):
    """Serve static files."""
    return send_from_directory('static', path)

if __name__ == '__main__':
    # Generate Pygments CSS for code highlighting
    formatter = HtmlFormatter(style='default')
    css_path = os.path.join(os.path.dirname(__file__), 'static', 'pygments.css')
    with open(css_path, 'w') as f:
        f.write(formatter.get_style_defs('.codehilite'))
    
    # Load configuration
    config = load_config()
    
    # Get port from config, environment variable, or use default
    port = int(os.environ.get('VIEWER_PORT', config['viewer']['port']))
    debug = os.environ.get('VIEWER_DEBUG', str(config['viewer']['debug'])).lower() in ('true', '1', 'yes')
    
    print(f"Starting Markdown viewer on http://0.0.0.0:{port}")
    
    # Run the Flask application
    app.run(host='0.0.0.0', port=port, debug=debug) 