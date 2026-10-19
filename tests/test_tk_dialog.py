import tkinter as tk
from tkinter import filedialog
import threading

def open_files_dialog():
    res = []
    def _run():
        root = tk.Tk()
        root.withdraw()
        root.wm_attributes('-topmost', 1)
        files = filedialog.askopenfilenames(
            title="Select Audio Files",
            filetypes=[
                ("Audio Files", "*.mp3 *.wav *.m4a *.aac *.flac *.ogg *.wma"),
                ("All Files", "*.*")
            ]
        )
        root.destroy()
        res.extend(files)

    t = threading.Thread(target=_run)
    t.start()
    t.join()
    return res

print("Tested dialog function defined.")
