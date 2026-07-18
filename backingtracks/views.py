import io
import json
import shutil
from pathlib import Path

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.core.exceptions import ValidationError
from PIL import Image

from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

from .models import BackingTrack, Stem

@login_required
def dashboard(request):
    tracks = request.user.backingtracks.all()
    total = tracks.count()
    ready = tracks.filter(status='ready').count()
    processing = tracks.filter(status='processing').count()
    queued = tracks.filter(status='queued').count()
    recent = tracks.order_by('-created_at')[:5]
    return render(request, 'backingtracks/dashboard.html', {
        'total': total, 'ready': ready,
        'processing': processing, 'queued': queued,
        'recent': recent,
    })

@login_required
def backingtracks_list(request):
    tracks = request.user.backingtracks.all()
    return render(request, 'backingtracks/backingtracks_list.html', {'tracks': tracks})

@login_required
@require_POST
def new_track(request):
    youtube_url = request.POST.get('youtube_url', '').strip()
    if not youtube_url:
        return redirect('/')
    parsed = urlparse(youtube_url)
    qs = parse_qs(parsed.query)
    qs.pop('list', None)
    qs.pop('start_radio', None)
    qs.pop('index', None)
    parsed = parsed._replace(query=urlencode(qs, doseq=True))
    youtube_url = urlunparse(parsed)
    youtube_url = youtube_url.rstrip('?')
    track = BackingTrack.objects.create(
        user=request.user,
        youtube_url=youtube_url,
        status='queued',
    )
    return redirect('track_status', track_id=track.id)

@login_required
def track_status(request, track_id):
    track = get_object_or_404(BackingTrack, id=track_id, user=request.user)
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        position = None
        if track.status == 'queued':
            position = BackingTrack.objects.filter(
                status='queued', created_at__lt=track.created_at
            ).count() + 1
        return JsonResponse({
            'status': track.status,
            'position': position,
        })
    return render(request, 'backingtracks/processing.html', {'track': track})

@login_required
def track_player(request, track_id):
    track = get_object_or_404(BackingTrack, id=track_id, user=request.user)
    if track.status != 'ready':
        return redirect('track_status', track_id=track.id)

    stems = track.stems.all()
    stems_data = []
    for stem in stems:
        stems_data.append({
            'name': stem.name,
            'url': stem.audio_file.url,
            'duration': stem.duration,
        })

    return render(request, 'backingtracks/player.html', {
        'track': track,
        'stems_json': json.dumps(stems_data),
    })

@login_required
@require_POST
def delete_track(request, track_id):
    track = get_object_or_404(BackingTrack, id=track_id, user=request.user)
    stem_dir = Path('media') / 'stems' / str(track.user.username) / str(track.id)
    if stem_dir.exists():
        shutil.rmtree(str(stem_dir))
    track.delete()
    return redirect('dashboard')

@login_required
def edit_track(request, track_id):
    track = get_object_or_404(BackingTrack, id=track_id, user=request.user)
    stems = track.stems.all()

    if request.method == 'POST':
        track.title = request.POST.get('title', '')
        track.artist = request.POST.get('artist', '')
        bpm_val = request.POST.get('bpm', '').strip()
        track.bpm = float(bpm_val) if bpm_val else None
        track.key = request.POST.get('key', '')

        stem_names = request.POST.getlist('stem_name')
        for i, stem in enumerate(stems):
            if i < len(stem_names) and stem_names[i].strip():
                stem.name = stem_names[i].strip()
                stem.save()

        if request.FILES.get('image'):
            img_file = request.FILES['image']
            if img_file.size > 5 * 1024 * 1024:
                raise ValidationError('Image must be under 5MB')
            try:
                img = Image.open(io.BytesIO(img_file.read()))
                img.verify()
                img_file.seek(0)
                if img.format not in ('JPEG', 'PNG'):
                    raise ValidationError('Only JPEG and PNG allowed')
            except Exception:
                raise ValidationError('Invalid image file')
            track.image = img_file

        track.save()
        return redirect('track_player', track_id=track.id)

    return render(request, 'backingtracks/edit_track.html', {
        'track': track,
        'stems': stems,
    })
