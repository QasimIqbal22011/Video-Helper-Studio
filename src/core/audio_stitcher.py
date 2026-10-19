import os
import sys
import re
import subprocess
import threading
from typing import List, Dict, Any, Optional, Callable
from .ffmpeg_utils import get_ffmpeg_path, get_audio_info

class AudioStitcher:
    """
    High-performance audio stitcher designed for YouTube Automation content creation.
    Concatenates multiple audio files into a unified master audio file with:
    - Customizable pause/gap duration between clips
    - YouTube audio loudness normalization (EBU R128 / loudnorm)
    - Resampling to uniform sample rate (44.1kHz or 48kHz)
    - Multi-format support (MP3, WAV, AAC, M4A, FLAC, OGG)
    - Live progress tracking and graceful cancellation
    """

    def __init__(self):
        self._current_process: Optional[subprocess.Popen] = None
        self._is_cancelled = False
        self._lock = threading.Lock()

    def cancel(self):
        """Cancels an ongoing stitching process."""
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

    def stitch(
        self,
        file_paths: List[str],
        output_path: str,
        gap_sec: float = 0.3,
        normalize_audio: bool = True,
        sample_rate: int = 48000,
        output_format: str = "mp3",
        bitrate_kbps: int = 320,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> Dict[str, Any]:
        """
        Executes the stitching pipeline.
        
        Args:
            file_paths: Ordered list of absolute paths to audio files
            output_path: Target destination path for master audio
            gap_sec: Duration in seconds to insert between clips (e.g. 0.3s)
            normalize_audio: If True, applies YouTube standard EBU R128 loudnorm
            sample_rate: Output sample rate (44100 or 48000)
            output_format: 'mp3', 'wav', 'm4a', 'aac', or 'flac'
            bitrate_kbps: Audio bitrate for lossy formats (e.g. 320 or 192)
            progress_callback: callback(percent_0_to_100, status_message)
            
        Returns:
            dict with metadata of the output file
        """
        self._is_cancelled = False
        
        if not file_paths:
            raise ValueError("No audio files provided for stitching.")
            
        if len(file_paths) == 0:
            raise ValueError("Audio file list is empty.")

        # Ensure output directory exists
        out_dir = os.path.dirname(os.path.abspath(output_path))
        os.makedirs(out_dir, exist_ok=True)

        if progress_callback:
            progress_callback(5.0, "Analyzing audio clips...")

        # Analyze clips & compute total expected duration
        total_clip_duration = 0.0
        clip_infos = []
        for i, fp in enumerate(file_paths):
            if self._is_cancelled:
                raise InterruptedError("Stitching cancelled by user.")
            info = get_audio_info(fp)
            clip_infos.append(info)
            total_clip_duration += info['duration']

        total_gaps = max(0, len(file_paths) - 1) * gap_sec
        total_expected_duration = total_clip_duration + total_gaps
        if total_expected_duration <= 0:
            total_expected_duration = 1.0

        ffmpeg_bin = get_ffmpeg_path()

        # Build FFmpeg command with complex_filter
        cmd = [ffmpeg_bin, "-y", "-hide_banner"]

        # Add all inputs
        for fp in file_paths:
            cmd.extend(["-i", fp])

        # Build filtergraph
        # We resample all inputs to target sample_rate and stereo fltp for seamless concatenation
        filter_parts = []
        concat_inputs = []
        n_elements = 0

        for i in range(len(file_paths)):
            # Normalize format for input i
            norm_label = f"in{i}"
            filter_parts.append(
                f"[{i}:a]aresample={sample_rate},aformat=sample_fmts=fltp:channel_layouts=stereo[{norm_label}]"
            )
            concat_inputs.append(f"[{norm_label}]")
            n_elements += 1

            # If gap > 0 and not the last clip, insert silence segment
            if gap_sec > 0.001 and i < len(file_paths) - 1:
                silence_label = f"gap{i}"
                filter_parts.append(
                    f"anullsrc=r={sample_rate}:cl=stereo,atrim=0:{gap_sec:.3f}[{silence_label}]"
                )
                concat_inputs.append(f"[{silence_label}]")
                n_elements += 1

        # Concat filter
        concat_filter = "".join(concat_inputs) + f"concat=n={n_elements}:v=0:a=1"

        if normalize_audio:
            # YouTube standard loudness normalization: Integrated -16 LUFS, True Peak -1.5 dB, LRA 11
            concat_filter += ",loudnorm=I=-16:TP=-1.5:LRA=11"

        filter_parts.append(concat_filter + "[outa]")
        full_filtergraph = ";".join(filter_parts)

        cmd.extend(["-filter_complex", full_filtergraph, "-map", "[outa]"])

        # Format-specific encoding options
        out_fmt = output_format.lower().replace('.', '')
        if out_fmt == "mp3":
            cmd.extend(["-c:a", "libmp3lame", "-b:a", f"{bitrate_kbps}k"])
        elif out_fmt == "wav":
            cmd.extend(["-c:a", "pcm_s16le"])
        elif out_fmt in ("m4a", "aac"):
            cmd.extend(["-c:a", "aac", "-b:a", f"{bitrate_kbps}k"])
        elif out_fmt == "flac":
            cmd.extend(["-c:a", "flac"])
        else:
            # Default to mp3
            cmd.extend(["-c:a", "libmp3lame", "-b:a", f"{bitrate_kbps}k"])

        cmd.extend(["-ar", str(sample_rate)])
        cmd.append(output_path)

        if progress_callback:
            progress_callback(15.0, "Starting audio concatenation & mastering...")

        # Setup Windows process flags
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

        # Read stderr line-by-line to extract time=... progress
        time_regex = re.compile(r"time=(\d+):(\d+):(\d+\.?\d*)")

        try:
            for line in proc.stderr:
                if self._is_cancelled:
                    proc.terminate()
                    raise InterruptedError("Stitching cancelled by user.")

                match = time_regex.search(line)
                if match:
                    hours = int(match.group(1))
                    minutes = int(match.group(2))
                    seconds = float(match.group(3))
                    current_time = hours * 3600 + minutes * 60 + seconds
                    progress_pct = 15.0 + (current_time / total_expected_duration) * 80.0
                    progress_pct = max(15.0, min(96.0, progress_pct))
                    
                    if progress_callback:
                        progress_callback(
                            round(progress_pct, 1),
                            f"Stitching & mastering... ({current_time:.1f}s / {total_expected_duration:.1f}s)"
                        )

            proc.wait()
            if proc.returncode != 0 and not self._is_cancelled:
                raise RuntimeError(f"FFmpeg stitching failed with exit code {proc.returncode}")

        finally:
            with self._lock:
                self._current_process = None

        if self._is_cancelled:
            if os.path.exists(output_path):
                try:
                    os.remove(output_path)
                except Exception:
                    pass
            raise InterruptedError("Stitching cancelled by user.")

        if progress_callback:
            progress_callback(100.0, "Master audio ready!")

        # Retrieve final output file info
        final_info = get_audio_info(output_path)
        return final_info
