import subprocess
import time

def test_save_dialog():
    ps_code = """
    Add-Type -AssemblyName System.Windows.Forms
    $d = New-Object System.Windows.Forms.SaveFileDialog
    $d.FileName = 'master_audio.mp3'
    $d.Filter = 'MP3 Audio (*.mp3)|*.mp3|WAV Audio (*.wav)|*.wav|All Files (*.*)|*.*'
    Write-Output "PS Dialog Script Verified"
    """
    cmd = ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps_code]
    t0 = time.time()
    res = subprocess.run(cmd, capture_output=True, text=True)
    t1 = time.time()
    print("Output:", res.stdout.strip())
    print("Time taken:", round(t1 - t0, 2), "seconds")

test_save_dialog()
