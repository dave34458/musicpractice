const NOTES = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']
const NOTE_MAP = Object.fromEntries(NOTES.map((n,i)=>[n,i]))
const CHORD_TOKEN = /^[A-G][#b]?(m|M|dim|aug|sus|add|[0-9]|\/)?/

function chartApp(applyData) {
  return {
    simplified: false,
    transpose: 0,
    data: applyData,
    tipEl: null,
    _currentChord: null,
    _currentVi: 0,
    _anchor: null,
    _transCache: null,
    _transCacheKey: 0,

    init() {
      this.tipEl = document.getElementById('chord-tip')
      this.wrapChords()
    },

    wrapChords() {
      document.querySelectorAll('.chord-block-chords').forEach(el => {
        el.innerHTML = el.textContent.replace(/(\S+)(\s*)/g, (m, word, sp) => {
          if (CHORD_TOKEN.test(word)) {
            return `<span class="chord-name-wrap" data-chord="${word}">${word}</span>${sp}`
          }
          return m
        })
      })
    },

    toggleSimplify() {
      this.simplified = !this.simplified
      this.transpose = 0
      this.closeTip()
      this._rebuildLines()
    },

    trans(n) {
      this.transpose += n
      this.closeTip()
      this._rebuildLines()
    },

    _rebuildLines() {
      document.querySelectorAll('.chord-block-chords').forEach(el => {
        const source = this.simplified ? el.dataset.simple : el.dataset.orig
        el.textContent = this._transposeLine(source, this.transpose)
      })
      this.wrapChords()
    },

    _transposeLine(line, semitones) {
      if (!semitones) return line
      let result = ''
      let cursor = 0
      line.replace(/(\S+)(\s*)/g, (m, token, sp, offset) => {
        result += ' '.repeat(Math.max(0, offset - cursor))
        result += CHORD_TOKEN.test(token) ? this._transposeToken(token, semitones) : token
        cursor = result.length
        return m
      })
      result += ' '.repeat(Math.max(0, line.length - result.length))
      return result
    },

    _transposeToken(token, semitones) {
      return token.replace(/[A-G][#b]?/g, note => {
        let idx = NOTE_MAP[note]
        if (idx === undefined && note.length === 2 && note[1] === 'b')
          idx = (NOTE_MAP[note[0]] - 1 + 12) % 12
        if (idx === undefined) return note
        return NOTES[(idx + semitones + 12) % 12]
      })
    },

    _voicingData() {
      if (!this.transpose) return this.data
      if (!this._transCache || this._transCacheKey !== this.transpose) {
        const merged = {}
        for (const [key, voicings] of Object.entries(this.data)) {
          const tkey = this._transposeToken(key, this.transpose)
          if (!merged[tkey]) merged[tkey] = []
          merged[tkey].push(...voicings)
        }
        this._transCache = merged
        this._transCacheKey = this.transpose
      }
      return this._transCache
    },

    _findKey(src, n) {
      const key = n.root + n.quality
      if (src[key]) return key
      if (n.quality.includes('/')) {
        const base = n.root + n.quality.split('/')[0]
        if (src[base]) return base
      }
      return null
    },

    _lookupShape(chordName, voicingIdx) {
      voicingIdx = voicingIdx || 0
      const n = this._normalize(chordName)
      if (!n) return null
      const src = this._voicingData()
      const key = this._findKey(src, n)
      if (key && src[key].length > voicingIdx) {
        return this._ugToShape(src[key][voicingIdx], this.transpose)
      }
      return null
    },

    _voicingCount(chordName) {
      const n = this._normalize(chordName)
      if (!n) return 0
      const src = this._voicingData()
      const key = this._findKey(src, n)
      return key ? src[key].length : 0
    },

    _normalize(name) {
      name = name.replace(/[\s,;]+/g,'').trim()
      if (!name) return null
      const m = name.match(/^([A-G][#b]?)(.*)/)
      if (!m) return null
      return { root: m[1], quality: m[2] || '' }
    },

    _ugToShape(v, semitones) {
      semitones = semitones || 0
      const frets = [...v.frets].reverse()
      const OPEN = [40, 45, 50, 55, 59, 64]
      const pitches = frets.map((f, s) => f < 0 ? null : OPEN[s] + f + semitones)
      return {
        frets,
        fingers: [...v.fingers].reverse(),
        pitches,
        baseFret: v.fret || 0,
        capos: (v.listCapos || []).map(c =>
          c.startString == null || c.lastString == null ? c : {
            ...c,
            startString: 5 - c.lastString,
            lastString: 5 - c.startString,
          }
        ),
      }
    },

    _playChord(shape) {
      const ctx = this._ctx || (this._ctx = new (window.AudioContext || window.webkitAudioContext)())
      if (ctx.state === 'suspended') ctx.resume()
      const t0 = ctx.currentTime + 0.02
      let i = 0
      for (const midi of shape.pitches || []) {
        if (midi == null) continue
        const freq = 440 * Math.pow(2, (midi - 69) / 12)
        const t = t0 + i * 0.045
        const osc = ctx.createOscillator()
        const gain = ctx.createGain()
        osc.type = 'triangle'
        osc.frequency.value = freq
        const peak = Math.min(0.32, 0.09 + midi / 1000)
        gain.gain.setValueAtTime(0.0001, t)
        gain.gain.exponentialRampToValueAtTime(peak, t + 0.01)
        gain.gain.exponentialRampToValueAtTime(0.0001, t + 1.8)
        osc.connect(gain).connect(ctx.destination)
        osc.start(t)
        osc.stop(t + 1.85)
        i++
      }
    },

    _renderFretboard(shape) {
      const frets = shape.frets; const fingers = shape.fingers
      const baseFret = shape.baseFret || 0; const capos = shape.capos || []
      const w = 184, h = 260, pad = 22
      const strX = [pad, pad+28, pad+56, pad+84, pad+112, pad+140]
      const fretY = [30, 80, 130, 180, 230]
      const dotR = 9
      const posFrets = frets.filter(f => f > 0)
      const minFret = posFrets.length ? Math.min(...posFrets) : 0
      const showLabel = minFret > 0 && baseFret > 0

      let svg = `<svg viewBox="0 0 ${w} ${h}" xmlns="http://www.w3.org/2000/svg">`
      svg += `<rect width="${w}" height="${h}" fill="none"/>`
      svg += `<line x1="${strX[0]-6}" y1="${fretY[0]}" x2="${strX[5]+6}" y2="${fretY[0]}" stroke="var(--studio-text)" stroke-width="${showLabel?2.5:5}" stroke-linecap="round"/>`
      for (let f = 1; f < 5; f++)
        svg += `<line x1="${strX[0]-6}" y1="${fretY[f]}" x2="${strX[5]+6}" y2="${fretY[f]}" stroke="var(--studio-border)" stroke-width="2.5"/>`
      for (let s = 0; s < 6; s++)
        svg += `<line x1="${strX[s]}" y1="${fretY[0]}" x2="${strX[s]}" y2="${fretY[4]}" stroke="var(--studio-border)" stroke-width="2"/>`
      if (showLabel)
        svg += `<text x="${strX[0]-8}" y="${fretY[0]+18}" text-anchor="end" font-size="12" fill="var(--studio-muted)" font-family="monospace">${baseFret}</text>`
      for (const capo of capos) {
        if (capo.fret > 0 && capo.fret <= 4 && capo.startString >= 0 && capo.lastString >= 0 && capo.lastString < 6) {
          const fy = fretY[capo.fret-1] + (fretY[capo.fret] - fretY[capo.fret-1]) / 2
          svg += `<line x1="${strX[capo.startString]}" y1="${fy}" x2="${strX[capo.lastString]}" y2="${fy}" stroke="var(--studio-amber)" stroke-width="4" stroke-linecap="round"/>`
        }
      }
      for (let s = 0; s < 6; s++) {
        const fret = frets[s]
        if (fret === -1)
          svg += `<text x="${strX[s]}" y="${fretY[0]-10}" text-anchor="middle" font-size="13" font-weight="700" fill="#ef4444" font-family="sans-serif">×</text>`
        else if (fret === 0)
          svg += `<text x="${strX[s]}" y="${fretY[0]-10}" text-anchor="middle" font-size="13" font-weight="700" fill="var(--studio-muted)" font-family="sans-serif">○</text>`
        else {
          const rel = showLabel ? (fret - baseFret) : fret
          if (rel >= 0 && rel < 5) {
            if (capos.some(c => c.fret === fret && s >= c.startString && s <= c.lastString)) continue
            const fy = fretY[Math.max(0, rel - 1)] + (fretY[rel] - fretY[Math.max(0, rel - 1)]) / 2
            const isRoot = fingers[s] === 1
            svg += `<circle cx="${strX[s]}" cy="${fy}" r="${dotR}" fill="${isRoot?'var(--studio-amber)':'var(--studio-text)'}" stroke="rgba(0,0,0,0.3)" stroke-width="1.5"/>`
            if (fingers[s] > 0)
              svg += `<text x="${strX[s]}" y="${fy+3.5}" text-anchor="middle" font-size="10" font-weight="700" fill="#fff" font-family="sans-serif">${fingers[s]}</text>`
          }
        }
      }
      svg += '</svg>'
      return svg
    },

    showTip(chord, vi, anchorEl) {
      this._currentChord = chord
      this._currentVi = vi || 0
      this._anchor = anchorEl
      const shape = this._lookupShape(chord, this._currentVi)
      const count = this._voicingCount(chord)
      let html = `<div class="chord-hover-tip-label">${chord}`
      html += shape ? `<button class="chord-play-btn" data-play title="Play chord">▶</button>` : ''
      html += `</div>`
      html += shape
        ? this._renderFretboard(shape)
        : '<div class="chord-hover-tip-none">No diagram available</div>'
      if (count > 1) {
        html += `<div class="chord-voicing-nav">`
        html += `<button class="chord-voicing-btn" data-voicing-nav="-1">◀</button>`
        html += `<div class="chord-voicing-dot">`
        for (let i = 0; i < Math.min(count, 5); i++)
          html += `<span class="${i === this._currentVi ? 'active' : ''}" data-voicing="${i}"></span>`
        html += `</div>`
        html += `<span class="chord-voicing-count">${this._currentVi + 1}/${count}</span>`
        html += `<button class="chord-voicing-btn" data-voicing-nav="1">▶</button>`
        html += `</div>`
      }
      this.tipEl.innerHTML = html
      this.tipEl.classList.add('show')
      this._position()
    },

    _position() {
      const r = this._anchor.getBoundingClientRect()
      const tw = this.tipEl.offsetWidth, th = this.tipEl.offsetHeight
      const wx = window.innerWidth, wy = window.innerHeight
      let x = r.right + 12, y = r.top
      if (x + tw > wx) x = r.left - tw - 12
      if (y + th > wy) y = Math.max(8, wy - th - 12)
      this.tipEl.style.left = x + 'px'
      this.tipEl.style.top = y + 'px'
    },

    onAreaClick(e) {
      const el = e.target.closest('.chord-name-wrap')
      if (!el) { this.closeTip(); return }
      if (this.tipEl.classList.contains('show') && this._currentChord === el.dataset.chord) {
        this.closeTip()
        return
      }
      this.showTip(el.dataset.chord, 0, el)
    },

    onTipClick(e) {
      const chord = this._currentChord
      if (!chord) return
      const play = e.target.closest('[data-play]')
      const dot = e.target.closest('[data-voicing]')
      const nav = e.target.closest('[data-voicing-nav]')
      const count = this._voicingCount(chord)
      if (play) {
        const shape = this._lookupShape(chord, this._currentVi)
        if (shape) this._playChord(shape)
      } else if (dot) {
        this.showTip(chord, parseInt(dot.dataset.voicing), this._anchor)
      } else if (nav && count > 1) {
        const step = parseInt(nav.dataset.voicingNav)
        this.showTip(chord, (this._currentVi + step + count) % count, this._anchor)
      }
    },

    closeTip() {
      this.tipEl.classList.remove('show')
      this._currentChord = null
    },
  }
}
