import os
import sys
import io

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.gui.server import create_app
from src.core.ffmpeg_utils import get_ffmpeg_path
import subprocess

def test_upload():
    ffmpeg_bin = get_ffmpeg_path()
    test_wav = os.path.join(BASE_DIR, "scratch_test_upload.wav")
    # Generate 5-second tone (~450KB, which would have failed with the old 100KB limit!)
    subprocess.run([ffmpeg_bin, "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=5.0", test_wav], check=True, capture_output=True)
    size = os.path.getsize(test_wav)
    print(f"Generated test file: {size} bytes ({size / 1024:.1f} KB)")

    app = create_app(os.path.join(BASE_DIR, 'src', 'gui', 'web'))

    # Simulate multipart POST to /upload_audio using webtest or bottle's test client
    import urllib.request
    from wsgiref.simple_server import make_server
    import threading

    server = make_server('127.0.0.1', 59921, app)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()

    # Upload using requests / urllib
    import requests
    with open(test_wav, 'rb') as f:
        files = {'audio_files': ('scratch_test_upload.wav', f, 'audio/wav')}
        res = requests.post('http://127.0.0.1:59921/upload_audio', files=files)

    print("Status code:", res.status_code)
    print("Response JSON:", res.json())
    server.shutdown()

    # Cleanup
    if os.path.exists(test_wav):
        os.remove(test_wav)

    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    data = res.json()
    assert data["success"] is True, f"Upload failed: {data}"
    assert len(data["clips"]) > 0, "No clips returned"
    print("\nUPLOAD TEST PASSED SUCCESSFULLY!")

if __name__ == '__main__':
    test_upload()
