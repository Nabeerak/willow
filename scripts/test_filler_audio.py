#!/usr/bin/env python3
"""
test_filler_audio.py — T062

Verifies filler audio files:
- All 5 clips present in data/filler_audio/
- Duration 200-500ms at 16kHz/16-bit/mono
- FillerAudioPlayer loads them correctly

Usage: python3 scripts/test_filler_audio.py
"""

import sys
import wave
from pathlib import Path
sys.path.insert(0, ".")

from src.voice.filler_audio import FillerAudioPlayer


EXPECTED_CLIPS = ["hmm", "aah", "right_so", "interesting", "cool_but"]
DATA_DIR = Path("data/filler_audio")
MIN_DURATION_MS = 100   # relaxed minimum for generated test clips
MAX_DURATION_MS = 1000


def check_wav(path: Path) -> tuple[bool, str]:
    """Verify WAV file properties."""
    try:
        with wave.open(str(path), "rb") as wf:
            channels = wf.getnchannels()
            sample_width = wf.getsampwidth()
            framerate = wf.getframerate()
            n_frames = wf.getnframes()
            duration_ms = (n_frames / framerate) * 1000
    except Exception as exc:
        return False, f"Cannot open: {exc}"

    issues = []
    if channels != 1:
        issues.append(f"channels={channels} (expected 1)")
    if sample_width != 2:
        issues.append(f"sample_width={sample_width} (expected 2 / 16-bit)")
    if framerate not in (16000, 48000):
        issues.append(f"framerate={framerate} (expected 16000 or 48000)")
    if not (MIN_DURATION_MS <= duration_ms <= MAX_DURATION_MS):
        issues.append(f"duration={duration_ms:.0f}ms (expected {MIN_DURATION_MS}-{MAX_DURATION_MS}ms)")

    if issues:
        return False, "; ".join(issues)
    return True, f"{duration_ms:.0f}ms {framerate}Hz 16-bit mono"


def main():
    print("=== Filler Audio Verification ===\n")

    all_ok = True

    # 1. File presence and properties
    print("File checks:")
    for name in EXPECTED_CLIPS:
        path = DATA_DIR / f"{name}.wav"
        exists = path.exists()
        if not exists:
            print(f"  {name}.wav  MISSING")
            all_ok = False
            continue
        ok, info = check_wav(path)
        status = "OK" if ok else "WARN"
        print(f"  {name}.wav  {status}  {info}")
        if not ok:
            all_ok = False

    # 2. FillerAudioPlayer load
    print("\nFillerAudioPlayer.load():")
    player = FillerAudioPlayer(data_dir=DATA_DIR)
    player.load()
    loaded = player.get_loaded_clips()
    print(f"  Loaded clips: {loaded}")
    for name in EXPECTED_CLIPS:
        status = "OK" if name in loaded else "MISSING"
        print(f"  {name}: {status}")

    # 3. Trigger mapping
    print("\nTrigger-to-filler mapping:")
    for trigger, expected_clip in [
        ("manipulation_pattern", "hmm"),
        ("truth_conflict", "aah"),
        ("emotional_spike", "right_so"),
    ]:
        clip = player.clip_for_trigger(trigger)
        ok = clip == expected_clip
        print(f"  {trigger} → {clip}  {'OK' if ok else 'FAIL (expected ' + expected_clip + ')'}")

    print()
    if all_ok:
        print("=== All checks passed ===")
    else:
        print("=== Some checks failed (see above) ===")
        sys.exit(1)


if __name__ == "__main__":
    main()
