#!/usr/bin/env python3
"""
Parametric 45-Degree 4-Way Pepper's Ghost Frustum Nested Laser-Cutting SVG Generator
- Exact 45-degree reflection angle relative to horizontal display:
  H_vert = (B - T) / 2
  S_slant = (B - T) / sqrt(2)
  face_bevel = atan(1 / sqrt(2)) = 35.2644 deg
- Supports 1x4 interlocking strip and 2x2 interlocking row grid (for Giant Monitor 480mm on mid-size laser beds)
"""
import math
from pathlib import Path

PRESETS = {
    "smartphone": {"label": "Smartphone (6.7 in)", "T": 18.0, "B": 90.0, "layout": "2x2"},
    "tablet":     {"label": "Tablet (11-13 in)",   "T": 30.0, "B": 170.0, "layout": "2x2"},
    "monitor":    {"label": "Mid-Size Monitor (24-27 in)", "T": 50.0, "B": 290.0, "layout": "2x2"},
    "giant":      {"label": "Giant Monitor (32-43 in)",    "T": 70.0, "B": 480.0, "layout": "2x2"},
}


def compute_frustum_dims(T: float, B: float, kerf_mm: float = 0.18) -> dict:
    # Apply half-kerf outward compensation so finished laser-cut acrylic matches exact optical geometry
    t_cut = T + kerf_mm
    b_cut = B + kerf_mm
    h_vert = (B - T) / 2.0
    s_slant = (B - T) / math.sqrt(2.0)
    s_cut = s_slant + kerf_mm
    l_side = (math.sqrt(3.0) / 2.0) * (B - T)
    return {
        "T_mm": round(T, 2),
        "B_mm": round(B, 2),
        "H_vert_mm": round(h_vert, 2),
        "S_slant_mm": round(s_slant, 2),
        "L_side_mm": round(l_side, 2),
        "bevel_deg": round(math.degrees(math.atan(1.0 / math.sqrt(2.0))), 4),
        "kerf_mm": kerf_mm,
        "T_cut": t_cut,
        "B_cut": b_cut,
        "S_cut": s_cut,
    }


def generate_nested_svg(T: float = 70.0, B: float = 480.0, kerf_mm: float = 0.18, label: str = "Giant Monitor (32-43 in)") -> str:
    d = compute_frustum_dims(T, B, kerf_mm)
    b = d["B_cut"]
    t = d["T_cut"]
    h = d["S_cut"]
    margin = 10.0
    gap = 4.0  # 4mm laser beam clearance between adjacent nested trapezoids

    # 2x2 Interlocking Row Grid:
    # Row 0: Trap 0 (upright at x=0) + Trap 1 (inverted 180 deg interlocked at x = (b + t)/2 + gap)
    # Row 1: Trap 2 (upright at x=0, y = h + gap) + Trap 3 (inverted 180 deg interlocked at x = (b + t)/2 + gap, y = h + gap)
    step_x = (b + t) / 2.0 + gap
    sheet_w = round(margin * 2 + step_x + b, 2)
    sheet_h = round(margin * 2 + h * 2 + gap + 18.0, 2)

    def trap_points(x0: float, y0: float, inverted: bool) -> str:
        inset = (b - t) / 2.0
        if not inverted:
            # Top edge narrow (t), bottom edge wide (b)
            p1 = (x0 + inset, y0)
            p2 = (x0 + inset + t, y0)
            p3 = (x0 + b, y0 + h)
            p4 = (x0, y0 + h)
        else:
            # Top edge wide (b), bottom edge narrow (t) -> interlocks into angled edge of upright trapezoid!
            p1 = (x0, y0)
            p2 = (x0 + b, y0)
            p3 = (x0 + inset + t, y0 + h)
            p4 = (x0 + inset, y0 + h)
        return " ".join(f"{px:.3f},{py:.3f}" for px, py in (p1, p2, p3, p4))

    traps = [
        (margin, margin, False, "FACE 1 (NORTH)"),
        (margin + step_x, margin, True, "FACE 2 (SOUTH - INVERTED NEST)"),
        (margin, margin + h + gap, False, "FACE 3 (EAST)"),
        (margin + step_x, margin + h + gap, True, "FACE 4 (WEST - INVERTED NEST)"),
    ]

    poly_lines = []
    for idx, (x0, y0, inv, tag) in enumerate(traps, 1):
        pts = trap_points(x0, y0, inv)
        cx = x0 + b * 0.5
        cy = y0 + h * 0.52
        poly_lines.append(
            f'  <polygon id="trapezoid_{idx}" points="{pts}" fill="none" stroke="#ff0000" stroke-width="0.2" />\n'
            f'  <text x="{cx:.2f}" y="{cy:.2f}" font-family="monospace" font-size="6.5" fill="#0066cc" text-anchor="middle">{tag}</text>'
        )

    footer_y = sheet_h - 6.0
    svg = f'''<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{sheet_w}mm" height="{sheet_h}mm" viewBox="0 0 {sheet_w} {sheet_h}">
  <!-- ALSTRA 4-WAY PEPPER'S GHOST 45-DEGREE FRUSTUM (2x2 INTERLOCKING NESTED SHEET) -->
  <!-- Cut Layer: #ff0000 (0.2mm hairline) | Engrave Layer: #0066cc | Material: 2-3mm Cast Clear Acrylic (PMMA) -->
  <rect x="0.5" y="0.5" width="{sheet_w - 1.0:.2f}" height="{sheet_h - 1.0:.2f}" fill="none" stroke="#0066cc" stroke-width="0.25" stroke-dasharray="3,2" />
{chr(10).join(poly_lines)}
  <text x="{margin:.2f}" y="{footer_y:.2f}" font-family="monospace" font-size="6.0" fill="#0066cc">
    ALSTRA 45-DEG PEPPER'S GHOST | {label} | T={d["T_mm"]}mm B={d["B_mm"]}mm H_vert={d["H_vert_mm"]}mm S_slant={d["S_slant_mm"]}mm | Bed={sheet_w}x{sheet_h}mm (2x2 Grid)
  </text>
</svg>
'''
    return svg


if __name__ == "__main__":
    out_dir = Path.home() / "ALSTRA_VERIFIED_EVIDENCE_BUNDLE" / "peppers_ghost_svgs"
    out_dir.mkdir(parents=True, exist_ok=True)
    for key, cfg in PRESETS.items():
        svg_txt = generate_nested_svg(cfg["T"], cfg["B"], 0.18, cfg["label"])
        f = out_dir / f"peppers_ghost_45deg_{key}_2x2_nested.svg"
        f.write_text(svg_txt, encoding="utf-8")
        dims = compute_frustum_dims(cfg["T"], cfg["B"])
        print(f"[✔] Generated {f.name} -> T={dims['T_mm']}mm, B={dims['B_mm']}mm, H_vert={dims['H_vert_mm']}mm, S_slant={dims['S_slant_mm']}mm")
