"""
Automated Build Script for Video Helper Studio
Compiles the application into a standalone Windows Executable (.exe)
"""
import os
import subprocess
import sys

def build():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    spec_file = os.path.join(base_dir, "VideoHelper.spec")

    print("=" * 60)
    print("Building Video Helper Studio Standalone Executable...")
    print(f"Working Directory: {base_dir}")
    print(f"Spec File: {spec_file}")
    print("=" * 60)

    cmd = [
        sys.executable,
        "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        spec_file
    ]

    result = subprocess.run(cmd, cwd=base_dir)
    if result.returncode == 0:
        exe_path = os.path.join(base_dir, "dist", "VideoHelper", "VideoHelper.exe")
        print("\n" + "=" * 60)
        print("BUILD SUCCESSFUL!")
        print(f"Standalone executable located at:\n{exe_path}")
        print("=" * 60)
    else:
        print("\nBuild failed with exit code:", result.returncode)

if __name__ == '__main__':
    build()
