// Move Coach overlay over rekordbox: same conductor (coach.js) and drawing
// (controller.js) as practice mode, but the clock is the outgoing deck's
// position as estimated from the FLX4's MIDI (GET /overlay/state, see
// app/overlay/midi_clock.py) instead of the app's own audio.
(function () {
  "use strict";

  var POLL_MS = 100;
  var data = JSON.parse(document.getElementById("overlay-data").textContent);
  var controller = new Controller(document.querySelector("svg.controller"));
  var el = function (id) { return document.getElementById(id); };

  var index = 0;
  var timeline = null;
  var snap = null; // last /overlay/state response
  var snapAt = 0; // performance.now() when it arrived

  // coach.js always describes deck 1 -> deck 2. Odd transitions run deck 2
  // -> deck 1, so swap the numbers in control ids and in the move text.
  function swapDigits(s) {
    return s.replace(/\b(deck|ch|channel|Deck|Channel|CH)(-| )?([12])\b/g, function (m, word, sep, n) {
      return word + (sep || "") + (n === "1" ? "2" : "1");
    });
  }
  function swapId(id) {
    return id.replace(/^(deck|ch)([12])-/, function (m, word, n) { return word + (n === "1" ? "2" : "1") + "-"; });
  }
  function mirrorMove(m) {
    return Object.assign({}, m, {
      title: swapDigits(m.title), detail: swapDigits(m.detail),
      focus: m.focus.map(swapId),
      changes: m.changes.map(function (c) { return Object.assign({}, c, { id: swapId(c.id) }); }),
    });
  }
  function mirrorState(s) {
    var controls = {};
    Object.keys(s.controls).forEach(function (id) { controls[swapId(id)] = s.controls[id]; });
    return Object.assign({}, s, {
      controls: controls,
      active: s.active.map(mirrorMove),
      next: s.next ? { move: mirrorMove(s.next.move), inBars: s.next.inBars } : null,
    });
  }

  function current() { return data.transitions[index]; }

  function select(i) {
    index = Math.max(0, Math.min(i, data.transitions.length - 1));
    var tr = current();
    timeline = tr ? Coach.buildTimeline(tr) : null;
    el("ov-transition").textContent = tr
      ? (index + 1) + "/" + data.transitions.length + "  " + tr.outName + " → " + tr.inName +
        "  (deck " + tr.outDeck + " → deck " + (3 - tr.outDeck) + ")"
      : "No set prepped yet. Analyze a playlist in the app first.";
  }

  function deckState(n) {
    return snap && snap.decks ? snap.decks[String(n)] : null;
  }

  // Outgoing deck position, extrapolated between polls so the animation is smooth.
  function outgoingPosition() {
    var d = deckState(current().outDeck);
    if (!d) return null;
    var elapsed = (performance.now() - snapAt) / 1000;
    return d.position + (d.playing ? elapsed * d.rate : 0);
  }

  function render() {
    requestAnimationFrame(render);
    var tr = current();
    if (!tr || !timeline) return;
    var t = outgoingPosition();
    var out = deckState(tr.outDeck);
    var inc = deckState(3 - tr.outDeck);

    if (t === null || (!out.playing && t === 0)) {
      el("coach-title").textContent = "Load " + tr.outName + " on deck " + tr.outDeck + " and press PLAY";
      el("coach-detail").textContent = "The coach follows your PLAY, CUE, LOAD and tempo moves from here.";
      el("coach-next").textContent = "";
      return;
    }

    var state = Coach.stateAt(timeline, t);
    if (tr.outDeck === 2) state = mirrorState(state);
    controller.render(state);

    var move = state.active[state.active.length - 1];
    el("coach-title").textContent = move ? move.title : (t < timeline.mixOutS ? "Let it play" : "Transition done");
    el("coach-detail").textContent = move ? move.detail : "";
    var nextBars = state.next ? Math.ceil(state.next.inBars) : null;
    el("coach-next").textContent = state.next
      ? "Next: " + state.next.move.title + " in " + nextBars + " bar" + (nextBars === 1 ? "" : "s")
      : (t < timeline.mixOutS ? "Mix starts in " + Math.ceil((timeline.mixOutS - t) / timeline.bar) + " bars" : "");

    // Hand over to the next transition once this one is finished and the
    // incoming deck is the one playing.
    if (t > timeline.endS && inc && inc.playing && index < data.transitions.length - 1) select(index + 1);
  }

  function showStatus() {
    var m = snap && snap.midi;
    el("ov-status").textContent = !m ? "Connecting…"
      : m.connected ? "Listening to " + m.port + (snap.last_message ? " · last: " + snap.last_message : "")
      : (m.error || "MIDI not connected");
  }

  function poll() {
    fetch("/overlay/state").then(function (r) { return r.json(); }).then(function (s) {
      snap = s;
      snapAt = performance.now();
      showStatus();
    }).catch(function () {}).then(function () { setTimeout(poll, POLL_MS); });
  }

  function sync(position) {
    var body = new URLSearchParams({ deck: current().outDeck, position: position });
    fetch("/overlay/sync", { method: "POST", body: body }).then(function (r) { return r.json(); }).then(function (s) {
      snap = s;
      snapAt = performance.now();
    });
  }

  el("ov-prev").addEventListener("click", function () { select(index - 1); });
  el("ov-next").addEventListener("click", function () { select(index + 1); });
  el("ov-sync-start").addEventListener("click", function () { sync(0); });
  el("ov-sync-mix").addEventListener("click", function () {
    if (timeline) sync(timeline.mixOutS - 8 * timeline.bar);
  });

  select(0);
  poll();
  render();
})();
