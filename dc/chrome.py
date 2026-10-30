from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:  # doctor and selection remain usable before optional install
    Image = None
    ImageDraw = None
    ImageFont = None

from .core.config import AppConfig, ROOT
from .core.io import atomic_write_json
from .core.hashing import file_hash
from .layout import fit_headline

EMOJI_MAP={"🎓":"education","⚖️":"law","💰":"economy","🏛️":"government","🗳️":"elections","🛂":"immigration","🔫":"guns","🩺":"health","👀":"eyes","😳":"flushed","🤔":"thinking","🥲":"tear","💔":"broken_heart","🔥":"fire","😮":"wow","🤦":"facepalm","💥":"boom"}


def emoji_image(text:str,pixels:int,config):
    font_path=ROOT/config.get("hook","emoji_font",default="assets/fonts/NotoColorEmoji.ttf")
    font=ImageFont.truetype(str(font_path),int(config.get("hook","emoji_strike_px",default=109)))
    glyph=Image.new("RGBA",(160,160),(0,0,0,0))
    ImageDraw.Draw(glyph).text((0,0),text,font=font,embedded_color=True)
    missing=Image.new("RGBA",glyph.size,(0,0,0,0))
    ImageDraw.Draw(missing).text((0,0),"\U0010ffff",font=font,embedded_color=True)
    if glyph.tobytes()==missing.tobytes():raise ValueError("Emoji is the font's missing-glyph bitmap")
    box=glyph.getbbox()
    if not box: raise ValueError("Empty emoji glyph")
    glyph=glyph.crop(box)
    glyph.thumbnail((pixels,pixels),Image.Resampling.LANCZOS)
    return glyph


def _font(size: int, bold: bool = False, config: AppConfig | None = None, font_file: str | None = None):
    if ImageFont is None:
        raise RuntimeError("Pillow is required for chrome rendering")
    candidates = []
    if config:
        candidates.append(ROOT / (font_file or ("assets/fonts/Poppins-SemiBold.ttf" if bold else config.get("header", "handle", "font", default="assets/fonts/Poppins-Regular.ttf"))))
        candidates.append(ROOT / "assets" / "fonts" / ("Inter-Bold.ttf" if bold else "Inter-Regular.ttf"))
    candidates += [Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"), Path("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf")]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def _placeholder_logo(diameter: int) -> Image.Image:
    if Image is None or ImageDraw is None:
        raise RuntimeError("Pillow is required for chrome rendering")
    image = Image.new("RGBA", (diameter, diameter), (255, 255, 255, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((0, 0, diameter - 1, diameter - 1), fill="#EC0000")
    draw.ellipse((diameter * 0.18, diameter * 0.18, diameter * 0.82, diameter * 0.82), outline="#FFFFFF", width=max(2, diameter // 24))
    draw.ellipse((diameter * 0.42, diameter * 0.42, diameter * 0.58, diameter * 0.58), fill="#FFFFFF")
    return image


def _asset_or_placeholder(path: Path, diameter: int) -> Image.Image:
    if path.exists():
        try:
            with Image.open(path) as opened:
                image = opened.convert("RGBA")
            image.thumbnail((diameter, diameter), Image.Resampling.LANCZOS)
            canvas = Image.new("RGBA", (diameter, diameter), (255, 255, 255, 0))
            canvas.alpha_composite(image, ((diameter - image.width) // 2, (diameter - image.height) // 2))
            return canvas
        except Exception:
            pass
    return _placeholder_logo(diameter)


def render_chrome(config: AppConfig, headline: str = "", output_path: Path | None = None, brand: dict[str, Any] | None = None) -> tuple[Image.Image, dict[str, Any]]:
    if Image is None or ImageDraw is None:
        raise RuntimeError("Pillow is required for chrome rendering; install requirements.txt")
    canvas = config.canvas
    regions = config.regions
    # Chrome owns every row above the feed, including the reserved top band and hook gap.
    header_h = int(regions["feed"]["y"])
    image = Image.new("RGBA", (int(canvas["w"]), header_h), canvas.get("bg", "#FFFFFF"))
    draw = ImageDraw.Draw(image)
    header = config.data["header"]
    logo = header["logo"]
    logo_path = ROOT / logo.get("file", "assets/logo.png")
    avatar = _asset_or_placeholder(logo_path, int(logo["d"]))
    mask = Image.new("L", avatar.size, 0)
    ImageDraw.Draw(mask).ellipse((0, 0, avatar.width - 1, avatar.height - 1), fill=255)
    image.paste(avatar, (int(logo["x"]), int(logo["y"])), mask)

    brand = brand or {}
    wordmark = str(brand.get("wordmark", "POLITICAL LENS"))
    lettering_text = "POLITICALLENS" if wordmark == "POLITICAL LENS" else wordmark
    handle = str(brand.get("handle", header["handle"]["text"]))
    wx = int(header["wordmark"]["x"])
    wm = header["wordmark"]
    wordmark_path = ROOT / wm.get("file", "assets/wordmark.png")
    if wordmark_path.is_file():
        with Image.open(wordmark_path) as asset:
            lettering = asset.convert("RGBA")
        bounds = lettering.getbbox()
        if bounds:
            lettering = lettering.crop(bounds)
        lettering.thumbnail((int(wm["ink_w"]), int(wm["cap_h"])), Image.Resampling.LANCZOS)
        image.alpha_composite(lettering, (wx, int(wm["cap_top"])))
        wordmark_box = [wx, int(wm["cap_top"]), wx + lettering.width, int(wm["cap_top"]) + lettering.height]
    else:
        size = 1
        for candidate_size in range(1, int(wm["cap_h"]) * 3):
            font = _font(candidate_size, True, config, wm.get("live_font"))
            box = font.getbbox(lettering_text)
            if box[2] - box[0] > wm["ink_w"] or box[3] - box[1] > wm["cap_h"]:
                break
            size = candidate_size
        name_font = _font(size, True, config, wm.get("live_font"))
        box = name_font.getbbox(lettering_text)
        draw.text((wx - box[0], int(wm["cap_top"]) - box[1]), lettering_text, font=name_font, fill="#3F3F3F")
        if wordmark == "POLITICAL LENS":
            lens_x = wx - box[0] + draw.textlength("POLITICAL", font=name_font)
            draw.text((lens_x, int(wm["cap_top"]) - box[1]), "LENS", font=name_font, fill="#EC0000")
        wordmark_box = [wx, int(wm["cap_top"]), wx + box[2] - box[0], int(wm["cap_top"]) + box[3] - box[1]]
    handle_size = 1
    for candidate_size in range(1, int(header["logo"]["d"])):
        candidate_font = _font(candidate_size, False, config)
        box = candidate_font.getbbox(handle)
        if box[2] - box[0] > header["handle"]["ink_w"]:
            break
        handle_size = candidate_size
    handle_font = _font(handle_size, False, config)
    handle_box = handle_font.getbbox(handle)
    hx, hy = int(header["handle"]["x"]), int(header["handle"]["ink_top"])
    draw.text((hx - handle_box[0], hy - handle_box[1]), handle, font=handle_font, fill=header["handle"]["color"])

    badge = header["badge"]
    if badge.get("mode") != "none":
        bx, by, diameter = int(badge["x"]), int(badge["y"]), int(badge["d"])
        draw.ellipse((bx, by, bx + diameter, by + diameter), fill=badge["color"])
        if badge.get("mode") == "platform_style":
            draw.line((bx + 12, by + diameter // 2, bx + 22, by + diameter - 14), fill="white", width=5)
            draw.line((bx + 22, by + diameter - 14, bx + diameter - 10, by + 12), fill="white", width=5)
        else:
            draw.ellipse((bx + 14, by + 14, bx + diameter - 14, by + diameter - 14), outline="white", width=3)
            draw.ellipse((bx + 22, by + 22, bx + diameter - 22, by + diameter - 22), fill="white")

    hook_font_path = ROOT / config.get("hook","font",default="assets/fonts/Poppins-SemiBold.ttf")
    emoji=next((key for key in EMOJI_MAP if headline.rstrip().endswith(key)),None)
    emoji_warning=None
    if emoji:
        headline=headline.rstrip()[:-len(emoji)].rstrip()
    fit = fit_headline(headline, config, hook_font_path if hook_font_path.exists() else None)
    if not fit["fit"]:raise ValueError("Headline does not fit its hook band")
    hook = config.data["hook"]
    lines = fit["lines"]
    hook_font = _font(int(fit["font_px"]), True, config,config.get("hook","font"))
    pitch = int(fit["font_px"] * float(hook.get("line_pitch", 1.04)))
    baseline = int(regions["hook"]["last_baseline"])
    start_y = baseline - (len(lines) - 1) * pitch
    hook_layer=Image.new("RGBA",image.size,(0,0,0,0))
    hook_draw=ImageDraw.Draw(hook_layer)
    for index, line in enumerate(lines):
        box = draw.textbbox((0, 0), line, font=hook_font)
        glyph = None
        glyph_gap = 0
        if emoji and index == len(lines)-1:
            try:
                glyph = emoji_image(emoji,round(fit["font_px"]*1.05),config)
                glyph_gap = round(fit["font_px"]*.25)
                if box[2]-box[0]+glyph.width+glyph_gap>hook["max_w"]:
                    raise ValueError("Emoji exceeds hook band")
            except (OSError,ValueError) as exc:
                emoji_warning="EMOJI_DROPPED: "+str(exc)
                glyph = None
                glyph_gap = 0
        total_width = box[2]-box[0]+(glyph.width+glyph_gap if glyph else 0)
        x = int(hook["center_x"] - total_width/2)
        hook_draw.text((x, start_y + index * pitch), line, font=hook_font, fill=hook["color"], anchor="ls")
        if glyph:
            ex=x+box[2]-box[0]+glyph_gap
            hook_layer.alpha_composite(glyph,(ex,start_y+index*pitch-glyph.height))

    ink=hook_layer.getbbox()
    shift=0
    if ink:
        # A requested baseline can put lowercase descenders below the hard hook
        # band. Keep font size/reference width, move only the measured overflow,
        # and record the effective baseline rather than silently clipping ink.
        shift=min(0,int(regions["hook"]["bottom"])-ink[3])
        ink=(ink[0],ink[1]+shift,ink[2],ink[3]+shift)
        left=regions["hook"].get("x",hook["center_x"]-hook["max_w"]/2)
        if ink[0]<left or ink[2]>left+hook["max_w"] or ink[1]<regions["hook"]["top_limit"] or ink[3]>regions["hook"]["bottom"]:
            raise ValueError("Measured headline ink leaves the hook band")
    image.alpha_composite(hook_layer,(0,shift))
    fit.update({"ink_box":list(ink) if ink else None,"requested_baseline":baseline,"effective_baseline":baseline+shift,"baseline_shift_px":shift})

    manifest = {"schema_version": 5, "width": image.width, "height": image.height, "headline": fit, "badge_mode": badge.get("mode"), "placeholder_logo": not logo_path.exists(), "placeholder_wordmark": not wordmark_path.exists(), "wordmark_box": wordmark_box, "handle_box": [hx, hy, hx + handle_box[2] - handle_box[0], hy + handle_box[3] - handle_box[1]],"emoji_warning":emoji_warning}
    manifest["logo"]={"file":str(logo_path.relative_to(ROOT)),"sha256":file_hash(logo_path) if logo_path.is_file() else None,"user_supplied":bool(logo.get("user_supplied")),"box":[logo["x"],logo["y"],logo["d"],logo["d"]],"operation":"uniform thumbnail and circular mask; original artwork retained"}
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        image.convert("RGB").save(output_path, format="PNG", optimize=False)
        atomic_write_json(output_path.with_suffix(".json"), manifest)
    return image, manifest


def render_extras(config: AppConfig, output_path: Path, source_label: str = "") -> Path:
    """Render optional bottom-band extras on a separate transparent layer."""
    if Image is None or ImageDraw is None:
        raise RuntimeError("Pillow is required for bottom-band extras")
    canvas = config.canvas
    image = Image.new("RGBA", (int(canvas["w"]), int(canvas["h"])), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    source_credit = config.get("polish", "source_credit", default={})
    if source_credit.get("enabled"):
        draw.text((canvas["w"] // 2, int(source_credit.get("y", 1790))), f"Source: {source_label} · full video in bio", font=_font(int(source_credit.get("px", 28)), False, config), fill="#7F7F7F", anchor="mm")
    image.save(output_path, format="PNG", optimize=False)
    return output_path
