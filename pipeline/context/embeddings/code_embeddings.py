"""
Code embeddings module for PR context extraction.
This module provides functionality for generating code embeddings.
"""

import logging
import os
from typing import Any, Dict, List, Optional, Union

# Setup logger
logger = logging.getLogger("code_embeddings")

class CodeEmbeddings:
    """
    Code embeddings generator using CodeBERT.
    """
    
    def __init__(self, model_name: str = "microsoft/codebert-base"):
        """
        Initialize the code embeddings generator.
        
        Args:
            model_name: Name of the model to use (default: CodeBERT)
        """
        self.model_name = model_name
        self.model = None
        self.tokenizer = None
        
        # Import here to avoid loading at module level
        try:
            import torch
            from transformers import AutoModel, AutoTokenizer
            
            # Load model and tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.model = AutoModel.from_pretrained(model_name)
            
            # Use GPU if available
            if torch.cuda.is_available():
                self.device = torch.device("cuda")
                self.model = self.model.to(self.device)
            else:
                self.device = torch.device("cpu")
            
            self.torch = torch
            self._is_initialized = True
            
            logger.debug(f"Initialized CodeEmbeddings with model: {model_name}")
        except ImportError as e:
            logger.error(f"Error initializing CodeEmbeddings: {e}. Transformers or PyTorch not installed.")
            self._is_initialized = False
        except Exception as e:
            logger.error(f"Error initializing CodeEmbeddings: {e}")
            self._is_initialized = False
    
    def embed_code(self, code_text: str) -> List[float]:
        """
        Generate embeddings for a code snippet.
        
        Args:
            code_text: The code text to embed
            
        Returns:
            List[float]: Embedding vector
            
        Raises:
            RuntimeError: If the embeddings generator is not initialized
        """
        if not self._is_initialized:
            logger.error("CodeEmbeddings not initialized")
            # Return empty vector as fallback
            return [0.0] * 768
        
        logger.debug("Generating embeddings for code")
        
        try:
            # Tokenize the code
            inputs = self.tokenizer(
                code_text, 
                return_tensors="pt", 
                truncation=True,
                max_length=512,
                padding="max_length"
            )
            
            # Move inputs to the appropriate device
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            
            # Generate embeddings
            with self.torch.no_grad():
                outputs = self.model(**inputs)
                
            # Use the [CLS] token embedding as the code embedding
            embedding = outputs.last_hidden_state[:, 0, :].cpu().numpy()[0]
            
            return embedding.tolist()
        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            # Return empty vector as fallback
            return [0.0] * 768
    
    def embed_file(self, file_path: str) -> List[float]:
        """
        Generate embeddings for a code file.
        
        Args:
            file_path: Path to the code file
            
        Returns:
            List[float]: Embedding vector
            
        Raises:
            RuntimeError: If the file cannot be read
        """
        logger.debug(f"Generating embeddings for file: {file_path}")
        
        try:
            # Read the file
            with open(file_path, 'r') as f:
                code_text = f.read()
            
            # Generate embeddings
            return self.embed_code(code_text)
        except Exception as e:
            logger.error(f"Error reading file: {e}")
            raise RuntimeError(f"Could not read file: {e}")
    
    def embed_code_units(self, code_units: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Generate embeddings for a list of code units.
        
        Args:
            code_units: List of code units (with 'code' field)
            
        Returns:
            List[Dict[str, Any]]: Code units with embedded vectors
        """
        logger.debug(f"Generating embeddings for {len(code_units)} code units")
        
        embedded_units = []
        for unit in code_units:
            code = unit.get("code", "")
            if code:
                embedding = self.embed_code(code)
                unit_with_embedding = {**unit, "embedding": embedding}
                embedded_units.append(unit_with_embedding)
            else:
                logger.warning(f"Code unit missing 'code' field: {unit}")
                # Include the unit without embedding
                embedded_units.append(unit)
        
        return embedded_units 