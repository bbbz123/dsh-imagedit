# dsh-asset-pipeline

**游戏素材后处理管线** — A DeepSeek Harness (DSH) skill plugin that turns
AI-generated images into engine-ready game assets: background removal
(rembg AI or instant flood-fill), alpha trim, padding, canvas normalization,
sprite-sheet composition with JSON metadata, and PNG/WebP export.

Originally adapted from a Codex skill, upgraded for DSH with a dependency-free
quick cutout and sprite-sheet support.

## Features

| Step | Tool | Notes |
|---|---|---|
| 抠图 | `--remove-bg` | rembg AI cutout (`isnet-general-use`) — complex backgrounds, shadows, hair |
| 抠图 | `--remove-bg-quick` | flood-fill cutout, **no rembg / no model download** — flat solid backdrops (generated art) |
| 裁剪 | `--trim` | remove transparent margins (alpha threshold) |
| 留白 | `--padding` | even padding around the sprite |
| 画布 | `--canvas` | scale + center onto a fixed canvas (e.g. `256x256` inventory icons) |
| 图集 | `sheet` (batch) | compose a sprite sheet + `sprites.json` (name/x/y/w/h per frame) |
| 导出 | `--exports` | `png` (optimized, oxipng/pngquant when available) and/or `webp` |

## Install

```powershell
# Option A — clone into your DSH user skills (all workspaces):
git clone https://github.com/bbbz123/dsh-asset-pipeline "$HOME\.dsh\skills\asset-pipeline"

# Option B — via dsh-market (search "asset-pipeline")
# Option C — copy the folder into <project>\.dsh\skills\asset-pipeline for one project
```

DSH discovers it automatically (no restart needed for the catalog; a restart
reloads skill content in running sessions).

## Usage

```powershell
# Single image — quick flood-fill cutout (flat white background art)
python scripts/asset_pipeline.py run `
  --input item.png `
  --remove-bg-quick auto `
  --canvas 256x256 --padding 16 `
  --out-dir output/assets/exported

# Single image — rembg AI cutout (complex background)
python scripts/asset_pipeline.py run --input item.png --remove-bg --canvas 256x256

# Batch + sprite sheet
python scripts/asset_pipeline.py batch --manifest manifest.json
```

`manifest.json` example:

```json
{
  "out_dir": "output/assets/exported",
  "remove_bg_quick": "auto",
  "trim": true,
  "padding": 16,
  "canvas": "256x256",
  "exports": ["png", "webp"],
  "sheet": "sprites.png",
  "items": [
    { "name": "potion_red", "input": "gen/potion-red.png" },
    { "name": "sword",      "input": "gen/sword.png" }
  ]
}
```

See [references/cli.md](references/cli.md) for the full CLI reference, and
`SKILL.md` for the agent-facing instructions.

## Recommended pipeline (with dsh-draw + vision-router)

```
dsh-draw / image_generate  (prompt: "flat solid white background, no shadows")
  → asset_pipeline.py run --remove-bg-quick auto --canvas 256x256 --padding 16
  → engine-ready transparent PNG (+ sprite sheet via batch)
```

For complex assets prefer `--remove-bg` (rembg); for a one-off visual check of
the cutout use `vision_extract_foreground`.

## Requirements

- Python 3.10+ and [Pillow](https://pypi.org/project/pillow/) (required)
- `rembg` (optional, only for `--remove-bg`)
- `oxipng` / `pngquant` (optional, auto-used when on PATH)

## License

MIT — see [LICENSE](LICENSE).
