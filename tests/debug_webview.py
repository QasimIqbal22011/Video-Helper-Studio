import webview
from webview.util import parse_file_type

f1 = 'Audio Files (*.mp3;*.wav;*.m4a;*.aac;*.flac;*.ogg)'
f2 = 'All files (*.*)'
print("Testing parse_file_type:")
try:
    print("f1:", parse_file_type(f1))
except Exception as e:
    print("f1 error:", e)

try:
    print("f2:", parse_file_type(f2))
except Exception as e:
    print("f2 error:", e)
