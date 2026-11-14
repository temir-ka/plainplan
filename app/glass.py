"""Stained-glass SVG generator: a jittered grid split into translucent facets."""
import random

PALETTE = ["#7C4DFF", "#B08CFF", "#D95BD0", "#3FD2C7", "#FFB65C", "#5B7CFF"]


def stained_glass(w=1200, h=700, cols=8, rows=5, seed=7, alpha=0.5, lead=0.22):
    rnd = random.Random(seed)
    cw, ch = w / cols, h / rows
    pts = [[(c * cw + (rnd.uniform(-.32, .32) * cw if 0 < c < cols else 0)),
            (r * ch + (rnd.uniform(-.32, .32) * ch if 0 < r < rows else 0))] for r in range(rows + 1) for c in range(cols + 1)]
    idx = lambda r, c: r * (cols + 1) + c
    polys = []
    for r in range(rows):
        for c in range(cols):
            a, b, d, e = pts[idx(r, c)], pts[idx(r, c + 1)], pts[idx(r + 1, c + 1)], pts[idx(r + 1, c)]
            tris = [(a, b, d), (a, d, e)] if rnd.random() < .5 else [(a, b, e), (b, d, e)]
            for t in tris:
                col = rnd.choice(PALETTE)
                op = round(rnd.uniform(.12, alpha), 2)
                pp = " ".join(f"{x:.0f},{y:.0f}" for x, y in t)
                polys.append(f'<polygon points="{pp}" fill="{col}" fill-opacity="{op}" stroke="rgba(255,255,255,{lead})" stroke-width="1.2"/>')
    return (f'<svg class="glass-svg" viewBox="0 0 {w} {h}" preserveAspectRatio="xMidYMid slice" aria-hidden="true">'
            + "".join(polys) + "</svg>")
