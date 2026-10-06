// Move Coach conductor: turns one transition's cue times into a timeline of
// moves, and answers "what should every control be doing at time t?".
//
// It knows nothing about where t comes from or how the answer is drawn:
// in-app practice feeds it the outgoing track's audio position; the future
// rekordbox overlay can feed it a MIDI-estimated position. The controller
// drawing (controller.js) and the demo mixer (practice.js) both render the
// same state, so what you see always matches what you hear.
//
// Times are seconds on the OUTGOING track's clock. Control values:
//   faders 0..1 (0 = down), knobs -1..1 (0 = center, -1 = fully left),
//   buttons 0/1 (lit).
(function (root) {
  "use strict";

  var LEAD_IN_BARS = 16; // demo starts this long before the mix so you hear the outgoing track alone
  var HEADS_UP_BARS = 8; // "coming up in N bars" shows this far ahead
  var TAIL_BARS = 4;

  var START_STATE = {
    "ch1-fader": 1, "ch2-fader": 0,
    "ch1-low": 0, "ch2-low": -1, // incoming bass starts killed so the two kicks don't clash
    "ch1-cfx": 0, "ch2-cfx": 0,
    "crossfader": 0.5,
    "deck1-play": 1, "deck2-play": 0,
    "deck2-cue": 0,
  };

  function barSeconds(bpm) {
    return (60 / bpm) * 4;
  }

  // opts: {outBpm, inBpm, mixOutS (outgoing MIX OUT cue), bassSwapS (outgoing
  // BASS SWAP cue), mixInS (incoming MIX IN cue)}. bassSwapS may be missing;
  // it then defaults to 16 bars after mixOutS, like cues.py places it.
  function buildTimeline(opts) {
    var bar = barSeconds(opts.outBpm);
    var t0 = opts.mixOutS;
    var swap = opts.bassSwapS != null ? opts.bassSwapS : t0 + 16 * bar;

    var moves = [
      {
        id: "cue_up", title: "Get deck 2 ready",
        detail: "Track 2 is cued on its MIX IN point. Bass is turned down on channel 2 so the kicks won't clash.",
        startS: t0 - HEADS_UP_BARS * bar, endS: t0,
        focus: ["deck2-cue", "ch2-low"], changes: [],
      },
      {
        id: "start", title: "Press PLAY on deck 2",
        detail: "Start it on the first beat of the phrase.",
        startS: t0, endS: t0 + bar / 2,
        focus: ["deck2-play"], changes: [{ id: "deck2-play", from: 0, to: 1 }],
      },
      {
        id: "fade_in", title: "Bring in channel 2",
        detail: "Slide the channel 2 fader up slowly over 8 bars.",
        startS: t0, endS: t0 + 8 * bar,
        focus: ["ch2-fader"], changes: [{ id: "ch2-fader", from: 0, to: 1 }],
      },
      {
        id: "bass_swap", title: "Swap the bass",
        detail: "In one bar: channel 1 LOW down, channel 2 LOW back to center.",
        startS: swap, endS: swap + bar,
        focus: ["ch1-low", "ch2-low"],
        changes: [{ id: "ch1-low", from: 0, to: -1 }, { id: "ch2-low", from: -1, to: 0 }],
      },
      {
        id: "filter_out", title: "Filter out channel 1",
        detail: "Turn channel 1's CFX to the right over 8 bars to thin it out.",
        startS: swap + bar, endS: swap + 9 * bar,
        focus: ["ch1-cfx"], changes: [{ id: "ch1-cfx", from: 0, to: 0.7 }],
      },
      {
        id: "fade_out", title: "Fade out channel 1",
        detail: "Pull the channel 1 fader down over 4 bars. Track 2 is now playing on its own.",
        startS: swap + 9 * bar, endS: swap + 13 * bar,
        focus: ["ch1-fader"], changes: [{ id: "ch1-fader", from: 1, to: 0 }],
      },
    ];

    return {
      bar: bar,
      startS: Math.max(0, t0 - LEAD_IN_BARS * bar),
      endS: swap + (13 + TAIL_BARS) * bar,
      mixOutS: t0,
      mixInS: opts.mixInS,
      rate: opts.inBpm ? opts.outBpm / opts.inBpm : 1, // incoming playback rate that matches tempos
      moves: moves,
    };
  }

  function easeInOut(p) {
    return p < 0.5 ? 2 * p * p : 1 - Math.pow(-2 * p + 2, 2) / 2;
  }

  // -> {controls: {id: value}, active: [move], next: {move, inBars} | null,
  //     progress: {moveId: 0..1}, incomingS: incoming track position or null}
  function stateAt(timeline, t) {
    var controls = Object.assign({}, START_STATE);
    var active = [];
    var progress = {};
    var next = null;

    timeline.moves.forEach(function (move) {
      var span = Math.max(move.endS - move.startS, 1e-6);
      var p = Math.min(1, Math.max(0, (t - move.startS) / span));
      progress[move.id] = p;
      move.changes.forEach(function (c) {
        controls[c.id] = c.from + (c.to - c.from) * easeInOut(p);
      });
      if (t >= move.startS && t < move.endS) {
        active.push(move);
      } else if (move.startS > t && (next === null || move.startS < next.move.startS)) {
        next = { move: move, inBars: (move.startS - t) / timeline.bar };
      }
    });
    if (next && next.inBars > HEADS_UP_BARS) next = null;

    var incomingS = t >= timeline.mixOutS ? timeline.mixInS + (t - timeline.mixOutS) * timeline.rate : null;
    return { controls: controls, active: active, next: next, progress: progress, incomingS: incomingS };
  }

  var Coach = { buildTimeline: buildTimeline, stateAt: stateAt, START_STATE: START_STATE };
  if (typeof module !== "undefined" && module.exports) module.exports = Coach;
  else root.Coach = Coach;
})(this);
