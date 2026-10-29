"""
RestoOS Desktop Standalone Application Launcher
Bundles FastAPI backend, SQLite local database, and bilingual web interface into a single Windows .exe.
"""
import os
import sys
import time
import socket
import threading
import webbrowser
from pathlib import Path

# Fix sys.path for PyInstaller frozen app
if getattr(sys, "frozen", False):
    bundle_dir = Path(sys._MEIPASS)
    exe_dir = Path(sys.executable).parent
    os.environ["RESTOOS_DATA_DIR"] = str(exe_dir)
else:
    bundle_dir = Path(__file__).resolve().parent
    exe_dir = bundle_dir

if str(bundle_dir) not in sys.path:
    sys.path.insert(0, str(bundle_dir))

import uvicorn
from server.main import app

def find_available_port(preferred=8000):
    for port in [preferred, 8001, 8002, 8080]:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return preferred

def open_browser(port):
    """Wait for server to bind port and launch the default browser to RestoOS."""
    time.sleep(1.8)
    url = f"http://127.0.0.1:{port}/"
    try:
        print(f"[RestoOS] Launching browser: {url}")
        webbrowser.open(url)
    except Exception as e:
        print(f"[RestoOS] Notice: Could not open browser automatically: {e}")

def main():
    target_port = find_available_port(8000)
    db_path = exe_dir / "restoos.db"
    
    print("=" * 68)
    print("  RestoOS — Modern Restaurant, Bar & Two-Tier Inventory Engine")
    print("  Edition: Pune Sahyadri & Permit Room FL-3 (Bilingual EN / मराठी)")
    print(f"  Live Desktop URL:     http://127.0.0.1:{target_port}/")
    print(f"  Persistent Database:  {db_path}")
    print("=" * 68)
    print("Starting background service and opening browser...")

    # Start browser opener in background thread
    threading.Thread(target=open_browser, args=(target_port,), daemon=True).start()

    # Run Uvicorn directly with the app object
    uvicorn.run(app, host="127.0.0.1", port=target_port, log_level="info")

if __name__ == "__main__":
    main()
