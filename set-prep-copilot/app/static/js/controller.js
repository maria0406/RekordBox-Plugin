// Draws Move Coach state onto the controller SVG (templates/_controller.html):
// knob angles, fader positions, lit buttons, plus a highlight ring and a
// direction arrow on whatever the DJ should be touching right now.
(function (root) {
  "use strict";

  var SVG_NS = "http://www.w3.org/2000/svg";
  var KNOB_SWEEP_DEG = 135; // knob value -1..1 maps to -135..+135 degrees

  function Controller(svg) {
    this.svg = svg;
    this.overlay = svg.querySelector("#coach-overlay");
  }

  Controller.prototype.el = function (id) {
    return this.svg.querySelector("#" + id);
  };

  Controller.prototype.set = function (id, value) {
    var el = this.el(id);
    if (!el) return;
    if (el.classList.contains("knob")) {
      el.querySelector(".knob-pointer").setAttribute("transform", "rotate(" + value * KNOB_SWEEP_DEG + ")");
    } else if (el.classList.contains("fader")) {
      var min = parseFloat(el.dataset.min), max = parseFloat(el.dataset.max);
      var pos = min + (max - min) * value;
      var cap = el.querySelector(".fader-cap");
      var other = cap.transform.baseVal.consolidate();
      if (el.dataset.axis === "x") {
        cap.setAttribute("transform", "translate(" + pos + "," + (other ? other.matrix.f : 0) + ")");
      } else {
        cap.setAttribute("transform", "translate(0," + pos + ")");
      }
    } else {
      el.classList.toggle("lit", value >= 0.5);
    }
  };

  // Center of a control in SVG viewBox coordinates.
  Controller.prototype.center = function (id) {
    var el = this.el(id);
    if (!el) return null;
    var target = el.querySelector(".fader-cap") || el.querySelector(".body") || el;
    var box = target.getBBox();
    var m = this.svg.getScreenCTM().inverse().multiply(target.getScreenCTM());
    var p = this.svg.createSVGPoint();
    p.x = box.x + box.width / 2;
    p.y = box.y + box.height / 2;
    return p.matrixTransform(m);
  };

  function node(tag, attrs) {
    var n = document.createElementNS(SVG_NS, tag);
    Object.keys(attrs).forEach(function (k) { n.setAttribute(k, attrs[k]); });
    return n;
  }

  // Arrow showing which way a control is about to move: straight along a
  // fader's axis, or curved around a knob.
  Controller.prototype.arrow = function (id, from, to) {
    var el = this.el(id), c = this.center(id);
    if (!el || !c || from === to) return null;
    if (el.classList.contains("fader")) {
      var horizontal = el.dataset.axis === "x";
      var dir = to > from ? 1 : -1;
      var len = 46;
      var dx = horizontal ? dir * len : 0;
      var dy = horizontal ? 0 : -dir * len; // fader "up" is toward smaller y
      var off = horizontal ? { x: 0, y: -26 } : { x: 34, y: 0 };
      return node("line", {
        class: "coach-arrow", "marker-end": "url(#arrowhead)",
        x1: c.x + off.x - dx / 2, y1: c.y + off.y - dy / 2,
        x2: c.x + off.x + dx / 2, y2: c.y + off.y + dy / 2,
      });
    }
    if (el.classList.contains("knob")) {
      var r = 34;
      var a0 = from * KNOB_SWEEP_DEG - 90, a1 = to * KNOB_SWEEP_DEG - 90;
      var rad = Math.PI / 180;
      var sweep = a1 > a0 ? 1 : 0;
      var large = Math.abs(a1 - a0) > 180 ? 1 : 0;
      var d = "M " + (c.x + r * Math.cos(a0 * rad)) + " " + (c.y + r * Math.sin(a0 * rad)) +
              " A " + r + " " + r + " 0 " + large + " " + sweep + " " +
              (c.x + r * Math.cos(a1 * rad)) + " " + (c.y + r * Math.sin(a1 * rad));
      return node("path", { class: "coach-arrow", d: d, "marker-end": "url(#arrowhead)" });
    }
    return null;
  };

  // state: Coach.stateAt(...) output.
  Controller.prototype.render = function (state) {
    var self = this;
    Object.keys(state.controls).forEach(function (id) { self.set(id, state.controls[id]); });

    this.svg.querySelectorAll(".ctl.focus, .ctl.soon").forEach(function (n) {
      n.classList.remove("focus", "soon");
    });
    while (this.overlay.firstChild) this.overlay.removeChild(this.overlay.firstChild);

    state.active.forEach(function (move) {
      move.focus.forEach(function (id) {
        var el = self.el(id);
        if (el) el.classList.add("focus");
      });
      move.changes.forEach(function (c) {
        var a = self.arrow(c.id, c.from, c.to);
        if (a) self.overlay.appendChild(a);
      });
    });
    if (state.next) {
      state.next.move.focus.forEach(function (id) {
        var el = self.el(id);
        if (el && !el.classList.contains("focus")) el.classList.add("soon");
      });
    }
  };

  root.Controller = Controller;
})(this);
