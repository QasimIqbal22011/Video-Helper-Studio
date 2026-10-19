import webview
import threading

class Api:
    def __init__(self):
        self.window = None

    def test_dialog(self):
        print("[Python] test_dialog called from JS!")
        print("[Python] Calling window.create_file_dialog...")
        try:
            res = self.window.create_file_dialog(webview.OPEN_DIALOG, allow_multiple=True)
            print("[Python] create_file_dialog returned:", res)
            return list(res) if res else []
        except Exception as e:
            print("[Python] Exception in create_file_dialog:", type(e), e)
            import traceback
            traceback.print_exc()
            return []

api = Api()
html = """
<!DOCTYPE html>
<html>
<body>
  <h2>Test Dialog</h2>
  <button id="btn">Click me</button>
  <script>
    window.addEventListener('pywebviewready', () => {
      console.log('pywebviewready!');
      document.getElementById('btn').onclick = async () => {
        console.log('Button clicked, calling api...');
        const res = await window.pywebview.api.test_dialog();
        console.log('Got response:', res);
      };
      // Auto click
      setTimeout(() => {
        document.getElementById('btn').click();
      }, 500);
    });
  </script>
</body>
</html>
"""

window = webview.create_window('Test Window', html=html, js_api=api)
api.window = window
# Auto close after 5 seconds
def auto_close():
    import time
    time.sleep(4)
    print("[Python] Auto closing test...")
    window.destroy()

threading.Thread(target=auto_close, daemon=True).start()
webview.start(debug=True)
