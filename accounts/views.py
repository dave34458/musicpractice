import json
from datetime import timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from django.db.models import Count, Min, Max, Q, Avg, Sum
from django.contrib import messages
from django.utils import timezone
from .models import Profile, Instrument, Genre
from .forms import ProfileForm, ProfileDeleteForm
from backingtracks.models import Stem


def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Welcome to MusicPractice!')
            return redirect('/')
    else:
        form = UserCreationForm()
    return render(request, 'registration/register.html', {'form': form})


def profile_view(request, username=None):
    if username:
        user = get_object_or_404(User, username=username)
        is_owner = request.user == user
    else:
        if not request.user.is_authenticated:
            return redirect('/login/')
        user = request.user
        is_owner = True

    profile, _ = Profile.objects.get_or_create(user=user)
    tracks_qs = user.backingtracks.all()
    track_count = tracks_qs.count()

    # status distribution
    status_counts = {
        s: tracks_qs.filter(status=s).count()
        for s in ['ready', 'processing', 'queued', 'error', 'rejected']
    }
    ready_pct = (status_counts['ready'] / track_count * 100) if track_count else 0

    # BPM stats
    bpm_stats = tracks_qs.aggregate(min_bpm=Min('bpm'), max_bpm=Max('bpm'), avg_bpm=Avg('bpm'))

    # duration
    duration_total = tracks_qs.aggregate(total=Sum('duration'))['total'] or 0

    # top key
    top_key_row = tracks_qs.exclude(key='').values('key').annotate(
        kcount=Count('key')
    ).order_by('-kcount').first()
    top_key = top_key_row['key'] if top_key_row else None

    # stems
    stems_total = Stem.objects.filter(backing_track__user=user).count()
    tracks_with_stems = tracks_qs.filter(stems__isnull=False).distinct().count()

    # genre distribution
    genre_dist = []
    for g in Genre.objects.filter(backingtracks__user=user).annotate(
        tcount=Count('backingtracks')
    ).order_by('-tcount'):
        genre_dist.append({'name': g.name, 'count': g.tcount})

    # tracks by skill level BPM range
    beginner_bpm = tracks_qs.filter(user__profile__skill_level='beginner').aggregate(avg=Avg('bpm'))['avg']
    advanced_bpm = tracks_qs.filter(user__profile__skill_level='advanced').aggregate(avg=Avg('bpm'))['avg']

    # account age
    profile_age = timezone.now() - user.date_joined
    profile_age_days = profile_age.days
    profile_age_years = profile_age_days // 365
    profile_age_months = (profile_age_days % 365) // 30

    # all tracks with annotations (capped at 50 for performance)
    all_tracks = tracks_qs.select_related('genre').annotate(
        stems_count=Count('stems')
    ).order_by('-created_at')[:50]

    # all playlists with track count
    all_playlists = user.playlists.annotate(
        tracks_count=Count('tracks')
    ).order_by('-created_at')

    # oldest/newest track dates
    track_dates = tracks_qs.aggregate(oldest=Min('created_at'), newest=Max('created_at'))

    return render(request, 'accounts/profile.html', {
        'profile_user': user,
        'profile': profile,
        'is_owner': is_owner,
        'track_count': track_count,
        'playlist_count': user.playlists.count(),
        'all_tracks': all_tracks,
        'all_playlists': all_playlists,
        'status_counts': status_counts,
        'ready_pct': round(ready_pct),
        'bpm_min': bpm_stats['min_bpm'],
        'bpm_max': bpm_stats['max_bpm'],
        'bpm_avg': bpm_stats['avg_bpm'],
        'duration_total': duration_total,
        'stems_total': stems_total,
        'tracks_with_stems': tracks_with_stems,
        'top_key': top_key,
        'genre_dist': genre_dist,
        'profile_age_years': profile_age_years,
        'profile_age_months': profile_age_months,
        'profile_age_days': profile_age_days,
        'track_oldest': track_dates['oldest'],
        'track_newest': track_dates['newest'],
    })


@login_required
def profile_edit(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        form = ProfileForm(request.POST, request.FILES, instance=profile, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('profile')
    else:
        form = ProfileForm(instance=profile, user=request.user)

    return render(request, 'accounts/profile_edit.html', {
        'form': form,
        'profile': profile,
        'instrument_choices_json': json.dumps(list(Instrument.objects.values_list('name', flat=True))),
        'genre_choices_json': json.dumps(list(Genre.objects.values_list('name', flat=True))),
    })


@login_required
def profile_delete(request):
    if request.method == 'POST':
        form = ProfileDeleteForm(request.POST)
        if form.is_valid():
            username = request.user.username
            logout(request)
            User.objects.filter(username=username).delete()
            messages.success(request, 'Your account has been permanently deleted.')
            return redirect('/')
    else:
        form = ProfileDeleteForm()

    track_count = request.user.backingtracks.count()
    playlist_count = request.user.playlists.count()

    return render(request, 'accounts/profile_delete.html', {
        'form': form,
        'track_count': track_count,
        'playlist_count': playlist_count,
    })
