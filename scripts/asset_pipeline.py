#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageChops, ImageDraw

DEFAULT_EXPORTS = ("png", "webp")
DEFAULT_ALPHA_THRESHOLD = 8
DEFAULT_BG_TOLERANCE = 40
SHEET_COLUMNS = 8
# Marker color used by flood-fill probing. Deliberately near-magenta but not
# exactly (255,0,255) so genuine magenta pixels in art are unlikely to collide.
MARKER = (254, 0, 254, 255)
MARKER_THRESHOLD = 12


@dataclass
class Job:
    input_path: Path
    output_stem: str
    out_dir: Path
    remove_bg: bool
    remove_bg_quick: str | None
    bg_tolerance: int
    trim: bool
    alpha_threshold: int
    padding: int
    canvas: tuple[int, int] | None
    exports: tuple[str, ...]
    webp_quality: int
    png_compress_level: int


def parse_canvas(raw: str | None) -> tuple[int, int] | None:
    if not raw:
        return None
    width, height = raw.lower().split("x", 1)
    return int(width), int(height)


def ensure_rgba(image: Image.Image) -> Image.Image:
    return image if image.mode == "RGBA" else image.convert("RGBA")


def remove_background(image: Image.Image, *, session) -> Image.Image:
    _, remove = load_rembg()
    if remove is None:
        raise RuntimeError("rembg is not installed; install it before using --remove-bg.")
    return ensure_rgba(remove(image, session=session))


def load_rembg():
    try:
        from rembg import new_session, remove
    except ImportError:  # pragma: no cover - optional dependency at runtime
        return None, None
    return new_session, remove


def _parse_hex_color(raw: str) -> tuple[int, int, int]:
    value = raw.lstrip("#")
    if len(value) != 6:
        raise ValueError(f"invalid hex color: {raw!r} (expected #RRGGBB)")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def _sample_bg_color(image: Image.Image) -> tuple[int, int, int]:
    """Average of the four corner pixels — a cheap solid-background estimate."""
    w, h = image.size
    corners = [image.getpixel(p)[:3] for p in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1))]
    return tuple(round(sum(c[i] for c in corners) / len(corners)) for i in range(3))  # type: ignore[return-value]


def quick_remove_background(
    image: Image.Image, *, bg_hex: str | None = None, tolerance: int = DEFAULT_BG_TOLERANCE
) -> Image.Image:
    """Flood-fill background removal for flat solid backgrounds (no rembg needed).

    Seeds the four edges, floods every connected region whose color is within
    ``tolerance`` of the background color, then zeroes alpha in the flooded
    area. Fast and dependency-light; best for clean single-color backdrops
    (e.g. images generated with a flat white background).
    """
    rgba = ensure_rgba(image)
    bg = _parse_hex_color(bg_hex) if bg_hex and bg_hex != "auto" else _sample_bg_color(rgba)
    w, h = rgba.size

    probe = rgba.copy()
    # Corners plus edge midpoints cover every background region touching a border.
    seeds = [
        (0, 0),
        (w - 1, 0),
        (0, h - 1),
        (w - 1, h - 1),
        (w // 2, 0),
        (w // 2, h - 1),
        (0, h // 2),
        (w - 1, h // 2),
    ]
    for sx, sy in seeds:
        p = rgba.getpixel((sx, sy))
        if abs(p[0] - bg[0]) + abs(p[1] - bg[1]) + abs(p[2] - bg[2]) > tolerance * 3:
            continue  # this edge point is not background-colored; skip it
        ImageDraw.floodfill(probe, (sx, sy), MARKER, thresh=tolerance)

    diff = ImageChops.difference(probe, rgba).convert("L")
    mask = diff.point(lambda v: 255 if v > MARKER_THRESHOLD else 0)
    alpha = rgba.getchannel("A")
    new_alpha = ImageChops.subtract(alpha, mask)  # zero alpha in the flooded area
    out = rgba.copy()
    out.putalpha(new_alpha)
    return out


def trim_alpha(image: Image.Image, *, alpha_threshold: int) -> Image.Image:
    rgba = ensure_rgba(image)
    alpha = rgba.getchannel("A")
    bbox = alpha.point(lambda px: 255 if px > alpha_threshold else 0).getbbox()
    if bbox is None:
        return rgba
    return rgba.crop(bbox)


def expand_with_padding(image: Image.Image, padding: int) -> Image.Image:
    if padding <= 0:
        return image
    rgba = ensure_rgba(image)
    width, height = rgba.size
    canvas = Image.new("RGBA", (width + padding * 2, height + padding * 2), (0, 0, 0, 0))
    canvas.alpha_composite(rgba, (padding, padding))
    return canvas


def place_on_canvas(image: Image.Image, canvas_size: tuple[int, int] | None) -> Image.Image:
    rgba = ensure_rgba(image)
    if canvas_size is None:
        return rgba
    target_w, target_h = canvas_size
    src_w, src_h = rgba.size
    scale = min(target_w / src_w, target_h / src_h)
    resized = rgba.resize(
        (max(1, round(src_w * scale)), max(1, round(src_h * scale))),
        Image.Resampling.LANCZOS,
    )
    canvas = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    x = (target_w - resized.width) // 2
    y = (target_h - resized.height) // 2
    canvas.alpha_composite(resized, (x, y))
    return canvas


def save_png(image: Image.Image, output_path: Path, *, compress_level: int) -> None:
    image.save(output_path, format="PNG", optimize=True, compress_level=compress_level)
    maybe_run_external_png_optimizer(output_path)


def save_webp(image: Image.Image, output_path: Path, *, quality: int) -> None:
    image.save(output_path, format="WEBP", lossless=False, quality=quality, method=6)


def maybe_run_external_png_optimizer(output_path: Path) -> None:
    for tool, args in (
        ("oxipng", ["-o", "4", "--strip", "safe", str(output_path)]),
        ("pngquant", ["--skip-if-larger", "--force", "--output", str(output_path), str(output_path)]),
    ):
        executable = shutil.which(tool)
        if not executable:
            continue
        subprocess.run([executable, *args], check=False, capture_output=True)
        break


def process_job(job: Job, *, session) -> list[Path]:
    image = Image.open(job.input_path)
    image.load()
    image = ensure_rgba(image)

    if job.remove_bg_quick:
        image = quick_remove_background(image, bg_hex=job.remove_bg_quick, tolerance=job.bg_tolerance)
    elif job.remove_bg:
        image = remove_background(image, session=session)
    if job.trim:
        image = trim_alpha(image, alpha_threshold=job.alpha_threshold)
    image = expand_with_padding(image, job.padding)
    image = place_on_canvas(image, job.canvas)

    job.out_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    for export in job.exports:
        output_path = job.out_dir / f"{job.output_stem}.{export}"
        if export == "png":
            save_png(image, output_path, compress_level=job.png_compress_level)
        elif export == "webp":
            save_webp(image, output_path, quality=job.webp_quality)
        else:
            raise ValueError(f"Unsupported export format: {export}")
        outputs.append(output_path)
    return outputs


def build_job_from_args(args: argparse.Namespace) -> Job:
    input_path = Path(args.input).resolve()
    output_stem = args.name or input_path.stem
    exports = tuple(args.exports or DEFAULT_EXPORTS)
    return Job(
        input_path=input_path,
        output_stem=output_stem,
        out_dir=Path(args.out_dir).resolve(),
        remove_bg=args.remove_bg,
        remove_bg_quick=args.remove_bg_quick,
        bg_tolerance=args.bg_tolerance,
        trim=args.trim,
        alpha_threshold=args.alpha_threshold,
        padding=args.padding,
        canvas=parse_canvas(args.canvas),
        exports=exports,
        webp_quality=args.webp_quality,
        png_compress_level=args.png_compress_level,
    )


def build_job_from_manifest(item: dict, *, base_dir: Path, defaults: dict) -> Job:
    input_path = (base_dir / item["input"]).resolve()
    exports = tuple(item.get("exports", defaults["exports"]))
    quick = item.get("remove_bg_quick", defaults["remove_bg_quick"])
    if quick is True:
        quick = "auto"
    return Job(
        input_path=input_path,
        output_stem=item.get("name", input_path.stem),
        out_dir=(base_dir / item.get("out_dir", defaults["out_dir"])).resolve(),
        remove_bg=item.get("remove_bg", defaults["remove_bg"]),
        remove_bg_quick=quick,
        bg_tolerance=item.get("bg_tolerance", defaults["bg_tolerance"]),
        trim=item.get("trim", defaults["trim"]),
        alpha_threshold=item.get("alpha_threshold", defaults["alpha_threshold"]),
        padding=item.get("padding", defaults["padding"]),
        canvas=parse_canvas(item.get("canvas", defaults["canvas"])),
        exports=exports,
        webp_quality=item.get("webp_quality", defaults["webp_quality"]),
        png_compress_level=item.get("png_compress_level", defaults["png_compress_level"]),
    )


def build_sprite_sheet(entries: list[tuple[str, Path]], sheet_name: str) -> Path:
    """Lay all PNG outputs out on a fixed-column grid sheet + sidecar JSON."""
    images: list[tuple[str, Image.Image]] = []
    for name, path in entries:
        if path is None or path.suffix.lower() != ".png" or not path.exists():
            continue
        images.append((name, Image.open(path).convert("RGBA")))
    if not images:
        raise RuntimeError("sprite sheet requested but no PNG outputs were produced")

    cell_w = max(img.width for _, img in images)
    cell_h = max(img.height for _, img in images)
    cols = min(SHEET_COLUMNS, len(images))
    rows = math.ceil(len(images) / cols)

    sheet = Image.new("RGBA", (cell_w * cols, cell_h * rows), (0, 0, 0, 0))
    frames: list[dict] = []
    for i, (name, img) in enumerate(images):
        col, row = i % cols, i // cols
        x = col * cell_w + (cell_w - img.width) // 2
        y = row * cell_h + (cell_h - img.height) // 2
        sheet.alpha_composite(img, (x, y))
        frames.append({"name": name, "x": x, "y": y, "w": img.width, "h": img.height})

    out_dir = entries[0][1].parent
    sheet_path = out_dir / sheet_name
    sheet.save(sheet_path, format="PNG", optimize=True)
    meta = {
        "sheet": sheet_name,
        "columns": cols,
        "rows": rows,
        "cell_width": cell_w,
        "cell_height": cell_h,
        "frames": frames,
    }
    (out_dir / (sheet_path.stem + ".json")).write_text(
        json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return sheet_path


def run_single(args: argparse.Namespace) -> int:
    rembg_new_session, _ = load_rembg()
    session = rembg_new_session("isnet-general-use") if args.remove_bg and rembg_new_session else None
    job = build_job_from_args(args)
    outputs = process_job(job, session=session)
    for output in outputs:
        print(output)
    return 0


def run_batch(args: argparse.Namespace) -> int:
    manifest_path = Path(args.manifest).resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    defaults = {
        "out_dir": manifest.get("out_dir", "output/assets/exported"),
        "remove_bg": manifest.get("remove_bg", True),
        "remove_bg_quick": manifest.get("remove_bg_quick", None),
        "bg_tolerance": manifest.get("bg_tolerance", DEFAULT_BG_TOLERANCE),
        "trim": manifest.get("trim", True),
        "alpha_threshold": manifest.get("alpha_threshold", DEFAULT_ALPHA_THRESHOLD),
        "padding": manifest.get("padding", 12),
        "canvas": manifest.get("canvas", "256x256"),
        "exports": manifest.get("exports", list(DEFAULT_EXPORTS)),
        "webp_quality": manifest.get("webp_quality", 92),
        "png_compress_level": manifest.get("png_compress_level", 9),
    }
    items: Iterable[dict] = manifest["items"]
    rembg_new_session, _ = load_rembg()
    need_rembg = any(
        item.get("remove_bg", defaults["remove_bg"]) and not item.get("remove_bg_quick", defaults["remove_bg_quick"])
        for item in items
    )
    session = rembg_new_session("isnet-general-use") if need_rembg and rembg_new_session else None

    sheet_entries: list[tuple[str, Path]] = []
    for item in items:
        job = build_job_from_manifest(item, base_dir=manifest_path.parent, defaults=defaults)
        outputs = process_job(job, session=session)
        png_out = next((p for p in outputs if p.suffix.lower() == ".png"), None)
        sheet_entries.append((job.output_stem, png_out))
        print(f"{job.input_path.name} -> {', '.join(str(output) for output in outputs)}")

    if manifest.get("sheet"):
        sheet_path = build_sprite_sheet(sheet_entries, manifest["sheet"])
        print(f"sprite sheet -> {sheet_path}")
    return 0


def add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--out-dir", default="output/assets/exported")
    parser.add_argument("--name")
    parser.add_argument("--remove-bg", action="store_true")
    parser.add_argument(
        "--remove-bg-quick",
        nargs="?",
        const="auto",
        default=None,
        metavar="HEX|auto",
        help="flood-fill cutout for flat solid backgrounds (no rembg); pass an optional #RRGGBB background color or 'auto' to sample the corners",
    )
    parser.add_argument("--bg-tolerance", type=int, default=DEFAULT_BG_TOLERANCE)
    parser.add_argument("--trim", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--alpha-threshold", type=int, default=DEFAULT_ALPHA_THRESHOLD)
    parser.add_argument("--padding", type=int, default=12)
    parser.add_argument("--canvas", default="256x256")
    parser.add_argument("--exports", nargs="+", choices=("png", "webp"), default=list(DEFAULT_EXPORTS))
    parser.add_argument("--webp-quality", type=int, default=92)
    parser.add_argument("--png-compress-level", type=int, default=9)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Lightweight postprocess pipeline for game assets: remove background (rembg or quick flood-fill), trim, pad, center, sheet, and export."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Process one image")
    run_parser.add_argument("--input", required=True)
    add_common_arguments(run_parser)
    run_parser.set_defaults(func=run_single)

    batch_parser = subparsers.add_parser("batch", help="Process a JSON manifest")
    batch_parser.add_argument("--manifest", required=True)
    batch_parser.set_defaults(func=run_batch)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
