import io
import json
import shutil
from pathlib import Path

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.core.exceptions import ValidationError
from django.db.models import Count, Avg, Sum, Min, Max, Q
from django.db.models.functions import TruncDate
from django.utils import timezone
from datetime import timedelta, date as date_mod
from collections import defaultdict
from PIL import Image

from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

from .models import BackingTrack, Stem, Playlist

@login_required
def dashboard(request):
    tracks = request.user.backingtracks.all()
    ready_tracks = tracks.filter(status='ready')

    # --- Stat cards ---
    total = tracks.count()
    ready = ready_tracks.count()
    processing = tracks.filter(status='processing').count()
    queued = tracks.filter(status='queued').count()
    error = tracks.filter(status='error').count()
    rejected = tracks.filter(status='rejected').count()
    stem_count = Stem.objects.filter(backing_track__user=request.user).count()

    # --- Duration ---
    ready_dur = ready_tracks.exclude(duration__isnull=True)
    dur_agg = ready_dur.aggregate(total=Sum('duration'), avg=Avg('duration'))
    total_seconds = dur_agg['total'] or 0
    avg_duration_sec = dur_agg['avg'] or 0
    practice_hours = int(total_seconds // 3600)
    practice_minutes = int((total_seconds % 3600) // 60)
    avg_duration_min = round(avg_duration_sec / 60, 1)

    # --- BPM stats ---
    ready_bpm = ready_tracks.exclude(Q(bpm__isnull=True) | Q(bpm=0))
    bpm_agg = ready_bpm.aggregate(avg=Avg('bpm'), mn=Min('bpm'), mx=Max('bpm'))
    bpm_avg = round(bpm_agg['avg'] or 0)
    bpm_min = round(bpm_agg['mn']) if bpm_agg['mn'] is not None else None
    bpm_max = round(bpm_agg['mx']) if bpm_agg['mx'] is not None else None

    bpm_slow = ready_bpm.filter(bpm__lt=80).count()
    bpm_medium = ready_bpm.filter(bpm__gte=80, bpm__lte=120).count()
    bpm_fast = ready_bpm.filter(bpm__gt=120).count()

    # --- Key distribution ---
    key_data = list(ready_tracks.exclude(key__exact='')
                    .values('key').annotate(cnt=Count('id')).order_by('-cnt'))
    total_keyed = sum(k['cnt'] for k in key_data)
    most_prolific_key = key_data[0] if key_data else None

    # --- Activity counts ---
    now = timezone.now()
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)
    added_this_week = tracks.filter(created_at__gte=week_ago).count()
    added_this_month = tracks.filter(created_at__gte=month_ago).count()

    # --- Streak (best consecutive days) ---
    date_qs = tracks.annotate(dt=TruncDate('created_at')) \
                    .values_list('dt', flat=True).distinct().order_by('dt')
    sorted_dates = list(date_qs)
    best_streak = 0
    cur = 0
    for i, d in enumerate(sorted_dates):
        if i == 0 or (d - sorted_dates[i-1]).days != 1:
            cur = 1
        else:
            cur += 1
        best_streak = max(best_streak, cur)

    # --- Heatmap (last 364 days, GitHub-style) ---
    heatmap_start_dt = now - timedelta(days=363)
    daily = tracks.filter(created_at__gte=heatmap_start_dt) \
                  .annotate(dt=TruncDate('created_at')) \
                  .values('dt').annotate(cnt=Count('id')).order_by('dt')
    daily_dict = defaultdict(int, ((d['dt'], d['cnt']) for d in daily))
    hcolors = ['#22222A', '#4A3A20', '#7A5A20', '#B8860E', '#FFA500']
    cells = []
    heatmap_start_date = heatmap_start_dt.date()
    for i in range(364):
        d = heatmap_start_date + timedelta(days=i)
        c = daily_dict.get(d, 0)
        lvl = c if c < 4 else 4
        cells.append({'date': d, 'weekday': d.isoweekday(),
                      'count': c, 'level': lvl, 'color': hcolors[lvl]})
    weeks_map = defaultdict(lambda: [None]*7)
    for cell in cells:
        iso_year, iso_week, _ = cell['date'].isocalendar()
        weeks_map[(iso_year, iso_week)][cell['weekday']-1] = cell
    heatmap_weeks = [weeks_map[k] for k in sorted(weeks_map.keys())]

    # --- First track date ---
    first_track = tracks.order_by('created_at').first()
    first_track_date = first_track.created_at if first_track else None

    # --- Success rate ---
    finished = ready + error + rejected
    success_rate = round(ready / finished * 100) if finished else 0

    # --- Recent ---
    recent = tracks.order_by('-created_at')[:7]

    return render(request, 'backingtracks/dashboard.html', {
        'total': total, 'ready': ready,
        'processing': processing, 'queued': queued,
        'error': error, 'rejected': rejected,
        'stem_count': stem_count,
        'practice_hours': practice_hours,
        'practice_minutes': practice_minutes,
        'avg_duration_min': avg_duration_min,
        'bpm_avg': bpm_avg, 'bpm_min': bpm_min, 'bpm_max': bpm_max,
        'bpm_slow': bpm_slow, 'bpm_medium': bpm_medium, 'bpm_fast': bpm_fast,
        'bpm_total': bpm_slow + bpm_medium + bpm_fast,
        'key_distribution': key_data, 'total_keyed': total_keyed,
        'most_prolific_key': most_prolific_key,
        'added_this_week': added_this_week,
        'added_this_month': added_this_month,
        'heatmap_weeks': heatmap_weeks,
        'best_streak': best_streak,
        'first_track_date': first_track_date,
        'success_rate': success_rate, 'finished': finished,
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

@login_required
def playlists(request):
    user_playlists = request.user.playlists.all()
    return render(request, 'backingtracks/playlists.html', {'playlists': user_playlists})

@login_required
def playlist_detail(request, playlist_id):
    playlist = get_object_or_404(Playlist, id=playlist_id, user=request.user)
    tracks = request.user.backingtracks.filter(status='ready').exclude(playlists=playlist)
    return render(request, 'backingtracks/playlist_detail.html', {'playlist': playlist, 'available_tracks': tracks})

@require_POST
@login_required
def create_playlist(request):
    name = request.POST.get('name', '').strip()
    if name:
        Playlist.objects.create(user=request.user, name=name)
    return redirect('/playlists/')

@require_POST
@login_required
def delete_playlist(request, playlist_id):
    playlist = get_object_or_404(Playlist, id=playlist_id, user=request.user)
    playlist.delete()
    return redirect('backingtracks')

@require_POST
@login_required
def add_to_playlist(request, track_id=None):
    if not track_id:
        track_id = request.POST.get('track_id')
    track = get_object_or_404(BackingTrack, id=track_id, user=request.user)
    playlist_id = request.POST.get('playlist_id')
    if playlist_id:
        playlist = get_object_or_404(Playlist, id=playlist_id, user=request.user)
        playlist.tracks.add(track)
    return redirect(request.META.get('HTTP_REFERER', 'backingtracks'))

@require_POST
@login_required
def remove_from_playlist(request, track_id, playlist_id):
    track = get_object_or_404(BackingTrack, id=track_id, user=request.user)
    playlist = get_object_or_404(Playlist, id=playlist_id, user=request.user)
    playlist.tracks.remove(track)
    return redirect('backingtracks')

@login_required
def edit_playlist(request, playlist_id):
    playlist = get_object_or_404(Playlist, id=playlist_id, user=request.user)
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if name:
            playlist.name = name
        playlist.description = request.POST.get('description', '').strip()
        if request.FILES.get('image'):
            playlist.image = request.FILES['image']
        playlist.save()
        return redirect('playlist_detail', playlist_id=playlist.id)
    return render(request, 'backingtracks/edit_playlist.html', {'playlist': playlist})
