import os
import sys
import subprocess
import time
import webbrowser
from threading import Thread

# Get project root and venv paths
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
VENV_DIR = os.path.join(ROOT_DIR, "venv")

# Determine the venv python executable location
if sys.platform == "win32":
    VENV_PYTHON = os.path.join(VENV_DIR, "Scripts", "python.exe")
else:
    VENV_PYTHON = os.path.join(VENV_DIR, "bin", "python")

def is_venv():
    """Checks if the current process is running inside a virtual environment."""
    return sys.prefix != sys.base_prefix or hasattr(sys, 'real_prefix')

def ensure_venv():
    """Checks if venv exists, and creates it if not."""
    if not os.path.exists(VENV_DIR):
        print(" Virtual environment not found. Creating it now...")
        # Use current python to create the venv
        subprocess.run([sys.executable, "-m", "venv", "venv"], check=True)
        print("✅ venv created.")

def re_execute_in_venv():
    """Restarts the script using the venv's python if we're not already in it."""
    if not is_venv():
        if os.path.exists(VENV_PYTHON):
            print(f"🔄 Switching to virtual environment...")
            # Re-run this script with the venv's python
            os.execv(VENV_PYTHON, [VENV_PYTHON] + sys.argv)
        else:
            print(" Critical: venv python not found despite check. Proceeding with caution...")

def install_requirements():
    """Asks user if they want to install dependencies and proceeds if yes."""
    req_path = os.path.join(ROOT_DIR, "backend", "requirements.txt")
    
    if os.path.exists(req_path):
        choice = input("📦 Do you want to check and install/update required libraries? (y/N): ").strip().lower()
        if choice == 'y':
            print("Installing dependencies...")
            # Use sys.executable which is now the venv python
            subprocess.run([sys.executable, "-m", "pip", "install", "-r", req_path], check=True)
        else:
            print("Skipping dependency installation.")
    else:
        print(f"Warning: Requirements file not found at {req_path}")

def run_server():
    """Runs the FastAPI server from the backend folder using the venv python."""
    backend_dir = os.path.join(ROOT_DIR, "backend")
    os.chdir(backend_dir)
    print("Starting MedSearch Backend...")
    # uvicorn is installed in venv, so -m uvicorn works with venv's python
    subprocess.run([sys.executable, "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"])

def open_browser():
    """Waits for the server to spin up and opens the browser."""
    print("Waiting for server to start...")
    time.sleep(4) 
    url = "http://127.0.0.1:8000"
    print(f"Opening browser at {url}")
    webbrowser.open(url)

if __name__ == "__main__":
    ensure_venv()
    re_execute_in_venv()
    
    install_requirements()

    # Start the server in a separate thread
    server_thread = Thread(target=run_server)
    server_thread.daemon = True
    server_thread.start()
    
    open_browser()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down MedSearch...")
        sys.exit(0)
