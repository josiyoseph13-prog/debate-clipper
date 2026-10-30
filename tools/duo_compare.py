"""Build honest visual contact sheets for the Duo-style evidence."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "reports" / "duo_style" / "compare"


def fit(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    image = image.convert("RGB")
    image.thumbnail(size)
    canvas = Image.new("RGB", size, "white")
    canvas.paste(image, ((size[0] - image.width) // 2, (size[1] - image.height) // 2))
    return canvas


def sheet(name: str, left: list[Path], right: list[Path], left_label: str, right_label: str) -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    tile = (360, 640)
    row_height = 680
    output = Image.new("RGB", (tile[0] * 2, row_height * len(left) + 44), "white")
    draw = ImageDraw.Draw(output)
    draw.text((8, 12), f"{left_label}  |  {right_label}", fill="black")
    for index, (left_path, right_path) in enumerate(zip(left, right)):
        y = 44 + index * row_height
        output.paste(fit(Image.open(left_path), tile), (0, y))
        output.paste(fit(Image.open(right_path), tile), (tile[0], y))
        draw.text((8, y + 4), left_path.stem, fill="black")
        draw.text((tile[0] + 8, y + 4), right_path.stem, fill="black")
    output.save(DEST / name, quality=92)


def main() -> int:
    reference = sorted((ROOT / "reports/duo_style/frames/reference_6").glob("frame_*.jpg"))
    built = sorted((ROOT / "reports/duo_style/exports/real_smart_unknown/after").glob("*.png"))
    if len(reference) < len(built) or not built:
        raise RuntimeError("Duo reference or built sample frames are missing")
    # The supplied references are edited outputs, while the built samples use
    # the real raw source. The sheet compares visual style only, not content or
    # synchronized moments.
    indices = [round(i * (len(reference) - 1) / (len(built) - 1)) for i in range(len(built))]
    sheet(
        "reference_6_vs_built_style_only.jpg",
        [reference[index] for index in indices],
        built,
        "Supplied edited reference 6",
        "Built Duo from raw source",
    )

    other = sorted((ROOT / "reports/duo_style/exports/different_clip/after").glob("*.png"))
    source = sorted((ROOT / "reports/duo_style/exports/different_clip/before").glob("*.png"))
    if len(other) != len(source) or not other:
        raise RuntimeError("Different-clip before/after samples are missing")
    sheet("different_clip_before_vs_duo.jpg", source, other, "Different clip source", "Built Duo")
    print({"reference_sheet": "reports/duo_style/compare/reference_6_vs_built_style_only.jpg", "different_clip_sheet": "reports/duo_style/compare/different_clip_before_vs_duo.jpg", "samples_each": len(built)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
