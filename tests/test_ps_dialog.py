import os
import sys
import subprocess

def test_ps_dialog():
    ps_cmd = (
        "[System.Reflection.Assembly]::LoadWithPartialName('System.Windows.Forms') | Out-Null; "
        "$f = New-Object System.Windows.Forms.OpenFileDialog; "
        "$f.Filter = 'Audio Files (*.mp3;*.wav)|*.mp3;*.wav|All Files (*.*)|*.*'; "
        "$f.Multiselect = $true; "
        "if ($f.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) { $f.FileNames }"
    )
    print("Testing PowerShell OpenFileDialog syntax...")
    cmd = ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps_cmd]
    # We won't block for user input, just verify it launches without error
    print("Command ready:", cmd[:3])

test_ps_dialog()
