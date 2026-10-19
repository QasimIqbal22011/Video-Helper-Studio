import os
import sys
import threading
import logging
import traceback
from datetime import datetime

# Determine base application directory
if getattr(sys, 'frozen', False):
    APP_DIR = os.path.dirname(sys.executable)
else:
    APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

LOG_FILE = os.path.join(APP_DIR, "debug_log.txt")

class LoggerWriter:
    """Redirects stdout/stderr writes to both original stream and log file."""
    def __init__(self, original_stream, log_func, prefix=""):
        self.original_stream = original_stream
        self.log_func = log_func
        self.prefix = prefix
        self.buffer = ""

    def write(self, message):
        if self.original_stream:
            try:
                self.original_stream.write(message)
                self.original_stream.flush()
            except Exception:
                pass
        
        self.buffer += message
        while "\n" in self.buffer:
            line, self.buffer = self.buffer.split("\n", 1)
            line = line.strip()
            if line:
                self.log_func(f"{self.prefix}{line}")

    def flush(self):
        if self.original_stream:
            try:
                self.original_stream.flush()
            except Exception:
                pass

def setup_logger():
    """Initializes the file logger and hooks for unhandled exceptions."""
    logger = logging.getLogger("VideoHelper")
    logger.setLevel(logging.DEBUG)

    # File Handler
    try:
        fh = logging.FileHandler(LOG_FILE, mode='a', encoding='utf-8')
        fh.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            '[%(asctime)s] [%(levelname)s] [%(threadName)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        fh.setFormatter(formatter)
        logger.addHandler(fh)
    except Exception as e:
        print(f"Could not initialize FileHandler for {LOG_FILE}: {e}")

    logger.info("=" * 70)
    logger.info(f"Video Helper Studio Started at {datetime.now().isoformat()}")
    logger.info(f"Python: {sys.version}")
    logger.info(f"App Directory: {APP_DIR}")
    logger.info(f"Log File: {LOG_FILE}")
    logger.info("=" * 70)

    # Redirect stdout and stderr
    sys.stdout = LoggerWriter(sys.stdout, logger.info, prefix="[STDOUT] ")
    sys.stderr = LoggerWriter(sys.stderr, logger.error, prefix="[STDERR] ")

    # Catch unhandled main thread exceptions
    def global_excepthook(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        err_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        logger.critical(f"UNHANDLED EXCEPTION:\n{err_msg}")

    sys.excepthook = global_excepthook

    # Catch unhandled background thread exceptions (Python 3.8+)
    def thread_excepthook(args):
        err_msg = "".join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback))
        logger.critical(f"UNHANDLED THREAD EXCEPTION in [{args.thread.name}]:\n{err_msg}")

    threading.excepthook = thread_excepthook

    return logger

app_logger = setup_logger()

def log_info(msg: str):
    app_logger.info(msg)

def log_error(msg: str, exc: Exception = None):
    if exc:
        app_logger.error(f"{msg}\n{traceback.format_exc()}")
    else:
        app_logger.error(msg)

def log_client_event(level: str, msg: str):
    """Logs client-side events or errors sent from JavaScript."""
    if level.lower() == 'error':
        app_logger.error(f"[CLIENT-JS] {msg}")
    elif level.lower() == 'warn':
        app_logger.warning(f"[CLIENT-JS] {msg}")
    else:
        app_logger.info(f"[CLIENT-JS] {msg}")
