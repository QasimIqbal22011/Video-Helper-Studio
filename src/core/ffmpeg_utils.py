import os
import sys
import re
import subprocess
import shutil
import tempfile
from typing import Optional, Dict, Any, List, Callable

def get_ffmpeg_path() -> str:
    """
    Locates the ffmpeg executable.
    Checks:
    1. PyInstaller bundled path (_MEIPASS)
    2. Local project resources/ffmpeg/ffmpeg.exe
    3. System PATH
    4. imageio_ffmpeg fallback
    """
    # 1. Bundled in PyInstaller single-folder or one-file
    if hasattr(sys, '_MEIPASS'):
        bundle_ffmpeg = os.path.join(sys._MEIPASS, 'resources', 'ffmpeg', 'ffmpeg.exe')
        if os.path.exists(bundle_ffmpeg):
            return bundle_ffmpeg
        
    # Check next to executable if frozen
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(sys.executable)
        exe_ffmpeg = os.path.join(exe_dir, 'resources', 'ffmpeg', 'ffmpeg.exe')
        if os.path.exists(exe_ffmpeg):
            return exe_ffmpeg

    # 2. Workspace resources folder
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    local_ffmpeg = os.path.join(base_dir, 'resources', 'ffmpeg', 'ffmpeg.exe')
    if os.path.exists(local_ffmpeg):
        return local_ffmpeg

    # 3. Check system PATH
    sys_ffmpeg = shutil.which('ffmpeg')
    if sys_ffmpeg:
        return sys_ffmpeg

    # 4. Fallback to imageio_ffmpeg if installed
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass

    raise FileNotFoundError("Could not find ffmpeg.exe. Please ensure it is in resources/ffmpeg/ or on your PATH.")


def get_audio_info(file_path: str) -> Dict[str, Any]:
    """
    Extracts duration, sample rate, channels, and bitrate using ffmpeg -i.
    Returns:
        dict: {
            'duration': float (seconds),
            'duration_formatted': str (mm:ss),
            'sample_rate': int,
            'channels': int,
            'bitrate_kbps': int,
            'format_name': str,
            'size_bytes': int,
            'size_formatted': str
        }
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    ffmpeg_bin = get_ffmpeg_path()
    file_size = os.path.getsize(file_path)

    # Format file size
    if file_size < 1024 * 1024:
        size_str = f"{file_size / 1024:.1f} KB"
    else:
        size_str = f"{file_size / (1024 * 1024):.2f} MB"

    cmd = [ffmpeg_bin, "-hide_banner", "-i", file_path]
    # Run with windows hide flag
    startupinfo = None
    if sys.platform == "win32":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding='utf-8',
        errors='replace',
        startupinfo=startupinfo
    )
    _, stderr = proc.communicate()

    # Parse Duration: 00:01:23.45
    duration = 0.0
    dur_match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", stderr)
    if dur_match:
        hours = int(dur_match.group(1))
        minutes = int(dur_match.group(2))
        seconds = float(dur_match.group(3))
        duration = hours * 3600 + minutes * 60 + seconds

    # Format duration mm:ss
    total_sec = int(duration)
    mins = total_sec // 60
    secs = total_sec % 60
    duration_formatted = f"{mins:02d}:{secs:02d}"

    # Parse sample rate: e.g. 44100 Hz
    sample_rate = 44100
    sr_match = re.search(r"(\d+)\s*Hz", stderr)
    if sr_match:
        sample_rate = int(sr_match.group(1))

    # Parse channels: stereo or mono or 5.1
    channels = 2
    if "stereo" in stderr:
        channels = 2
    elif "mono" in stderr:
        channels = 1

    # Parse bitrate: e.g. 192 kb/s or 320 kb/s
    bitrate = 192
    br_match = re.search(r"bitrate:\s*(\d+)\s*kb/s", stderr)
    if br_match:
        bitrate = int(br_match.group(1))

    ext = os.path.splitext(file_path)[1].lower().replace('.', '')

    return {
        'path': file_path,
        'filename': os.path.basename(file_path),
        'duration': duration,
        'duration_formatted': duration_formatted,
        'sample_rate': sample_rate,
        'channels': channels,
        'bitrate_kbps': bitrate,
        'format_name': ext.upper(),
        'size_bytes': file_size,
        'size_formatted': size_str
    }
