#!/usr/bin/env python3
"""
PRhythm main entry point.
"""

import argparse
import sys
import os
from pathlib import Path

# Add src and tests to path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir / 'src'))
sys.path.insert(0, str(current_dir / 'tests'))

from test_llm_connection import test_llm_connection


def main():
    """Main entry point for PRhythm system."""
    
    parser = argparse.ArgumentParser(
        description="PRhythm - GitHub PR Analysis System",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '--test_llm_connection',
        action='store_true',
        help='Test basic LLM connection with a hello world message'
    )
    
    parser.add_argument(
        '--test_llm_model',
        type=str,
        default=None,
        help='Specify LLM provider for connection test (e.g., openai, anthropic, google, ollama)'
    )
    
    args = parser.parse_args()
    
    # Handle test LLM connection
    if args.test_llm_connection:
        print("=" * 50)
        print("PRhythm LLM Connection Test")
        print("=" * 50)
        
        success = test_llm_connection(model_override=args.test_llm_model)
        
        print("=" * 50)
        if success:
            print("Test Result: ✅ Success")
            return 0
        else:
            print("Test Result: ❌ Failed")
            return 1
    
    # If no arguments provided, show help
    if len(sys.argv) == 1:
        parser.print_help()
        return 0
    
    return 0


if __name__ == "__main__":
    sys.exit(main())