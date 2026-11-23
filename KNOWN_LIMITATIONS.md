# Known limitations

- **Degree-guard trigger is failure-only.** The out-degree guard fires when the
  master returns no incumbent at all (`assign is None`). It does not detect
  quality degradation: on 640x25 the inequality can leave the master with an
  incumbent but a much worse one (solution count dropping from 10 to 1), which
  the guard cannot see; it then waits several iterations before dropping the
  rows. Measured cost of this blind spot was about -1.12 RPD points on 640x25
  and ~0.14 points averaged over the eight standard sizes. A quality-triggered
  guard would require a new threshold parameter for a ~0.14-point reward, so it
  was not added.
- **`ARC_CACHE_ON` and exact reproduction.** The published numbers were produced
  with the candidate-arc cache disabled. The cache changes solve TIME only (the
  candidate lists are identical), but for bit-faithful reproduction set
  `ARC_CACHE_ON = False` in `hlbb_hm.py`.
- **Some docstrings contain historical development references.** Current usage
  instructions are in the README, not in module docstrings.
