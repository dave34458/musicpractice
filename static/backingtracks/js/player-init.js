function player() {
  return {
    stems: STEMS_DATA,
    track: TRACK_DATA,
    engine: null,
    playing: false,
    ready: false,
    progressInterval: null,
    currentTime: 0,
    duration: 0,
    progressPct: 0,
    visualizerAnimId: null,
    channelWaveforms: [],
    // Reactive state for mute/solo/volume
    muted: {},
    soloed: {},
    volumes: {},
    masterVolume: 100,

    async init() {
      this.engine = new AudioEngine();
      await this.engine.load(this.stems);
      this.duration = this.engine.getDuration();
      this.ready = true;

      // Init reactive state
      this.stems.forEach(stem => {
        this.muted[stem.name] = false;
        this.soloed[stem.name] = false;
        this.volumes[stem.name] = 100;
      });

      this.genChannelWaveforms();
      this.$nextTick(() => this.startVisualizer());
    },

    genChannelWaveforms() {
      this.channelWaveforms = this.stems.map(() => {
        const len = 48;
        return Array.from({ length: len }, () => Math.random() * 0.6 + 0.2);
      });
    },

    updateChannelWaveforms() {
      if (!this.engine || !this.playing) return;
      this.channelWaveforms = this.stems.map((stem) => {
        const freqData = this.engine.getFrequencyData(stem.name);
        if (!freqData || !freqData.length) return Array(48).fill(0);
        return Array.from({ length: 48 }, (_, j) => {
          const idx = Math.floor((j / 48) * freqData.length);
          return freqData[idx] / 255;
        });
      });
    },

    startVisualizer() {
      const canvas = document.getElementById('visualizer');
      if (!canvas) { console.warn('visualizer canvas not found'); return; }
      const ctx = canvas.getContext('2d');
      if (!ctx) { console.warn('no canvas context'); return; }

      const wrap = canvas.parentElement;
      const resize = () => {
        canvas.width = wrap.clientWidth || 400;
        canvas.height = wrap.clientHeight || 80;
      };
      resize();

      const ro = new ResizeObserver(resize);
      ro.observe(wrap);

      const draw = () => {
        this.visualizerAnimId = requestAnimationFrame(draw);
        const data = this.engine ? this.engine.getFrequencyData() : null;
        const cw = canvas.width;
        const ch = canvas.height;
        if (!cw || !ch) return;

        ctx.clearRect(0, 0, cw, ch);

        const bars = 128;
        const gap = 1;
        const barW = Math.max(1, (cw - gap * (bars - 1)) / bars);
        const midY = ch / 2;

        if (data) {
          for (let i = 0; i < bars; i++) {
            const idx = Math.floor((i / bars) * data.length);
            const val = data[idx] / 255;
            const barH = Math.max(2, val * ch * 0.85);
            const x = i * (barW + gap);
            const y = midY - barH / 2;
            ctx.fillStyle = `rgba(217, 119, 6, ${0.15 + val * 0.5})`;
            ctx.fillRect(x, y, Math.ceil(barW), barH);
          }
        } else if (!this.playing) {
          ctx.globalAlpha = 0.3;
          ctx.fillStyle = 'rgba(217, 119, 6, 0.04)';
          for (let i = 0; i < bars; i++) {
            const x = i * (barW + gap);
            ctx.fillRect(x, midY - 1, Math.ceil(barW), 2);
          }
          ctx.globalAlpha = 1;
        }
      };
      draw();
    },

    togglePlay() {
      if (!this.ready) return;
      if (this.playing) {
        this.engine.pause();
        this.playing = false;
        if (this.progressInterval) clearInterval(this.progressInterval);
        this.currentTime = this.engine.getCurrentTime();
        this.progressPct = (this.currentTime / this.duration) * 100;
      } else {
        this.engine.play();
        this.playing = true;
        this._trackProgress();
      }
    },

    stop() {
      this.engine.stop();
      this.playing = false;
      this.currentTime = 0;
      this.progressPct = 0;
      if (this.progressInterval) clearInterval(this.progressInterval);
    },

    seek(event) {
      const rect = event.currentTarget.getBoundingClientRect();
      const pct = Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width));
      const time = pct * this.duration;
      this.engine.seek(time);
      this.currentTime = time;
      this.progressPct = pct * 100;
    },

    _trackProgress() {
      if (this.progressInterval) clearInterval(this.progressInterval);
      this.progressInterval = setInterval(() => {
        if (this.engine && this.playing) {
          this.currentTime = this.engine.getCurrentTime();
          this.progressPct = (this.currentTime / this.duration) * 100;
          this.updateChannelWaveforms();
          if (this.currentTime >= this.duration) this.stop();
        }
      }, 50);
    },

    toggleMute(name) {
      this.engine.toggleMute(name);
      this.muted[name] = !this.muted[name];
    },

    toggleSolo(name) {
      this.engine.toggleSolo(name);
      this.soloed[name] = !this.soloed[name];
    },

    setVolume(name, value) {
      const v = parseInt(value) / 100;
      this.engine.setVolume(name, v);
      this.volumes[name] = parseInt(value);
    },

    setMasterVolume(value) {
      const v = parseInt(value) / 100;
      this.engine.setMasterVolume(v);
      this.masterVolume = parseInt(value);
    },

    formatTime(secs) {
      const m = Math.floor(secs / 60);
      const s = Math.floor(secs % 60);
      return m + ':' + (s < 10 ? '0' : '') + s;
    },
  };
}
