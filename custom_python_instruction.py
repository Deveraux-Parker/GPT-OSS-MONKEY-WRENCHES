#!/usr/bin/env python3
"""
Custom Python tool instruction for HARMONY
"""

PYTHON_INSTRUCTION = """
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
```
""".strip()