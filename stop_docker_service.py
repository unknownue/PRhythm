#!/usr/bin/env python3

# stop_docker_service.py - Simple script to stop PRhythm Docker service

import os
import sys
import subprocess
import argparse
from pathlib import Path

# Set color output
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
RED = '\033[0;31m'
NC = '\033[0m'  # No Color

# Script directory
SCRIPT_DIR = Path(__file__).parent.absolute()
os.chdir(SCRIPT_DIR)

def print_color(color, message):
    """Print colored message"""
    print(f"{color}{message}{NC}")

def display_usage():
    """Display usage information"""
    print_color(YELLOW, "Usage:")
    print("  python stop_docker_service.py [options]")
    print_color(YELLOW, "\nOptions:")
    print("  -h, --help    Display this help message")
    print("  -r, --remove  Remove container and volumes after stopping")

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

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Stop PRhythm Docker service", add_help=False)
    parser.add_argument('-h', '--help', action='store_true', help="Display help message")
    parser.add_argument('-r', '--remove', action='store_true', help="Remove container and volumes after stopping")
    
    args, unknown = parser.parse_known_args()
    
    if args.help:
        display_usage()
        sys.exit(0)
    
    if unknown:
        print_color(RED, f"Error: Unknown option(s): {' '.join(unknown)}")
        display_usage()
        sys.exit(1)
    
    # Check if Docker is running
    try:
        run_command(["docker", "info"], capture_output=True)
    except Exception:
        print_color(RED, "Error: Docker is not running. Cannot stop service.")
        sys.exit(1)
    
    # Check if container is running
    result = run_command("docker ps -q -f name=prhythm", shell=True, capture_output=True, check=False)
    container_running = result and result.stdout.strip()
    
    if not container_running:
        print_color(YELLOW, "PRhythm container is not running. Nothing to stop.")
        
        # Check if container exists but is stopped
        result = run_command("docker ps -a -q -f name=prhythm", shell=True, capture_output=True, check=False)
        container_exists = result and result.stdout.strip()
        
        if container_exists and args.remove:
            print_color(YELLOW, "Removing stopped container...")
            os.chdir(os.path.join(SCRIPT_DIR, "docker"))
            run_command("docker-compose rm -f", shell=True)
            print_color(GREEN, "Container successfully removed.")
        
        sys.exit(0)
    
    # Get current viewer port (for display information)
    result = run_command(
        "docker inspect --format='{{range $p, $conf := .NetworkSettings.Ports}}{{if eq $p \"9090/tcp\"}}{{(index $conf 0).HostPort}}{{end}}{{end}}' prhythm",
        shell=True,
        capture_output=True,
        check=False
    )
    
    viewer_port = "9090"  # Default port
    if result and result.stdout.strip():
        viewer_port = result.stdout.strip()
    
    # Stop Docker service
    print_color(YELLOW, "Stopping Docker service...")
    
    # Change to docker directory
    os.chdir(os.path.join(SCRIPT_DIR, "docker"))
    
    # Stop Docker container
    if args.remove:
        print_color(YELLOW, "Stopping and removing container...")
        run_command("docker-compose down -v", shell=True)
    else:
        run_command("docker-compose down", shell=True)
    
    # Check if container is stopped
    result = run_command("docker ps -q -f name=prhythm", shell=True, capture_output=True, check=False)
    if not result or not result.stdout.strip():
        print_color(GREEN, "Docker service successfully stopped!")
    else:
        print_color(RED, "Error: Failed to stop Docker service.")
        sys.exit(1)
    
    # Display status information
    print()
    print_color(GREEN, "PRhythm Docker service has been stopped.")
    print_color(YELLOW, f"The Markdown viewer at http://localhost:{viewer_port} is no longer available.")
    
    if args.remove:
        print_color(YELLOW, "Container and volumes have been removed.")
    else:
        print()
        print_color(YELLOW, "Useful commands:")
        print_color(GREEN, "  Start service again:")
        print("    python start_docker_service.py")
        print_color(GREEN, "  View generated reports:")
        print("    ls -la analysis")
    
    print()
    print_color(GREEN, "Done!")

if __name__ == "__main__":
    main() 