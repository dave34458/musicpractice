class AudioEngine {
  constructor() {
    this.ctx = null;
    this.buffers = {};
    this.gains = {};
    this.sources = {};
    this.muted = {};
    this.soloed = {};
    this.customVolumes = {};
    this.analysers = {};
    this.masterAnalyser = null;
    this.masterGain = null;
    this.playing = false;
    this.offset = 0;
    this.startWallTime = 0;
    this.loaded = false;
    this._duration = 0;
  }

  async load(stemsData) {
    this.ctx = new AudioContext();

    this.masterGain = this.ctx.createGain();
    this.masterGain.gain.value = 1;
    this.masterAnalyser = this.ctx.createAnalyser();
    this.masterAnalyser.fftSize = 256;
    this.masterGain.connect(this.masterAnalyser);
    this.masterAnalyser.connect(this.ctx.destination);

    const promises = stemsData.map(async (stem) => {
      const resp = await fetch(stem.url);
      const arrayBuffer = await resp.arrayBuffer();
      const audioBuffer = await this.ctx.decodeAudioData(arrayBuffer);
      this.buffers[stem.name] = audioBuffer;
      this.muted[stem.name] = false;
      this.soloed[stem.name] = false;
      this._duration = Math.max(this._duration, audioBuffer.duration);
    });

    await Promise.all(promises);
    this.loaded = true;
  }

  _createSources(offset) {
    for (const [name, buffer] of Object.entries(this.buffers)) {
      const source = this.ctx.createBufferSource();
      source.buffer = buffer;

      const gain = this.ctx.createGain();
      const anySolo = Object.values(this.soloed).some(v => v);
      const savedVol = this.customVolumes[name] ?? 1;

      if (this.muted[name]) {
        gain.gain.value = 0;
      } else if (anySolo && !this.soloed[name]) {
        gain.gain.value = 0;
      } else {
        gain.gain.value = savedVol;
      }

      source.connect(gain);
      gain.connect(this.masterGain);
      const analyser = this.ctx.createAnalyser();
      analyser.fftSize = 256;
      gain.connect(analyser);
      this.analysers[name] = analyser;
      this.gains[name] = gain;
      this.sources[name] = source;

      source.start(0, offset);
    }
  }

  _stopSources() {
    for (const source of Object.values(this.sources)) {
      try { source.stop(); } catch (e) {}
    }
    this.sources = {};
    this.gains = {};
  }

  getDuration() {
    return this._duration;
  }

  getCurrentTime() {
    if (!this.loaded) return 0;
    if (this.playing) {
      return this.offset + (this.ctx.currentTime - this.startWallTime);
    }
    return this.offset;
  }

  seek(time) {
    if (!this.loaded) return;
    this.offset = Math.max(0, Math.min(time, this._duration));
    if (this.playing) {
      this._stopSources();
      this._createSources(this.offset);
      this.startWallTime = this.ctx.currentTime;
    }
  }

  async play() {
    if (!this.loaded) return;
    if (this.ctx.state === 'suspended') await this.ctx.resume();
    if (this.playing) return;
    if (this.offset >= this._duration) this.offset = 0;
    this._createSources(this.offset);
    this.startWallTime = this.ctx.currentTime;
    this.playing = true;
  }

  pause() {
    if (!this.playing) return;
    this.offset += this.ctx.currentTime - this.startWallTime;
    this.ctx.suspend();
    this._stopSources();
    this.playing = false;
  }

  stop() {
    this._stopSources();
    this.playing = false;
    this.offset = 0;
  }

  setVolume(name, value) {
    this.customVolumes[name] = value;
    if (this.gains[name]) this.gains[name].gain.value = value;
  }

  setMasterVolume(value) {
    if (this.masterGain) this.masterGain.gain.value = value;
  }

  getMasterVolume() {
    return this.masterGain ? this.masterGain.gain.value : 1;
  }

  getVolume(name) {
    return this.gains[name] ? this.gains[name].gain.value : 1;
  }

  toggleMute(name) {
    this.muted[name] = !this.muted[name];
    this._applyMuteSolo();
  }

  toggleSolo(name) {
    this.soloed[name] = !this.soloed[name];
    this._applyMuteSolo();
  }

  isMuted(name) { return !!this.muted[name]; }
  isSoloed(name) { return !!this.soloed[name]; }

  _applyMuteSolo() {
    const anySolo = Object.values(this.soloed).some(v => v);
    for (const name of Object.keys(this.gains)) {
      if (this.muted[name]) {
        this.gains[name].gain.value = 0;
      } else if (anySolo && !this.soloed[name]) {
        this.gains[name].gain.value = 0;
      } else {
        this.gains[name].gain.value = this.customVolumes[name] ?? 1;
      }
    }
  }

  getFrequencyData(name) {
    if (!name) {
      if (!this.masterAnalyser) return null;
      const data = new Uint8Array(this.masterAnalyser.frequencyBinCount);
      this.masterAnalyser.getByteFrequencyData(data);
      return data;
    }
    const analyser = this.analysers[name];
    if (!analyser) return null;
    const data = new Uint8Array(analyser.frequencyBinCount);
    analyser.getByteFrequencyData(data);
    return data;
  }

  getWaveformData(name) {
    if (!name) {
      if (!this.masterAnalyser) return null;
      const data = new Uint8Array(this.masterAnalyser.frequencyBinCount);
      this.masterAnalyser.getByteTimeDomainData(data);
      return data;
    }
    const analyser = this.analysers[name];
    if (!analyser) return null;
    const data = new Uint8Array(analyser.frequencyBinCount);
    analyser.getByteTimeDomainData(data);
    return data;
  }

  destroy() {
    this.stop();
    if (this.ctx) this.ctx.close();
  }
}
