#!/usr/bin/env python3
"""
Example script to test the Harmony tools
"""

import requests
import json

# Test the Python tool
def test_python_tool():
    """Test Python execution"""
    print("Testing Python tool...")
    
    response = requests.post(
        "http://localhost:5002/chat",
        json={
            "messages": [
                {
                    "role": "user",
                    "content": "Calculate the 1000th prime number"
                }
            ],
            "model": "meta-llama/Llama-3.2-3B-Instruct",
            "temperature": 0.7,
            "stream": False,
            "tools": ["python"]
        }
    )
    
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")

# Test the browser tool
def test_browser_tool():
    """Test browser navigation"""
    print("\nTesting Browser tool...")
    
    response = requests.post(
        "http://localhost:5002/chat",
        json={
            "messages": [
                {
                    "role": "user",
                    "content": "Go to example.com and tell me what you see"
                }
            ],
            "model": "meta-llama/Llama-3.2-3B-Instruct",
            "temperature": 0.7,
            "stream": False,
            "tools": ["browser"]
        }
    )
    
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")

if __name__ == "__main__":
    print("Make sure the Harmony app is running on http://localhost:5002")
    print("=" * 50)
    
    try:
        test_python_tool()
    except Exception as e:
        print(f"Python tool test failed: {e}")
    
    try:
        test_browser_tool()
    except Exception as e:
        print(f"Browser tool test failed: {e}")