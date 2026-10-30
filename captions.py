"""
Viral word-by-word caption renderer for Debate Clipper.

Renders captions in the style of modern short-form social media:
- White text with heavy black outline
- Bright green active word
- Large bold typography
- Centered horizontally
- Word-by-word timing
"""
import html
from pathlib import Path


def ass_time(seconds):
    """Convert seconds to ASS time format (H:MM:SS.CC)."""
    seconds = max(0, float(seconds))
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    cs = int(round((s - int(s)) * 100))
    return f'{h}:{m:02d}:{int(s):02d}.{cs:02d}'


def ass_escape(s):
    """Escape special characters for ASS format."""
    return s.replace('\\', '\\\\').replace('{', '\\{').replace('}', '\\}')


def hex_to_ass(rgb):
    """Convert hex color to ASS color format (&HAABBGGRR)."""
    rgb = rgb.lstrip('#')
    if len(rgb) != 6:
        return '&H00FFFFFF'
    r, g, b = int(rgb[0:2], 16), int(rgb[2:4], 16), int(rgb[4:6], 16)
    return f'&H00{b:02X}{g:02X}{r:02X}'


def build_ass(
    transcript,
    clip_start,
    clip_end,
    output_path: Path,
    font='Arial',
    size=72,
    active_color='#00FF00',
    text_color='#FFFFFF',
    outline_color='#000000',
    outline_width=4,
    shadow_strength=3,
    y=1000,
    words_per_beat=3,
    animation_timing=0.05,
    punctuation_fix=True,
):
    """
    Build an ASS subtitle file with viral word-by-word captions.

    Args:
        transcript: Transcript dict with segments containing word timestamps
        clip_start: Start time of the clip in seconds
        clip_end: End time of the clip in seconds
        output_path: Path to write the ASS file
        font: Font name
        size: Font size in points
        active_color: Color of the active/current word (hex)
        text_color: Color of inactive words (hex)
        outline_color: Color of the text outline (hex)
        outline_width: Width of the outline in points
        shadow_strength: Strength of the shadow/glow effect
        y: Vertical position of captions (from top of video)
        words_per_beat: Number of words per caption beat
        animation_timing: Timing for word highlight animation

    Returns:
        Path to the generated ASS file
    """
    # Collect all words within the clip range
    words = []
    for seg in transcript.get('segments', []):
        for w in seg.get('words', []):
            if w['end'] >= clip_start and w['start'] <= clip_end:
                words.append({
                    'start': max(w['start'], clip_start) - clip_start,
                    'end': min(w['end'], clip_end) - clip_start,
                    'word': w['word'].strip()
                })

    if not words:
        # Write empty ASS file
        header = _build_ass_header(font, size, text_color, active_color, outline_color, outline_width, shadow_strength, y)
        output_path.write_text(header, encoding='utf-8')
        return output_path

    # Group words into beats
    lines = []
    for i in range(0, len(words), words_per_beat):
        group = words[i:i + words_per_beat]
        if not group:
            continue
        st = group[0]['start']
        en = group[-1]['end']
        parts = []
        for w in group:
            parts.append((w['start'], w['end'], w['word']))
        lines.append((st, en, parts))

    # Build ASS content
    header = _build_ass_header(font, size, text_color, active_color, outline_color, outline_width, shadow_strength, y)

    events = []
    for st, en, parts in lines:
        # Base line (all words in white)
        base_text = ' '.join(p[2] for p in parts)
        events.append(
            f'Dialogue: 0,{ass_time(st)},{ass_time(en)},Main,,0,0,0,,{ass_escape(base_text)}'
        )

        # Word-by-word highlighting
        for j, (ws, we, word) in enumerate(parts):
            # Build the line with this word highlighted
            before = []
            for k, (xst, xen, xword) in enumerate(parts):
                if k < j:
                    before.append(ass_escape(xword))
                elif k == j:
                    # Highlight this word
                    before.append(
                        r'{\c' + hex_to_ass(active_color)[1:] + r'}'
                        + ass_escape(xword)
                        + r'{\c' + hex_to_ass(text_color)[1:] + r'}'
                    )
                else:
                    before.append(ass_escape(xword))

            highlight_text = ' '.join(before)
            events.append(
                f'Dialogue: 1,{ass_time(ws)},{ass_time(we)},Main,,0,0,0,,{highlight_text}'
            )

    output_path.write_text(header + '\n'.join(events) + '\n', encoding='utf-8')
    return output_path


def _build_ass_header(font, size, text_color, active_color, outline_color, outline_width, shadow_strength, y):
    """Build the ASS file header with styles."""
    # Map font name to Inter font family
    font_name = "Inter" if "Inter" in font else font
    return f'''[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Main,{font_name},{size},{hex_to_ass(text_color)},{hex_to_ass(active_color)},{hex_to_ass(outline_color)},&H00000000,-1,0,0,0,100,100,0,0,1,{outline_width},{shadow_strength},2,80,80,{max(80, 1920 - int(y))},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
