// Practice mode: clicking a cue animates the control it maps to on the
// generic two-deck rig, per the design doc's "Cue to move mapping" table.
// This previews the move -- it does not listen to a real MIDI controller.
(function () {
  function control(name) {
    return document.querySelector('[data-control="' + name + '"]');
  }

  function pulse(el, color, holdMs) {
    if (!el) return;
    el.style.setProperty("--pulse-color", color);
    el.classList.add("pulse");
    setTimeout(function () {
      el.classList.remove("pulse");
    }, holdMs || 1800);
  }

  function turnKnob(el, color, holdMs) {
    if (!el) return;
    el.style.setProperty("--pulse-color", color);
    el.classList.add("turn");
    setTimeout(function () {
      el.classList.remove("turn");
    }, holdMs || 2200);
  }

  function faderTo(el, direction, color, holdMs) {
    if (!el) return;
    el.style.setProperty("--pulse-color", color);
    el.classList.add(direction); // "up" or "down"
    setTimeout(function () {
      el.classList.remove(direction);
    }, holdMs || 2200);
  }

  function flashButton(btn, holdMs) {
    if (!btn) return;
    btn.style.outline = "3px solid " + (btn.dataset.color || "#fff");
    setTimeout(function () {
      btn.style.outline = "";
    }, holdMs || 900);
  }

  function animateCue(cueName, side, color, btn) {
    switch (cueName) {
      case "MIX IN": {
        const play = control(side === "in" ? "in-play" : "out-play");
        pulse(play, color, 900);
        setTimeout(function () {
          faderTo(control(side === "in" ? "in-fader" : "out-fader"), "up", color);
        }, 900);
        break;
      }
      case "MIX OUT": {
        faderTo(control(side === "out" ? "out-fader" : "in-fader"), "down", color);
        break;
      }
      case "BASS SWAP": {
        turnKnob(control("out-low"), color);
        turnKnob(control("in-low"), color);
        break;
      }
      case "FILTER": {
        turnKnob(control(side === "out" ? "out-filter" : "in-filter"), color);
        break;
      }
      case "LOOP 8": {
        pulse(control(side === "out" ? "out-loop" : "in-loop"), color, 2200);
        break;
      }
      default: {
        // e.g. DROP -- not mapped to a physical move in the design doc's
        // table (it's the "fully in" marker, not an action to take), so
        // just flash the cue button itself.
        flashButton(btn, 1200);
      }
    }
  }

  document.querySelectorAll(".cue-btn").forEach(function (btn) {
    btn.addEventListener("click", function () {
      animateCue(btn.dataset.cue, btn.dataset.side, btn.dataset.color, btn);
    });
  });
})();
