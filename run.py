"""
ACAD Assistant - Application Launcher.
Starts the unified FastAPI web server on localhost:8000.
"""

import os
import socket
import sys

# Ensure UTF-8 stdout on Windows
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Add backend directory to sys.path
backend_dir = os.path.join(os.path.dirname(__file__), "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)


def get_local_ip():
    """Gets local network IP for mobile companion connection."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


if __name__ == "__main__":
    local_ip = get_local_ip()
    port = 8000

    print("=" * 65)
    print(">> ACAD ASSISTANT (Academic AI Assistant for Lecturers) <<")
    print("=" * 65)
    print(f"[*] Server berjalan pada:")
    print(f"    --> Localhost (Laptop Dosen): http://localhost:{port}")
    print(f"    --> Mobile Companion (Kamera HP/Tablet): http://{local_ip}:{port}")
    print("=" * 65)
    print("[*] Menjalankan server Uvicorn...")

    import uvicorn
    # Change working directory to backend so relative paths work cleanly
    os.chdir(backend_dir)
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)
