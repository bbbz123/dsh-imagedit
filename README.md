# dsh-imagedit

**本地图像编辑工具箱** — A DeepSeek Harness (DSH) plugin **and** skill for
deterministic local image editing: background cutout (rembg AI or instant
flood-fill), trim, flip, rotate, brightness/contrast/saturation, blur,
sharpen, rounded corners, border, canvas normalization, sprite sheets, and
PNG/JPEG/WebP export.

Dual form: a **cordis plugin** that registers an `image_edit` agent tool
(agent calls it directly with structured parameters), and a **skill** with the
same functionality via a Python CLI. Originally adapted from a Codex skill and
upgraded for DSH (dependency-free quick cutout, sprite sheets, JPEG export,
batch-directory processing).

## Features

| Area | Operations |
|---|---|
| 抠图 | `remove_bg: quick` (flood-fill, no model) · `remove_bg: rembg` (AI) |
| 基础 | `trim` · `flip h/v` · `rotate` · `padding` · `canvas WxH` (scale+center) |
| 调色 | `brightness` · `contrast` · `saturation` |
| 滤镜 | `blur` · `sharpen` |
| 修饰 | `rounded` (corners) · `border W[,HEX]` · `auto-orient` (EXIF) |
| 批量 | JSON manifest · `--dir` recursive folder · sprite sheet + `sprites.json` |
| 导出 | PNG (oxipng/pngquant auto) · JPEG · WebP (`quality`) |

## Install

### As a plugin (agent tool `image_edit`) — recommended

```powershell
# local link install
dsh plugin --profile web add link:D:\path\to\dsh-imagedit

# once published on npm / GitHub
dsh plugin --profile web add dsh-imagedit
# or
dsh plugin --profile web add github:bbbz123/dsh-imagedit
```

Restart `dsh web`; the `image_edit` tool then appears in the tool catalog and
the agent can call it directly. Override the Python interpreter with the
`DSH_IMAGEDIT_PYTHON` environment variable if needed.

### As a skill (CLI)

```powershell
git clone https://github.com/bbbz123/dsh-imagedit "$HOME\.dsh\skills\dsh-imagedit"
# or copy the folder into <project>\.dsh\skills\dsh-imagedit for one project
```

DSH discovers it automatically. The skill instructs the agent to prefer the
`image_edit` tool when available and fall back to the CLI.

## Usage

### Agent tool

Call `image_edit` with structured params, e.g.:

```json
{
  "input": "gen/sword.png",
  "remove_bg": "quick",
  "bg_color": "auto",
  "canvas": "256x256",
  "padding": 16,
  "formats": ["png", "webp"]
}
```

### CLI

```powershell
# quick flood-fill cutout + canvas
python scripts/asset_pipeline.py run --input item.png `
  --remove-bg-quick auto --canvas 256x256 --padding 16 --out-dir output/images/edited

# combined edits
python scripts/asset_pipeline.py run --input item.png `
  --remove-bg-quick #FFFFFF --rotate 90 --flip h `
  --brightness 1.1 --saturation 1.2 --rounded 30 --border "4,#FF0000" `
  --exports png jpg --out-dir output/images/edited

# batch a whole folder (recursive)
python scripts/asset_pipeline.py batch --dir ./photos --rotate 90 --exports jpg

# batch manifest + sprite sheet
python scripts/asset_pipeline.py batch --manifest manifest.json
```

See [references/cli.md](references/cli.md) for the full CLI reference and
manifest schema, and `SKILL.md` for the agent-facing instructions.

## Recommended pipeline (with dsh-draw + vision-router)

```
dsh-draw / image_generate  (prompt: "flat solid white background, no shadows")
  → image_edit (remove_bg: quick, canvas, padding)  →  engine-ready PNG
  → batch manifest with "sheet" for a sprite atlas
```

For complex assets prefer `remove_bg: "rembg"`; for one-off visual checks of
the cutout use `vision_extract_foreground`.

## Requirements

- Python 3.10+ and [Pillow](https://pypi.org/project/pillow/) (required)
- `rembg` (optional, only for the `rembg` cutout mode)
- `oxipng` / `pngquant` (optional, auto-used when on PATH)

## License

MIT — see [LICENSE](LICENSE).
