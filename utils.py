import json
import os
import re
import shutil
import subprocess
from pathlib import Path


def run_cmd(args, cwd=None):
    p = subprocess.run(args, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if p.returncode != 0:
        raise RuntimeError(f'Command failed ({p.returncode}): {" ".join(map(str,args))}\n{p.stdout[-6000:]}')
    return p.stdout


def ffmpeg_exists():
    try:
        subprocess.run(['ffmpeg', '-version'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return True
    except Exception:
        return False


def ffprobe_json(path):
    out = run_cmd(['ffprobe', '-v', 'error', '-show_format', '-show_streams', '-of', 'json', str(path)])
    return json.loads(out)


def safe_name(value, max_len=80):
    value = re.sub(r'[^A-Za-z0-9._-]+', '_', value).strip('_')
    return value[:max_len] or 'clip'


def fmt_time(seconds):
    seconds = float(seconds)
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f'{h:02d}:{m:02d}:{s:06.3f}'


def find_ffmpeg():
    """
    Find the FFmpeg executable.

    Checks (in order):
      1. FFMPEG_PATH environment variable
      2. ffmpeg on PATH
      3. Common Windows install locations

    Returns a Path to the executable.
    Raises FileNotFoundError with a helpful message if not found.
    """
    # 1. Environment variable
    env_path = os.environ.get('FFMPEG_PATH')
    if env_path:
        p = Path(env_path)
        if p.exists():
            return p

    # 2. PATH
    which_path = shutil.which('ffmpeg')
    if which_path:
        return Path(which_path)

    # 3. Common Windows locations
    common_paths = [
        Path(r'C:\ffmpeg\bin\ffmpeg.exe'),
        Path(r'C:\Program Files\ffmpeg\bin\ffmpeg.exe'),
        Path(r'C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe'),
        Path.home() / 'AppData' / 'Local' / 'Microsoft' / 'WinGet' / 'Links' / 'ffmpeg.exe',
        Path(r'D:\charlie youtube long videos\yt-dlp-master\.exe\ffmpeg.exe'),
    ]
    for p in common_paths:
        if p.exists():
            return p

    raise FileNotFoundError(
        'FFmpeg not found. Install FFmpeg and add it to PATH, '
        'or set the FFMPEG_PATH environment variable. '
        'See: https://ffmpeg.org/download.html'
    )


def has_audio_stream(source, ffmpeg_path=None):
    """
    Check whether a video file contains an audio stream.

    Returns True if audio is present (or if the check fails),
    False if the file definitely has no audio stream.
    """
    ffprobe_path = None

    if ffmpeg_path is not None:
        candidate = str(ffmpeg_path).replace('ffmpeg.exe', 'ffprobe.exe')
        if Path(candidate).exists():
            ffprobe_path = candidate

    if ffprobe_path is None:
        which_ffprobe = shutil.which('ffprobe')
        if which_ffprobe:
            ffprobe_path = which_ffprobe

    if ffprobe_path is None:
        # Cannot check — assume audio is present
        return True

    try:
        result = subprocess.run(
            [
                ffprobe_path,
                '-v', 'error',
                '-select_streams', 'a',
                '-show_entries', 'stream=index',
                '-of', 'csv=p=0',
                str(source),
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return bool(result.stdout.strip())
    except Exception:
        # Check failed — assume audio is present
        return True


# ---------------------------------------------------------
# JSON Job Manifest
# ---------------------------------------------------------

def save_job_manifest(path, job_data):
    """
    Save a job manifest to a JSON file.

    Args:
        path: Path to the manifest file
        job_data: Dictionary containing job state
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(job_data, indent=2), encoding='utf-8')


def load_job_manifest(path):
    """
    Load a job manifest from a JSON file.

    Returns the job data dictionary, or None if not found/invalid.
    """
    path = Path(path)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return None


def is_stage_completed(job_data, stage):
    """
    Check if a specific stage has been completed in the job manifest.

    Args:
        job_data: Dictionary containing job state
        stage: String name of the stage to check

    Returns True if the stage is marked as completed.
    """
    if not job_data:
        return False
    stages = job_data.get('stages', {})
    return stages.get(stage, False)


def update_job_stage(job_data, stage, completed=True, error=None):
    """
    Update the status of a specific stage in the job manifest.

    Args:
        job_data: Dictionary containing job state
        stage: String name of the stage
        completed: Boolean indicating if the stage is done
        error: Optional error message if the stage failed

    Returns the updated job data dictionary.
    """
    if 'stages' not in job_data:
        job_data['stages'] = {}

    job_data['stages'][stage] = completed

    if error is not None:
        job_data['error'] = error

    job_data['updated_at'] = __import__('datetime').datetime.now().isoformat()

    return job_data
