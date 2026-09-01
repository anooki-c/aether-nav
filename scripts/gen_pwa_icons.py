#!/usr/bin/env python3
"""生成云航导航 PWA 品牌图标（#5341CD 圆角底 + 白色"云"字）。

输出到 frontend/public/：
  icons/icon-192.png          常规 192x192（圆角，iOS 风格）
  icons/icon-512.png          常规 512x512
  icons/icon-maskable-512.png maskable 512x512（内容缩至安全区，避免被裁）
  apple-touch-icon.png        iOS 主屏图标 180x180（方形全出血，系统自行加圆角）

用法: python scripts/gen_pwa_icons.py
依赖: Pillow（纯本地渲染，无需外网）
"""
import os
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUBLIC = os.path.join(ROOT, "frontend", "public")
ICONS = os.path.join(PUBLIC, "icons")

PRIMARY = (83, 65, 205)  # #5341CD，与 style.css --c-primary 一致
WHITE = (255, 255, 255, 255)

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\msyhbd.ttc",   # Windows 微软雅黑 Bold
    r"C:\Windows\Fonts\msyh.ttc",
    "/System/Library/Fonts/PingFang.ttc",          # macOS 苹方
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]


def load_font(size):
    for p in FONT_CANDIDATES:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


def rounded_icon(size, radius_ratio=0.2237, char_ratio=0.46):
    """圆角底 + 白色"云"字。radius_ratio≈iOS 图标圆角比例。"""
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    r = max(1, int(size * radius_ratio))
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=r, fill=PRIMARY)

    # 先量后缩：让"云"字占画布 char_ratio 比例（水平/垂直取小者）
    font = load_font(int(size * 0.8))
    bbox = d.textbbox((0, 0), "云", font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    scale = (size * char_ratio) / max(w, h, 1)
    font = load_font(max(8, int(size * 0.8 * scale)))
    bbox = d.textbbox((0, 0), "云", font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (size - w) / 2 - bbox[0]
    y = (size - h) / 2 - bbox[1]
    d.text((x, y), "云", font=font, fill=WHITE)
    return im


def square_icon(size, char_ratio=0.58):
    """方形全出血版（apple-touch-icon 规范：不预切圆角）。"""
    im = Image.new("RGBA", (size, size), PRIMARY)
    d = ImageDraw.Draw(im)
    font = load_font(int(size * 0.8))
    bbox = d.textbbox((0, 0), "云", font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    scale = (size * char_ratio) / max(w, h, 1)
    font = load_font(max(8, int(size * 0.8 * scale)))
    bbox = d.textbbox((0, 0), "云", font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (size - w) / 2 - bbox[0]
    y = (size - h) / 2 - bbox[1]
    d.text((x, y), "云", font=font, fill=WHITE)
    return im


def main():
    os.makedirs(ICONS, exist_ok=True)
    targets = [
        (os.path.join(ICONS, "icon-192.png"), rounded_icon(192)),
        (os.path.join(ICONS, "icon-512.png"), rounded_icon(512)),
        # maskable：安全区为直径 80% 的圆，内容缩到 68% 画布保证不被裁
        (os.path.join(ICONS, "icon-maskable-512.png"), rounded_icon(512, radius_ratio=0.5, char_ratio=0.34)),
        (os.path.join(PUBLIC, "apple-touch-icon.png"), square_icon(180)),
    ]
    for path, im in targets:
        im.convert("RGB").save(path, "PNG")
        print("生成", os.path.relpath(path, ROOT), im.size)


if __name__ == "__main__":
    main()
