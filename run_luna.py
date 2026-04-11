"""Luna Engine — compiled binary entry point."""
import sys
import os

# Force UTF-8 I/O — compiled binaries may default to ASCII, crashing on emoji/unicode
os.environ['PYTHONUTF8'] = '1'
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

import json
import threading
from pathlib import Path

# Resolve base directory
if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).parent

os.chdir(BASE_DIR)
os.environ['LUNA_BASE_DIR'] = str(BASE_DIR)
os.environ['LUNA_BASE_PATH'] = str(BASE_DIR)

# Data directory — separate from binary in Tauri/app mode
# LUNA_DATA_DIR (set by Tauri shell) -> ~/Library/Application Support/Luna/
# If not set, data lives alongside the binary (standalone mode)
DATA_DIR = Path(os.environ.get('LUNA_DATA_DIR', str(BASE_DIR)))
os.environ.setdefault('LUNA_DATA_DIR', str(DATA_DIR))

# Load secrets.json if it exists (replaces .env for compiled binary)
secrets_path = DATA_DIR / 'config' / 'secrets.json'
if secrets_path.exists():
    for key, val in json.loads(secrets_path.read_text()).items():
        if val:
            try:
                val.encode('ascii')
                os.environ[key] = val
            except UnicodeEncodeError:
                print(f"WARNING: {key} contains non-ASCII characters, skipping")

# Fallback: load .env if it exists (dev mode)
env_path = DATA_DIR / '.env' if (DATA_DIR / '.env').exists() else BASE_DIR / '.env'
if env_path.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(env_path)
    except ImportError:
        pass  # dotenv not available in compiled binary

# Only add src/ to path if the full source tree exists (dev mode).
# In compiled mode Nuitka has modules built in — a partial src/ dir
# in the dist would shadow them and cause ModuleNotFoundError.
if (BASE_DIR / 'src' / 'luna' / 'api').is_dir():
    sys.path.insert(0, str(BASE_DIR / 'src'))

import uvicorn
from luna.api.server import app


def _find_free_port(preferred: int = 8000) -> int | None:
    """Try preferred port. If busy and Luna is already running, return None."""
    import socket
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('127.0.0.1', preferred))
            return preferred
    except OSError:
        # Port busy — check if it's an existing Luna instance
        import urllib.request
        try:
            resp = urllib.request.urlopen(f'http://127.0.0.1:{preferred}/api/status', timeout=2)
            if resp.status == 200:
                return None  # Luna is already running
        except Exception:
            pass
        # Not Luna — fall back to OS-assigned ephemeral port
        print(f"WARNING: Port {preferred} busy (not Luna), using random port")
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('127.0.0.1', 0))
            return s.getsockname()[1]


def _run_server(port: int) -> None:
    """Start uvicorn in a background thread."""
    uvicorn.run(app, host='127.0.0.1', port=port, log_level='warning')


if __name__ == "__main__":
    explicit_port = os.environ.get('LUNA_PORT')
    if explicit_port:
        port = int(explicit_port)
    else:
        port = _find_free_port()
        if port is None:
            # Luna is already running on the preferred port
            import webbrowser
            preferred = 8000
            print(f"Luna is already running on port {preferred}. Opening browser.")
            webbrowser.open(f'http://127.0.0.1:{preferred}')
            sys.exit(0)
    os.environ['LUNA_PORT'] = str(port)

    if explicit_port:
        # Sidecar/headless mode — external process (Tauri) manages the window
        uvicorn.run(app, host='127.0.0.1', port=port, log_level='warning')
    else:
        # Standalone mode — we manage our own window
        server_thread = threading.Thread(target=_run_server, args=(port,), daemon=True)
        server_thread.start()

        try:
            import webview
            webview.create_window('Luna', f'http://127.0.0.1:{port}', width=1280, height=860)
            webview.start()
        except ImportError:
            import time
            import webbrowser
            time.sleep(2)
            webbrowser.open(f'http://127.0.0.1:{port}')
            print(f'Luna is running on port {port}. Press Ctrl+C to stop.')
            try:
                server_thread.join()
            except KeyboardInterrupt:
                pass
