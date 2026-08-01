// MIDI playback via SpessaSynth (Web Audio worklet synthesizer).
// ESM module. Exposes MidiPlayer used by processing/detail pages.
import { WorkletSynthesizer } from '/static/midis/js/spessasynth_lib.esm.js?v=6';

// MT3_FULL_PLUS group -> representative GM program (first of the group's programs).
const PROGRAM_MAP = {
  acoustic_piano: 0, electric_piano: 2, chromatic_percussion: 8, organ: 16,
  acoustic_guitar: 24, clean_electric_guitar: 26, distorted_electric_guitar: 29,
  acoustic_bass: 32, electric_bass: 33, violin: 40, viola: 41, cello: 42,
  contrabass: 43, orchestral_harp: 46, timpani: 47, string_ensemble: 48,
  synth_strings: 50, voice: 52, orchestra_hit: 55, trumpet: 56, trombone: 57,
  tuba: 58, french_horn: 60, brass_section: 61, soprano_and_alto_sax: 64,
  tenor_sax: 66, baritone_sax: 67, oboe: 68, english_horn: 69, bassoon: 70,
  clarinet: 71, flutes: 72, synth_lead: 80, synth_pad: 88, drums: 0,
};
const DRUM_CHANNEL = 9;
const VELOCITY = 127;
const LOOKAHEAD = 2.5;
const TICK_MS = 250;

export class MidiPlayer {
  constructor() {
    this.ctx = null;
    this.synth = null;
    this.notes = [];
    this.readyPromise = null;
    this.playing = false;
    this.pos = 0;
    this.playStartWall = 0;
    this.playStartPos = 0;
    this._idx = 0;
    this._programmed = new Set();
    this._scheduled = new Set();
    this._pending = new Map();
    this._timer = 0;
    this.channelVols = {};
    this.channels = {};
    this.onTime = null;
  }

  init(soundfontUrl, processorUrl) {
    if (this.readyPromise) return this.readyPromise;
    this.readyPromise = (async () => {
      this.ctx = new AudioContext();
      await this.ctx.audioWorklet.addModule(processorUrl);
      this.synth = new WorkletSynthesizer(this.ctx);
      const sfont = await (await fetch(soundfontUrl)).arrayBuffer();
      await this.synth.soundBankManager.addSoundBank(sfont, 'main');
      await this.synth.isReady;
      this.synth.setSystemParameter('reverbGain', 0);
      this.synth.setSystemParameter('chorusGain', 0);
      this.synth.setSystemParameter('delayGain', 0);
      this.synth.connect(this.ctx.destination);
    })().catch((err) => {
      this.readyPromise = null;
      throw err;
    });
    return this.readyPromise;
  }

  setNotes(notes) {
    this.notes = [...(notes || [])].sort((a, b) => a.start - b.start);
    this._idx = this._lowerBound(this.position());
  }

  channelFor(instrument) {
    if (instrument === 'drums') return DRUM_CHANNEL;
    if (!(instrument in this.channels)) {
      const used = Object.values(this.channels);
      let ch = 0;
      while (used.includes(ch)) ch++;
      this.channels[instrument] = Math.min(ch, 8);
    }
    return this.channels[instrument];
  }

  programFor(instrument) {
    return PROGRAM_MAP[instrument] != null ? PROGRAM_MAP[instrument] : 0;
  }

  setVolume(v) {
    if (this.synth) this.synth.setSystemParameter('gain', Math.max(0, v));
  }

  setChannelVolume(instrument, v) {
    this.channelVols[instrument] = Math.max(0, v);
    if (!this.synth) return;
    const ch = this.channels[instrument];
    if (ch !== undefined) this.synth.midiChannels[ch].setSystemParameter('gain', this.channelVols[instrument]);
  }

  _ensureProgram(ch, instrument) {
    this.synth.midiChannels[ch].setSystemParameter('gain', this.channelVols[instrument] ?? 2);
    if (this._programmed.has(ch)) return;
    this._programmed.add(ch);
    if (instrument === 'drums') this.synth.midiChannels[ch].setDrums(true);
    this.synth.programChange(ch, this.programFor(instrument));
  }

  _lowerBound(t) {
    let lo = 0, hi = this.notes.length;
    while (lo < hi) {
      const mid = (lo + hi) >> 1;
      if (this.notes[mid].start < t) lo = mid + 1; else hi = mid;
    }
    return lo;
  }

  _scheduleNote(note) {
    const ch = this.channelFor(note.instrument);
    const key = ch + ':' + note.pitch + ':' + note.start;
    if (this._scheduled.has(key)) return;
    this._scheduled.add(key);
    this._ensureProgram(ch, note.instrument);
    const t = this.ctx.currentTime + Math.max(note.start - this.position(), 0);
    const dur = Math.max(note.end - note.start, 0.05);
    this._pending.set(key, { ch, pitch: note.pitch, t });
    this.synth.noteOn(ch, note.pitch, VELOCITY, { time: t });
    this.synth.noteOff(ch, note.pitch, { time: t + dur });
  }

  // Stop all sounding voices (force = hard cut) and purge the worklet's
  // future event queue (patched stopAllChannels clears it) so queued noteOns
  // die too — stop is instant, no ghost notes after seek.
  _stopSynth(force) {
    if (!this.synth) return;
    this._pending.clear();
    this._scheduled.clear();
    this.synth.stopAll(force);
  }

  position() {
    if (!this.playing) return this.pos;
    return this.playStartPos + (performance.now() - this.playStartWall) / 1000;
  }

  duration() {
    let d = 0;
    for (const n of this.notes) d = Math.max(d, n.end);
    return d;
  }

  async play(fromPos) {
    if (!this.synth) throw new Error('Player not initialized');
    await this.ctx.resume();
    if (this.ctx.state !== 'running') throw new Error('Audio context suspended — click play again');
    if (fromPos != null) this.pos = Math.max(0, fromPos);
    this._stopSynth(true);
    this.playStartPos = this.pos;
    this.playStartWall = performance.now();
    this._idx = this._lowerBound(this.pos);
    this.playing = true;
    this._tick();
  }

  pause() {
    if (!this.playing) return;
    this.pos = this.position();
    this.playing = false;
    clearTimeout(this._timer);
    if (this.synth) this._stopSynth(true);
    if (this.onTime) this.onTime(this.pos);
  }

  seek(t) {
    const wasPlaying = this.playing;
    this.pause();
    this.pos = Math.max(0, t);
    if (wasPlaying) this.play();
  }

  reschedule() {
    this._idx = this._lowerBound(this.position());
  }

  stopAll() {
    this.pause();
  }

  _tick() {
    if (!this.playing) return;
    const pos = this.position();
    const dur = this.duration();
    if (pos >= dur) {
      this.playing = false;
      clearTimeout(this._timer);
      this._stopSynth(true);
      this.pos = dur;
      if (this.onTime) this.onTime(dur);
      return;
    }
    while (this._idx < this.notes.length && this.notes[this._idx].start <= pos + LOOKAHEAD) {
      this._scheduleNote(this.notes[this._idx]);
      this._idx++;
    }
    for (const [k, v] of this._pending) {
      if (v.t <= this.ctx.currentTime) {
        this._pending.delete(k);
        this._scheduled.delete(k);
      }
    }
    if (this.onTime) this.onTime(pos);
    this._timer = setTimeout(() => this._tick(), TICK_MS);
  }
}
