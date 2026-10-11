"""
Chuyển một ảnh minh hoạ thành ASCII có màu, lưu vào scripts/art.json để today.py dùng.

  python scripts/make_art.py <ảnh> [--cols 52] [--rows 32] [--split 26]

--split: cột chia ảnh thành 2 nhân vật (trái / phải) để mỗi người nhún nhảy riêng.
         Bỏ qua (hoặc 0) nếu chỉ có một nhân vật.

Lưu ý bản quyền: chỉ commit art.json (bản ASCII đã chỉnh sửa), KHÔNG commit ảnh gốc
vào repo public nếu điều khoản của nguồn ảnh cấm phân phối lại (ví dụ イラストマン).
"""
import argparse
import colorsys
import json
from pathlib import Path

from PIL import Image

RAMP = " .,:;-=+*%#@"


def convert(path, cols, rows):
    im = Image.open(path).convert("RGBA")
    bg = Image.new("RGBA", im.size, "white")
    bg.alpha_composite(im)
    rgb = bg.convert("RGB")
    W, H = rgb.size
    cw, ch = W / cols, H / rows
    grid = []
    for y in range(rows):
        row = []
        for x in range(cols):
            box = rgb.crop((int(x * cw), int(y * ch), int((x + 1) * cw), int((y + 1) * ch)))
            px = list(box.getdata())
            lum = sum(0.299 * r + 0.587 * g + 0.114 * b for r, g, b in px) / len(px)
            dark = 1 - lum / 255
            ch_ = RAMP[min(len(RAMP) - 1, int(dark ** 0.7 * len(RAMP) * 1.6))]
            # Màu: chỉ giữ cho vùng tô màu bão hoà (cà vạt, má hồng...); nét viền dùng màu theme
            ink = [p for p in px if sum(p) < 720]
            color = None
            if ink and ch_ != " ":
                r, g, b = (sum(c[i] for c in ink) / len(ink) for i in range(3))
                h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
                if s > 0.45 and v > 0.45:
                    color = "#%02x%02x%02x" % (int(r), int(g), int(b))
            row.append([ch_, color])
        grid.append(row)
    # bỏ dòng trống cuối
    while grid and all(c[0] == " " for c in grid[-1]):
        grid.pop()
    return grid


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--cols", type=int, default=52)
    ap.add_argument("--rows", type=int, default=32)
    ap.add_argument("--split", type=int, default=0)
    a = ap.parse_args()
    grid = convert(a.image, a.cols, a.rows)
    out = Path(__file__).with_name("art.json")
    out.write_text(json.dumps({"split": a.split, "grid": grid}, separators=(",", ":")), encoding="utf-8")
    for row in grid:
        print("".join(c[0] for c in row).rstrip())
    print(f"→ {out}")


if __name__ == "__main__":
    main()
