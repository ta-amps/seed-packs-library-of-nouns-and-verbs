# Motion Learning & Formula Retargeting

Short-form technical videos live or die in their first 600 milliseconds and their beat-to-beat pacing. Rather than copying pixels, audio, or copyrighted footage from reference clips, `video_motion/motion.py` learns **pure mathematical timing and trajectory formulas** (`MotionProfile`) from lightweight observation traces.

## Canonical 6-Beat Narrative Formula

For a reference `16.0s` short-form story, the motion learner models six contiguous narrative phases and snaps internal transitions to nearby detected cuts or speaker switches:

| Beat Phase | Canonical Window (`16.0s`) | Normalized Ratio | Narrative Job | Typical Easing |
|---|---|---|---|---|
| `hook` | `0.0s – 0.6s` | `0.0000 – 0.0375` | Pattern interrupt; visual subject pops into frame immediately | `spring_pop` |
| `orientation` | `0.6s – 2.0s` | `0.0375 – 0.1250` | Establish cast, coordinate axes, or problem context | `ease_out_cubic` |
| `setup` | `2.0s – 6.0s` | `0.1250 – 0.3750` | Introduce baseline mechanism or Naive vs. Deterministic contrast | `ease_in_out_cubic` |
| `escalation` | `6.0s – 11.0s` | `0.3750 – 0.6875` | Compounding state change, benchmark bars rising, rapid speaker turns | `ease_in_out_cubic` |
| `punchline` | `11.0s – 14.8s` | `0.6875 – 0.9250` | Payoff metric, final comparison state, or visual reveal | `spring_pop` |
| `hold` | `14.8s – 16.0s` | `0.9250 – 1.0000` | Clean Loop/Read hold so viewers can absorb the final frame | `step_hold` |

*(When authoring a `16.0s` scene without a separate tail hold, `punchline` spans `11.0–16.0s` followed by a brief `hold`, or `retarget_motion()` scales all six `[start_ratio, end_ratio]` intervals proportionally to any target duration such as `10.0s`, `12.0s`, or `24.0s`.)*

## Parametric Easing Curve Fitting

Within each segmented beat `[t0, t1]`, `learn_motion_profile()` normalizes time `u = (t - t0) / (t1 - t0)` and projects the primary actor's `(primary_norm_x, primary_norm_y, primary_scale)` displacement onto `[0..1]`. It then evaluates all five parametric easing primitives and selects the minimum root-mean-square error (`fit_rmse`) match:

1. `linear`: `f(u) = u`
2. `ease_out_cubic`: `f(u) = 1 - (1 - u)^3`
3. `ease_in_out_cubic`: piecewise cubic S-curve accelerating to `u = 0.5` and decelerating cleanly to `1.0`
4. `spring_pop`: `f(u) = 1 - (1 - u) * exp(-5u) * cos(2.5 * pi * u)` (overshoots ~`1.05` mid-beat before settling smoothly to `1.0`)
5. `step_hold`: discrete hold (`0.0` for `u < 1`, `1.0` at `u = 1`) for freeze beats and cut snaps

## Retargeting Without Copying Source Media

A saved `MotionProfile` stores only:
- `beat_proportions` (`phase`, `start_ratio`, `end_ratio`, `mean_energy`, `dominant_easing`, `fit_rmse`),
- `median_cut_cadence_s` and `mean_motion_intensity`,
- normalized `LearnedTrajectory` waypoints (`ratio`, `norm_x`, `norm_y`, `scale`, `easing`), and
- canonical `profile_sha256`.

Calling `retarget_motion(profile, cast, duration_s=12.0, aspect="reels_9x16")` maps every beat boundary to an exact integer frame (`round(ratio * total_frames) / fps`), places the new open-licensed `CastMember` rigs inside `safe_canvas` so lower-third captions never occlude faces, and emits a ready-to-audit `SceneRecipe`.
