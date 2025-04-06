"""
Code Analyzer Agent for PR context extraction.
This agent analyzes code structure, logic, and patterns.
"""

import logging
from typing import Any, Dict, List
from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI

from .base_agent import BaseAgent

# Setup logger
logger = logging.getLogger("code_analyzer_agent")

# Define the code analyzer agent prompt template
CODE_ANALYZER_PROMPT = """
You are the Code Analyzer Agent responsible for analyzing code structure, logic, and patterns.
Your goal is to understand the code and provide insightful analysis.

For this task, you need to:
1. Analyze the code structure (functions, classes, etc.)
2. Identify execution logic and control flow
3. Recognize code patterns and design principles
4. Provide insights on code quality

Think step by step to analyze the code thoroughly.

Question: {question}

{format_instructions}
"""

class CodeAnalyzerAgent(BaseAgent):
    """
    Code Analyzer Agent that analyzes code structure, logic, and patterns.
    This agent identifies functions, classes, execution logic, etc.
    """
    
    def __init__(self, llm_provider, tools, repo_path):
        """
        Initialize the code analyzer agent.
        
        Args:
            llm_provider: LLM provider to use
            tools: List of tools this agent can use
            repo_path: Path to the repository
        """
        super().__init__(llm_provider, tools, "CodeAnalyzerAgent")
        self.repo_path = repo_path
        
        # Create prompt template
        self.prompt_template = PromptTemplate(
            template=CODE_ANALYZER_PROMPT,
            input_variables=["question"],
            partial_variables={"format_instructions": ""}
        )
    
    def _get_langchain_llm(self):
        """Get a LangChain LLM wrapper for the provider."""
        # Convert the PRhythm provider to a LangChain LLM
        return ChatOpenAI(
            model=self.llm_provider.model,
            temperature=self.llm_provider.temperature,
            api_key=self.llm_provider.api_key,
            base_url=self.llm_provider.base_url
        )
    
    def analyze_code(self, code_segment: str, file_path: str = None, language: str = None) -> Dict[str, Any]:
        """
        Analyze a code segment to understand its structure and patterns.
        
        Args:
            code_segment: Code text to analyze
            file_path: Optional path to the file containing the code
            language: Optional programming language of the code
            
        Returns:
            Dict[str, Any]: Analysis results
        """
        logger.debug(f"Analyzing code segment from {file_path or 'unknown file'}")
        
        # Determine language if not provided
        if not language and file_path:
            # Simple language detection based on file extension
            if file_path.endswith(".rs"):
                language = "rust"
            elif file_path.endswith(".py"):
                language = "python"
            elif file_path.endswith(".js") or file_path.endswith(".ts"):
                language = "javascript"
            elif file_path.endswith(".java"):
                language = "java"
            elif file_path.endswith(".go"):
                language = "go"
            elif file_path.endswith(".cpp") or file_path.endswith(".cc") or file_path.endswith(".h"):
                language = "cpp"
            else:
                language = "unknown"
        
        # Construct question for the agent
        lang_info = f" (language: {language})" if language else ""
        file_info = f" from file {file_path}" if file_path else ""
        question = f"Analyze this code segment{file_info}{lang_info}:\n\n```{language or ''}\n{code_segment}\n```"
        
        # Run the agent
        result = self.run({"question": question})
        
        # Extract analysis from result
        analysis = {
            "code_segment": code_segment,
            "file_path": file_path,
            "language": language,
            "analysis": result.get("output", "No analysis generated")
        }
        
        logger.debug(f"Completed code analysis for {file_path or 'unknown file'}")
        return analysis
    
    def analyze_code_structure(self, code_segment: str, language: str = None) -> Dict[str, Any]:
        """
        Analyze the structure of a code segment (functions, classes, etc.).
        
        Args:
            code_segment: Code text to analyze
            language: Programming language of the code
            
        Returns:
            Dict[str, Any]: Structure analysis results
        """
        logger.debug("Analyzing code structure")
        
        # Use the parse_code tool if available (would come from .tools.code_tools)
        parsed_code = None
        for tool in self.tools:
            if tool.name == "parse_code":
                try:
                    parsed_code = tool.func(code_segment, language)
                    break
                except Exception as e:
                    logger.error(f"Error parsing code: {str(e)}")
        
        # If tool-based parsing failed, fall back to agent-based analysis
        if not parsed_code:
            logger.debug("Falling back to agent-based code structure analysis")
            question = f"Analyze only the structure of this code (functions, classes, modules):\n\n```{language or ''}\n{code_segment}\n```"
            result = self.run({"question": question})
            parsed_code = result.get("output", "No structure analysis generated")
        
        return {
            "structure_type": "parsed" if isinstance(parsed_code, dict) else "text_analysis",
            "structure": parsed_code
        }
    
    def analyze_control_flow(self, code_segment: str, language: str = None) -> Dict[str, Any]:
        """
        Analyze the control flow of a code segment.
        
        Args:
            code_segment: Code text to analyze
            language: Programming language of the code
            
        Returns:
            Dict[str, Any]: Control flow analysis results
        """
        logger.debug("Analyzing code control flow")
        
        # Control flow analysis typically requires deeper understanding
        # For now, rely on the agent to analyze
        question = f"Analyze only the control flow of this code (conditionals, loops, function calls):\n\n```{language or ''}\n{code_segment}\n```"
        result = self.run({"question": question})
        
        return {
            "control_flow": result.get("output", "No control flow analysis generated")
        }
    
    def identify_code_patterns(self, code_segment: str, language: str = None) -> Dict[str, Any]:
        """
        Identify design patterns and coding practices in a code segment.
        
        Args:
            code_segment: Code text to analyze
            language: Programming language of the code
            
        Returns:
            Dict[str, Any]: Pattern analysis results
        """
        logger.debug("Identifying code patterns")
        
        # Pattern identification is complex and best handled by the LLM agent
        question = f"Identify design patterns and coding practices in this code:\n\n```{language or ''}\n{code_segment}\n```"
        result = self.run({"question": question})
        
        return {
            "patterns": result.get("output", "No patterns identified")
        }
    
    def assess_code_quality(self, code_segment: str, language: str = None) -> Dict[str, Any]:
        """
        Assess the quality of a code segment.
        
        Args:
            code_segment: Code text to analyze
            language: Programming language of the code
            
        Returns:
            Dict[str, Any]: Quality assessment results
        """
        logger.debug("Assessing code quality")
        
        # Code quality assessment using the agent
        question = f"Assess the quality of this code (readability, maintainability, potential issues):\n\n```{language or ''}\n{code_segment}\n```"
        result = self.run({"question": question})
        
        return {
            "quality_assessment": result.get("output", "No quality assessment generated")
        } 