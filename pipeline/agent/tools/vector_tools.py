"""
Vector tools for PR context extraction agents.
These tools help agents with semantic code search and understanding.
"""

import logging
import os
import numpy as np
from typing import Any, Dict, List, Optional
from langchain.tools import BaseTool, tool

# Setup logger
logger = logging.getLogger("vector_tools")

# Global vector store (would be initialized properly in a real implementation)
_vector_store = None

@tool
def vectorstore_search(query_embedding: List[float], k: int = 5) -> List[Dict[str, Any]]:
    """
    Search the vector store for semantically similar code.
    
    Args:
        query_embedding: Embedding vector for the query
        k: Number of results to return
        
    Returns:
        List[Dict[str, Any]]: Semantically similar code segments
    """
    logger.debug(f"Searching vector store for top {k} matches")
    
    try:
        # In a real implementation, this would use FAISS or another vector database
        # For this prototype, we'll implement a simple in-memory search
        
        # Check if vector store is initialized
        if _vector_store is None:
            _initialize_vector_store()
        
        if not _vector_store or not _vector_store.get("vectors"):
            logger.warning("Vector store not initialized or empty")
            return []
        
        # Convert query embedding to numpy array
        query_vector = np.array(query_embedding)
        
        # Calculate similarity with all stored vectors
        similarities = []
        for idx, item in enumerate(_vector_store.get("vectors", [])):
            vector = np.array(item.get("vector", []))
            
            # Skip empty vectors
            if len(vector) == 0:
                continue
                
            # Calculate cosine similarity
            similarity = _cosine_similarity(query_vector, vector)
            similarities.append((similarity, idx))
        
        # Sort by similarity (descending)
        similarities.sort(reverse=True)
        
        # Return top k results
        results = []
        for similarity, idx in similarities[:k]:
            item = _vector_store["vectors"][idx]
            result = {
                "file_path": item.get("file_path", ""),
                "segment_type": item.get("segment_type", ""),
                "name": item.get("name", ""),
                "code": item.get("code", ""),
                "similarity_score": float(similarity)
            }
            results.append(result)
        
        return results
    except Exception as e:
        logger.error(f"Error searching vector store: {str(e)}")
        return []

def _initialize_vector_store(repo_path: Optional[str] = None):
    """
    Initialize the vector store with code embeddings.
    
    Args:
        repo_path: Optional path to the repository root
    """
    global _vector_store
    
    logger.debug("Initializing vector store")
    
    # In a real implementation, this would:
    # 1. Scan the repository for code files
    # 2. Parse the code to extract functions, classes, etc.
    # 3. Generate embeddings for each code unit
    # 4. Store the embeddings in a vector database (e.g., FAISS)
    
    # For this prototype, we'll create a simple in-memory store with dummy data
    _vector_store = {
        "vectors": [
            # Each item would have a vector, file path, segment type, name, and code
            # These are dummy entries for illustration
            {
                "vector": np.random.rand(768).tolist(),  # Random 768-dim vector
                "file_path": "src/main.rs",
                "segment_type": "function",
                "name": "main",
                "code": "fn main() {\n    println!(\"Hello, world!\");\n}"
            },
            {
                "vector": np.random.rand(768).tolist(),
                "file_path": "src/lib.rs",
                "segment_type": "function",
                "name": "add",
                "code": "pub fn add(a: i32, b: i32) -> i32 {\n    a + b\n}"
            }
            # In a real implementation, there would be many more entries
        ]
    }
    
    logger.debug(f"Vector store initialized with {len(_vector_store['vectors'])} entries")

def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """
    Calculate cosine similarity between two vectors.
    
    Args:
        a: First vector
        b: Second vector
        
    Returns:
        float: Cosine similarity (between -1 and 1)
    """
    # Ensure vectors have same length
    if len(a) != len(b):
        # Pad the shorter vector with zeros
        if len(a) < len(b):
            a = np.pad(a, (0, len(b) - len(a)), 'constant')
        else:
            b = np.pad(b, (0, len(a) - len(b)), 'constant')
    
    # Calculate dot product and magnitudes
    dot_product = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    
    # Handle zero division
    if norm_a == 0 or norm_b == 0:
        return 0
    
    # Return cosine similarity
    return dot_product / (norm_a * norm_b)

def get_vector_tools() -> List[BaseTool]:
    """
    Get a list of vector tools.
    
    Returns:
        List[BaseTool]: List of vector tools
    """
    # Initialize vector store if needed
    if _vector_store is None:
        _initialize_vector_store()
    
    tools = [
        vectorstore_search
    ]
    
    return tools 