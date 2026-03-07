"""
Pure Python math verification for noise gate constants.

Feature: 002-gemini-audio-opt (Phase 8)
Task: T020

Verifies:
  - -50 dBFS float32 threshold = 0.003162
  - 200ms hold at 48 kHz = 9600 samples
  - 200ms hold at 16 kHz = 3200 samples
  - 16-bit PCM scale sanity check: round(32768 * 10^(-50/20)) == 104
"""

import math


def test_threshold_dbfs_to_linear():
    """10^(-50/20) should equal 0.003162 within tolerance."""
    threshold = 10 ** (-50 / 20)
    assert abs(threshold - 0.003162) < 1e-6


def test_hold_samples_at_48khz():
    """200ms at 48 kHz = 9600 samples."""
    hold_samples = int(0.200 * 48000)
    assert hold_samples == 9600


def test_hold_samples_at_16khz():
    """200ms at 16 kHz = 3200 samples."""
    hold_samples = int(0.200 * 16000)
    assert hold_samples == 3200


def test_16bit_pcm_scale_sanity():
    """16-bit PCM equivalent of -50 dBFS: round(32768 * 0.003162) == 104."""
    pcm_value = round(32768 * 10 ** (-50 / 20))
    assert pcm_value == 104
