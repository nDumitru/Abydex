#!/usr/bin/env python3
"""Generates the Abydex icon (original artwork): a portal ring made of circuit traces and
nodes, with a pyramid built from 3D-print layers inside (Abydos / Egypt + layer-by-layer
printing). Writes abydex/webui/static/abydex.svg; PNG/ICO are made by scripts/render_icon.js.
"""
import math
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "abydex" / "webui" / "static" / "abydex.svg"
ACC = "#ff7a1a"     # copper
GLOW = "#3fa9ff"    # portal light
BG = "#15181c"
C, R = 256, 156     # ring center / radius


def svg() -> str:
    # circuit pins around the ring: short radial traces ending in nodes, 45-degree kinks
    pins, nodes = [], []
    for k in range(12):
        a = math.radians(90 + k * 30 + 15)
        x1, y1 = C + R * math.cos(a), C - R * math.sin(a)
        x2, y2 = C + (R + 30) * math.cos(a), C - (R + 30) * math.sin(a)
        if k % 2:  # every other pin turns, like a PCB trace
            a2 = a + math.radians(9)
            x2, y2 = C + (R + 36) * math.cos(a2), C - (R + 36) * math.sin(a2)
            xm, ym = C + (R + 19) * math.cos(a), C - (R + 19) * math.sin(a)
            pins.append(f'    <polyline points="{x1:.0f},{y1:.0f} {xm:.0f},{ym:.0f} {x2:.0f},{y2:.0f}"/>')
        else:
            pins.append(f'    <line x1="{x1:.0f}" y1="{y1:.0f}" x2="{x2:.0f}" y2="{y2:.0f}"/>')
        nodes.append(f'    <circle cx="{x2:.0f}" cy="{y2:.0f}" r="10"/>')

    # pyramid made of print layers (bottom -> top)
    layers = []
    base_y, h, gap = 322, 20, 8
    for i, w in enumerate((212, 168, 124, 80, 36)):
        y = base_y - i * (h + gap)
        layers.append(f'  <rect x="{C - w / 2}" y="{y}" width="{w}" height="{h}" rx="6" fill="{ACC}" '
                      f'opacity="{0.55 + i * 0.1:.2f}"/>')
    apex_y = base_y - 4 * (h + gap)
    # light traces from the apex to the ring
    rays = "\n".join(
        f'    <polyline points="{C},{apex_y - 14} {C + dx},{apex_y - 14 - abs(dx)} {C + dx},{yy}"/>'
        for dx, yy in ((-52, 128), (0, 108), (52, 128)))

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512">
  <title>Abydex</title>
  <defs>
    <radialGradient id="g" cx="50%" cy="50%" r="50%">
      <stop offset="0" stop-color="{GLOW}" stop-opacity="0.35"/>
      <stop offset="1" stop-color="{GLOW}" stop-opacity="0.04"/>
    </radialGradient>
  </defs>
  <rect width="512" height="512" rx="112" fill="{BG}"/>
  <circle cx="{C}" cy="{C}" r="{R - 12}" fill="url(#g)"/>
  <g fill="none" stroke="{ACC}" stroke-width="10" stroke-linecap="round" stroke-linejoin="round">
{chr(10).join(pins)}
  </g>
  <circle cx="{C}" cy="{C}" r="{R}" fill="none" stroke="{ACC}" stroke-width="20"/>
  <circle cx="{C}" cy="{C}" r="{R - 20}" fill="none" stroke="{ACC}" stroke-width="4" opacity="0.6"/>
  <g fill="none" stroke="{GLOW}" stroke-width="8" stroke-linecap="round" stroke-linejoin="round" opacity="0.9">
{rays}
  </g>
{chr(10).join(layers)}
  <g fill="{BG}" stroke="{ACC}" stroke-width="7">
{chr(10).join(nodes)}
  </g>
</svg>
'''


if __name__ == "__main__":
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(svg(), encoding="utf-8")
    print(OUT)
