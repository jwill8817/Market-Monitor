"""
Generate jaws.ico — crisp financial chart icon.
Renders each frame at 4× scale then downsamples with LANCZOS for clean edges.
"""
from PIL import Image, ImageDraw, ImageFont
import os, math

SIZES = [16, 32, 48, 64, 128, 256]
SCALE = 4          # render at 4× then downsample

# Palette
C_BG     = (13,  17,  23)       # #0d1117
C_CARD   = (28,  33,  40)       # #1c2128
C_CARD2  = (33,  38,  45)       # #21262d
C_BORDER = (48,  54,  61)       # #30363d
C_ACCENT = (247, 129, 102)      # #f78166  coral
C_GREEN  = (63,  185, 80)       # #3fb950
C_RED    = (248, 81,  73)       # #f85149
C_BLUE   = (88,  166, 255)      # #58a6ff
C_TEXT   = (230, 237, 243)      # #e6edf3
C_DIM    = (139, 148, 158)      # #8b949e


def _round_rect(draw, xy, r, fill=None, outline=None, width=1):
    x0, y0, x1, y1 = xy
    draw.rounded_rectangle([x0, y0, x1, y1], radius=r, fill=fill,
                            outline=outline, width=width)


def make_frame(size):
    S  = size * SCALE          # working canvas size
    r  = S // 7                # corner radius
    pad = S // 14

    img  = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # ── background ──────────────────────────────────────────────
    _round_rect(draw, [0, 0, S-1, S-1], r, fill=C_BG)

    # ── accent stripe at top (≈18 % height) ────────────────────
    stripe_h = int(S * 0.18)
    _round_rect(draw, [0, 0, S-1, stripe_h + r], r, fill=C_ACCENT)
    draw.rectangle([0, r, S-1, stripe_h], fill=C_ACCENT)

    # "JAWS" text inside stripe — only at ≥ 48px
    if size >= 48:
        font = None
        for fname in ["arialbd.ttf", "calibrib.ttf", "verdanab.ttf", "segoeui.ttf"]:
            try:
                font = ImageFont.truetype(f"C:/Windows/Fonts/{fname}",
                                          int(stripe_h * 0.72))
                break
            except Exception:
                pass
        if font:
            bb   = draw.textbbox((0, 0), "JAWS", font=font)
            tw, th = bb[2]-bb[0], bb[3]-bb[1]
            tx = (S - tw) // 2 - bb[0]
            ty = (stripe_h - th) // 2 - bb[1]
            draw.text((tx, ty), "JAWS", font=font, fill=C_BG)

    # ── chart area geometry ──────────────────────────────────────
    cx0 = pad
    cx1 = S - pad
    cy0 = stripe_h + pad
    cy1 = S - pad
    cw  = cx1 - cx0
    ch  = cy1 - cy0

    # subtle horizontal grid lines
    lw_grid = max(1, S // 180)
    for frac in (0.25, 0.5, 0.75):
        y = cy0 + int(ch * frac)
        draw.line([(cx0, y), (cx1, y)], fill=C_BORDER, width=lw_grid)

    # ── rising line chart ────────────────────────────────────────
    # 8 control points: dips early, strong rally into top-right
    raw_y = [0.72, 0.82, 0.65, 0.75, 0.55, 0.62, 0.35, 0.18]
    n     = len(raw_y)
    pts   = [(cx0 + cw * i // (n-1),
              cy0 + int(ch * v)) for i, v in enumerate(raw_y)]

    # filled area under the line
    poly = [(cx0, cy1)] + pts + [(cx1, cy1)]
    fill_col = (*C_GREEN[:3], 40)    # very transparent green
    draw.polygon(poly, fill=fill_col)

    # smooth the line with midpoint subdivision (1 pass) for anti-alias feel
    smooth = [pts[0]]
    for i in range(len(pts)-1):
        mx = (pts[i][0] + pts[i+1][0]) // 2
        my = (pts[i][1] + pts[i+1][1]) // 2
        smooth.append((mx, my))
        smooth.append(pts[i+1])
    lw_line = max(2, S // 36)
    draw.line(smooth, fill=C_GREEN, width=lw_line, joint="curve")

    # ── candlestick overlay (last 5 bars, right side) ───────────
    n_bars   = 5
    bar_zone = cw * 3 // 5         # right 60 % of chart width
    bar_w    = bar_zone // (n_bars * 3)
    bar_w    = max(bar_w, 3)
    spacing  = bar_zone // n_bars
    # (open_frac, close_frac, high_frac, low_frac, bull?)
    candles  = [
        (0.68, 0.55, 0.72, 0.52, True),
        (0.52, 0.60, 0.62, 0.50, False),
        (0.56, 0.45, 0.58, 0.42, True),
        (0.42, 0.32, 0.44, 0.30, True),
        (0.30, 0.18, 0.32, 0.16, True),
    ]
    lw_wick = max(1, S // 128)
    for i, (o, c, h, lo, bull) in enumerate(candles):
        cx  = cx0 + cw*2//5 + spacing*i + spacing//2
        oy  = cy0 + int(ch * o)
        cy_ = cy0 + int(ch * c)
        hy  = cy0 + int(ch * h)
        ly  = cy0 + int(ch * lo)
        col = C_GREEN if bull else C_RED
        draw.line([(cx, hy), (cx, ly)], fill=col, width=lw_wick)
        body_t = min(oy, cy_)
        body_b = max(oy, cy_) + max(1, S//96)
        draw.rectangle([cx-bar_w, body_t, cx+bar_w, body_b], fill=col)

    # ── glow dot at latest high point ───────────────────────────
    px, py = pts[-1]
    dr = max(3, S // 22)
    # outer glow ring
    draw.ellipse([px-dr*2, py-dr*2, px+dr*2, py+dr*2],
                 fill=(*C_GREEN[:3], 50))
    draw.ellipse([px-dr, py-dr, px+dr, py+dr],
                 fill=C_GREEN, outline=C_BG, width=max(1, S//96))

    # ── thin border around whole icon ───────────────────────────
    _round_rect(draw, [1, 1, S-2, S-2], r,
                outline=(*C_BORDER, 200), width=max(1, S//128))

    # ── downsample to target size ────────────────────────────────
    return img.resize((size, size), Image.LANCZOS)


frames = [make_frame(s) for s in SIZES]
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jaws.ico")
frames[0].save(out, format="ICO",
               sizes=[(s, s) for s in SIZES],
               append_images=frames[1:])
print(f"Icon saved: {out}")
