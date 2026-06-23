"""Tiny dependency-free SVG chart helpers (no CDN, works offline).

`line_chart` renders a labelled line chart; `sparkline` renders a compact
trend line. Both return an SVG string to drop into a template with |safe.
"""
from html import escape

# Theme colours (kept in sync with static/style.css)
_ACCENT = "#4f8cff"
_GRID = "#2c3852"
_TEXT = "#8c98b0"
_FILL = "rgba(79,140,255,0.12)"


def _fmt(v):
    f = float(v)
    return str(int(f)) if f == int(f) else f"{f:.1f}"


def line_chart(points, width=680, height=240, unit=""):
    """points: list of (label, value). Returns an SVG string."""
    if not points:
        return '<p class="muted small">No data yet — log a session to see progress.</p>'

    n = len(points)
    ml, mr, mt, mb = 48, 14, 16, 38
    iw, ih = width - ml - mr, height - mt - mb
    vals = [float(v) for _, v in points]
    vmax = max(vals) or 1.0

    def px(i):
        return ml + (iw * i / (n - 1) if n > 1 else iw / 2)

    def py(v):
        return mt + ih * (1 - v / vmax)

    parts = [
        f'<svg viewBox="0 0 {width} {height}" class="chart" '
        f'preserveAspectRatio="xMidYMid meet" role="img">'
    ]

    # Horizontal gridlines + y-axis labels (0, mid, max)
    for frac in (0, 0.5, 1):
        v = vmax * frac
        gy = py(v)
        parts.append(
            f'<line x1="{ml}" y1="{gy:.1f}" x2="{width - mr}" y2="{gy:.1f}" '
            f'stroke="{_GRID}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{ml - 6}" y="{gy + 4:.1f}" text-anchor="end" '
            f'font-size="11" fill="{_TEXT}">{_fmt(v)}</text>'
        )

    # Area fill + line (only meaningful with >1 point)
    coords = [(px(i), py(vals[i])) for i in range(n)]
    if n > 1:
        area = f"M{coords[0][0]:.1f},{py(0):.1f} " + " ".join(
            f"L{x:.1f},{y:.1f}" for x, y in coords
        ) + f" L{coords[-1][0]:.1f},{py(0):.1f} Z"
        parts.append(f'<path d="{area}" fill="{_FILL}" stroke="none"/>')
        poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in coords)
        parts.append(
            f'<polyline points="{poly}" fill="none" stroke="{_ACCENT}" '
            f'stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>'
        )

    # Points + value labels + x labels
    label_step = max(1, (n + 7) // 8)  # show ~8 x-labels max
    for i, (label, v) in enumerate(points):
        x, y = coords[i]
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" fill="{_ACCENT}"/>')
        parts.append(
            f'<text x="{x:.1f}" y="{y - 9:.1f}" text-anchor="middle" '
            f'font-size="10" fill="{_TEXT}">{_fmt(v)}</text>'
        )
        if i % label_step == 0 or i == n - 1:
            parts.append(
                f'<text x="{x:.1f}" y="{height - 12}" text-anchor="middle" '
                f'font-size="10" fill="{_TEXT}">{escape(str(label))}</text>'
            )

    if unit:
        parts.append(
            f'<text x="{ml}" y="12" font-size="10" fill="{_TEXT}">{escape(unit)}</text>'
        )
    parts.append("</svg>")
    return "".join(parts)


def sparkline(values, width=120, height=34):
    """Compact trend line from a list of numbers."""
    vals = [float(v) for v in values]
    if not vals:
        return ""
    n = len(vals)
    pad = 3
    iw, ih = width - 2 * pad, height - 2 * pad
    vmax = max(vals) or 1.0
    vmin = min(vals)
    span = (vmax - vmin) or 1.0

    def px(i):
        return pad + (iw * i / (n - 1) if n > 1 else iw / 2)

    def py(v):
        return pad + ih * (1 - (v - vmin) / span)

    coords = [(px(i), py(vals[i])) for i in range(n)]
    out = [f'<svg viewBox="0 0 {width} {height}" class="spark" preserveAspectRatio="none">']
    if n > 1:
        poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in coords)
        out.append(
            f'<polyline points="{poly}" fill="none" stroke="{_ACCENT}" '
            f'stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>'
        )
    lx, ly = coords[-1]
    out.append(f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="2.6" fill="{_ACCENT}"/>')
    out.append("</svg>")
    return "".join(out)
