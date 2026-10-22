"""生成应用图标（assets/icon.ico 与 assets/icon.png）。

设计思路：深靛蓝到青色的圆角底板上，放置一张白色报表纸张，
纸面用三条流动的渐变波纹表示"消息流 / 数据流"。
纯 Pillow 绘制，不依赖设计软件，修改颜色或形状后重新运行即可。

用法：
    python tools/make_icon.py
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageOps

# ---- 调色板 ----
BG_TOP = (67, 56, 202)        # indigo-700
BG_BOTTOM = (14, 165, 233)    # sky-500
PAGE = (248, 250, 252)        # slate-50
FOLD = (219, 234, 254)        # blue-100
FOLD_LINE = (191, 219, 254)   # blue-200
INK = (79, 70, 229)           # indigo-600
STREAM = (14, 165, 233)       # sky-500
STREAM_LIGHT = (34, 211, 238) # cyan-400

SS = 4                        # 超采样倍数，用于抗锯齿
BASE = 1024
SIZE = BASE * SS

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "assets"


def _vertical_gradient(size: int, top: tuple[int, int, int], bottom: tuple[int, int, int]) -> Image.Image:
    gray = Image.linear_gradient("L").resize((size, size), Image.Resampling.BICUBIC)
    return ImageOps.colorize(gray, black=top, white=bottom).convert("RGBA")


def _rounded_mask(size: int, radius: int) -> Image.Image:
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, size - 1, size - 1), radius=radius, fill=255
    )
    return mask


def _draw_wave(
    draw: ImageDraw.ImageDraw,
    y: float,
    amplitude: float,
    phase: float,
    width: float,
    color: tuple[int, int, int, int],
    x0: float,
    x1: float,
) -> None:
    """画一条两端圆头的正弦波纹（用填充多边形，避免折线拼接出缝隙）。"""
    steps = 160
    points: list[tuple[float, float]] = []
    for index in range(steps + 1):
        t = index / steps
        x = x0 + (x1 - x0) * t
        y_offset = math.sin(t * math.pi * 2.2 + phase) * amplitude
        points.append((x, y + y_offset))

    half = width / 2
    left_edge: list[tuple[float, float]] = []
    right_edge: list[tuple[float, float]] = []
    for index, (x, y) in enumerate(points):
        if index == 0:
            dx, dy = points[1][0] - x, points[1][1] - y
        elif index == len(points) - 1:
            dx, dy = x - points[index - 1][0], y - points[index - 1][1]
        else:
            dx = points[index + 1][0] - points[index - 1][0]
            dy = points[index + 1][1] - points[index - 1][1]
        length = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / length * half, dx / length * half
        left_edge.append((x + nx, y + ny))
        right_edge.append((x - nx, y - ny))

    draw.polygon(left_edge + right_edge[::-1], fill=color)
    for point in (points[0], points[-1]):
        draw.ellipse(
            (point[0] - half, point[1] - half, point[0] + half, point[1] + half),
            fill=color,
        )


def build_icon() -> Image.Image:
    canvas = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    radius = int(SIZE * 0.225)

    # 底板：渐变 + 左上高光 + 右下暗角
    board = _vertical_gradient(SIZE, BG_TOP, BG_BOTTOM)

    glow = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    glow_draw.ellipse(
        (-SIZE * 0.25, -SIZE * 0.35, SIZE * 0.75, SIZE * 0.55),
        fill=(255, 255, 255, 46),
    )
    glow_draw.ellipse(
        (SIZE * 0.55, SIZE * 0.65, SIZE * 1.25, SIZE * 1.3),
        fill=(2, 6, 23, 60),
    )
    glow = glow.filter(ImageFilter.GaussianBlur(SIZE * 0.09))
    board = Image.alpha_composite(board, glow)

    # 圆角裁剪
    board.putalpha(_rounded_mask(SIZE, radius))
    canvas = Image.alpha_composite(canvas, board)

    # 内描边，增加精致感
    border = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    border_draw = ImageDraw.Draw(border)
    inset = SIZE * 0.012
    border_draw.rounded_rectangle(
        (inset, inset, SIZE - 1 - inset, SIZE - 1 - inset),
        radius=radius - int(inset),
        outline=(255, 255, 255, 40),
        width=max(1, int(SIZE * 0.006)),
    )
    border.putalpha(Image.composite(border.getchannel("A"), Image.new("L", (SIZE, SIZE), 0), _rounded_mask(SIZE, radius)))
    canvas = Image.alpha_composite(canvas, border)

    # ---- 报表纸张 ----
    page_w, page_h = SIZE * 0.50, SIZE * 0.60
    cx, cy = SIZE / 2, SIZE * 0.505
    left, top = cx - page_w / 2, cy - page_h / 2
    right, bottom = cx + page_w / 2, cy + page_h / 2
    page_radius = SIZE * 0.055

    # 投影
    shadow = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle(
        (left, top + SIZE * 0.025, right, bottom + SIZE * 0.025),
        radius=page_radius,
        fill=(2, 6, 23, 110),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(SIZE * 0.035))
    canvas = Image.alpha_composite(canvas, shadow)

    page = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    page_draw = ImageDraw.Draw(page)
    page_draw.rounded_rectangle(
        (left, top, right, bottom), radius=page_radius, fill=PAGE
    )

    # 右上角折角
    fold = SIZE * 0.115
    page_draw.polygon(
        [(right - fold, top), (right, top + fold), (right - fold, top + fold)],
        fill=FOLD,
    )
    page_draw.line(
        [(right - fold, top), (right - fold, top + fold), (right, top + fold)],
        fill=FOLD_LINE,
        width=max(1, int(SIZE * 0.007)),
        joint="curve",
    )
    canvas = Image.alpha_composite(canvas, page)

    # ---- 纸面上的流动波纹 ----
    stream = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    stream_draw = ImageDraw.Draw(stream)
    margin_x = page_w * 0.16
    x0, x1 = left + margin_x, right - margin_x
    base_y = top + page_h * 0.40
    line_gap = page_h * 0.155
    wave_width = SIZE * 0.042

    waves = (
        (base_y, 1.0, 0.0, INK + (255,)),
        (base_y + line_gap, 0.8, 1.1, STREAM + (255,)),
        (base_y + line_gap * 2, 0.55, 2.2, STREAM_LIGHT + (255,)),
    )
    for y, scale, phase, color in waves:
        _draw_wave(
            stream_draw,
            y=y,
            amplitude=SIZE * 0.022 * scale,
            phase=phase,
            width=wave_width,
            color=color,
            x0=x0,
            x1=x1,
        )

    # 让波纹只出现在纸张范围内
    page_mask = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(page_mask).rounded_rectangle(
        (left, top, right, bottom), radius=page_radius, fill=255
    )
    stream.putalpha(Image.composite(stream.getchannel("A"), Image.new("L", (SIZE, SIZE), 0), page_mask))
    canvas = Image.alpha_composite(canvas, stream)

    return canvas.resize((BASE, BASE), Image.Resampling.LANCZOS)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    icon = build_icon()

    icon.save(OUT_DIR / "icon.png", "PNG")
    icon.resize((256, 256), Image.Resampling.LANCZOS).save(OUT_DIR / "icon_256.png", "PNG")

    sizes = [(16, 16), (20, 20), (24, 24), (32, 32), (40, 40), (48, 48), (64, 64), (128, 128), (256, 256)]
    icon.save(OUT_DIR / "icon.ico", format="ICO", sizes=sizes)

    print(f"已生成：{OUT_DIR / 'icon.ico'}")
    print(f"已生成：{OUT_DIR / 'icon.png'}")


if __name__ == "__main__":
    main()
