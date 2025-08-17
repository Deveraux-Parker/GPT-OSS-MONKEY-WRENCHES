#!/usr/bin/env python3
"""
Instructions for built-in tools that should be added directly to developer message
"""

def get_builtin_tools_instruction(include_python=False, include_browser=False):
    """Get instructions for enabled built-in tools"""
    if not include_python and not include_browser:
        return ""
    
    sections = ["# Built-in Tools"]
    
    if include_python:
        sections.append("""
## python

The `python` tool executes Python code for calculations, data processing, and internal reasoning. When asked to perform calculations, generate sequences, or process data, you should use this tool to ensure accuracy.

### Usage
To use the python tool, send a message in the analysis channel:
```
<|channel|>analysis to=python<|message|>
# Your Python code here
print(result)  # Use print to see output
<|end|>
```

### Important Notes
- The code runs in a stateless environment - variables don't persist between calls
- Always use `print()` to see results - return values alone won't be visible
- The code execution has a 30-second timeout
- Standard library modules are available (math, datetime, json, etc.)
- External packages like numpy, pandas are NOT available

### Examples

1. **Mathematical calculations:**
```
<|channel|>analysis to=python<|message|>
import math
x = 5
y = 12
hypotenuse = math.sqrt(x**2 + y**2)
print(f"The hypotenuse of a {x}-{y} right triangle is {hypotenuse}")
<|end|>
```

2. **Date/time operations:**
```
<|channel|>analysis to=python<|message|>
from datetime import datetime, timedelta
today = datetime.now()
future = today + timedelta(days=30)
print(f"30 days from now will be: {future.strftime('%Y-%m-%d')}")
<|end|>
```

3. **Data processing:**
```
<|channel|>analysis to=python<|message|>
data = [23, 45, 12, 67, 34, 89, 21]
average = sum(data) / len(data)
print(f"Average: {average:.2f}")
print(f"Max: {max(data)}, Min: {min(data)}")
<|end|>
```""")
    
    if include_browser:
        sections.append("""
## browser

The built-in browser tool allows me to help you find information on the web and browse specific web pages.

I can search the web, open pages, find specific content on pages, and navigate through search results. The browser runs in a stateless mode where each command starts fresh.

### Available Commands

1. **Search the web:**
```
<|channel|>analysis to=browser<|message|>
search [query] [optional: topn=5] [optional: source=web]
<|end|>
```

2. **Open a search result or URL:**
```
<|channel|>analysis to=browser<|message|>
open [id or url]
<|end|>
```

3. **Find text on the current page:**
```
<|channel|>analysis to=browser<|message|>
find [text]
<|end|>
```

### Example Usage

**Searching for information:**
```
<|channel|>analysis to=browser<|message|>
search "latest AI developments" topn=5
<|end|>
```

**Opening a specific result:**
```
<|channel|>analysis to=browser<|message|>
open 1
<|end|>
```

**Finding specific content:**
```
<|channel|>analysis to=browser<|message|>
find "machine learning"
<|end|>
```""")
    
    return "\n".join(sections)