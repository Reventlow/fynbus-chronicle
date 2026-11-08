/*
 * Kursusmateriale player (templates/courses/player.html).
 *
 * Video: playback speed buttons (remembered per browser) and "Fortsæt fra
 * mm:ss" when the viewer left a video part-way.
 *
 * Slides: presentations (as their PDF rendition) and PDFs are drawn one
 * page at a time with pdf.js, vendored under static/js/pdfjs (4.10.38) and
 * loaded only on this page. Arrow keys / PageUp / PageDown / space / Home /
 * End move, F toggles full screen, clicking the left or right half of the
 * slide steps back or forward, and a swipe does the same on touch. The page
 * is kept in the URL (#3) and remembered per browser, so a reload or a
 * shared link lands on the same slide.
 *
 * Every localStorage access is wrapped: private windows may refuse it, and
 * the player must work without it.
 */
(function () {
  "use strict";

  function load(key) {
    try { return window.localStorage.getItem(key); } catch (e) { return null; }
  }
  function store(key, value) {
    try {
      if (value === null) window.localStorage.removeItem(key);
      else window.localStorage.setItem(key, String(value));
    } catch (e) { /* storage unavailable: keep going without it */ }
  }
  function clock(seconds) {
    var s = Math.floor(seconds % 60), m = Math.floor(seconds / 60) % 60, h = Math.floor(seconds / 3600);
    var mm = h ? String(m).padStart(2, "0") : String(m);
    return (h ? h + ":" : "") + mm + ":" + String(s).padStart(2, "0");
  }

  // ---- video ---------------------------------------------------------------

  function initVideo(stage) {
    var video = stage.querySelector("video");
    var key = "km-pos-" + stage.dataset.key;
    var page = stage.closest(".km-stage-col");
    var rateButtons = page.querySelectorAll("[data-rate]");
    var resume = page.querySelector("[data-resume]");

    function setRate(rate) {
      video.playbackRate = rate;
      rateButtons.forEach(function (b) {
        var on = Number(b.dataset.rate) === rate;
        b.classList.toggle("segmented-btn-active", on);
        b.setAttribute("aria-pressed", on ? "true" : "false");
      });
    }
    var savedRate = Number(load("km-speed")) || 1;
    setRate(savedRate);
    video.addEventListener("loadedmetadata", function () { video.playbackRate = savedRate; });
    rateButtons.forEach(function (b) {
      b.addEventListener("click", function () {
        savedRate = Number(b.dataset.rate);
        setRate(savedRate);
        store("km-speed", savedRate);
      });
    });

    video.addEventListener("loadedmetadata", function () {
      var pos = Number(load(key));
      if (pos > 10 && pos < video.duration - 10) {
        resume.textContent = "Fortsæt fra " + clock(pos);
        resume.hidden = false;
        resume.addEventListener("click", function () {
          video.currentTime = pos;
          video.play();
          resume.hidden = true;
        }, { once: true });
      }
    });
    var last = 0;
    video.addEventListener("timeupdate", function () {
      if (Math.abs(video.currentTime - last) >= 5) {
        last = video.currentTime;
        store(key, Math.floor(last));
        if (last > 10) resume.hidden = true;
      }
    });
    video.addEventListener("ended", function () {
      store(key, null);
      var next = document.querySelector("[data-next-item]");
      if (next) next.classList.add("is-up-next");
    });
  }

  // ---- slides --------------------------------------------------------------

  function initSlides(stage) {
    var page = stage.closest(".km-stage-col");
    var canvas = stage.querySelector("canvas");
    var status = stage.querySelector("[data-status]");
    var pageOut = page.querySelector("[data-page]");
    var pagesOut = page.querySelector("[data-pages]");
    var key = "km-slide-" + stage.dataset.key;
    var doc = null, current = 1, busy = false, queued = null;

    function fail(msg) {
      status.textContent = msg;
      status.hidden = false;
      stage.classList.add("is-error");
    }

    function render(n) {
      if (!doc) return;
      n = Math.max(1, Math.min(doc.numPages, n));
      current = n;
      pageOut.textContent = n;
      canvas.setAttribute("aria-label", "Side " + n + " af " + doc.numPages);
      history.replaceState(null, "", "#" + n);
      store(key, n);
      page.querySelectorAll("[data-prev]").forEach(function (b) { b.disabled = n <= 1; });
      page.querySelectorAll("[data-next]").forEach(function (b) { b.disabled = n >= doc.numPages; });
      // One render at a time (pdf.js refuses two on the same canvas); a
      // request that arrives meanwhile is kept, and only the newest one.
      if (busy) { queued = n; return; }
      busy = true;
      doc.getPage(n).then(function (p) {
        var base = p.getViewport({ scale: 1 });
        var box = stage.getBoundingClientRect();
        var full = document.fullscreenElement === stage;
        var maxW = box.width, maxH = full ? box.height : Math.max(240, window.innerHeight * 0.72);
        var scale = Math.min(maxW / base.width, maxH / base.height);
        var dpr = window.devicePixelRatio || 1;
        var vp = p.getViewport({ scale: scale * dpr });
        canvas.width = Math.floor(vp.width);
        canvas.height = Math.floor(vp.height);
        canvas.style.width = Math.floor(vp.width / dpr) + "px";
        canvas.style.height = Math.floor(vp.height / dpr) + "px";
        return p.render({ canvasContext: canvas.getContext("2d"), viewport: vp }).promise;
      }).then(function () {
        status.hidden = true;
      }).catch(function () {
        fail("Siden kunne ikke vises.");
      }).finally(function () {
        busy = false;
        if (queued !== null) { var q = queued; queued = null; render(q); }
      });
    }

    function go(delta) { render(current + delta); }

    page.querySelectorAll("[data-prev]").forEach(function (b) { b.addEventListener("click", function () { go(-1); }); });
    page.querySelectorAll("[data-next]").forEach(function (b) { b.addEventListener("click", function () { go(1); }); });

    var fsButton = page.querySelector("[data-fullscreen]");
    function toggleFullscreen() {
      if (document.fullscreenElement) document.exitFullscreen();
      else if (stage.requestFullscreen) stage.requestFullscreen().catch(function () {});
    }
    if (fsButton) {
      if (!stage.requestFullscreen) fsButton.hidden = true;
      fsButton.addEventListener("click", toggleFullscreen);
    }
    document.addEventListener("fullscreenchange", function () { render(current); });

    document.addEventListener("keydown", function (e) {
      if (e.defaultPrevented || e.altKey || e.ctrlKey || e.metaKey) return;
      var t = e.target;
      if (t && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName))) return;
      var k = e.key;
      if (k === "ArrowRight" || k === "PageDown" || (k === " " && t === stage)) { go(1); e.preventDefault(); }
      else if (k === "ArrowLeft" || k === "PageUp") { go(-1); e.preventDefault(); }
      else if (k === "Home") { render(1); e.preventDefault(); }
      else if (k === "End" && doc) { render(doc.numPages); e.preventDefault(); }
      else if (k === "f" || k === "F") { toggleFullscreen(); e.preventDefault(); }
    });

    var touchX = null;
    stage.addEventListener("touchstart", function (e) { touchX = e.touches[0].clientX; }, { passive: true });
    stage.addEventListener("touchend", function (e) {
      if (touchX === null) return;
      var dx = e.changedTouches[0].clientX - touchX;
      touchX = null;
      if (Math.abs(dx) > 50) go(dx < 0 ? 1 : -1);
    });

    var resizeTimer = null;
    window.addEventListener("resize", function () {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(function () { render(current); }, 150);
    });

    import(stage.dataset.lib).then(function (pdfjs) {
      pdfjs.GlobalWorkerOptions.workerSrc = stage.dataset.worker;
      return pdfjs.getDocument({ url: stage.dataset.src, isEvalSupported: false }).promise;
    }).then(function (d) {
      doc = d;
      pagesOut.textContent = d.numPages;
      var fromHash = parseInt(location.hash.slice(1), 10);
      render(fromHash || Number(load(key)) || 1);
    }).catch(function () {
      fail("Præsentationen kunne ikke indlæses. Prøv at hente den i stedet.");
    });
  }

  function init() {
    document.querySelectorAll("[data-video-player]").forEach(initVideo);
    document.querySelectorAll("[data-slide-player]").forEach(initSlides);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
