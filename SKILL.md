---
name: dsh-imagedit
description: Local image editing toolkit — cutout (quick flood-fill for flat solid backgrounds, or rembg AI), trim, flip, rotate, brightness/contrast/saturation, blur, sharpen, rounded corners, border, padding, canvas resize+center, sprite sheets, and PNG/JPEG/WebP export. Use when the user asks to edit, clean up, cut out, resize, rotate, flip, enhance, or convert local images into engine-ready icons, sprites, portraits, photos, or other image assets.
---

# dsh-imagedit

Deterministic local image editing (no AI, no network). **If the `image_edit`
tool is available in this session, call it with structured parameters instead
of building shell commands.** Otherwise use the bundled CLI below.

## Agent workflow

1. Get the source image path (`vision_materialize` first if you only have an attachment id).
2. Call `image_edit` with the desired operations (cutout / trim / flip / rotate /
   enhance / blur / sharpen / rounded / border / canvas / formats).
3. Show the result to the user with `vision_present`.

Recommended game-asset loop: generate with a flat solid background
("flat solid white background, no shadows"), then `image_edit` with
`remove_bg: "quick"`, `canvas: "256x256"`, `padding: 16` → engine-ready PNG.
For complex backgrounds (shadows, hair, transparency) use `remove_bg: "rembg"`.

## CLI (fallback)

Single image — quick flood-fill cutout (no rembg):

```powershell
python scripts/asset_pipeline.py run `
  --input <image-path> `
  --remove-bg-quick auto `
  --canvas 256x256 `
  --padding 16 `
  --out-dir output/images/edited
```

AI cutout (rembg) for complex backgrounds:

```powershell
python scripts/asset_pipeline.py run `
  --input <image-path> `
  --remove-bg `
  --canvas 256x256 `
  --out-dir output/images/edited
```

Combined edits:

```powershell
python scripts/asset_pipeline.py run `
  --input <image-path> `
  --remove-bg-quick #FFFFFF `
  --rotate 90 --flip h `
  --brightness 1.1 --contrast 1.05 --saturation 1.2 `
  --blur 0 --sharpen 0.5 `
  --rounded 30 --border "4,#FF0000" `
  --canvas 256x256 --padding 8 `
  --exports png jpg --quality 90 `
  --out-dir output/images/edited
```

Batch: JSON manifest (per-item overrides + optional sprite sheet) or a directory:

```powershell
python scripts/asset_pipeline.py batch --manifest manifest.json
python scripts/asset_pipeline.py batch --dir ./photos --rotate 90 --exports jpg
```

Read [references/cli.md](references/cli.md) for the full reference (all options,
manifest schema, sprite sheet).

## Options

| Option | Meaning |
|---|---|
| `--remove-bg-quick [HEX\|auto]` | flood-fill cutout, no rembg — flat solid backdrops |
| `--remove-bg` | rembg AI cutout (downloads `isnet-general-use` on first run) |
| `--trim` / `--no-trim` | trim transparent margins (default on) |
| `--flip h\|v` | horizontal / vertical flip |
| `--rotate DEG` | rotate (90/180/270 lossless) |
| `--rotate-bg HEX` | fill color for arbitrary angles |
| `--brightness/--contrast/--saturation F` | color enhancements (default 1.0) |
| `--blur R` | gaussian blur radius |
| `--sharpen F` | sharpening amount |
| `--rounded R` | rounded-corner radius |
| `--border W[,HEX]` | border width + optional color |
| `--padding N` | even padding |
| `--canvas WxH` | scale + center onto a fixed canvas |
| `--exports png\|jpg\|webp [...]` | output formats |
| `--quality N` | JPEG/WebP quality (default 92) |
| `--auto-orient` | apply EXIF orientation |
| `sheet` (batch manifest) | compose sprite sheet + `sprites.json` |

## Rules

- Keep a PNG master export whenever the image may be imported into a game engine.
- `--remove-bg-quick` and `--remove-bg` are mutually exclusive; quick wins.
- Treat the first `rembg` run as slow (model download); prefer `--remove-bg-quick`
  for flat-color generated art.
- External PNG optimizers (`oxipng`, `pngquant`) are used automatically when on PATH.

## Resources

- `scripts/asset_pipeline.py` - main deterministic CLI (also wrapped by the `image_edit` tool)
- `scripts/asset_pipeline.ps1` - Windows wrapper
- `references/cli.md` - full CLI reference and manifest schema
