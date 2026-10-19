import os
import sys
import subprocess

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core.timeline_aligner import TimelineAligner, parse_timestamp_from_filename
from src.core.ffmpeg_utils import get_ffmpeg_path

def run_tests():
    print("Testing timestamp parsing...")
    assert parse_timestamp_from_filename("image-1_00:00.png") == 0.0
    assert parse_timestamp_from_filename("image-2_00:05.jpg") == 5.0
    assert parse_timestamp_from_filename("image-10_01:23.png") == 83.0
    assert parse_timestamp_from_filename("image_1_00:00.png") == 0.0
    assert parse_timestamp_from_filename("00:00.png") == 0.0
    assert parse_timestamp_from_filename("00_05.jpg") == 5.0
    assert parse_timestamp_from_filename("01_23.png") == 83.0
    assert parse_timestamp_from_filename("01:05:20.png") == 3920.0
    assert parse_timestamp_from_filename("00_15_500.png") == 15.5
    assert parse_timestamp_from_filename("scene_02_10.jpg") == 130.0
    assert parse_timestamp_from_filename("image-1_00_00.png") == 0.0
    assert parse_timestamp_from_filename("image-1_00_03_26") == 3.26
    assert parse_timestamp_from_filename("image-1_00_03_26.png") == 3.26
    assert parse_timestamp_from_filename("00_03_26.jpg") == 3.26
    assert parse_timestamp_from_filename("image-2_01_03_26.png") == 63.26
    print("Timestamp parsing tests passed!")

    print("\nTesting alignment calculations...")
    aligner = TimelineAligner()
    images = [
        "C:/images/00_00.png",
        "C:/images/00_05.png",
        "C:/images/00_12.png"
    ]
    audio_dur = 20.0
    aligned = aligner.align_images(images, audio_dur)
    assert len(aligned) == 3
    assert aligned[0]['start_sec'] == 0.0
    assert aligned[0]['end_sec'] == 5.0
    assert aligned[0]['duration'] == 5.0

    assert aligned[1]['start_sec'] == 5.0
    assert aligned[1]['end_sec'] == 12.0
    assert aligned[1]['duration'] == 7.0

    assert aligned[2]['start_sec'] == 12.0
    assert aligned[2]['end_sec'] == 20.0
    assert aligned[2]['duration'] == 8.0
    print("Alignment calculations passed!")

    # Test rendering short video
    print("\nTesting video rendering with FFmpeg...")
    ffmpeg_bin = get_ffmpeg_path()
    test_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scratch_timeline_test'))
    os.makedirs(test_dir, exist_ok=True)

    img1 = os.path.join(test_dir, "00_00_red.png")
    img2 = os.path.join(test_dir, "00_02_blue.png")
    test_audio = os.path.join(test_dir, "test_audio.wav")
    test_video = os.path.join(test_dir, "aligned_output.mp4")

    # Generate 2 solid color images
    subprocess.run([
        ffmpeg_bin, "-y", "-f", "lavfi", "-i", "color=c=red:s=1280x720:d=1",
        "-frames:v", "1", img1
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    subprocess.run([
        ffmpeg_bin, "-y", "-f", "lavfi", "-i", "color=c=blue:s=1280x720:d=1",
        "-frames:v", "1", img2
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Generate 4-second sine tone audio
    subprocess.run([
        ffmpeg_bin, "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=4",
        test_audio
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    aligned_imgs = aligner.align_images([img1, img2], audio_duration=4.0)
    print("Aligned images:", aligned_imgs)

    def on_prog(pct, msg):
        print(f"[{pct:.1f}%] {msg}")

    result = aligner.render_video(
        aligned_images=aligned_imgs,
        audio_path=test_audio,
        output_path=test_video,
        width=1280,
        height=720,
        fps=30,
        use_hardware_accel=True,
        progress_callback=on_prog
    )

    print("\nVideo render complete:")
    print("Output:", result)
    assert os.path.exists(test_video)
    assert result['size_bytes'] > 1000
    print("\nTIMELINE ALIGNER UNIT TESTS PASSED!")

if __name__ == '__main__':
    run_tests()
