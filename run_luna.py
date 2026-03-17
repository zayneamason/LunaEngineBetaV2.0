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
            os.environ[key] = val

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


def _find_free_port() -> int:
    """Grab an ephemeral port from the OS — guaranteed not to collide."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def _run_server(port: int) -> None:
    """Start uvicorn in a background thread."""
    uvicorn.run(app, host='127.0.0.1', port=port, log_level='warning')


if __name__ == "__main__":
    explicit_port = os.environ.get('LUNA_PORT')
    port = int(explicit_port) if explicit_port else _find_free_port()
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
