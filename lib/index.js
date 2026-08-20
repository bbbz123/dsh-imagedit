/**
 * dsh-imagedit — local image editing tool for DeepSeek Harness.
 *
 * Registers a single `image_edit` tool that wraps the bundled Python CLI
 * (`scripts/asset_pipeline.py`) with structured parameters, so the agent can
 * call it directly without hand-building shell commands.
 *
 * Requirements at runtime: a `python` (or `python3`) interpreter with Pillow.
 * rembg is optional and only used for the `rembg` cutout mode.
 * Override the interpreter with the DSH_IMAGEDIT_PYTHON environment variable.
 */
import { defineTool } from "@deepseek-ai/dsh-tools";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { fileURLToPath } from "node:url";
import path from "node:path";

const execFileAsync = promisify(execFile);

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const SCRIPT = path.join(ROOT, "scripts", "asset_pipeline.py");

function pickPython() {
  if (process.env.DSH_IMAGEDIT_PYTHON) return process.env.DSH_IMAGEDIT_PYTHON;
  return process.platform === "win32" ? "python" : "python3";
}

async function runCli(args) {
  const python = pickPython();
  try {
    const { stdout } = await execFileAsync(python, [SCRIPT, ...args], {
      timeout: 600000,
      maxBuffer: 16 * 1024 * 1024,
    });
    return stdout
      .trim()
      .split(/\r?\n/)
      .filter((line) => line.length > 0);
  } catch (err) {
    const detail = err && err.stderr ? `\n${err.stderr}` : "";
    throw new Error(`dsh-imagedit: python CLI failed (${err && err.message ? err.message : err}${detail})`);
  }
}

function imageEditTool() {
  return defineTool({
    name: "image_edit",
    description:
      "Edit a local image deterministically with local operations (no AI, no network): cutout (quick flood-fill for flat solid backgrounds, or rembg AI), trim transparent margins, flip, rotate, brightness/contrast/saturation, gaussian blur, sharpen, rounded corners, border, padding, canvas resize+center, and export PNG/JPEG/WebP. Returns the output file paths. Show results to the user with vision_present.",
    parameters: {
      input: {
        type: "string",
        description:
          "Path to the source image file (use vision_materialize first if you only have an attachment id).",
        required: true,
      },
      remove_bg: {
        type: "string",
        enum: ["quick", "rembg"],
        description:
          "quick = flood-fill cutout for flat solid backgrounds (recommended for generated art, no model download); rembg = AI cutout (requires rembg installed).",
      },
      bg_color: {
        type: "string",
        description:
          "Background color for the quick cutout as #RRGGBB, or 'auto' to sample the corners (default auto).",
      },
      trim: {
        type: "boolean",
        description: "Trim transparent margins (default true).",
      },
      flip: {
        type: "string",
        enum: ["h", "v"],
        description: "Flip horizontally (h) or vertically (v).",
      },
      rotate: {
        type: "integer",
        description: "Rotate by degrees (90/180/270 are lossless).",
      },
      brightness: { type: "number", description: "Brightness multiplier (default 1.0)." },
      contrast: { type: "number", description: "Contrast multiplier (default 1.0)." },
      saturation: { type: "number", description: "Saturation multiplier (default 1.0)." },
      blur: { type: "number", description: "Gaussian blur radius in pixels." },
      sharpen: { type: "number", description: "Sharpening amount (0..~4)." },
      rounded: { type: "integer", description: "Rounded-corner radius in pixels." },
      border: {
        type: "string",
        description: "Border as 'WIDTH[,#RRGGBB]', e.g. '4,#FF0000' (default color #000000).",
      },
      canvas: {
        type: "string",
        description: "Scale and center onto a fixed canvas, e.g. '256x256'.",
      },
      padding: { type: "integer", description: "Even padding around the image in pixels." },
      formats: {
        type: "array",
        items: { type: "string", enum: ["png", "jpg", "webp"] },
        description: "Output formats (default ['png','webp']).",
      },
      quality: { type: "integer", description: "JPEG/WebP quality (default 92)." },
      out_dir: {
        type: "string",
        description: "Output directory (default ./output/images/edited).",
      },
    },
    output: {
      schema: {
        type: "object",
        properties: {
          ok: { type: "boolean", const: true },
          outputs: { type: "array", items: { type: "string" } },
        },
        additionalProperties: false,
      },
    },
    async execute(args) {
      const cli = ["run", "--input", args.input];
      if (args.remove_bg === "quick") cli.push("--remove-bg-quick", args.bg_color || "auto");
      else if (args.remove_bg === "rembg") cli.push("--remove-bg");
      if (args.trim === false) cli.push("--no-trim");
      if (args.flip) cli.push("--flip", args.flip);
      if (args.rotate != null) cli.push("--rotate", String(args.rotate));
      if (args.brightness != null && args.brightness !== 1)
        cli.push("--brightness", String(args.brightness));
      if (args.contrast != null && args.contrast !== 1)
        cli.push("--contrast", String(args.contrast));
      if (args.saturation != null && args.saturation !== 1)
        cli.push("--saturation", String(args.saturation));
      if (args.blur != null && args.blur > 0) cli.push("--blur", String(args.blur));
      if (args.sharpen != null && args.sharpen > 0) cli.push("--sharpen", String(args.sharpen));
      if (args.rounded != null && args.rounded > 0) cli.push("--rounded", String(args.rounded));
      if (args.border) cli.push("--border", args.border);
      if (args.canvas) cli.push("--canvas", args.canvas);
      if (args.padding != null && args.padding > 0) cli.push("--padding", String(args.padding));
      if (args.formats && args.formats.length) cli.push("--exports", ...args.formats);
      if (args.quality != null) cli.push("--quality", String(args.quality));
      if (args.out_dir) cli.push("--out-dir", args.out_dir);

      const outputs = await runCli(cli);
      return { ok: true, outputs };
    },
  });
}

/**
 * @param {import("@deepseek-ai/cordis").Context} ctx
 */
export default function dshImagedit(ctx) {
  ctx.effect(() => ctx.tools.register(imageEditTool()), "dsh-imagedit: image_edit tool");
}
