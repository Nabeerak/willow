 Searched for 4 patterns (ctrl+o to expand)                                                                                                                                                
                                                                                                                                                                                            
● Found it. From the constitution — these are the two deferred mood sequences that were explicitly out of scope for MVP:                                                                    
                                                                                                                                                                                            
  - Exponential Sequence: Governs Defense/Trust — spikes on provocation,                                                                                                                    
    drops fast on resolution                                                                                                                                                                
  - Sine Wave Sequence: Governs Engagement/Pacing — natural ebb and flow                                                                                                                    
    of when to push vs. listen                                                                                                                                                              
  - Priority Logic: Exponential MUST override Sine Wave during trust events;
    Arithmetic is baseline when no conflict is active

  Currently Willow only has the Arithmetic sequence (current_m) — one emotional axis. Adding these two gives Willow a full 3-dimensional mood system.

  What each sequence adds

  ┌────────────────┬──────────────────┬─────────────────┬─────────────────────────────────────────────────────────────┐
  │    Sequence    │  State Variable  │     Governs     │                          Behavior                           │
  ├────────────────┼──────────────────┼─────────────────┼─────────────────────────────────────────────────────────────┤
  │ Arithmetic ✅  │ current_m        │ Social Presence │ Slow drift, ambient vibe                                    │
  ├────────────────┼──────────────────┼─────────────────┼─────────────────────────────────────────────────────────────┤
  │ Exponential 🔜 │ defense_level    │ Defense/Trust   │ Spikes hard on provocation, drops fast on resolution        │
  ├────────────────┼──────────────────┼─────────────────┼─────────────────────────────────────────────────────────────┤
  │ Sine Wave 🔜   │ engagement_phase │ Pacing          │ Natural push/listen rhythm — when to elaborate vs. be brief │
  └────────────────┴──────────────────┴─────────────────┴─────────────────────────────────────────────────────────────┘

  Priority rule (from constitution)

  Exponential → overrides Sine Wave during trust events
  Arithmetic  → baseline when no conflict active

  Scope for 11 days

  This is spec 003. I'd suggest:

  - Days 1-2: Spec + plan (/sp.specify + /sp.plan)
  - Days 3-4: Tasks + implementation of Exponential sequence
  - Days 5-6: Sine Wave sequence + priority logic
  - Days 7-8: Wire both into Tier 1/2/3 responses (affects tone, length, pacing)
  - Days 9-10: Tests + calibration
  - Day 11: Cloud Run deploy (T069) + UI update

  Want to kick off with /sp.specify for the mood sequences spec?

✻ Cooked for 1m 28s

❯ what else?                                                                                                                                                                                
             
● Read 2 files (ctrl+o to expand)                                                                                                                                                           
                                                                                                                                                                                            
● Everything deferred from MVP, pulled directly from the spec and constitution:                                                                                                             
                        
  ---                                                                                                                                                                                       
  Full backlog of deferred features                                                                                                                                                         
                                                                                                                                                                                            
  From the Constitution (Mood — highest priority)                                                                                                                                           
                  
  ┌───────────────────────────┬────────────────────────────────────────────────────────────────────────────────────┐
  │          Feature          │                                    What it does                                    │
  ├───────────────────────────┼────────────────────────────────────────────────────────────────────────────────────┤
  │ Exponential Sequence      │ Defense/Trust axis — spikes hard on provocation, drops fast on resolution          │
  ├───────────────────────────┼────────────────────────────────────────────────────────────────────────────────────┤
  │ Sine Wave Sequence        │ Engagement/Pacing axis — natural rhythm of when Willow pushes vs. listens          │
  ├───────────────────────────┼────────────────────────────────────────────────────────────────────────────────────┤
  │ 3-sequence priority logic │ Exponential overrides Sine Wave during trust events; Arithmetic is always baseline │
  └───────────────────────────┴────────────────────────────────────────────────────────────────────────────────────┘

  From the Spec (Out of Scope)

  ┌──────────────────────────────────────────────┬────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
  │                   Feature                    │                                                  What it does                                                  │
  ├──────────────────────────────────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Full Owned Plot database                     │ Right now: 10-20 curated facts. Full version: larger, structured domain knowledge Willow defends               │
  ├──────────────────────────────────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Vector embedding for contradiction detection │ Replace keyword matching with semantic similarity — catches paraphrased contradictions the keyword gate misses │
  ├──────────────────────────────────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Multi-session memory                         │ Willow remembers you across sessions — not just within one conversation                                        │
  ├──────────────────────────────────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Voice customization                          │ User or admin configures Willow's voice, not hardcoded to "Aoede"                                              │
  ├──────────────────────────────────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Real-time Sovereign Truth updates            │ Add/edit facts during a live session without restart                                                           │
  ├──────────────────────────────────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Multi-user conversation support              │ More than one participant in a session                                                                         │
  ├──────────────────────────────────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ FFT pitch analysis                           │ Detect intonation (questioning tone, sarcasm through pitch) — placeholder exists, needs activation             │
  ├──────────────────────────────────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ localStorage audio buffer state              │ Persist noise gate buffer across page refreshes                                                                │
  ├──────────────────────────────────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Mobile app interface                         │ Native iOS/Android rather than browser                                                                         │
  └──────────────────────────────────────────────┴────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘

  ---
  Realistic for 11 days

  ┌──────────┬──────────────────────────────────────────────────────────────────┬──────┐
  │ Priority │                             Feature                              │ Days │
  ├──────────┼──────────────────────────────────────────────────────────────────┼──────┤
  │ 1        │ Exponential + Sine Wave sequences + priority logic (spec 003)    │ 4    │
  ├──────────┼──────────────────────────────────────────────────────────────────┼──────┤
  │ 2        │ Vector embedding contradiction detection (replaces keyword gate) │ 2    │
  ├──────────┼──────────────────────────────────────────────────────────────────┼──────┤
  │ 3        │ Full Owned Plot database — expand sovereign truths meaningfully  │ 1    │
  ├──────────┼──────────────────────────────────────────────────────────────────┼──────┤
  │ 4        │ Multi-session memory (Firestore or Cloud Storage)                │ 2    │
  ├──────────┼──────────────────────────────────────────────────────────────────┼──────┤
  │ 5        │ T069 Cloud Run deploy + UI polish                                │ 1    │
  ├──────────┼──────────────────────────────────────────────────────────────────┼──────┤
  │ —        │ Buffer (testing, calibration, integration)                       │ 1    │
  └──────────┴──────────────────────────────────────────────────────────────────┴──────┘

  The mood sequences (Exponential + Sine Wave) are the most impactful — they complete the constitution's vision. Everything else is expansion. What do you want to tackle first?

❯ but out of scope is a real leaverage                                                                                                                                                      
                                       
● Exactly right. Each one isn't just a feature — it's a capability gap that limits what Willow can be. Here's the leverage map:                                                             
                                                                                                                                                                                            
  ---                                                                                                                                                                                       
  The Leverage Map                                                                                                                                                                          
                                                                                                                                                                                            
  🔴 Tier 1 — Changes what Willow is

  ┌───────────────────────────────┬─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
  │            Feature            │                                                                    The Leverage                                                                     │
  ├───────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Multi-session memory          │ Without it, Willow is a chatbot. With it, Willow is a relationship. She remembers who you are, how you've behaved, what you've tried before. The    │
  │                               │ behavioral model becomes longitudinal.                                                                                                              │
  ├───────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Exponential + Sine Wave       │ Without them, Willow has one emotional axis. With all three, she has a genuine mood architecture — defense spikes independently of ambient warmth,  │
  │ sequences                     │ engagement breathes naturally. She stops feeling like a state machine.                                                                              │
  ├───────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Vector embedding              │ Without it, the Sovereign layer is only as good as the keywords you wrote. With it, paraphrased contradictions get caught. "You're from England"    │
  │ contradiction detection       │ fires the same gate as "You were born in London." The integrity layer becomes real.                                                                 │
  └───────────────────────────────┴─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘

  🟡 Tier 2 — Expands what Willow knows

  ┌──────────────────────────────┬──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
  │           Feature            │                                                                     The Leverage                                                                     │
  ├──────────────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Full Owned Plot database     │ 10-20 facts is a demo. A structured, curated domain is a product. This is the difference between Willow defending herself on 15 topics vs. being     │
  │                              │ genuinely authoritative.                                                                                                                             │
  ├──────────────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Real-time Sovereign Truth    │ Turns the Owned Plot from a static file into a living knowledge base you can curate without a redeploy.                                              │
  │ updates                      │                                                                                                                                                      │
  ├──────────────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ FFT pitch analysis           │ Intonation is the layer keywords can never reach. "Really?" said flatly vs. rising — completely different intent. This unlocks a new signal          │
  │                              │ dimension for the Thought Signature.                                                                                                                 │
  └──────────────────────────────┴──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘

  🟢 Tier 3 — Broadens who Willow serves

  ┌─────────────────────────┬───────────────────────────────────────────────────────────────────────────────────────────────────────┐
  │         Feature         │                                             The Leverage                                              │
  ├─────────────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Mobile app interface    │ Browser-only limits the audience. Native mobile is where voice agents live.                           │
  ├─────────────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Multi-user conversation │ Single-user is personal AI. Multi-user is mediation, coaching, facilitation — entirely new use cases. │
  ├─────────────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Voice customization     │ Persona lock-in vs. platform flexibility.                                                             │
  └─────────────────────────┴───────────────────────────────────────────────────────────────────────────────────────────────────────┘

  ---
  11-day sequence by leverage

  ┌──────┬──────────────────────────────────────────────────────────────────────────┬────────────────────────────────────────────────────────────┐
  │ Days │                                   Work                                   │                       Why this order                       │
  ├──────┼──────────────────────────────────────────────────────────────────────────┼────────────────────────────────────────────────────────────┤
  │ 1–2  │ Spec 003: Exponential + Sine Wave                                        │ Foundation — touches Tier 2 which everything flows through │
  ├──────┼──────────────────────────────────────────────────────────────────────────┼────────────────────────────────────────────────────────────┤
  │ 3–4  │ Multi-session memory (Firestore)                                         │ Highest product leverage, independent of mood sequences    │
  ├──────┼──────────────────────────────────────────────────────────────────────────┼────────────────────────────────────────────────────────────┤
  │ 5–6  │ Vector embedding contradiction detection                                 │ Upgrades Tier 4's integrity layer significantly            │
  ├──────┼──────────────────────────────────────────────────────────────────────────┼────────────────────────────────────────────────────────────┤
  │ 7    │ Expand Owned Plot + real-time updates                                    │ Data work, no new architecture needed                      │
  ├──────┼──────────────────────────────────────────────────────────────────────────┼────────────────────────────────────────────────────────────┤
  │ 8    │ FFT pitch analysis (activate the flag)                                   │ Low-risk, flag already exists                              │
  ├──────┼──────────────────────────────────────────────────────────────────────────┼────────────────────────────────────────────────────────────┤
  │ 9–10 │ Cloud Run deploy (T069) + integration testing across all three sequences │                                                            │
  ├──────┼──────────────────────────────────────────────────────────────────────────┼────────────────────────────────────────────────────────────┤
  │ 11   │ UI update to surface new state dimensions                                │ Show the three axes visually                               │
  └──────┴──────────────────────────────────────────────────────────────────────────┴────────────────────────────────────────────────────────────┘

  ---
  Want to start with spec 003 (the mood sequences) since it's the constitutional backbone, or jump to multi-session memory since it changes the product identity most?


What you'd need to update per feature

  ┌─────────────────────────┬────────────────────────────────────────────────────────┐
  │         Feature         │                    UI change needed                    │
  ├─────────────────────────┼────────────────────────────────────────────────────────┤
  │ Exponential + Sine Wave │ Add 2 new state bars (defense_level, engagement_phase) │
  ├─────────────────────────┼────────────────────────────────────────────────────────┤
  │ Multi-session memory    │ Add "returning user" indicator, past session summary   │
  ├─────────────────────────┼────────────────────────────────────────────────────────┤
  │ Vector embeddings       │ Invisible to UI — backend only                         │
  ├─────────────────────────┼────────────────────────────────────────────────────────┤
  │ Full Owned Plot         │ Maybe a "defending truth" indicator when Tier 4 fires  │
  ├─────────────────────────┼────────────────────────────────────────────────────────┤
  │ FFT pitch               │ Could surface intonation signal in debug mode          │
  └─────────────────────────┴────────────────────────────────────────────────────────┘
