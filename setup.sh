#!/bin/bash
# Setup script for Harmony VLLM App

echo "Setting up Harmony VLLM App..."
echo "=============================="

# Check Python version
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "Python version: $python_version"

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt

# Check Docker
echo "Checking Docker..."
if command -v docker &> /dev/null; then
    echo "✓ Docker is installed"
    echo "Pulling Python Docker image..."
    docker pull python:3.11-slim
else
    echo "⚠ Docker is not installed. Python tool will use subprocess mode."
    echo "  To enable sandboxed execution, install Docker:"
    echo "  sudo apt-get install docker.io"
fi

# Check ChromeDriver
echo "Checking ChromeDriver..."
if command -v chromedriver &> /dev/null; then
    echo "✓ ChromeDriver is installed"
    chromedriver --version
else
    echo "⚠ ChromeDriver is not installed. Browser tool will not work."
    echo "  Install with: sudo apt-get install chromium-chromedriver"
fi

# Create necessary directories
echo "Creating directories..."
mkdir -p logs
mkdir -p screenshots

echo ""
echo "Setup complete!"
echo ""
echo "To start the app:"
echo "1. Activate virtual environment: source venv/bin/activate"
echo "2. Set OpenAI API key: export OPENAI_API_KEY='your-key'"
echo "3. Run the app: python harmony_vllm_app.py"
echo ""
echo "For VLLM backend, start VLLM server first:"
echo "python -m vllm.entrypoints.openai.api_server --model meta-llama/Llama-3.2-3B-Instruct --port 5001"