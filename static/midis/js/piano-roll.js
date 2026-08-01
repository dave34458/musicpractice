// Piano roll canvas renderer (vanilla)
// renderPianoRoll(canvas, notes, { playhead, duration, follow, window })
// follow + window: show a fixed window of `window` seconds around the playhead
// instead of the whole track (readable on long recordings).
(function () {
  'use strict';

  var NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];

  var PALETTE = [
    '#D97706', '#3B82F6', '#22C55E', '#EC4899', '#8B5CF6',
    '#06B6D4', '#F59E0B', '#10B981', '#EF4444', '#6366F1',
    '#84CC16', '#F97316', '#14B8A6', '#A855F7',
  ];

  function instrumentColor(name, map) {
    if (!(name in map)) {
      var hash = 0;
      for (var i = 0; i < name.length; i++) hash = (hash * 31 + name.charCodeAt(i)) >>> 0;
      map[name] = PALETTE[hash % PALETTE.length];
    }
    return map[name];
  }

  function noteName(pitch) {
    return NOTE_NAMES[pitch % 12] + (Math.floor(pitch / 12) - 1);
  }

  var metricCache = { ref: null, maxEnd: 0, minPitch: 127, maxPitch: 0 };

  function notesMetrics(notes) {
    if (metricCache.ref === notes) return metricCache;
    var maxEnd = 0, minPitch = 127, maxPitch = 0;
    for (var i = 0; i < notes.length; i++) {
      var n = notes[i];
      if (n.end > maxEnd) maxEnd = n.end;
      if (n.pitch < minPitch) minPitch = n.pitch;
      if (n.pitch > maxPitch) maxPitch = n.pitch;
    }
    metricCache.ref = notes;
    metricCache.maxEnd = maxEnd;
    metricCache.minPitch = minPitch;
    metricCache.maxPitch = maxPitch;
    return metricCache;
  }

  function fmtTime(s) {
    return Math.floor(s / 60) + ':' + String(Math.floor(s % 60)).padStart(2, '0');
  }

  function draw(canvas, notes, opts) {
    opts = opts || {};
    var dpr = window.devicePixelRatio || 1;
    var rect = canvas.getBoundingClientRect();
    var W = Math.max(rect.width, 100);
    var H = Math.max(rect.height, 120);
    if (canvas.width !== Math.round(W * dpr) || canvas.height !== Math.round(H * dpr)) {
      canvas.width = Math.round(W * dpr);
      canvas.height = Math.round(H * dpr);
    }
    var ctx = canvas.getContext('2d');
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, W, H);

    var MARGIN_L = 42;
    var MARGIN_B = 22;
    var MARGIN_T = 8;
    var MARGIN_R = 12;

    var m = notesMetrics(notes);
    var maxEnd = m.maxEnd;
    var minPitch = m.minPitch;
    var maxPitch = m.maxPitch;
    var duration = Math.max(maxEnd, 10) + 1;
    if (opts.duration && opts.duration > duration) duration = opts.duration + 1;
    minPitch = Math.max(21, Math.min(minPitch, 60) - 2);
    maxPitch = Math.min(108, Math.max(maxPitch, 72) + 2);

    var plotW = W - MARGIN_L - MARGIN_R;
    var plotH = H - MARGIN_T - MARGIN_B;

    // Follow-window mode: fixed time span sliding with the playhead.
    var windowSec = opts.follow && opts.window > 0 ? opts.window : 0;
    var t0 = 0;
    var t1 = duration;
    if (windowSec > 0) {
      var ph = opts.playhead != null ? opts.playhead : 0;
      t0 = Math.max(0, Math.min(ph - windowSec * 0.2, duration - windowSec));
      t1 = t0 + windowSec;
    }
    var pxPerSec = plotW / Math.max(t1 - t0, 1);

    function xOf(t) { return MARGIN_L + (t - t0) * pxPerSec; }
    function yOf(p) { return MARGIN_T + plotH - ((p - minPitch) / (maxPitch - minPitch + 1)) * plotH; }
    var bandH = plotH / (maxPitch - minPitch + 1);

    // Grid
    ctx.font = '9px "DM Mono", monospace';
    for (var sec = Math.ceil(t0); sec <= Math.ceil(t1); sec++) {
      var x = xOf(sec);
      if (x > W - MARGIN_R) break;
      ctx.strokeStyle = sec % 5 === 0 ? 'rgba(255,255,255,0.08)' : 'rgba(255,255,255,0.03)';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(Math.round(x) + 0.5, MARGIN_T);
      ctx.lineTo(Math.round(x) + 0.5, H - MARGIN_B);
      ctx.stroke();
      if (sec % 5 === 0) {
        ctx.fillStyle = 'rgba(232,224,212,0.35)';
        ctx.textAlign = 'center';
        ctx.fillText(fmtTime(sec), x, H - 8);
      }
    }

    // Pitch lines + labels (C notes)
    ctx.textAlign = 'right';
    for (var p = minPitch; p <= maxPitch; p++) {
      var y = Math.round(yOf(p)) + 0.5;
      if (p % 12 === 0) {
        ctx.strokeStyle = 'rgba(255,255,255,0.05)';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(MARGIN_L, y);
        ctx.lineTo(W - MARGIN_R, y);
        ctx.stroke();
        ctx.fillStyle = 'rgba(232,224,212,0.4)';
        ctx.fillText(noteName(p), MARGIN_L - 8, y + 3);
      }
    }

    // Notes (clipped to the plot area)
    var colors = {};
    var minW = 2;
    ctx.save();
    ctx.beginPath();
    ctx.rect(MARGIN_L, MARGIN_T, plotW, plotH);
    ctx.clip();
    for (var j = 0; j < notes.length; j++) {
      var note = notes[j];
      if (note.start >= t1 || note.end < t0) continue;
      var nx = xOf(note.start);
      var nw = Math.max((note.end - note.start) * pxPerSec, minW);
      var ny = yOf(note.pitch);
      ctx.fillStyle = instrumentColor(note.instrument, colors);
      var r = Math.max(Math.min(bandH / 2, 2), 0.5);
      ctx.beginPath();
      ctx.roundRect(nx, ny, nw, Math.max(bandH - 1, 2), r);
      ctx.fill();
    }
    ctx.restore();

    // Playhead
    if (opts.playhead != null) {
      var phx = xOf(opts.playhead);
      if (phx >= MARGIN_L - 4 && phx <= W - MARGIN_R + 4) {
        ctx.strokeStyle = '#F59E0B';
        ctx.lineWidth = 1.5;
        ctx.shadowColor = 'rgba(245,158,11,0.6)';
        ctx.shadowBlur = 6;
        ctx.beginPath();
        ctx.moveTo(Math.round(phx) + 0.5, MARGIN_T);
        ctx.lineTo(Math.round(phx) + 0.5, H - MARGIN_B);
        ctx.stroke();
        ctx.shadowBlur = 0;
      }
    }
  }

  window.renderPianoRoll = function (canvas, notes, opts) {
    draw(canvas, notes || [], opts || {});
  };

  window.instrumentColor = function (name) {
    return instrumentColor(name, {});
  };
})();
