import os
import sys
import socket
import threading
import webview
from wsgiref.simple_server import make_server, WSGIRequestHandler

# Ensure project root is in sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.core.logger import log_info, log_error
from src.gui.server import create_app
from src.gui.api_bridge import ApiBridge

class SilentWSGIRequestHandler(WSGIRequestHandler):
    """Suppresses standard console request logging for a cleaner terminal output."""
    def log_message(self, format, *args):
        pass

def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]

def run_server(app, host: str, port: int):
    server = make_server(host, port, app, handler_class=SilentWSGIRequestHandler)
    server.serve_forever()

def main():
    # Locate web assets directory
    if hasattr(sys, '_MEIPASS'):
        web_dir = os.path.join(sys._MEIPASS, 'src', 'gui', 'web')
    else:
        web_dir = os.path.join(BASE_DIR, 'src', 'gui', 'web')

    app = create_app(web_dir)
    port = find_free_port()
    host = '127.0.0.1'

    # Start local backend WSGI server in background daemon thread
    server_thread = threading.Thread(target=run_server, args=(app, host, port), daemon=True)
    server_thread.start()

    # Initialize PyWebView JS API Bridge
    bridge = ApiBridge()

    # Create native standalone desktop window (matches OpenVox desktop shell)
    window = webview.create_window(
        title="Video Helper Studio",
        url=f"http://{host}:{port}/",
        js_api=bridge,
        width=1240,
        height=840,
        min_size=(960, 680),
        background_color='#0b0e17'
    )
    bridge.set_window(window)

    # Launch PyWebView with Chromium WebView2 runtime
    debug_mode = "--debug" in sys.argv
    webview.start(debug=debug_mode, private_mode=False)

if __name__ == '__main__':
    main()
