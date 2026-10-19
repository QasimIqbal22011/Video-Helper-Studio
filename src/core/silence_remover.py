import os
import sys
import re
import subprocess
import threading
from typing import List, Dict, Any, Optional, Callable, Tuple
from .ffmpeg_utils import get_ffmpeg_path, get_audio_info
from .logger import log_info, log_error

class AudioSilenceRemover:
    """
    Intelligent audio silence and dead-air remover designed for YouTube voiceovers.
    Uses FFmpeg silencedetect to identify unvoiced pauses, merges with safety margin buffers,
    and stitches active speech segments with zero click/pop artifacts.
    """

    def __init__(self):
        self._current_process: Optional[subprocess.Popen] = None
        self._is_cancelled = False
        self._lock = threading.Lock()

    def cancel(self):
        """Cancels an ongoing silence detection or removal job."""
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

    def detect_silence_intervals(
        self,
        file_path: str,
        threshold_db: float = -40.0,
        min_duration_sec: float = 0.4,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> Tuple[List[Dict[str, float]], float]:
        """
        Runs FFmpeg silencedetect on the audio file and returns:
        (list of detected silence intervals [{'start': s, 'end': e, 'duration': d}], total_duration)
        """
        self._is_cancelled = False
        info = get_audio_info(file_path)
        total_duration = info['duration']

        if total_duration <= 0:
            return [], 0.0

        if progress_callback:
            progress_callback(10.0, "Analyzing audio waveform for silences...")

        ffmpeg_bin = get_ffmpeg_path()
        # silencedetect filter
        filter_str = f"silencedetect=noise={threshold_db:.1f}dB:d={min_duration_sec:.2f}"
        cmd = [
            ffmpeg_bin, "-hide_banner", "-i", file_path,
            "-af", filter_str,
            "-f", "null", "-"
        ]

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

        silence_start_regex = re.compile(r"silence_start:\s*(-?\d+\.?\d*)")
        silence_end_regex = re.compile(r"silence_end:\s*(-?\d+\.?\d*)\s*\|\s*silence_duration:\s*(-?\d+\.?\d*)")
        time_regex = re.compile(r"time=(\d+):(\d+):(\d+\.?\d*)")

        silence_intervals = []
        pending_start = None

        try:
            for line in proc.stderr:
                if self._is_cancelled:
                    proc.terminate()
                    raise InterruptedError("Silence detection cancelled by user.")

                # Monitor scan progress
                t_match = time_regex.search(line)
                if t_match and progress_callback:
                    hours = int(t_match.group(1))
                    mins = int(t_match.group(2))
                    secs = float(t_match.group(3))
                    cur_time = hours * 3600 + mins * 60 + secs
                    pct = 10.0 + min(35.0, (cur_time / max(1.0, total_duration)) * 35.0)
                    progress_callback(round(pct, 1), f"Scanning for dead air ({cur_time:.1f}s / {total_duration:.1f}s)...")

                # Detect start
                start_match = silence_start_regex.search(line)
                if start_match:
                    pending_start = max(0.0, float(start_match.group(1)))

                # Detect end
                end_match = silence_end_regex.search(line)
                if end_match:
                    end_val = min(total_duration, float(end_match.group(1)))
                    dur_val = float(end_match.group(2))
                    start_val = pending_start if pending_start is not None else max(0.0, end_val - dur_val)
                    if end_val > start_val:
                        dur_val = end_val - start_val
                        silence_intervals.append({
                            'start': round(start_val, 3),
                            'end': round(end_val, 3),
                            'duration': round(dur_val, 3),
                            'start_formatted': f"{int(start_val // 60):02d}:{start_val % 60:05.2f}",
                            'end_formatted': f"{int(end_val // 60):02d}:{end_val % 60:05.2f}",
                            'duration_formatted': f"{dur_val:.2f}s"
                        })
                    pending_start = None

            proc.wait()
        finally:
            with self._lock:
                self._current_process = None

        # If silence was ongoing at the very end of file
        if pending_start is not None and pending_start < total_duration:
            dur_val = total_duration - pending_start
            silence_intervals.append({
                'start': round(pending_start, 3),
                'end': round(total_duration, 3),
                'duration': round(dur_val, 3),
                'start_formatted': f"{int(pending_start // 60):02d}:{pending_start % 60:05.2f}",
                'end_formatted': f"{int(total_duration // 60):02d}:{total_duration % 60:05.2f}",
                'duration_formatted': f"{dur_val:.2f}s"
            })

        return silence_intervals, total_duration

    def compute_speech_intervals(
        self,
        silence_intervals: List[Dict[str, float]],
        total_duration: float,
        margin_ms: float = 80.0
    ) -> List[Tuple[float, float]]:
        """
        Inverts silence intervals into voiced speech intervals, applying a safety margin
        so words/breaths are never abruptly clipped.
        """
        margin_sec = max(0.0, margin_ms / 1000.0)

        if not silence_intervals:
            return [(0.0, total_duration)]

        # Sort silence intervals by start
        sorted_silences = sorted(silence_intervals, key=lambda x: x['start'])

        # Invert to speech segments
        raw_speech = []
        cur_pos = 0.0

        for s in sorted_silences:
            s_start = s['start']
            s_end = s['end']

            if s_start > cur_pos:
                raw_speech.append((cur_pos, s_start))
            cur_pos = max(cur_pos, s_end)

        if cur_pos < total_duration:
            raw_speech.append((cur_pos, total_duration))

        if not raw_speech:
            return []

        # Apply buffer margins and merge overlapping segments
        buffered_speech = []
        for start, end in raw_speech:
            # Expand start earlier and end later by margin
            b_start = max(0.0, start - margin_sec)
            b_end = min(total_duration, end + margin_sec)
            buffered_speech.append((b_start, b_end))

        # Merge any overlaps
        merged = []
        for start, end in buffered_speech:
            if not merged:
                merged.append((start, end))
            else:
                last_start, last_end = merged[-1]
                if start <= last_end:
                    merged[-1] = (last_start, max(last_end, end))
                else:
                    merged.append((start, end))

        # Filter out negligible micro-segments (< 0.05s)
        final_segments = [(round(s, 3), round(e, 3)) for s, e in merged if (e - s) >= 0.05]
        return final_segments

    def remove_silences(
        self,
        file_path: str,
        output_path: str,
        threshold_db: float = -40.0,
        min_duration_sec: float = 0.4,
        margin_ms: float = 80.0,
        normalize_audio: bool = True,
        sample_rate: int = 48000,
        output_format: str = "mp3",
        bitrate_kbps: int = 320,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> Dict[str, Any]:
        """
        Full pipeline: detects silences, slices active speech with margins,
        concatenates cleanly, applies optional YouTube loudnorm, and returns results.
        """
        self._is_cancelled = False

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Input file not found: {file_path}")

        # 1. Detect silences
        silences, total_dur = self.detect_silence_intervals(
            file_path=file_path,
            threshold_db=threshold_db,
            min_duration_sec=min_duration_sec,
            progress_callback=progress_callback
        )

        if self._is_cancelled:
            raise InterruptedError("Cancelled by user.")

        total_silence_sec = sum(s['duration'] for s in silences)
        total_silence_count = len(silences)

        # 2. Compute speech segments with safety margin
        speech_segments = self.compute_speech_intervals(silences, total_dur, margin_ms)

        if not speech_segments:
            raise ValueError("All audio was detected as silence. Try raising the threshold or decreasing duration.")

        expected_new_dur = sum(end - start for start, end in speech_segments)
        saved_sec = max(0.0, total_dur - expected_new_dur)
        saved_pct = round((saved_sec / max(0.001, total_dur)) * 100, 1)

        if progress_callback:
            progress_callback(
                50.0,
                f"Found {total_silence_count} pauses ({saved_sec:.1f}s dead air). Trimming..."
            )

        # 3. Build FFmpeg filtergraph to extract and concatenate active speech
        ffmpeg_bin = get_ffmpeg_path()
        out_dir = os.path.dirname(os.path.abspath(output_path))
        os.makedirs(out_dir, exist_ok=True)

        cmd = [ffmpeg_bin, "-y", "-hide_banner", "-i", file_path]

        filter_parts = []
        concat_inputs = []

        for idx, (seg_start, seg_end) in enumerate(speech_segments):
            dur = seg_end - seg_start
            label = f"seg{idx}"
            # atrim, asetpts, and resample
            filter_parts.append(
                f"[0:a]atrim=start={seg_start:.3f}:end={seg_end:.3f},asetpts=PTS-STARTPTS,"
                f"aresample={sample_rate},aformat=sample_fmts=fltp:channel_layouts=stereo[{label}]"
            )
            concat_inputs.append(f"[{label}]")

        concat_filter = "".join(concat_inputs) + f"concat=n={len(speech_segments)}:v=0:a=1"

        if normalize_audio:
            concat_filter += ",loudnorm=I=-16:TP=-1.5:LRA=11"

        filter_parts.append(concat_filter + "[outa]")
        full_filtergraph = ";".join(filter_parts)

        cmd.extend(["-filter_complex", full_filtergraph, "-map", "[outa]"])

        # Output encoding
        out_fmt = output_format.lower().replace('.', '')
        if out_fmt == "mp3":
            cmd.extend(["-c:a", "libmp3lame", "-b:a", f"{bitrate_kbps}k"])
        elif out_fmt == "wav":
            cmd.extend(["-c:a", "pcm_s16le"])
        elif out_fmt in ("m4a", "aac"):
            cmd.extend(["-c:a", "aac", "-b:a", f"{bitrate_kbps}k"])
        else:
            cmd.extend(["-c:a", "libmp3lame", "-b:a", f"{bitrate_kbps}k"])

        cmd.extend(["-ar", str(sample_rate)])
        cmd.append(output_path)

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

        try:
            for line in proc.stderr:
                if self._is_cancelled:
                    proc.terminate()
                    raise InterruptedError("Cancelled by user.")

                t_match = time_regex.search(line)
                if t_match and progress_callback:
                    hours = int(t_match.group(1))
                    mins = int(t_match.group(2))
                    secs = float(t_match.group(3))
                    cur_time = hours * 3600 + mins * 60 + secs
                    pct = 50.0 + min(46.0, (cur_time / max(0.1, expected_new_dur)) * 46.0)
                    progress_callback(round(pct, 1), f"Rendering tight master track ({cur_time:.1f}s / {expected_new_dur:.1f}s)...")

            proc.wait()
            if proc.returncode != 0 and not self._is_cancelled:
                raise RuntimeError(f"FFmpeg silence removal failed with exit code {proc.returncode}")

        finally:
            with self._lock:
                self._current_process = None

        if self._is_cancelled:
            if os.path.exists(output_path):
                try:
                    os.remove(output_path)
                except Exception:
                    pass
            raise InterruptedError("Silence removal cancelled by user.")

        if progress_callback:
            progress_callback(100.0, "Voiceover tightened and ready!")

        final_info = get_audio_info(output_path)

        return {
            'output_info': final_info,
            'path': final_info['path'],
            'filename': final_info['filename'],
            'duration': final_info['duration'],
            'duration_formatted': final_info['duration_formatted'],
            'size_bytes': final_info['size_bytes'],
            'size_formatted': final_info['size_formatted'],
            'format_name': final_info['format_name'],
            'sample_rate': final_info['sample_rate'],
            'original_duration': total_dur,
            'original_duration_formatted': f"{int(total_dur // 60):02d}:{int(total_dur % 60):02d}",
            'trimmed_duration': final_info['duration'],
            'trimmed_duration_formatted': final_info['duration_formatted'],
            'silence_count': total_silence_count,
            'silence_removed_sec': round(saved_sec, 2),
            'time_saved_sec': round(saved_sec, 2),
            'percent_saved': saved_pct,
            'time_saved_percent': saved_pct,
            'silence_segments': silences[:100]  # First 100 silence intervals for telemetry UI
        }
