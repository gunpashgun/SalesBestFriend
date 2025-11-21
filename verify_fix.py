#!/usr/bin/env python3
"""
Verify that main_trial_class.py has no nested global declarations
"""

import ast
import sys

def check_nested_globals(filename):
    """Check if a Python file has nested global declarations"""
    with open(filename, 'r') as f:
        source = f.read()
    
    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError as e:
        print(f"❌ SYNTAX ERROR: {e}")
        return False
    
    errors = []
    
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            # Track which variables are declared global at function level
            function_level_globals = set()
            
            # Check global declarations at function level (body[0], body[1], etc.)
            for stmt in node.body:
                if isinstance(stmt, ast.Global):
                    function_level_globals.update(stmt.names)
            
            # Now check for nested global declarations
            def check_nested(node, depth=0):
                for child in ast.walk(node):
                    if child != node and isinstance(child, ast.Global):
                        # This is a nested global declaration
                        errors.append(
                            f"❌ Function '{node.name}' line {node.lineno}: "
                            f"Nested global declaration at line {child.lineno} for {child.names}"
                        )
            
            # Check nested statements (inside if, while, try, etc.)
            for i, stmt in enumerate(node.body):
                # Skip top-level global declarations
                if i < 10 and isinstance(stmt, ast.Global):
                    continue
                # Check everything else for nested globals
                check_nested(stmt)
    
    if errors:
        print(f"❌ Found {len(errors)} nested global declaration(s):")
        for error in errors:
            print(f"   {error}")
        return False
    else:
        print("✅ No nested global declarations found!")
        return True


if __name__ == "__main__":
    filename = "backend/main_trial_class.py"
    print(f"🔍 Checking {filename}...")
    print()
    
    success = check_nested_globals(filename)
    
    if success:
        print()
        print("✅ Syntax verification PASSED!")
        print("   The file is ready to deploy.")
        sys.exit(0)
    else:
        print()
        print("❌ Syntax verification FAILED!")
        print("   Please fix the errors before deploying.")
        sys.exit(1)

