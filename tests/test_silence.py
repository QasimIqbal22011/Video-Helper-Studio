import os
import sys
import subprocess

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.core.ffmpeg_utils import get_ffmpeg_path, get_audio_info
from src.core.silence_remover import AudioSilenceRemover

def test_silence():
    ffmpeg_bin = get_ffmpeg_path()
    test_dir = os.path.join(BASE_DIR, "scratch_test_silence")
    os.makedirs(test_dir, exist_ok=True)

    test_input = os.path.join(test_dir, "speech_with_silence.wav")
    test_output = os.path.join(test_dir, "silence_removed.mp3")

    # Generate: 2s tone (440Hz), 2s silence, 2s tone (880Hz) = total 6s
    filter_graph = "sine=f=440:d=2[s1];aevalsrc=0:d=2[silence];sine=f=880:d=2[s2];[s1][silence][s2]concat=n=3:v=0:a=1"
    subprocess.run([ffmpeg_bin, "-y", "-f", "lavfi", "-i", filter_graph, test_input], check=True, capture_output=True)

    in_info = get_audio_info(test_input)
    print(f"Created test audio: duration={in_info['duration']}s")

    remover = AudioSilenceRemover()

    def prog(pct, msg):
        print(f"[{pct:5.1f}%] {msg}")

    # Detect silences
    silences, dur = remover.detect_silence_intervals(test_input, threshold_db=-35.0, min_duration_sec=0.5, progress_callback=prog)
    print(f"Detected {len(silences)} silence(s):", silences)

    # Remove silences
    res = remover.remove_silences(
        file_path=test_input,
        output_path=test_output,
        threshold_db=-35.0,
        min_duration_sec=0.5,
        margin_ms=80.0,
        normalize_audio=True,
        progress_callback=prog
    )

    print("\nSilence Removal Result:")
    print(f"Original Duration: {res['original_duration_formatted']}")
    print(f"Trimmed Duration:  {res['trimmed_duration_formatted']}")
    print(f"Time Saved:        {res['time_saved_sec']}s ({res['time_saved_percent']}%)")
    print(f"Silences Cut:      {res['silence_count']}")
    print(f"Output File:       {res['output_info']['filename']} ({res['output_info']['size_formatted']})")

    # Cleanup
    for f in [test_input, test_output]:
        if os.path.exists(f):
            try: os.remove(f)
            except Exception: pass
    try: os.rmdir(test_dir)
    except Exception: pass

    assert res['silence_count'] >= 1
    assert res['trimmed_duration'] < in_info['duration']
    print("\nSILENCE REMOVAL TEST PASSED PERFECTLY!")

if __name__ == '__main__':
    test_silence()
