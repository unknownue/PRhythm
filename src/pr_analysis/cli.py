#!/usr/bin/env python3
"""
Command Line Interface for PRhythm - GitHub PR Analysis Tool
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Optional

from .pr_analyzer import analyze_pr
from .configuration import PRAnalysisConfiguration, AnalysisDepth, MockLLMMode


def setup_argument_parser():
    """Set up command line argument parser."""
    
    parser = argparse.ArgumentParser(
        description="PRhythm - Analyze GitHub Pull Requests using multi-agent AI system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze a PR with default settings
  python -m pr_analysis.cli https://github.com/owner/repo 123

  # Deep analysis with real LLM
  python -m pr_analysis.cli https://github.com/owner/repo 123 --depth deep --no-mock

  # Quick analysis for CI/CD pipeline  
  python -m pr_analysis.cli https://github.com/owner/repo 123 --depth quick --output report.json

  # Use mock responses for development
  python -m pr_analysis.cli https://github.com/owner/repo 123 --mock realistic
        """
    )
    
    # Required arguments
    parser.add_argument(
        "repository_url", 
        help="GitHub repository URL (e.g., https://github.com/owner/repo)"
    )
    parser.add_argument(
        "pr_number",
        type=int,
        help="Pull request number to analyze"
    )
    
    # Analysis options
    parser.add_argument(
        "--depth", "-d",
        choices=["quick", "standard", "deep"],
        default="standard",
        help="Analysis depth (default: standard)"
    )
    parser.add_argument(
        "--no-context",
        action="store_true",
        help="Skip context gathering (faster but less comprehensive)"
    )
    
    # Output options
    parser.add_argument(
        "--output", "-o",
        help="Output file path (default: stdout)"
    )
    parser.add_argument(
        "--format", "-f",
        choices=["markdown", "json", "html"],
        default="markdown",
        help="Output format (default: markdown)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output with debug information"
    )
    
    # Mock LLM options (for development)
    parser.add_argument(
        "--mock",
        choices=["disabled", "simple", "realistic", "mixed"],
        default="simple",
        help="Mock LLM mode for development/testing (default: simple)"
    )
    parser.add_argument(
        "--no-mock",
        action="store_true",
        help="Disable mock LLM and use real API calls"
    )
    parser.add_argument(
        "--mock-delay",
        type=float,
        default=1.0,
        help="Artificial delay for mock responses in seconds (default: 1.0)"
    )
    
    # Configuration
    parser.add_argument(
        "--github-token",
        help="GitHub API token (can also use GITHUB_TOKEN env var)"
    )
    parser.add_argument(
        "--config",
        help="Path to configuration file (JSON)"
    )
    
    return parser


def load_config(args) -> PRAnalysisConfiguration:
    """Load configuration from arguments and config file."""
    
    config_data = {}
    
    # Load from config file if provided
    if args.config:
        config_path = Path(args.config)
        if config_path.exists():
            with open(config_path) as f:
                config_data = json.load(f)
        else:
            print(f"Warning: Config file not found: {config_path}", file=sys.stderr)
    
    # Override with command line arguments
    if args.github_token:
        config_data["github_token"] = args.github_token
    
    if args.no_mock:
        config_data["mock_llm_mode"] = MockLLMMode.DISABLED
    else:
        config_data["mock_llm_mode"] = MockLLMMode(args.mock)
    
    config_data["mock_response_delay_seconds"] = args.mock_delay
    config_data["default_analysis_depth"] = AnalysisDepth(args.depth)
    config_data["report_format"] = args.format
    
    return PRAnalysisConfiguration(**config_data)


def format_output(analysis_result, format_type: str, verbose: bool = False) -> str:
    """Format analysis result for output."""
    
    if format_type == "json":
        if verbose:
            return json.dumps({
                "analysis_report": json.loads(analysis_result.analysis_report),
                "metadata": analysis_result.metadata,
                "pr_info": analysis_result.pr,
                "repository_context": analysis_result.repository_context,
                "diff_info": analysis_result.diff
            }, indent=2, default=str)
        else:
            return analysis_result.analysis_report
    
    elif format_type == "html":
        # Basic HTML formatting
        report_data = json.loads(analysis_result.analysis_report)
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>{report_data.get('title', 'PR Analysis Report')}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .section {{ margin: 20px 0; }}
        .risk-high {{ color: #d73a49; }}
        .risk-medium {{ color: #f66a0a; }}
        .risk-low {{ color: #28a745; }}
        pre {{ background: #f6f8fa; padding: 10px; border-radius: 5px; }}
    </style>
</head>
<body>
    <h1>{report_data.get('title', 'PR Analysis Report')}</h1>
    
    <div class="section">
        <h2>Executive Summary</h2>
        <p>{report_data.get('executive_summary', 'No summary available')}</p>
    </div>
    
    <div class="section">
        <h2>Repository Overview</h2>
        <p>{report_data.get('repository_overview', 'No overview available')}</p>
    </div>
    
    <div class="section">
        <h2>Changes Summary</h2>
        <p>{report_data.get('changes_summary', 'No changes summary available')}</p>
    </div>
    
    <div class="section">
        <h2>Impact Analysis</h2>
        <p>{report_data.get('impact_analysis', 'No impact analysis available')}</p>
    </div>
    
    <div class="section">
        <h2>Risk Assessment</h2>
        <p>{report_data.get('risk_assessment', 'No risk assessment available')}</p>
    </div>
    
    <div class="section">
        <h2>Recommendations</h2>
        <ul>
"""
        for rec in report_data.get('recommendations', []):
            html += f"            <li>{rec}</li>\n"
        
        html += f"""        </ul>
    </div>
    
    <div class="section">
        <h2>Conclusion</h2>
        <p>{report_data.get('conclusion', 'No conclusion available')}</p>
    </div>
    
    <footer>
        <p><small>Generated by PRhythm at {analysis_result.generated_at}</small></p>
    </footer>
</body>
</html>
"""
        return html
    
    else:  # markdown (default)
        report_data = json.loads(analysis_result.analysis_report)
        markdown = f"""# {report_data.get('title', 'PR Analysis Report')}

## Executive Summary

{report_data.get('executive_summary', 'No summary available')}

## Repository Overview  

{report_data.get('repository_overview', 'No overview available')}

## Changes Summary

{report_data.get('changes_summary', 'No changes summary available')}

## Impact Analysis

{report_data.get('impact_analysis', 'No impact analysis available')}

## Risk Assessment

{report_data.get('risk_assessment', 'No risk assessment available')}

## Recommendations

"""
        for rec in report_data.get('recommendations', []):
            markdown += f"- {rec}\n"
        
        markdown += f"""
## Conclusion

{report_data.get('conclusion', 'No conclusion available')}

---

*Generated by PRhythm at {analysis_result.generated_at}*
"""
        
        if verbose:
            markdown += f"""

## Technical Details

```json
{json.dumps(report_data.get('technical_details', {}), indent=2)}
```

## Metadata

```json
{json.dumps(analysis_result.metadata, indent=2, default=str)}
```
"""
        
        return markdown


async def main():
    """Main CLI function."""
    
    parser = setup_argument_parser()
    args = parser.parse_args()
    
    try:
        # Load configuration
        config = load_config(args)
        
        if args.verbose:
            print(f"Analyzing PR #{args.pr_number} from {args.repository_url}", file=sys.stderr)
            print(f"Analysis depth: {args.depth}", file=sys.stderr)
            print(f"Mock mode: {config.mock_llm_mode.value}", file=sys.stderr)
        
        # Run analysis
        result = await analyze_pr(
            repository_url=args.repository_url,
            pr_number=args.pr_number,
            analysis_depth=args.depth,
            include_context=not args.no_context,
            config={"configurable": config.model_dump()}
        )
        
        # Format output
        output = format_output(result, args.format, args.verbose)
        
        # Write output
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(output)
            if args.verbose:
                print(f"Report written to: {args.output}", file=sys.stderr)
        else:
            print(output)
            
    except KeyboardInterrupt:
        print("\nAnalysis cancelled by user", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())