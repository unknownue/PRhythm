"""
Relationship Extractor Agent for PR context extraction.
This agent discovers and maps relationships between code components.
"""

import logging
from typing import Any, Dict, List
from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI

from .base_agent import BaseAgent

# Setup logger
logger = logging.getLogger("relationship_extractor_agent")

# Define the relationship extractor agent prompt template
RELATIONSHIP_EXTRACTOR_PROMPT = """
You are the Relationship Extractor Agent responsible for discovering and mapping relationships between code components.
Your goal is to identify how different parts of the code relate to each other.

For this task, you need to:
1. Identify function and method call relationships
2. Map class inheritance relationships
3. Determine data flow and dependencies
4. Analyze import/export relationships

Think step by step to identify all important relationships.

Question: {question}

{format_instructions}
"""

class RelationshipExtractorAgent(BaseAgent):
    """
    Relationship Extractor Agent that discovers and maps relationships between code components.
    This agent identifies call graphs, inheritance relations, etc.
    """
    
    def __init__(self, llm_provider, tools, repo_path):
        """
        Initialize the relationship extractor agent.
        
        Args:
            llm_provider: LLM provider to use
            tools: List of tools this agent can use
            repo_path: Path to the repository
        """
        super().__init__(llm_provider, tools, "RelationshipExtractorAgent")
        self.repo_path = repo_path
        
        # Create prompt template
        self.prompt_template = PromptTemplate(
            template=RELATIONSHIP_EXTRACTOR_PROMPT,
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
    
    def extract_relationships(self, entity_name: str, file_path: str, entity_type: str = None) -> Dict[str, Any]:
        """
        Extract relationships for a code entity.
        
        Args:
            entity_name: Name of the entity (function, class, etc.)
            file_path: Path to the file containing the entity
            entity_type: Type of the entity (function, class, module)
            
        Returns:
            Dict[str, Any]: Extracted relationships
        """
        logger.debug(f"Extracting relationships for {entity_type or 'entity'} {entity_name} in {file_path}")
        
        # Use available tools to gather relationship data
        callers = self._find_callers(entity_name, file_path)
        callees = self._find_callees(entity_name, file_path)
        
        # For classes, extract inheritance relationships
        class_hierarchy = {}
        if entity_type == "class":
            class_hierarchy = self._map_inheritance(entity_name, file_path)
        
        # Extract dependencies
        dependencies = self._analyze_dependencies(file_path)
        
        # Compile all relationships
        relationships = {
            "entity_name": entity_name,
            "entity_type": entity_type,
            "file_path": file_path,
            "call_relationships": {
                "callers": callers,
                "callees": callees
            },
            "class_hierarchy": class_hierarchy,
            "dependencies": dependencies
        }
        
        logger.debug(f"Extracted relationships for {entity_name}")
        return relationships
    
    def _find_callers(self, entity_name: str, file_path: str) -> List[Dict[str, str]]:
        """
        Find callers of an entity.
        
        Args:
            entity_name: Name of the entity
            file_path: Path to the file containing the entity
            
        Returns:
            List[Dict[str, str]]: List of callers
        """
        logger.debug(f"Finding callers of {entity_name}")
        
        # Use find_callers tool if available
        for tool in self.tools:
            if tool.name == "find_callers":
                try:
                    return tool.func(entity_name, file_path)
                except Exception as e:
                    logger.error(f"Error finding callers: {str(e)}")
        
        # If tool not available, ask the agent to analyze
        question = f"Find all callers of the entity '{entity_name}' in the codebase. The entity is defined in {file_path}."
        result = self.run({"question": question})
        
        # Try to parse the result
        callers = []
        try:
            # Simplified parsing - in a real implementation, would parse structured output
            if isinstance(result.get("output"), str):
                lines = result.get("output").split("\n")
                for line in lines:
                    if "caller" in line.lower() and "->" in line:
                        caller, _ = line.split("->")
                        callers.append({"name": caller.strip(), "file": "unknown"})
        except Exception as e:
            logger.error(f"Error parsing callers: {str(e)}")
        
        return callers
    
    def _find_callees(self, entity_name: str, file_path: str) -> List[Dict[str, str]]:
        """
        Find callees (functions called by this entity).
        
        Args:
            entity_name: Name of the entity
            file_path: Path to the file containing the entity
            
        Returns:
            List[Dict[str, str]]: List of callees
        """
        logger.debug(f"Finding callees of {entity_name}")
        
        # Use find_callees tool if available
        for tool in self.tools:
            if tool.name == "find_callees":
                try:
                    return tool.func(entity_name, file_path)
                except Exception as e:
                    logger.error(f"Error finding callees: {str(e)}")
        
        # If tool not available, ask the agent to analyze
        question = f"Find all functions or methods called by the entity '{entity_name}' defined in {file_path}."
        result = self.run({"question": question})
        
        # Try to parse the result
        callees = []
        try:
            # Simplified parsing - in a real implementation, would parse structured output
            if isinstance(result.get("output"), str):
                lines = result.get("output").split("\n")
                for line in lines:
                    if "calls" in line.lower() and "->" in line:
                        _, callee = line.split("->")
                        callees.append({"name": callee.strip(), "file": "unknown"})
        except Exception as e:
            logger.error(f"Error parsing callees: {str(e)}")
        
        return callees
    
    def _map_inheritance(self, class_name: str, file_path: str) -> Dict[str, List[Dict[str, str]]]:
        """
        Map inheritance relationships for a class.
        
        Args:
            class_name: Name of the class
            file_path: Path to the file containing the class
            
        Returns:
            Dict[str, List[Dict[str, str]]]: Inheritance map
        """
        logger.debug(f"Mapping inheritance for class {class_name}")
        
        # Use map_inheritance tool if available
        for tool in self.tools:
            if tool.name == "map_inheritance":
                try:
                    return tool.func(class_name, file_path)
                except Exception as e:
                    logger.error(f"Error mapping inheritance: {str(e)}")
        
        # If tool not available, ask the agent to analyze
        question = f"Map the inheritance hierarchy for the class '{class_name}' defined in {file_path}. Identify parent classes and child classes."
        result = self.run({"question": question})
        
        # Default inheritance structure
        inheritance = {
            "parents": [],
            "children": []
        }
        
        # Try to parse the result
        try:
            # Attempt to extract structured information from the text
            if isinstance(result.get("output"), str):
                text = result.get("output")
                
                # Simple parsing - look for sections about parents and children
                if "parent" in text.lower():
                    for line in text.lower().split("parent")[1].split("\n"):
                        if ":" in line or "-" in line:
                            separator = ":" if ":" in line else "-"
                            parent = line.split(separator)[1].strip()
                            if parent and parent != "none" and parent != "n/a":
                                inheritance["parents"].append({"name": parent, "file": "unknown"})
                
                if "child" in text.lower():
                    for line in text.lower().split("child")[1].split("\n"):
                        if ":" in line or "-" in line:
                            separator = ":" if ":" in line else "-"
                            child = line.split(separator)[1].strip()
                            if child and child != "none" and child != "n/a":
                                inheritance["children"].append({"name": child, "file": "unknown"})
        except Exception as e:
            logger.error(f"Error parsing inheritance: {str(e)}")
            
        return inheritance
    
    def _analyze_dependencies(self, file_path: str) -> Dict[str, List[str]]:
        """
        Analyze dependencies for a file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Dict[str, List[str]]: Dependencies analysis
        """
        logger.debug(f"Analyzing dependencies for {file_path}")
        
        # Use analyze_dependencies tool if available
        for tool in self.tools:
            if tool.name == "analyze_dependencies":
                try:
                    return tool.func(file_path)
                except Exception as e:
                    logger.error(f"Error analyzing dependencies: {str(e)}")
        
        # If tool not available, ask the agent to analyze
        question = f"Analyze the dependencies for the file at {file_path}. Identify imports, exports, and other dependencies."
        result = self.run({"question": question})
        
        # Default dependencies structure
        dependencies = {
            "imports": [],
            "exports": []
        }
        
        # Try to parse the result
        try:
            # Attempt to extract structured information from the text
            if isinstance(result.get("output"), str):
                text = result.get("output")
                
                # Simple parsing - look for sections about imports and exports
                if "import" in text.lower():
                    for line in text.lower().split("import")[1].split("\n"):
                        if ":" in line or "-" in line:
                            separator = ":" if ":" in line else "-"
                            imported = line.split(separator)[1].strip()
                            if imported and imported != "none" and imported != "n/a":
                                dependencies["imports"].append(imported)
                
                if "export" in text.lower():
                    for line in text.lower().split("export")[1].split("\n"):
                        if ":" in line or "-" in line:
                            separator = ":" if ":" in line else "-"
                            exported = line.split(separator)[1].strip()
                            if exported and exported != "none" and exported != "n/a":
                                dependencies["exports"].append(exported)
        except Exception as e:
            logger.error(f"Error parsing dependencies: {str(e)}")
            
        return dependencies
    
    def compare_relationships(self, before_relationships: Dict[str, Any], after_relationships: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compare relationships before and after changes.
        
        Args:
            before_relationships: Relationships before the change
            after_relationships: Relationships after the change
            
        Returns:
            Dict[str, Any]: Comparison results
        """
        logger.debug("Comparing relationships before and after changes")
        
        # Initialize comparison structure
        comparison = {
            "added_callers": [],
            "removed_callers": [],
            "added_callees": [],
            "removed_callees": [],
            "changed_inheritance": {
                "added_parents": [],
                "removed_parents": [],
                "added_children": [],
                "removed_children": []
            },
            "changed_dependencies": {
                "added_imports": [],
                "removed_imports": [],
                "added_exports": [],
                "removed_exports": []
            }
        }
        
        # Compare callers
        before_callers = set(caller["name"] for caller in before_relationships.get("call_relationships", {}).get("callers", []))
        after_callers = set(caller["name"] for caller in after_relationships.get("call_relationships", {}).get("callers", []))
        comparison["added_callers"] = list(after_callers - before_callers)
        comparison["removed_callers"] = list(before_callers - after_callers)
        
        # Compare callees
        before_callees = set(callee["name"] for callee in before_relationships.get("call_relationships", {}).get("callees", []))
        after_callees = set(callee["name"] for callee in after_relationships.get("call_relationships", {}).get("callees", []))
        comparison["added_callees"] = list(after_callees - before_callees)
        comparison["removed_callees"] = list(before_callees - after_callees)
        
        # Compare inheritance
        before_parents = set(parent["name"] for parent in before_relationships.get("class_hierarchy", {}).get("parents", []))
        after_parents = set(parent["name"] for parent in after_relationships.get("class_hierarchy", {}).get("parents", []))
        comparison["changed_inheritance"]["added_parents"] = list(after_parents - before_parents)
        comparison["changed_inheritance"]["removed_parents"] = list(before_parents - after_parents)
        
        before_children = set(child["name"] for child in before_relationships.get("class_hierarchy", {}).get("children", []))
        after_children = set(child["name"] for child in after_relationships.get("class_hierarchy", {}).get("children", []))
        comparison["changed_inheritance"]["added_children"] = list(after_children - before_children)
        comparison["changed_inheritance"]["removed_children"] = list(before_children - after_children)
        
        # Compare dependencies
        before_imports = set(before_relationships.get("dependencies", {}).get("imports", []))
        after_imports = set(after_relationships.get("dependencies", {}).get("imports", []))
        comparison["changed_dependencies"]["added_imports"] = list(after_imports - before_imports)
        comparison["changed_dependencies"]["removed_imports"] = list(before_imports - after_imports)
        
        before_exports = set(before_relationships.get("dependencies", {}).get("exports", []))
        after_exports = set(after_relationships.get("dependencies", {}).get("exports", []))
        comparison["changed_dependencies"]["added_exports"] = list(after_exports - before_exports)
        comparison["changed_dependencies"]["removed_exports"] = list(before_exports - after_exports)
        
        return comparison 