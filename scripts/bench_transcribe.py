"""Benchmark muscriptor transcription speed and quality on a fixed file.

Usage:
  python scripts/bench_transcribe.py [--threads N] [--out out.mid] [--compare ref.mid] [--compile] [--int8] [--keep-logits-fp32]
"""
import argparse
import os
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

AUDIO = BASE / 'media' / 'midis' / 'audio' / 'Creeping_Death_3.mp3'
REF = BASE / 'media' / 'midis' / 'midi' / '10.mid'
MODEL = BASE / 'models' / 'muscriptor-small.safetensors'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--threads', type=int, default=None)
    ap.add_argument('--out', type=str, default=None)
    ap.add_argument('--compare', type=str, default=str(REF))
    ap.add_argument('--compile', action='store_true')
    ap.add_argument('--int8', action='store_true')
    ap.add_argument('--int8-all', action='store_true')
    ap.add_argument('--batch', type=int, default=None)
    ap.add_argument('--no-prelude', action='store_true')
    ap.add_argument('--keep-logits-fp32', action='store_true')
    ap.add_argument('--audio', type=str, default=str(AUDIO))
    ap.add_argument('--model', type=str, default=str(MODEL))
    args = ap.parse_args()

    import torch
    if args.threads:
        torch.set_num_threads(args.threads)
        torch.set_num_interop_threads(1)
    print(f'threads={torch.get_num_threads()} capability={torch.backends.cpu.get_cpu_capability()} '
          f'avx2={torch.backends.mkldnn.is_available()}')

    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    import django
    django.setup()
    from midis.services import _patch_accelerator_synchronize
    _patch_accelerator_synchronize()

    from muscriptor import TranscriptionModel
    model = TranscriptionModel.load_model(str(args.model))
    print('model:', Path(args.model).name)

    if args.compile:
        model._model = _compile_model(model._model)
    if args.int8_all:
        model._model = _quantize(model._model, keep_logits_fp32=args.keep_logits_fp32, ffn_only=False)
    if args.int8:
        model._model = _quantize(model._model, keep_logits_fp32=args.keep_logits_fp32)

    from muscriptor.events import NoteStartEvent, NoteEndEvent, ProgressEvent

    t0 = time.perf_counter()
    notes = {}
    events = []
    chunks = 0
    kw = {}
    if args.batch:
        kw['batch_size'] = args.batch
        kw['prelude_forcing'] = False if args.no_prelude else True
        if args.no_prelude:
            kw['prelude_forcing'] = False
    for event in model.transcribe(args.audio, instruments=None, **kw):
        events.append(event)
        if isinstance(event, ProgressEvent):
            chunks = event.total
        elif isinstance(event, NoteStartEvent):
            notes[event.index] = {
                'pitch': event.pitch,
                'start': event.start_time,
                'end': event.start_time + 0.05,
            }
        elif isinstance(event, NoteEndEvent):
            idx = event.start_event.index
            if idx in notes:
                notes[idx]['end'] = event.end_time
    dt = time.perf_counter() - t0
    print(f'RESULT wall={dt:.2f}s chunks={chunks} notes={len(notes)}')

    if args.out:
        midi_bytes = model.events_to_midi_bytes(iter(events))
        Path(args.out).write_bytes(midi_bytes)
        print(f'wrote {args.out} ({len(midi_bytes)} bytes)')
        if Path(args.compare).exists():
            match = _note_match(list(notes.values()), _parse_midi_notes(args.compare))
            ref = len(_parse_midi_notes(args.compare))
            print(f'compare vs {args.compare}: notes={len(notes)} ref_notes={ref} '
                  f'matched={match["matched"]} '
                  f'precision={match["precision"]:.1%} recall={match["recall"]:.1%} '
                  f'identical_bytes={midi_bytes == Path(args.compare).read_bytes()}')


def _parse_midi_notes(path):
    """Return [(pitch, start_sec, end_sec), ...] via mido (handles multi-track/running status)."""
    import mido
    mid = mido.MidiFile(path)
    tpb = mid.ticks_per_beat
    tempo = 500000
    active = {}
    notes = []
    tick = 0
    for msg in mid:
        tick += msg.time
        if msg.type == 'set_tempo':
            tempo = msg.tempo
        elif msg.type == 'note_on' and msg.velocity > 0:
            active[(msg.channel, msg.note)] = tick
        elif msg.type in ('note_off', 'note_on') and (msg.channel, msg.note) in active:
            s = active.pop((msg.channel, msg.note))
            notes.append((msg.note, mido.tick2second(s, tpb, tempo), mido.tick2second(tick, tpb, tempo)))
    return notes


def _note_match(transcribed, ref_notes):
    def unpack(n):
        return (n['pitch'], n['start'], n['end']) if isinstance(n, dict) else n
    matched = 0
    for pitch, s, e in ref_notes:
        for n2 in transcribed:
            p2, s2, e2 = unpack(n2)
            if p2 == pitch and abs(s2 - s) < 0.3:
                matched += 1
                break
    ref = len(ref_notes)
    return {
        'matched': matched,
        'ref': ref,
        'precision': matched / max(len(transcribed), 1),
        'recall': matched / max(ref, 1),
    }


def _compile_model(model):
    import torch
    torch._dynamo.config.suppress_errors = True
    model.transformer = torch.compile(model.transformer)
    print('compile: transformer wrapped (errors suppressed -> eager fallback)')
    return model


def _quantize(model, keep_logits_fp32=True, ffn_only=True):
    import torch
    from torch.ao.quantization import default_dynamic_qconfig, quantize_dynamic
    from torch import nn
    from torch.nn import functional as F

    # Per-channel x86 qconfig for accuracy on FP32 CPU GEMMs.
    qconfig = default_dynamic_qconfig
    targets = set()
    for name, mod in model.named_modules():
        if isinstance(mod, nn.Linear):
            if keep_logits_fp32 and name == 'linear':
                continue
            targets.add(name)
    if ffn_only:
        # Avoid attention interplay: only the FFN linears (2/3 of matmul bytes).
        targets = sorted(n for n in targets if n.endswith(('.linear1', '.linear2')))
    else:
        targets = sorted(targets)
        # Attention forward uses nn.functional.linear(self.in_proj_weight) directly,
        # so the module swap would be a no-op — route it through self.in_proj instead.
        # KV caches stay fp32: init_state takes dtype from self.in_proj_weight, which
        # remains the original fp32 tensor after the swap.
        from muscriptor.modules.transformer import StreamingMultiheadAttention
        import einops

        def forward(self, query, model_state=None):
            projected = self.in_proj(query)
            packed = einops.rearrange(projected, 'b t (p h d) -> b t p h d', p=3, h=self.num_heads)
            q, k, v = packed.unbind(dim=2)
            k, v = self._complete_kv(k, v, self.get_state(model_state))
            q_t, k_t, v_t = q.transpose(1, 2), k.transpose(1, 2), v.transpose(1, 2)
            if q_t.shape[2] == 1:
                x = F.scaled_dot_product_attention(q_t, k_t, v_t, dropout_p=0.0)
            else:
                x = F.scaled_dot_product_attention(q_t, k_t, v_t, is_causal=True, dropout_p=0.0)
            x = x.transpose(1, 2)
            x = einops.rearrange(x, 'b t h d -> b t (h d)')
            return self.out_proj(x)

        StreamingMultiheadAttention.forward = forward
    print('quantizing', len(targets), 'linears (ffn_only=' + str(ffn_only) + ')')
    model = quantize_dynamic(
        model,
        qconfig_spec={n: qconfig for n in targets},
        dtype=torch.qint8,
        mapping={nn.Linear: nn.quantized.dynamic.Linear},
    )
    return model


if __name__ == '__main__':
    main()
