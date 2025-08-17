#!/usr/bin/env python3
"""
Python as a Function Tool Wrapper
Based on OpenAI's gpt-oss implementation but adapted for function namespace
"""

import asyncio
import subprocess
import tempfile
import os
import sys
import json
from typing import Dict, Any

class PythonFunctionTool:
    """Python tool that works in the functions namespace"""
    
    def __init__(self, timeout=120):
        self.timeout = timeout
        
    def get_tool_definition(self) -> Dict[str, Any]:
        """Return the tool definition for the functions namespace"""
        return {
            "name": "python",
            "description": "Execute Python code and return the output. IMPORTANT: You MUST use print() to produce output. The code runs in a stateless environment. Example: print(random.randint(1,20)) NOT just random.randint(1,20)",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Python code to execute. ALWAYS use print() to show results. Example: print(random.randint(1,20)) will output the number. Just random.randint(1,20) will output nothing."
                    }
                },
                "required": ["code"]
            }
        }
    
    def execute(self, code: str) -> Dict[str, Any]:
        """Execute Python code and return the result"""
        try:
            # Create a temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(code)
                temp_file = f.name
            
            # Execute the script
            result = subprocess.run(
                [sys.executable, temp_file],
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            
            # Clean up
            os.unlink(temp_file)
            
            # Prepare output
            output = result.stdout
            if result.stderr:
                output += f"\n[STDERR]\n{result.stderr}"
                
            return {"output": output if output else "[No output]"}
            
        except subprocess.TimeoutExpired:
            return {"error": f"Code execution timed out after {self.timeout} seconds"}
        except Exception as e:
            return {"error": f"Execution error: {str(e)}"}
    
    def handle_tool_call(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle a tool call from the model"""
        code = params.get('code', '')
        if not code:
            return {"error": "No code provided"}
        
        return self.execute(code)


# Integration helper
def add_python_to_functions(existing_tools: list) -> list:
    """Add Python tool to the functions list"""
    python_tool = PythonFunctionTool()
    tools = existing_tools.copy()
    tools.append(python_tool.get_tool_definition())
    return tools


# Test if run directly
if __name__ == "__main__":
    tool = PythonFunctionTool()
    
    # Test the tool
    test_code = """
import random
result = random.randint(1, 20)
print(f"D20 roll: {result}")
"""
    
    print("Testing Python as Function Tool")
    print("="*60)
    print(f"Tool definition: {json.dumps(tool.get_tool_definition(), indent=2)}")
    print(f"\nExecuting test code:")
    print(test_code)
    print(f"\nResult: {tool.handle_tool_call({'code': test_code})}")