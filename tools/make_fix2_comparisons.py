"""Make honest reference/before/after evidence triptychs for Fix Round 2."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def make_triptych(reference: Path, before: Path, after: Path, output: Path) -> None:
    from PIL import Image, ImageDraw

    images = [Image.open(path).convert("RGB") for path in (reference, before, after)]
    height = 620
    resized = []
    for image in images:
        width = max(1, round(image.width * height / image.height))
        resized.append(image.resize((width, height)))
    labels = ["Reference", "Before", "After"]
    widths = [image.width for image in resized]
    canvas = Image.new("RGB", (sum(widths), height + 42), "white")
    draw = ImageDraw.Draw(canvas)
    x = 0
    for label, image in zip(labels, resized):
        canvas.paste(image, (x, 42))
        draw.text((x + 8, 12), label, fill=(20, 35, 55))
        x += image.width
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output, format="PNG", optimize=True)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    fallback_reference = root / "reference image" / "Screenshot 2026-10-05 181036.png"
    ids = ("c_a9ef26901548", "c_3b29c90cfa17", "c_9ecc907d1157")
    for kind in ("framing", "captions"):
        reference = root / "reports" / "fix2" / kind / "reference" / "political_lens91_middle.png"
        if not reference.is_file():
            reference = fallback_reference
        for candidate in ids:
            before = root / "reports" / "fix2" / kind / "before" / f"{candidate}_before_middle.png"
            after_candidates = sorted((root / "reports" / "fix2" / kind / "after").glob(f"{candidate}_after*_middle.png"))
            after = after_candidates[-1] if after_candidates else None
            if reference.is_file() and before.is_file() and after and after.is_file():
                make_triptych(reference, before, after, root / "reports" / "fix2" / kind / "comparisons" / f"{candidate}_middle.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
