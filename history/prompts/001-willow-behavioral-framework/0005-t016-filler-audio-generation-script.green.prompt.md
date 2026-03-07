---
id: 0005
title: T016 Filler Audio Generation Script
stage: green
date: 2026-02-28
surface: agent
model: claude-opus-4-5-20251101
feature: 001-willow-behavioral-framework
branch: 001-willow-behavioral-framework
user: nabeera
command: Task T016
labels: ["filler-audio", "phase2", "foundational", "latency-masking"]
links:
  spec: /home/nabeera/willow/specs/001-willow-behavioral-framework/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - /home/nabeera/willow/scripts/generate_filler_audio.py
  - /home/nabeera/willow/data/filler_audio/hmm.wav
  - /home/nabeera/willow/data/filler_audio/aah.wav
  - /home/nabeera/willow/data/filler_audio/right_so.wav
  - /home/nabeera/willow/data/filler_audio/interesting.wav
  - /home/nabeera/willow/data/filler_audio/cool_but.wav
tests:
  - Manual execution test: script generates all 5 WAV files
  - Manual verification: all files meet 16kHz, 16-bit, mono specs
  - Skip-if-exists test: re-running script skips valid existing files
---

## Prompt

Execute Phase 2 foundational task T016 for Willow Behavioral Framework.

**Your Task (T016):**

Create filler audio generation script at /home/nabeera/willow/scripts/generate_filler_audio.py:

The script should:
1. Generate 5 filler audio WAV files using text-to-speech or create placeholder WAV files
2. Output directory: data/filler_audio/
3. Files to generate:
   - hmm.wav (for Tier 3 manipulation detection)
   - aah.wav (for Tier 4 truth conflict)
   - right_so.wav (for emotional spike)
   - interesting.wav (for new tactic flagged)
   - cool_but.wav (for engagement drop)

4. Audio specifications:
   - Duration: 200-500ms each
   - Sample rate: 16kHz
   - Bit depth: 16-bit
   - Channels: Mono

5. Implementation options (in order of preference):
   - Use pyttsx3 or gTTS if available
   - Use wave module to generate simple tone placeholders
   - Create silent WAV files as placeholders with correct format

6. The script should:
   - Check if files already exist (skip if present)
   - Print progress for each file
   - Verify file duration after creation
   - Handle errors gracefully

Make the script executable and add proper shebang.

## Response snapshot

Created `/home/nabeera/willow/scripts/generate_filler_audio.py` with:
- Proper shebang (`#!/usr/bin/env python3`)
- Multi-fallback TTS strategy: pyttsx3 -> gTTS+pydub -> tone placeholders -> silent placeholders
- 5 filler audio configurations with tier trigger mappings
- WAV generation using standard library `wave` and `struct` modules
- File verification (duration, sample rate, bit depth, channels)
- Skip-if-exists logic with validation of existing files
- Fade in/out envelope on tone placeholders for natural sound
- Different frequencies per filler (180Hz-300Hz) for auditory distinction
- Comprehensive progress output and summary

All 5 WAV files generated successfully with correct specifications:
- hmm.wav: 400ms, 12844 bytes (180Hz tone)
- aah.wav: 300ms, 9644 bytes (220Hz tone)
- right_so.wav: 450ms, 14444 bytes (260Hz tone)
- interesting.wav: 500ms, 16044 bytes (300Hz tone)
- cool_but.wav: 400ms, 12844 bytes (240Hz tone)

## Outcome

- Impact: Phase 2 foundational task T016 complete; filler audio infrastructure ready for Tier 3/4 latency masking
- Tests: Manual execution verified; all files meet 16kHz/16-bit/mono specs; skip-if-exists works
- Files: 1 Python script + 5 WAV files created
- Next prompts: T017 (execute script to verify WAV files) - already done in this session
- Reflection: Used standard library only (wave, struct, math) for maximum portability; TTS integration available but not required for MVP

## Evaluation notes (flywheel)

- Failure modes observed: None - script executed successfully on first run
- Graders run and results (PASS/FAIL): Manual verification PASS (file format verified with `file` command)
- Prompt variant (if applicable): N/A
- Next experiment (smallest change to try): Add real TTS audio when pyttsx3/gTTS available in production environment
