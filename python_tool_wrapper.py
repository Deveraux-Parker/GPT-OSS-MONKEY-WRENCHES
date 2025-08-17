#!/usr/bin/env python3
"""
Wrapper to make Python execution work with our string-based system
Can use either Docker-based execution or direct subprocess execution
"""

import asyncio
import subprocess
import tempfile
import os
import sys
from typing import Dict, Any, AsyncIterator
from openai_harmony import Message, TextContent


class PythonToolWrapper:
    """Wrapper around Python execution to provide string-based interface"""
    
    def __init__(self, use_docker=None):
        # Auto-detect Docker if not specified
        if use_docker is None:
            try:
                # Check if Docker is available
                result = subprocess.run(['docker', '--version'], capture_output=True, text=True)
                self.use_docker = result.returncode == 0
            except:
                self.use_docker = False
        else:
            self.use_docker = use_docker
        if use_docker:
            try:
                import docker
                self.docker_client = docker.from_env()
                # Try to pull python:3.11 image if not present
                try:
                    self.docker_client.images.get("python:3.11")
                except:
                    print("Pulling python:3.11 Docker image...")
                    self.docker_client.images.pull("python:3.11")
            except Exception as e:
                print(f"Docker not available: {e}. Falling back to subprocess.")
                self.use_docker = False
                self.docker_client = None
        else:
            self.docker_client = None
    
    def instruction(self) -> str:
        """Get the Python tool instruction"""
        sandbox_info = "Docker container" if self.use_docker else "subprocess"
        return f"""
Use this tool to execute Python code in your chain of thought. The code will not be shown to the user. This tool should be used for internal reasoning, calculations, and data processing.
When you send a message containing python code to python, it will be executed in a {"sandboxed Docker container with no network access and limited resources" if self.use_docker else "stateless subprocess environment"}, and the stdout of that process will be returned to you. You have to use print statements to access the output.
        """.strip()
    
    def _execute_subprocess(self, script: str) -> str:
        """Execute Python script using subprocess"""
        try:
            # Create a temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(script)
                temp_file = f.name
            
            # Execute the script
            result = subprocess.run(
                [sys.executable, temp_file],
                capture_output=True,
                text=True,
                timeout=120  # 120 second timeout as per spec
            )
            
            # Clean up
            os.unlink(temp_file)
            
            # Combine stdout and stderr
            output = result.stdout
            if result.stderr:
                output += f"\n[STDERR]\n{result.stderr}"
            
            return output if output else "[No output]"
            
        except subprocess.TimeoutExpired:
            return "[Error: Script execution timed out after 30 seconds]"
        except Exception as e:
            return f"[Error executing script: {str(e)}]"
    
    def _execute_docker(self, script: str) -> str:
        """Execute Python script using Docker"""
        if not self.docker_client:
            return self._execute_subprocess(script)
        
        try:
            import io
            import tarfile
            
            # Create a temporary tar archive containing the script
            script_name = "script.py"
            tarstream = io.BytesIO()
            with tarfile.open(fileobj=tarstream, mode="w") as tar:
                script_bytes = script.encode("utf-8")
                tarinfo = tarfile.TarInfo(name=script_name)
                tarinfo.size = len(script_bytes)
                tar.addfile(tarinfo, io.BytesIO(script_bytes))
            tarstream.seek(0)
            
            # Start the container with security restrictions
            container = self.docker_client.containers.create(
                "python:3.11-slim",  # Use slim image
                command="sleep infinity", 
                detach=True,
                mem_limit="512m",  # Limit memory to 512MB
                cpu_period=100000,
                cpu_quota=50000,  # Limit to 50% of one CPU
                network_mode="none",  # No network access
                # read_only=True,  # Can't use this - prevents copying script
                tmpfs={'/tmp': 'size=100M,mode=1777'},  # /tmp is writable (100MB limit)
                security_opt=["no-new-privileges"]  # Security hardening
            )
            
            try:
                container.start()
                # Put the script into the container
                container.put_archive(path="/tmp", data=tarstream.read())
                # Execute the script with timeout
                exec_result = container.exec_run(
                    f"python /tmp/{script_name}",
                    demux=True
                )
                
                # Get stdout and stderr
                stdout, stderr = exec_result.output
                output = ""
                
                if stdout:
                    output = stdout.decode("utf-8")
                if stderr:
                    output += f"\n[STDERR]\n{stderr.decode('utf-8')}"
                
                return output if output else "[No output]"
                
            finally:
                container.remove(force=True)
                
        except Exception as e:
            return f"[Docker execution error: {str(e)}. Falling back to subprocess.]"
    
    async def execute(self, script: str) -> str:
        """Execute Python script asynchronously"""
        try:
            # Run execution in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            
            if self.use_docker:
                result = await loop.run_in_executor(None, self._execute_docker, script)
            else:
                result = await loop.run_in_executor(None, self._execute_subprocess, script)
            
            return result
            
        except Exception as e:
            return f"[Execution error: {str(e)}]"


# Global instance - auto-detect Docker, fallback to subprocess if not available
python_tool_wrapper = PythonToolWrapper(use_docker=None)