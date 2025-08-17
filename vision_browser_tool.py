"""
Vision-based browser tool for Harmony
Adapted from smolagents vision_web_browser.py
"""

import os
import base64
import json
import logging
from io import BytesIO
from typing import Dict, Any, Optional, List
from time import sleep
import re

try:
    import PIL.Image
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    import helium
    HAS_SELENIUM = True
except ImportError:
    HAS_SELENIUM = False
    logging.warning("Selenium/Helium not available. Install with: pip install selenium helium pillow")

class VisionBrowserTool:
    """Browser tool that provides visual feedback through screenshots"""
    
    def __init__(self, headless: bool = False, use_personal_profile: bool = True):
        self.headless = headless
        self.use_personal_profile = use_personal_profile
        self.driver = None
        self.last_screenshot = None
        
    def initialize_driver(self):
        """Initialize the Selenium WebDriver"""
        if not HAS_SELENIUM:
            raise ImportError("Selenium is required for browser tool")
            
        chrome_options = webdriver.ChromeOptions()
        
        # Use a dedicated AI assistant browser profile (separate from personal)
        if self.use_personal_profile:
            profile_dir = os.path.expanduser("~/.harmony_ai_browser_profile")
            if not os.path.exists(profile_dir):
                os.makedirs(profile_dir)
            chrome_options.add_argument(f"--user-data-dir={profile_dir}")
            chrome_options.add_argument("--profile-directory=AIAssistant")
            logging.info(f"Using AI assistant browser profile: {profile_dir}")
        
        # Set window size
        chrome_options.add_argument("--window-size=1200,800")
        chrome_options.add_argument("--force-device-scale-factor=1")
        
        # Make it behave like a real browser
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # Use an honest user agent that identifies as an AI assistant
        chrome_options.add_argument("user-agent=Mozilla/5.0 (compatible; HarmonyAI/1.0; +https://github.com/harmony-ai) Chrome/136.0.0.0")
        
        # Enable features a real user would have
        chrome_options.add_argument("--enable-features=NetworkService,NetworkServiceInProcess")
        chrome_options.add_argument("--disable-features=VizDisplayCompositor")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--no-sandbox")  # Required for some Linux environments
        
        # Set preferences to act more human
        prefs = {
            "credentials_enable_service": True,
            "profile.password_manager_enabled": True,
            "profile.default_content_setting_values.notifications": 1,
            "profile.default_content_setting_values.geolocation": 1,
        }
        chrome_options.add_experimental_option("prefs", prefs)
        
        if self.headless:
            chrome_options.add_argument("--headless=new")  # Use new headless mode
            
        self.driver = helium.start_chrome(headless=self.headless, options=chrome_options)
        return self.driver
    
    def take_screenshot(self) -> Dict[str, Any]:
        """Take a screenshot and return it as base64"""
        if not self.driver:
            return {"error": "Browser not initialized"}
            
        try:
            sleep(0.5)  # Let animations complete
            png_bytes = self.driver.get_screenshot_as_png()
            image = PIL.Image.open(BytesIO(png_bytes))
            
            # Convert to base64 for easy transmission
            buffered = BytesIO()
            image.save(buffered, format="PNG")
            img_base64 = base64.b64encode(buffered.getvalue()).decode()
            
            self.last_screenshot = image
            
            return {
                "screenshot": f"data:image/png;base64,{img_base64}",
                "size": image.size,
                "url": self.driver.current_url
            }
        except Exception as e:
            return {"error": f"Screenshot failed: {str(e)}"}
    
    def execute_browser_command(self, command: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Execute a browser command and return result with screenshot"""
        if not self.driver:
            self.initialize_driver()
            
        result = {"command": command, "params": params}
        
        try:
            if command == "navigate":
                url = params.get("url", "")
                if not url.startswith(("http://", "https://")):
                    url = "https://" + url
                helium.go_to(url)
                result["status"] = "success"
                result["message"] = f"Navigated to {url}"
                
                # Wait a bit for the page to fully load
                sleep(2)
                
                # Automatically extract text after navigation
                try:
                    page_text = self.driver.find_element(By.TAG_NAME, "body").text
                    result["text"] = page_text
                except Exception as e:
                    logging.warning(f"Could not extract text after navigation: {e}")
                
            elif command == "click":
                text = params.get("text", "")
                element_type = params.get("type", "any")  # any, link, button
                
                if element_type == "link":
                    helium.click(helium.Link(text))
                else:
                    helium.click(text)
                result["status"] = "success"
                result["message"] = f"Clicked on '{text}'"
                
            elif command == "type":
                text = params.get("text", "")
                into = params.get("into", None)
                
                if into:
                    helium.write(text, into=into)
                else:
                    helium.write(text)
                result["status"] = "success"
                result["message"] = f"Typed '{text}'"
                
            elif command == "press":
                key = params.get("key", "ENTER")
                key_map = {
                    "ENTER": Keys.ENTER,
                    "TAB": Keys.TAB,
                    "ESCAPE": Keys.ESCAPE,
                    "BACKSPACE": Keys.BACKSPACE,
                    "DELETE": Keys.DELETE,
                    "UP": Keys.UP,
                    "DOWN": Keys.DOWN,
                    "LEFT": Keys.LEFT,
                    "RIGHT": Keys.RIGHT,
                }
                helium.press(key_map.get(key, Keys.ENTER))
                result["status"] = "success"
                result["message"] = f"Pressed {key}"
                
            elif command == "scroll":
                direction = params.get("direction", "down")
                amount = params.get("amount", 500)
                
                if direction == "down":
                    helium.scroll_down(num_pixels=amount)
                else:
                    helium.scroll_up(num_pixels=amount)
                result["status"] = "success"
                result["message"] = f"Scrolled {direction} {amount}px"
                
            elif command == "search":
                text = params.get("text", "")
                nth = params.get("nth", 1)
                
                elements = self.driver.find_elements(By.XPATH, f"//*[contains(text(), '{text}')]")
                if nth > len(elements):
                    result["status"] = "error"
                    result["message"] = f"Only {len(elements)} matches found for '{text}'"
                else:
                    elem = elements[nth - 1]
                    self.driver.execute_script("arguments[0].scrollIntoView(true);", elem)
                    result["status"] = "success"
                    result["message"] = f"Found {len(elements)} matches, focused on #{nth}"
                    
            elif command == "back":
                self.driver.back()
                result["status"] = "success"
                result["message"] = "Went back to previous page"
                
            elif command == "refresh":
                self.driver.refresh()
                result["status"] = "success"
                result["message"] = "Refreshed the page"
                
            elif command == "close_popups":
                webdriver.ActionChains(self.driver).send_keys(Keys.ESCAPE).perform()
                result["status"] = "success"
                result["message"] = "Pressed ESC to close popups"
                
            elif command == "wait":
                seconds = params.get("seconds", 2)
                sleep(seconds)
                result["status"] = "success"
                result["message"] = f"Waited {seconds} seconds"
                
            elif command == "extract_text":
                # Extract all visible text from the page
                text = self.driver.find_element(By.TAG_NAME, "body").text
                result["status"] = "success"
                result["text"] = text
                result["message"] = f"Extracted {len(text)} characters of text"
                
            elif command == "extract_links":
                # Extract all links from the page
                links = []
                elements = self.driver.find_elements(By.TAG_NAME, "a")
                for elem in elements:
                    href = elem.get_attribute("href")
                    text = elem.text.strip()
                    if href and text:
                        links.append({"text": text, "url": href})
                result["status"] = "success"
                result["links"] = links
                result["message"] = f"Found {len(links)} links"
                
            elif command == "screenshot":
                # Just take a screenshot without any action
                result["status"] = "success"
                result["message"] = "Screenshot taken"
                
            else:
                result["status"] = "error"
                result["message"] = f"Unknown command: {command}"
                
        except Exception as e:
            result["status"] = "error"
            result["message"] = str(e)
            
        # Always include a screenshot with the result
        screenshot_data = self.take_screenshot()
        result.update(screenshot_data)
        
        return result
    
    def close(self):
        """Close the browser"""
        if self.driver:
            self.driver.quit()
            self.driver = None
            

# Function to handle tool calls from the harmony app
def handle_browser_tool_call(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle browser tool calls in the harmony format
    
    Expected params format:
    {
        "action": "navigate|click|type|scroll|search|etc",
        "parameters": {
            // action-specific parameters
        }
    }
    """
    global _browser_instance
    
    # Initialize browser if needed
    if '_browser_instance' not in globals():
        _browser_instance = VisionBrowserTool(headless=False)
    
    action = params.get("action", "screenshot")
    parameters = params.get("parameters", {})
    
    # Map the action to browser command
    return _browser_instance.execute_browser_command(action, parameters)


# Example usage for testing
if __name__ == "__main__":
    browser = VisionBrowserTool(headless=False)
    
    # Navigate to a page
    result = browser.execute_browser_command("navigate", {"url": "https://www.google.com"})
    print(f"Navigate result: {result['message']}")
    
    # Type in search box
    result = browser.execute_browser_command("type", {"text": "OpenAI GPT", "into": "Search"})
    print(f"Type result: {result['message']}")
    
    # Press Enter
    result = browser.execute_browser_command("press", {"key": "ENTER"})
    print(f"Press result: {result['message']}")
    
    # Wait for results
    result = browser.execute_browser_command("wait", {"seconds": 2})
    
    # Extract links
    result = browser.execute_browser_command("extract_links", {})
    print(f"Found {len(result.get('links', []))} links")
    
    # Close browser
    browser.close()