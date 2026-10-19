import webview
import threading
import tkinter as tk
from tkinter import filedialog

class Api:
    def __init__(self):
        self.window = None

    def test_tk_dialog(self):
        print("[Python] test_tk_dialog called from JS!")
        result = []
        def _dialog():
            root = tk.Tk()
            root.withdraw()
            root.wm_attributes('-topmost', 1)
            # Just test creating and destroying without user interaction
            print("[Python] Tk root created successfully!")
            root.destroy()
            result.append("OK")

        t = threading.Thread(target=_dialog)
        t.start()
        t.join(timeout=2.0)
        print("[Python] Thread finished. Result:", result)
        return result

api = Api()
html = """
<!DOCTYPE html>
<html>
<body>
  <h2>Test Tk Dialog</h2>
  <script>
    window.addEventListener('pywebviewready', async () => {
      console.log('pywebviewready!');
      const res = await window.pywebview.api.test_tk_dialog();
      console.log('JS received:', res);
    });
  </script>
</body>
</html>
"""

window = webview.create_window('Test Window', html=html, js_api=api)
api.window = window

def auto_close():
    import time
    time.sleep(3)
    window.destroy()

threading.Thread(target=auto_close, daemon=True).start()
webview.start(debug=False)
