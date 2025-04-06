"""
Repository tools for PR context extraction agents.
These tools help agents analyze code repository structure and relationships.
"""

import logging
import os
import subprocess
import re
from typing import Any, Dict, List, Optional
from langchain.tools import BaseTool, tool

# Setup logger
logger = logging.getLogger("repo_tools")

@tool
def find_callers(function_name: str, file_path: str, repo_path: Optional[str] = None) -> List[Dict[str, str]]:
    """
    Find all functions that call a specific function.
    
    Args:
        function_name: Name of the function to find callers for
        file_path: Path to the file containing the function
        repo_path: Optional path to the repository root
        
    Returns:
        List[Dict[str, str]]: List of caller information (name and file)
    """
    logger.debug(f"Finding callers of {function_name} in {file_path}")
    
    try:
        # Change directory to repo path if provided
        current_dir = os.getcwd()
        if repo_path:
            os.chdir(repo_path)
        
        # For Rust code, use simple regex for function calls
        # This is a simplified implementation
        # In a real implementation, you might use a more sophisticated approach
        
        # Get the file extension to determine language
        _, extension = os.path.splitext(file_path)
        
        callers = []
        
        if extension == ".rs":
            # For Rust, look for function calls like "function_name(" or "function_name::<"
            pattern = re.escape(function_name) + r'(\s*::<[^>]*>)?\s*\('
            
            # Use ripgrep if available for faster searching
            try:
                rg_command = ["rg", "-l", pattern]
                result = subprocess.run(rg_command, capture_output=True, text=True, check=True)
                matching_files = result.stdout.strip().split('\n')
                
                for matching_file in matching_files:
                    if not matching_file:
                        continue
                    
                    # Skip the file itself
                    if os.path.samefile(matching_file, file_path):
                        continue
                    
                    # Find the functions in this file that call the target function
                    with open(matching_file, 'r') as f:
                        content = f.read()
                    
                    # Extract functions (simplified approach)
                    fn_matches = re.finditer(r'(pub\s+)?(async\s+)?fn\s+([a-zA-Z0-9_]+)\s*\(', content)
                    for fn_match in fn_matches:
                        caller_name = fn_match.group(3)
                        
                        # Check if this function calls the target function
                        fn_start = fn_match.start()
                        body_start = content.find('{', fn_start)
                        if body_start > 0:
                            # Find matching closing brace
                            open_braces = 1
                            body_end = body_start
                            for i in range(body_start + 1, len(content)):
                                if content[i] == '{':
                                    open_braces += 1
                                elif content[i] == '}':
                                    open_braces -= 1
                                    if open_braces == 0:
                                        body_end = i
                                        break
                            
                            if body_end > body_start:
                                # Check if function body contains a call
                                fn_body = content[body_start:body_end+1]
                                call_match = re.search(pattern, fn_body)
                                if call_match:
                                    callers.append({"name": caller_name, "file": matching_file})
            except subprocess.CalledProcessError:
                # Fallback to grep if ripgrep is not available
                grep_command = ["grep", "-l", pattern, "--include=*.rs", "-r", "."]
                try:
                    result = subprocess.run(grep_command, capture_output=True, text=True, check=True)
                    matching_files = result.stdout.strip().split('\n')
                    
                    # Process each file as above
                    # (Code would be similar to the ripgrep case)
                except subprocess.CalledProcessError:
                    logger.warning("Both ripgrep and grep failed, no callers found")
        
        # Go back to original directory
        if repo_path:
            os.chdir(current_dir)
        
        return callers
    except Exception as e:
        logger.error(f"Error finding callers: {str(e)}")
        
        # Go back to original directory
        if repo_path:
            os.chdir(current_dir)
        
        # Return empty list on error
        return []

@tool
def find_callees(function_name: str, file_path: str, repo_path: Optional[str] = None) -> List[Dict[str, str]]:
    """
    Find all functions called by a specific function.
    
    Args:
        function_name: Name of the function to find callees for
        file_path: Path to the file containing the function
        repo_path: Optional path to the repository root
        
    Returns:
        List[Dict[str, str]]: List of callee information (name and file)
    """
    logger.debug(f"Finding callees of {function_name} in {file_path}")
    
    try:
        # Change directory to repo path if provided
        current_dir = os.getcwd()
        if repo_path:
            os.chdir(repo_path)
        
        # Read the file
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Get the file extension to determine language
        _, extension = os.path.splitext(file_path)
        
        callees = []
        
        if extension == ".rs":
            # Extract the function body
            fn_pattern = r'(pub\s+)?(async\s+)?fn\s+' + re.escape(function_name) + r'\s*\('
            fn_match = re.search(fn_pattern, content)
            
            if fn_match:
                fn_start = fn_match.start()
                body_start = content.find('{', fn_start)
                
                if body_start > 0:
                    # Find matching closing brace
                    open_braces = 1
                    body_end = body_start
                    for i in range(body_start + 1, len(content)):
                        if content[i] == '{':
                            open_braces += 1
                        elif content[i] == '}':
                            open_braces -= 1
                            if open_braces == 0:
                                body_end = i
                                break
                    
                    if body_end > body_start:
                        # Find function calls in the body
                        fn_body = content[body_start:body_end+1]
                        
                        # Simple regex pattern for function calls
                        # This is a simplified approach that won't catch all cases
                        call_pattern = r'([a-zA-Z0-9_:]+)(\s*::<[^>]*>)?\s*\('
                        for call_match in re.finditer(call_pattern, fn_body):
                            callee_name = call_match.group(1)
                            
                            # Skip self calls
                            if callee_name == function_name:
                                continue
                                
                            # Skip method calls (with dot notation)
                            if '.' in callee_name:
                                continue
                                
                            # Add to the list of callees
                            callees.append({"name": callee_name, "file": "unknown"})
            
            # Resolve file paths for callees (would be more complex in a real implementation)
        
        # Go back to original directory
        if repo_path:
            os.chdir(current_dir)
        
        return callees
    except Exception as e:
        logger.error(f"Error finding callees: {str(e)}")
        
        # Go back to original directory
        if repo_path:
            os.chdir(current_dir)
        
        # Return empty list on error
        return []

@tool
def analyze_dependencies(file_path: str, repo_path: Optional[str] = None) -> Dict[str, List[str]]:
    """
    Analyze dependencies for a file.
    
    Args:
        file_path: Path to the file to analyze
        repo_path: Optional path to the repository root
        
    Returns:
        Dict[str, List[str]]: Dependencies information
    """
    logger.debug(f"Analyzing dependencies for {file_path}")
    
    try:
        # Change directory to repo path if provided
        current_dir = os.getcwd()
        if repo_path:
            os.chdir(repo_path)
        
        # Read the file
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Get the file extension to determine language
        _, extension = os.path.splitext(file_path)
        
        imports = []
        exported = []
        
        if extension == ".rs":
            # Find imports in Rust (use, extern crate)
            for line in content.split('\n'):
                # Look for use statements
                if line.strip().startswith('use '):
                    import_match = re.search(r'use\s+([^;]+);', line)
                    if import_match:
                        imports.append(import_match.group(1).strip())
                
                # Look for extern crate statements
                if line.strip().startswith('extern crate '):
                    extern_match = re.search(r'extern\s+crate\s+([^;]+);', line)
                    if extern_match:
                        imports.append(extern_match.group(1).strip())
            
            # Find exports in Rust (pub items)
            for line in content.split('\n'):
                if re.search(r'^\s*pub\s+(fn|struct|enum|trait|type|const)\s+([a-zA-Z0-9_]+)', line):
                    export_match = re.search(r'pub\s+(fn|struct|enum|trait|type|const)\s+([a-zA-Z0-9_]+)', line)
                    if export_match:
                        item_type = export_match.group(1)
                        item_name = export_match.group(2)
                        exported.append(f"{item_type} {item_name}")
        
        # Go back to original directory
        if repo_path:
            os.chdir(current_dir)
        
        return {
            "imports": imports,
            "exports": exported
        }
    except Exception as e:
        logger.error(f"Error analyzing dependencies: {str(e)}")
        
        # Go back to original directory
        if repo_path:
            os.chdir(current_dir)
        
        # Return empty data on error
        return {
            "imports": [],
            "exports": []
        }

@tool
def map_inheritance(class_name: str, file_path: str, repo_path: Optional[str] = None) -> Dict[str, List[Dict[str, str]]]:
    """
    Map inheritance relationships for a class.
    
    Args:
        class_name: Name of the class
        file_path: Path to the file containing the class
        repo_path: Optional path to the repository root
        
    Returns:
        Dict[str, List[Dict[str, str]]]: Inheritance information
    """
    logger.debug(f"Mapping inheritance for class {class_name} in {file_path}")
    
    try:
        # Change directory to repo path if provided
        current_dir = os.getcwd()
        if repo_path:
            os.chdir(repo_path)
        
        # Read the file
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Get the file extension to determine language
        _, extension = os.path.splitext(file_path)
        
        parents = []
        children = []
        
        if extension == ".rs":
            # In Rust, we look for trait implementations and trait definitions
            
            # Look for struct definition
            struct_pattern = r'(pub\s+)?struct\s+' + re.escape(class_name)
            struct_match = re.search(struct_pattern, content)
            
            if struct_match:
                # Look for trait implementations
                impl_pattern = r'impl(\s+<[^>]+>)?\s+([a-zA-Z0-9_:]+)\s+for\s+' + re.escape(class_name)
                for impl_match in re.finditer(impl_pattern, content):
                    trait_name = impl_match.group(2)
                    parents.append({"name": trait_name, "file": "unknown"})
            
            # Look for traits defined by this class
            trait_pattern = r'(pub\s+)?trait\s+' + re.escape(class_name)
            trait_match = re.search(trait_pattern, content)
            
            if trait_match:
                # Find implementations of this trait (would need to search all files)
                # This is simplified and would not be complete
                trait_impl_pattern = r'impl(\s+<[^>]+>)?\s+' + re.escape(class_name) + r'\s+for\s+([a-zA-Z0-9_:]+)'
                
                # Use ripgrep if available
                try:
                    rg_command = ["rg", "-l", trait_impl_pattern]
                    result = subprocess.run(rg_command, capture_output=True, text=True, check=True)
                    matching_files = result.stdout.strip().split('\n')
                    
                    for matching_file in matching_files:
                        if not matching_file:
                            continue
                        
                        # Read the file and find the actual implementations
                        with open(matching_file, 'r') as f:
                            file_content = f.read()
                        
                        for impl_match in re.finditer(trait_impl_pattern, file_content):
                            child_name = impl_match.group(2)
                            children.append({"name": child_name, "file": matching_file})
                except subprocess.CalledProcessError:
                    # Fallback to grep
                    try:
                        grep_command = ["grep", "-l", trait_impl_pattern, "--include=*.rs", "-r", "."]
                        result = subprocess.run(grep_command, capture_output=True, text=True, check=True)
                        matching_files = result.stdout.strip().split('\n')
                        
                        # Process files as above
                    except subprocess.CalledProcessError:
                        logger.warning("Both ripgrep and grep failed, no children found")
        
        # Go back to original directory
        if repo_path:
            os.chdir(current_dir)
        
        return {
            "parents": parents,
            "children": children
        }
    except Exception as e:
        logger.error(f"Error mapping inheritance: {str(e)}")
        
        # Go back to original directory
        if repo_path:
            os.chdir(current_dir)
        
        # Return empty data on error
        return {
            "parents": [],
            "children": []
        }

def get_repo_tools(repo_path: str = None) -> List[BaseTool]:
    """
    Get a list of repository tools.
    
    Args:
        repo_path: Path to the repository root
        
    Returns:
        List[BaseTool]: List of repository tools
    """
    tools = [
        find_callers,
        find_callees,
        analyze_dependencies,
        map_inheritance
    ]
    
    return tools 