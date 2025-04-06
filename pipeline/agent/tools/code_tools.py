"""
Code tools for PR context extraction agents.
These tools help agents analyze and manipulate code.
"""

import logging
import os
import tempfile
import subprocess
from typing import Any, Dict, List, Optional
from langchain.tools import BaseTool, tool

# Setup logger
logger = logging.getLogger("code_tools")

@tool
def get_code_at_commit(commit_hash: str, file_path: str) -> str:
    """
    Get the content of a file at a specific commit.
    
    Args:
        commit_hash: The commit hash to get the file content from
        file_path: Path to the file
        
    Returns:
        str: Content of the file at the given commit
    """
    logger.debug(f"Getting code at commit {commit_hash} for {file_path}")
    
    try:
        # Use git show to get file content at commit
        command = ["git", "show", f"{commit_hash}:{file_path}"]
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        logger.error(f"Error getting code at commit: {str(e)}")
        raise RuntimeError(f"Could not get file content at commit {commit_hash}: {e.stderr}")

@tool
def get_current_code_segment(file_path: str, start_line: int = None, end_line: int = None) -> str:
    """
    Get a specific code segment from the current version of a file.
    
    Args:
        file_path: Path to the file
        start_line: Starting line (1-indexed)
        end_line: Ending line (1-indexed)
        
    Returns:
        str: Content of the specified segment
    """
    logger.debug(f"Getting current code segment from {file_path}")
    
    try:
        # Read the file
        with open(file_path, 'r') as f:
            lines = f.readlines()
        
        # Return specific lines if provided
        if start_line is not None and end_line is not None:
            # Adjust for 1-indexed input
            if start_line < 1:
                start_line = 1
            if end_line > len(lines):
                end_line = len(lines)
                
            return ''.join(lines[start_line-1:end_line])
        else:
            # Return the entire file
            return ''.join(lines)
    except Exception as e:
        logger.error(f"Error getting current code segment: {str(e)}")
        raise RuntimeError(f"Could not get code segment from {file_path}: {str(e)}")

@tool
def parse_code(code: str, language: str = None) -> Dict[str, Any]:
    """
    Parse code to extract structures like functions, classes, etc.
    
    Args:
        code: The code text to parse
        language: Programming language of the code
        
    Returns:
        Dict[str, Any]: Parsed code structure
    """
    logger.debug(f"Parsing code for {language or 'unknown'} language")
    
    # Detect language if not provided
    if not language:
        # Simple language detection based on content
        if "fn " in code and "pub " in code and "impl " in code:
            language = "rust"
        elif "def " in code and ":" in code:
            language = "python"
        elif "function " in code or "const " in code or "let " in code:
            language = "javascript"
        elif "class " in code and "{" in code:
            language = "java"
        elif "func " in code and "package " in code:
            language = "go"
        else:
            language = "unknown"
    
    # Use appropriate parser based on language
    if language == "rust":
        return _parse_rust_code(code)
    elif language == "python":
        return _parse_python_code(code)
    else:
        # For other languages, use a simplified generic parser
        return _parse_generic_code(code, language)

def _parse_rust_code(code: str) -> Dict[str, Any]:
    """
    Parse Rust code using tree-sitter.
    
    Args:
        code: Rust code to parse
        
    Returns:
        Dict[str, Any]: Parsed structure
    """
    try:
        # This is a simplified implementation
        # In a real implementation, you would:
        # 1. Use tree-sitter to parse the code
        # 2. Traverse the AST to extract functions, structs, traits, etc.
        
        functions = []
        structs = []
        traits = []
        impls = []
        
        # Simple regex-based extraction (not reliable, but simple for prototype)
        import re
        
        # Find functions
        fn_pattern = r'(pub\s+)?(async\s+)?fn\s+([a-zA-Z0-9_]+)\s*\('
        for match in re.finditer(fn_pattern, code):
            fn_name = match.group(3)
            
            # Extract the function body (simplified)
            fn_start = match.start()
            body_start = code.find('{', fn_start)
            if body_start > 0:
                # Find matching closing brace
                open_braces = 1
                body_end = body_start
                for i in range(body_start + 1, len(code)):
                    if code[i] == '{':
                        open_braces += 1
                    elif code[i] == '}':
                        open_braces -= 1
                        if open_braces == 0:
                            body_end = i
                            break
                
                if body_end > body_start:
                    fn_code = code[fn_start:body_end+1]
                    functions.append({
                        "name": fn_name,
                        "code": fn_code,
                        "start_line": code[:fn_start].count('\n') + 1,
                        "end_line": code[:body_end].count('\n') + 1
                    })
        
        # Find structs
        struct_pattern = r'(pub\s+)?struct\s+([a-zA-Z0-9_]+)'
        for match in re.finditer(struct_pattern, code):
            struct_name = match.group(2)
            
            # Extract the struct body (simplified)
            struct_start = match.start()
            body_start = code.find('{', struct_start)
            if body_start > 0:
                # Find matching closing brace
                open_braces = 1
                body_end = body_start
                for i in range(body_start + 1, len(code)):
                    if code[i] == '{':
                        open_braces += 1
                    elif code[i] == '}':
                        open_braces -= 1
                        if open_braces == 0:
                            body_end = i
                            break
                
                if body_end > body_start:
                    struct_code = code[struct_start:body_end+1]
                    structs.append({
                        "name": struct_name,
                        "code": struct_code,
                        "start_line": code[:struct_start].count('\n') + 1,
                        "end_line": code[:body_end].count('\n') + 1
                    })
        
        # Find traits
        trait_pattern = r'(pub\s+)?trait\s+([a-zA-Z0-9_]+)'
        for match in re.finditer(trait_pattern, code):
            trait_name = match.group(2)
            
            # Extract the trait body (simplified)
            trait_start = match.start()
            body_start = code.find('{', trait_start)
            if body_start > 0:
                # Find matching closing brace
                open_braces = 1
                body_end = body_start
                for i in range(body_start + 1, len(code)):
                    if code[i] == '{':
                        open_braces += 1
                    elif code[i] == '}':
                        open_braces -= 1
                        if open_braces == 0:
                            body_end = i
                            break
                
                if body_end > body_start:
                    trait_code = code[trait_start:body_end+1]
                    traits.append({
                        "name": trait_name,
                        "code": trait_code,
                        "start_line": code[:trait_start].count('\n') + 1,
                        "end_line": code[:body_end].count('\n') + 1
                    })
        
        # Find impls
        impl_pattern = r'impl(\s+<[^>]+>)?\s+([a-zA-Z0-9_:]+)\s+for\s+([a-zA-Z0-9_:]+)'
        for match in re.finditer(impl_pattern, code):
            impl_trait = match.group(2)
            impl_for = match.group(3)
            
            # Extract the impl body (simplified)
            impl_start = match.start()
            body_start = code.find('{', impl_start)
            if body_start > 0:
                # Find matching closing brace
                open_braces = 1
                body_end = body_start
                for i in range(body_start + 1, len(code)):
                    if code[i] == '{':
                        open_braces += 1
                    elif code[i] == '}':
                        open_braces -= 1
                        if open_braces == 0:
                            body_end = i
                            break
                
                if body_end > body_start:
                    impl_code = code[impl_start:body_end+1]
                    impls.append({
                        "trait": impl_trait,
                        "for_type": impl_for,
                        "code": impl_code,
                        "start_line": code[:impl_start].count('\n') + 1,
                        "end_line": code[:body_end].count('\n') + 1
                    })
        
        return {
            "language": "rust",
            "functions": functions,
            "structs": structs,
            "traits": traits,
            "impls": impls
        }
    except Exception as e:
        logger.error(f"Error parsing Rust code: {str(e)}")
        # Return simplified structure on error
        return {
            "language": "rust",
            "functions": [],
            "structs": [],
            "traits": [],
            "impls": [],
            "error": str(e)
        }

def _parse_python_code(code: str) -> Dict[str, Any]:
    """
    Parse Python code.
    
    Args:
        code: Python code to parse
        
    Returns:
        Dict[str, Any]: Parsed structure
    """
    try:
        # Simple parsing for Python code
        # In a real implementation, you would use ast module
        
        functions = []
        classes = []
        
        # Simple regex-based extraction (not reliable, but simple for prototype)
        import re
        
        # Find functions
        fn_pattern = r'def\s+([a-zA-Z0-9_]+)\s*\('
        for match in re.finditer(fn_pattern, code):
            fn_name = match.group(1)
            
            # Extract the function body (simplified)
            fn_start = match.start()
            body_start = code.find(':', fn_start)
            
            if body_start > 0:
                # Get indentation level
                next_line_start = code.find('\n', body_start) + 1
                if next_line_start > 0 and next_line_start < len(code):
                    # Find the first non-whitespace character
                    current_indent = 0
                    for i in range(next_line_start, len(code)):
                        if code[i].isspace():
                            current_indent += 1
                        else:
                            break
                    
                    # Find the end of the function based on indentation
                    body_end = next_line_start
                    for i in range(next_line_start, len(code)):
                        if i == 0 or code[i-1] == '\n':
                            # Check indentation at start of line
                            line_indent = 0
                            for j in range(i, min(i+current_indent, len(code))):
                                if code[j].isspace():
                                    line_indent += 1
                                else:
                                    break
                            
                            if line_indent < current_indent and code[i] != '\n' and i > next_line_start:
                                # Found a line with less indentation
                                body_end = i - 1
                                break
                    
                    if body_end > body_start:
                        fn_code = code[fn_start:body_end]
                        functions.append({
                            "name": fn_name,
                            "code": fn_code,
                            "start_line": code[:fn_start].count('\n') + 1,
                            "end_line": code[:body_end].count('\n') + 1
                        })
        
        # Find classes
        class_pattern = r'class\s+([a-zA-Z0-9_]+)(\s*\([^)]*\))?:'
        for match in re.finditer(class_pattern, code):
            class_name = match.group(1)
            
            # Extract the class body (simplified)
            class_start = match.start()
            body_start = match.end()
            
            if body_start > 0:
                # Get indentation level
                next_line_start = code.find('\n', body_start) + 1
                if next_line_start > 0 and next_line_start < len(code):
                    # Find the first non-whitespace character
                    current_indent = 0
                    for i in range(next_line_start, len(code)):
                        if code[i].isspace():
                            current_indent += 1
                        else:
                            break
                    
                    # Find the end of the class based on indentation
                    body_end = next_line_start
                    for i in range(next_line_start, len(code)):
                        if i == 0 or code[i-1] == '\n':
                            # Check indentation at start of line
                            line_indent = 0
                            for j in range(i, min(i+current_indent, len(code))):
                                if code[j].isspace():
                                    line_indent += 1
                                else:
                                    break
                            
                            if line_indent < current_indent and code[i] != '\n' and i > next_line_start:
                                # Found a line with less indentation
                                body_end = i - 1
                                break
                    
                    if body_end > body_start:
                        class_code = code[class_start:body_end]
                        classes.append({
                            "name": class_name,
                            "code": class_code,
                            "start_line": code[:class_start].count('\n') + 1,
                            "end_line": code[:body_end].count('\n') + 1
                        })
        
        return {
            "language": "python",
            "functions": functions,
            "classes": classes
        }
    except Exception as e:
        logger.error(f"Error parsing Python code: {str(e)}")
        # Return simplified structure on error
        return {
            "language": "python",
            "functions": [],
            "classes": [],
            "error": str(e)
        }

def _parse_generic_code(code: str, language: str) -> Dict[str, Any]:
    """
    Generic code parser for unsupported languages.
    
    Args:
        code: Code to parse
        language: Programming language
        
    Returns:
        Dict[str, Any]: Simplified parsed structure
    """
    # For generic code, just provide a simplified structure
    lines = code.split('\n')
    return {
        "language": language,
        "total_lines": len(lines),
        "raw_code": code
    }

def get_code_tools(repo_path: str = None) -> List[BaseTool]:
    """
    Get a list of code tools.
    
    Args:
        repo_path: Path to the repository root
        
    Returns:
        List[BaseTool]: List of code tools
    """
    tools = [
        get_code_at_commit,
        get_current_code_segment,
        parse_code
    ]
    
    return tools 