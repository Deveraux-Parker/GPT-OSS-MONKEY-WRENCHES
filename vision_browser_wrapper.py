"""
Wrapper to integrate vision browser tool with harmony format
"""

import json
import logging
from typing import Dict, Any, Optional

from vision_browser_tool import VisionBrowserTool, HAS_SELENIUM

class VisionBrowserWrapper:
    """Wrapper that provides browser functionality in harmony functions format"""
    
    def __init__(self, mock_mode=False):
        self.browser = None
        self.initialized = False
        self.mock_mode = mock_mode or not HAS_SELENIUM
        
    def get_tool_definition(self) -> Dict[str, Any]:
        """Return the tool definition for the functions namespace"""
        return {
            "name": "browser",
            "description": "Control a web browser with visual feedback. Navigation automatically extracts page text. Actions: navigate, click, type, scroll, search, extract_text, extract_links, back, refresh, close_popups, wait, screenshot",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["navigate", "click", "type", "scroll", "search", "extract_text", 
                                "extract_links", "back", "refresh", "close_popups", "wait", "screenshot"],
                        "description": "The browser action to perform"
                    },
                    "parameters": {
                        "type": "object",
                        "description": "Action-specific parameters",
                        "properties": {
                            "url": {"type": "string", "description": "URL to navigate to (for navigate action)"},
                            "text": {"type": "string", "description": "Text to click/type/search (for click/type/search actions)"},
                            "into": {"type": "string", "description": "Element to type into (for type action)"},
                            "type": {"type": "string", "enum": ["any", "link", "button"], "description": "Element type (for click action)"},
                            "direction": {"type": "string", "enum": ["up", "down"], "description": "Scroll direction"},
                            "amount": {"type": "integer", "description": "Scroll amount in pixels"},
                            "nth": {"type": "integer", "description": "Which occurrence to find (for search action)"},
                            "key": {"type": "string", "enum": ["ENTER", "TAB", "ESCAPE", "BACKSPACE", "DELETE", "UP", "DOWN", "LEFT", "RIGHT"], "description": "Key to press"},
                            "seconds": {"type": "number", "description": "Seconds to wait"}
                        }
                    }
                },
                "required": ["action"]
            }
        }
    
    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the browser tool with given parameters"""
        # Check if we're in mock mode
        if self.mock_mode:
            return self._execute_mock(params)
            
        if not HAS_SELENIUM:
            return {
                "error": "Browser tool requires selenium and helium. Install with: pip install selenium helium pillow",
                "status": "error"
            }
            
        try:
            # Initialize browser on first use
            if not self.initialized:
                self.browser = VisionBrowserTool(headless=False)
                self.initialized = True
                
            action = params.get("action", "screenshot")
            action_params = params.get("parameters", {})
            
            # Execute the browser command
            result = self.browser.execute_browser_command(action, action_params)
            
            # Format the response for harmony
            if result.get("status") == "success":
                response = {
                    "status": "success",
                    "message": result.get("message", ""),
                    "url": result.get("url", ""),
                }
                
                # Include extracted data if available
                if "text" in result:
                    response["extracted_text"] = result["text"]
                if "links" in result:
                    response["links"] = result["links"]
                    
                # Include screenshot info (not the full base64 to avoid bloating the response)
                if "screenshot" in result:
                    response["screenshot_available"] = True
                    response["screenshot_size"] = result.get("size", [])
                    
                return response
            else:
                return {
                    "status": "error",
                    "error": result.get("message", "Unknown error"),
                    "url": result.get("url", "")
                }
                
        except Exception as e:
            logging.error(f"Browser tool error: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    def close(self):
        """Close the browser"""
        if self.browser:
            self.browser.close()
            self.browser = None
            self.initialized = False
    
    def _execute_mock(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute mock browser actions for testing"""
        action = params.get("action", "screenshot")
        action_params = params.get("parameters", {})
        
        # Mock responses for different actions
        if action == "navigate":
            url = action_params.get("url", "")
            # Automatically extract text after navigation
            mock_text = "Example Domain\n\nThis domain is for use in illustrative examples in documents. You may use this domain in literature without prior coordination or asking for permission.\n\nMore information..."
            return {
                "status": "success",
                "message": f"[MOCK] Navigated to {url}",
                "url": url,
                "screenshot_available": True,
                "screenshot_size": [1200, 800],
                "extracted_text": mock_text
            }
        
        elif action == "extract_text":
            # Return mock text based on current URL
            return {
                "status": "success",
                "message": "[MOCK] Extracted page text",
                "extracted_text": "Example Domain\n\nThis domain is for use in illustrative examples in documents. You may use this domain in literature without prior coordination or asking for permission.\n\nMore information...",
                "url": "https://example.com"
            }
        
        elif action == "click":
            text = action_params.get("text", "")
            return {
                "status": "success",
                "message": f"[MOCK] Clicked on '{text}'",
                "url": "https://example.com/clicked"
            }
        
        elif action == "type":
            text = action_params.get("text", "")
            return {
                "status": "success",
                "message": f"[MOCK] Typed '{text}'",
                "url": "https://example.com"
            }
        
        elif action == "scroll":
            direction = action_params.get("direction", "down")
            amount = action_params.get("amount", 500)
            return {
                "status": "success",
                "message": f"[MOCK] Scrolled {direction} {amount}px",
                "url": "https://example.com"
            }
        
        elif action == "extract_links":
            return {
                "status": "success",
                "message": "[MOCK] Extracted links",
                "links": [
                    {"text": "More information...", "url": "https://www.iana.org/domains/example"},
                    {"text": "Example link", "url": "https://example.com/page"}
                ],
                "url": "https://example.com"
            }
        
        else:
            return {
                "status": "success",
                "message": f"[MOCK] Executed action: {action}",
                "url": "https://example.com"
            }


# Usage instructions for the model
BROWSER_INSTRUCTIONS = """
The browser tool allows you to control a web browser with these actions:

1. **navigate**: Go to a URL
   Example: {"action": "navigate", "parameters": {"url": "https://www.google.com"}}

2. **click**: Click on text or elements
   Example: {"action": "click", "parameters": {"text": "Sign in", "type": "link"}}

3. **type**: Type text into input fields
   Example: {"action": "type", "parameters": {"text": "hello world", "into": "Search"}}

4. **scroll**: Scroll the page
   Example: {"action": "scroll", "parameters": {"direction": "down", "amount": 500}}

5. **search**: Find text on the page (like Ctrl+F)
   Example: {"action": "search", "parameters": {"text": "Python", "nth": 2}}

6. **extract_text**: Get all visible text from the page
   Example: {"action": "extract_text", "parameters": {}}

7. **extract_links**: Get all links from the page
   Example: {"action": "extract_links", "parameters": {}}

8. **back**: Go back to previous page
   Example: {"action": "back", "parameters": {}}

9. **wait**: Wait for a few seconds
   Example: {"action": "wait", "parameters": {"seconds": 2}}

10. **screenshot**: Take a screenshot of current state
    Example: {"action": "screenshot", "parameters": {}}

Tips:
- Always navigate to a URL before trying other actions
- Use wait after navigation or clicks to let pages load
- Extract text or links to understand page content
- Use search to find specific content on the page
"""


# Test the wrapper
if __name__ == "__main__":
    wrapper = VisionBrowserWrapper()
    
    # Test navigation
    result = wrapper.execute({
        "action": "navigate",
        "parameters": {"url": "https://en.wikipedia.org/wiki/Python_(programming_language)"}
    })
    print(f"Navigation result: {json.dumps(result, indent=2)}")
    
    # Test text extraction
    result = wrapper.execute({
        "action": "extract_text",
        "parameters": {}
    })
    print(f"Extracted {len(result.get('extracted_text', ''))} characters")
    
    # Test search
    result = wrapper.execute({
        "action": "search",
        "parameters": {"text": "Guido van Rossum"}
    })
    print(f"Search result: {json.dumps(result, indent=2)}")
    
    # Close browser
    wrapper.close()