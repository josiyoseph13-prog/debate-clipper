from pathlib import Path
import json
import yt_dlp
from utils import safe_name, find_ffmpeg


def download_youtube(url: str, output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)

    ffmpeg_path = find_ffmpeg()

    opts = {
        'format': 'bv*[height<=1080]+ba/b[height<=1080]',

        'merge_output_format': 'mp4',
        'ffmpeg_location': str(ffmpeg_path),
        'outtmpl': str(output_dir / '%(id)s.%(ext)s'),
        'noplaylist': True,
        'quiet': True,
        'no_warnings': False,
    }

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)

        video_id = info.get('id') or safe_name(url)

        path = Path(ydl.prepare_filename(info))

        if path.suffix.lower() != '.mp4':
            candidate = path.with_suffix('.mp4')
            if candidate.exists():
                path = candidate

        if not path.exists():
            matches = list(output_dir.glob(f'{video_id}.*'))

            if not matches:
                raise FileNotFoundError(
                    f'yt-dlp finished but output video was not found for {video_id}'
                )

            path = max(matches, key=lambda p: p.stat().st_mtime)

        metadata = {
            k: info.get(k)
            for k in (
                'id',
                'title',
                'duration',
                'channel',
                'uploader',
                'webpage_url',
                'description',
                'chapters',
                'heatmap',
                'upload_date',
                'license',
            )
        }

        (
            output_dir / f'{video_id}.metadata.json'
        ).write_text(
            json.dumps(metadata, indent=2),
            encoding='utf-8'
        )

        return path, metadata
