#!/usr/bin/env python3
"""
Filler Audio Generation Script for Willow Behavioral Framework

Generates per-voice filler WAV files used to mask Tier 3/4 processing latency.
Voice assignment matches ZONE_VOICE_MAP in gemini_live.py:
  - Leda   (neutral_m) — all 5 clips
  - Kore   (low_m)     — hmm, aah
  - Zephyr (high_m)    — hmm, interesting, right_so

Output filenames: {Voice}_{clip}.wav  (e.g. Leda_hmm.wav, Kore_hmm.wav)

Audio Specifications:
- Sample rate: 24kHz
- Bit depth: 16-bit
- Channels: Mono

Generation order (per clip):
1. Gemini TTS (google-genai SDK — matches actual conversation voice)
2. Tone placeholder (wave module — no external deps)
3. Silent WAV placeholder (last resort)
"""

import os
import struct
import sys
import wave
import math
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
load_dotenv()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SAMPLE_RATE = 24000
BIT_DEPTH = 16
CHANNELS = 1
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "filler_audio"

# Clip text and max duration per clip name.
# Durations are generous — filler gets cancelled by _on_audio_chunk when
# Gemini responds, so clips don't need to be tight. Too-short clips get
# cut mid-syllable and sound broken.
CLIP_CONFIGS: dict[str, tuple[str, int]] = {
    "hmm":         ("Hmmm.",          1000),
    "aah":         ("Aah.",            800),
    "right_so":    ("Right, so.",     1500),
    "interesting": ("Interesting.",   1500),
    "cool_but":    ("Cool, but.",     1500),
}

# Which clips to generate for each voice
VOICE_FILLER_MAP: dict[str, list[str]] = {
    "Leda":   ["hmm", "aah", "right_so", "interesting", "cool_but"],
    "Kore":   ["hmm", "aah"],
    "Zephyr": ["hmm", "interesting", "right_so"],
}

# Frequencies for tone placeholders (one per clip)
_TONE_FREQ: dict[str, float] = {
    "hmm":         180.0,
    "aah":         220.0,
    "right_so":    260.0,
    "interesting": 300.0,
    "cool_but":    240.0,
}


# ---------------------------------------------------------------------------
# WAV utilities
# ---------------------------------------------------------------------------

def get_wav_duration_ms(filepath: Path) -> Optional[float]:
    try:
        with wave.open(str(filepath), "rb") as wf:
            return (wf.getnframes() / wf.getframerate()) * 1000
    except Exception:
        return None


def verify_wav_specs(filepath: Path) -> bool:
    try:
        with wave.open(str(filepath), "rb") as wf:
            ok = (
                wf.getnchannels() == CHANNELS
                and wf.getsampwidth() == BIT_DEPTH // 8
                and wf.getframerate() == SAMPLE_RATE
            )
            duration_ms = (wf.getnframes() / wf.getframerate()) * 1000
            if not ok:
                return False
            if duration_ms < 100 or duration_ms > 800:
                return False
            return True
    except Exception:
        return False


def write_pcm_to_wav(filepath: Path, pcm_bytes: bytes) -> None:
    with wave.open(str(filepath), "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(BIT_DEPTH // 8)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm_bytes)


# ---------------------------------------------------------------------------
# Generation methods
# ---------------------------------------------------------------------------

def try_gemini_tts(text: str, voice_name: str, filepath: Path, max_duration_ms: int = 500) -> bool:
    """Generate audio via Gemini TTS API using the specified voice."""
    try:
        from google import genai
        from google.genai import types

        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            print("  Gemini TTS skipped: no API key in environment")
            return False

        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-2.5-flash-preview-tts",
            contents=text,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name=voice_name
                        )
                    )
                ),
            ),
        )

        candidate = response.candidates[0] if response.candidates else None
        if not candidate or not candidate.content or not candidate.content.parts:
            print(f"  Gemini TTS returned empty response for voice={voice_name}")
            return False
        audio_data = candidate.content.parts[0].inline_data.data
        if not audio_data:
            return False

        # Gemini TTS returns raw PCM (L16, 24kHz, mono).
        # Trim to max_duration_ms — TTS often overshoots for short phrases.
        bytes_per_ms = SAMPLE_RATE * (BIT_DEPTH // 8) * CHANNELS // 1000  # 48 bytes/ms
        max_bytes = max_duration_ms * bytes_per_ms
        if len(audio_data) > max_bytes:
            # Fade out last 30ms to avoid click
            fade_bytes = 30 * bytes_per_ms
            audio_data = bytearray(audio_data[:max_bytes])
            import array as _arr
            fade_start = max_bytes - fade_bytes
            samples = _arr.array("h", bytes(audio_data[fade_start:]))
            fade_len = len(samples)
            for i in range(fade_len):
                samples[i] = int(samples[i] * (1.0 - i / fade_len))
            audio_data[fade_start:] = samples.tobytes()
            audio_data = bytes(audio_data)
            print(f"  Trimmed TTS output to {max_duration_ms}ms (was {len(response.candidates[0].content.parts[0].inline_data.data) // bytes_per_ms}ms)")

        write_pcm_to_wav(filepath, audio_data)
        print(f"  Generated with Gemini TTS ({voice_name})")
        return True

    except ImportError:
        print("  Gemini TTS skipped: google-genai not installed")
        return False
    except Exception as exc:
        if filepath.exists():
            filepath.unlink()
        print(f"  Gemini TTS failed: {exc}")
        return False


def generate_tone_wav(filepath: Path, duration_ms: int, frequency: float) -> bool:
    try:
        num_samples = int(SAMPLE_RATE * duration_ms / 1000)
        fade = int(SAMPLE_RATE * 0.05)
        samples = []
        for i in range(num_samples):
            env = 1.0
            if i < fade:
                env = i / fade
            elif i > num_samples - fade:
                env = (num_samples - i) / fade
            samples.append(int(32767 * 0.5 * env * math.sin(
                2 * math.pi * frequency * i / SAMPLE_RATE
            )))
        packed = struct.pack(f"<{len(samples)}h", *samples)
        write_pcm_to_wav(filepath, packed)
        return True
    except Exception as exc:
        print(f"  Tone generation failed: {exc}")
        return False


def generate_silent_wav(filepath: Path, duration_ms: int) -> bool:
    try:
        num_samples = int(SAMPLE_RATE * duration_ms / 1000)
        write_pcm_to_wav(filepath, b"\x00" * num_samples * (BIT_DEPTH // 8))
        return True
    except Exception as exc:
        print(f"  Silent WAV failed: {exc}")
        return False


# ---------------------------------------------------------------------------
# Per-clip orchestration
# ---------------------------------------------------------------------------

def generate_clip(voice_name: str, clip_name: str, force: bool = False) -> bool:
    text, duration_ms = CLIP_CONFIGS[clip_name]
    filename = f"{voice_name}_{clip_name}.wav"
    filepath = OUTPUT_DIR / filename

    print(f"\n  {filename} ...")

    if filepath.exists() and not force:
        if verify_wav_specs(filepath):
            ms = get_wav_duration_ms(filepath)
            print(f"  Skipping (valid, {ms:.0f}ms)")
            return True
        print("  Existing file invalid — regenerating")

    # 1. Gemini TTS (trim to target duration)
    if try_gemini_tts(text, voice_name, filepath, max_duration_ms=duration_ms):
        return True

    # 2. Tone placeholder
    print("  Falling back to tone placeholder")
    freq = _TONE_FREQ.get(clip_name, 220.0)
    if generate_tone_wav(filepath, duration_ms, freq) and verify_wav_specs(filepath):
        print(f"  Generated tone ({freq}Hz)")
        return True

    # 3. Silent placeholder
    print("  Falling back to silent placeholder")
    if generate_silent_wav(filepath, duration_ms):
        print("  Generated silent placeholder")
        return True

    print(f"  FAILED: {filename}")
    return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Generate Willow filler audio clips")
    parser.add_argument("--force", action="store_true", help="Regenerate even if file exists")
    parser.add_argument("--voice", help="Only generate clips for this voice (Leda/Kore/Zephyr)")
    parser.add_argument("--clip", help="Only generate this clip name (hmm/aah/etc)")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Output: {OUTPUT_DIR}  |  {SAMPLE_RATE}Hz, {BIT_DEPTH}-bit, mono")

    voices = [args.voice] if args.voice else list(VOICE_FILLER_MAP.keys())
    results: dict[str, bool] = {}

    for voice in voices:
        if voice not in VOICE_FILLER_MAP:
            print(f"Unknown voice: {voice}. Valid: {list(VOICE_FILLER_MAP)}")
            continue
        clips = [args.clip] if args.clip else VOICE_FILLER_MAP[voice]
        print(f"\n{'='*50}\n{voice}\n{'='*50}")
        for clip in clips:
            if clip not in CLIP_CONFIGS:
                print(f"  Unknown clip: {clip}")
                continue
            key = f"{voice}_{clip}"
            results[key] = generate_clip(voice, clip, force=args.force)

    print(f"\n{'='*50}")
    ok = sum(1 for v in results.values() if v)
    for key, success in results.items():
        tag = "OK" if success else "FAIL"
        fp = OUTPUT_DIR / f"{key}.wav"
        if success and fp.exists():
            ms = get_wav_duration_ms(fp)
            print(f"  [{tag}] {key}.wav  {ms:.0f}ms  {fp.stat().st_size} bytes")
        else:
            print(f"  [{tag}] {key}.wav")
    print(f"\nGenerated: {ok}/{len(results)}")
    return 0 if ok == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
