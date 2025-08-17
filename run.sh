#!/bin/bash
# Run script for Harmony VLLM App

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Check if port 5002 is already in use
if lsof -Pi :5002 -sTCP:LISTEN -t >/dev/null ; then
    echo "Port 5002 is already in use. Please stop the existing process."
    exit 1
fi

# Set default environment variables
export FLASK_APP=harmony_vllm_app.py
export FLASK_ENV=development

# Start the application
echo "Starting Harmony VLLM App on http://localhost:5002"
python harmony_vllm_app.py