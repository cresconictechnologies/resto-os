"""
RestoOS PyInstaller Build Script
Compiles the complete Python FastAPI application and static web frontend into a standalone Windows RestoOS.exe.
"""
import sys
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent

def build():
    print("=" * 65)
    print("Building standalone RestoOS.exe with PyInstaller...")
    print("Project Root:", PROJECT_ROOT)
    print("=" * 65)

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--name=RestoOS",
        "--onefile",
        "--clean",
        "--add-data=static;static",
        "--add-data=server/restoos.db;server",
        "--hidden-import=uvicorn.logging",
        "--hidden-import=uvicorn.loops",
        "--hidden-import=uvicorn.loops.auto",
        "--hidden-import=uvicorn.protocols",
        "--hidden-import=uvicorn.protocols.http",
        "--hidden-import=uvicorn.protocols.http.auto",
        "--hidden-import=uvicorn.protocols.websockets",
        "--hidden-import=uvicorn.protocols.websockets.auto",
        "--hidden-import=uvicorn.lifespans",
        "--hidden-import=uvicorn.lifespans.on",
        "--hidden-import=starlette.middleware.base",
        "--hidden-import=sqlalchemy.dialects.sqlite",
        "run_desktop.py",
    ]

    print("Running command:\n", " ".join(cmd))
    res = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
    if res.returncode == 0:
        exe_path = PROJECT_ROOT / "dist" / "RestoOS.exe"
        print("\n" + "=" * 65)
        print("BUILD SUCCESSFUL!")
        print("Standalone Executable created at:")
        print(f" -> {exe_path}")
        if exe_path.exists():
            size_mb = exe_path.stat().st_size / (1024 * 1024)
            print(f" -> Size: {size_mb:.2f} MB")
        print("=" * 65)
    else:
        print("\nBuild failed with exit code:", res.returncode)
        sys.exit(res.returncode)

if __name__ == "__main__":
    build()
