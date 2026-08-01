import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, FileResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST

from .models import Midi


@login_required
def index(request):
    if request.method == 'POST':
        audio = request.FILES.get('audio')
        if audio:
            midi = Midi.objects.create(
                user=request.user,
                title=request.POST.get('title', '').strip() or audio.name,
                audio=audio,
                instruments=request.POST.get('instruments', '').strip(),
            )
            return redirect('midis:status', midi_id=midi.id)
    return render(request, 'midis/list.html', {
        'midis': request.user.midis.all(),
    })


@login_required
def status(request, midi_id):
    midi = get_object_or_404(Midi, id=midi_id, user=request.user)
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'status': midi.status,
            'progress': midi.progress,
            'total': midi.total,
            'note_count': midi.note_count,
            'error': midi.error_message,
        })
    return render(request, 'midis/processing.html', {'midi': midi})


@login_required
def notes(request, midi_id):
    midi = get_object_or_404(Midi, id=midi_id, user=request.user)
    try:
        data = json.loads(midi.notes_json or '[]')
    except ValueError:
        data = []
    return JsonResponse(data, safe=False)


@login_required
def detail(request, midi_id):
    midi = get_object_or_404(Midi, id=midi_id, user=request.user)
    if midi.status != 'ready':
        return redirect('midis:status', midi_id=midi.id)
    notes = json.loads(midi.notes_json or '[]')
    counts = {}
    for note in notes:
        counts[note['instrument']] = counts.get(note['instrument'], 0) + 1

    def display_name(name):
        return ' '.join(w.capitalize() for w in name.split('_'))

    channels = [
        {'name': name, 'label': display_name(name), 'count': counts[name]}
        for name in sorted(counts)
    ]
    return render(request, 'midis/detail.html', {
        'midi': midi,
        'notes_json': midi.notes_json,
        'channels': channels,
    })


@login_required
def download(request, midi_id):
    midi = get_object_or_404(Midi, id=midi_id, user=request.user)
    if not midi.midi:
        return redirect('midis:detail', midi_id=midi.id)
    return FileResponse(
        midi.midi.open('rb'),
        as_attachment=True,
        filename=f'{midi.title or midi_id}.mid',
    )


@login_required
@require_POST
def delete(request, midi_id):
    midi = get_object_or_404(Midi, id=midi_id, user=request.user)
    midi.audio.delete(save=False)
    if midi.midi:
        midi.midi.delete(save=False)
    midi.delete()
    return redirect('midis:index')
