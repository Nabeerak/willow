willow/
│
├── main.py              # entry point — runs everything
├── config.py            # API keys, constants, tuning values
│
├── core/
│   ├── state.py         # State Manager — aₙ, d, m, the pulse
│   ├── sequences.py     # arithmetic decay formula
│   ├── signatures.py    # Thought Signature detection
│   └── plot.py          # Owned Plot — Sovereign Truths
│
├── voice/
│   ├── stream.py        # Gemini Live API WebSocket connection
│   ├── filler.py        # filler audio clips + trigger logic
│   └── audio/           # .wav filler files (hmm, aah, right so...)
│
├── agent/
│   ├── injector.py      # Prompt Injector — state → system prompt
│   └── parser.py        # [THOUGHT] tag parser
│
├── tests/
│   └── test_state.py    # test the arithmetic decay first
│
└── requirements.txt     # dependencies