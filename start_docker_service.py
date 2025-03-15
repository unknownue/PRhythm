#!/usr/bin/env python3
# start_docker_service.py - One-click script to start Docker service for PR report updates
# This script performs the following steps:
# 1. Check environment variables
# 2. Build and start Docker container
# 3. Optionally run an immediate update
# 4. Display status and usage information

import os
import sys
import subprocess
import argparse
import json
import shutil
from pathlib import Path

# Colors for output
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
RED = '\033[0;31m'
NC = '\033[0m'  # No Color

# Script directory
SCRIPT_DIR = Path(__file__).parent.absolute()
os.chdir(SCRIPT_DIR)

def print_color(color, message):
    """Print colored message"""
    print(f"{color}{message}\033[0m")

def command_exists(command):
    """Check if a command exists"""
    return shutil.which(command) is not None

def display_usage():
    """Display usage information"""
    print_color(YELLOW, "Usage:")
    print("  python start_docker_service.py [options]")
    print_color(YELLOW, "\nOptions:")
    print("  -h, --help       Display this help message")
    print("  -r, --run-now    Run an immediate update after starting the service")
    print("  -f, --force      Force rebuild Docker image")
    print("  -p, --port PORT  Specify a custom port for the Markdown viewer")
    print("  -s, --schedule SECONDS  Set interval in seconds for scheduled PR updates")
    print("  -g, --github-token TOKEN  Specify GitHub token directly")
    print("  -l, --llm-key KEY  Specify LLM API key directly")
    print("  -d, --deepseek-key KEY  Specify DeepSeek API key directly")
    print_color(YELLOW, "\nEnvironment Variables:")
    print("  GITHUB_TOKEN     GitHub API token (can also be set in config.json)")
    print("  LLM_API_KEY      LLM API key (can also be set in config.json)")
    print("  DEEPSEEK_API_KEY DeepSeek API key (can also be set in config.json)")
    print("  VIEWER_PORT      Port for the Markdown viewer (overrides config.json)")

def run_command(command, shell=False, check=True, capture_output=False):
    """Run a shell command and handle errors"""
    try:
        result = subprocess.run(
            command, 
            shell=shell, 
            check=check, 
            text=True, 
            capture_output=capture_output
        )
        return result
    except subprocess.CalledProcessError as e:
        print_color(RED, f"Error executing command: {e}")
        if capture_output and e.stderr:
            print_color(RED, f"Error details: {e.stderr}")
        return None

def check_prerequisites():
    """Check if all prerequisites are installed"""
    print_color(YELLOW, "Checking prerequisites...")
    
    # Check if Docker is installed
    if not command_exists("docker"):
        print_color(RED, "Error: Docker is not installed. Please install Docker first.")
        sys.exit(1)
    
    # Check if Docker Compose is installed
    if not command_exists("docker-compose"):
        print_color(RED, "Error: Docker Compose is not installed. Please install Docker Compose first.")
        sys.exit(1)
    
    # Check if Docker daemon is running
    try:
        run_command(["docker", "info"], capture_output=True)
    except Exception:
        print_color(RED, "Error: Docker daemon is not running. Please start Docker first.")
        sys.exit(1)

def check_config_file():
    """Check if config.json exists, if not create it from example"""
    if not os.path.isfile("config.json"):
        print_color(YELLOW, "Creating config.json from config.example.json...")
        if os.path.isfile("config.example.json"):
            shutil.copy("config.example.json", "config.json")
            print_color(YELLOW, "Please edit config.json with your actual values.")
            sys.exit(1)
        else:
            print_color(RED, "Error: config.example.json file not found. Please create config.json file manually.")
            sys.exit(1)

def read_token_from_config(token_path):
    """
    Read token from config.json using a path specification
    
    Args:
        token_path: List of keys to navigate to the token in the config
                   e.g. ['github', 'token'] or ['llm', 'api_key']
    
    Returns:
        The token string if found and valid, None otherwise
    """
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
        
        # Navigate through the config dictionary using the path
        current = config
        for key in token_path:
            if key in current:
                current = current[key]
            else:
                return None
        
        # Check if token is valid
        if isinstance(current, str) and current.strip():
            return current.strip()
    except Exception as e:
        print(f"Error reading config: {e}", file=sys.stderr)
    
    return None

def get_viewer_port_from_config():
    """Get viewer port from config.json"""
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
        
        if 'viewer' in config and 'port' in config['viewer']:
            return str(config['viewer']['port'])
    except Exception:
        pass
    
    return "9090"  # Default port

def update_config_with_port(port):
    """Update config.json with the custom port"""
    try:
        with open('config.json', 'r') as f:
            config = json.load(f) or {}
        
        if 'viewer' not in config:
            config['viewer'] = {'enabled': True, 'port': int(port), 'debug': False}
        else:
            config['viewer']['port'] = int(port)
            
            # Remove analysis_dir from viewer if it exists (now using paths.analysis_dir)
            if 'analysis_dir' in config['viewer']:
                del config['viewer']['analysis_dir']
        
        with open('config.json', 'w') as f:
            json.dump(config, f, indent=2)
        
        return True
    except Exception as e:
        print(f"Error updating config: {e}", file=sys.stderr)
        return False

def check_port_in_use(port):
    """Check if the port is already in use"""
    if not command_exists("lsof"):
        return False
    
    try:
        result = subprocess.run(
            f"lsof -i:{port}", 
            shell=True, 
            capture_output=True, 
            text=True
        )
        return result.returncode == 0
    except Exception:
        return False

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Start Docker service for PR report updates", add_help=False)
    parser.add_argument('-h', '--help', action='store_true', help="Display help message")
    parser.add_argument('-r', '--run-now', action='store_true', help="Run an immediate update after starting the service")
    parser.add_argument('-f', '--force', action='store_true', help="Force rebuild Docker image")
    parser.add_argument('-p', '--port', type=str, help="Specify a custom port for the Markdown viewer")
    parser.add_argument('-s', '--schedule', type=str, help="Set interval in seconds for scheduled PR updates")
    parser.add_argument('-g', '--github-token', type=str, help="Specify GitHub token directly")
    parser.add_argument('-l', '--llm-key', type=str, help="Specify LLM API key directly")
    parser.add_argument('-d', '--deepseek-key', type=str, help="Specify DeepSeek API key directly")
    
    args, unknown = parser.parse_known_args()
    
    if args.help:
        display_usage()
        sys.exit(0)
    
    if unknown:
        print_color(RED, f"Error: Unknown option(s): {' '.join(unknown)}")
        display_usage()
        sys.exit(1)
    
    # Check prerequisites
    check_prerequisites()
    
    # Check environment variables
    print_color(YELLOW, "Checking environment variables...")
    
    # Check if config.json file exists
    check_config_file()
    
    # Define token configurations
    token_configs = [
        {
            'name': 'GitHub token',
            'env_var': 'GITHUB_TOKEN',
            'config_path': ['github', 'token'],
            'arg_value': args.github_token
        },
        {
            'name': 'LLM API key',
            'env_var': 'LLM_API_KEY',
            'config_path': ['llm', 'providers', 'openai', 'api_key'],
            'arg_value': args.llm_key
        },
        {
            'name': 'DeepSeek API key',
            'env_var': 'DEEPSEEK_API_KEY',
            'config_path': ['llm', 'providers', 'deepseek', 'api_key'],
            'arg_value': args.deepseek_key
        }
    ]
    
    # Process each token
    tokens = {}
    for config in token_configs:
        env_var = config['env_var']
        token_value = os.environ.get(env_var)
        
        # Read from config.json if not set in environment and not provided as argument
        if not token_value and not config['arg_value']:
            print_color(YELLOW, f"Attempting to read {config['name']} from config.json...")
            config_token = read_token_from_config(config['config_path'])
            if config_token:
                os.environ[env_var] = config_token
                token_value = config_token
                print_color(YELLOW, f"Using {config['name']} from config.json")
            else:
                # For LLM API key, try to get from the current provider
                if env_var == 'LLM_API_KEY':
                    # Get current provider
                    provider = read_token_from_config(['llm', 'provider'])
                    if provider:
                        provider_api_key = read_token_from_config(['llm', 'providers', provider, 'api_key'])
                        if provider_api_key:
                            os.environ[env_var] = provider_api_key
                            token_value = provider_api_key
                            print_color(YELLOW, f"Using {config['name']} from current provider ({provider}) in config.json")
                        else:
                            print_color(YELLOW, f"No valid {config['name']} found for provider {provider} in config.json")
                    else:
                        print_color(YELLOW, f"No valid provider found in config.json")
                else:
                    print_color(YELLOW, f"No valid {config['name']} found in config.json")
        
        # Use command line value if provided
        if config['arg_value']:
            os.environ[env_var] = config['arg_value']
            token_value = config['arg_value']
            print_color(YELLOW, f"Using {config['name']} from command line")
        
        tokens[env_var] = token_value
    
    # Check required environment variables
    if not tokens['GITHUB_TOKEN']:
        print_color(RED, "Error: GITHUB_TOKEN is not set.")
        print_color(YELLOW, "Please set it in config.json, as an environment variable, or use --github-token option.")
        sys.exit(1)
    
    if not tokens['LLM_API_KEY']:
        print_color(RED, "Error: LLM_API_KEY is not set.")
        provider = read_token_from_config(['llm', 'provider'])
        if provider:
            print_color(YELLOW, f"Please set it in config.json under llm.providers.{provider}.api_key, as an environment variable, or use --llm-key option.")
        else:
            print_color(YELLOW, "Please set it in config.json under llm.providers.[provider].api_key, as an environment variable, or use --llm-key option.")
        sys.exit(1)
    
    # Get viewer port
    config_port = get_viewer_port_from_config()
    
    # Use custom port if specified
    if args.port:
        if not args.port.isdigit():
            print_color(RED, "Error: --port requires a valid port number")
            sys.exit(1)
        
        print_color(YELLOW, f"Using custom port: {args.port}")
        os.environ['VIEWER_PORT'] = args.port
        viewer_port = args.port
        
        # Update config.json with the custom port
        update_config_with_port(args.port)
    else:
        # Use port from config.json
        print_color(YELLOW, f"Using port from config.json: {config_port}")
        os.environ['VIEWER_PORT'] = config_port
        viewer_port = config_port
    
    # Check if port is already in use
    if check_port_in_use(viewer_port):
        print_color(RED, f"Error: Port {viewer_port} is already in use.")
        print_color(YELLOW, "You can specify a different port with --port option or by changing the viewer.port value in config.json.")
        print_color(YELLOW, "Alternatively, you can run:")
        print("  ./viewer/change_port.sh <new_port>")
        sys.exit(1)
    
    # Start Docker service
    print_color(YELLOW, f"Starting Docker service with port {viewer_port}...")
    
    # Change to docker directory
    os.chdir(os.path.join(SCRIPT_DIR, "docker"))
    
    # Build and start Docker container
    if args.force:
        print_color(YELLOW, "Forcing rebuild of Docker image...")
        run_command(f"VIEWER_PORT={viewer_port} docker-compose build --no-cache", shell=True)
    
    # Start Docker container with the specified port
    run_command(f"VIEWER_PORT={viewer_port} docker-compose up -d", shell=True)
    
    # Check if container is running
    result = run_command("docker ps -q -f name=prhythm", shell=True, capture_output=True)
    if result and result.stdout.strip():
        print_color(GREEN, "Docker service started successfully!")
    else:
        print_color(RED, "Error: Failed to start Docker service.")
        print_color(YELLOW, "Check Docker logs for more information:")
        print("  docker logs prhythm")
        sys.exit(1)
    
    # Run immediate update if requested
    if args.run_now:
        print_color(YELLOW, "Running immediate update...")
        if args.schedule:
            print_color(YELLOW, f"Starting scheduled updates with interval of {args.schedule} seconds...")
            run_command(f"docker exec -it prhythm python /app/pipeline/update_pr_reports.py --schedule {args.schedule}", shell=True)
        else:
            run_command("docker exec -it prhythm python /app/pipeline/update_pr_reports.py", shell=True)
    elif args.schedule:
        print_color(YELLOW, f"Starting scheduled updates with interval of {args.schedule} seconds...")
        run_command(f"docker exec -d prhythm bash -c \"nohup python /app/pipeline/update_pr_reports.py --schedule {args.schedule} > /app/update_log.txt 2>&1 &\"", shell=True)
        print_color(YELLOW, "Updates are running in background. Check logs with:")
        print("  docker exec prhythm cat /app/update_log.txt")
    
    # Display status and usage information
    print()
    print_color(GREEN, "PRhythm Docker service is now running!")
    if args.schedule:
        print_color(YELLOW, f"PR updates are scheduled to run every {args.schedule} seconds.")
    else:
        print_color(YELLOW, "You need to manually run updates when needed.")
    print_color(YELLOW, f"Markdown viewer is available at: http://localhost:{viewer_port}")
    
    print()
    print_color(YELLOW, "Useful commands:")
    print_color(GREEN, "  View logs:")
    print("    docker logs -f prhythm")
    print_color(GREEN, "  Run manual update:")
    if args.schedule:
        print("    docker exec prhythm cat /app/update_log.txt  # View scheduled update logs")
    else:
        print("    docker exec -it prhythm python /app/pipeline/update_pr_reports.py")
        print("    docker exec -it prhythm python /app/pipeline/update_pr_reports.py --schedule 3600  # Run hourly")
    print_color(GREEN, "  Stop service:")
    print("    cd docker && docker-compose down")
    print_color(GREEN, "  View generated reports:")
    print("    ls -la analysis")
    print_color(GREEN, "  Change viewer port:")
    print("    ./viewer/change_port.sh <new_port>")
    
    print()
    print_color(GREEN, "Done!")

if __name__ == "__main__":
    main() 