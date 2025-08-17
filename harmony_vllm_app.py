#!/usr/bin/env python3
"""
HARMONY vLLM Demo Application
Uses OpenAI's official harmony renderer library to properly format prompts
"""

from flask import Flask, render_template, request, jsonify, Response, send_from_directory
import json
import requests
from typing import List, Dict, Any, Optional
import logging
from dataclasses import dataclass, asdict
from datetime import datetime
import random
import re
import asyncio
# from browser_tool_wrapper import browser_tool_wrapper  # Removed old browser
# from custom_browser_instruction import BROWSER_INSTRUCTION  # Removed old browser
from python_tool_wrapper import python_tool_wrapper
from python_function_wrapper import PythonFunctionTool
from custom_python_instruction import PYTHON_INSTRUCTION
from official_python_instruction import OFFICIAL_PYTHON_INSTRUCTION
# from official_browser_instruction import OFFICIAL_BROWSER_INSTRUCTION  # Removed old browser
from builtin_tool_instructions import get_builtin_tools_instruction

# Import harmony components
from openai_harmony import (
    Author,
    Conversation,
    DeveloperContent,
    HarmonyEncodingName,
    Message,
    Role,
    SystemContent,
    ToolDescription,
    load_harmony_encoding,
    ReasoningEffort,
    StreamableParser
)

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# vLLM server configuration
VLLM_BASE_URL = "http://localhost:8000"
MODEL_NAME = "openai/gpt-oss-20b"

# Load harmony encoding
try:
    encoding = load_harmony_encoding(HarmonyEncodingName.HARMONY_GPT_OSS)
    logging.info("Harmony encoding loaded successfully")
    
    # Debug: Check available attributes
    logging.info(f"Encoding attributes: {dir(encoding)}")
    
    # Try to get special tokens
    if hasattr(encoding, 'special_tokens'):
        logging.info(f"Has special_tokens method")
    elif hasattr(encoding, 'special_tokens_set'):
        logging.info(f"Has special_tokens_set attribute")
    else:
        logging.warning("No special tokens attribute found")
        
except Exception as e:
    logging.error(f"Failed to load harmony encoding: {e}")
    encoding = None

@dataclass
class ConversationState:
    """Maintains conversation state"""
    messages: List[Message]
    system_config: Dict[str, Any]
    developer_config: Dict[str, Any]
    
conversation_state = ConversationState(messages=[], system_config={}, developer_config={})

# Vision browser instance will be created on demand
_vision_browser_instance = None


# Removed old browser system message function


def create_system_message_with_builtin_tools(data: Dict[str, Any]) -> str:
    """Create system message with built-in tools in the correct format"""
    model_identity = data.get('model_identity', 'You are ChatGPT, a large language model trained by OpenAI.')
    knowledge_cutoff = data.get('knowledge_cutoff', '2024-06')
    current_date = data.get('current_date', datetime.now().strftime("%Y-%m-%d"))
    reasoning_level = data.get('reasoning_level', 'HIGH')
    
    # Build the system message parts
    system_parts = []
    system_parts.append(model_identity)
    system_parts.append(f"\nKnowledge cutoff: {knowledge_cutoff}")
    system_parts.append(f"\nCurrent date: {current_date}")
    
    # Add reasoning level only if not "o1" (default)
    if reasoning_level and reasoning_level.upper() != "O1":
        system_parts.append(f"\nReasoning: {reasoning_level.lower()}")
    
    # Add valid channels line
    system_parts.append("\n\n# Valid channels: analysis, commentary, final. Channel must be included for every message.")
    
    # Add the tools line if there are function tools
    tools = data.get('tools', [])
    if tools:
        system_parts.append("\nCalls to these tools must go to the commentary channel: 'functions'.")
    
    return "".join(system_parts)

# Update Python timeout constant
PYTHON_TIMEOUT = 120  # 120 seconds as per spec

# Fake weather database
WEATHER_DATA = {
    "San Francisco, CA": {"temp_c": 18, "temp_f": 64, "condition": "foggy", "humidity": 75, "wind_speed": 15},
    "New York, NY": {"temp_c": 22, "temp_f": 72, "condition": "partly cloudy", "humidity": 60, "wind_speed": 10},
    "Tokyo": {"temp_c": 26, "temp_f": 79, "condition": "sunny", "humidity": 55, "wind_speed": 8},
    "London": {"temp_c": 16, "temp_f": 61, "condition": "rainy", "humidity": 85, "wind_speed": 20},
    "Paris": {"temp_c": 20, "temp_f": 68, "condition": "cloudy", "humidity": 65, "wind_speed": 12},
    "Sydney": {"temp_c": 24, "temp_f": 75, "condition": "sunny", "humidity": 50, "wind_speed": 18},
}

def get_fake_weather(location: str, format: str = "celsius") -> Dict[str, Any]:
    """Get fake weather data for a location"""
    # Normalize location
    location = location.strip()
    
    # Check if we have data for this location
    if location in WEATHER_DATA:
        data = WEATHER_DATA[location]
    else:
        # Generate random weather for unknown locations
        data = {
            "temp_c": random.randint(10, 35),
            "temp_f": random.randint(50, 95),
            "condition": random.choice(["sunny", "cloudy", "rainy", "foggy", "partly cloudy"]),
            "humidity": random.randint(30, 90),
            "wind_speed": random.randint(5, 25),
        }
    
    # Format response based on requested format
    if format == "fahrenheit":
        return {
            "temperature": data["temp_f"],
            "unit": "fahrenheit",
            "condition": data["condition"],
            "humidity": data["humidity"],
            "wind_speed": data["wind_speed"],
            "location": location
        }
    else:
        return {
            "temperature": data["temp_c"],
            "unit": "celsius",
            "condition": data["condition"],
            "humidity": data["humidity"],
            "wind_speed": data["wind_speed"],
            "location": location
        }

def validate_weather_params(params: Dict[str, Any]) -> tuple[bool, Optional[str]]:
    """Validate weather API parameters"""
    if not isinstance(params, dict):
        return False, "Parameters must be a JSON object"
    
    if "location" not in params:
        return False, "Missing required parameter: location"
    
    if not isinstance(params["location"], str):
        return False, "Location must be a string"
    
    if "format" in params and params["format"] not in ["celsius", "fahrenheit"]:
        return False, f"Invalid format: {params['format']}. Must be 'celsius' or 'fahrenheit'"
    
    return True, None

# Removed old browser tool execution function

def execute_tool_call(tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a tool call and return the result"""
    
    # Handle Python tool (built-in)
    if tool_name == "python":
        script = params.get("script", params.get("code", ""))
        if not script:
            return {"error": "Python tool requires 'script' parameter"}
        
        # Run async function in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                python_tool_wrapper.execute(script)
            )
            return {"output": result}
        finally:
            loop.close()
    
    # Handle Python as a function tool
    elif tool_name == "functions.python":
        python_func_tool = PythonFunctionTool()
        return python_func_tool.handle_tool_call(params)
    
    # Handle vision browser tool
    elif tool_name == "functions.browser":
        try:
            from vision_browser_wrapper import VisionBrowserWrapper
            # Use a global instance to maintain browser state
            global _vision_browser_instance
            if _vision_browser_instance is None:
                _vision_browser_instance = VisionBrowserWrapper(mock_mode=False)  # Use real browser
            return _vision_browser_instance.execute(params)
        except ImportError:
            return {"error": "Vision browser tool not available. Install with: pip install selenium helium pillow"}
    
    # Handle weather functions
    elif tool_name == "functions.get_current_weather":
        valid, error = validate_weather_params(params)
        if not valid:
            return {"error": error}
        
        location = params["location"]
        format = params.get("format", "celsius")
        return get_fake_weather(location, format)
    
    elif tool_name == "functions.get_location":
        # Fake user location
        return {"location": "San Francisco, CA", "country": "United States"}
    
    elif tool_name == "functions.get_multiple_weathers":
        if "locations" not in params:
            return {"error": "Missing required parameter: locations"}
        
        if not isinstance(params["locations"], list):
            return {"error": "Locations must be an array"}
        
        format = params.get("format", "celsius")
        results = []
        for location in params["locations"]:
            if isinstance(location, str):
                results.append(get_fake_weather(location, format))
            else:
                results.append({"error": f"Invalid location: {location}"})
        
        return {"locations": results}
    
    # Removed old browser tool calls
    
    else:
        return {"error": f"Unknown tool: {tool_name}"}

def extract_tool_calls(text: str) -> List[Dict[str, Any]]:
    """Extract tool calls from model output"""
    tool_calls = []
    
    # Pattern for commentary channel (functions.*)
    # More lenient - capture everything after <|message|> until we hit another <|start|> or end
    commentary_pattern = r'<\|channel\|>commentary\s+to=([\w\.]+).*?<\|message\|>(.*?)(?:<\|call\|>|<\|end\|>|<\|start\|>|$)'
    
    # Pattern for analysis channel (browser.*)
    analysis_pattern = r'<\|channel\|>analysis\s+to=([\w\.]+).*?<\|message\|>(.*?)(?:<\|call\|>|<\|end\|>|<\|start\|>|$)'
    
    # Find all matches for both patterns
    all_matches = []
    
    # Commentary channel matches
    matches = re.findall(commentary_pattern, text, re.DOTALL)
    for recipient, content in matches:
        all_matches.append((recipient, content, "commentary"))
    
    # Analysis channel matches
    matches = re.findall(analysis_pattern, text, re.DOTALL)
    for recipient, content in matches:
        all_matches.append((recipient, content, "analysis"))
    
    for recipient, content, channel in all_matches:
        content = content.strip()
        
        # Special handling for Python tool - it takes raw code, not JSON
        if recipient == "python":
            tool_calls.append({
                "tool": recipient,
                "params": {"script": content},
                "raw_content": content,
                "channel": channel
            })
            continue
        
        # Clean up content - sometimes it includes extra protocol text
        # Try to extract JSON - look for balanced braces
        brace_count = 0
        json_start = -1
        json_end = -1
        
        for i, char in enumerate(content):
            if char == '{':
                if json_start == -1:
                    json_start = i
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0 and json_start != -1:
                    json_end = i + 1
                    break
        
        if json_start != -1 and json_end != -1:
            json_content = content[json_start:json_end]
            try:
                params = json.loads(json_content)
                tool_calls.append({
                    "tool": recipient,
                    "params": params,
                    "raw_content": content,
                    "channel": channel
                })
                continue
            except json.JSONDecodeError:
                pass
        
        # If not valid JSON, skip this tool call
        logging.warning(f"Skipping invalid tool call for {recipient}: {content[:100]}...")
    
    logging.info(f"Extracted {len(tool_calls)} tool calls from text")
    if tool_calls:
        logging.info(f"Tool calls: {tool_calls}")
    return tool_calls

def extract_final_content(raw_response: str) -> str:
    """Extract only the final channel content from raw HARMONY response"""
    # First try to find content in final channel
    pattern = r'<\|channel\|>final<\|message\|>(.*?)(?:<\|return\|>|<\|end\|>|$)'
    matches = re.findall(pattern, raw_response, re.DOTALL)
    if matches:
        return matches[-1].strip()
    
    # If no final channel, check if this is a continuation response
    # Look for content after the last <|end|>
    if '<|end|>' in raw_response:
        parts = raw_response.split('<|end|>')
        # Get the last non-empty part
        for part in reversed(parts):
            clean_part = part.strip()
            # Skip if it's empty or starts with special tokens
            if clean_part and not clean_part.startswith('<|') and not clean_part.startswith('{'):
                # This is likely the final user-facing message
                return clean_part
    
    return ""

def filter_cot_from_content(content: str) -> str:
    """Remove analysis channel content from assistant messages for conversation history"""
    # Remove everything between <|channel|>analysis and <|channel|>final
    pattern = r'<\|channel\|>analysis.*?(?=<\|channel\|>final)'
    filtered = re.sub(pattern, '', content, flags=re.DOTALL)
    
    # Also remove standalone analysis blocks
    pattern2 = r'<\|channel\|>analysis.*?<\|end\|>'
    filtered = re.sub(pattern2, '', filtered, flags=re.DOTALL)
    
    return filtered.strip()

def normalize_stop_token(response: str) -> str:
    """Normalize stop tokens - convert <|return|> to <|end|>"""
    return response.replace('<|return|>', '<|end|>')

@app.route('/')
def index():
    """Serve the main HTML interface"""
    return render_template('harmony_demo.html')

@app.route('/test')
def test():
    """Serve the test page"""
    return send_from_directory('.', 'test_tools.html')

@app.route('/test2')
def test2():
    """Serve the frontend test page"""
    return send_from_directory('.', 'test_frontend.html')

@app.route('/demos/d20')
def d20_demo():
    """Serve the D20 demo"""
    return send_from_directory('.', 'd20_demo.html')

@app.route('/demos/d20-detailed')
def d20_demo_detailed():
    """Serve the detailed D20 demo"""
    return send_from_directory('.', 'd20_demo_detailed.html')

@app.route('/demos/compare')
def serve_compare():
    """Serve the comparison HTML"""
    return send_from_directory('.', 'compare_approaches.html')

@app.route('/demos/d20-cycling')
def serve_d20_cycling():
    """Serve the D20 demo with cycling examples"""
    return send_from_directory('.', 'd20_demo_cycling.html')

@app.route('/api/check_server', methods=['GET'])
def check_server():
    """Check if vLLM server is accessible"""
    try:
        response = requests.get(f"{VLLM_BASE_URL}/v1/models")
        return jsonify({
            "status": "connected",
            "models": response.json()
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500

@app.route('/api/tokenize', methods=['POST'])
def tokenize():
    """Tokenize text using harmony encoding"""
    if not encoding:
        return jsonify({"error": "Harmony encoding not loaded"}), 500
    
    try:
        text = request.json.get('text', '')
        # Try different methods to encode with special tokens
        try:
            # Try the encode method with allowed_special parameter
            tokens = list(encoding.encode(text, allowed_special="all"))
        except:
            try:
                # Try just encode without parameters
                tokens = list(encoding.encode(text))
            except Exception as e:
                return jsonify({"error": f"Failed to encode text: {str(e)}"}), 500
        
        token_texts = [encoding.decode([t]) for t in tokens]
        
        # Get special tokens if available
        special_tokens = {}
        if hasattr(encoding, 'special_tokens'):
            try:
                special_tokens = {k: v for k, v in encoding.special_tokens().items()}
            except:
                special_tokens = list(encoding.special_tokens) if hasattr(encoding.special_tokens, '__iter__') else {}
        elif hasattr(encoding, 'special_tokens_set'):
            # It's a set, not a dict
            special_tokens = list(encoding.special_tokens_set)
        
        return jsonify({
            "tokens": tokens,
            "token_texts": token_texts,
            "special_tokens": special_tokens
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def safe_json_serialize(obj):
    """Convert objects to JSON-serializable format"""
    if hasattr(obj, '__dict__'):
        return obj.__dict__
    elif hasattr(obj, '_asdict'):
        return obj._asdict()
    else:
        return str(obj)

@app.route('/api/render_prompt', methods=['POST'])
def render_prompt():
    """Render the full prompt using harmony"""
    if not encoding:
        return jsonify({"error": "Harmony encoding not loaded"}), 500
    
    try:
        data = request.json
        
        # Check if built-in tools are enabled
        include_python = data.get('include_python', False)
        include_browser = data.get('include_browser', False)
        
        if include_python or include_browser:
            # Use custom system message with built-in tools
            system_text = create_system_message_with_builtin_tools(data)
            system_message = Message.from_role_and_content(Role.SYSTEM, system_text)
        else:
            # Use standard system message
            system_message = (
                SystemContent.new()
                .with_model_identity(data.get('model_identity', 'You are ChatGPT, a large language model trained by OpenAI.'))
                .with_reasoning_effort(ReasoningEffort[data.get('reasoning_level', 'HIGH').upper()])
                .with_conversation_start_date(data.get('current_date', datetime.now().strftime("%Y-%m-%d")))
                .with_knowledge_cutoff(data.get('knowledge_cutoff', '2024-06'))
                .with_required_channels(["analysis", "commentary", "final"])
            )
        
        # Create developer message
        developer_message = DeveloperContent.new()
        
        # Add regular instructions
        instructions_parts = []
        if data.get('instructions'):
            instructions_parts.append(data['instructions'])
        
        # Add built-in tool instructions if enabled
        if include_python or include_browser:
            from builtin_tool_instructions import get_builtin_tools_instruction
            builtin_instructions = get_builtin_tools_instruction(
                include_python=include_python,
                include_browser=include_browser
            )
            if builtin_instructions:
                instructions_parts.append(builtin_instructions)
        
        # Combine all instructions
        if instructions_parts:
            combined_instructions = '\n\n'.join(instructions_parts)
            developer_message = developer_message.with_instructions(combined_instructions)
        
        # Get function tool descriptions for developer message
        tools = data.get('tools', [])
        
        tool_descriptions = []
        for tool in tools:
            td = ToolDescription.new(
                tool['name'],
                tool['description'],
                parameters=tool.get('parameters', {})
            )
            tool_descriptions.append(td)
        
        # Add function tools to developer message if any are available
        if tool_descriptions:
            # Try different method names
            try:
                developer_message = developer_message.with_function_tools(tool_descriptions)
            except AttributeError:
                try:
                    developer_message = developer_message.with_tools(tool_descriptions)
                except AttributeError:
                    logging.warning("Could not add tools to developer message")
        
        # Build conversation
        if include_python or include_browser:
            # system_message is already a Message object
            messages = [
                system_message,
                Message.from_role_and_content(Role.DEVELOPER, developer_message)
            ]
        else:
            messages = [
                Message.from_role_and_content(Role.SYSTEM, system_message),
                Message.from_role_and_content(Role.DEVELOPER, developer_message)
            ]
        
        # Add conversation history with CoT filtering
        for msg in data.get('conversation_history', []):
            if msg['role'] == 'user':
                messages.append(Message.from_role_and_content(Role.USER, msg['content']))
            elif msg['role'] == 'assistant':
                # Filter out CoT from assistant messages
                filtered_content = filter_cot_from_content(msg['content'])
                if filtered_content:  # Only add if there's content after filtering
                    assistant_msg = Message.from_role_and_content(Role.ASSISTANT, filtered_content)
                    if 'channel' in msg:
                        assistant_msg = assistant_msg.with_channel(msg['channel'])
                    if 'recipient' in msg:
                        assistant_msg = assistant_msg.with_recipient(msg['recipient'])
                    if 'content_type' in msg:
                        assistant_msg = assistant_msg.with_content_type(msg['content_type'])
                    messages.append(assistant_msg)
            elif msg['role'] == 'tool':
                # Handle tool messages
                tool_msg = Message.from_author_and_content(
                    Author.new(Role.TOOL, msg.get('name', 'tool')),
                    msg['content']
                )
                if 'recipient' in msg:
                    tool_msg = tool_msg.with_recipient(msg['recipient'])
                if 'channel' in msg:
                    tool_msg = tool_msg.with_channel(msg['channel'])
                messages.append(tool_msg)
        
        # Add current user message or messages array
        if data.get('current_message'):
            messages.append(Message.from_role_and_content(Role.USER, data['current_message']))
        elif data.get('messages'):
            # Handle messages array format
            for msg in data['messages']:
                if msg['role'] == 'user':
                    messages.append(Message.from_role_and_content(Role.USER, msg['content']))
        
        # Create conversation
        conversation = Conversation.from_messages(messages)
        
        # Render to tokens
        tokens = encoding.render_conversation_for_completion(conversation, Role.ASSISTANT)
        
        # Convert tokens to text for display
        prompt_text = encoding.decode(tokens)
        
        # Don't add constrain token - we want the model to use channel format, not JSON
        
        # Also get token details
        token_texts = [encoding.decode([t]) for t in tokens]
        
        # Ensure everything is JSON serializable
        response_data = {
            "prompt": prompt_text,
            "tokens": [int(t) for t in tokens],  # Ensure tokens are ints
            "token_texts": token_texts,
            "token_count": len(tokens)
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        logging.error(f"Error rendering prompt: {e}")
        logging.error(f"Error type: {type(e)}")
        import traceback
        logging.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/execute_tool', methods=['POST'])
def execute_tool():
    """Execute a tool call"""
    try:
        data = request.json
        tool_name = data.get('tool')
        params = data.get('params', {})
        
        if not tool_name:
            return jsonify({"error": "Missing tool name"}), 400
        
        result = execute_tool_call(tool_name, params)
        
        return jsonify({
            "tool": tool_name,
            "params": params,
            "result": result
        })
    except Exception as e:
        logging.error(f"Error executing tool: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/chat', methods=['POST'])
def chat():
    """Send chat request to vLLM server with harmony formatting"""
    if not encoding:
        return jsonify({"error": "Harmony encoding not loaded"}), 500
    
    # Track all prompts sent during this request
    prompts_sent = []
    
    try:
        data = request.json
        
        # Don't call render_prompt() directly as it creates a Flask response
        # Instead, inline the rendering logic here
        try:
            # Check if built-in tools are enabled
            include_python = data.get('include_python', False)
            include_browser = data.get('include_browser', False)
            
            if include_python or include_browser:
                # Use custom system message with built-in tools
                system_text = create_system_message_with_builtin_tools(data)
                system_message = Message.from_role_and_content(Role.SYSTEM, system_text)
            else:
                # Use standard system message
                system_message = (
                    SystemContent.new()
                    .with_model_identity(data.get('model_identity', 'You are ChatGPT, a large language model trained by OpenAI.'))
                    .with_reasoning_effort(ReasoningEffort[data.get('reasoning_level', 'HIGH').upper()])
                    .with_conversation_start_date(data.get('current_date', datetime.now().strftime("%Y-%m-%d")))
                    .with_knowledge_cutoff(data.get('knowledge_cutoff', '2024-06'))
                    .with_required_channels(["analysis", "commentary", "final"])
                )
            
            # Create developer message
            developer_message = DeveloperContent.new()
            if data.get('instructions'):
                developer_message = developer_message.with_instructions(data['instructions'])
            
            # Get function tool descriptions
            tools = data.get('tools', [])
            
            # Add vision browser to tools if include_browser is True
            if include_browser:
                # Add vision browser to tools list if not already present
                if not any(t.get('name') == 'browser' for t in tools):
                    from vision_browser_wrapper import VisionBrowserWrapper
                    wrapper = VisionBrowserWrapper(mock_mode=False)  # Use real browser
                    browser_def = wrapper.get_tool_definition()
                    tools.append(browser_def)
            
            tool_descriptions = []
            for tool in tools:
                td = ToolDescription.new(
                    tool['name'],
                    tool['description'],
                    parameters=tool.get('parameters', {})
                )
                tool_descriptions.append(td)
            
            # Add function tools to developer message if any are available
            if tool_descriptions:
                try:
                    developer_message = developer_message.with_function_tools(tool_descriptions)
                except AttributeError:
                    try:
                        developer_message = developer_message.with_tools(tool_descriptions)
                    except AttributeError:
                        logging.warning("Could not add tools to developer message")
            
            # Build conversation
            if include_python or include_browser:
                # system_message is already a Message object
                messages = [
                    system_message,
                    Message.from_role_and_content(Role.DEVELOPER, developer_message)
                ]
            else:
                messages = [
                    Message.from_role_and_content(Role.SYSTEM, system_message),
                    Message.from_role_and_content(Role.DEVELOPER, developer_message)
                ]
            
            # Add conversation history with CoT filtering
            for msg in data.get('conversation_history', []):
                if msg['role'] == 'user':
                    messages.append(Message.from_role_and_content(Role.USER, msg['content']))
                elif msg['role'] == 'assistant':
                    # Filter out CoT from assistant messages
                    filtered_content = filter_cot_from_content(msg['content'])
                    if filtered_content:  # Only add if there's content after filtering
                        assistant_msg = Message.from_role_and_content(Role.ASSISTANT, filtered_content)
                        if 'channel' in msg:
                            assistant_msg = assistant_msg.with_channel(msg['channel'])
                        if 'recipient' in msg:
                            assistant_msg = assistant_msg.with_recipient(msg['recipient'])
                        if 'content_type' in msg:
                            assistant_msg = assistant_msg.with_content_type(msg['content_type'])
                        messages.append(assistant_msg)
                elif msg['role'] == 'tool':
                    tool_msg = Message.from_author_and_content(
                        Author.new(Role.TOOL, msg.get('name', 'tool')),
                        msg['content']
                    )
                    if 'recipient' in msg:
                        tool_msg = tool_msg.with_recipient(msg['recipient'])
                    if 'channel' in msg:
                        tool_msg = tool_msg.with_channel(msg['channel'])
                    messages.append(tool_msg)
            
            # Add current user message or messages array
            if data.get('current_message'):
                messages.append(Message.from_role_and_content(Role.USER, data['current_message']))
            elif data.get('messages'):
                # Handle messages array format
                for msg in data['messages']:
                    if msg['role'] == 'user':
                        messages.append(Message.from_role_and_content(Role.USER, msg['content']))
            
            # Create conversation and render
            conversation = Conversation.from_messages(messages)
            tokens = encoding.render_conversation_for_completion(conversation, Role.ASSISTANT)
            prompt = encoding.decode(tokens)
            
            # Don't add constrain token - we want the model to use channel format, not JSON
            
        except Exception as e:
            logging.error(f"Error rendering prompt in chat: {e}")
            return jsonify({"error": f"Failed to render prompt: {str(e)}"}), 500
        
        # Track this initial prompt (will add response later)
        initial_prompt_info = {
            "stage": "initial",
            "prompt": prompt,
            "token_count": len(tokens),
            "timestamp": datetime.now().isoformat()
        }
        
        # Send to vLLM
        vllm_response = requests.post(
            f"{VLLM_BASE_URL}/v1/completions",
            json={
                "model": MODEL_NAME,
                "prompt": prompt,
                "max_tokens": data.get('max_tokens', 2048),
                "temperature": data.get('temperature', 0.7),
                "stop": ["<|return|>", "<|call|>"],
                "stream": False,
                "skip_special_tokens": False,
                "logprobs": 1
            }
        )
        
        if vllm_response.status_code != 200:
            return jsonify({"error": f"vLLM error: {vllm_response.text}"}), 500
        
        vllm_data = vllm_response.json()
        response_text = vllm_data['choices'][0]['text']
        finish_reason = vllm_data['choices'][0].get('finish_reason', 'unknown')
        
        logging.info(f"vLLM finish_reason: {finish_reason}")
        logging.info(f"Response length: {len(response_text)}")
        logging.info(f"Response ends with: {response_text[-50:] if len(response_text) > 50 else response_text}")
        
        # Check if response contains tool calls
        tool_calls = extract_tool_calls(response_text)
        logging.info(f"Initial response extracted {len(tool_calls)} tool calls: {tool_calls}")
        logging.info(f"Initial response text ends with: ...{repr(response_text[-200:])}")
        
        # If stopped because of <|call|>, append it
        if finish_reason == 'stop' and not response_text.endswith('<|call|>'):
            response_text += '<|call|>'
            logging.info("Appended <|call|> because finish_reason was 'stop'")
        
        # Add response to initial prompt info and track it
        initial_prompt_info['response'] = response_text
        prompts_sent.append(initial_prompt_info)
        
        # Handle multiple rounds of tool calls
        all_tool_responses = []
        current_prompt = prompt
        current_response = response_text
        max_rounds = 3  # Prevent infinite loops - reduced from 10
        round_count = 0
        
        while tool_calls and round_count < max_rounds:
            round_count += 1
            logging.info(f"Processing tool calls round {round_count}: {len(tool_calls)} calls")
            
            # Execute tool calls for this round
            tool_responses = []
            
            for tool_call in tool_calls:
                tool_name = tool_call['tool']
                params = tool_call['params']
                channel = tool_call.get('channel', 'commentary')
                
                logging.info(f"Executing tool: {tool_name} with params: {params}")
                
                # Execute the tool
                result = execute_tool_call(tool_name, params)
                
                # Format tool response in HARMONY format
                # Use the same channel as the request (analysis for browser, commentary for others)
                # Built-in tools (python, browser) return raw output, functions return JSON
                if tool_name in ['python', 'browser']:
                    # Built-in tools return raw output
                    tool_response = f'<|return|>{result}<|end|>'
                else:
                    # Function tools return JSON
                    tool_response = f'<|return|>{json.dumps(result)}<|end|>'
                tool_responses.append({
                    'tool': tool_name,
                    'params': params,
                    'result': result,
                    'formatted_response': tool_response
                })
            
            all_tool_responses.extend(tool_responses)
            
            # Append tool responses to the conversation and continue
            continued_prompt = current_prompt + current_response
            for tr in tool_responses:
                continued_prompt += tr['formatted_response']
            continued_prompt += '<|start|>assistant<|message|>'
            
            # Prepare continuation prompt info (will add response later)
            continuation_prompt_info = {
                "stage": f"continuation_round_{round_count}",
                "prompt": continued_prompt,
                "token_count": len(list(encoding.encode(continued_prompt, allowed_special="all"))),
                "timestamp": datetime.now().isoformat(),
                "tool_calls": tool_calls
            }
            
            # Make another request to vLLM to continue after tool execution
            continue_response = requests.post(
                f"{VLLM_BASE_URL}/v1/completions",
                json={
                    "model": MODEL_NAME,
                    "prompt": continued_prompt,
                    "max_tokens": data.get('max_tokens', 2048),
                    "temperature": data.get('temperature', 0.7),
                    "stop": ["<|return|>", "<|call|>", "<|end|>"],  # Stop on return, call, or end
                    "stream": False,
                    "skip_special_tokens": False,
                    "logprobs": 1
                }
            )
            
            if continue_response.status_code == 200:
                continue_data = continue_response.json()
                continued_text = continue_data['choices'][0]['text']
                finish_reason = continue_data['choices'][0].get('finish_reason', 'unknown')
                
                logging.info(f"Round {round_count} finish_reason: {finish_reason}")
                logging.info(f"Round {round_count} response ends with: {continued_text[-50:] if len(continued_text) > 50 else continued_text}")
                
                # Check if we have an incomplete tool call at the end
                if finish_reason == 'stop' and not continued_text.endswith('<|call|>'):
                    # Check for tool call patterns
                    if any(pattern in continued_text[-150:] for pattern in ['to=browser.', 'to=functions.']):
                        continued_text += '<|call|>'
                        logging.info("Appended <|call|> to incomplete tool call")
                
                # Add response to continuation prompt info and track it
                continuation_prompt_info['response'] = continued_text
                prompts_sent.append(continuation_prompt_info)
                
                # Update for next iteration
                current_prompt = continued_prompt
                current_response = continued_text
                
                # Check for more tool calls in the continued response
                tool_calls = extract_tool_calls(continued_text)
                logging.info(f"Round {round_count} found {len(tool_calls)} new tool calls")
                logging.info(f"Round {round_count} continued text: {continued_text}")
                
                # If no more tool calls, we're done
                if not tool_calls:
                    break
            else:
                logging.error(f"Failed to continue after tool execution: {continue_response.text}")
                # Still track the failed continuation
                continuation_prompt_info['response'] = f"[Error: {continue_response.status_code}]"
                continuation_prompt_info['error'] = continue_response.text
                prompts_sent.append(continuation_prompt_info)
                break
        
        # Build the complete response from all rounds
        full_response = response_text
        for tr in all_tool_responses:
            full_response += tr['formatted_response']
        if round_count > 0:  # If we did any continuations
            full_response += current_response
        
        # Parse the complete response
        try:
            response_tokens = list(encoding.encode(full_response, allowed_special="all"))
        except:
            response_tokens = list(encoding.encode(full_response))
        
        try:
            parsed_messages = encoding.parse_messages_from_completion_tokens(response_tokens, Role.ASSISTANT)
        except Exception as e:
            logging.warning(f"Failed to parse messages: {e}")
            parsed_messages = []
        
        # Extract structured information
        channels = {}
        for msg in parsed_messages:
            channel = getattr(msg, 'channel', 'default')
            
            # Skip tool messages - we don't want to display these in the channels
            if hasattr(msg, 'author') and hasattr(msg.author, 'role') and msg.author.role == Role.TOOL:
                continue
                
            if channel not in channels:
                channels[channel] = []
            
            # Extract content as string
            content_str = ""
            if hasattr(msg, 'content'):
                if isinstance(msg.content, str):
                    content_str = msg.content
                elif isinstance(msg.content, list):
                    # Extract text from TextContent objects
                    for item in msg.content:
                        if hasattr(item, 'text'):
                            content_str += item.text
                        else:
                            content_str += str(item)
                else:
                    content_str = str(msg.content)
            else:
                content_str = str(msg)
            
            # Skip if this is a code/JSON message (tool call)
            recipient = getattr(msg, 'recipient', None)
            content_type = getattr(msg, 'content_type', None)
            
            # Filter out JSON tool calls from display
            if recipient and '.' in str(recipient) and content_type == 'code':
                # This is a tool call, skip it
                continue
                
            channels[channel].append({
                'content': content_str,
                'recipient': recipient,
                'content_type': content_type
            })
        
        # Extract final content for conversation history
        final_content = extract_final_content(full_response)
        
        logging.info(f"Sending response with {len(full_response)} chars, {round_count} rounds, {len(all_tool_responses)} tool calls")
        logging.info(f"Full response ends with: {repr(full_response[-100:])}")
        
        return jsonify({
            "raw_response": full_response,
            "final_content": final_content,
            "tokens": response_tokens,
            "parsed_messages": channels,
            "tool_calls": all_tool_responses,
            "prompts_sent": prompts_sent,
            "rounds": round_count,
            "logprobs": vllm_data['choices'][0].get('logprobs', {})
        })
        
    except Exception as e:
        logging.error(f"Error in chat: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/stream', methods=['POST'])
def stream():
    """Stream chat responses with live parsing"""
    if not encoding:
        return jsonify({"error": "Harmony encoding not loaded"}), 500
    
    # Get data before entering the generator
    data = request.get_json()
    
    # Track all prompts sent during this streaming request
    prompts_sent = []
    
    def generate(data):
        try:
            
            # Inline prompt rendering (same as in chat endpoint)
            try:
                # Check if built-in tools are enabled
                include_python = data.get('include_python', False)
                include_browser = data.get('include_browser', False)
                
                if include_python or include_browser:
                    # Use custom system message with built-in tools
                    system_text = create_system_message_with_builtin_tools(data)
                    system_message = Message.from_role_and_content(Role.SYSTEM, system_text)
                else:
                    # Use standard system message
                    system_message = (
                        SystemContent.new()
                        .with_model_identity(data.get('model_identity', 'You are ChatGPT, a large language model trained by OpenAI.'))
                        .with_reasoning_effort(ReasoningEffort[data.get('reasoning_level', 'HIGH').upper()])
                        .with_conversation_start_date(data.get('current_date', datetime.now().strftime("%Y-%m-%d")))
                        .with_knowledge_cutoff(data.get('knowledge_cutoff', '2024-06'))
                        .with_required_channels(["analysis", "commentary", "final"])
                    )
                
                # Create developer message
                developer_message = DeveloperContent.new()
                
                # Add regular instructions
                instructions_parts = []
                if data.get('instructions'):
                    instructions_parts.append(data['instructions'])
                
                # Add built-in tool instructions if enabled
                if include_python or include_browser:
                    from builtin_tool_instructions import get_builtin_tools_instruction
                    builtin_instructions = get_builtin_tools_instruction(
                        include_python=include_python,
                        include_browser=include_browser
                    )
                    if builtin_instructions:
                        instructions_parts.append(builtin_instructions)
                
                # Combine all instructions
                if instructions_parts:
                    combined_instructions = '\n\n'.join(instructions_parts)
                    developer_message = developer_message.with_instructions(combined_instructions)
                
                # Get function tool descriptions
                tools = data.get('tools', [])
                
                tool_descriptions = []
                for tool in tools:
                    td = ToolDescription.new(
                        tool['name'],
                        tool['description'],
                        parameters=tool.get('parameters', {})
                    )
                    tool_descriptions.append(td)
                
                # Add function tools to developer message if any are available
                if tool_descriptions:
                    try:
                        developer_message = developer_message.with_function_tools(tool_descriptions)
                    except AttributeError:
                        try:
                            developer_message = developer_message.with_tools(tool_descriptions)
                        except AttributeError:
                            logging.warning("Could not add tools to developer message")
                
                # Build conversation
                if include_python or include_browser:
                    # system_message is already a Message object
                    messages = [
                        system_message,
                        Message.from_role_and_content(Role.DEVELOPER, developer_message)
                    ]
                else:
                    messages = [
                        Message.from_role_and_content(Role.SYSTEM, system_message),
                        Message.from_role_and_content(Role.DEVELOPER, developer_message)
                    ]
                
                # Add conversation history - properly handle raw content
                for msg in data.get('conversation_history', []):
                    if msg['role'] == 'user':
                        messages.append(Message.from_role_and_content(Role.USER, msg['content']))
                    elif msg['role'] == 'assistant':
                        # If we have raw content, just append it directly to prompt
                        if 'rawContent' in msg:
                            # We'll handle this differently - store for later
                            pass
                        else:
                            # Old format compatibility
                            assistant_msg = Message.from_role_and_content(Role.ASSISTANT, msg.get('content', ''))
                            if 'channel' in msg:
                                assistant_msg = assistant_msg.with_channel(msg['channel'])
                            if 'recipient' in msg:
                                assistant_msg = assistant_msg.with_recipient(msg['recipient'])
                            if 'content_type' in msg:
                                assistant_msg = assistant_msg.with_content_type(msg['content_type'])
                            messages.append(assistant_msg)
                    elif msg['role'] == 'tool':
                        tool_msg = Message.from_author_and_content(
                            Author.new(Role.TOOL, msg.get('name', 'tool')),
                            msg['content']
                        )
                        if 'recipient' in msg:
                            tool_msg = tool_msg.with_recipient(msg['recipient'])
                        if 'channel' in msg:
                            tool_msg = tool_msg.with_channel(msg['channel'])
                        messages.append(tool_msg)
                
                # Add current user message
                messages.append(Message.from_role_and_content(Role.USER, data['current_message']))
                
                # Create conversation and render
                conversation = Conversation.from_messages(messages)
                tokens = encoding.render_conversation_for_completion(conversation, Role.ASSISTANT)
                prompt = encoding.decode(tokens)
                
            except Exception as e:
                yield f"data: {json.dumps({'error': f'Failed to render prompt: {str(e)}'})}\n\n"
                return
            
            # Track the initial prompt (will add response later)
            initial_prompt_info = {
                "stage": "initial",
                "prompt": prompt,
                "token_count": len(tokens),
                "timestamp": datetime.now().isoformat()
            }
            
            # Create streaming parser
            parser = StreamableParser(encoding, role=Role.ASSISTANT)
            accumulated_text = ""  # Accumulate text to handle partial special tokens
            
            # Send streaming request to vLLM
            with requests.post(
                f"{VLLM_BASE_URL}/v1/completions",
                json={
                    "model": MODEL_NAME,
                    "prompt": prompt,
                    "max_tokens": data.get('max_tokens', 2048),
                    "temperature": data.get('temperature', 0.7),
                    "stop": ["<|return|>"],
                    "stream": True,
                    "skip_special_tokens": False,
                    "logprobs": 1
                },
                stream=True
            ) as response:
                
                for line in response.iter_lines():
                    if line:
                        line = line.decode('utf-8')
                        if line.startswith('data: '):
                            chunk_data = line[6:]
                            if chunk_data == '[DONE]':
                                break
                            
                            try:
                                chunk = json.loads(chunk_data)
                                if 'choices' in chunk and chunk['choices']:
                                    text = chunk['choices'][0].get('text', '')
                                    
                                    if text:
                                        accumulated_text += text
                                        
                                        # Send update with accumulated text
                                        yield f"data: {json.dumps({
                                            'text': text,
                                            'accumulated': accumulated_text,
                                            'current_role': 'assistant',
                                            'current_channel': None,
                                            'last_content_delta': text,
                                            'current_content': accumulated_text,
                                            'current_recipient': None,
                                            'current_content_type': None
                                        })}\n\n"
                                        
                            except json.JSONDecodeError:
                                continue
                
                # Add initial response to prompt info
                initial_prompt_info['response'] = accumulated_text
                prompts_sent.append(initial_prompt_info)
                
                # Check if response contains tool calls
                tool_calls = extract_tool_calls(accumulated_text)
                
                # If the stream stopped but we have a tool call pattern, append <|call|>
                if tool_calls and not accumulated_text.endswith('<|call|>'):
                    for tc in tool_calls:
                        if tc['tool'] and tc['params']:
                            accumulated_text += '<|call|>'
                            logging.info("Appended <|call|> to streaming response")
                            break
                
                if tool_calls and '<|call|>' in accumulated_text:
                    # Execute tool calls and continue the conversation
                    tool_responses = []
                    
                    for tool_call in tool_calls:
                        tool_name = tool_call['tool']
                        params = tool_call['params']
                        channel = tool_call.get('channel', 'commentary')
                        
                        # Execute the tool
                        result = execute_tool_call(tool_name, params)
                        
                        # Format tool response
                        # Use the same channel as the request (analysis for browser, commentary for others)
                        tool_response = f'<|start|>{tool_name} to=assistant<|channel|>{channel}<|message|>{json.dumps(result)}<|end|>'
                        tool_responses.append({
                            'tool': tool_name,
                            'params': params,
                            'result': result,
                            'formatted_response': tool_response
                        })
                        
                        # Send tool execution info
                        yield f"data: {json.dumps({
                            'tool_executed': {
                                'tool': tool_name,
                                'params': params,
                                'result': result
                            }
                        })}\n\n"
                    
                    # Continue the conversation with tool responses
                    continued_prompt = prompt + accumulated_text
                    for tr in tool_responses:
                        continued_prompt += tr['formatted_response']
                    continued_prompt += '<|start|>assistant<|message|>'
                    
                    # Prepare continuation prompt info (will add response later)
                    continuation_prompt_info = {
                        "stage": "continuation_after_tools",
                        "prompt": continued_prompt,
                        "token_count": len(list(encoding.encode(continued_prompt, allowed_special="all"))),
                        "timestamp": datetime.now().isoformat(),
                        "tool_calls": tool_calls
                    }
                    
                    # Add tool responses to accumulated text for complete raw response
                    for tr in tool_responses:
                        accumulated_text += tr['formatted_response']
                    
                    # Stream the continuation
                    yield f"data: {json.dumps({'continuing_after_tools': True})}\n\n"
                    
                    with requests.post(
                        f"{VLLM_BASE_URL}/v1/completions",
                        json={
                            "model": MODEL_NAME,
                            "prompt": continued_prompt,
                            "max_tokens": data.get('max_tokens', 2048),
                            "temperature": data.get('temperature', 0.7),
                            "stop": ["<|return|>"],
                            "stream": True,
                            "skip_special_tokens": False,
                            "logprobs": 1
                        },
                        stream=True
                    ) as continue_response:
                        
                        for line in continue_response.iter_lines():
                            if line:
                                line = line.decode('utf-8')
                                if line.startswith('data: '):
                                    chunk_data = line[6:]
                                    if chunk_data == '[DONE]':
                                        break
                                    
                                    try:
                                        chunk = json.loads(chunk_data)
                                        if 'choices' in chunk and chunk['choices']:
                                            text = chunk['choices'][0].get('text', '')
                                            
                                            if text:
                                                accumulated_text += text
                                                
                                                yield f"data: {json.dumps({
                                                    'text': text,
                                                    'accumulated': accumulated_text,
                                                    'is_continuation': True
                                                })}\n\n"
                                                
                                    except json.JSONDecodeError:
                                        continue
                        
                        # Add continuation response to prompt info
                        if 'continuation_prompt_info' in locals():
                            # Get the continuation response text by finding what was added after the prompt
                            continuation_start = len(continuation_prompt_info['prompt'])
                            continuation_response = accumulated_text[continuation_start:] if len(accumulated_text) > continuation_start else accumulated_text
                            continuation_prompt_info['response'] = continuation_response
                            prompts_sent.append(continuation_prompt_info)
                
                # Parse the complete accumulated text
                if accumulated_text:
                    # Extract all content manually
                    parsed_messages = []
                    
                    # Extract channel content using regex
                    import re
                    
                    # Find all analysis messages
                    for match in re.finditer(r'<\|channel\|>analysis<\|message\|>(.*?)(?=<\|end\|>|<\|start\|>|$)', accumulated_text, re.DOTALL):
                        parsed_messages.append({
                            'role': 'assistant',
                            'channel': 'analysis',
                            'content': match.group(1).strip(),
                            'recipient': None,
                            'content_type': None
                        })
                    
                    # Find all commentary/tool calls
                    for match in re.finditer(r'<\|channel\|>commentary(?:\s+to=([\w\.]+))?.*?<\|message\|>(.*?)(?=<\|call\|>|<\|end\|>|<\|start\|>|$)', accumulated_text, re.DOTALL):
                        parsed_messages.append({
                            'role': 'assistant',
                            'channel': 'commentary',
                            'content': match.group(2).strip() if match.group(2) else '',
                            'recipient': match.group(1) if match.group(1) else None,
                            'content_type': None
                        })
                    
                    # Find all final messages
                    for match in re.finditer(r'<\|channel\|>final<\|message\|>(.*?)(?=<\|return\|>|<\|end\|>|<\|start\|>|$)', accumulated_text, re.DOTALL):
                        parsed_messages.append({
                            'role': 'assistant',
                            'channel': 'final',
                            'content': match.group(1).strip(),
                            'recipient': None,
                            'content_type': None
                        })
                else:
                    parsed_messages = []
                
                # Build the complete raw response including tool responses
                if 'tool_responses' in locals() and tool_responses:
                    # We had tool calls, so build the full response
                    full_raw_response = accumulated_text
                    # Note: accumulated_text already includes everything because we accumulated
                    # from both the initial response AND the continuation after tools
                else:
                    # No tool calls, just the direct response
                    full_raw_response = accumulated_text
                
                # Extract final content for conversation history
                final_content = extract_final_content(full_raw_response) if full_raw_response else ""
                
                # Send final parsed messages with tool info and all prompts
                yield f"data: {json.dumps({
                    'done': True,
                    'raw_response': full_raw_response,  # Include the complete raw response
                    'final_content': final_content,  # Add clean content for frontend
                    'parsed_messages': parsed_messages,
                    'tool_calls': tool_responses if 'tool_responses' in locals() else [],
                    'prompts_sent': prompts_sent  # All prompts sent during streaming
                })}\n\n"
                
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    
    return Response(generate(data), mimetype='text/event-stream')

if __name__ == '__main__':
    app.run(debug=False, port=5000)