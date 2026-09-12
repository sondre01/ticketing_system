import os
import sys
import subprocess

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
venv_python = os.path.join(ROOT_DIR, ".venv", "Scripts", "python.exe")

# Automatically switch to project virtual environment if run with global python
if os.path.exists(venv_python) and sys.executable.lower() != os.path.abspath(venv_python).lower():
    result = subprocess.run([venv_python] + sys.argv)
    sys.exit(result.returncode)

import uvicorn
from backend.config import HOST, PORT

if __name__ == "__main__":
    print("=" * 60)
    print("Khin Ticket System Starting...")
    print(f"Server URL: http://{HOST}:{PORT}")
    print(f"API Docs:   http://{HOST}:{PORT}/docs")
    print("=" * 60)
    uvicorn.run("backend.main:app", host=HOST, port=PORT, reload=True)
