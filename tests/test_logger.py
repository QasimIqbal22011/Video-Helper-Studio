import os
import sys

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.core.logger import log_info, log_error, LOG_FILE

log_info("Verification entry: Logger initialized successfully.")
print("LOG_FILE location:", LOG_FILE)
print("File exists:", os.path.exists(LOG_FILE))
with open(LOG_FILE, 'r', encoding='utf-8') as f:
    print("Last 3 lines of debug_log.txt:")
    lines = f.readlines()
    for l in lines[-3:]:
        print("  ", l.strip())
