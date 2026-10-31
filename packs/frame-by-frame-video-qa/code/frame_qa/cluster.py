"""The `cluster` verb's work: join one detector's hits on nearby frames into findings.

Hits of the same detector and kind join when they are at most `max_gap_frames` apart and their boxes overlap
by `match_iou` or more (whole-frame hits join on their key). A second pass joins findings of the same
detector and kind whose boxes nearly coincide and that are less than a second apart, keeping every interval.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .detectors import SEVERITY_RANK, Box, Hit, iou, union, worse


@dataclass
class Cluster:
    detector: str
    kind: str
    key: str
    hits: list[Hit] = field(default_factory=list)
    intervals: list[list[int]] = field(default_factory=list)

    @property
    def first(self) -> int:
        return self.hits[0].frame

    @property
    def last(self) -> int:
        return self.hits[-1].frame

    @property
    def severity(self) -> str:
        level = "note"
        for hit in self.hits:
            level = worse(level, hit.severity)
        return level

    @property
    def box(self) -> Box | None:
        rep = self.representative
        return rep.box

    @property
    def union_box(self) -> Box | None:
        boxes = [h.box for h in self.hits if h.box is not None]
        if not boxes:
            return None
        out = boxes[0]
        for b in boxes[1:]:
            out = union(out, b)
        return out

    @property
    def representative(self) -> Hit:
        """The worst hit: highest severity, then highest score, then the earliest frame."""
        return sorted(self.hits, key=lambda h: (-SEVERITY_RANK[h.severity], -h.score, h.frame))[0]

    def last_box(self) -> Box | None:
        return self.hits[-1].box


def _affinity(cluster: Cluster, hit: Hit, frame_gap: int, match_iou: float) -> float:
    """How well a hit continues a cluster: its box IoU with the cluster's last box, 1.0 for a matching key,
    or -1 when it cannot join."""
    if hit.frame - cluster.last > frame_gap or hit.frame == cluster.last:
        return -1.0
    if hit.key.startswith("shot:") or cluster.key.startswith("shot:"):
        return 1.0 if hit.key == cluster.key else -1.0
    last = cluster.last_box()
    if hit.box is None or last is None:
        return 1.0 if hit.key == cluster.key and hit.box is None and last is None else -1.0
    score = iou(last, hit.box)
    return score if score >= match_iou else -1.0


def cluster_hits(hits: list[Hit], spec: dict, fps: float) -> list[Cluster]:
    rules = spec["clustering"]
    gap = int(rules["max_gap_frames"])
    match_iou = float(rules["match_iou"])
    groups: dict[tuple[str, str], list[Hit]] = {}
    for hit in hits:
        groups.setdefault((hit.detector, hit.kind), []).append(hit)
    out: list[Cluster] = []
    for (detector, kind), items in sorted(groups.items()):
        by_frame: dict[int, list[Hit]] = {}
        for hit in items:
            by_frame.setdefault(hit.frame, []).append(hit)
        active: list[Cluster] = []
        for frame in sorted(by_frame):
            frame_hits = sorted(by_frame[frame], key=lambda h: (h.box or (0, 0, 0, 0), h.key))
            pairs = []
            for ci, cluster in enumerate(active):
                for hi, hit in enumerate(frame_hits):
                    score = _affinity(cluster, hit, gap, match_iou)
                    if score >= 0:
                        pairs.append((-score, ci, hi))
            pairs.sort()
            used_c, used_h = set(), set()
            for _, ci, hi in pairs:
                if ci in used_c or hi in used_h:
                    continue
                active[ci].hits.append(frame_hits[hi])
                used_c.add(ci)
                used_h.add(hi)
            for hi, hit in enumerate(frame_hits):
                if hi in used_h:
                    continue
                cluster = Cluster(detector, kind, hit.key, [hit])
                active.append(cluster)
                out.append(cluster)
            active = [c for c in active if frame - c.last <= gap]
    merged = _merge_near(out, fps)
    for cluster in merged:
        if not cluster.intervals:
            cluster.intervals = [[cluster.first, cluster.last]]
    return _apply_duration_rules(merged, spec, fps)


def _merge_near(clusters: list[Cluster], fps: float, gap_s: float = 1.0, same_iou: float = 0.5) -> list[Cluster]:
    by_kind: dict[tuple[str, str], list[Cluster]] = {}
    for c in clusters:
        by_kind.setdefault((c.detector, c.kind), []).append(c)
    out = []
    for key, items in sorted(by_kind.items()):
        items.sort(key=lambda c: (c.first, c.last))
        if key[0] in TEMPORAL or any(c.key.startswith("shot:") for c in items):
            out.extend(items)
            continue
        kept: list[Cluster] = []
        for c in items:
            joined = False
            for k in reversed(kept):
                near = 0 <= c.first - k.last <= gap_s * fps
                same = (c.union_box is None and k.union_box is None and c.key == k.key) or (
                    c.union_box is not None and k.union_box is not None and iou(c.union_box, k.union_box) >= same_iou)
                if near and same:
                    if not k.intervals:
                        k.intervals = [[k.first, k.last]]
                    k.intervals.append([c.first, c.last])
                    k.hits.extend(c.hits)
                    k.hits.sort(key=lambda h: (h.frame, h.box or (0, 0, 0, 0)))
                    joined = True
                    break
            if not joined:
                kept.append(c)
        out.extend(kept)
    out.sort(key=lambda c: (c.first, c.detector, c.kind, c.box or (0, 0, 0, 0)))
    return out


TEMPORAL = {"transitions", "freezes_and_motion"}


def _apply_duration_rules(clusters: list[Cluster], spec: dict, fps: float) -> list[Cluster]:
    out = []
    every = int(spec["sampling"]["spatial_every_frames"])
    for c in clusters:
        span_frames = c.last - c.first + (1 if c.detector in TEMPORAL else every)
        seconds = span_frames / fps
        minimum = spec["detectors"][c.detector]["thresholds"].get("min_duration_s", 0.0)
        if c.detector not in TEMPORAL and seconds < minimum:
            continue
        if c.kind == "text_at_edge":
            level = "major" if seconds >= 0.5 else "minor"
            for hit in c.hits:
                hit.severity = level
        out.append(c)
    return out
