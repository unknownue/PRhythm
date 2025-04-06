"""
Context Extraction Agent for PR context extraction.
This agent extracts the most relevant code context for PR changes.
"""

import logging
from typing import Any, Dict, List
from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI

from .base_agent import BaseAgent

# Setup logger
logger = logging.getLogger("context_extraction_agent")

# Define the context extraction agent prompt template
CONTEXT_EXTRACTION_PROMPT = """
You are the Context Extraction Agent responsible for extracting the most relevant code context for PR changes.
Your goal is to identify the most important context to understand the changes.

For this task, you need to:
1. Determine the exact code before and after the change
2. Extract surrounding context that helps understand the change
3. Identify related code in other files that interacts with the changed code
4. Prioritize the most relevant context for understanding the change

Think step by step to extract the most useful context.

Question: {question}

{format_instructions}
"""

class ContextExtractionAgent(BaseAgent):
    """
    Context Extraction Agent that extracts the most relevant code context for PR changes.
    This agent identifies the code context needed to understand the changes.
    """
    
    def __init__(self, llm_provider, tools, repo_path):
        """
        Initialize the context extraction agent.
        
        Args:
            llm_provider: LLM provider to use
            tools: List of tools this agent can use
            repo_path: Path to the repository
        """
        super().__init__(llm_provider, tools, "ContextExtractionAgent")
        self.repo_path = repo_path
        
        # Create prompt template
        self.prompt_template = PromptTemplate(
            template=CONTEXT_EXTRACTION_PROMPT,
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
    
    def extract_context(self, changed_entity_name: str, file_path: str, 
                       before_code: str = None, after_code: str = None,
                       diff: str = None, entity_type: str = None) -> Dict[str, Any]:
        """
        Extract context for a changed entity.
        
        Args:
            changed_entity_name: Name of the changed entity
            file_path: Path to the file containing the entity
            before_code: Code before the change (optional)
            after_code: Code after the change (optional)
            diff: Diff of the change (optional)
            entity_type: Type of the entity (function, class, module)
            
        Returns:
            Dict[str, Any]: Extracted context
        """
        logger.debug(f"Extracting context for {entity_type or 'entity'} {changed_entity_name} in {file_path}")
        
        # First, make sure we have both before and after code
        if not before_code or not after_code:
            if diff:
                # Extract before and after code from diff
                before_code, after_code = self._extract_code_from_diff(diff)
            else:
                # Get code from other sources
                before_code = self._get_code_at_commit(file_path, "HEAD~1", changed_entity_name, entity_type)
                after_code = self._get_current_code_segment(file_path, changed_entity_name, entity_type)
        
        # Extract structural context using tools
        structural_context = self._extract_structural_context(changed_entity_name, file_path, entity_type)
        
        # Extract semantic context using vector search
        embedding = self._create_embedding(after_code)
        semantic_context = self._search_semantic_similar_code(embedding)
        
        # Integrate contexts
        combined_context = self._integrate_contexts(structural_context, semantic_context)
        
        # Rank by relevance
        ranked_context = self._rank_by_relevance(combined_context, after_code)
        
        # Prune context to control size
        final_context = self._prune_context(ranked_context, max_tokens=8000)
        
        # Format the final context
        formatted_context = {
            "entity_name": changed_entity_name,
            "entity_type": entity_type,
            "file_path": file_path,
            "before_context": {
                "code": before_code,
                "related_code": final_context.get("before_related_code", [])
            },
            "after_context": {
                "code": after_code,
                "related_code": final_context.get("after_related_code", [])
            },
            "shared_context": final_context.get("shared_context", [])
        }
        
        logger.debug(f"Extracted context for {changed_entity_name}")
        return formatted_context
    
    def _extract_code_from_diff(self, diff: str) -> tuple:
        """
        Extract before and after code from a diff.
        
        Args:
            diff: Diff content
            
        Returns:
            tuple: (before_code, after_code)
        """
        logger.debug("Extracting code from diff")
        
        # Use parse_diff tool if available
        for tool in self.tools:
            if tool.name == "parse_diff":
                try:
                    parsed_diff = tool.func(diff)
                    # Extract before and after code from the parsed diff
                    before_code = "\n".join(parsed_diff.get("before_lines", []))
                    after_code = "\n".join(parsed_diff.get("after_lines", []))
                    return before_code, after_code
                except Exception as e:
                    logger.error(f"Error parsing diff: {str(e)}")
        
        # Fallback: Simple heuristic extraction
        before_lines = []
        after_lines = []
        current_section = None
        
        for line in diff.split("\n"):
            if line.startswith("---"):
                continue
            elif line.startswith("+++"):
                continue
            elif line.startswith("-"):
                before_lines.append(line[1:])
                current_section = "before"
            elif line.startswith("+"):
                after_lines.append(line[1:])
                current_section = "after"
            elif line.startswith(" "):
                # Context line, add to both sections
                line_content = line[1:]
                before_lines.append(line_content)
                after_lines.append(line_content)
        
        return "\n".join(before_lines), "\n".join(after_lines)
    
    def _get_code_at_commit(self, file_path: str, commit_hash: str, entity_name: str, entity_type: str) -> str:
        """
        Get code for an entity at a specific commit.
        
        Args:
            file_path: Path to the file
            commit_hash: Commit hash
            entity_name: Name of the entity
            entity_type: Type of the entity
            
        Returns:
            str: Code at the commit
        """
        logger.debug(f"Getting code at commit {commit_hash} for {entity_name}")
        
        # Use get_code_at_commit tool if available
        for tool in self.tools:
            if tool.name == "get_code_at_commit":
                try:
                    file_content = tool.func(commit_hash, file_path)
                    # Extract the entity code from the file content
                    if entity_name and entity_type:
                        for parse_tool in self.tools:
                            if parse_tool.name == "parse_code":
                                parsed_code = parse_tool.func(file_content)
                                # Find the entity in the parsed code
                                if entity_type == "function":
                                    for func in parsed_code.get("functions", []):
                                        if func.get("name") == entity_name:
                                            return func.get("code", "")
                                elif entity_type == "class":
                                    for cls in parsed_code.get("classes", []):
                                        if cls.get("name") == entity_name:
                                            return cls.get("code", "")
                    # If we can't extract the specific entity, return the whole file
                    return file_content
                except Exception as e:
                    logger.error(f"Error getting code at commit: {str(e)}")
        
        # Fallback: Ask the agent
        question = f"Get the code for {entity_type} '{entity_name}' in file {file_path} at commit {commit_hash}."
        result = self.run({"question": question})
        
        return result.get("output", "")
    
    def _get_current_code_segment(self, file_path: str, entity_name: str, entity_type: str) -> str:
        """
        Get current code for an entity.
        
        Args:
            file_path: Path to the file
            entity_name: Name of the entity
            entity_type: Type of the entity
            
        Returns:
            str: Current code
        """
        logger.debug(f"Getting current code for {entity_name}")
        
        # Placeholder implementation
        # In a real implementation, this would use tools to read the current file
        # and extract the entity code
        for tool in self.tools:
            if tool.name == "get_current_code_segment":
                try:
                    # Simplified approach: read entire file and extract entity
                    if entity_name and entity_type:
                        for read_tool in self.tools:
                            if read_tool.name == "read_file":
                                file_content = read_tool.func(file_path)
                                # Parse the file to find the entity
                                for parse_tool in self.tools:
                                    if parse_tool.name == "parse_code":
                                        parsed_code = parse_tool.func(file_content)
                                        # Find the entity in the parsed code
                                        if entity_type == "function":
                                            for func in parsed_code.get("functions", []):
                                                if func.get("name") == entity_name:
                                                    return func.get("code", "")
                                        elif entity_type == "class":
                                            for cls in parsed_code.get("classes", []):
                                                if cls.get("name") == entity_name:
                                                    return cls.get("code", "")
                                # If we can't extract the specific entity, return the whole file
                                return file_content
                except Exception as e:
                    logger.error(f"Error getting current code: {str(e)}")
        
        # Fallback: Ask the agent
        question = f"Get the current code for {entity_type} '{entity_name}' in file {file_path}."
        result = self.run({"question": question})
        
        return result.get("output", "")
    
    def _extract_structural_context(self, entity_name: str, file_path: str, entity_type: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        Extract structural context for an entity.
        
        Args:
            entity_name: Name of the entity
            file_path: Path to the file
            entity_type: Type of the entity
            
        Returns:
            Dict[str, List[Dict[str, Any]]]: Structural context
        """
        logger.debug(f"Extracting structural context for {entity_name}")
        
        # Initialize context structure
        context = {
            "callers": [],
            "callees": [],
            "class_hierarchy": {
                "parents": [],
                "children": []
            },
            "sibling_entities": [],
            "import_relations": {
                "imports": [],
                "imported_by": []
            }
        }
        
        # Get callers and callees
        for tool in self.tools:
            if tool.name == "find_callers":
                try:
                    context["callers"] = tool.func(entity_name, file_path)
                except Exception as e:
                    logger.error(f"Error finding callers: {str(e)}")
            
            if tool.name == "find_callees":
                try:
                    context["callees"] = tool.func(entity_name, file_path)
                except Exception as e:
                    logger.error(f"Error finding callees: {str(e)}")
        
        # Get class hierarchy if entity is a class
        if entity_type == "class":
            for tool in self.tools:
                if tool.name == "map_inheritance":
                    try:
                        context["class_hierarchy"] = tool.func(entity_name, file_path)
                    except Exception as e:
                        logger.error(f"Error mapping inheritance: {str(e)}")
        
        # Get imports and dependencies
        for tool in self.tools:
            if tool.name == "analyze_dependencies":
                try:
                    deps = tool.func(file_path)
                    context["import_relations"]["imports"] = deps.get("imports", [])
                    context["import_relations"]["imported_by"] = deps.get("imported_by", [])
                except Exception as e:
                    logger.error(f"Error analyzing dependencies: {str(e)}")
        
        # Get sibling entities (other functions/classes in the same file)
        # This would typically use parse_code to find all entities in the file
        
        return context
    
    def _create_embedding(self, code: str) -> List[float]:
        """
        Create embedding for code.
        
        Args:
            code: Code to embed
            
        Returns:
            List[float]: Embedding vector
        """
        logger.debug("Creating embedding for code")
        
        # In a real implementation, this would use a code embedding model
        # For now, return a placeholder value
        return [0.0] * 768  # Placeholder for a 768-dimensional embedding
    
    def _search_semantic_similar_code(self, embedding: List[float], k: int = 5) -> List[Dict[str, Any]]:
        """
        Search for semantically similar code using embeddings.
        
        Args:
            embedding: Code embedding
            k: Number of results to return
            
        Returns:
            List[Dict[str, Any]]: Semantically similar code segments
        """
        logger.debug(f"Searching for semantically similar code (top {k})")
        
        # Use vectorstore_search tool if available
        for tool in self.tools:
            if tool.name == "vectorstore_search":
                try:
                    return tool.func(embedding, k)
                except Exception as e:
                    logger.error(f"Error searching vector store: {str(e)}")
        
        # Placeholder: return empty list if tool not available
        return []
    
    def _integrate_contexts(self, structural_context: Dict[str, Any], semantic_context: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Integrate structural and semantic contexts.
        
        Args:
            structural_context: Structural context
            semantic_context: Semantic context
            
        Returns:
            Dict[str, Any]: Integrated context
        """
        logger.debug("Integrating structural and semantic contexts")
        
        # Initialize integrated context
        integrated_context = {
            "structural_elements": structural_context,
            "semantic_elements": []
        }
        
        # Process semantic context, removing duplicates
        existing_files = set()
        for item in semantic_context:
            file_path = item.get("file_path", "")
            code = item.get("code", "")
            
            # Skip if already included in structural context
            if file_path in existing_files:
                continue
                
            integrated_context["semantic_elements"].append({
                "file_path": file_path,
                "segment_type": item.get("segment_type", "unknown"),
                "name": item.get("name", ""),
                "code": code,
                "similarity_score": item.get("similarity_score", 0.0)
            })
            
            existing_files.add(file_path)
        
        return integrated_context
    
    def _rank_by_relevance(self, context: Dict[str, Any], changed_code: str) -> Dict[str, Any]:
        """
        Rank context elements by relevance to the changed code.
        
        Args:
            context: Integrated context
            changed_code: Changed code to compare against
            
        Returns:
            Dict[str, Any]: Ranked context
        """
        logger.debug("Ranking context by relevance")
        
        # Initialize ranked context
        ranked_context = {
            "high_relevance": [],
            "medium_relevance": [],
            "low_relevance": []
        }
        
        # Process structural elements
        structural = context.get("structural_elements", {})
        
        # Direct callers/callees are high relevance
        for caller in structural.get("callers", []):
            ranked_context["high_relevance"].append({
                "file_path": caller.get("file", ""),
                "entity_name": caller.get("name", ""),
                "relationship": "caller",
                "code": "",  # Would be populated in a real implementation
                "reason": f"Directly calls the changed code"
            })
        
        for callee in structural.get("callees", []):
            ranked_context["high_relevance"].append({
                "file_path": callee.get("file", ""),
                "entity_name": callee.get("name", ""),
                "relationship": "callee",
                "code": "",  # Would be populated in a real implementation
                "reason": f"Directly called by the changed code"
            })
        
        # Class hierarchy is high/medium relevance
        for parent in structural.get("class_hierarchy", {}).get("parents", []):
            ranked_context["high_relevance"].append({
                "file_path": parent.get("file", ""),
                "entity_name": parent.get("name", ""),
                "relationship": "parent_class",
                "code": "",  # Would be populated in a real implementation
                "reason": f"Parent class of the changed code"
            })
        
        for child in structural.get("class_hierarchy", {}).get("children", []):
            ranked_context["medium_relevance"].append({
                "file_path": child.get("file", ""),
                "entity_name": child.get("name", ""),
                "relationship": "child_class",
                "code": "",  # Would be populated in a real implementation
                "reason": f"Child class of the changed code"
            })
        
        # Process semantic elements
        for element in context.get("semantic_elements", []):
            similarity = element.get("similarity_score", 0.0)
            
            if similarity > 0.8:
                relevance = "high_relevance"
                reason = "Very similar to the changed code"
            elif similarity > 0.5:
                relevance = "medium_relevance"
                reason = "Moderately similar to the changed code"
            else:
                relevance = "low_relevance"
                reason = "Somewhat similar to the changed code"
            
            ranked_context[relevance].append({
                "file_path": element.get("file_path", ""),
                "entity_name": element.get("name", ""),
                "relationship": "semantic_similarity",
                "code": element.get("code", ""),
                "reason": reason,
                "similarity_score": similarity
            })
        
        return ranked_context
    
    def _prune_context(self, ranked_context: Dict[str, Any], max_tokens: int = 8000) -> Dict[str, Any]:
        """
        Prune context to control token count.
        
        Args:
            ranked_context: Ranked context
            max_tokens: Maximum token count
            
        Returns:
            Dict[str, Any]: Pruned context
        """
        logger.debug(f"Pruning context to max {max_tokens} tokens")
        
        # Initialize pruned context
        pruned_context = {
            "before_related_code": [],
            "after_related_code": [],
            "shared_context": []
        }
        
        # Simple token estimation: roughly 4 characters per token
        estimated_tokens = 0
        token_budget = max_tokens
        
        # Always include high relevance
        for item in ranked_context.get("high_relevance", []):
            code = item.get("code", "")
            estimated_item_tokens = len(code) // 4
            
            if estimated_tokens + estimated_item_tokens <= token_budget:
                pruned_context["before_related_code"].append(item)
                pruned_context["after_related_code"].append(item)
                estimated_tokens += estimated_item_tokens
            else:
                # If we can't fit the full code, truncate
                max_chars = (token_budget - estimated_tokens) * 4
                if max_chars > 100:  # Only include if we can get a meaningful snippet
                    truncated_item = item.copy()
                    truncated_item["code"] = code[:max_chars] + "... [truncated]"
                    truncated_item["truncated"] = True
                    pruned_context["before_related_code"].append(truncated_item)
                    pruned_context["after_related_code"].append(truncated_item)
                    estimated_tokens = token_budget
                break
        
        # If we have budget left, include medium relevance
        if estimated_tokens < token_budget:
            for item in ranked_context.get("medium_relevance", []):
                code = item.get("code", "")
                estimated_item_tokens = len(code) // 4
                
                if estimated_tokens + estimated_item_tokens <= token_budget:
                    pruned_context["shared_context"].append(item)
                    estimated_tokens += estimated_item_tokens
                else:
                    # If we can't fit the full code, truncate
                    max_chars = (token_budget - estimated_tokens) * 4
                    if max_chars > 100:  # Only include if we can get a meaningful snippet
                        truncated_item = item.copy()
                        truncated_item["code"] = code[:max_chars] + "... [truncated]"
                        truncated_item["truncated"] = True
                        pruned_context["shared_context"].append(truncated_item)
                        estimated_tokens = token_budget
                    break
        
        # Only include low relevance if we have lots of budget left
        if estimated_tokens < token_budget * 0.7:  # Only if we've used less than 70% of budget
            for item in ranked_context.get("low_relevance", []):
                code = item.get("code", "")
                estimated_item_tokens = len(code) // 4
                
                if estimated_tokens + estimated_item_tokens <= token_budget:
                    pruned_context["shared_context"].append(item)
                    estimated_tokens += estimated_item_tokens
                else:
                    break
        
        logger.debug(f"Pruned context to approximately {estimated_tokens} tokens")
        return pruned_context 