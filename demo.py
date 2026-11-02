#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
人类是 Bug，时间是变量 —— Phase 1

三个对照组：
    A  纯循环          一个闭合的圆，没有之前，也没有之后
    B  只有耗散        有方向了，但螺旋会停
    C  耗散 + 记忆 + Hook   有方向，而且停不下来

只用 Python 标准库，输出三张 SVG 和一份 metrics.json。
"""

from __future__ import annotations

import html
import json
import math
import random
from dataclasses import dataclass
from pathlib import Path

# ---------------------------------------------------------------- 参数

ROOT = Path(__file__).resolve().parent
FIG_DIR = ROOT / "figures"

STEPS = 720
OMEGA0 = 0.18          # 每步转过的角度
GAMMA = 0.018          # 每步的耗散比例
THETA = 0.22           # Hook 阈值：半径掉到这里以下，就被踢一下
KICK = 0.82            # Hook 的踢力
GOLDEN = 2.399963229728653
SEED = 20261102

SYMBOLS = ("慢", "稳", "快")
DELTA = {"慢": -1, "稳": 0, "快": 1}

# Phase 1 只实现 external。Phase 2 在这里加 internal：
# 符号不再从 rng 里抽，而是从记忆里长出来。
HOOK_SOURCE = "external"

PAPER = "#F7F3EC"
INK = "#2F2B27"
MUTED = "#7A7168"
FAINT = "#DCD3C5"
GRID = "#E6DFD3"
BLUE = "#7D8FA9"
SAGE = "#93A38C"
SAGE_LINE = "#788B70"
CLAY = "#B78E6E"
ROSE = "#C8A9A4"

EPOCH_COLORS = ["#6F829E", "#7F9178", "#B78E6E", "#C8A9A4", "#8FA3A8", "#A8A48E"]

SANS = "'Noto Sans SC','Noto Sans CJK SC','PingFang SC','Microsoft YaHei',sans-serif"
SERIF = "'Noto Serif SC','Noto Serif CJK SC','Songti SC',SimSun,serif"


# ---------------------------------------------------------------- 模拟

@dataclass
class Run:
    mode: str
    xs: list[float]
    ys: list[float]
    taus: list[float]
    omegas: list[float]
    epochs: list[int]
    hooks: list[dict]
    symbols: list[str]


def draw_hook_symbol(rng: random.Random, memory: list[str],
                     source: str = HOOK_SOURCE) -> str:
    """Phase 1：从外面拿一个符号。

    Phase 2 在这里加 "internal" 分支：把 memory 压成一个新符号，
    让 Hook 从循环内部长出来。
    """
    if source == "external":
        return rng.choices(SYMBOLS, weights=(0.4, 0.2, 0.4))[0]
    raise NotImplementedError("Phase 2：内部 Hook 还没有实现")


def simulate(mode: str, hook_source: str = HOOK_SOURCE) -> Run:
    rng = random.Random(SEED + {"A": 1, "B": 2, "C": 3}[mode])
    x, y = 1.0, 0.0
    omega = OMEGA0
    tau = 0.0
    xs, ys, taus, omegas = [x], [y], [tau], [omega]
    epochs = [0]
    hooks: list[dict] = []
    symbols: list[str] = []

    for t in range(STEPS):
        r = math.hypot(x, y)

        # Hook：只发生在 C 组。掉到阈值以下，就从外面拿一个符号，
        # 把状态踢出去，同时改写下一步的节律。
        if mode == "C" and r < THETA:
            symbol = draw_hook_symbol(rng, symbols, hook_source)
            d = DELTA[symbol]
            k = len(symbols) + 1
            phi = math.atan2(y, x) + GOLDEN + d * 0.45
            x += KICK * math.cos(phi)
            y += KICK * math.sin(phi)
            omega = OMEGA0 + d * 0.14
            symbols.append(symbol)
            hooks.append({"step": t, "x": x, "y": y, "symbol": symbol, "k": k})
            r = math.hypot(x, y)

        # 耗散：A 组不收缩，B/C 每步缩一点
        r_new = r if mode == "A" else r * (1.0 - GAMMA)

        # 旋转
        if r > 1e-9:
            ca, sa = math.cos(omega), math.sin(omega)
            ux, uy = x / r, y / r
            x = r_new * (ux * ca - uy * sa)
            y = r_new * (ux * sa + uy * ca)
        else:
            x = y = 0.0

        # 累积耗散：只增不减，是三维图里的“高度”
        if mode != "A":
            tau += GAMMA * r * r

        xs.append(x)
        ys.append(y)
        taus.append(tau)
        omegas.append(omega)
        epochs.append(len(symbols))

    return Run(mode, xs, ys, taus, omegas, epochs, hooks, symbols)


def _bin(x: float, y: float, bins: int = 48, lo: float = -1.2, hi: float = 1.2):
    bx = int((x - lo) / (hi - lo) * bins)
    by = int((y - lo) / (hi - lo) * bins)
    if 0 <= bx < bins and 0 <= by < bins:
        return bx, by
    return None


def compute_metrics(run: Run) -> dict:
    n = len(run.xs)
    start = int(n * 0.75)
    mean_r = sum(math.hypot(run.xs[i], run.ys[i]) for i in range(start, n)) / (n - start)

    seen: set[tuple[int, int]] = set()
    for i in range(n):
        b = _bin(run.xs[i], run.ys[i])
        if b is not None:
            seen.add(b)
    coverage = len(seen) / (48 * 48)

    # “末段新态”：末段 25% 里，与更早所有状态的距离都大于 0.02 的比例。
    # 用距离而不是网格，避免圆上的采样点因为网格边界被误判成“新”。
    eps = 0.02
    new_last = 0
    for i in range(start, n):
        dmin = min(
            math.hypot(run.xs[i] - run.xs[j], run.ys[i] - run.ys[j])
            for j in range(start)
        )
        if dmin > eps:
            new_last += 1

    return {
        "mean_radius_last": mean_r,
        "coverage": coverage,
        "novelty_last": new_last / (n - start),
        "omega_span": max(run.omegas) - min(run.omegas),
        "tau_final": run.taus[-1],
        "hooks": len(run.hooks),
    }


# ---------------------------------------------------------------- 颜色与 SVG 工具

def _rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _hex(rgb: tuple[float, float, float]) -> str:
    return "#%02X%02X%02X" % tuple(max(0, min(255, int(round(v)))) for v in rgb)


def mix(c1: str, c2: str, t: float) -> str:
    a, b = _rgb(c1), _rgb(c2)
    t = max(0.0, min(1.0, t))
    return _hex(tuple(a[i] + (b[i] - a[i]) * t for i in range(3)))


def svg_start(w: int, h: int) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}" role="img">'
    )


def bg(w: int, h: int) -> str:
    return f'<rect width="{w}" height="{h}" fill="{PAPER}"/>'


def line(x1, y1, x2, y2, stroke, width=1.0, opacity=1.0, dash=None) -> str:
    attrs = (
        f'x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" '
        f'stroke="{stroke}" stroke-width="{width}" stroke-linecap="round" opacity="{opacity}"'
    )
    if dash:
        attrs += f' stroke-dasharray="{dash}"'
    return f"<line {attrs}/>"


def circle(cx, cy, r, fill="none", stroke="none", width=1.0, opacity=1.0, dash=None) -> str:
    attrs = (
        f'cx="{cx:.2f}" cy="{cy:.2f}" r="{r:.2f}" fill="{fill}" '
        f'stroke="{stroke}" stroke-width="{width}" opacity="{opacity}"'
    )
    if dash:
        attrs += f' stroke-dasharray="{dash}"'
    return f"<circle {attrs}/>"


def text(x, y, s, size=12, fill=INK, family="sans", anchor="start",
         weight="normal", opacity=1.0, letter_spacing=None) -> str:
    fam = SANS if family == "sans" else SERIF
    attrs = (
        f'x="{x:.2f}" y="{y:.2f}" font-family="{fam}" font-size="{size}" '
        f'fill="{fill}" text-anchor="{anchor}" font-weight="{weight}" opacity="{opacity}"'
    )
    if letter_spacing:
        attrs += f' letter-spacing="{letter_spacing}"'
    return f"<text {attrs}>{html.escape(s)}</text>"


def polyline(points, stroke, width=1.8, opacity=0.95) -> str:
    pts = " ".join(f"{x:.2f},{y:.2f}" for x, y in points)
    return (
        f'<polyline points="{pts}" fill="none" stroke="{stroke}" '
        f'stroke-width="{width}" stroke-linejoin="round" stroke-linecap="round" opacity="{opacity}"/>'
    )


# ---------------------------------------------------------------- 投影

def fit_2d(box, extent=1.15):
    x0, y0, w, h = box
    s = min(w, h) / (2 * extent) * 0.92
    cx, cy = x0 + w / 2, y0 + h / 2
    return lambda x, y: (cx + x * s, cy - y * s)


class Camera:
    def __init__(self, az=-0.62, el=0.38, z_stretch=1.45):
        self.az, self.el = az, el
        self.z_stretch = z_stretch
        self.right = (-math.sin(az), math.cos(az), 0.0)
        self.up = (
            -math.cos(az) * math.sin(el),
            -math.sin(az) * math.sin(el),
            math.cos(el),
        )
        self.forward = (
            math.cos(az) * math.cos(el),
            math.sin(az) * math.cos(el),
            math.sin(el),
        )

    def raw(self, x, y, z, zmax):
        X = x / 1.15
        Y = y / 1.15
        Z = (z / zmax) * self.z_stretch if zmax > 0 else 0.0
        sx = X * self.right[0] + Y * self.right[1] + Z * self.right[2]
        sy = -(X * self.up[0] + Y * self.up[1] + Z * self.up[2])
        depth = X * self.forward[0] + Y * self.forward[1] + Z * self.forward[2]
        return sx, sy, depth


def nice_ticks(ymax: float) -> list[float]:
    if ymax >= 6:
        return [0, 2, 4, 6]
    if ymax >= 2:
        return [0, 1, 2]
    if ymax >= 1:
        return [0, 0.5, 1.0]
    return [0, 0.2, 0.4]


def fit_camera(cam: Camera, zmax, box, extent=1.24):
    x0, y0, w, h = box
    corners = []
    for x in (-extent, extent):
        for y in (-extent, extent):
            for z in (0, zmax):
                corners.append(cam.raw(x, y, z, zmax)[:2])
    minx = min(c[0] for c in corners)
    maxx = max(c[0] for c in corners)
    miny = min(c[1] for c in corners)
    maxy = max(c[1] for c in corners)
    s = min(w / (maxx - minx), h / (maxy - miny)) * 0.92
    ox = x0 + w / 2 - (minx + maxx) / 2 * s
    oy = y0 + h / 2 - (miny + maxy) / 2 * s

    def project(x, y, z):
        rx, ry, d = cam.raw(x, y, z, zmax)
        return ox + rx * s, oy + ry * s, d

    return project


# ---------------------------------------------------------------- 轨迹

def color_for(run: Run, i: int) -> str:
    if run.mode == "A":
        return BLUE
    if run.mode == "B":
        return SAGE_LINE
    e = run.epochs[min(i + 1, len(run.epochs) - 1)]
    return EPOCH_COLORS[e % len(EPOCH_COLORS)]


def segments_2d(run: Run, project):
    out = []
    hook_steps = {hk["step"] for hk in run.hooks}
    for i in range(len(run.xs) - 1):
        x1, y1 = project(run.xs[i], run.ys[i])
        x2, y2 = project(run.xs[i + 1], run.ys[i + 1])
        c = color_for(run, i)
        if i in hook_steps:
            c = mix(c, PAPER, 0.55)
        out.append((0.0, x1, y1, x2, y2, c))
    return out


def segments_3d(run: Run, project):
    out = []
    for i in range(len(run.xs) - 1):
        x1, y1, d1 = project(run.xs[i], run.ys[i], run.taus[i])
        x2, y2, d2 = project(run.xs[i + 1], run.ys[i + 1], run.taus[i + 1])
        out.append((0.5 * (d1 + d2), x1, y1, x2, y2, color_for(run, i)))
    out.sort(key=lambda s: s[0])
    return out


def draw_segments(segs, width=1.7, opacity=0.92) -> str:
    return "\n".join(
        line(x1, y1, x2, y2, c, width, opacity) for _, x1, y1, x2, y2, c in segs
    )


def markers_2d(run: Run, project) -> str:
    parts = []
    sx, sy = project(run.xs[0], run.ys[0])
    parts.append(circle(sx, sy, 3.2, fill=INK))
    ex, ey = project(run.xs[-1], run.ys[-1])
    parts.append(circle(ex, ey, 3.8, fill=PAPER, stroke=INK, width=1.2))
    for hk in run.hooks:
        hx, hy = project(hk["x"], hk["y"])
        parts.append(circle(hx, hy, 3.2, fill=PAPER, stroke=CLAY, width=1.1))
    return "\n".join(parts)


def markers_3d(run: Run, project) -> str:
    parts = []
    sx, sy, _ = project(run.xs[0], run.ys[0], run.taus[0])
    parts.append(circle(sx, sy, 3.2, fill=INK))
    ex, ey, _ = project(run.xs[-1], run.ys[-1], run.taus[-1])
    parts.append(circle(ex, ey, 3.8, fill=PAPER, stroke=INK, width=1.2))
    for hk in run.hooks:
        hx, hy, _ = project(hk["x"], hk["y"], run.taus[hk["step"]])
        parts.append(circle(hx, hy, 3.2, fill=PAPER, stroke=CLAY, width=1.1))
    return "\n".join(parts)


# ---------------------------------------------------------------- 面板

def title_color(mode: str) -> str:
    return {"A": BLUE, "B": SAGE, "C": CLAY}[mode]


def phase_panel(run: Run, x0: int, y0: int, w: int, h: int) -> str:
    box = (x0 + 18, y0 + 96, w - 36, h - 150)
    project = fit_2d(box)
    cx, cy = project(0, 0)
    r = project(1, 0)[0] - cx

    parts = [
        circle(cx, cy, r, stroke=GRID, width=0.8, dash="2 5"),
        draw_segments(segments_2d(run, project), width=1.25 if run.mode == "C" else 1.7),
        markers_2d(run, project),
        text(x0 + w / 2, y0 + 42, TITLES[run.mode], size=18,
             fill=title_color(run.mode), family="serif", anchor="middle"),
        text(x0 + w / 2, y0 + 66, SUBS_2D[run.mode], size=12.5,
             fill=MUTED, anchor="middle"),
    ]
    return "\n".join(parts)


def spiral_panel(run: Run, x0: int, y0: int, w: int, h: int, zmax: float,
                 cam: Camera) -> str:
    box = (x0 + 16, y0 + 92, w - 32, h - 136)
    project = fit_camera(cam, zmax, box)

    parts = []
    for v in (-1, 0, 1):
        a = project(v, -1, 0)
        b = project(v, 1, 0)
        parts.append(line(a[0], a[1], b[0], b[1], GRID, 0.8, 0.75))
        a = project(-1, v, 0)
        b = project(1, v, 0)
        parts.append(line(a[0], a[1], b[0], b[1], GRID, 0.8, 0.75))

    ax, ay = -1.12, -1.12
    p0 = project(ax, ay, 0)
    p1 = project(ax, ay, zmax)
    parts.append(line(p0[0], p0[1], p1[0], p1[1], FAINT, 1.0))
    ticks = nice_ticks(zmax)
    for z in ticks:
        px, py, _ = project(ax, ay, z)
        parts.append(line(px - 4, py, px, py, FAINT, 0.9))
        parts.append(text(px - 7, py + 3.5, f"{z:g}", size=10, fill=MUTED, anchor="end"))

    lx, ly, _ = project(1.16, 0, 0)
    parts.append(text(lx, ly + 4, "x", size=11, fill=MUTED, anchor="middle"))
    lx, ly, _ = project(0, 1.16, 0)
    parts.append(text(lx, ly + 4, "y", size=11, fill=MUTED, anchor="middle"))
    lx, ly, _ = project(ax, ay, zmax * 1.04)
    parts.append(text(lx, ly - 2, "τ", size=12, fill=MUTED, anchor="middle"))

    parts.append(draw_segments(segments_3d(run, project), width=1.25 if run.mode == "C" else 1.7))
    parts.append(markers_3d(run, project))
    parts.append(text(x0 + w / 2, y0 + 42, TITLES[run.mode], size=18,
                      fill=title_color(run.mode), family="serif", anchor="middle"))
    parts.append(text(x0 + w / 2, y0 + 66, SUBS_3D[run.mode], size=12.5,
                      fill=MUTED, anchor="middle"))
    return "\n".join(parts)


# ---------------------------------------------------------------- 三张图

TITLES = {
    "A": "A · 纯循环",
    "B": "B · 只有耗散",
    "C": "C · 耗散 + 记忆 + Hook",
}
SUBS_2D = {
    "A": "闭合的圆：没有之前，也没有之后",
    "B": "有方向了，但最后缩成一个点",
    "C": "每一次被改写，都落在新的相位上",
}
SUBS_3D = {
    "A": "贴在底面：高度为零",
    "B": "有方向了，但螺旋会停",
    "C": "有方向，而且停不下来",
}


def legend(x: int, y: int) -> str:
    return "\n".join([
        circle(x + 4, y - 4, 3.2, fill=INK),
        text(x + 14, y, "起点", size=11.2, fill=MUTED),
        circle(x + 78, y - 4, 3.6, fill=PAPER, stroke=INK, width=1.1),
        text(x + 88, y, "终点", size=11.2, fill=MUTED),
        circle(x + 150, y - 4, 3.2, fill=PAPER, stroke=CLAY, width=1.1),
        text(x + 160, y, "Hook（慢 / 稳 / 快）", size=11.2, fill=MUTED),
    ])


def make_phase_svg(runs: list[Run]) -> str:
    w, h = 1200, 420
    parts = [
        svg_start(w, h),
        bg(w, h),
        text(30, 24, "二维投影 · 从正上方看", size=12, fill=MUTED,
             letter_spacing="0.14em"),
    ]
    for i, run in enumerate(runs):
        parts.append(phase_panel(run, 30 + i * 390, 0, 360, 420))
    parts.append(legend(30, 402))
    parts.append("</svg>")
    return "\n".join(parts)


def make_spiral_svg(runs: list[Run], zmax: float) -> str:
    w, h = 1200, 440
    cam = Camera()
    parts = [
        svg_start(w, h),
        bg(w, h),
        text(30, 24, "三维内部空间 · 高度是累积耗散 τ", size=12, fill=MUTED,
             letter_spacing="0.14em"),
    ]
    for i, run in enumerate(runs):
        parts.append(spiral_panel(run, 30 + i * 390, 0, 360, 440, zmax, cam))
    parts.append(legend(30, 422))
    parts.append("</svg>")
    return "\n".join(parts)


def series_panel(runs: list[Run], x0: int, y0: int, w: int, h: int, kind: str) -> str:
    ax0, ay0 = x0 + 58, y0 + 64
    aw, ah = w - 78, h - 104

    if kind == "radius":
        vals = [[math.hypot(r.xs[i], r.ys[i]) for i in range(len(r.xs))] for r in runs]
        ymax = 1.1
    else:
        vals = [r.taus for r in runs]
        ymax = max(r.taus[-1] for r in runs) * 1.08
    yticks = nice_ticks(ymax)

    def px(t):
        return ax0 + t / STEPS * aw

    def py(v):
        return ay0 + ah - v / ymax * ah

    parts = []
    for yt in yticks:
        yy = py(yt)
        parts.append(line(ax0, yy, ax0 + aw, yy, GRID, 0.7, 0.75))
        parts.append(text(ax0 - 8, yy + 3.5, f"{yt:g}", size=10, fill=MUTED, anchor="end"))
    for xt in (0, 200, 400, 600):
        xx = px(xt)
        parts.append(line(xx, ay0, xx, ay0 + ah, GRID, 0.7, 0.75))
        parts.append(text(xx, ay0 + ah + 18, str(xt), size=10, fill=MUTED, anchor="middle"))

    parts.append(line(ax0, ay0 + ah, ax0 + aw, ay0 + ah, FAINT, 1.0))
    parts.append(line(ax0, ay0, ax0, ay0 + ah, FAINT, 1.0))
    parts.append(text(ax0 + aw / 2, ay0 + ah + 38, "步数", size=11, fill=MUTED, anchor="middle"))

    if kind == "radius":
        yy = py(THETA)
        parts.append(line(ax0, yy, ax0 + aw, yy, ROSE, 1.0, 0.9, dash="4 5"))
        parts.append(text(ax0 + aw - 4, yy - 6, "θ", size=11, fill=ROSE, anchor="end"))

    for idx, (run, color, name) in enumerate(zip(runs, (BLUE, SAGE_LINE, CLAY), ("A", "B", "C"))):
        pts = [(px(i), py(v)) for i, v in enumerate(vals[idx])]
        parts.append(polyline(pts, color, 1.8, 0.95))
        if kind == "radius" and run.mode == "C":
            for hk in run.hooks:
                parts.append(circle(px(hk["step"]), py(math.hypot(hk["x"], hk["y"])),
                                    2.0, fill=CLAY))
        # 末端直接标注
        ex, ey = pts[-1]
        parts.append(text(ex - 6, ey - 7, name, size=10.5, fill=color, anchor="end"))

    if kind == "tau":
        parts.append(text(px(300) + 6, py(1.7), "τ 只增不减", size=11, fill=CLAY))
        parts.append(text(px(560), py(0.5) - 7, "B 饱和", size=10,
                          fill=SAGE_LINE, anchor="middle"))

    if kind == "radius":
        parts.append(text(x0 + 20, y0 + 26, "半径 |v|：它会不会死？", size=17,
                          fill=INK, family="serif"))
        parts.append(text(x0 + 20, y0 + 48, "A 恒定 / B 衰减 / C 被 Hook 反复拉回",
                          size=11.5, fill=MUTED))
    else:
        parts.append(text(x0 + 20, y0 + 26, "累积耗散 τ：它回不回得去？", size=17,
                          fill=INK, family="serif"))
        parts.append(text(x0 + 20, y0 + 48, "A 为 0 / B 饱和 / C 持续上升",
                          size=11.5, fill=MUTED))

    return "\n".join(parts)


def make_arrow_svg(runs: list[Run]) -> str:
    w, h = 1200, 520
    parts = [
        svg_start(w, h),
        bg(w, h),
        text(60, 28, "时间箭头 · 半径与累积耗散", size=12, fill=MUTED,
             letter_spacing="0.14em"),
        series_panel(runs, 60, 60, 520, 400, "radius"),
        series_panel(runs, 640, 60, 520, 400, "tau"),
    ]
    parts.append("</svg>")
    return "\n".join(parts)


# ---------------------------------------------------------------- 入口

def fmt_pct(v: float) -> str:
    return f"{v * 100:.1f}%"


def main() -> None:
    runs = [simulate(m) for m in ("A", "B", "C")]
    zmax = max(r.taus[-1] for r in runs)
    zmax = max(zmax, 1.0) * 1.06

    FIG_DIR.mkdir(exist_ok=True)
    (FIG_DIR / "phase.svg").write_text(make_phase_svg(runs), encoding="utf-8")
    (FIG_DIR / "spiral.svg").write_text(make_spiral_svg(runs, zmax), encoding="utf-8")
    (FIG_DIR / "arrow.svg").write_text(make_arrow_svg(runs), encoding="utf-8")

    metrics = {r.mode: compute_metrics(r) for r in runs}
    payload = {
        "seed": SEED,
        "steps": STEPS,
        "params": {
            "omega0": OMEGA0,
            "gamma": GAMMA,
            "theta": THETA,
            "kick": KICK,
        },
        "groups": metrics,
    }
    (FIG_DIR / "metrics.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"\n  seed = {SEED}   steps = {STEPS}   zmax = {zmax:.2f}\n")
    print(f"  {'组':<4}{'末段半径':>10}{'覆盖率':>10}{'末段新态':>10}{'节律变化':>10}{'τ 终值':>10}{'Hook':>6}")
    print("  " + "-" * 64)
    for mode, m in metrics.items():
        print(
            f"  {mode:<4}{m['mean_radius_last']:>10.2f}{fmt_pct(m['coverage']):>10}"
            f"{fmt_pct(m['novelty_last']):>10}{m['omega_span']:>10.2f}"
            f"{m['tau_final']:>10.2f}{m['hooks']:>6}"
        )
    print(f"\n  已写出: figures/phase.svg, figures/spiral.svg, figures/arrow.svg, figures/metrics.json\n")


if __name__ == "__main__":
    main()
