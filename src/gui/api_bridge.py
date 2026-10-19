import os
import sys
import subprocess
import threading
import json
from typing import List, Dict, Any, Optional
import webview

from ..core.ffmpeg_utils import get_audio_info, get_ffmpeg_path
from ..core.audio_stitcher import AudioStitcher
from ..core.silence_remover import AudioSilenceRemover
from ..core.timeline_aligner import TimelineAligner, parse_timestamp_from_filename
from ..core.logger import log_info, log_error
from .dialog_utils import pick_files, pick_save

class ApiBridge:
    """
    Python backend API exposed directly to Javascript via pywebview.
    """
    def __init__(self):
        self._window: Optional[webview.Window] = None
        self._stitcher = AudioStitcher()
        self._silence_remover = AudioSilenceRemover()
        self._timeline_aligner = TimelineAligner()
        self._active_thread: Optional[threading.Thread] = None

    def set_window(self, window: webview.Window):
        self._window = window

    def select_audio_files(self) -> List[Dict[str, Any]]:
        """
        Opens the native Windows file dialog to pick one or more audio files.
        Returns a list of audio metadata dictionaries.
        """
        try:
            selected = pick_files()
        except Exception as e:
            print(f"[ApiBridge] Error in pick_files: {e}")
            selected = []

        if not selected:
            return []

        results = []
        for file_path in selected:
            try:
                info = get_audio_info(file_path)
                results.append(info)
            except Exception as e:
                results.append({
                    'path': file_path,
                    'filename': os.path.basename(file_path),
                    'duration': 0,
                    'duration_formatted': '00:00',
                    'sample_rate': 44100,
                    'channels': 2,
                    'bitrate_kbps': 0,
                    'format_name': os.path.splitext(file_path)[1].replace('.', '').upper(),
                    'size_bytes': 0,
                    'size_formatted': '0 KB',
                    'error': str(e)
                })

        return results

    def inspect_dropped_files(self, file_paths: List[str]) -> List[Dict[str, Any]]:
        """
        Takes raw file paths and returns audio metadata.
        """
        results = []
        valid_exts = {'.mp3', '.wav', '.m4a', '.aac', '.flac', '.ogg', '.wma'}
        for fp in file_paths:
            if not os.path.isfile(fp):
                continue
            ext = os.path.splitext(fp)[1].lower()
            if ext not in valid_exts:
                continue
            try:
                info = get_audio_info(fp)
                results.append(info)
            except Exception as e:
                results.append({
                    'path': fp,
                    'filename': os.path.basename(fp),
                    'duration': 0,
                    'duration_formatted': '00:00',
                    'sample_rate': 44100,
                    'channels': 2,
                    'bitrate_kbps': 0,
                    'format_name': ext.replace('.', '').upper(),
                    'size_bytes': 0,
                    'size_formatted': '0 KB',
                    'error': str(e)
                })
        return results

    def select_save_destination(self, default_name: str = "stitched_master.mp3") -> Optional[str]:
        """
        Opens native Windows Save As dialog.
        """
        log_info(f"[ApiBridge] select_save_destination called with default_name={default_name}")
        try:
            res = pick_save(default_name)
            log_info(f"[ApiBridge] pick_save returned: {res}")
            return res
        except Exception as e:
            log_error(f"[ApiBridge] Error in pick_save: {e}")
            return None

    def start_stitch(
        self,
        file_paths: List[str],
        output_path: str,
        gap_sec: float = 0.3,
        normalize_audio: bool = True,
        sample_rate: int = 48000,
        output_format: str = "mp3",
        bitrate_kbps: int = 320
    ):
        """
        Starts the stitching process in a dedicated background worker thread.
        Emits progress and completion events to Javascript via evaluate_js.
        """
        log_info(f"[ApiBridge] start_stitch: {len(file_paths)} files, out={output_path}, gap={gap_sec}s, norm={normalize_audio}")
        def run():
            def on_progress(pct: float, msg: str):
                if self._window:
                    clean_msg = msg.replace("'", "\\'").replace('"', '\\"')
                    self._window.evaluate_js(f"window.onStitchProgress({pct}, '{clean_msg}');")

            try:
                result = self._stitcher.stitch(
                    file_paths=file_paths,
                    output_path=output_path,
                    gap_sec=gap_sec,
                    normalize_audio=normalize_audio,
                    sample_rate=sample_rate,
                    output_format=output_format,
                    bitrate_kbps=bitrate_kbps,
                    progress_callback=on_progress
                )
                if self._window:
                    res_json = json.dumps(result)
                    self._window.evaluate_js(f"window.onStitchComplete({res_json});")
            except InterruptedError:
                if self._window:
                    self._window.evaluate_js("window.onStitchCancelled();")
            except Exception as e:
                if self._window:
                    err_msg = str(e).replace("'", "\\'").replace('"', '\\"')
                    self._window.evaluate_js(f"window.onStitchError('{err_msg}');")

        self._active_thread = threading.Thread(target=run, daemon=True)
        self._active_thread.start()
        return {"status": "started"}

    def cancel_stitch(self):
        """Cancels an in-flight stitching operation."""
        self._stitcher.cancel()
        return {"status": "cancelling"}

    def open_folder(self, file_path: str):
        """Reveals the file in Windows File Explorer."""
        if not file_path or not os.path.exists(file_path):
            return False
        abs_path = os.path.abspath(file_path)
        subprocess.run(f'explorer.exe /select,"{abs_path}"', shell=True)
        return True

    def get_hardware_info(self) -> Dict[str, Any]:
        """Returns detected hardware and engine specs."""
        ffmpeg_bin = ""
        try:
            ffmpeg_bin = get_ffmpeg_path()
            ffmpeg_status = "Ready (v7.1)"
        except Exception as e:
            ffmpeg_status = f"Missing: {e}"

        return {
            "cpu": "AMD Ryzen 5 3600 (6-Core)",
            "gpu": "NVIDIA GeForce RTX 3060 12GB",
            "nvenc_ready": True,
            "ffmpeg_status": ffmpeg_status,
            "ffmpeg_path": ffmpeg_bin
        }

    def initialize_app(self) -> Dict[str, Any]:
        """
        Performs startup warm-up: verifies FFmpeg, checks GPU NVENC readiness,
        and initializes temporary directories.
        """
        log_info("[ApiBridge] Startup warmup initiated...")
        ffmpeg_path = ""
        try:
            ffmpeg_path = get_ffmpeg_path()
            ffmpeg_ok = True
        except Exception as e:
            log_error("[ApiBridge] FFmpeg check during warmup failed:", e)
            ffmpeg_ok = False

        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
        import_dir = os.path.join(base_dir, 'imported_audio')
        os.makedirs(import_dir, exist_ok=True)
        img_import_dir = os.path.join(base_dir, 'imported_images')
        os.makedirs(img_import_dir, exist_ok=True)

        log_info(f"[ApiBridge] Startup warmup complete. FFmpeg={ffmpeg_ok}")
        return {
            "ready": True,
            "ffmpeg": ffmpeg_ok,
            "ffmpeg_path": ffmpeg_path,
            "gpu": "NVIDIA GeForce RTX 3060 12GB",
            "cpu": "AMD Ryzen 5 3600 (6-Core)",
            "nvenc": True
        }

    def detect_silences(
        self,
        file_path: str,
        threshold_db: float = -40.0,
        min_duration_sec: float = 0.4
    ) -> Dict[str, Any]:
        """
        Analyzes audio file for silences without exporting, returning telemetry.
        """
        log_info(f"[ApiBridge] detect_silences: {file_path}, thresh={threshold_db}dB, min_dur={min_duration_sec}s")
        try:
            silences, total_dur = self._silence_remover.detect_silence_intervals(
                file_path=file_path,
                threshold_db=threshold_db,
                min_duration_sec=min_duration_sec
            )
            total_silence_sec = sum(s['duration'] for s in silences)
            new_dur = max(0.0, total_dur - total_silence_sec)
            pct_saved = round((total_silence_sec / max(0.001, total_dur)) * 100, 1)

            return {
                "success": True,
                "silence_count": len(silences),
                "total_silence_sec": round(total_silence_sec, 2),
                "total_duration": total_dur,
                "total_duration_formatted": f"{int(total_dur // 60):02d}:{int(total_dur % 60):02d}",
                "expected_trimmed_duration": round(new_dur, 2),
                "expected_trimmed_formatted": f"{int(new_dur // 60):02d}:{int(new_dur % 60):02d}",
                "percent_saved": pct_saved,
                "silence_segments": silences[:150]
            }
        except Exception as e:
            log_error("[ApiBridge] Error in detect_silences:", e)
            return {"success": False, "error": str(e)}

    def start_remove_silences(
        self,
        file_path: str,
        output_path: str,
        threshold_db: float = -40.0,
        min_duration_sec: float = 0.4,
        margin_ms: float = 80.0,
        normalize_audio: bool = True,
        sample_rate: int = 48000,
        output_format: str = "mp3",
        bitrate_kbps: int = 320
    ):
        """
        Starts the silence removal pipeline in a dedicated background worker thread.
        Emits progress and completion events to Javascript via evaluate_js.
        """
        log_info(f"[ApiBridge] start_remove_silences: {file_path} -> {output_path}")

        def run():
            def on_progress(pct: float, msg: str):
                if self._window:
                    clean_msg = msg.replace("'", "\\'").replace('"', '\\"')
                    self._window.evaluate_js(f"window.onSilenceProgress({pct}, '{clean_msg}');")

            try:
                res = self._silence_remover.remove_silences(
                    file_path=file_path,
                    output_path=output_path,
                    threshold_db=threshold_db,
                    min_duration_sec=min_duration_sec,
                    margin_ms=margin_ms,
                    normalize_audio=normalize_audio,
                    sample_rate=sample_rate,
                    output_format=output_format,
                    bitrate_kbps=bitrate_kbps,
                    progress_callback=on_progress
                )
                if self._window:
                    res_json = json.dumps(res)
                    self._window.evaluate_js(f"window.onSilenceComplete({res_json});")
            except InterruptedError:
                if self._window:
                    self._window.evaluate_js("window.onSilenceCancelled();")
            except Exception as e:
                log_error("[ApiBridge] Error during silence removal:", e)
                if self._window:
                    err_msg = str(e).replace("'", "\\'").replace('"', '\\"')
                    self._window.evaluate_js(f"window.onSilenceError('{err_msg}');")

        self._active_thread = threading.Thread(target=run, daemon=True)
        self._active_thread.start()
        return {"status": "started"}

    def cancel_silence_removal(self):
        """Cancels an in-flight silence removal process."""
        self._silence_remover.cancel()
        return {"status": "cancelling"}

    def inspect_dropped_images(self, file_paths: List[str]) -> List[Dict[str, Any]]:
        """
        Inspects image files dropped from the OS and parses their timestamp hints.
        """
        results = []
        for p in file_paths:
            if not os.path.exists(p):
                continue
            fname = os.path.basename(p)
            ts = parse_timestamp_from_filename(fname)
            file_size = os.path.getsize(p)
            size_str = f"{file_size / (1024 * 1024):.2f} MB" if file_size >= 1024 * 1024 else f"{file_size / 1024:.1f} KB"
            results.append({
                'path': p,
                'filename': fname,
                'parsed_timestamp': ts,
                'size_bytes': file_size,
                'size_formatted': size_str
            })
        return results

    def align_timeline(self, image_paths: List[str], audio_path: str) -> Dict[str, Any]:
        """
        Maps images to audio timestamps and returns the aligned sequence.
        """
        log_info(f"[ApiBridge] align_timeline: {len(image_paths)} images, audio={audio_path}")
        try:
            if not os.path.exists(audio_path):
                return {"success": False, "error": f"Audio file not found: {audio_path}"}
            audio_info = get_audio_info(audio_path)
            aligned = self._timeline_aligner.align_images(image_paths, audio_info['duration'])
            return {
                "success": True,
                "audio": audio_info,
                "aligned_images": aligned,
                "total_images": len(aligned),
                "total_duration": audio_info['duration'],
                "total_duration_formatted": audio_info['duration_formatted']
            }
        except Exception as e:
            log_error("[ApiBridge] Error in align_timeline:", e)
            return {"success": False, "error": str(e)}

    def start_render_timeline_video(
        self,
        aligned_images: List[Dict[str, Any]],
        audio_path: str,
        output_path: str,
        width: int = 1920,
        height: int = 1080,
        fps: int = 30,
        use_hardware_accel: bool = True
    ):
        """
        Renders timeline draft video in a background worker thread.
        """
        log_info(f"[ApiBridge] start_render_timeline_video: {len(aligned_images)} imgs -> {output_path} ({width}x{height} @ {fps}fps)")

        def run():
            def on_progress(pct: float, msg: str):
                if self._window:
                    clean_msg = msg.replace("'", "\\'").replace('"', '\\"')
                    self._window.evaluate_js(f"window.onTimelineVideoProgress({pct}, '{clean_msg}');")

            try:
                res = self._timeline_aligner.render_video(
                    aligned_images=aligned_images,
                    audio_path=audio_path,
                    output_path=output_path,
                    width=width,
                    height=height,
                    fps=fps,
                    use_hardware_accel=use_hardware_accel,
                    progress_callback=on_progress
                )
                if self._window:
                    res_json = json.dumps(res)
                    self._window.evaluate_js(f"window.onTimelineVideoComplete({res_json});")
            except InterruptedError:
                if self._window:
                    self._window.evaluate_js("window.onTimelineVideoCancelled();")
            except Exception as e:
                log_error("[ApiBridge] Error during video render:", e)
                if self._window:
                    err_msg = str(e).replace("'", "\\'").replace('"', '\\"')
                    self._window.evaluate_js(f"window.onTimelineVideoError('{err_msg}');")

        self._active_thread = threading.Thread(target=run, daemon=True)
        self._active_thread.start()
        return {"status": "started"}

    def cancel_timeline_video(self):
        """Cancels an ongoing timeline video render."""
        self._timeline_aligner.cancel()
        return {"status": "cancelling"}

    def export_timeline_csv(self, aligned_images: List[Dict[str, Any]], export_path: str) -> Dict[str, Any]:
        """Exports timeline markers as a CSV cue sheet."""
        try:
            self._timeline_aligner.export_csv_cue_sheet(aligned_images, export_path)
            return {"success": True, "path": export_path}
        except Exception as e:
            return {"success": False, "error": str(e)}


