/**
 * Audio Capture — Main-thread setup for noise-gated microphone input.
 *
 * Initializes getUserMedia with echo cancellation, loads the NoiseGateProcessor
 * AudioWorklet, and returns a gated MediaStream suitable for Gemini Live streaming.
 *
 * T024: Passes NoiseGateConfig.threshold_dbfs as processorOptions to the
 * AudioWorklet so the threshold is configurable without touching JS (FR-009).
 *
 * T025: Exports handleServerCommand() for the browser WebSocket client to forward
 * flush_audio_buffer commands to the AudioWorklet processor.
 *
 * T026: Implements adaptive streaming buffer (FR-011). Starts at 1024 samples,
 * drops to 512 after 30 seconds of stable operation (no underruns detected).
 *
 * T028: Implements 3-second pre-flight warmup. During warmup the noise gate runs
 * (allowing hardware buffers to settle) but onPreflightStart/onPreflightEnd
 * callbacks notify the caller so Tier 4 is suppressed on the Python side.
 *
 * Feature: 002-gemini-audio-opt (User Story 1 + Phase 9 Audio Hardening)
 */

/**
 * Initialize noise-gated audio capture pipeline.
 *
 * Audio graph: getUserMedia (mic) → AudioWorkletNode (noise gate) → MediaStreamDestination
 *
 * @param {Object} [options]
 * @param {number} [options.thresholdDbfs=-50.0] Gate threshold in dBFS (T024, FR-009)
 * @param {number} [options.bufferSize=1024] Initial streaming buffer in samples (T026, FR-011)
 * @param {number} [options.preflightDurationMs=3000] Pre-flight warmup duration (T028, FR-013)
 * @param {function} [options.onPreflightStart] Called when warmup begins — caller should signal Python
 * @param {function} [options.onPreflightEnd] Called when warmup ends — caller should signal Python
 * @returns {Promise<{audioContext, noiseGateNode, gatedStream, stop, preflightPromise, getBufferSize}>}
 */
export async function initNoiseGate(options = {}) {
  const {
    thresholdDbfs = parseFloat(localStorage.getItem('willow_threshold_dbfs')) || -50.0,
    bufferSize: initialBufferSize = parseInt(localStorage.getItem('willow_buffer_size'), 10) || 1024,
    preflightDurationMs = 3000,
    onPreflightStart = null,
    onPreflightEnd = null,
  } = options;

  // Persist resolved settings for next session
  localStorage.setItem('willow_threshold_dbfs', thresholdDbfs.toString());
  localStorage.setItem('willow_buffer_size', initialBufferSize.toString());

  // Acquire microphone with echo cancellation enabled
  const micStream = await navigator.mediaDevices.getUserMedia({
    audio: {
      echoCancellation: true,    // Browser AEC removes agent audio from mic input
      noiseSuppression: false,   // Our gate handles suppression; browser's can interfere
      autoGainControl: false     // Prevent AGC from boosting quiet audio above threshold
    },
    video: false
  });

  // Create AudioContext
  const audioContext = new AudioContext();

  // Handle autoplay policy — resume if suspended
  if (audioContext.state === 'suspended') {
    await audioContext.resume();
  }

  // Load noise gate AudioWorklet processor
  await audioContext.audioWorklet.addModule('noise-gate-processor.js');

  // T024 / FR-009: Pass threshold_dbfs as processorOptions so the processor
  // reads it at construction time. No JS edit needed to change the threshold.
  const noiseGateNode = new AudioWorkletNode(audioContext, 'noise-gate-processor', {
    processorOptions: {
      threshold_dbfs: thresholdDbfs,
    },
  });
  noiseGateNode.onprocessorerror = (event) => {
    console.error('NoiseGateProcessor error:', event);
  };

  // Create capture destination for gated output
  const captureDestination = audioContext.createMediaStreamDestination();

  // Wire audio graph: mic → noise gate → capture destination
  const micSource = audioContext.createMediaStreamSource(micStream);
  micSource.connect(noiseGateNode);
  noiseGateNode.connect(captureDestination);

  // Visibility change diagnostics (US5: Tab Backgrounding)
  // AudioWorklet runs on a dedicated audio rendering thread and is unaffected
  // by tab visibility. This handler logs state changes for diagnostics only.
  document.addEventListener('visibilitychange', () => {
    console.log(`[audio_capture] Tab visibility: ${document.visibilityState}, AudioContext state: ${audioContext.state}`);
  });

  // T026 / FR-011: Adaptive streaming buffer.
  // Start at initialBufferSize (1024). After 30 seconds of stable operation
  // (zero underruns), drop to 512 for lower latency.
  let currentBufferSize = initialBufferSize;
  let underrunCount = 0;
  let stableStartTime = Date.now();

  const adaptiveBufferInterval = setInterval(() => {
    const elapsedMs = Date.now() - stableStartTime;
    if (currentBufferSize > 512 && underrunCount === 0 && elapsedMs >= 30_000) {
      currentBufferSize = 512;
      console.log('[audio_capture] Adaptive buffer: stable for 30s, dropping to 512 samples');
    }
  }, 5_000);

  // Expose underrun reporting so streaming code can increment the counter
  function reportUnderrun() {
    underrunCount++;
    stableStartTime = Date.now(); // Reset stability window on underrun
    currentBufferSize = initialBufferSize; // Revert to safe size
    console.warn(`[audio_capture] Buffer underrun detected — reverted to ${currentBufferSize} samples`);
  }

  function getBufferSize() {
    return currentBufferSize;
  }

  // T028: Pre-flight warmup (FR-013)
  // The noise gate runs during the warmup window so hardware buffers can settle.
  // The caller is responsible for forwarding the preflight_start/preflight_end
  // signals to the Python layer (via WebSocket JSON messages).
  const preflightPromise = new Promise((resolve) => {
    if (onPreflightStart) {
      onPreflightStart();
    }
    console.log(`[audio_capture] Pre-flight warmup started (${preflightDurationMs}ms)`);

    setTimeout(() => {
      if (onPreflightEnd) {
        onPreflightEnd();
      }
      console.log('[audio_capture] Pre-flight warmup complete — session live');
      resolve();
    }, preflightDurationMs);
  });

  /**
   * Stop audio capture — releases mic tracks, closes AudioContext, clears timers.
   */
  function stop() {
    clearInterval(adaptiveBufferInterval);
    micStream.getTracks().forEach(track => track.stop());
    audioContext.close();
  }

  return {
    audioContext,
    noiseGateNode,
    gatedStream: captureDestination.stream,
    stop,
    preflightPromise,
    getBufferSize,
    reportUnderrun,
  };
}

/**
 * Handle a server command received on the WebSocket.
 *
 * The browser WebSocket client should call this function when it receives a
 * text (JSON) frame from the Python server. This function routes the command
 * to the appropriate AudioWorklet processor.
 *
 * T025: flush_audio_buffer → forwards to NoiseGateProcessor port with fade-out
 *
 * @param {AudioWorkletNode} noiseGateNode Reference from initNoiseGate()
 * @param {Object} command Parsed JSON command from the server
 * @param {string} command.type Command type (e.g. "flush_audio_buffer")
 * @param {number} [command.fade_duration_ms=7] Fade-out duration for flush
 */
export function handleServerCommand(noiseGateNode, command) {
  if (!noiseGateNode || !command) return;

  if (command.type === 'flush_audio_buffer') {
    // Forward flush to AudioWorklet processor thread (T025, FR-010)
    noiseGateNode.port.postMessage({
      type: 'flush',
      fade_duration_ms: command.fade_duration_ms || 7,
    });
    console.log(`[audio_capture] Flush command sent to AudioWorklet (fade: ${command.fade_duration_ms || 7}ms)`);
  }
}
