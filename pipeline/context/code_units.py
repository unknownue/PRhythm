"""
Code units module for PR context extraction.
This module provides functionality for extracting and managing code units.
"""

import ast
import logging
import os
import re
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

# Setup logger
logger = logging.getLogger("code_units")

class UnitType(str, Enum):
    """Enum for code unit types."""
    FUNCTION = "function"
    CLASS = "class"
    METHOD = "method"
    MODULE = "module"
    IMPORT = "import"
    UNKNOWN = "unknown"

class CodeUnitExtractor:
    """
    Extracts code units from source files.
    A code unit is a discrete piece of code such as a function, class, or method.
    """
    
    def __init__(self):
        """Initialize the code unit extractor."""
        pass
    
    def extract_units_from_file(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Extract code units from a file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            List[Dict[str, Any]]: List of code units
        """
        logger.debug(f"Extracting code units from file: {file_path}")
        
        try:
            # Read the file
            with open(file_path, 'r') as f:
                content = f.read()
            
            # Extract all code units
            units = self.extract_units_from_content(content, file_path)
            
            return units
        except Exception as e:
            logger.error(f"Error extracting code units from file {file_path}: {e}")
            return []
    
    def extract_units_from_content(self, content: str, file_path: str = "") -> List[Dict[str, Any]]:
        """
        Extract code units from content.
        
        Args:
            content: Source code content
            file_path: Optional file path for reference
            
        Returns:
            List[Dict[str, Any]]: List of code units
        """
        # Determine language based on file extension
        ext = os.path.splitext(file_path)[1] if file_path else ""
        
        if ext in ['.py']:
            return self._extract_python_units(content, file_path)
        elif ext in ['.js', '.ts', '.jsx', '.tsx']:
            return self._extract_js_units(content, file_path)
        elif ext in ['.java']:
            return self._extract_java_units(content, file_path)
        elif ext in ['.rs']:
            return self._extract_rust_units(content, file_path)
        elif ext in ['.go']:
            return self._extract_go_units(content, file_path)
        else:
            # Simple line-based extraction for unsupported languages
            return self._extract_generic_units(content, file_path)
    
    def _extract_python_units(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """Extract units from Python code using AST."""
        logger.debug("Extracting Python code units")
        units = []
        
        try:
            # Parse the content
            tree = ast.parse(content)
            
            # Extract module-level docstring
            if (isinstance(tree.body[0], ast.Expr) and 
                isinstance(tree.body[0].value, ast.Str)):
                units.append({
                    "type": UnitType.MODULE,
                    "name": os.path.basename(file_path),
                    "docstring": tree.body[0].value.s,
                    "code": tree.body[0].value.s,
                    "file_path": file_path,
                    "start_line": 1,
                    "end_line": tree.body[0].end_lineno
                })
            
            # Extract imports
            imports = []
            for node in tree.body:
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    import_code = ast.get_source_segment(content, node)
                    if import_code:
                        imports.append(import_code)
            
            if imports:
                units.append({
                    "type": UnitType.IMPORT,
                    "name": "imports",
                    "code": "\n".join(imports),
                    "file_path": file_path,
                    "start_line": tree.body[0].lineno if tree.body else 1,
                    "end_line": tree.body[-1].end_lineno if tree.body else 1
                })
            
            # Extract functions and classes
            for node in tree.body:
                if isinstance(node, ast.FunctionDef):
                    func_code = ast.get_source_segment(content, node)
                    if func_code:
                        docstring = ast.get_docstring(node)
                        units.append({
                            "type": UnitType.FUNCTION,
                            "name": node.name,
                            "docstring": docstring,
                            "code": func_code,
                            "file_path": file_path,
                            "start_line": node.lineno,
                            "end_line": node.end_lineno
                        })
                
                elif isinstance(node, ast.ClassDef):
                    class_code = ast.get_source_segment(content, node)
                    if class_code:
                        docstring = ast.get_docstring(node)
                        class_unit = {
                            "type": UnitType.CLASS,
                            "name": node.name,
                            "docstring": docstring,
                            "code": class_code,
                            "file_path": file_path,
                            "start_line": node.lineno,
                            "end_line": node.end_lineno,
                            "methods": []
                        }
                        
                        # Extract methods
                        for item in node.body:
                            if isinstance(item, ast.FunctionDef):
                                method_code = ast.get_source_segment(content, item)
                                if method_code:
                                    method_docstring = ast.get_docstring(item)
                                    class_unit["methods"].append({
                                        "type": UnitType.METHOD,
                                        "name": f"{node.name}.{item.name}",
                                        "docstring": method_docstring,
                                        "code": method_code,
                                        "file_path": file_path,
                                        "start_line": item.lineno,
                                        "end_line": item.end_lineno
                                    })
                        
                        units.append(class_unit)
            
            return units
            
        except SyntaxError as e:
            logger.error(f"Syntax error parsing Python file {file_path}: {e}")
            return self._extract_generic_units(content, file_path)
        except Exception as e:
            logger.error(f"Error extracting Python units: {e}")
            return self._extract_generic_units(content, file_path)
    
    def _extract_js_units(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """Extract units from JavaScript/TypeScript code using regex patterns."""
        logger.debug("Extracting JavaScript/TypeScript code units")
        units = []
        
        try:
            # Simple regex for JS functions, classes, and methods
            # This is a simplified approach, a proper parser would be better
            
            # Extract functions
            function_pattern = r'(async\s+)?function\s+(\w+)\s*\([^)]*\)\s*{[^}]*}'
            function_matches = re.finditer(function_pattern, content, re.DOTALL)
            
            for match in function_matches:
                func_name = match.group(2)
                func_code = match.group(0)
                
                units.append({
                    "type": UnitType.FUNCTION,
                    "name": func_name,
                    "code": func_code,
                    "file_path": file_path,
                    "start_line": content[:match.start()].count('\n') + 1,
                    "end_line": content[:match.end()].count('\n') + 1
                })
            
            # Extract classes
            class_pattern = r'class\s+(\w+)(?:\s+extends\s+\w+)?\s*{[^}]*}'
            class_matches = re.finditer(class_pattern, content, re.DOTALL)
            
            for match in class_matches:
                class_name = match.group(1)
                class_code = match.group(0)
                
                class_unit = {
                    "type": UnitType.CLASS,
                    "name": class_name,
                    "code": class_code,
                    "file_path": file_path,
                    "start_line": content[:match.start()].count('\n') + 1,
                    "end_line": content[:match.end()].count('\n') + 1,
                    "methods": []
                }
                
                # Extract methods within the class
                method_pattern = r'(?:async\s+)?(\w+)\s*\([^)]*\)\s*{[^}]*}'
                method_matches = re.finditer(method_pattern, class_code, re.DOTALL)
                
                for method_match in method_matches:
                    method_name = method_match.group(1)
                    if method_name != 'constructor':  # Skip constructor for simplicity
                        method_code = method_match.group(0)
                        
                        class_start_line = content[:match.start()].count('\n') + 1
                        method_start_offset = class_code[:method_match.start()].count('\n')
                        method_end_offset = class_code[:method_match.end()].count('\n')
                        
                        class_unit["methods"].append({
                            "type": UnitType.METHOD,
                            "name": f"{class_name}.{method_name}",
                            "code": method_code,
                            "file_path": file_path,
                            "start_line": class_start_line + method_start_offset,
                            "end_line": class_start_line + method_end_offset
                        })
                
                units.append(class_unit)
            
            return units
            
        except Exception as e:
            logger.error(f"Error extracting JS/TS units: {e}")
            return self._extract_generic_units(content, file_path)
    
    def _extract_java_units(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """Extract units from Java code using regex patterns."""
        logger.debug("Extracting Java code units")
        
        # For simplicity, we'll use generic extraction for Java
        # A proper parser would be better
        return self._extract_generic_units(content, file_path)
    
    def _extract_rust_units(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """Extract units from Rust code using regex patterns."""
        logger.debug("Extracting Rust code units")
        
        # For simplicity, we'll use generic extraction for Rust
        # A proper parser would be better
        return self._extract_generic_units(content, file_path)
    
    def _extract_go_units(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """Extract units from Go code using regex patterns."""
        logger.debug("Extracting Go code units")
        
        # For simplicity, we'll use generic extraction for Go
        # A proper parser would be better
        return self._extract_generic_units(content, file_path)
    
    def _extract_generic_units(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """
        Extract units from generic code using simple line-based approach.
        Used as a fallback for unsupported languages or when parsing fails.
        """
        logger.debug("Extracting generic code units")
        
        # Split content into chunks of 50 lines max
        lines = content.split('\n')
        chunks = [lines[i:i+50] for i in range(0, len(lines), 50)]
        
        units = []
        for i, chunk in enumerate(chunks):
            start_line = i * 50 + 1
            end_line = start_line + len(chunk) - 1
            
            units.append({
                "type": UnitType.UNKNOWN,
                "name": f"chunk_{i}",
                "code": '\n'.join(chunk),
                "file_path": file_path,
                "start_line": start_line,
                "end_line": end_line
            })
        
        return units 