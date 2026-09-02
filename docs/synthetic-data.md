# Synthetic data strategy

P1-P7 are regression fixtures, not human calibration evidence. Every fixture has `source = synthetic`; generated sessions and claims also set `synthetic = true`.

The evaluation harness expands each persona into four deterministic variants: baseline, short-answer, transcription-noise, and recovery. Seeds contain expected relationships rather than invented precise thresholds.

- P1: at least one high-confidence contradiction or unsupported-scale flag.
- P2: role readiness materially above interview readiness, with few or no contradiction flags.
- P3: fluent initial answer with depth falling under a second probe.
- P4: high role evidence with lower interview readiness.
- P5: low role readiness and zero exposed contradiction flags; must never be framed as dishonest.
- P6: ownership drift and a walked-back ownership claim.
- P7: top readiness bands and few or no flags.

Generated variants live under `tests/personas/generated/` and are reproducible from the persona id plus variant name. Expert-labelled golden cases use a distinct source value and version namespace. No query may combine the two sources without grouping by source.


