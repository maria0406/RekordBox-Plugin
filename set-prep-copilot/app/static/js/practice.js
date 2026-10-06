// Practice mode: watch-and-listen demo of each transition.
//
// The app plays both tracks and performs the mix itself (fader volume, LOW
// EQ, CFX filter) while the controller drawing shows the same moves. Both are
// rendered from one Coach.stateAt() call per frame, so the animation can
// never drift from what you hear. The outgoing track's audio position is the
// clock; if audio can't load, a silent wall clock drives the animation alone.
(function () {
  "use strict";

  var data = JSON.parse(document.getElementById("practice-data").textContent);
  var controller = new Controller(document.querySelector("svg.controller"));
  var caption = {
    title: document.getElementById("coach-title"),
    detail: document.getElementById("coach-detail"),
    next: document.getElementById("coach-next"),
    clock: document.getElementById("coach-clock"),
  };
  var scrub = document.getElementById("coach-scrub");
  var playBtn = document.getElementById("coach-play");

  var audioCtx = null;
  var current = null; // the Demo being shown

  function fmt(s) {
    s = Math.max(0, Math.round(s));
    return Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0");
  }

  // One deck's signal chain: <audio> -> LOW shelf -> CFX (HPF + LPF) -> fader.
  function Channel(ctx, audio) {
    this.src = ctx.createMediaElementSource(audio);
    this.low = ctx.createBiquadFilter();
    this.low.type = "lowshelf";
    this.low.frequency.value = 200;
    this.hp = ctx.createBiquadFilter();
    this.hp.type = "highpass";
    this.lp = ctx.createBiquadFilter();
    this.lp.type = "lowpass";
    this.gain = ctx.createGain();
    this.src.connect(this.low).connect(this.hp).connect(this.lp).connect(this.gain).connect(ctx.destination);
    this.apply(1, 0, 0);
  }

  Channel.prototype.apply = function (fader, low, cfx) {
    this.gain.gain.value = fader * fader; // roughly an audio-taper fader
    this.low.gain.value = low < 0 ? low * 30 : low * 6; // -30 dB "kill" .. +6 dB
    this.hp.frequency.value = cfx > 0 ? 20 * Math.pow(100, cfx) : 10; // CFX right: high-pass sweep up to 2 kHz
    this.lp.frequency.value = cfx < 0 ? 20000 * Math.pow(0.01, -cfx) : 22000; // CFX left: low-pass
  };

  function Demo(t) {
    this.t = t;
    this.timeline = Coach.buildTimeline(t);
    this.outAudio = new Audio("/audio/" + encodeURIComponent(t.outId));
    this.inAudio = new Audio("/audio/" + encodeURIComponent(t.inId));
    this.inAudio.preservesPitch = true; // keylock: tempo-matching shouldn't change the key
    this.silent = false;
    this.silentClock = { t: this.timeline.startS, last: null };
    var self = this;
    this.outAudio.addEventListener("error", function () { self.silent = true; });
  }

  Demo.prototype.ensureGraph = function () {
    if (this.outCh || this.silent) return;
    audioCtx = audioCtx || new (window.AudioContext || window.webkitAudioContext)();
    this.outCh = new Channel(audioCtx, this.outAudio);
    this.inCh = new Channel(audioCtx, this.inAudio);
  };

  Demo.prototype.time = function () {
    return this.silent ? this.silentClock.t : this.outAudio.currentTime;
  };

  Demo.prototype.seek = function (s) {
    s = Math.min(Math.max(s, this.timeline.startS), this.timeline.endS);
    if (this.silent) this.silentClock.t = s;
    else this.outAudio.currentTime = s;
    this.render();
  };

  Demo.prototype.playing = function () {
    return this.silent ? this.silentClock.last !== null : !this.outAudio.paused;
  };

  Demo.prototype.play = function () {
    this.ensureGraph();
    if (audioCtx) audioCtx.resume();
    if (this.time() >= this.timeline.endS || this.time() < this.timeline.startS) this.seek(this.timeline.startS);
    var self = this;
    if (this.silent) {
      this.silentClock.last = performance.now();
    } else {
      this.outAudio.play().catch(function () {
        self.silent = true; // e.g. file missing: fall back to animation only
        self.silentClock.t = self.timeline.startS;
        self.silentClock.last = performance.now();
      });
    }
    loop();
  };

  Demo.prototype.pause = function () {
    this.outAudio.pause();
    this.inAudio.pause();
    this.silentClock.last = null;
  };

  // Keep the incoming deck where the conductor says it should be.
  Demo.prototype.syncIncoming = function (state) {
    var a = this.inAudio;
    if (this.silent) return;
    if (state.incomingS === null || !this.playing()) {
      if (!a.paused) a.pause();
      return;
    }
    a.playbackRate = this.timeline.rate;
    if (Math.abs(a.currentTime - state.incomingS) > 0.05) a.currentTime = state.incomingS;
    if (a.paused) a.play().catch(function () {});
  };

  Demo.prototype.render = function () {
    if (this.silent && this.silentClock.last !== null) {
      var now = performance.now();
      this.silentClock.t += (now - this.silentClock.last) / 1000;
      this.silentClock.last = now;
    }
    var t = this.time();
    var state = Coach.stateAt(this.timeline, t);
    var c = state.controls;

    controller.render(state);
    if (this.outCh) {
      this.outCh.apply(c["ch1-fader"], c["ch1-low"], c["ch1-cfx"]);
      this.inCh.apply(c["ch2-fader"] * c["deck2-play"], c["ch2-low"], c["ch2-cfx"]);
    }
    this.syncIncoming(state);

    var move = state.active[state.active.length - 1];
    caption.title.textContent = move ? move.title : (t < this.timeline.mixOutS ? "Listen to track 1" : "Track 2 is playing");
    caption.detail.textContent = move ? move.detail : "";
    caption.next.textContent = state.next
      ? "Next: " + state.next.move.title + " in " + Math.ceil(state.next.inBars) + " bar" + (Math.ceil(state.next.inBars) === 1 ? "" : "s")
      : "";
    var barsToMix = (this.timeline.mixOutS - t) / this.timeline.bar;
    caption.clock.textContent = this.t.outName + " " + fmt(t) +
      (state.incomingS !== null ? "  ·  " + this.t.inName + " " + fmt(state.incomingS) : "  ·  mix starts in " + Math.ceil(barsToMix) + " bars");

    scrub.min = this.timeline.startS;
    scrub.max = this.timeline.endS;
    scrub.value = t;
    playBtn.textContent = this.playing() ? "Pause" : "Play demo";

    if (t >= this.timeline.endS) this.pause();
  };

  function loop() {
    if (!current) return;
    current.render();
    if (current.playing()) requestAnimationFrame(loop);
  }

  function select(index) {
    if (current) current.pause();
    current = new Demo(data.transitions[index]);
    document.querySelectorAll(".transition-block").forEach(function (b, i) {
      b.classList.toggle("selected", i === index);
    });
    current.render();
  }

  playBtn.addEventListener("click", function () {
    if (!current) return;
    if (current.playing()) {
      current.pause();
      current.render();
    } else {
      current.play();
    }
  });
  scrub.addEventListener("input", function () {
    if (current) current.seek(parseFloat(scrub.value));
  });

  document.querySelectorAll(".transition-block").forEach(function (block, i) {
    block.querySelector(".select-transition").addEventListener("click", function () { select(i); });
    var chips = block.querySelector(".move-chips");
    Coach.buildTimeline(data.transitions[i]).moves.forEach(function (move) {
      var chip = document.createElement("button");
      chip.type = "button";
      chip.className = "cue-btn move-chip";
      chip.textContent = move.title;
      chip.addEventListener("click", function () {
        if (!current || current.t !== data.transitions[i]) select(i);
        var m = current.timeline.moves.find(function (x) { return x.id === move.id; });
        current.seek(m.startS - current.timeline.bar); // one bar of run-up
      });
      chips.appendChild(chip);
    });
  });

  if (data.transitions.length) select(0);
})();
