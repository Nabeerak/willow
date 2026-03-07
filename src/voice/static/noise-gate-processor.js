/**
 * NoiseGateProcessor — AudioWorklet processor for client-side noise gating.
 *
 * Threshold is configurable via processorOptions.threshold_dbfs (T024, FR-009).
 * Falls back to -50 dBFS if not provided.
 *
 * Supports flush command (T025, FR-010): when the main thread sends
 * {type: 'flush', fade_duration_ms: N}, the processor applies a linear
 * fade-out over N milliseconds then closes the gate. This prevents audible
 * clicks/pops at waveform peaks when Tier 4 hard-cuts the audio stream.
 *
 * Runs on the audio rendering thread — unaffected by tab backgrounding.
 *
 * Feature: 002-gemini-audio-opt (User Story 1 + Phase 9 Audio Hardening)
 */
class NoiseGateProcessor extends AudioWorkletProcessor {
  constructor(options) {
    super(options);

    // T024 / FR-009: Read threshold_dbfs from processor options, fall back to -50 dBFS.
    // Convert dBFS to linear float32: threshold = 10^(dBFS/20)
    const thresholdDbfs = options?.processorOptions?.threshold_dbfs ?? -50.0;
    this._threshold = Math.pow(10, thresholdDbfs / 20);

    // 200ms hold in samples, computed once at construction
    this._holdDurationSamples = Math.round(0.200 * sampleRate);
    this._holdSamplesRemaining = 0;
    this._gateOpen = false;

    // Fade-out state machine (T025, FR-010)
    // When a flush command arrives, we fade audio to zero over _fadeTotalSamples
    // using a linear ramp, then close the gate. This prevents the audible click
    // that occurs when audio is cut at a non-zero waveform value.
    this._fadingOut = false;
    this._fadeTotalSamples = 0;
    this._fadeSamplesRemaining = 0;

    // Listen for control messages from main thread (T025)
    this.port.onmessage = (event) => {
      const msg = event.data;
      if (msg.type === 'flush') {
        // Start fade-out: convert ms to samples
        // Default 7ms at 48kHz = 336 samples — enough to avoid pops
        const durationMs = msg.fade_duration_ms || 7;
        this._fadeTotalSamples = Math.round((durationMs / 1000) * sampleRate);
        this._fadeSamplesRemaining = this._fadeTotalSamples;
        this._fadingOut = true;
      }
    };
  }

  process(inputs, outputs, parameters) {
    const inChannel = inputs[0]?.[0];
    const outChannel = outputs[0]?.[0];
    if (!inChannel || !outChannel) return true;

    const blockSize = inChannel.length; // 128 samples per block

    // === Fade-out path (T025) ===
    // When fading, apply per-sample linear ramp regardless of gate state.
    // Once fade completes, close gate and silence output.
    if (this._fadingOut) {
      for (let i = 0; i < blockSize; i++) {
        if (this._fadeSamplesRemaining > 0) {
          // Linear ramp: gain goes from current position to 0
          const gain = this._fadeSamplesRemaining / this._fadeTotalSamples;
          outChannel[i] = inChannel[i] * gain;
          this._fadeSamplesRemaining--;
        } else {
          // Fade complete — output silence
          outChannel[i] = 0;
        }
      }

      if (this._fadeSamplesRemaining <= 0) {
        // Fade finished — close gate, clear fade state
        this._fadingOut = false;
        this._gateOpen = false;
        this._holdSamplesRemaining = 0;
      }

      return true;
    }

    // === Normal gate path ===

    // Compute RMS energy for this block
    let sumSq = 0;
    for (let i = 0; i < blockSize; i++) {
      sumSq += inChannel[i] * inChannel[i];
    }
    const rms = Math.sqrt(sumSq / blockSize);

    // Gate logic with hold timer
    if (rms >= this._threshold) {
      // Speech detected — open gate, reset hold
      this._gateOpen = true;
      this._holdSamplesRemaining = this._holdDurationSamples;
    } else if (this._holdSamplesRemaining > 0) {
      // Below threshold but still in hold period — keep gate open
      this._holdSamplesRemaining = Math.max(0, this._holdSamplesRemaining - blockSize);
      this._gateOpen = true;
    } else {
      // Below threshold and hold expired — close gate
      this._gateOpen = false;
    }

    // Copy input to output only when gate is open
    // Output buffer is pre-zeroed by browser — silence is automatic when closed
    if (this._gateOpen) {
      for (let i = 0; i < blockSize; i++) {
        outChannel[i] = inChannel[i];
      }
    }

    return true; // Keep processor alive
  }
}

registerProcessor('noise-gate-processor', NoiseGateProcessor);
