"""Render the Perfect Store wheel as an inline SVG whose wedges reflect live
pipeline progress:  pending (faint) -> running (amber pulse) -> done (full colour).
"""

from __future__ import annotations

import math

from gui.steps import WEDGES

_C = 300.0                      # canvas centre
_R_CORE = 68.0                  # centre disc
_R_IN0, _R_IN1 = 72.0, 108.0   # thin accent ring
_R_OUT0, _R_OUT1 = 116.0, 246.0  # thick status ring
_R_LABEL = 182.0               # wedge title anchor
_R_GLYPH = 232.0               # status glyph anchor
_R_BAND = 270.0                # outer group-band label anchor
_N = len(WEDGES)
_SPAN = 360.0 / _N
_START = -90.0 - _SPAN / 2.0   # centre wedge 0 on the top-right diagonal

_FILL_OP = {"pending": 0.14, "running": 0.60, "done": 1.0}
_GLYPH = {"pending": "○", "running": "◐", "done": "✓"}   # ○ ◐ ✓


def _pol(r: float, deg: float) -> tuple[float, float]:
    a = math.radians(deg)
    return _C + r * math.cos(a), _C + r * math.sin(a)


def _sector(r_in: float, r_out: float, a0: float, a1: float, pad: float = 1.3) -> str:
    a0, a1 = a0 + pad, a1 - pad
    x0o, y0o = _pol(r_out, a0)
    x1o, y1o = _pol(r_out, a1)
    x1i, y1i = _pol(r_in, a1)
    x0i, y0i = _pol(r_in, a0)
    large = 1 if (a1 - a0) > 180 else 0
    return (
        f"M {x0o:.2f} {y0o:.2f} "
        f"A {r_out:.2f} {r_out:.2f} 0 {large} 1 {x1o:.2f} {y1o:.2f} "
        f"L {x1i:.2f} {y1i:.2f} "
        f"A {r_in:.2f} {r_in:.2f} 0 {large} 0 {x0i:.2f} {y0i:.2f} Z"
    )


def _wrap(text: str, width: int = 15) -> list[str]:
    lines, cur = [], ""
    for w in text.split():
        if cur and len(cur) + 1 + len(w) > width:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return lines[:3]


def wedge_status(steps_status: dict, wedge: dict, run_active: bool, run_done: bool) -> str:
    """Collapse a wedge's member step statuses into one of pending/running/done."""
    if not wedge["steps"]:                       # Execution & Tracking
        return "done" if run_done else ("running" if run_active else "pending")
    sts = [steps_status.get(s, "pending") for s in wedge["steps"]]
    if all(s == "done" for s in sts):
        return "done"
    if any(s in ("running", "done") for s in sts):
        return "running"
    return "pending"


def build_wheel_svg(steps_status: dict, run_active: bool = False,
                    run_done: bool = False) -> str:
    parts: list[str] = [
        f'<svg viewBox="0 0 600 600" width="100%" xmlns="http://www.w3.org/2000/svg" '
        f'font-family="Inter, Segoe UI, Helvetica, Arial, sans-serif">',
        '<rect width="600" height="600" fill="none"/>',
    ]

    for i, wedge in enumerate(WEDGES):
        a0 = _START + i * _SPAN
        a1 = a0 + _SPAN
        mid = (a0 + a1) / 2.0
        status = wedge_status(steps_status, wedge, run_active, run_done)
        op = _FILL_OP[status]
        color = wedge["color"]

        # thin accent ring
        parts.append(
            f'<path d="{_sector(_R_IN0, _R_IN1, a0, a1, pad=1.6)}" fill="{color}" '
            f'fill-opacity="{min(op + 0.15, 1.0):.2f}"/>'
        )

        # thick status wedge
        pulse = ""
        if status == "running":
            pulse = ('<animate attributeName="fill-opacity" '
                     'values="0.35;0.78;0.35" dur="1.4s" repeatCount="indefinite"/>')
        parts.append(
            f'<path d="{_sector(_R_OUT0, _R_OUT1, a0, a1)}" fill="{color}" '
            f'fill-opacity="{op:.2f}" stroke="#ffffff" stroke-width="4">{pulse}</path>'
        )

        # wedge title (rotated tangential, auto-flip on the lower half)
        tx, ty = _pol(_R_LABEL, mid)
        rot = mid + 90.0
        if 90.0 < (rot % 360.0) < 270.0:
            rot += 180.0
        text_fill = "#ffffff" if status != "pending" else "#5b6b7a"
        lines = _wrap(wedge["title"].upper())
        dy0 = -(len(lines) - 1) * 8.5
        tspans = "".join(
            f'<tspan x="0" dy="{(0 if k == 0 else 17):.0f}">{ln}</tspan>'
            for k, ln in enumerate(lines)
        )
        parts.append(
            f'<g transform="translate({tx:.2f} {ty:.2f}) rotate({rot:.2f})">'
            f'<text text-anchor="middle" y="{dy0:.0f}" font-size="13" '
            f'font-weight="700" letter-spacing="0.5" fill="{text_fill}">{tspans}</text>'
            f'</g>'
        )

        # status glyph near the outer rim
        gx, gy = _pol(_R_GLYPH, mid)
        parts.append(
            f'<text x="{gx:.2f}" y="{gy:.2f}" text-anchor="middle" '
            f'dominant-baseline="central" font-size="20" font-weight="700" '
            f'fill="{"#ffffff" if status != "pending" else "#9aa7b2"}">{_GLYPH[status]}</text>'
        )

        # outer group band label (once per distinct band, at its first wedge)
        if i == 0 or WEDGES[i - 1]["band"] != wedge["band"]:
            span_wedges = [w for w in WEDGES if w["band"] == wedge["band"]]
            first_idx = WEDGES.index(span_wedges[0])
            last_idx = WEDGES.index(span_wedges[-1])
            b_mid = _START + (first_idx + last_idx + 1) / 2.0 * _SPAN
            bx, by = _pol(_R_BAND, b_mid)
            brot = b_mid + 90.0
            if 90.0 < (brot % 360.0) < 270.0:
                brot += 180.0
            parts.append(
                f'<g transform="translate({bx:.2f} {by:.2f}) rotate({brot:.2f})">'
                f'<text text-anchor="middle" font-size="12" font-weight="700" '
                f'letter-spacing="2" fill="#8895a1">{wedge["band"]}</text></g>'
            )

    # centre disc
    parts.append(
        f'<circle cx="{_C}" cy="{_C}" r="{_R_CORE}" fill="#ffffff" '
        f'stroke="#d7dde2" stroke-width="2"/>'
    )
    parts.append(
        f'<text x="{_C}" y="{_C - 8}" text-anchor="middle" font-size="19" '
        f'font-weight="800" fill="#1b3a5c" letter-spacing="1">PERFECT</text>'
    )
    parts.append(
        f'<text x="{_C}" y="{_C + 14}" text-anchor="middle" font-size="19" '
        f'font-weight="800" fill="#1b3a5c" letter-spacing="1">STORE</text>'
    )

    parts.append('</svg>')
    return "".join(parts)
