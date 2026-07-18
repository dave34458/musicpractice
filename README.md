<div align="center">
  <br>
  <img src="static/backingtracks/img/logo.svg" alt="MusicPractice" width="600">
  <br>
  <br>
  <p><strong>A studio-grade web application for musicians to practise with AI-separated instrument stems.</strong></p>
  <br>
  <p>
    <img src="https://img.shields.io/badge/python-3.12+-blue.svg" alt="Python">
    <img src="https://img.shields.io/badge/django-4.2+-green.svg" alt="Django">
    <img src="https://img.shields.io/badge/demucs-htdemucs_6s-orange.svg" alt="Demucs">
    <img src="https://img.shields.io/badge/license-MIT-lightgrey.svg" alt="License">
  </p>
  <br>
</div>

---

## Overview

MusicPractice transforms any YouTube video into a personal practice tool. Submit a link, and the application downloads the audio, separates it into six individual stems using Demucs, detects the BPM and musical key, normalises loudness to broadcast standard, and presents a channel-strip mixer for isolated playback.

Designed for musicians who need to hear individual parts — vocals, drums, bass, guitar, piano — to learn, transcribe, or perform alongside their favourite tracks.

---

## Features

| | Status |
|---|---|
| **YouTube Import + Backing Track Creation** | ✓ Built |
| **Six-Stem AI Separation** (vocals, drums, bass, guitar, piano, other) | ✓ Built |
| **BPM and Key Detection** | ✓ Built |
| **Studio Mixer** (per-stem mute, solo, volume, master gain) | ✓ Built |
| **Chord Detection** | △ Planned |
| **Leaderboard Ranking** | △ Planned |

---

## Architecture

### Technology Stack

```
Backend         Django 4.2+ / Python 3.12 / SQLite
Frontend        Alpine.js · Tailwind CSS v4 · daisyUI v5
Audio Engine    Web Audio API (vanilla JavaScript)
Separation      Demucs (subprocess, -j 4 parallel chunks)
Analysis        librosa · numpy
Download        yt-dlp
Encoding        ffmpeg (via imageio-ffmpeg)
```

### Pipeline

```
YouTube URL  →  Queue  →  Download (yt-dlp)  →  Normalise (-14 LUFS)
     ↓
BPM + Key Detection (librosa)  →  Stem Separation (Demucs)
     ↓
Encode to MP3 (128 kbps)  →  Save to Database  →  Ready
```

### Project Structure

```
├── config/                  Django project settings
├── accounts/                User authentication
├── backingtracks/           Core application
│   ├── models.py            Track and stem data models
│   ├── views.py             All route handlers
│   ├── services.py          Processing pipeline and queue worker
│   └── urls.py              Route definitions
├── templates/               Django templates
│   └── backingtracks/       Player, dashboard, list, edit, status
├── static/
│   └── backingtracks/
│       ├── css/style.css    Application stylesheet
│       ├── js/
│       │   ├── audio-engine.js    Web Audio API engine
│       │   └── player-init.js     Alpine.js component
│       └── img/             Brand assets
├── media/                   User content (stems, thumbnails, logs)
├── manage.py
└── requirements.txt
```

---

## Setup

### Prerequisites

- Python 3.10 or later
- Node.js (required by yt-dlp for JavaScript extraction)
- Demucs model cache (~300 MB, downloaded on first use)

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd musicpractice

# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Collect static files
python manage.py collectstatic --noinput

# Start the development server
python manage.py runserver
```

Open `http://127.0.0.1:8000/`, register, and submit a YouTube URL to begin.

---

## Routes

| Method | Path | Description |
|---|---|---|
| GET | `/` | Dashboard with stats and recent tracks |
| GET | `/backingtracks/` | Track listing with status filter |
| POST | `/backingtracks/new/` | Submit a YouTube URL |
| GET | `/backingtracks/<id>/` | Player with channel strip mixer |
| GET | `/backingtracks/<id>/status/` | Processing status (JSON) |
| GET | `/backingtracks/<id>/edit/` | Edit metadata |
| POST | `/backingtracks/<id>/delete/` | Delete track |

---

## License

MIT
