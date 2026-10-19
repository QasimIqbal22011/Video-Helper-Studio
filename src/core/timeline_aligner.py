import os
import sys
import re
import subprocess
import threading
import tempfile
from typing import List, Dict, Any, Optional, Callable, Tuple
from .ffmpeg_utils import get_ffmpeg_path, get_audio_info
from .logger import log_info, log_error

def format_seconds_to_time(sec: float) -> str:
    """Formats float seconds into MM:SS.ss or HH:MM:SS."""
    if sec < 0:
        sec = 0.0
    hrs = int(sec // 3600)
    mins = int((sec % 3600) // 60)
    secs = sec % 60
    if hrs > 0:
        return f"{hrs:02d}:{mins:02d}:{secs:05.2f}"
    return f"{mins:02d}:{secs:05.2f}"

def parse_timestamp_from_filename(filename: str) -> Optional[float]:
    """
    Extracts timestamp cues in seconds from image filenames.
    Supports formats like:
      - 00:00.png, 01:23.jpg, 01:05:20.png
      - 00_00.png, 01_23.jpg, 01_05_20.png
      - 00-00.png, 01-23.jpg
      - 00.15.png, 01.23.jpg
      - 0015.png, 0130.jpg (4 digits MMSS)
      - scene_01_23.png, 00_15_intro.jpg
      - 00_15_500.png (with milliseconds)
    """
    stem = os.path.splitext(filename)[0]

    # Pattern 1: HH:MM:SS or HH_MM_SS or HH-MM-SS
    m_hms = re.search(r'(?:^|[^\d])(\d{1,2})[:_.-](\d{2})[:_.-](\d{2})(?:[:_.-](\d{1,3}))?(?:[^\d]|$)', stem)
    if m_hms:
        hrs = int(m_hms.group(1))
        mins = int(m_hms.group(2))
        secs = int(m_hms.group(3))
        ms = float("0." + m_hms.group(4)) if m_hms.group(4) else 0.0
        return hrs * 3600.0 + mins * 60.0 + secs + ms

    # Pattern 2: MM:SS or MM_SS or MM-SS or MM.SS (e.g. 01:23, 00_15, 05-40)
    m_ms = re.search(r'(?:^|[^\d])(\d{1,3})[:_.-](\d{2})(?:[:_.-](\d{1,3}))?(?:[^\d]|$)', stem)
    if m_ms:
        mins = int(m_ms.group(1))
        secs = int(m_ms.group(2))
        ms = float("0." + m_ms.group(3)) if m_ms.group(3) else 0.0
        return mins * 60.0 + secs + ms

    # Pattern 3: 4 consecutive digits (e.g. 0000 -> 0s, 0130 -> 1m30s = 90s)
    m_4d = re.search(r'(?:^|[^\d])(\d{2})(\d{2})(?:[^\d]|$)', stem)
    if m_4d:
        mins = int(m_4d.group(1))
        secs = int(m_4d.group(2))
        if mins < 60 and secs < 60:
            return mins * 60.0 + secs

    return None

class TimelineAligner:
    """
    Intelligent timeline image-audio aligner for YouTube video automation.
    Maps timed still images against voiceover audio, produces synchronized
    timeline telemetry, and renders NVENC-accelerated MP4 drafts.
    """

    def __init__(self):
        self._current_process: Optional[subprocess.Popen] = None
        self._is_cancelled = False
        self._lock = threading.Lock()

    def cancel(self):
        """Cancels an in-flight video rendering process."""
        with self._lock:
            self._is_cancelled = True
            if self._current_process and self._current_process.poll() is None:
                try:
                    self._current_process.terminate()
                except Exception:
                    try:
                        self._current_process.kill()
                    except Exception:
                        pass

    def align_images(
        self,
        image_paths: List[str],
        audio_duration: float
    ) -> List[Dict[str, Any]]:
        """
        Calculates the start time, end time, and duration for every image
        along the audio timeline.
        """
        if not image_paths:
            return []

        parsed_items = []
        for idx, img_path in enumerate(image_paths):
            filename = os.path.basename(img_path)
            ts = parse_timestamp_from_filename(filename)
            parsed_items.append({
                'path': img_path,
                'filename': filename,
                'parsed_timestamp': ts,
                'original_index': idx
            })

        # Separate items with explicit timestamps and items without
        with_ts = [it for it in parsed_items if it['parsed_timestamp'] is not None]
        without_ts = [it for it in parsed_items if it['parsed_timestamp'] is None]

        # If all or most have timestamps, sort by parsed_timestamp
        if len(with_ts) > 0:
            with_ts.sort(key=lambda x: x['parsed_timestamp'])
            # Any images without timestamps can be placed at the end or interleaved
            ordered_items = with_ts + without_ts
        else:
            # Fallback: keep original file order
            ordered_items = parsed_items

        total_images = len(ordered_items)
        aligned = []

        # Calculate time positions
        for i, item in enumerate(ordered_items):
            # Determine start time
            if item['parsed_timestamp'] is not None:
                start_sec = max(0.0, float(item['parsed_timestamp']))
            else:
                # Evenly distribute if timestamp is missing
                start_sec = round((i / max(1, total_images)) * audio_duration, 2)

            aligned.append({
                'index': i,
                'path': item['path'],
                'filename': item['filename'],
                'start_sec': start_sec,
                'end_sec': 0.0,
                'duration': 0.0
            })

        # Ensure first image starts at 0.0 if not already
        if aligned:
            aligned[0]['start_sec'] = 0.0

        # Compute end_sec and duration for each image
        for i in range(total_images):
            start = aligned[i]['start_sec']
            if i < total_images - 1:
                next_start = aligned[i + 1]['start_sec']
                # Ensure each image has at least 0.2s duration
                end = max(start + 0.2, next_start)
                # Adjust next image start if necessary to avoid overlaps
                aligned[i + 1]['start_sec'] = max(aligned[i + 1]['start_sec'], end)
            else:
                # Last image holds until the audio ends
                end = max(start + 0.5, audio_duration)

            dur = round(end - start, 3)
            aligned[i]['start_sec'] = round(start, 3)
            aligned[i]['end_sec'] = round(end, 3)
            aligned[i]['duration'] = dur
            aligned[i]['start_formatted'] = format_seconds_to_time(start)
            aligned[i]['end_formatted'] = format_seconds_to_time(end)
            aligned[i]['duration_formatted'] = f"{dur:.2f}s"

        return aligned

    def render_video(
        self,
        aligned_images: List[Dict[str, Any]],
        audio_path: str,
        output_path: str,
        width: int = 1920,
        height: int = 1080,
        fps: int = 30,
        use_hardware_accel: bool = True,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> Dict[str, Any]:
        """
        Renders a 1080p/4K MP4 video with synchronized audio from aligned still images.
        Uses NVENC hardware acceleration when available.
        """
        self._is_cancelled = False

        if not aligned_images:
            raise ValueError("No images provided for timeline alignment.")
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        audio_info = get_audio_info(audio_path)
        total_audio_dur = audio_info['duration']

        if progress_callback:
            progress_callback(5.0, "Preparing timeline video manifest...")

        # Create temporary FFmpeg concat manifest
        temp_dir = tempfile.mkdtemp(prefix="vh_timeline_")
        manifest_path = os.path.join(temp_dir, "concat_manifest.txt")

        try:
            with open(manifest_path, "w", encoding="utf-8") as f:
                f.write("ffconcat version 1.0\n")
                for item in aligned_images:
                    clean_path = item['path'].replace("\\", "/")
                    dur = max(0.04, float(item['duration']))
                    f.write(f"file '{clean_path}'\n")
                    f.write(f"duration {dur:.4f}\n")
                # Repeat last image once without duration per FFmpeg concat demuxer spec
                last_path = aligned_images[-1]['path'].replace("\\", "/")
                f.write(f"file '{last_path}'\n")

            ffmpeg_bin = get_ffmpeg_path()
            out_dir = os.path.dirname(os.path.abspath(output_path))
            os.makedirs(out_dir, exist_ok=True)

            # Filter for scaling and letterboxing/pillarboxing to target resolution
            vf = (
                f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black,"
                f"fps={fps},format=yuv420p"
            )

            cmd = [
                ffmpeg_bin, "-y", "-hide_banner",
                "-f", "concat", "-safe", "0", "-i", manifest_path,
                "-i", audio_path,
                "-vf", vf
            ]

            # Choose video encoder: test NVENC if requested
            if use_hardware_accel:
                cmd.extend(["-c:v", "h264_nvenc", "-preset", "p4", "-cq", "22", "-b:v", "8M"])
            else:
                cmd.extend(["-c:v", "libx264", "-preset", "veryfast", "-crf", "20"])

            cmd.extend([
                "-c:a", "aac", "-b:a", "192k",
                "-shortest",
                output_path
            ])

            log_info(f"[TimelineAligner] Executing FFmpeg video render: {' '.join(cmd)}")

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
                startupinfo=startupinfo,
                bufsize=1
            )

            with self._lock:
                self._current_process = proc

            time_regex = re.compile(r"time=(\d+):(\d+):(\d+\.?\d*)")

            for line in proc.stderr:
                if self._is_cancelled:
                    proc.terminate()
                    raise InterruptedError("Video rendering cancelled by user.")

                t_match = time_regex.search(line)
                if t_match and progress_callback:
                    hours = int(t_match.group(1))
                    mins = int(t_match.group(2))
                    secs = float(t_match.group(3))
                    cur_time = hours * 3600 + mins * 60 + secs
                    pct = 10.0 + min(88.0, (cur_time / max(1.0, total_audio_dur)) * 88.0)
                    progress_callback(
                        round(pct, 1),
                        f"Rendering timeline video ({cur_time:.1f}s / {total_audio_dur:.1f}s)..."
                    )

            proc.wait()

            # If NVENC failed (e.g. driver mismatch), retry with software libx264
            if proc.returncode != 0 and use_hardware_accel and not self._is_cancelled:
                log_info("[TimelineAligner] NVENC render exited non-zero, retrying with CPU libx264...")
                return self.render_video(
                    aligned_images=aligned_images,
                    audio_path=audio_path,
                    output_path=output_path,
                    width=width,
                    height=height,
                    fps=fps,
                    use_hardware_accel=False,
                    progress_callback=progress_callback
                )

            if proc.returncode != 0 and not self._is_cancelled:
                raise RuntimeError(f"FFmpeg video render failed with exit code {proc.returncode}")

        finally:
            with self._lock:
                self._current_process = None
            try:
                if os.path.exists(manifest_path):
                    os.remove(manifest_path)
                if os.path.exists(temp_dir):
                    os.rmdir(temp_dir)
            except Exception:
                pass

        if self._is_cancelled:
            if os.path.exists(output_path):
                try:
                    os.remove(output_path)
                except Exception:
                    pass
            raise InterruptedError("Video rendering cancelled by user.")

        if progress_callback:
            progress_callback(100.0, "Timeline video generated successfully!")

        file_size = os.path.getsize(output_path)
        size_str = f"{file_size / (1024 * 1024):.2f} MB" if file_size >= 1024 * 1024 else f"{file_size / 1024:.1f} KB"

        return {
            'path': output_path,
            'filename': os.path.basename(output_path),
            'size_bytes': file_size,
            'size_formatted': size_str,
            'duration': total_audio_dur,
            'duration_formatted': format_seconds_to_time(total_audio_dur),
            'image_count': len(aligned_images),
            'resolution': f"{width}x{height}",
            'fps': fps
        }

    def export_csv_cue_sheet(self, aligned_images: List[Dict[str, Any]], export_path: str):
        """Exports timeline markers as a CSV cue sheet for DaVinci Resolve / Premiere."""
        with open(export_path, "w", encoding="utf-8") as f:
            f.write("Index,Filename,Start Time,End Time,Duration (s),File Path\n")
            for item in aligned_images:
                f.write(
                    f"{item['index'] + 1},\"{item['filename']}\",{item['start_formatted']},"
                    f"{item['end_formatted']},{item['duration']:.2f},\"{item['path']}\"\n"
                )
        return export_path
