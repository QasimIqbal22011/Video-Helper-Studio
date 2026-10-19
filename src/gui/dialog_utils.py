import os
import sys
import subprocess
from ..core.logger import log_info, log_error

def pick_files():
    """
    Opens a native Windows Open File Dialog in an isolated subprocess.
    Because it runs in a separate process, it CANNOT freeze or block pywebview / WebView2.
    """
    log_info("Opening native Open File Dialog via isolated subprocess...")
    ps_code = (
        "[System.Reflection.Assembly]::LoadWithPartialName('System.Windows.Forms') | Out-Null; "
        "$f = New-Object System.Windows.Forms.OpenFileDialog; "
        "$f.Title = 'Select Audio Clips'; "
        "$f.Filter = 'All Supported Audio (*.mp3;*.wav;*.m4a;*.aac;*.flac;*.ogg;*.wma)|*.mp3;*.wav;*.m4a;*.aac;*.flac;*.ogg;*.wma|All Files (*.*)|*.*'; "
        "$f.Multiselect = $true; "
        "if ($f.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) { "
        "   $f.FileNames | ForEach-Object { Write-Output $_ } "
        "}"
    )

    startupinfo = None
    if sys.platform == "win32":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0

    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps_code],
            capture_output=True,
            text=True,
            startupinfo=startupinfo,
            timeout=120
        )
        if proc.returncode == 0 and proc.stdout:
            lines = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
            log_info(f"Open File Dialog returned {len(lines)} file(s).")
            return lines
    except Exception as e:
        log_error("Exception in pick_files subprocess:", e)

    return []

def pick_save(default_name="stitched_master.mp3"):
    """
    Opens a native Windows Save File Dialog in an isolated subprocess.
    Cannot freeze or block pywebview / WebView2.
    """
    log_info(f"Opening native Save File Dialog for '{default_name}' via isolated subprocess...")
    ps_code = f"""
    [System.Reflection.Assembly]::LoadWithPartialName('System.Windows.Forms') | Out-Null
    $d = New-Object System.Windows.Forms.SaveFileDialog
    $d.Title = 'Save Master Audio'
    $d.FileName = '{default_name}'
    $d.Filter = 'MP3 Audio (*.mp3)|*.mp3|WAV Audio (*.wav)|*.wav|M4A Audio (*.m4a)|*.m4a|All Files (*.*)|*.*'
    $d.DefaultExt = 'mp3'
    if ($d.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {{
        Write-Output $d.FileName
    }}
    """

    startupinfo = None
    if sys.platform == "win32":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0

    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps_code],
            capture_output=True,
            text=True,
            startupinfo=startupinfo,
            timeout=120
        )
        if proc.returncode == 0 and proc.stdout.strip():
            result = proc.stdout.strip().splitlines()[-1].strip()
            log_info(f"Save File Dialog selected: {result}")
            return result
    except Exception as e:
        log_error("Exception in pick_save subprocess:", e)

    return None
