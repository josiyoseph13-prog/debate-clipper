from pathlib import Path
import json

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / 'assets'
INPUT = ROOT / 'input'
TRANSCRIPTS = ROOT / 'transcripts'
CLIPS = ROOT / 'clips'
OUTPUT = ROOT / 'output'
WORK = ROOT / 'work'
SETTINGS_FILE = ROOT / 'settings.json'

DEFAULT_SETTINGS = {
    # Account / Header
    'display_name': 'Political Lens',
    'username': '@political_lens',
    'verified': False,
    'avatar_path': None,
    'header_height': 280,
    'logo_size': 110,
    'header_bg_color': '#FFFFFF',
    'account_name_color': '#000000',
    'username_color': '#666666',
    'verified_badge_color': '#1DA1F2',

    # Hook / Headline
    'headline': '',
    'hook_font': 'Arial',
    'hook_size': 72,
    'hook_color': '#000000',
    'hook_line_spacing': 1.3,
    'hook_max_lines': 4,
    'hook_emoji_enabled': True,

    # Uncertainty fallback when active speaker is uncertain
    'active_speaker_fallback': 'prefer_charlie',

    # Video
    'video_quality': 'high',
    'video_codec': 'libx264',
    'video_crf': 20,
    'video_preset': 'veryfast',

    # Captions
    'font': 'Arial',
    'caption_size': 72,
    'caption_color': '#FFFFFF',
    'active_word_color': '#00FF00',
    'caption_outline_color': '#000000',
    'caption_outline_width': 4,
    'caption_shadow_strength': 3,
    'caption_y': 1000,
    'caption_words_per_beat': 3,
    'caption_animation_timing': 0.05,
    'caption_avoid_faces': True,
    'caption_face_threshold': 0.3,

    # Canvas
    'canvas_width': 1080,
    'canvas_height': 1920,
    'canvas_bg_color': '#FFFFFF',
    'canvas_rounded_corners': True,
    'canvas_corner_radius': 40,

    # Model
    'model': 'base',
    'ollama_enabled': False,
    'ollama_model': 'llama3.2:3b',
}


def ensure_dirs():
    for p in (ASSETS, INPUT, TRANSCRIPTS, CLIPS, OUTPUT, WORK):
        p.mkdir(parents=True, exist_ok=True)


def load_settings():
    ensure_dirs()
    if not SETTINGS_FILE.exists():
        return DEFAULT_SETTINGS.copy()
    try:
        data = json.loads(SETTINGS_FILE.read_text(encoding='utf-8'))
        result = DEFAULT_SETTINGS.copy()
        result.update(data)
        return result
    except Exception:
        return DEFAULT_SETTINGS.copy()


def save_settings(data):
    ensure_dirs()
    SETTINGS_FILE.write_text(json.dumps(data, indent=2), encoding='utf-8')
