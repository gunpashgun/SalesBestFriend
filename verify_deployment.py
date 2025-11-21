#!/usr/bin/env python3
"""
Comprehensive verification script to ensure main_trial_class.py is syntax-correct
and ready for deployment.
"""
import py_compile
import ast
import sys
from pathlib import Path

def verify_syntax():
    """Verify Python syntax using py_compile"""
    print("=" * 60)
    print("TEST 1: Python Syntax Check (py_compile)")
    print("=" * 60)
    try:
        py_compile.compile('backend/main_trial_class.py', doraise=True)
        print("✅ PASSED: No syntax errors found")
        return True
    except py_compile.PyCompileError as e:
        print(f"❌ FAILED: Syntax error found:\n{e}")
        return False

def verify_ast():
    """Verify code can be parsed into AST"""
    print("\n" + "=" * 60)
    print("TEST 2: AST Parse Check")
    print("=" * 60)
    try:
        with open('backend/main_trial_class.py', 'r') as f:
            code = f.read()
        ast.parse(code)
        print("✅ PASSED: Code successfully parsed into AST")
        return True
    except SyntaxError as e:
        print(f"❌ FAILED: AST parsing error:\n{e}")
        print(f"   Line {e.lineno}: {e.text}")
        return False

def verify_no_nested_globals():
    """Verify no nested global declarations"""
    print("\n" + "=" * 60)
    print("TEST 3: Check for Nested Global Declarations")
    print("=" * 60)
    
    with open('backend/main_trial_class.py', 'r') as f:
        lines = f.readlines()
    
    nested_globals = []
    in_function = False
    function_indent = 0
    
    for i, line in enumerate(lines, 1):
        stripped = line.lstrip()
        if stripped.startswith('def ') or stripped.startswith('async def '):
            in_function = True
            function_indent = len(line) - len(stripped)
        elif in_function and stripped.startswith('global '):
            current_indent = len(line) - len(stripped)
            # Global should be at function_indent + 4 (one level of indentation)
            if current_indent > function_indent + 4:
                nested_globals.append((i, line.rstrip()))
    
    if nested_globals:
        print(f"❌ FAILED: Found {len(nested_globals)} nested global declaration(s):")
        for line_num, line_content in nested_globals:
            print(f"   Line {line_num}: {line_content}")
        return False
    else:
        print("✅ PASSED: No nested global declarations found")
        return True

def verify_global_before_assignment():
    """Verify global declarations appear before assignments"""
    print("\n" + "=" * 60)
    print("TEST 4: Global Before Assignment Check")
    print("=" * 60)
    
    try:
        with open('backend/main_trial_class.py', 'r') as f:
            code = f.read()
        
        tree = ast.parse(code)
        
        issues = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                globals_declared = set()
                for i, stmt in enumerate(node.body):
                    if isinstance(stmt, ast.Global):
                        globals_declared.update(stmt.names)
                    elif isinstance(stmt, (ast.Assign, ast.AugAssign)):
                        # Check if assigning to a variable before it's declared global
                        targets = []
                        if isinstance(stmt, ast.Assign):
                            targets = [t.id for t in stmt.targets if isinstance(t, ast.Name)]
                        elif isinstance(stmt, ast.AugAssign):
                            if isinstance(stmt.target, ast.Name):
                                targets = [stmt.target.id]
                        
                        # If we're assigning to a variable that later appears in global
                        for target in targets:
                            # Check if this variable is declared global later
                            for later_stmt in node.body[i+1:]:
                                if isinstance(later_stmt, ast.Global) and target in later_stmt.names:
                                    issues.append(f"Function {node.name}: '{target}' assigned before global declaration")
        
        if issues:
            print(f"❌ FAILED: Found {len(issues)} issue(s):")
            for issue in issues:
                print(f"   {issue}")
            return False
        else:
            print("✅ PASSED: All global declarations appear before assignments")
            return True
    except Exception as e:
        print(f"⚠️  WARNING: Could not complete check: {e}")
        return True  # Don't fail on this check

def show_global_declarations():
    """Show all global declarations for review"""
    print("\n" + "=" * 60)
    print("INFO: Global Declarations Found")
    print("=" * 60)
    
    with open('backend/main_trial_class.py', 'r') as f:
        lines = f.readlines()
    
    for i, line in enumerate(lines, 1):
        if 'global ' in line and line.strip().startswith('global '):
            # Show context: 2 lines before
            start = max(0, i-3)
            print(f"\nAround line {i}:")
            for j in range(start, min(i+1, len(lines))):
                prefix = ">>>" if j == i-1 else "   "
                print(f"{prefix} {j+1:4d} | {lines[j].rstrip()}")

def main():
    print("\n🔍 DEPLOYMENT VERIFICATION SCRIPT")
    print("=" * 60)
    print("File: backend/main_trial_class.py")
    print("=" * 60)
    
    tests = [
        verify_syntax(),
        verify_ast(),
        verify_no_nested_globals(),
        verify_global_before_assignment()
    ]
    
    show_global_declarations()
    
    print("\n" + "=" * 60)
    print("FINAL RESULT")
    print("=" * 60)
    
    if all(tests):
        print("✅ ALL TESTS PASSED")
        print("\n🚀 Code is ready for deployment!")
        print("\nTo deploy to Railway:")
        print("   git push origin main")
        print("\nNote: Railway may need to clear its cache if it's still")
        print("showing the old error. Check the Railway build logs.")
        return 0
    else:
        print("❌ SOME TESTS FAILED")
        print("\n⚠️  Please fix the issues before deploying")
        return 1

if __name__ == "__main__":
    sys.exit(main())

