# Harmony VLLM App

A Flask web application that demonstrates the OpenAI Harmony format with VLLM backend, featuring browser automation and sandboxed Python execution.

## Features

- **OpenAI Harmony Format**: Implements the Harmony prompt format for tool use
- **VLLM Integration**: Uses VLLM for fast local LLM inference
- **Vision Browser Tool**: Selenium-based browser automation with screenshot capabilities
- **Sandboxed Python Tool**: Docker-sandboxed Python execution for safety
- **Real-time Streaming**: Server-sent events for streaming responses
- **Dark Mode UI**: Modern interface with dark mode support

## Prerequisites

- Python 3.11+
- Docker (for sandboxed Python execution)
- Chrome/Chromium browser (for browser tool)
- VLLM-compatible GPU (for local inference)

## Installation

Clone the repository

Install dependencies:

Install ChromeDriver:
```bash
# On Ubuntu/Debian
sudo apt-get update
sudo apt-get install chromium-chromedriver

# On macOS with Homebrew
brew install chromedriver

# Or download manually from https://chromedriver.chromium.org/
```

Pull Docker Python image (for sandboxed execution):
```bash
docker pull python:3.11-slim
```

## Configuration

1. Set up your OpenAI API key (if using OpenAI backend):
```bash
export OPENAI_API_KEY="your-api-key-here"
```

2. For VLLM backend, ensure your model is loaded:
```bash
# Example for loading a model with VLLM
python -m vllm.entrypoints.openai.api_server \
  --model meta-llama/Llama-3.2-3B-Instruct \
  --port 5001
```

## Usage

1. Start the Flask application:
```bash
python harmony_vllm_app.py
```

2. Open your browser to `http://localhost:5002`

3. Select your desired tools:
   - **Vision Browser Tool**: For web browsing and screenshots
   - **Python Tool**: For calculations and data processing

4. Start chatting! The AI will use the enabled tools to help with your requests.

## Tool Details

### Vision Browser Tool
- Uses Selenium WebDriver for browser automation
- Captures screenshots for visual analysis
- Extracts text content from web pages
- **Note**: Many sites have anti-bot protection (Cloudflare, etc.)

### Python Tool
- Executes Python code in Docker containers
- Security restrictions:
  - No network access
  - 512MB memory limit
  - 50% CPU limit
  - Read-only filesystem (except /tmp)
- Falls back to subprocess if Docker unavailable

## Security Considerations

1. **Python Execution**: Always runs in sandboxed environment
2. **Browser Tool**: Uses separate browser profile, no access to personal data
3. **API Keys**: Never commit API keys to repository
4. **Docker**: Ensure Docker daemon is properly secured

## Architecture

- `harmony_vllm_app.py`: Main Flask application
- `vision_browser_wrapper.py`: Browser tool wrapper
- `python_tool_wrapper.py`: Python execution wrapper
- `templates/harmony_demo.html`: Frontend UI
- `python/openai_harmony/`: Harmony format types

## Development

Run tests:
```bash
pytest
```

Format code:
```bash
black .
```

Lint code:
```bash
flake8 .
```

## Troubleshooting

### Browser Tool Issues
- Ensure ChromeDriver is installed and in PATH
- Check Chrome/Chromium version compatibility
- Some sites block automated browsers

### Python Tool Issues
- Verify Docker is installed: `docker --version`
- Check Docker permissions: `docker ps`
- Ensure python:3.11-slim image is pulled

### VLLM Issues
- Check GPU availability: `nvidia-smi`
- Verify VLLM server is running on correct port
- Monitor memory usage for large models

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see LICENSE file for details.

## Acknowledgments

- OpenAI for the Harmony format specification
- VLLM team for the inference engine
- Selenium project for browser automation
