#!/usr/bin/env python3
"""
Example usage of the PRhythm GitHub PR Analysis tool.
"""

import asyncio
import json
import os
from dotenv import load_dotenv
from src.pr_analysis import analyze_pr, PRAnalysisConfiguration, AnalysisDepth, MockLLMMode

# Load environment variables from .env file
load_dotenv()


async def example_basic_analysis():
    """Example of basic PR analysis with mock LLM."""
    
    print("=== Basic PR Analysis Example ===")
    
    # Example repository and PR (using a real PR for demonstration)
    repo_url = "https://github.com/microsoft/TypeScript"
    pr_number = 62113  # Real PR for testing
    
    try:
        # Configure to use mock LLM for demonstration
        config = {
            "configurable": {
                "mock_llm_mode": MockLLMMode.REALISTIC,
                "mock_response_delay_seconds": 0.5,  # Faster for demo
                "github_token": os.getenv("GITHUB_TOKEN"),  # Set this environment variable
                "default_analysis_depth": AnalysisDepth.STANDARD
            }
        }
        
        print(f"Analyzing PR #{pr_number} from {repo_url}")
        print("Using mock LLM responses for demonstration...")
        print()
        
        # Run the analysis
        result = await analyze_pr(
            repository_url=repo_url,
            pr_number=pr_number,
            analysis_depth="standard",
            include_context=True,
            config=config
        )
        
        # Parse and display the results
        if result.analysis_report:
            try:
                report_data = json.loads(result.analysis_report)
                
                print("📊 ANALYSIS RESULTS")
                print("=" * 50)
                print()
                
                print("📋 Executive Summary:")
                print(report_data.get("executive_summary", "No summary available"))
                print()
                
                print("🏗️ Repository Overview:")
                print(report_data.get("repository_overview", "No overview available"))
                print()
                
                print("🔄 Changes Summary:")
                print(report_data.get("changes_summary", "No changes summary available"))
                print()
                
                print("⚠️ Risk Assessment:")
                print(report_data.get("risk_assessment", "No risk assessment available"))
                print()
                
                print("💡 Recommendations:")
                recommendations = report_data.get("recommendations", [])
                if recommendations:
                    for i, rec in enumerate(recommendations, 1):
                        print(f"  {i}. {rec}")
                else:
                    print("  No recommendations available")
                print()
                
                print("🎯 Conclusion:")
                print(report_data.get("conclusion", "No conclusion available"))
                print()
                
                # Show technical details if available
                technical_details = report_data.get("technical_details", {})
                if technical_details:
                    print("🔧 Technical Details:")
                    for key, value in technical_details.items():
                        print(f"  {key}: {value}")
                    print()
                
            except json.JSONDecodeError:
                print("Raw analysis report:")
                print(result.analysis_report)
        
        print("✅ Analysis completed successfully!")
        
        # Show metadata
        print("\n📋 Analysis Metadata:")
        for key, value in result.metadata.items():
            print(f"  {key}: {value}")
            
    except Exception as e:
        print(f"❌ Error during analysis: {str(e)}")
        print("\nTroubleshooting tips:")
        print("1. Make sure GITHUB_TOKEN environment variable is set")
        print("2. Verify the repository URL and PR number are correct")
        print("3. Check your internet connection")


async def example_quick_analysis():
    """Example of quick analysis for CI/CD pipeline."""
    
    print("\n=== Quick Analysis Example (CI/CD) ===")
    
    repo_url = "https://github.com/facebook/react"
    pr_number = 33999  # Real PR for testing
    
    try:
        # Quick analysis with minimal configuration
        result = await analyze_pr(
            repository_url=repo_url,
            pr_number=pr_number,
            analysis_depth="quick",
            include_context=False,  # Skip context for speed
            config={
                "configurable": {
                    "mock_llm_mode": MockLLMMode.SIMPLE,
                    "mock_response_delay_seconds": 0.1,
                    "github_token": os.getenv("GITHUB_TOKEN")
                }
            }
        )
        
        print(f"Quick analysis of PR #{pr_number}")
        
        if result.analysis_report:
            report_data = json.loads(result.analysis_report)
            print(f"Risk Level: {report_data.get('risk_assessment', 'Unknown')}")
            print(f"Recommendations: {len(report_data.get('recommendations', []))}")
            
        print("✅ Quick analysis completed!")
        
    except Exception as e:
        print(f"❌ Quick analysis failed: {str(e)}")


async def example_configuration_options():
    """Example showing different configuration options."""
    
    print("\n=== Configuration Options Example ===")
    
    # Create custom configuration
    config = PRAnalysisConfiguration(
        # GitHub settings
        github_token=os.getenv("GITHUB_TOKEN"),
        
        # Analysis settings
        default_analysis_depth=AnalysisDepth.DEEP,
        max_context_files=15,
        include_code_snippets=True,
        include_risk_assessment=True,
        include_recommendations=True,
        
        # Mock LLM settings (for development)
        mock_llm_mode=MockLLMMode.REALISTIC,
        mock_response_delay_seconds=0.8,
        
        # Storage settings
        repo_storage_path="./data/repos",
        analysis_cache_path="./data/analysis",
        report_output_path="./reports",
        
        # Model assignments (if using real LLMs)
        pr_supervisor_model="openai:gpt-4",
        repository_analyzer_model="openai:gpt-4-mini",
        diff_analyzer_model="openai:gpt-4",
        context_gatherer_model="openai:gpt-4-mini",
        report_generator_model="openai:gpt-4"
    )
    
    print("Configuration created:")
    print(f"  Analysis Depth: {config.default_analysis_depth.value}")
    print(f"  Mock LLM Mode: {config.mock_llm_mode.value}")
    print(f"  Max Context Files: {config.max_context_files}")
    print(f"  Include Code Snippets: {config.include_code_snippets}")
    print(f"  Report Format: {config.report_format}")


async def main():
    """Run all examples."""
    
    print("🎯 PRhythm - GitHub PR Analysis Tool Examples")
    print("=" * 60)
    
    if not os.getenv("GITHUB_TOKEN"):
        print("⚠️  Warning: GITHUB_TOKEN environment variable not set.")
        print("   The examples will use mock data for demonstration.")
        print("   Set GITHUB_TOKEN to analyze real repositories.")
        print()
    
    # Run examples
    await example_basic_analysis()
    await example_quick_analysis()
    await example_configuration_options()
    
    print("\n🚀 Examples completed!")
    print("\nNext steps:")
    print("1. Set GITHUB_TOKEN environment variable")
    print("2. Try analyzing a real PR:")
    print("   python example_pr_analysis.py")
    print("3. Use the CLI tool for more options:")
    print("   python -m src.pr_analysis.cli https://github.com/owner/repo 123")


if __name__ == "__main__":
    asyncio.run(main())