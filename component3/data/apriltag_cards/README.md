# Phase 7B.1 AprilTag cards

These cards are generated locally from OpenCV's `DICT_APRILTAG_36h11`; no
third-party marker images are used. IDs 200, 201, and 202 represent the demo
store checkpoints. ID 42 is deliberately unknown and is used only for rejection
testing.

Regenerate and verify every PNG before printing:

```bash
component3/.venv/bin/python component3/data/apriltag_cards/generate_cards.py
```

Each PDF contains a 200 mm square card with a centered 160 mm marker and 20 mm
white margins. Its human-readable label is in a separate 20 mm strip below the
card, outside the marker and card quiet zone. Print with **Actual Size / 100%**,
disable "Fit to page", use matte paper, and measure the black marker boundary;
it must be 160 mm square. The A2 sheet contains all four cards at the same scale.
