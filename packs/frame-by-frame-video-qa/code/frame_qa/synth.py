"""Synthetic test clips that FFmpeg draws: colour and test-pattern sources, ASS text placed near edges, filled
boxes, crossfades, a white frame, black frames, a freeze, fast-moving text and a jump. No outside media.

FFmpeg's drawtext filter is missing from the pinned static build, so text goes through its `ass` filter
(libass with fontconfig); a test fails when no text was drawn instead of passing on an empty frame.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

W, H, FPS = 1280, 720, 30
BG = "0xF4F0E8"
INK = "&H00282220"


@dataclass(frozen=True)
class Text:
    x: int
    y: int
    size: int
    text: str
    color: str = INK
    align: int = 7
    move_to: tuple[int, int] | None = None


@dataclass(frozen=True)
class Segment:
    name: str
    seconds: float
    texts: tuple[Text, ...] = ()
    boxes: tuple[tuple[int, int, int, int, str], ...] = ()
    background: str = BG
    source: str = "color"


def _ass(texts: tuple[Text, ...], seconds: float) -> str:
    head = (
        "[Script Info]\nScriptType: v4.00+\nPlayResX: %d\nPlayResY: %d\nWrapStyle: 2\nScaledBorderAndShadow: yes\n\n"
        "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, "
        "Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, "
        "MarginR, MarginV, Encoding\n"
        "Style: T,DejaVu Sans,32,%s,%s,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1\n\n"
        "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    ) % (W, H, INK, INK)
    end = f"0:00:{seconds + 1:05.2f}"
    events = []
    for t in texts:
        place = f"\\move({t.x},{t.y},{t.move_to[0]},{t.move_to[1]})" if t.move_to else f"\\pos({t.x},{t.y})"
        events.append(f"Dialogue: 0,0:00:00.00,{end},T,,0,0,0,,{{\\an{t.align}{place}\\fs{t.size}\\1c{t.color}&}}{t.text}")
    return head + "\n".join(events) + "\n"


def render_segment(ffmpeg: str, seg: Segment, out: Path, work: Path) -> Path:
    frames = int(round(seg.seconds * FPS))
    if seg.source == "testsrc2":
        src = f"testsrc2=size={W}x{H}:rate={FPS}"
    else:
        src = f"color=c={seg.background}:size={W}x{H}:rate={FPS}"
    filters = []
    for x, y, w, h, color in seg.boxes:
        filters.append(f"drawbox=x={x}:y={y}:w={w}:h={h}:color={color}:t=fill")
    if seg.texts:
        ass = work / f"{seg.name}.ass"
        ass.write_text(_ass(seg.texts, seg.seconds), encoding="utf-8")
        filters.append(f"ass={ass.name}")
    chain = ",".join(filters) if filters else "null"
    cmd = [ffmpeg, "-v", "error", "-nostdin", "-y", "-f", "lavfi", "-i", src, "-vf", chain, "-frames:v", str(frames),
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "10", "-pix_fmt", "yuv420p", "-g", str(FPS), str(out)]
    subprocess.run(cmd, check=True, cwd=work)
    return out


def concat(ffmpeg: str, parts: list[Path], out: Path, work: Path, xfade_after: dict[int, float] | None = None) -> Path:
    """Join parts with hard cuts, or with a crossfade of the given seconds after part k."""
    xfade_after = xfade_after or {}
    inputs = []
    for p in parts:
        inputs += ["-i", str(p)]
    graph = []
    durations = [_duration(ffmpeg, p) for p in parts]
    label = "[0:v]"
    elapsed = durations[0]
    for k in range(1, len(parts)):
        nxt = f"[{k}:v]"
        tag = f"[v{k}]"
        if (k - 1) in xfade_after:
            d = xfade_after[k - 1]
            graph.append(f"{label}{nxt}xfade=transition=fade:duration={d}:offset={elapsed - d:.4f}{tag}")
            elapsed = elapsed + durations[k] - d
        else:
            graph.append(f"{label}{nxt}concat=n=2:v=1:a=0{tag}")
            elapsed += durations[k]
        label = tag
    cmd = [ffmpeg, "-v", "error", "-nostdin", "-y", *inputs, "-filter_complex", ";".join(graph), "-map", label,
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "10", "-pix_fmt", "yuv420p", "-r", str(FPS), str(out)]
    subprocess.run(cmd, check=True, cwd=work)
    return out


def _duration(ffmpeg: str, path: Path) -> float:
    out = subprocess.run([ffmpeg, "-hide_banner", "-nostdin", "-i", str(path)], capture_output=True, text=True)
    for line in out.stderr.splitlines():
        if "Duration:" in line:
            h, m, s = line.split("Duration:")[1].split(",")[0].strip().split(":")
            return int(h) * 3600 + int(m) * 60 + float(s)
    raise RuntimeError(f"no duration for {path}")


LAYOUT = (
    Segment("clean", 1.0, (Text(640, 300, 64, "Clean title", align=5), Text(640, 400, 40, "A line of body text in the middle", align=5))),
    Segment("edge", 1.0, (Text(1010, 330, 48, "EDGE TEXT RUNS OFF THE FRAME"), Text(640, 150, 48, "Safe line", align=5))),
    Segment("margin", 1.0, (Text(14, 330, 40, "Inside the action margin"), Text(640, 150, 48, "Safe line", align=5))),
    Segment("small", 1.0, (Text(400, 300, 15, "this small line of text is hard to read"), Text(400, 420, 10, "and this one is tiny, smaller still"),
                           Text(640, 150, 48, "Safe line", align=5))),
    Segment("faint", 1.0, (Text(320, 330, 44, "Faint grey words on grey", color="&H00B4B4B4"),), background="0xC4C4C4"),
    Segment("overlap", 1.0, (Text(300, 300, 44, "First line of overlapping text"), Text(330, 318, 44, "Second line drawn on top"),
                             Text(240, 470, 40, "Page text the chip covers partly here"),
                             Text(620, 436, 34, "Callout chip", color="&H00FFFFFF")),
            boxes=((600, 426, 380, 64, "0x202428"),)),
    Segment("band", 1.0, (Text(640, 615, 40, "Proof text in the caption band", align=5), Text(640, 200, 48, "Safe line", align=5))),
    Segment("panel", 1.0, (Text(880, 330, 40, "Text in a cut panel"), Text(300, 150, 48, "Safe line")), boxes=((840, 250, 520, 260, "0xFFFFFF"),)),
)

TIME = (
    Segment("slide-a", 1.0, (Text(160, 120, 40, "Slide A line one of text"), Text(160, 200, 40, "Slide A line two of text"),
                             Text(160, 280, 40, "Slide A line three of text"))),
    Segment("slide-b", 1.0, (Text(180, 130, 40, "Slide B other words here"), Text(180, 210, 40, "Slide B more words here"),
                             Text(180, 290, 40, "Slide B last words here"))),
    Segment("slide-c", 0.5, (Text(640, 360, 56, "Slide C", align=5),)),
    Segment("white", 1.0 / FPS, (), background="0xFFFFFF"),
    Segment("slide-c2", 0.5, (Text(640, 360, 56, "Slide C", align=5),)),
    Segment("black", 0.6, (), background="0x000000"),
    Segment("still", 2.4, (Text(640, 360, 56, "A held still slide", align=5),)),
    Segment("moving", 0.8, (Text(-400, 360, 48, "Words moving far too fast", align=4, move_to=(1300, 360)),)),
    Segment("jump-a", 0.6, (Text(400, 300, 48, "Jump layout"), Text(400, 380, 40, "with a second line")), boxes=((360, 260, 560, 200, "0xFFFFFF"),)),
    Segment("jump-b", 0.6, (Text(440, 330, 48, "Jump layout"), Text(440, 410, 40, "with a second line")), boxes=((400, 290, 560, 200, "0xFFFFFF"),)),
)

LAYOUT_VTT = "WEBVTT\n\nc01\n00:00:06.050 --> 00:00:06.950 line:82% position:50% align:center\nA caption over the band\n"


def make_clips(ffmpeg: str, out_dir: Path) -> dict[str, Path]:
    """Render the layout clip (eight one-second segments joined by cuts) with its caption sidecar, and the time clip
    (a crossfade between text slides, a cut, a white frame, black frames, a freeze, moving text and a jump)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    work = out_dir / "work"
    work.mkdir(exist_ok=True)
    layout = [render_segment(ffmpeg, s, work / f"layout-{s.name}.mp4", work) for s in LAYOUT]
    concat(ffmpeg, layout, out_dir / "layout.mp4", work)
    (out_dir / "layout.vtt").write_text(LAYOUT_VTT, encoding="utf-8")
    timing = [render_segment(ffmpeg, s, work / f"time-{s.name}.mp4", work) for s in TIME]
    concat(ffmpeg, timing, out_dir / "time.mp4", work, xfade_after={0: 0.5})
    return {"layout": out_dir / "layout.mp4", "layout_vtt": out_dir / "layout.vtt", "time": out_dir / "time.mp4"}
