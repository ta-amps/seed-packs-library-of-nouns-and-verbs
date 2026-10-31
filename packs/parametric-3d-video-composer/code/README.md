# parametric-3d-video-composer code

Standard-library scene planner and layout verifier for `packs/parametric-3d-video-composer`:

- `parametric_composer.camera`: `1x3` and `2x2` Product Hub 3D perspective camera trajectory planner (`overview -> pillar_focus -> bridge_zoom_out -> next_pillar -> finale_hub`) with quintic C2 smootherstep easing and 3D pinhole projection.
- `parametric_composer.layout`: desktop browser window and tab chrome layout calculator plus safe-stage (`x: 96..1824, y: 72..820`) and lower caption band (`y: 836..1080`) collision verifier.
- `parametric_composer.transitions`: zero-double-exposure transition validator forbidding text-on-text crossfades in favor of camera moves or clean cuts, plus clamped card aura and quadratic Bezier edge-packet interpolation curves.

Run `make check` to compile with `-W error` and run all unit tests and the worked-example recomputation.
