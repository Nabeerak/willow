#!/usr/bin/env python3
"""
Filler Audio Generation Script for Willow Behavioral Framework

Generates 5 filler audio WAV files used to mask latency during Tier 3/4 processing:
- hmm.wav: Tier 3 manipulation detection
- aah.wav: Tier 4 truth conflict
- right_so.wav: Emotional spike
- interesting.wav: New tactic flagged
- cool_but.wav: Engagement drop

Audio Specifications:
- Duration: 200-500ms each
- Sample rate: 16kHz
- Bit depth: 16-bit
- Channels: Mono

Implementation tries in order:
1. pyttsx3 (offline TTS)
2. gTTS (Google TTS - requires internet)
3. wave module (generates tone placeholders)
4. Silent WAV placeholders (fallback)
"""

import os
import sys
import struct
import wave
import math
from pathlib import Path
from typing import Optional, Tuple, Dict

# Constants
SAMPLE_RATE = 24000  # 16kHz
BIT_DEPTH = 16  # 16-bit
CHANNELS = 1  # Mono
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "filler_audio"

# Filler audio configurations: filename -> (text, duration_ms, tier_trigger)
FILLER_CONFIGS: Dict[str, Tuple[str, int, str]] = {
    "hmm.wav": ("Hmm", 400, "Tier 3 manipulation detection"),
    "aah.wav": ("Aah", 300, "Tier 4 truth conflict"),
    "right_so.wav": ("Right, so", 450, "Emotional spike"),
    "interesting.wav": ("Interesting", 500, "New tactic flagged"),
    "cool_but.wav": ("Cool, but", 400, "Engagement drop"),
}


def get_wav_duration_ms(filepath: Path) -> Optional[float]:
    """Get duration of a WAV file in milliseconds."""
    try:
        with wave.open(str(filepath), "rb") as wav_file:
            frames = wav_file.getnframes()
            rate = wav_file.getframerate()
            duration_ms = (frames / rate) * 1000
            return duration_ms
    except Exception as e:
        print(f"  Warning: Could not read WAV duration: {e}")
        return None


def verify_wav_specs(filepath: Path) -> bool:
    """Verify WAV file meets specifications."""
    try:
        with wave.open(str(filepath), "rb") as wav_file:
            channels = wav_file.getnchannels()
            sample_width = wav_file.getsampwidth()  # bytes
            framerate = wav_file.getframerate()
            frames = wav_file.getnframes()
            duration_ms = (frames / framerate) * 1000

            issues = []
            if channels != CHANNELS:
                issues.append(f"channels={channels} (expected {CHANNELS})")
            if sample_width != BIT_DEPTH // 8:
                issues.append(f"bit_depth={sample_width * 8} (expected {BIT_DEPTH})")
            if framerate != SAMPLE_RATE:
                issues.append(f"sample_rate={framerate} (expected {SAMPLE_RATE})")
            if duration_ms < 200 or duration_ms > 500:
                issues.append(f"duration={duration_ms:.0f}ms (expected 200-500ms)")

            if issues:
                print(f"  Warning: {', '.join(issues)}")
                return False
            return True
    except Exception as e:
        print(f"  Error verifying WAV: {e}")
        return False


def generate_tone_wav(filepath: Path, duration_ms: int, frequency: float = 220.0) -> bool:
    """
    Generate a simple sine wave tone as a WAV file.
    Uses the wave module (standard library) - no external dependencies.
    """
    try:
        num_samples = int(SAMPLE_RATE * duration_ms / 1000)

        # Generate sine wave samples
        samples = []
        for i in range(num_samples):
            # Sine wave with fade in/out envelope
            t = i / SAMPLE_RATE
            envelope = 1.0

            # Fade in (first 50ms)
            fade_samples = int(SAMPLE_RATE * 0.05)
            if i < fade_samples:
                envelope = i / fade_samples
            # Fade out (last 50ms)
            elif i > num_samples - fade_samples:
                envelope = (num_samples - i) / fade_samples

            # Generate sample with envelope
            sample = int(32767 * 0.5 * envelope * math.sin(2 * math.pi * frequency * t))
            samples.append(sample)

        # Write WAV file
        with wave.open(str(filepath), "wb") as wav_file:
            wav_file.setnchannels(CHANNELS)
            wav_file.setsampwidth(BIT_DEPTH // 8)  # 2 bytes for 16-bit
            wav_file.setframerate(SAMPLE_RATE)

            # Pack samples as signed 16-bit integers
            packed_samples = struct.pack(f"<{len(samples)}h", *samples)
            wav_file.writeframes(packed_samples)

        return True
    except Exception as e:
        print(f"  Error generating tone: {e}")
        return False


def generate_silent_wav(filepath: Path, duration_ms: int) -> bool:
    """
    Generate a silent WAV file as a fallback placeholder.
    """
    try:
        num_samples = int(SAMPLE_RATE * duration_ms / 1000)

        with wave.open(str(filepath), "wb") as wav_file:
            wav_file.setnchannels(CHANNELS)
            wav_file.setsampwidth(BIT_DEPTH // 8)
            wav_file.setframerate(SAMPLE_RATE)

            # Silent samples (all zeros)
            silent_samples = b"\x00" * (num_samples * (BIT_DEPTH // 8))
            wav_file.writeframes(silent_samples)

        return True
    except Exception as e:
        print(f"  Error generating silent WAV: {e}")
        return False


def try_pyttsx3_generation(text: str, filepath: Path, duration_ms: int) -> bool:
    """
    Try to generate audio using pyttsx3 (offline TTS).
    Returns True if successful, False otherwise.
    """
    try:
        import pyttsx3
        import tempfile

        engine = pyttsx3.init()

        # Configure voice properties
        engine.setProperty("rate", 150)  # Slower for clearer filler sounds

        # pyttsx3 saves to file directly
        engine.save_to_file(text, str(filepath))
        engine.runAndWait()

        # Verify the file was created and is not empty
        if filepath.exists():
            if filepath.stat().st_size > 0 and verify_wav_specs(filepath):
                print(f"  Generated with pyttsx3")
                return True
            else:
                # Remove invalid/empty file
                filepath.unlink()
        return False
    except ImportError:
        return False
    except Exception as e:
        if filepath.exists():
            filepath.unlink()
        print(f"  pyttsx3 failed: {e}")
        return False


def try_gtts_generation(text: str, filepath: Path, duration_ms: int) -> bool:
    """
    Try to generate audio using gTTS (Google Text-to-Speech).
    Requires internet connection.
    Returns True if successful, False otherwise.
    """
    try:
        from gtts import gTTS
        import tempfile

        # gTTS generates MP3, we need to convert to WAV
        # This is complex without additional dependencies, so we skip if pydub not available
        try:
            from pydub import AudioSegment
        except ImportError:
            return False

        # Generate MP3 to temp file
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp_path = tmp.name

        tts = gTTS(text=text, lang="en")
        tts.save(tmp_path)

        # Convert to WAV with correct specs
        audio = AudioSegment.from_mp3(tmp_path)
        audio = audio.set_frame_rate(SAMPLE_RATE)
        audio = audio.set_channels(CHANNELS)
        audio = audio.set_sample_width(BIT_DEPTH // 8)

        # Trim to target duration if needed
        if len(audio) > duration_ms:
            audio = audio[:duration_ms]

        audio.export(str(filepath), format="wav")

        # Clean up temp file
        os.unlink(tmp_path)

        print(f"  Generated with gTTS + pydub")
        return True
    except ImportError:
        return False
    except Exception as e:
        print(f"  gTTS failed: {e}")
        return False


def generate_filler_audio(filename: str, text: str, duration_ms: int, tier_trigger: str) -> bool:
    """
    Generate a single filler audio file using the best available method.
    """
    filepath = OUTPUT_DIR / filename

    print(f"\nGenerating {filename} ({tier_trigger})...")

    # Check if file already exists
    if filepath.exists():
        print(f"  File already exists, verifying...")
        if verify_wav_specs(filepath):
            duration = get_wav_duration_ms(filepath)
            print(f"  Skipping (valid file, {duration:.0f}ms)")
            return True
        else:
            print(f"  Existing file does not meet specs, regenerating...")

    # Try TTS methods in order of preference
    success = False

    # 1. Try pyttsx3 (offline TTS)
    if not success:
        success = try_pyttsx3_generation(text, filepath, duration_ms)

    # 2. Try gTTS (requires internet + pydub)
    if not success:
        success = try_gtts_generation(text, filepath, duration_ms)

    # 3. Generate tone placeholder using wave module
    if not success:
        print(f"  TTS not available, generating tone placeholder...")
        # Use different frequencies for different fillers
        freq_map = {
            "hmm.wav": 180.0,      # Lower hum
            "aah.wav": 220.0,      # Mid tone
            "right_so.wav": 260.0, # Slightly higher
            "interesting.wav": 300.0,
            "cool_but.wav": 240.0,
        }
        frequency = freq_map.get(filename, 220.0)
        success = generate_tone_wav(filepath, duration_ms, frequency)
        if success:
            print(f"  Generated tone placeholder ({frequency}Hz)")

    # 4. Fallback: silent WAV placeholder
    if not success:
        print(f"  Tone generation failed, creating silent placeholder...")
        success = generate_silent_wav(filepath, duration_ms)
        if success:
            print(f"  Generated silent placeholder")

    # Verify final result
    if success and filepath.exists():
        duration = get_wav_duration_ms(filepath)
        if duration:
            print(f"  Created: {filepath}")
            print(f"  Duration: {duration:.0f}ms")
            verify_wav_specs(filepath)
            return True

    print(f"  FAILED to generate {filename}")
    return False


def main():
    """Main entry point for filler audio generation."""
    print("=" * 60)
    print("Willow Filler Audio Generator")
    print("=" * 60)
    print(f"\nOutput directory: {OUTPUT_DIR}")
    print(f"Sample rate: {SAMPLE_RATE}Hz")
    print(f"Bit depth: {BIT_DEPTH}-bit")
    print(f"Channels: {'Mono' if CHANNELS == 1 else 'Stereo'}")
    print(f"Target duration: 200-500ms per file")

    # Create output directory if it doesn't exist
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"\nOutput directory ready: {OUTPUT_DIR}")

    # Check available TTS engines
    print("\nChecking available TTS engines...")
    tts_available = []

    try:
        import pyttsx3
        tts_available.append("pyttsx3")
    except ImportError:
        pass

    try:
        from gtts import gTTS
        from pydub import AudioSegment
        tts_available.append("gTTS+pydub")
    except ImportError:
        pass

    if tts_available:
        print(f"  Available: {', '.join(tts_available)}")
    else:
        print("  No TTS engines available, will use tone placeholders")

    # Generate all filler audio files
    print("\n" + "-" * 60)
    print("Generating filler audio files...")
    print("-" * 60)

    results = {}
    for filename, (text, duration_ms, tier_trigger) in FILLER_CONFIGS.items():
        success = generate_filler_audio(filename, text, duration_ms, tier_trigger)
        results[filename] = success

    # Summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)

    success_count = sum(1 for s in results.values() if s)
    total_count = len(results)

    for filename, success in results.items():
        status = "OK" if success else "FAILED"
        filepath = OUTPUT_DIR / filename
        if success and filepath.exists():
            duration = get_wav_duration_ms(filepath)
            size = filepath.stat().st_size
            print(f"  [{status}] {filename}: {duration:.0f}ms, {size} bytes")
        else:
            print(f"  [{status}] {filename}")

    print(f"\nGenerated: {success_count}/{total_count} files")

    if success_count == total_count:
        print("\nAll filler audio files generated successfully!")
        return 0
    else:
        print("\nSome files failed to generate. Check errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
