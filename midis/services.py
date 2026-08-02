import json
import threading
import time
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile

from .models import Midi

_model = None
_model_lock = threading.Lock()


def _patch_accelerator_synchronize():
    # muscriptor 0.2.2 calls torch.accelerator.synchronize() unconditionally on
    # torch >= 2.6, which raises when no GPU/MPS accelerator is present.
    import torch
    if torch.accelerator.is_available():
        return
    import muscriptor.accelerator
    muscriptor.accelerator.synchronize = lambda: None


def get_model():
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                _patch_accelerator_synchronize()
                from muscriptor import TranscriptionModel
                _model = TranscriptionModel.load_model(str(settings.MUSCRIPTOR_MODEL_PATH))
    return _model


def _instrument_names(instruments):
    from muscriptor.tokenizer.mt3 import MT3_FULL_PLUS_GROUP_NAMES
    valid = set(MT3_FULL_PLUS_GROUP_NAMES)
    return [name.strip() for name in instruments.split(',') if name.strip() in valid]


def _update_midi(midi_id, **fields):
    return Midi.objects.filter(id=midi_id).update(**fields)


def process_midi(midi_id):
    from muscriptor.events import NoteStartEvent, NoteEndEvent, ProgressEvent

    midi = Midi.objects.filter(id=midi_id).first()
    if midi is None:
        return
    _update_midi(midi_id, status='processing')
    print(f'[worker] midi {midi_id} -> processing', flush=True)

    try:
        model = get_model()

        notes = {}
        duration = 0.0
        events = []

        for event in model.transcribe(
            str(midi.audio.path),
            instruments=_instrument_names(midi.instruments) or None,
            prelude_forcing=True,
        ):
            events.append(event)
            if isinstance(event, ProgressEvent):
                updated = _update_midi(
                    midi_id,
                    progress=event.completed,
                    total=event.total,
                    notes_json=json.dumps(list(notes.values())),
                    note_count=len(notes),
                )
                if not updated:
                    print(f'[worker] midi {midi_id} deleted mid-process, aborting', flush=True)
                    return
            elif isinstance(event, NoteStartEvent):
                notes[event.index] = {
                    'pitch': event.pitch,
                    'start': round(event.start_time, 3),
                    'end': round(event.start_time + 0.05, 3),
                    'instrument': event.instrument,
                }
            elif isinstance(event, NoteEndEvent):
                idx = event.start_event.index
                if idx in notes:
                    notes[idx]['end'] = round(event.end_time, 3)
                    duration = max(duration, event.end_time)

        midi_bytes = model.events_to_midi_bytes(iter(events))
        midi.midi.save(f'{midi.id}.mid', ContentFile(midi_bytes), save=False)

        updated = _update_midi(
            midi_id,
            midi=midi.midi.name,
            notes_json=json.dumps(list(notes.values())),
            note_count=len(notes),
            duration=round(duration, 2),
            status='ready',
        )
        if not updated:
            print(f'[worker] midi {midi_id} deleted mid-process, aborting', flush=True)
            return
        print(f'[worker] midi {midi_id} -> ready', flush=True)

    except Exception:
        import traceback
        log_dir = Path(settings.MEDIA_ROOT) / 'logs'
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f'midis_{midi_id}.log'
        with open(log_file, 'w') as f:
            traceback.print_exc(file=f)
        _update_midi(
            midi_id,
            status='error',
            error_message='MIDI generation failed. Check media/logs for details.',
        )
        print(f'[worker] midi {midi_id} -> error (see {log_file})', flush=True)


def worker_loop():
    while True:
        try:
            midi = Midi.objects.filter(status='queued').order_by('created_at').first()
            if midi:
                print(f'[worker] picking midi {midi.id}', flush=True)
                process_midi(midi.id)
            else:
                time.sleep(2)
        except Exception:
            import traceback
            traceback.print_exc()
            time.sleep(5)


def start_worker():
    thread = threading.Thread(target=worker_loop, daemon=True)
    thread.start()
    print(f'[worker] started (tid={thread.ident})', flush=True)
