"""
Configurable header renderer for Debate Clipper.

Renders a white header with logo, account name, username,
and optional verified badge. Uses Inter font.
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# Project-local Inter font directory
_FONTS_DIR = Path(__file__).resolve().parent.parent / 'assets' / 'fonts'


def _font(size, bold=False):
    """
    Load Inter font, falling back to system fonts if unavailable.

    Search order:
      1. Project-local assets/fonts/Inter-*.ttf
      2. Windows system fonts
      3. DejaVu Sans (Linux)
      4. Default bitmap font (last resort)
    """
    # 1. Project-local Inter fonts
    if bold:
        inter_path = _FONTS_DIR / 'Inter-Bold.ttf'
    else:
        inter_path = _FONTS_DIR / 'Inter-Regular.ttf'

    if inter_path.exists():
        return ImageFont.truetype(str(inter_path), size)

    # 2. Windows system fonts
    system_fonts = [
        'C:/Windows/Fonts/arialbd.ttf' if bold else 'C:/Windows/Fonts/arial.ttf',
        'C:/Windows/Fonts/segoeuib.ttf' if bold else 'C:/Windows/Fonts/segoeui.ttf',
    ]
    for p in system_fonts:
        if Path(p).exists():
            return ImageFont.truetype(p, size)

    # 3. DejaVu Sans (Linux)
    dejavu = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf' if bold else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
    if Path(dejavu).exists():
        return ImageFont.truetype(dejavu, size)

    # 4. Last resort
    return ImageFont.load_default()


def render_header(
    width=1080,
    height=280,
    display_name='Political Lens',
    username='@political_lens',
    verified=False,
    avatar_path=None,
    logo_size=110,
    bg_color='#FFFFFF',
    name_color='#000000',
    username_color='#666666',
    badge_color='#1DA1F2',
):
    """
    Render the account header.

    Returns a PIL Image of size (width, height).
    """
    im = Image.new('RGB', (width, height), bg_color)
    d = ImageDraw.Draw(im)

    x = 40
    y = (height - logo_size) // 2

    # Avatar
    if avatar_path and Path(avatar_path).exists():
        try:
            av = Image.open(avatar_path).convert('RGB').resize((logo_size, logo_size))
        except Exception:
            av = Image.new('RGB', (logo_size, logo_size), (220, 220, 220))
    else:
        av = Image.new('RGB', (logo_size, logo_size), (220, 220, 220))

    # Circular mask
    mask = Image.new('L', (logo_size, logo_size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, logo_size, logo_size), fill=255)
    im.paste(av, (x, y), mask)

    # Account name
    name_x = x + logo_size + 24
    name_y = y + 10
    d.text((name_x, name_y), display_name, font=_font(44, True), fill=name_color)

    # Username
    username_y = name_y + 56
    d.text((name_x, username_y), username, font=_font(30), fill=username_color)

    # Verified badge
    if verified:
        # Draw a checkmark badge
        badge_x = name_x + int(len(display_name) * 22) + 10
        badge_y = name_y + 8
        badge_size = 28
        d.ellipse(
            (badge_x, badge_y, badge_x + badge_size, badge_y + badge_size),
            fill=badge_color,
        )
        # Checkmark
        d.line(
            (badge_x + 6, badge_y + 14, badge_x + 12, badge_y + 20),
            fill='white',
            width=3,
        )
        d.line(
            (badge_x + 12, badge_y + 20, badge_x + 22, badge_y + 8),
            fill='white',
            width=3,
        )

    return im


def render_hook(
    width=1080,
    height=200,
    text='',
    font_name='Arial',
    font_size=72,
    text_color='#000000',
    line_spacing=1.3,
    max_lines=4,
    bg_color='#FFFFFF',
):
    """
    Render the hook/headline area.

    Returns a PIL Image of size (width, height).
    """
    im = Image.new('RGB', (width, height), bg_color)
    d = ImageDraw.Draw(im)

    if not text:
        return im

    # Word wrap
    words = text.split()
    lines = []
    current_line = ''
    for word in words:
        test_line = (current_line + ' ' + word).strip()
        bbox = d.textbbox((0, 0), test_line, font=_font(font_size, True))
        if bbox[2] > width - 80:
            if current_line:
                lines.append(current_line)
            current_line = word
        else:
            current_line = test_line
    if current_line:
        lines.append(current_line)

    # Limit lines
    lines = lines[:max_lines]

    # Draw centered
    line_height = int(font_size * line_spacing)
    total_height = len(lines) * line_height
    start_y = (height - total_height) // 2

    for i, line in enumerate(lines):
        bbox = d.textbbox((0, 0), line, font=_font(font_size, True))
        line_width = bbox[2] - bbox[0]
        x = (width - line_width) // 2
        y = start_y + i * line_height
        d.text((x, y), line, font=_font(font_size, True), fill=text_color)

    return im
