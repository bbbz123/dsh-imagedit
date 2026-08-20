---
name: asset-pipeline
description: Process generated game assets and sprites by removing backgrounds (AI rembg or quick flood-fill for flat solid backdrops), trimming transparent edges, adding padding, centering on fixed canvases, optionally composing sprite sheets, and exporting PNG/WebP outputs. Use when the agent needs to turn AI-generated images into engine-ready icons, item sprites, portraits, or other game assets, especially when the user mentions cutout, transparency, trim, padding, canvas sizing, sprite sheet, or batch export.
---

# Asset Pipeline

Use the bundled CLI for deterministic asset cleanup. Default to this skill when the work is image postprocessing rather than image generation.

## Workflow

1. Decide whether the task is a single image or a batch manifest.
2. Use `scripts/asset_pipeline.py`.
3. Pick the background removal mode:
   - `--remove-bg-quick` — **flood-fill cutout, no rembg, no model download.** Best for images generated with a flat solid background (e.g. dsh-draw output prompted with "flat solid white background, no shadows"). Pass `auto` to sample the corner color, or a hex like `#FFFFFF`.
   - `--remove-bg` — **rembg AI cutout** (downloads the `isnet-general-use` model on first run). Use for complex backgrounds, shadows, hair/fur, or when flood-fill fails.
4. Keep `--trim` enabled unless the user explicitly wants original framing preserved.
5. Add `--padding` and `--canvas` to make icons consistent in-engine.
6. In batch mode, set `"sheet": "sprites.png"` to also compose a sprite sheet with a `sprites.json` sidecar (name/x/y/w/h per frame).
7. Export `png` for engine imports; add `webp` only when previews or web surfaces are useful.

## End-to-end game asset loop (with dsh-draw + vision-router)

```
dsh-draw / image_generate (prompt: "flat solid white background, no shadows")
  → asset_pipeline.py run --remove-bg-quick auto --canvas 256x256 --padding 16
  → engine-ready transparent PNG (+ optional sprite sheet via batch manifest)
```

For complex assets (shadows, transparency, busy backgrounds) prefer `--remove-bg` (rembg); use `vision_extract_foreground` for one-off visual checks of the cutout.

## Commands

Single image:

```powershell
python scripts/asset_pipeline.py run `
  --input <image-path> `
  --remove-bg-quick auto `
  --canvas 256x256 `
  --padding 16 `
  --out-dir output/assets/exported
```

Explicit background color:

```powershell
python scripts/asset_pipeline.py run `
  --input <image-path> `
  --remove-bg-quick #FFFFFF `
  --bg-tolerance 40 `
  --canvas 256x256 `
  --out-dir output/assets/exported
```

AI cutout (rembg) for complex backgrounds:

```powershell
python scripts/asset_pipeline.py run `
  --input <image-path> `
  --remove-bg `
  --canvas 256x256 `
  --padding 16 `
  --out-dir output/assets/exported
```

Batch manifest:

```powershell
python scripts/asset_pipeline.py batch --manifest <manifest-json>
```

Read [references/cli.md](references/cli.md) for concrete examples and manifest structure.

## Rules

- Keep a PNG master export whenever the image may be imported into a game engine.
- Treat the first `rembg` run as slow because it may download the segmentation model; prefer `--remove-bg-quick` for flat-color generated art.
- Avoid background removal on images that already have clean alpha.
- Use square canvases for inventory icons unless the user specifies another aspect ratio.
- If external PNG optimizers such as `oxipng` or `pngquant` are installed, the script will use them automatically.
- `--remove-bg-quick` and `--remove-bg` are mutually exclusive; quick wins if both are present.

## Resources

- `scripts/asset_pipeline.py` - main deterministic CLI
- `scripts/asset_pipeline.ps1` - Windows wrapper for direct invocation
- `references/cli.md` - usage patterns and batch manifest example
