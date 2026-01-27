"""Anchor-based auto-calibration for GOP3."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    import cv2  # type: ignore
except Exception:  # pragma: no cover - optional at runtime
    cv2 = None  # type: ignore


ANCHOR_REF_WIDTH = 2560
ANCHOR_REF_HEIGHT = 1440


@dataclass
class AnchorMatch:
    name: str
    score: float
    scale: float
    x: int
    y: int
    ref_x: int
    ref_y: int


@dataclass
class Transform:
    scale: float
    offset_x: float
    offset_y: float
    anchors: List[AnchorMatch]
    window_rect: Optional[Tuple[int, int, int, int]] = None


ANCHOR_DEFS = [
    {
        "name": "home",
        "file": "anchors/home_icon.png",
        "ref_box": (450, 350, 60, 70),
        "search_margin": 0.10,
    },
    {
        "name": "friends",
        "file": "anchors/friends_icon.png",
        "ref_box": (1852, 353, 55, 61),
        "search_margin": 0.10,
    },
]


class AutoCalibrator:
    """Finds anchor templates to derive scale + offset transform."""

    def __init__(self, enabled: bool = True, threshold: float = 0.75):
        self.enabled = enabled
        self.threshold = threshold
        self.ref_w = ANCHOR_REF_WIDTH
        self.ref_h = ANCHOR_REF_HEIGHT
        self.anchors = self._load_anchors()
        self.transform: Optional[Transform] = None
        self.status = "disabled" if not enabled else "uninitialized"
        self.last_attempt = 0.0

    def _load_anchors(self) -> List[Dict[str, object]]:
        if cv2 is None:
            return []
        base = Path(__file__).resolve().parent
        anchors: List[Dict[str, object]] = []
        for anchor in ANCHOR_DEFS:
            path = base / anchor["file"]
            tmpl = cv2.imread(str(path))
            if tmpl is None:
                continue
            x, y, w, h = anchor["ref_box"]
            margin = float(anchor.get("search_margin", 0.08))
            xp1 = max(0.0, x / self.ref_w - margin)
            xp2 = min(1.0, (x + w) / self.ref_w + margin)
            yp1 = max(0.0, y / self.ref_h - margin)
            yp2 = min(1.0, (y + h) / self.ref_h + margin)
            entry = dict(anchor)
            entry["template"] = tmpl
            entry["x_percent"] = (xp1, xp2)
            entry["y_percent"] = (yp1, yp2)
            anchors.append(entry)
        return anchors

    def _match_anchor(self, screen, anchor: Dict[str, object], scales: List[float], *, full_search: bool = False) -> Optional[AnchorMatch]:
        if cv2 is None:
            return None
        tmpl = anchor.get("template")
        if tmpl is None:
            return None
        h, w = screen.shape[:2]
        if full_search:
            rx1, ry1, rx2, ry2 = 0, 0, w, h
        else:
            rx1 = int(w * anchor["x_percent"][0])
            rx2 = int(w * anchor["x_percent"][1])
            ry1 = int(h * anchor["y_percent"][0])
            ry2 = int(h * anchor["y_percent"][1])
            if rx2 <= rx1 or ry2 <= ry1:
                return None
        roi = screen[ry1:ry2, rx1:rx2]
        if roi.size == 0:
            return None

        screen_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        tmpl_gray = cv2.cvtColor(tmpl, cv2.COLOR_BGR2GRAY)

        best_score = -1.0
        best_loc = None
        best_scale = None
        for scale in scales:
            if scale <= 0:
                continue
            scaled = cv2.resize(tmpl_gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
            th, tw = scaled.shape[:2]
            if th <= 4 or tw <= 4:
                continue
            if th > screen_gray.shape[0] or tw > screen_gray.shape[1]:
                continue
            res = cv2.matchTemplate(screen_gray, scaled, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)
            if max_val > best_score:
                best_score = float(max_val)
                best_loc = max_loc
                best_scale = float(scale)

        if best_loc is None or best_scale is None or best_score < self.threshold:
            return None
        ref_x, ref_y, _, _ = anchor["ref_box"]
        return AnchorMatch(
            name=str(anchor["name"]),
            score=best_score,
            scale=best_scale,
            x=int(rx1 + best_loc[0]),
            y=int(ry1 + best_loc[1]),
            ref_x=int(ref_x),
            ref_y=int(ref_y),
        )

    def calibrate(self, screen) -> Optional[Transform]:
        if not self.enabled or cv2 is None or not self.anchors:
            self.status = "disabled" if not self.enabled else "unavailable"
            return None
        now = time.time()
        if now - self.last_attempt < 0.8 and self.transform is not None:
            return self.transform
        self.last_attempt = now

        h, w = screen.shape[:2]
        scale_guess = min(w / self.ref_w, h / self.ref_h)
        scales = [scale_guess * s for s in (0.85, 0.92, 1.0, 1.08, 1.15)]

        matches: List[AnchorMatch] = []
        for anchor in self.anchors:
            match = self._match_anchor(screen, anchor, scales)
            if match:
                matches.append(match)

        if not matches:
            # Retry once with a wider search window.
            for anchor in self.anchors:
                match = self._match_anchor(screen, anchor, scales, full_search=True)
                if match:
                    matches.append(match)

        if not matches:
            self.status = "no_match"
            return None

        total_weight = sum(m.score for m in matches) or 1.0
        scale = sum(m.scale * m.score for m in matches) / total_weight
        offsets_x = [m.x - (m.ref_x * scale) for m in matches]
        offsets_y = [m.y - (m.ref_y * scale) for m in matches]
        offset_x = float(sorted(offsets_x)[len(offsets_x) // 2])
        offset_y = float(sorted(offsets_y)[len(offsets_y) // 2])

        if scale < 0.5 or scale > 2.5:
            self.status = "bad_scale"
            return None

        # Sanity check: transformed anchor points must be on-screen.
        for m in matches:
            tx = int(round(m.ref_x * scale + offset_x))
            ty = int(round(m.ref_y * scale + offset_y))
            if tx < 0 or tx >= w or ty < 0 or ty >= h:
                self.status = "bad_transform"
                return None

        self.transform = Transform(scale=scale, offset_x=offset_x, offset_y=offset_y, anchors=matches)
        self.status = "ok"
        return self.transform

    def estimate_window_rect(self, screen, top_crop_px: int = 140) -> Optional[Tuple[int, int, int, int]]:
        if cv2 is None:
            return None
        h, w = screen.shape[:2]
        hsv = cv2.cvtColor(screen, cv2.COLOR_BGR2HSV)
        mask = (hsv[:, :, 1] > 50) & (hsv[:, :, 2] > 40)
        mask = mask.astype("uint8") * 255
        mask[: min(top_crop_px, h), :] = 0
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None
        cnt = max(contours, key=cv2.contourArea)
        x, y, bw, bh = cv2.boundingRect(cnt)
        if bw < int(w * 0.4) or bh < int(h * 0.3):
            return None
        return (x, y, x + bw, y + bh)

    def apply_point(self, point: Tuple[int, int]) -> Tuple[int, int]:
        if not self.transform:
            return point
        x, y = point
        scale = self.transform.scale
        return (
            int(round(x * scale + self.transform.offset_x)),
            int(round(y * scale + self.transform.offset_y)),
        )

    def region_rect(self, region_cfg: Dict[str, Tuple[float, float]], screen_shape: Tuple[int, int, int]) -> Tuple[int, int, int, int]:
        h, w = screen_shape[:2]
        if self.transform:
            rx1 = region_cfg["x_percent"][0] * self.ref_w
            rx2 = region_cfg["x_percent"][1] * self.ref_w
            ry1 = region_cfg["y_percent"][0] * self.ref_h
            ry2 = region_cfg["y_percent"][1] * self.ref_h
            x1 = int(round(rx1 * self.transform.scale + self.transform.offset_x))
            x2 = int(round(rx2 * self.transform.scale + self.transform.offset_x))
            y1 = int(round(ry1 * self.transform.scale + self.transform.offset_y))
            y2 = int(round(ry2 * self.transform.scale + self.transform.offset_y))
        else:
            x1 = int(w * region_cfg["x_percent"][0])
            x2 = int(w * region_cfg["x_percent"][1])
            y1 = int(h * region_cfg["y_percent"][0])
            y2 = int(h * region_cfg["y_percent"][1])

        min_w = max(10, int(w * 0.02))
        min_h = max(10, int(h * 0.02))
        x1 = max(0, min(w - 1, x1))
        x2 = max(1, min(w, x2))
        y1 = max(0, min(h - 1, y1))
        y2 = max(1, min(h, y2))
        if (x2 - x1) < min_w or (y2 - y1) < min_h:
            return 0, 0, 0, 0
        return x1, y1, x2, y2
