import os
import subprocess
import sys
import threading
import tempfile
import time
from pathlib import Path

from django.core.files import File

import imageio_ffmpeg

from .models import BackingTrack, Stem

def process_track(track_id):
    import numpy as np
    import yt_dlp
    import librosa

    ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
    os.environ['PATH'] = str(Path(ffmpeg_path).parent) + os.pathsep + os.environ.get('PATH', '')

    track = BackingTrack.objects.get(id=track_id)
    track.status = 'downloading'
    track.save()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        try:
            full_wav = tmpdir / 'full.wav'
            title_text = track.youtube_url

            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': {'default': str(tmpdir / 'full.%(ext)s'), 'thumbnail': str(tmpdir / 'thumb.%(ext)s')},
                'ffmpeg_location': ffmpeg_path,
                'prefer_ffmpeg': True,
                'noplaylist': True,
                'keepvideo': False,
                'retries': 3,
                'js_runtimes': {'node': {}},
                'writethumbnail': True,
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'wav',
                }],
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(track.youtube_url, download=True)
                title_text = info.get('title', track.youtube_url)

            for f in tmpdir.iterdir():
                if f.stem == 'thumb' and f.suffix in ('.jpg', '.jpeg', '.png', '.webp'):
                    with open(f, 'rb') as img_f:
                        track.image.save(f'thumb_{track.id}{f.suffix}', File(img_f), save=False)
                    break

            duration_secs = info.get('duration', 0)
            if duration_secs > 900:
                track.status = 'rejected'
                track.save()
                return

            if not full_wav.exists():
                for f in tmpdir.iterdir():
                    if f.suffix == '.wav':
                        full_wav = f
                        break

            track.status = 'processing'
            track.save()

            norm_wav = tmpdir / 'normalized.wav'
            subprocess.run(
                [ffmpeg_path, '-i', str(full_wav), '-af', 'loudnorm=I=-14:LRA=1:TP=-1', '-y', str(norm_wav)],
                capture_output=True, check=True,
            )
            full_wav = norm_wav

            y, sr = librosa.load(str(full_wav), sr=None)
            duration = float(librosa.get_duration(y=y, sr=sr))
            tempo_val = librosa.beat.tempo(y=y, sr=sr)
            if hasattr(tempo_val, 'ndim'):
                bpm = float(tempo_val.flat[0])
            else:
                bpm = float(tempo_val or 120.0)

            parts = title_text.split(' - ', 1)
            title = parts[1] if len(parts) > 1 else title_text
            artist = parts[0] if len(parts) > 1 else ''

            y_harm = librosa.effects.harmonic(y)
            tuning = librosa.estimate_tuning(y=y_harm, sr=sr)
            chroma = librosa.feature.chroma_cqt(y=y_harm, sr=sr, tuning=tuning)
            chroma_mean = np.mean(chroma, axis=1)
            ks_major = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
            ks_minor = [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]
            notes = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
            best_key = ''
            best_corr = -1
            for i in range(12):
                rm = ks_major[-i:] + ks_major[:-i]
                c = np.corrcoef(chroma_mean, rm)[0,1]
                if c > best_corr:
                    best_corr = c
                    best_key = f'{notes[i]} major'
                rn = ks_minor[-i:] + ks_minor[:-i]
                c = np.corrcoef(chroma_mean, rn)[0,1]
                if c > best_corr:
                    best_corr = c
                    best_key = f'{notes[i]} minor'

            track.title = title
            track.artist = artist
            track.bpm = bpm
            track.key = best_key
            track.duration = duration
            track.save()

            demucs_args = [
                sys.executable, '-m', 'demucs.separate',
                '-n', 'htdemucs_6s',
                '-j', '4',
                '-o', str(tmpdir / 'separated'),
                str(full_wav),
            ]

            result = subprocess.run(demucs_args, capture_output=True, text=True)
            if result.returncode != 0:
                log_dir = Path('media') / 'logs'
                log_dir.mkdir(parents=True, exist_ok=True)
                log_file = log_dir / f'demucs_{track.id}.log'
                log_file.write_text(f'rc={result.returncode}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}')
                result.check_returncode()

            sep_dir = tmpdir / 'separated' / 'htdemucs_6s' / full_wav.stem
            if not sep_dir.exists():
                stem_files = sorted((tmpdir / 'separated').rglob('*.wav'))
            else:
                stem_files = sorted(sep_dir.glob('*.wav'))

            stem_dir = Path('media') / 'stems' / track.user.username / str(track.id)
            stem_dir.mkdir(parents=True, exist_ok=True)

            for stem_file in stem_files:
                stem_name = stem_file.stem
                dest = stem_dir / f'{stem_name}.mp3'
                subprocess.run(
                    [ffmpeg_path, '-i', str(stem_file), '-ab', '128k', '-y', str(dest)],
                    capture_output=True, check=True,
                )

                Stem.objects.create(
                    backing_track=track,
                    name=stem_name,
                    audio_file=f'stems/{track.user.username}/{track.id}/{stem_name}.mp3',
                    duration=duration,
                )

            track.status = 'ready'
            track.save()

        except Exception:
            import traceback
            log_dir = Path('media') / 'logs'
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / f'error_{track.id}.log'
            with open(log_file, 'w') as f:
                traceback.print_exc(file=f)
            track.status = 'error'
            track.save()

def worker_loop():
    while True:
        try:
            track = BackingTrack.objects.filter(status='queued').order_by('created_at').first()
            if track:
                process_track(track.id)
            else:
                time.sleep(2)
        except Exception:
            import traceback
            traceback.print_exc()
            time.sleep(5)

def start_worker():
    thread = threading.Thread(target=worker_loop, daemon=True)
    thread.start()
