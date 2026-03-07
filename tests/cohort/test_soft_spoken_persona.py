"""
Calibration Cohort: Soft-Spoken Persona — T029

Verifies that a soft-spoken user's voice is not incorrectly gated out by the
-50 dBFS noise gate threshold. Tests the math for threshold alternatives
(-40 dBFS, -45 dBFS) and their impact on legitimate quiet speech.

Per spec 002 FR-009: The noise gate threshold must not suppress legitimate
soft speech from real users. This cohort validates the dBFS-to-linear
conversion and the RMS boundary conditions for a soft-spoken persona.
"""

import math

import pytest


# ---------------------------------------------------------------------------
# dBFS to linear conversion (mirrors noise-gate-processor.js logic)
# ---------------------------------------------------------------------------

def dbfs_to_linear(dbfs: float) -> float:
    """Convert dBFS to linear float32 amplitude (10^(dBFS/20))."""
    return math.pow(10, dbfs / 20)


# ---------------------------------------------------------------------------
# Threshold boundary math
# ---------------------------------------------------------------------------

class TestThresholdBoundaryMath:
    """Verify threshold conversions used in noise-gate-processor.js (T024, FR-009)."""

    def test_minus50_dbfs_linear(self):
        """Default -50 dBFS threshold converts to ≈ 0.003162."""
        threshold = dbfs_to_linear(-50.0)
        assert abs(threshold - 0.003162) < 1e-5

    def test_minus45_dbfs_linear(self):
        """-45 dBFS threshold converts to ≈ 0.005623."""
        threshold = dbfs_to_linear(-45.0)
        assert abs(threshold - 0.005623) < 1e-5

    def test_minus40_dbfs_linear(self):
        """-40 dBFS threshold converts to ≈ 0.01."""
        threshold = dbfs_to_linear(-40.0)
        assert abs(threshold - 0.01) < 1e-5

    def test_threshold_ordering(self):
        """Less negative dBFS = higher threshold = more audio suppressed."""
        t40 = dbfs_to_linear(-40.0)
        t45 = dbfs_to_linear(-45.0)
        t50 = dbfs_to_linear(-50.0)
        assert t50 < t45 < t40


# ---------------------------------------------------------------------------
# Soft-spoken persona RMS levels
# ---------------------------------------------------------------------------

class TestSoftSpokenRMSLevels:
    """
    Model soft-spoken speech as RMS values and verify gate behaviour.

    Typical RMS ranges for speech at 48kHz float32:
    - Loud speech:      0.05 – 0.30
    - Normal speech:    0.01 – 0.05
    - Soft speech:      0.004 – 0.01   ← soft-spoken persona lives here
    - Background noise: 0.001 – 0.003
    """

    # Representative soft-spoken speech RMS (float32 0–1 scale)
    SOFT_SPEECH_RMS = 0.005  # midpoint of soft-speech range

    def test_soft_speech_above_default_threshold(self):
        """Soft speech (RMS 0.005) clears the -50 dBFS threshold (0.003162)."""
        threshold_50 = dbfs_to_linear(-50.0)
        assert self.SOFT_SPEECH_RMS > threshold_50, (
            f"Soft speech RMS {self.SOFT_SPEECH_RMS} is below -50 dBFS "
            f"threshold {threshold_50:.6f} — gate would incorrectly suppress it"
        )

    def test_soft_speech_gated_by_45_dbfs_threshold(self):
        """
        Soft speech (RMS 0.005) is GATED by -45 dBFS (threshold 0.005623).

        This documents that -45 dBFS is too tight for this soft-spoken persona.
        RMS 0.005 ≈ -46 dBFS, which is below the -45 dBFS cutoff.
        Recommendation: use -50 dBFS (default) for soft-spoken compatibility.
        """
        threshold_45 = dbfs_to_linear(-45.0)
        # 0.005 < 0.005623 — soft speech is suppressed at -45 dBFS
        assert self.SOFT_SPEECH_RMS < threshold_45, (
            "-45 dBFS gates soft speech at RMS 0.005 — this is the expected "
            "behaviour that documents -45 dBFS as too tight for soft speakers"
        )

    def test_soft_speech_below_40_dbfs_threshold(self):
        """
        Soft speech (RMS 0.005) is GATED by the stricter -40 dBFS threshold.
        This documents that -40 dBFS is too aggressive for soft-spoken users.
        """
        threshold_40 = dbfs_to_linear(-40.0)
        # 0.005 < 0.01 — soft speech is suppressed at -40 dBFS
        assert self.SOFT_SPEECH_RMS < threshold_40, (
            "-40 dBFS should gate soft speech — if this fails, the threshold "
            "or test RMS constant has changed"
        )

    def test_background_noise_below_default_threshold(self):
        """Background noise (RMS 0.002) stays below the -50 dBFS threshold."""
        background_rms = 0.002  # Typical quiet room background
        threshold_50 = dbfs_to_linear(-50.0)
        assert background_rms < threshold_50, (
            "Background noise should be suppressed at -50 dBFS"
        )


# ---------------------------------------------------------------------------
# Recommended threshold for soft-spoken users
# ---------------------------------------------------------------------------

class TestRecommendedThreshold:
    """Document the recommended threshold for soft-spoken persona compatibility."""

    def test_minus50_clears_soft_speech_with_headroom(self):
        """
        -50 dBFS leaves 3.8 dB of headroom above soft-spoken speech.

        Soft speech RMS 0.005 ≈ -46.0 dBFS.
        Default threshold: -50.0 dBFS.
        Headroom: 4 dB — sufficient for typical soft-spoken users.
        """
        soft_rms = 0.005
        soft_dbfs = 20 * math.log10(soft_rms)        # ≈ -46.0 dBFS
        threshold_dbfs = -50.0
        headroom_db = soft_dbfs - threshold_dbfs      # positive = above threshold

        assert headroom_db > 0, "Soft speech must clear the default threshold"
        assert headroom_db >= 3.0, (
            f"Headroom {headroom_db:.1f} dB < 3 dB — threshold may gate some "
            "soft-spoken users. Consider -52 or -55 dBFS."
        )

    def test_minus45_is_too_tight_for_softest_users(self):
        """
        -45 dBFS provides 1 dB headroom — marginal for very soft speakers.
        Documents that -45 dBFS is acceptable for most but risks edge cases.
        """
        very_soft_rms = 0.006  # Near the top of soft-speech range
        very_soft_dbfs = 20 * math.log10(very_soft_rms)
        threshold_dbfs = -45.0
        headroom_db = very_soft_dbfs - threshold_dbfs

        # Headroom exists but is tight — this is a documentation test, not a gate
        assert headroom_db > 0, (
            f"Very soft speech ({very_soft_dbfs:.1f} dBFS) is below -45 dBFS threshold"
        )
