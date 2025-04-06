"""
Context Synthesizer Agent for PR context extraction.
This agent integrates outputs from different analysis agents into a final context.
"""

import logging
import json
from typing import Any, Dict, List
from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI

from .base_agent import BaseAgent

# Setup logger
logger = logging.getLogger("context_synthesizer_agent")

# Define the context synthesizer agent prompt template
CONTEXT_SYNTHESIZER_PROMPT = """
You are the Context Synthesizer Agent responsible for integrating outputs from different analysis agents.
Your goal is to produce a coherent, well-organized context for understanding a PR change.

For this task, you need to:
1. Organize information into clear "before" and "after" change sections
2. Identify shared/unchanged but related context
3. Ensure the final output is complete, consistent, and useful for understanding the change

Think step by step to synthesize the final context document.

Question: {question}

{format_instructions}
"""

class ContextSynthesizerAgent(BaseAgent):
    """
    Context Synthesizer Agent that integrates outputs from different analysis agents.
    This agent produces the final context representation.
    """
    
    def __init__(self, llm_provider, tools):
        """
        Initialize the context synthesizer agent.
        
        Args:
            llm_provider: LLM provider to use
            tools: List of tools this agent can use
        """
        super().__init__(llm_provider, tools, "ContextSynthesizerAgent")
        
        # Create prompt template
        self.prompt_template = PromptTemplate(
            template=CONTEXT_SYNTHESIZER_PROMPT,
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
    
    def synthesize(self, code_analysis: Dict[str, Any], relationship_analysis: Dict[str, Any], 
                  extracted_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Synthesize the final context from different analysis outputs.
        
        Args:
            code_analysis: Output from the code analyzer agent
            relationship_analysis: Output from the relationship extractor agent
            extracted_context: Output from the context extraction agent
            
        Returns:
            Dict[str, Any]: Final synthesized context
        """
        logger.debug("Synthesizing final context")
        
        # Combine all inputs for the agent
        combined_input = {
            "code_analysis": code_analysis,
            "relationship_analysis": relationship_analysis,
            "extracted_context": extracted_context
        }
        
        # Convert to JSON string for the agent
        combined_input_str = json.dumps(combined_input, indent=2)
        
        # Construct question for the agent
        question = "Synthesize the following analysis outputs into a final context document:\n\n" + combined_input_str
        
        # Run the agent
        result = self.run({"question": question})
        
        # Try to parse the result as JSON
        synthesized_context = {}
        try:
            if isinstance(result.get("output"), str):
                # Try to find and extract JSON from the result
                json_str = result.get("output")
                if "```json" in json_str:
                    # Extract JSON from code block
                    json_str = json_str.split("```json")[1].split("```")[0].strip()
                
                try:
                    synthesized_context = json.loads(json_str)
                except json.JSONDecodeError:
                    logger.warning("Could not parse agent output as JSON")
                    synthesized_context = self._format_output_from_text(result.get("output"))
            elif isinstance(result.get("output"), dict):
                synthesized_context = result.get("output")
        except Exception as e:
            logger.error(f"Error parsing agent result: {str(e)}")
            synthesized_context = self._format_output_from_text(result.get("output", ""))
        
        # Ensure the output follows the expected structure
        return self._ensure_output_structure(synthesized_context, extracted_context)
    
    def _format_output_from_text(self, text: str) -> Dict[str, Any]:
        """
        Format a structured output from text when JSON parsing fails.
        
        Args:
            text: Text output from the agent
            
        Returns:
            Dict[str, Any]: Structured output
        """
        logger.debug("Formatting output from text")
        
        # Create a basic structure
        output = {
            "before_context": {
                "code_segments": [],
                "architectural_elements": {
                    "description": "",
                    "key_components": []
                }
            },
            "after_context": {
                "code_segments": [],
                "architectural_elements": {
                    "description": "",
                    "key_components": []
                }
            },
            "shared_context": {
                "code_segments": [],
                "dependencies": []
            },
            "context_summary": {
                "key_changes": [],
                "implications": [],
                "related_areas": []
            }
        }
        
        # Simple text parsing to extract sections
        if "before" in text.lower():
            before_section = text.lower().split("before")[1].split("after")[0] if "after" in text.lower() else text.lower().split("before")[1]
            output["before_context"]["architectural_elements"]["description"] = before_section
        
        if "after" in text.lower():
            after_section = text.lower().split("after")[1].split("shared")[0] if "shared" in text.lower() else text.lower().split("after")[1]
            output["after_context"]["architectural_elements"]["description"] = after_section
        
        if "summary" in text.lower():
            summary_section = text.lower().split("summary")[1]
            output["context_summary"]["key_changes"] = [line.strip() for line in summary_section.split("\n") if line.strip()]
        
        return output
    
    def _ensure_output_structure(self, synthesized_context: Dict[str, Any], extracted_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ensure the output follows the expected structure.
        
        Args:
            synthesized_context: Synthesized context from the agent
            extracted_context: Original extracted context
            
        Returns:
            Dict[str, Any]: Properly structured output
        """
        logger.debug("Ensuring output structure")
        
        # Define the expected structure
        expected_structure = {
            "before_context": {
                "code_segments": [],
                "architectural_elements": {
                    "description": "",
                    "key_components": []
                }
            },
            "after_context": {
                "code_segments": [],
                "architectural_elements": {
                    "description": "",
                    "key_components": []
                }
            },
            "shared_context": {
                "code_segments": [],
                "dependencies": []
            },
            "context_summary": {
                "key_changes": [],
                "implications": [],
                "related_areas": []
            }
        }
        
        # Merge the synthesized context with the expected structure
        result = expected_structure.copy()
        
        # Update with synthesized content if available
        if "before_context" in synthesized_context:
            result["before_context"] = synthesized_context["before_context"]
        
        if "after_context" in synthesized_context:
            result["after_context"] = synthesized_context["after_context"]
        
        if "shared_context" in synthesized_context:
            result["shared_context"] = synthesized_context["shared_context"]
        
        if "context_summary" in synthesized_context:
            result["context_summary"] = synthesized_context["context_summary"]
        
        # Fallback to extracted_context if synthesized_context is incomplete
        if not result["before_context"]["code_segments"] and "before_context" in extracted_context:
            # Convert extracted_context format to expected format
            code = extracted_context["before_context"].get("code", "")
            if code:
                result["before_context"]["code_segments"].append({
                    "file_path": extracted_context.get("file_path", ""),
                    "segment_type": extracted_context.get("entity_type", "unknown"),
                    "name": extracted_context.get("entity_name", ""),
                    "code": code,
                    "importance": "high",
                    "reason": "Main changed code"
                })
            
            for related in extracted_context["before_context"].get("related_code", []):
                result["before_context"]["code_segments"].append({
                    "file_path": related.get("file_path", ""),
                    "segment_type": "unknown",
                    "name": related.get("entity_name", ""),
                    "code": related.get("code", ""),
                    "importance": "medium",
                    "reason": related.get("reason", "Related to changed code")
                })
        
        if not result["after_context"]["code_segments"] and "after_context" in extracted_context:
            # Convert extracted_context format to expected format
            code = extracted_context["after_context"].get("code", "")
            if code:
                result["after_context"]["code_segments"].append({
                    "file_path": extracted_context.get("file_path", ""),
                    "segment_type": extracted_context.get("entity_type", "unknown"),
                    "name": extracted_context.get("entity_name", ""),
                    "code": code,
                    "importance": "high",
                    "reason": "Main changed code"
                })
            
            for related in extracted_context["after_context"].get("related_code", []):
                result["after_context"]["code_segments"].append({
                    "file_path": related.get("file_path", ""),
                    "segment_type": "unknown",
                    "name": related.get("entity_name", ""),
                    "code": related.get("code", ""),
                    "importance": "medium",
                    "reason": related.get("reason", "Related to changed code")
                })
        
        if not result["shared_context"]["code_segments"] and "shared_context" in extracted_context:
            for shared in extracted_context.get("shared_context", []):
                result["shared_context"]["code_segments"].append({
                    "file_path": shared.get("file_path", ""),
                    "segment_type": "unknown",
                    "name": shared.get("entity_name", ""),
                    "code": shared.get("code", ""),
                    "importance": "medium",
                    "reason": shared.get("reason", "Shared context")
                })
        
        return result
    
    def format_output_json(self, context: Dict[str, Any]) -> str:
        """
        Format the output as a JSON string.
        
        Args:
            context: Context to format
            
        Returns:
            str: Formatted JSON string
        """
        logger.debug("Formatting output as JSON")
        
        try:
            return json.dumps(context, indent=2)
        except Exception as e:
            logger.error(f"Error formatting JSON: {str(e)}")
            return json.dumps({"error": "Could not format context as JSON"}, indent=2) 