// Minimal deck engine: arrow keys / space / click advance; each slide's .reveal elements show one by
// one before the next slide; `?` toggles speaker notes (the slide's <aside class="notes">); hash = slide index.
(function () {
  const slides = Array.from(document.querySelectorAll(".slide"));
  const progress = document.querySelector(".progress");
  const notesBox = document.querySelector(".notes");
  let i = Math.max(0, Math.min(slides.length - 1, parseInt(location.hash.slice(1) || "0", 10) || 0));
  function show(n) {
    slides.forEach((s, k) => s.classList.toggle("active", k === n));
    i = n; location.hash = String(n);
    if (progress) progress.style.width = ((n + 1) / slides.length * 100) + "%";
    const foot = slides[n].querySelector(".footer .n"); if (foot) foot.textContent = (n + 1) + " / " + slides.length;
    if (notesBox) { const a = slides[n].querySelector("aside.notes"); notesBox.innerHTML = a ? a.innerHTML : "<em>no notes</em>"; }
    slides[n].querySelectorAll("video[autoplay]").forEach(v => { try { v.currentTime = 0; v.play(); } catch (e) {} });
  }
  function next() {
    const pending = slides[i].querySelector(".reveal:not(.shown)");
    if (pending) { pending.classList.add("shown"); return; }
    if (i < slides.length - 1) show(i + 1);
  }
  function prev() { if (i > 0) show(i - 1); }
  document.addEventListener("keydown", (e) => {
    if (e.key === "ArrowRight" || e.key === " " || e.key === "PageDown") { e.preventDefault(); next(); }
    else if (e.key === "ArrowLeft" || e.key === "PageUp") { e.preventDefault(); prev(); }
    else if (e.key === "Home") show(0); else if (e.key === "End") show(slides.length - 1);
    else if (e.key === "?") notesBox && notesBox.classList.toggle("on");
    else if (e.key === "a") slides[i].querySelectorAll(".reveal").forEach(r => r.classList.add("shown"));
  });
  document.addEventListener("click", (e) => { if (!e.target.closest("a, button, input, video, .notes")) next(); });
  slides.forEach((s, k) => { const f = s.querySelector(".footer"); if (!f) { const d = document.createElement("div"); d.className = "footer"; d.innerHTML = '<span>Control, simulate and train robots with natural language</span><span class="n"></span>'; s.appendChild(d); } });
  if (location.search.includes("all=1")) document.querySelectorAll(".reveal").forEach(r => r.classList.add("shown"));
  show(i);
})();
