// Keeps the hidden playlist_name field in sync with the picked playlist, and
// populates the opener/closer lock dropdowns from that playlist's tracks
// (GET /setup/tracks?playlist_id=...) so the DJ can pin a fixed opener or
// closer before the set gets ordered (design doc: "The DJ can lock a track
// in place, such as a fixed opener or closer, and the tool orders around it").
(function () {
  const playlistSelect = document.getElementById("playlist_id");
  const playlistNameField = document.getElementById("playlist_name");
  const openerSelect = document.getElementById("locked_opener_id");
  const closerSelect = document.getElementById("locked_closer_id");
  if (!playlistSelect) return;

  function resetLockSelect(select) {
    select.innerHTML = '<option value="">None</option>';
  }

  function loadTracksForLocks(playlistId) {
    if (!playlistId) return;
    fetch("/setup/tracks?playlist_id=" + encodeURIComponent(playlistId))
      .then(function (resp) { return resp.json(); })
      .then(function (data) {
        resetLockSelect(openerSelect);
        resetLockSelect(closerSelect);
        (data.tracks || []).forEach(function (t) {
          const label = t.name + (t.artist ? " — " + t.artist : "");
          [openerSelect, closerSelect].forEach(function (select) {
            const opt = document.createElement("option");
            opt.value = t.id;
            opt.textContent = label;
            select.appendChild(opt);
          });
        });
      })
      .catch(function () {
        // Non-fatal: locking is optional, the analyze form still works
        // without it if this fetch fails for some reason.
      });
  }

  function onPlaylistChange() {
    const opt = playlistSelect.options[playlistSelect.selectedIndex];
    if (playlistNameField && opt) playlistNameField.value = opt.text;
    loadTracksForLocks(playlistSelect.value);
  }

  playlistSelect.addEventListener("change", onPlaylistChange);
  if (playlistSelect.value) onPlaylistChange();
})();
