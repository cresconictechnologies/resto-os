"""
RestoOS Serverless Entry Point for Vercel Deployment
Imports the ASGI FastAPI application from server.main.
"""

import sys
from pathlib import Path

# Ensure project root is in sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from server.main import app

# Vercel Serverless ASGI export
handler = app
