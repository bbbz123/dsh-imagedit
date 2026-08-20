# CLI

## Single image — quick flood-fill cutout (no rembg)

Best for images generated with a flat solid background:

```powershell
python scripts/asset_pipeline.py run `
  --input output/imagegen/item.png `
  --remove-bg-quick auto `
  --canvas 256x256 `
  --padding 16 `
  --out-dir output/assets/exported
```

`--remove-bg-quick` accepts:
- `auto` — sample the corner color (default)
- `#RRGGBB` — explicit background color, e.g. `--remove-bg-quick #FFFFFF`

Tune the cutout with `--bg-tolerance` (default 40; raise for softer backdrops, lower for edge cases).

## Single image — AI cutout (rembg)

For complex backgrounds / shadows / hair / fur (downloads `isnet-general-use` model on first run):

```powershell
python scripts/asset_pipeline.py run `
  --input output/imagegen/item.png `
  --remove-bg `
  --canvas 256x256 `
  --padding 16 `
  --out-dir output/assets/exported
```

## Batch manifest

```powershell
python scripts/asset_pipeline.py batch --manifest asset-pipeline.example.json
```

Typical manifest (quick cutout + sprite sheet):

```json
{
  "out_dir": "output/assets/exported",
  "remove_bg": false,
  "remove_bg_quick": "auto",
  "bg_tolerance": 40,
  "trim": true,
  "padding": 16,
  "canvas": "256x256",
  "exports": ["png", "webp"],
  "sheet": "sprites.png",
  "items": [
    {
      "name": "potion_red",
      "input": "output/imagegen/potion-red.png"
    },
    {
      "name": "sword",
      "input": "output/imagegen/sword.png"
    }
  ]
}
```

Per-item fields override the top-level defaults. `sheet` composes every item's
PNG output onto a fixed-column grid (`sprites.png`) and writes `sprites.json`
with `name / x / y / w / h` per frame plus sheet dimensions — ready for a game
engine atlas importer.

## Notes

- `out_dir` and `input` paths in a manifest resolve relative to the manifest file.
- `--remove-bg-quick` and `--remove-bg` are mutually exclusive; quick wins.
- External optimizers (`oxipng`, `pngquant`) are used automatically when on PATH.
