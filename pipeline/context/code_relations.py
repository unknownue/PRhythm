"""
Code relations module for PR context extraction.
This module provides functionality for analyzing relationships between code units.
"""

import ast
import logging
import re
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union

# Setup logger
logger = logging.getLogger("code_relations")

class RelationType(str, Enum):
    """Enum for code relation types."""
    CALLS = "calls"
    IMPORTS = "imports"
    INHERITS = "inherits"
    CONTAINS = "contains"
    IMPLEMENTS = "implements"
    USES = "uses"
    REFERENCES = "references"
    UNKNOWN = "unknown"

class RelationDetector:
    """
    Detects relationships between code units.
    """
    
    def __init__(self):
        """Initialize the relation detector."""
        pass
    
    def detect_relations(self, code_units: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Detect relationships between code units.
        
        Args:
            code_units: List of code units
            
        Returns:
            List[Dict[str, Any]]: List of relationships
        """
        logger.debug(f"Detecting relations between {len(code_units)} code units")
        
        relations = []
        
        # First, collect all unit names for reference checking
        unit_names = {}
        for unit in code_units:
            unit_type = unit.get("type", "unknown")
            unit_name = unit.get("name", "")
            
            if unit_name:
                unit_names[unit_name] = unit
                
                # For methods, also add the method name without class prefix
                if "." in unit_name:
                    method_name = unit_name.split(".")[-1]
                    unit_names[method_name] = unit
        
        # Analyze each unit for relations
        for source_unit in code_units:
            source_type = source_unit.get("type", "unknown")
            source_name = source_unit.get("name", "")
            source_code = source_unit.get("code", "")
            
            if not source_code:
                continue
            
            # Analyze each unit
            file_ext = source_unit.get("file_path", "").split(".")[-1] if source_unit.get("file_path") else ""
            
            if file_ext == "py":
                # Python relation detection
                relations.extend(self._detect_python_relations(source_unit, code_units, unit_names))
            elif file_ext in ["js", "ts", "jsx", "tsx"]:
                # JavaScript/TypeScript relation detection
                relations.extend(self._detect_js_relations(source_unit, code_units, unit_names))
            else:
                # Generic relation detection for other languages
                relations.extend(self._detect_generic_relations(source_unit, code_units, unit_names))
        
        return relations
    
    def _detect_python_relations(self, source_unit: Dict[str, Any], 
                                code_units: List[Dict[str, Any]],
                                unit_names: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Detect relations in Python code."""
        relations = []
        source_name = source_unit.get("name", "")
        source_code = source_unit.get("code", "")
        source_type = source_unit.get("type", "")
        
        if not source_code or not source_name:
            return relations
        
        try:
            # Parse the code to get the AST for more accurate analysis
            tree = ast.parse(source_code)
            
            # Check for inheritance
            if source_type == "class":
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef) and node.name == source_name.split(".")[-1]:
                        for base in node.bases:
                            if isinstance(base, ast.Name) and base.id in unit_names:
                                relations.append({
                                    "source": source_name,
                                    "target": base.id,
                                    "type": RelationType.INHERITS,
                                    "description": f"{source_name} inherits from {base.id}"
                                })
            
            # Check for function calls
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name) and node.func.id in unit_names:
                        target_name = node.func.id
                        relations.append({
                            "source": source_name,
                            "target": target_name,
                            "type": RelationType.CALLS,
                            "description": f"{source_name} calls {target_name}"
                        })
                    elif isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
                        # Method calls like obj.method()
                        potential_target = f"{node.func.value.id}.{node.func.attr}"
                        if potential_target in unit_names:
                            relations.append({
                                "source": source_name,
                                "target": potential_target,
                                "type": RelationType.CALLS,
                                "description": f"{source_name} calls {potential_target}"
                            })
            
            # Check for imports
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for name in node.names:
                        if name.name in unit_names:
                            relations.append({
                                "source": source_name,
                                "target": name.name,
                                "type": RelationType.IMPORTS,
                                "description": f"{source_name} imports {name.name}"
                            })
                elif isinstance(node, ast.ImportFrom):
                    if node.module in unit_names:
                        relations.append({
                            "source": source_name,
                            "target": node.module,
                            "type": RelationType.IMPORTS,
                            "description": f"{source_name} imports from {node.module}"
                        })
                    for name in node.names:
                        full_name = f"{node.module}.{name.name}" if node.module else name.name
                        if full_name in unit_names:
                            relations.append({
                                "source": source_name,
                                "target": full_name,
                                "type": RelationType.IMPORTS,
                                "description": f"{source_name} imports {full_name}"
                            })
            
        except SyntaxError as e:
            logger.error(f"Syntax error parsing Python code for relations: {e}")
            return self._detect_generic_relations(source_unit, code_units, unit_names)
        except Exception as e:
            logger.error(f"Error detecting Python relations: {e}")
            return self._detect_generic_relations(source_unit, code_units, unit_names)
        
        return relations
    
    def _detect_js_relations(self, source_unit: Dict[str, Any], 
                            code_units: List[Dict[str, Any]],
                            unit_names: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Detect relations in JavaScript/TypeScript code."""
        relations = []
        source_name = source_unit.get("name", "")
        source_code = source_unit.get("code", "")
        source_type = source_unit.get("type", "")
        
        if not source_code or not source_name:
            return relations
        
        try:
            # Use regex patterns to identify relations
            
            # Check for imports
            import_patterns = [
                r'import\s+{\s*([^}]+)\s*}\s+from\s+[\'"]([^\'"]+)[\'"]',  # import { thing } from 'module'
                r'import\s+(\w+)\s+from\s+[\'"]([^\'"]+)[\'"]',  # import thing from 'module'
                r'require\([\'"]([^\'"]+)[\'"]\)'  # require('module')
            ]
            
            for pattern in import_patterns:
                for match in re.finditer(pattern, source_code):
                    if pattern.startswith('require'):
                        module_name = match.group(1)
                        if module_name in unit_names:
                            relations.append({
                                "source": source_name,
                                "target": module_name,
                                "type": RelationType.IMPORTS,
                                "description": f"{source_name} requires {module_name}"
                            })
                    elif pattern.startswith('import\\s+{'):
                        imported_items = match.group(1).split(',')
                        module_name = match.group(2)
                        
                        for item in imported_items:
                            item = item.strip()
                            if item in unit_names:
                                relations.append({
                                    "source": source_name,
                                    "target": item,
                                    "type": RelationType.IMPORTS,
                                    "description": f"{source_name} imports {item} from {module_name}"
                                })
                    else:
                        imported_item = match.group(1)
                        module_name = match.group(2)
                        
                        if imported_item in unit_names:
                            relations.append({
                                "source": source_name,
                                "target": imported_item,
                                "type": RelationType.IMPORTS,
                                "description": f"{source_name} imports {imported_item} from {module_name}"
                            })
            
            # Check for class inheritance
            if source_type == "class":
                extends_pattern = r'class\s+' + re.escape(source_name.split(".")[-1]) + r'\s+extends\s+(\w+)'
                for match in re.finditer(extends_pattern, source_code):
                    base_class = match.group(1)
                    if base_class in unit_names:
                        relations.append({
                            "source": source_name,
                            "target": base_class,
                            "type": RelationType.INHERITS,
                            "description": f"{source_name} extends {base_class}"
                        })
            
            # Check for function calls
            for unit_name, unit in unit_names.items():
                if unit_name == source_name:
                    continue
                    
                # Check for simple function calls: functionName()
                call_pattern = r'(?<![.\w])' + re.escape(unit_name.split(".")[-1]) + r'\s*\('
                if re.search(call_pattern, source_code):
                    relations.append({
                        "source": source_name,
                        "target": unit_name,
                        "type": RelationType.CALLS,
                        "description": f"{source_name} calls {unit_name}"
                    })
                
                # Check for method calls on objects: obj.methodName()
                if "." in unit_name:
                    obj_name, method_name = unit_name.split(".", 1)
                    method_pattern = r'(?<![.\w])' + re.escape(obj_name) + r'\.' + re.escape(method_name) + r'\s*\('
                    if re.search(method_pattern, source_code):
                        relations.append({
                            "source": source_name,
                            "target": unit_name,
                            "type": RelationType.CALLS,
                            "description": f"{source_name} calls {unit_name}"
                        })
            
        except Exception as e:
            logger.error(f"Error detecting JS/TS relations: {e}")
            return self._detect_generic_relations(source_unit, code_units, unit_names)
        
        return relations
    
    def _detect_generic_relations(self, source_unit: Dict[str, Any], 
                                code_units: List[Dict[str, Any]],
                                unit_names: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Detect relations in generic code.
        This is a simplified approach using string matching.
        """
        relations = []
        source_name = source_unit.get("name", "")
        source_code = source_unit.get("code", "")
        
        if not source_code or not source_name:
            return relations
        
        # Simple string matching for references
        for unit_name, unit in unit_names.items():
            if unit_name == source_name:
                continue
                
            # Only check for significant names (avoid common words)
            if len(unit_name) > 3:
                # Use word boundary regex to avoid partial matches
                if re.search(r'\b' + re.escape(unit_name) + r'\b', source_code):
                    relations.append({
                        "source": source_name,
                        "target": unit_name,
                        "type": RelationType.REFERENCES,
                        "description": f"{source_name} references {unit_name}"
                    })
        
        return relations
    
    def build_relation_graph(self, code_units: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Build a relation graph from code units.
        
        Args:
            code_units: List of code units
            
        Returns:
            Dict[str, Any]: Relation graph with nodes and edges
        """
        logger.debug("Building relation graph")
        
        # Detect relations
        relations = self.detect_relations(code_units)
        
        # Create graph
        nodes = []
        edges = []
        
        # Add nodes for each unit
        node_ids = set()
        for unit in code_units:
            unit_name = unit.get("name", "")
            if unit_name and unit_name not in node_ids:
                node_ids.add(unit_name)
                nodes.append({
                    "id": unit_name,
                    "type": unit.get("type", "unknown"),
                    "file_path": unit.get("file_path", "")
                })
        
        # Add edges for each relation
        for relation in relations:
            source_name = relation.get("source", "")
            target_name = relation.get("target", "")
            relation_type = relation.get("type", "")
            
            if source_name and target_name and source_name in node_ids and target_name in node_ids:
                edges.append({
                    "source": source_name,
                    "target": target_name,
                    "type": relation_type,
                    "description": relation.get("description", "")
                })
        
        return {
            "nodes": nodes,
            "edges": edges
        } 