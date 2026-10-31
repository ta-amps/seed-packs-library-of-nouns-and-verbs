# multimodal_align

Standard-library Python tools for aligning per-frame image/video segmentation masks, speech-to-text
word timings, and non-occluding layout safe zones.

## Commands

```bash
python3 -m multimodal_align align timeline.json --max-drift-ms 250 --max-intrusion 0.05
make check
```
