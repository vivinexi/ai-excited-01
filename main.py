#!/usr/bin/env python3
"""The Wave That Is a Horse -- make.fun bounty ai-excited-01.

A program that draws ONE image (1024x1024 PNG) and writes it to
/output/entry.png: a giant ocean wave shaped like a galloping white
horse, a tiny surfer riding inside the curl, under an orange sunset.

Standard library only. No network, no downloaded assets, no external
files. Fully deterministic: the same code produces the same bytes on
every run.
"""

import math
import os
import random
import struct
import zlib

W = H = 1024

# ---------------------------------------------------------------- canvas
buf = bytearray(W * H * 3)


def set_px(x, y, r, g, b):
    if 0 <= x < W and 0 <= y < H:
        i = (y * W + x) * 3
        buf[i] = r
        buf[i + 1] = g
        buf[i + 2] = b


def lerp(c1, c2, t):
    return (
        int(c1[0] + (c2[0] - c1[0]) * t),
        int(c1[1] + (c2[1] - c1[1]) * t),
        int(c1[2] + (c2[2] - c1[2]) * t),
    )


def fill_rect(x0, y0, x1, y1, rgb):
    """Opaque axis-aligned rectangle, fast row slices."""
    x0 = max(0, int(x0))
    y0 = max(0, int(y0))
    x1 = min(W, int(x1))
    y1 = min(H, int(y1))
    if x1 <= x0 or y1 <= y0:
        return
    row = bytes(rgb) * (x1 - x0)
    for y in range(y0, y1):
        s = (y * W + x0) * 3
        buf[s:s + len(row)] = row


def vgrad(y0, y1, stops):
    """Vertical gradient. stops: list of (y, rgb) sorted by y."""
    for y in range(max(0, y0), min(H, y1)):
        # find surrounding stops
        for k in range(len(stops) - 1):
            ya, ca = stops[k]
            yb, cb = stops[k + 1]
            if ya <= y <= yb:
                t = 0.0 if yb == ya else (y - ya) / (yb - ya)
                c = lerp(ca, cb, t)
                break
        else:
            c = stops[-1][1] if y >= stops[-1][0] else stops[0][1]
        fill_rect(0, y, W, y + 1, c)


def hspan(y, x0, x1, rgb, alpha=1.0):
    """One horizontal span on row y, opaque or alpha-blended."""
    x0 = max(0, int(x0))
    x1 = min(W, int(x1))
    if x1 <= x0 or y < 0 or y >= H:
        return
    if alpha >= 1.0:
        row = bytes(rgb) * (x1 - x0)
        s = (y * W + x0) * 3
        buf[s:s + len(row)] = row
    else:
        r, g, b = rgb
        base = y * W * 3
        for x in range(x0, x1):
            i = base + x * 3
            buf[i] = int(buf[i] + (r - buf[i]) * alpha)
            buf[i + 1] = int(buf[i + 1] + (g - buf[i + 1]) * alpha)
            buf[i + 2] = int(buf[i + 2] + (b - buf[i + 2]) * alpha)


def fill_ellipse(cx, cy, rx, ry, rgb, alpha=1.0):
    """Filled ellipse, scanline by scanline."""
    rx = abs(rx)
    ry = abs(ry)
    if rx < 0.5 or ry < 0.5:
        return
    for dy in range(-int(ry), int(ry) + 1):
        y = int(cy) + dy
        if y < 0 or y >= H:
            continue
        t = dy / ry
        if abs(t) >= 1.0:
            continue
        dx = rx * math.sqrt(1.0 - t * t)
        hspan(y, cx - dx, cx + dx, rgb, alpha)


def fill_poly(pts, rgb, alpha=1.0):
    """Filled polygon (even-odd scanline fill)."""
    if len(pts) < 3:
        return
    ys = [p[1] for p in pts]
    y0 = max(0, int(math.floor(min(ys))))
    y1 = min(H - 1, int(math.ceil(max(ys))))
    n = len(pts)
    for y in range(y0, y1 + 1):
        xs = []
        for k in range(n):
            x1, y1p = pts[k]
            x2, y2p = pts[(k + 1) % n]
            if y1p == y2p:
                continue
            if (y1p <= y < y2p) or (y2p <= y < y1p):
                xs.append(x1 + (y - y1p) * (x2 - x1) / (y2p - y1p))
        if not xs:
            continue
        xs.sort()
        for k in range(0, len(xs) - 1, 2):
            hspan(y, xs[k], xs[k + 1], rgb, alpha)


def catmull_rom(pts, samples=10, closed=True):
    """Dense polyline through control points (Catmull-Rom spline)."""
    out = []
    n = len(pts)
    count = n if closed else n - 1
    for k in range(count):
        if closed:
            p0 = pts[(k - 1) % n]
            p1 = pts[k]
            p2 = pts[(k + 1) % n]
            p3 = pts[(k + 2) % n]
        else:
            p0 = pts[max(0, k - 1)]
            p1 = pts[k]
            p2 = pts[min(n - 1, k + 1)]
            p3 = pts[min(n - 1, k + 2)]
        for s in range(samples):
            t = s / samples
            t2 = t * t
            t3 = t2 * t
            x = 0.5 * ((2 * p1[0]) + (-p0[0] + p2[0]) * t
                       + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2
                       + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3)
            y = 0.5 * ((2 * p1[1]) + (-p0[1] + p2[1]) * t
                       + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2
                       + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3)
            out.append((x, y))
    return out


def smooth_poly(pts, rgb, alpha=1.0, samples=10):
    fill_poly(catmull_rom(pts, samples, closed=True), rgb, alpha)


def thick_line(pts, width, rgb, alpha=1.0):
    """A thick curved stroke: discs dropped at exact arc-length
    intervals along a smooth path, so the stroke is solid, not beaded."""
    path = catmull_rom(pts, samples=16, closed=False)
    if not path:
        return
    r = width / 2.0
    gap = max(2.0, r * 0.5)
    fill_ellipse(path[0][0], path[0][1], r, r, rgb, alpha)
    need = gap
    px, py = path[0]
    for (x, y) in path[1:]:
        dx, dy = x - px, y - py
        d = math.hypot(dx, dy)
        while d >= need:
            t = need / d
            nx = px + dx * t
            ny = py + dy * t
            fill_ellipse(nx, ny, r, r, rgb, alpha)
            px, py = nx, ny
            dx, dy = x - px, y - py
            d = math.hypot(dx, dy)
            need = gap
        need -= d
        px, py = x, y
    fill_ellipse(path[-1][0], path[-1][1], r, r, rgb, alpha)


def circle(cx, cy, r, rgb, alpha=1.0):
    fill_ellipse(cx, cy, r, r, rgb, alpha)


# ---------------------------------------------------------------- palette
SKY = [(0, (26, 16, 68)), (150, (94, 38, 140)), (280, (198, 52, 96)),
       (380, (244, 110, 40)), (430, (251, 191, 36))]
SEA = [(430, (21, 94, 117)), (560, (14, 116, 144)), (760, (12, 74, 110)),
       (1024, (8, 47, 73))]
WHITE = (248, 250, 252)
FOAM = (224, 242, 254)
SHADE = (186, 220, 240)
DEEP = (8, 47, 73)
WAVE_DARK = (12, 74, 110)
WAVE_MID = (14, 116, 144)
SUN_CORE = (255, 247, 204)
SUN_MID = (255, 209, 102)
GLOW = (249, 115, 22)
RIM = (253, 230, 138)
DARK = (15, 23, 42)

# ------------------------------------------------------------------- sky
def draw_sky():
    vgrad(0, 432, SKY)
    # sun glow: concentric translucent discs, top-right
    sx, sy = 920, 220
    for r, a in ((240, 0.10), (185, 0.14), (140, 0.20), (105, 0.30)):
        fill_ellipse(sx, sy, r, r, GLOW, a)
    fill_ellipse(sx, sy, 56, 56, SUN_MID, 1.0)
    fill_ellipse(sx, sy, 44, 44, SUN_CORE, 1.0)
    # a few high clouds, warm streaks
    for (cx, cy, rx, ry, a) in (
            (180, 120, 150, 14, 0.35), (220, 140, 110, 10, 0.30),
            (560, 90, 170, 12, 0.30), (880, 170, 120, 10, 0.35),
            (420, 200, 130, 9, 0.28)):
        fill_ellipse(cx, cy, rx, ry, (255, 170, 120), a)
    # birds: tiny dark chevrons
    for (bx, by, s) in ((300, 150, 10), (340, 130, 8), (660, 110, 9),
                        (700, 140, 7), (180, 210, 8)):
        thick_line([(bx - s, by + s * 0.4), (bx, by - s * 0.4),
                    (bx + s, by + s * 0.4)], 2.5, DARK, 0.85)

# ------------------------------------------------------------------- sea
def draw_sea():
    vgrad(430, 1024, SEA)
    # sun reflection: soft shimmering gold under the sun (right side)
    rng = random.Random(7)
    for k in range(30):
        y = 445 + k * 20
        w = 24 + k * 3.2
        x0 = 920 - w + rng.uniform(-10, 10)
        hspan(y, x0, x0 + 2 * w, (251, 191, 36), 0.10 + 0.08 * rng.random())
        hspan(y + 5, x0 + 12, x0 + 2 * w - 12, (253, 230, 138), 0.08)

# ------------------------------------------------------------------ wave
def draw_wave():
    # the big wave wall on the left: deep teal mass, crest high left,
    # its right edge curving down so the right side stays open sea
    wall = [(0, 450), (80, 370), (180, 300), (300, 275), (420, 300),
            (520, 350), (600, 420), (650, 520), (630, 650), (560, 820),
            (460, 1024), (0, 1024)]
    smooth_poly(wall, WAVE_DARK, 1.0, samples=12)
    # lighter face on the wall
    face = [(0, 480), (100, 395), (210, 325), (330, 300), (450, 325),
            (550, 375), (620, 450), (635, 540), (600, 680), (520, 860),
            (430, 1024), (0, 1024)]
    smooth_poly(face, WAVE_MID, 0.55, samples=12)
    # bright foam lip along the top edge of the wall
    lip = [(0, 450), (80, 370), (180, 300), (300, 275), (420, 300),
           (520, 350), (600, 420)]
    thick_line(lip, 13, FOAM, 0.9)
    thick_line(lip, 6, WHITE, 0.95)
    # the curling lip: tube arching over the barrel, top-left
    curl = [(60, 380), (120, 300), (230, 268), (340, 285), (400, 340)]
    thick_line(curl, 42, WAVE_MID, 1.0)
    thick_line(curl, 30, FOAM, 0.85)
    thick_line(curl, 16, WHITE, 0.9)
    # barrel mouth: dark opening under the curl (surfer rides inside)
    fill_ellipse(175, 485, 105, 78, DEEP, 1.0)
    fill_ellipse(175, 480, 85, 58, (10, 60, 90), 1.0)
    # inner glow at the back of the barrel
    fill_ellipse(160, 490, 45, 28, (56, 189, 248), 0.35)

# ------------------------------------------------------------------ horse
HORSE_OUTLINE = [
    (965, 385), (930, 350), (895, 322), (862, 312),   # nose -> forehead -> poll
    (795, 250), (695, 232), (600, 258),               # high-arched crest
    (530, 335), (430, 358), (350, 375),               # withers dip -> back
    (295, 415), (268, 475),                           # croup -> rear
    (255, 570), (228, 665), (205, 745),               # hind leg, extended back
    (195, 760), (218, 770),                           # hind hoof
    (252, 675), (275, 585),                           # hind leg front edge
    (305, 625), (420, 645), (530, 640), (605, 612),   # belly -> chest bottom
    (675, 685), (765, 745), (808, 765), (825, 752),   # front leg, extended
    (775, 698), (700, 638),                           # front leg back edge
    (648, 562), (640, 472), (695, 402), (775, 365),   # chest -> throat
    (845, 362), (858, 378), (905, 392),               # jaw -> chin
]


def draw_horse():
    # soft drop shadow so the white pops off the blue wall
    shadow = [(x + 10, y + 14) for (x, y) in HORSE_OUTLINE]
    smooth_poly(shadow, (6, 40, 64), 0.45, samples=10)
    # main body, white foam
    smooth_poly(HORSE_OUTLINE, WHITE, 1.0, samples=12)
    # second (far) legs, slightly shaded, for depth
    fill_poly([(650, 620), (700, 690), (760, 740), (775, 750), (725, 695),
               (675, 635)], SHADE, 1.0)
    fill_poly([(295, 555), (270, 645), (240, 725), (255, 737), (285, 650),
               (310, 575)], SHADE, 1.0)
    # cool shading along the belly and under the neck
    thick_line([(325, 618), (440, 647), (555, 635)], 22, SHADE, 0.5)
    thick_line([(655, 505), (705, 435), (775, 372)], 15, SHADE, 0.45)
    # warm sunset rim light along the crest and back
    thick_line([(862, 312), (795, 250), (695, 232), (600, 258), (530, 335),
                (430, 358)], 7, RIM, 0.85)
    thick_line([(895, 322), (930, 350), (965, 385)], 6, RIM, 0.8)
    # ears: two pointed triangles at the poll
    fill_poly([(845, 318), (855, 272), (875, 312)], WHITE, 1.0)
    fill_poly([(868, 310), (887, 278), (897, 315)], WHITE, 1.0)
    # eye: dark, with a spark of light
    circle(888, 340, 8, DARK, 1.0)
    circle(890, 338, 3, WHITE, 1.0)
    # nostril
    circle(948, 372, 4, DARK, 0.8)
    # mane: wind-blown white streaks anchored on the high crest,
    # sweeping back over the sky, plus short strands falling down the neck
    for (pts, wd) in (
            ([(800, 258), (680, 210), (540, 195), (420, 210)], 14),
            ([(750, 262), (620, 215), (480, 200), (360, 220)], 10),
            ([(700, 268), (580, 225), (450, 215), (340, 240)], 7),
            ([(650, 255), (600, 300), (560, 340)], 8),
            ([(720, 250), (680, 300), (640, 340)], 7)):
        thick_line(pts, wd, WHITE, 0.95)
        thick_line(pts, wd * 0.45, FOAM, 0.9)
    # tail: a solid tapered spray tail from the rump toward the barrel,
    # plus one thin trailing streak
    smooth_poly([(275, 455), (200, 465), (130, 515), (95, 585), (90, 600),
                 (130, 595), (185, 540), (245, 495), (290, 475)],
                WHITE, 0.92, samples=10)
    thick_line([(280, 490), (210, 520), (160, 565), (140, 610)], 6, WHITE, 0.9)
    # foam streaks along the body (wave texture)
    for (pts, wd, a) in (
            ([(360, 460), (500, 445), (620, 465)], 8, 0.6),
            ([(350, 530), (490, 520), (620, 540)], 7, 0.55),
            ([(390, 595), (520, 590), (620, 605)], 7, 0.5)):
        thick_line(pts, wd, FOAM, a)
    # small spray bursts from the hooves (tight, fine dots only)
    rng = random.Random(42)
    for (hx, hy) in ((210, 758), (822, 755), (775, 752)):
        for _ in range(12):
            ang = rng.uniform(0, math.pi * 2)
            dist = rng.uniform(3, 24)
            r = rng.uniform(1.0, 2.6)
            circle(hx + math.cos(ang) * dist,
                   hy + math.sin(ang) * dist * 0.7 - rng.uniform(0, 11),
                   r, WHITE, rng.uniform(0.5, 0.95))
    # fine spray off the crest
    for _ in range(12):
        x = rng.uniform(450, 720)
        y = rng.uniform(200, 240)
        circle(x, y, rng.uniform(1.0, 2.4), WHITE, rng.uniform(0.4, 0.9))

# ----------------------------------------------------------------- surfer
def draw_surfer():
    # tiny dark figure on a white board, inside the barrel mouth
    bx, by = 175, 500
    # board
    thick_line([(bx - 34, by + 14), (bx + 34, by - 6)], 7, WHITE, 1.0)
    # legs (crouched)
    thick_line([(bx - 4, by - 2), (bx - 12, by - 26), (bx - 2, by - 34)],
               5, DARK, 1.0)
    thick_line([(bx + 6, by - 4), (bx + 14, by - 24), (bx + 4, by - 34)],
               5, DARK, 1.0)
    # torso + arms out for balance
    thick_line([(bx - 2, by - 34), (bx + 2, by - 62)], 7, DARK, 1.0)
    thick_line([(bx + 1, by - 52), (bx - 26, by - 62)], 5, DARK, 1.0)
    thick_line([(bx + 1, by - 52), (bx + 28, by - 66)], 5, DARK, 1.0)
    # head
    circle(bx + 2, by - 70, 7, DARK, 1.0)
    # spray trail behind the board
    rng = random.Random(99)
    for _ in range(18):
        circle(bx - 40 - rng.uniform(0, 46), by + 8 - rng.uniform(0, 14),
               rng.uniform(1.5, 4), WHITE, rng.uniform(0.5, 0.9))

# -------------------------------------------------------------- foreground
def draw_foreground():
    # soft white wash and fine foam at the bottom of the frame
    rng = random.Random(5)
    for _ in range(40):
        x = rng.uniform(0, 1024)
        y = rng.uniform(945, 1024)
        circle(x, y, rng.uniform(1.0, 3.5), WHITE, rng.uniform(0.15, 0.45))
    thick_line([(0, 985), (250, 968), (520, 982), (780, 965), (1024, 980)],
               16, WHITE, 0.45)
    thick_line([(0, 1005), (300, 992), (600, 1004), (1024, 994)],
               10, FOAM, 0.4)

# --------------------------------------------------------------------- png
def _chunk(typ, data):
    return (struct.pack(">I", len(data)) + typ + data
            + struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF))


def write_png(path, pixels, w, h):
    raw = bytearray()
    stride = w * 3
    for y in range(h):
        raw.append(0)  # filter: None
        raw += pixels[y * stride:(y + 1) * stride]
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n"
    png += _chunk(b"IHDR", ihdr)
    png += _chunk(b"IDAT", zlib.compress(bytes(raw), 6))
    png += _chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)
    return len(png)


def main():
    outdir = os.environ.get("MAKEFUN_OUTPUT_DIR") or "/output"
    os.makedirs(outdir, exist_ok=True)
    draw_sky()
    draw_sea()
    draw_wave()
    draw_horse()
    draw_surfer()
    draw_foreground()
    n = write_png(os.path.join(outdir, "entry.png"), buf, W, H)
    print(f"wrote {os.path.join(outdir, 'entry.png')} ({n} bytes, {W}x{H})")


if __name__ == "__main__":
    main()
