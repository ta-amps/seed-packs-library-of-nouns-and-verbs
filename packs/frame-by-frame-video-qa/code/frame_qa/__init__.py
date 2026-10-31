"""Frame-by-frame computer-vision QA for an encoded video.

Deterministic tools a worker runs inside a claimed verb: sample every frame, run nine detectors, join hits
on nearby frames into findings, draw each finding on its frame, and report. Nothing here calls a model API,
opens a network connection, publishes or enqueues anything. The text detector is a local ONNX model that
runs on the CPU; without it, a model-free OpenCV detector is used.
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
