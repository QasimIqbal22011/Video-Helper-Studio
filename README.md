# Video Helper Studio (YouTube Automation Desktop App)

A modern, standalone desktop application designed to automate tedious editing workflows for YouTube Automation content creators. Built with Python, pywebview (Chromium WebView2), and high-performance FFmpeg hardware acceleration.

> 📘 **For AI Assistants & Developers**: See [AI_DEVELOPER_GUIDE.md](file:///a:/My%20Video%20Hwelper%20APP/AI_DEVELOPER_GUIDE.md) for the complete engineering manual, internal contracts, threading rules, and gotchas.

---

## Active Workflow Engines

### 🎚️ 1. Audio Stitcher & Master Voiceover Builder (Ready)
- **Multi-Format Input**: Support for `.mp3`, `.wav`, `.m4a`, `.aac`, `.flac`, `.ogg`, and `.wma`.
- **Drag-and-Drop & Reordering**: Easily reorder clips via drag-and-drop, Move Up / Move Down buttons, or **Natural Alphanumeric Sorting** (`1.wav`, `2.wav`, `10.wav`).
- **Inline Clip Preview**: Instant audio preview for each added clip directly in the list.
- **Smart Pause Spacing**: Configurable pause/gap between clips (`0.0s`, `0.2s`, `0.3s`, `0.5s`, `1.0s`, or custom slider).
- **YouTube Loudness Mastering**: Built-in EBU R128 (`-16 LUFS`, `-1.5 dB True Peak`) normalization to prevent volume imbalances between voiceover takes.
- **Pipeline Integration**: 1-click **"Send to Silence Remover"** and **"Send to Timeline"** buttons.

### ✂️ 2. Audio Silence Remover (Ready)
- **Dead-Air Removal**: Uses FFmpeg `silencedetect` with configurable dB threshold and minimum duration.
- **Voice Safety Buffers**: Adds configurable margin padding (`80ms` recommended) to the start and end of speech segments to guarantee word endings and natural breaths are never clipped.
- **Micro-Crossfade Concatenation**: Assembles active speech segments with zero click/pop artifacts.
- **Live Telemetry UI**: Real-time list of detected pauses with timestamps and time saved.
- **Pipeline Integration**: 1-click **"Send to Stitcher"** and **"Send to Timeline"** buttons.

### ⏱️ 3. Smart Timeline Image Aligner (Ready)
- **Automated Mapping**: Parses timestamp cues from filenames (`00:00.png`, `00_07.jpg`, `01_23.png`, `0015.png`, etc.) and positions each image along the audio timeline.
- **Interactive Sequence Cards**: Displays live image thumbnails with start/end timestamps and duration badges.
- **NVENC Hardware Acceleration**: High-speed video rendering using **NVIDIA RTX 3060 NVENC** (`h264_nvenc`) with CPU fallback (`libx264`).
- **Embedded Video Player**: Watch and review the rendered 1080p video directly inside the app.
- **CSV Cue Sheet**: Exports a timestamped CSV sheet for direct import into Premiere Pro / DaVinci Resolve.

### 🎬 4. Ken Burns Zoom & Crossfade Transitions (Upcoming Next)
- Smooth dynamic zoom-in / zoom-out motion and crossfade transitions for YouTube viewer retention.

---

## 🎨 Design & Aesthetic
- **Native Desktop Window**: Standalone desktop window powered by pywebview (no browser tabs, no command prompt popup).
- **Dark Obsidian & Crisp Light Themes**: Fast toggle with persisted user preference.
- **Hardware Status Indicator**: Automatically checks and displays GPU NVENC and CPU specs during startup.

---

## 🚀 How to Run

### Option A: Run the Standalone .exe (No Python Required)
Navigate to the `dist` folder and launch:
```text
A:\My Video Hwelper APP\dist\VideoHelper\VideoHelper.exe
```

### Option B: Run from Source (Python Dev Mode)
```powershell
python src/main.py
```

### Option C: Run Unit Tests
```powershell
python tests/test_stitcher.py
python tests/test_silence.py
python tests/test_timeline.py
```

### Option D: Recompile the .exe
```powershell
python build_exe.py
```
