# MusicPractice

The goal is to get you to play and produce the songs you love better. MusicPractice turns what you listen to into material you can work with.

- **Version:** v0.0.1
- **Maturity:** Basic - deployed, actively developed

[![Python](https://img.shields.io/badge/Python-3.12-blue?style=flat-square&logo=python)](https://www.python.org)
[![Django](https://img.shields.io/badge/Django-4.2-green?style=flat-square&logo=django)](https://www.djangoproject.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](LICENSE)
[![Deploy](https://img.shields.io/github/actions/workflow/status/dave34458/musicpractice/deploy.yml?style=flat-square&label=Deploy)](https://github.com/dave34458/musicpractice/actions)

Live instance: [https://mscprctc.duckdns.org](https://mscprctc.duckdns.org)

## Features

| Feature | What it does |
| --- | --- |
| **Stem separation** | Splits a track into six stems (vocals, drums, bass, guitar, keys, other) with Demucs; each gets its own channel strip (mute, solo, volume) and an analyzer readout. |
| **MIDI transcription** | Turns uploaded audio into a MIDI piano roll with in-browser playback. |
| **Chord charts** | Pulls chord charts from an online database and renders the chords over the right words, with simplify and transpose. |
| **Playlists** | Reusable sets of tracks. |
| **Dashboard** | Per-user statistics: processing state, practice time, BPM range and speed distribution, key distribution, practice calendar. |

## How it works

Each subsystem runs its own worker, a daemon thread polling for `status='queued'` (FIFO by `created_at`).

### Backing tracks

1. **Download** - `yt-dlp` pulls `bestaudio`, post-processes it to WAV with `FFmpegExtractAudio`, writes the thumbnail, rejects anything over 900 seconds.
2. **Normalize** - `ffmpeg` loudnorm to `I=-14:LRA=1:TP=-1`.
3. **Analyze** - `librosa.load(sr=None)` and `beat.tempo` for BPM; key is a Krumhansl-Schmuckler fit: `estimate_tuning` feeds tuning-corrected `chroma_cqt`; the pitch-class vector is Pearson-correlated against the KS major/minor profiles, argmax over 12 rotations.
4. **Stem separation** - `python -m demucs.separate -n htdemucs_6s -j 4`, then each stem is transcoded to 128 kbps MP3.

### MIDI

1. **Filter** - instrument names from the submit form are validated against `MT3_FULL_PLUS_GROUP_NAMES`.
2. **Transcribe** - the MuScript model runs with `prelude_forcing=True`; note events stream in as `NoteStartEvent`/`NoteEndEvent`.
3. **Serialize** - events are written to JSON for the piano roll, then compiled to a `.mid` via `events_to_midi_bytes`.

A failed job leaves a traceback in `media/logs/` and sets the status to `error`. The two worker subsystems run independently.

### Chord charts

1. **Search** - pulls the index out of a page-serialized JSON blob, filters out gated tabs, and ranks results with a `score_result` heuristic.
2. **Parse** - `chart_parser` drops tuning/tab/preamble lines via `TUNING_PATTERN`/`TAB_LINE`, reconstructs chord offsets from inline `[ch]...[/ch]` markers into a fixed-width char array, and splits the progression on `SECTION_PATTERN` labels.
3. **Align** - every chord is re-anchored to the nearest lyric word token by index distance; a `simplify_chord` pass reduces each token to `root + quality`, and `chart.js` transposes per-token by semitones while keeping alignment.

## Architecture

Django 4.2 running four apps - `accounts`, `backingtracks`, `chordfinder`, `midis`. Each app has its own models, views, and URL routes under one `config` project.

Heavy processing runs out of band. On startup, `backingtracks.apps.ready()` resets any stuck (`downloading`/`processing`) tracks back to `queued` and launches a daemon worker thread; `midis.services.start_worker()` starts the second one. Each worker polls its table for the oldest `queued` row and processes it serially, so CPU-heavy jobs (Demucs, MuScript) never block a request.

The frontend is Django templates plus minimal Alpine.js; stems playback runs in the browser on the Web Audio API.

## Development workflow

Push to `main` triggers `.github/workflows/deploy.yml`, which SSHes to the GCP VM and runs `deploy/deploy.sh`. The service runs under systemd (`musicpractice.service`) behind nginx on `mscprctc.duckdns.org`.

## Project structure

```text
accounts/       users, profiles, instruments, genres
backingtracks/  dashboard, library, player, playlists
chordfinder/    chord search and parsing
midis/          MIDI transcription and piano roll
templates/      Django templates
static/         static assets
deploy/         GCP provisioning and deployment
```

## Install

Manual setup in order:

```bash
git clone https://github.com/dave34458/musicpractice.git directory
cd directory
python -m venv .venv && .venv/Scripts/activate    # Windows
# or: source .venv/bin/activate                  # macOS / Linux
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Then open [http://127.0.0.1:8000/](http://127.0.0.1:8000/), register, and add a track from the dashboard.

### Tests

```bash
python manage.py test
```

### MIDI models

MIDI transcription needs two files, added once. Both are gitignored:

```text
models/muscriptor-small.safetensors
static/midis/audio/MuseScore_General.sf3
```

The first is MuScript-small from [`MuScriptor/MuScriptor-small`](https://huggingface.co/MuScriptor/MuScriptor-small) on Hugging Face (gated; accept the license first). The second is the soundfont from `MuScriptor/assets`. Without them, everything except MIDI transcription still works.