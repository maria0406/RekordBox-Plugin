// Cue color legend panel toggle, shared across every page.
(function () {
  const panel = document.getElementById("legend-panel");
  const openLink = document.getElementById("legend-toggle");
  const closeBtn = document.getElementById("legend-close");
  if (!panel || !openLink) return;

  openLink.addEventListener("click", function (e) {
    e.preventDefault();
    panel.hidden = false;
  });
  if (closeBtn) {
    closeBtn.addEventListener("click", function () {
      panel.hidden = true;
    });
  }
})();
