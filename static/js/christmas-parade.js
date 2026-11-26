/*
 * Christmas ("Jul") — the julestue scenes and the kalenderlys.
 *
 * Scenes: now and then a nisse walks in to spread some cheer (a sign, a
 * handful of glitter, risalamande with the marzipan pig in tow) or to tease
 * a little (tugging the corner of a card, hanging a tiny nisse hat on a
 * heading); children have a snowball fight along the bottom; a Lucia
 * procession walks by (rare, but guaranteed once on 13 December); a
 * reindeer peeks up from the bottom edge; a woven julehjerte floats down;
 * the sleigh crosses the sky. All art is original inline SVG.
 *
 * Loaded by templates/components/christmas_banner.html on every page, but
 * scenes only play while <html data-event="christmas"> (the schedule, a
 * user pick in the tweaks panel, or ?force-theme=christmas). Decoration
 * only: actors are aria-hidden, ignore the pointer (pointer-events: none in
 * CSS), never run with prefers-reduced-motion, pause while the tab is
 * hidden, and only one scene (one actor element, a few dozen nodes at most)
 * is on screen at a time. Styles live in static/src/input.css under "Jul".
 *
 * Kalenderlys: candleState() mirrors apps/themes/candle.py (the tests
 * compare the two). The candle markup is server-rendered; this script only
 * re-computes it from the browser's clock on load and every few minutes.
 * That is a state change, not motion, so it runs with reduced motion too.
 *
 * Preview: add ?christmas-parade=now (or =<scene name>) to any URL to play
 * one at once, or call window.chronicleChristmas.play("lucia").
 */
(function () {
  "use strict";

  // ---- Kalenderlys --------------------------------------------------------

  var DAYS = 24;

  /**
   * Where the kalenderlys stands at local time `d` (a Date). Same rules as
   * candle_state() in apps/themes/candle.py:
   *   1–24 Dec: that day, lit, burned (day - 1 + share of today) / 24;
   *   25 Dec onwards: burnt down (burned 1) and out;
   *   any other date (a preview): 1 December at the current time of day.
   */
  function candleState(d) {
    if (d.getMonth() === 11 && d.getDate() > DAYS) {
      return { day: DAYS, burned: 1, lit: false };
    }
    var day = d.getMonth() === 11 ? d.getDate() : 1;
    var seconds = d.getHours() * 3600 + d.getMinutes() * 60 + d.getSeconds();
    return { day: day, burned: (day - 1 + seconds / 86400) / DAYS, lit: true };
  }

  /** The line under the date; mirrors candle_caption() in templatetags/christmas.py. */
  function candleCaption(state) {
    if (!state.lit) return "Brændt ned. Glædelig jul!";
    var left = DAYS - state.day;
    if (left === 0) return "Juleaften: det sidste mærke brænder i dag";
    return left + " " + (left === 1 ? "dag" : "dage") + " til juleaften";
  }

  // ---- Lucia's guaranteed day ---------------------------------------------

  /**
   * Whether the guaranteed Lucia procession is still owed at local time `d`.
   * It is due on 13 December and, when the 13th is a Saturday or Sunday,
   * also on the Monday after, when people are at work. `servedYear` is the
   * year (a string, or null) in which this browser last *served* that
   * guarantee; a Lucia that came up at random or in a preview on another
   * day never sets it, so it cannot use up the guaranteed one.
   */
  function luciaDueOn(d, servedYear) {
    if (d.getMonth() !== 11) return false;
    var thirteenth = new Date(d.getFullYear(), 11, 13).getDay();   // 0 = Sunday
    var monday = thirteenth === 6 ? 15 : thirteenth === 0 ? 14 : 13;
    var day = d.getDate();
    if (day !== 13 && day !== monday) return false;
    return servedYear !== String(d.getFullYear());
  }

  // Exposed for the tests (node evaluates this file without a window).
  if (typeof module === "object" && module && module.exports) {
    module.exports = { candleState: candleState, candleCaption: candleCaption, luciaDueOn: luciaDueOn };
  }
  if (typeof window === "undefined" || typeof document === "undefined") return;

  var CANDLE_EVERY = 3 * 60 * 1000;   // re-melt every three minutes

  function refreshCandles() {
    var nodes = document.querySelectorAll("[data-xc]");
    if (!nodes.length) return;
    var state = candleState(new Date());
    var caption = candleCaption(state);
    for (var i = 0; i < nodes.length; i++) {
      var el = nodes[i];
      el.style.setProperty("--xc-left", (1 - state.burned).toFixed(4));
      el.setAttribute("data-lit", state.lit ? "1" : "0");
      var day = el.querySelector("[data-xc-day]");
      if (day) day.textContent = String(state.day);
      var cap = el.querySelector("[data-xc-caption]");
      if (cap) cap.textContent = caption;
    }
  }

  /**
   * The sidebar copy of the kalenderlys is allowed to shrink (input.css) so
   * it never pushes the on-call card and the sidebar footer out of the
   * 100vh sidebar. When it had to shrink it would show clipped, so mark
   * <html data-xc-cramped> and CSS shows the dashboard's copy instead.
   * Measured with the mark removed; both steps run in one task, so nothing
   * paints in between. A hidden slot (collapsed sidebar, theme off)
   * measures 0 and never counts as cramped.
   */
  function fitSidebarCandle() {
    var slot = document.querySelector(".xc-slot-sidebar");
    if (!slot) return;
    var root = document.documentElement;
    root.removeAttribute("data-xc-cramped");
    if (slot.scrollHeight > slot.clientHeight + 1) root.setAttribute("data-xc-cramped", "");
  }

  function watchSidebarCandle() {
    if (!document.querySelector(".xc-slot-sidebar")) return;
    fitSidebarCandle();
    var queued = false;
    function refit() {
      if (queued) return;
      queued = true;
      window.requestAnimationFrame(function () { queued = false; fitSidebarCandle(); });
    }
    window.addEventListener("resize", refit);
    document.body.addEventListener("htmx:afterSettle", refit);
    // Alpine sets data-event after load; the user collapses/expands the sidebar.
    if (window.MutationObserver) {
      new MutationObserver(refit).observe(document.documentElement,
        { attributes: true, attributeFilter: ["data-event", "data-sidebar"] });
    }
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(refit);
  }

  // ---- Scenes ---------------------------------------------------------------

  var FIRST_DELAY = [15, 30];   // seconds before the first scene
  var NEXT_DELAY = [80, 170];   // seconds between scenes
  var HAT_STAYS = 45000;        // ms a nisse hat stays on a heading

  var reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function themeOn() {
    return document.documentElement.getAttribute("data-event") === "christmas";
  }

  function rand(min, max) {
    return min + Math.random() * (max - min);
  }

  function pick(list) {
    return list[Math.floor(Math.random() * list.length)];
  }

  // A Danish nisse: red cap with a floppy tip, white beard, grey wool
  // tunic, clogs. Legs, arms and the cap are groups so CSS can walk, wave
  // and bob them. `cls` adds modifiers (xm-carry: arms held still).
  function nisse(cls) {
    return '<svg class="xm-nisse ' + (cls || "") + '" viewBox="0 0 60 100" width="54" height="90" aria-hidden="true">' +
      '<g class="xm-leg xm-leg-l"><path class="xm-wool" d="M25 70 L23 87"/>' +
        '<path class="xm-clog" d="M17 87 Q16 93 22 94 L29 94 Q31 89 26 86 Z"/></g>' +
      '<g class="xm-leg xm-leg-r"><path class="xm-wool" d="M35 70 L37 87"/>' +
        '<path class="xm-clog" d="M34 86 Q29 89 31 94 L38 94 Q44 93 43 87 Z"/></g>' +
      '<path class="xm-tunic" d="M17 75 Q15 52 30 47 Q45 52 43 75 Z"/>' +
      '<path class="xm-belt" d="M16.6 66 L43.4 66"/>' +
      '<rect class="xm-buckle" x="27.5" y="64" width="5" height="4" rx="0.8"/>' +
      '<g class="xm-arm xm-arm-l"><path class="xm-sleeve" d="M21 53 Q13 60 14 68"/><circle class="xm-skin" cx="14" cy="69.5" r="3.3"/></g>' +
      '<g class="xm-arm xm-arm-r"><path class="xm-sleeve" d="M39 53 Q47 60 46 68"/><circle class="xm-skin" cx="46" cy="69.5" r="3.3"/></g>' +
      '<circle class="xm-skin" cx="30" cy="38" r="10"/>' +
      '<path class="xm-beard" d="M20 39 Q20 55 30 57 Q40 55 40 39 Q35 45 30 44.5 Q25 45 20 39 Z"/>' +
      '<circle class="xm-cheek" cx="24.2" cy="40" r="2"/><circle class="xm-cheek" cx="35.8" cy="40" r="2"/>' +
      '<circle class="xm-nose" cx="30" cy="39.5" r="2.6"/>' +
      '<circle class="xm-eye" cx="26.4" cy="35.8" r="1.3"/><circle class="xm-eye" cx="33.6" cy="35.8" r="1.3"/>' +
      '<g class="xm-cap"><path class="xm-red" d="M19 33 Q19 16 31 9 Q43 4 51 15 Q45 15 41 19 Q42 26 41 33 Z"/>' +
        '<circle class="xm-white" cx="51" cy="16" r="3.8"/>' +
        '<rect class="xm-white" x="18" y="30" width="24" height="5" rx="2.5"/></g>' +
    '</svg>';
  }

  // A tiny nisse cap on its own, for hanging on a heading.
  var TINY_HAT =
    '<svg viewBox="0 0 30 26" width="26" height="23" aria-hidden="true">' +
      '<path class="xm-red" d="M3 22 Q4 9 14 4 Q23 0 28 9 Q24 9 21 12 Q23 17 23 22 Z"/>' +
      '<circle class="xm-white" cx="28" cy="10" r="2.8"/>' +
      '<rect class="xm-white" x="1.5" y="19.5" width="23" height="4.5" rx="2.2"/>' +
    '</svg>';

  // A child in winter clothes. Colours come from --xm-coat / --xm-knit on
  // the wrapper; the right-hand child is mirrored in CSS.
  function kid(side) {
    return '<span class="xm-kid xm-kid-' + side + '">' +
      '<svg class="xm-kid-svg" viewBox="0 0 50 80" width="46" height="74" aria-hidden="true">' +
        '<path class="xm-boot" d="M15 72 H23 V78 H12 Q11 74 15 72 Z M27 72 H35 Q39 74 38 78 H27 Z"/>' +
        '<path class="xm-pants" d="M16 58 L16 73 L23 73 L25 63 L27 73 L34 73 L34 58 Z"/>' +
        '<g class="xm-kid-arm"><path class="xm-coat-line" d="M16 42 Q10 48 11 55"/><circle class="xm-mitten" cx="11" cy="56" r="3"/></g>' +
        '<path class="xm-coat" d="M13 61 Q12 40 25 37 Q38 40 37 61 Z"/>' +
        '<g class="xm-throw-arm"><path class="xm-coat-line" d="M34 42 Q40 48 40 55"/><circle class="xm-mitten" cx="40" cy="56" r="3"/></g>' +
        '<path class="xm-scarf" d="M17 36 Q25 41 33 36 L33 40 Q25 44 17 40 Z M28 40 L33 51 L28.5 51 Z"/>' +
        '<circle class="xm-skin" cx="25" cy="27" r="9"/>' +
        '<circle class="xm-cheek" cx="20.5" cy="30" r="1.8"/><circle class="xm-cheek" cx="29.5" cy="30" r="1.8"/>' +
        '<circle class="xm-eye" cx="22" cy="26.5" r="1.1"/><circle class="xm-eye" cx="28" cy="26.5" r="1.1"/>' +
        '<path class="xm-smile" d="M22.5 31 Q25 33.4 27.5 31"/>' +
        '<g class="xm-kid-hat"><path class="xm-knit" d="M15.5 25 Q16 14 25 13 Q34 14 34.5 25 Z"/>' +
          '<rect class="xm-knit-brim" x="15" y="22" width="20" height="4.5" rx="2"/>' +
          '<circle class="xm-white" cx="25" cy="12" r="3.4"/></g>' +
      '</svg></span>';
  }

  // A Lucia-optog figure: white gown, and either the candle crown and red
  // sash (Lucia), tinsel and a single candle (an attendant), or the
  // starry cone hat and star on a stick (a stjernedreng).
  function luciaFigure(kind, extra) {
    var head =
      '<path class="xm-hair-' + (kind === "lucia" ? "light" : "dark") + '" d="M12 22 Q12 13 20 13 Q28 13 28 22 L29 34 Q20 31 11 34 Z"/>' +
      '<circle class="xm-skin" cx="20" cy="22" r="7"/>' +
      '<circle class="xm-eye" cx="17.6" cy="21.5" r="0.9"/><circle class="xm-eye" cx="22.4" cy="21.5" r="0.9"/>' +
      '<path class="xm-sing" d="M18.6 25.6 Q20 27.4 21.4 25.6 Z"/>';
    var gown =
      '<path class="xm-gown" d="M13 33 Q20 29 27 33 L34 88 Q20 91 6 88 Z"/>' +
      '<path class="xm-gown-fold" d="M16 46 L13 86 M24 46 L27 86"/>';
    var top = "";
    var hands = '<circle class="xm-skin" cx="18" cy="52" r="2.2"/><circle class="xm-skin" cx="22" cy="52" r="2.2"/>';
    if (kind === "lucia") {
      gown += '<path class="xm-sash" d="M11.6 47 L28.4 47 L28.9 51 L11.1 51 Z M22 51 L25 66 L20.5 66 Z"/>';
      top =
        '<ellipse class="xm-wreath" cx="20" cy="15.5" rx="9" ry="2.6"/>' +
        [12.5, 16.2, 20, 23.8, 27.5].map(function (x, i) {
          var h = i === 2 ? 8 : 6.5;
          return '<rect class="xm-candle" x="' + (x - 0.9) + '" y="' + (14 - h) + '" width="1.8" height="' + h + '" rx="0.4"/>' +
                 '<path class="xm-tiny-flame" d="M' + x + ' ' + (14 - h - 4) + ' Q' + (x + 1.4) + ' ' + (14 - h - 1.5) + ' ' + x + ' ' + (14 - h - 0.3) +
                 ' Q' + (x - 1.4) + ' ' + (14 - h - 1.5) + ' ' + x + ' ' + (14 - h - 4) + ' Z"/>';
        }).join("") +
        '<circle class="xm-berry" cx="15" cy="17" r="0.9"/><circle class="xm-berry" cx="25" cy="17" r="0.9"/>';
    } else if (kind === "pige") {
      top = '<path class="xm-tinsel" d="M12.5 17 Q20 12 27.5 17"/>';
      gown += '<path class="xm-tinsel" d="M12 47 L28 47"/>';
      hands =
        '<rect class="xm-candle" x="19" y="40" width="2" height="12" rx="0.4"/>' +
        '<path class="xm-tiny-flame" d="M20 34.5 Q21.6 37.5 20 39.6 Q18.4 37.5 20 34.5 Z"/>' + hands;
    } else {
      top =
        '<path class="xm-cone" d="M13.5 17 L20 -6 L26.5 17 Z"/>' +
        '<path class="xm-gold" d="M19 2 l1 -1.6 l1 1.6 l-1 1.6 Z M17.3 10 l1 -1.6 l1 1.6 l-1 1.6 Z M21.7 12 l1 -1.6 l1 1.6 l-1 1.6 Z"/>';
      hands =
        '<path class="xm-stick" d="M23 52 L31 22"/>' +
        '<path class="xm-gold" d="M31.8 13.5 L33.2 17.6 L37.4 17.8 L34 20.4 L35.2 24.5 L31.8 22 L28.4 24.5 L29.6 20.4 L26.2 17.8 L30.4 17.6 Z"/>' + hands;
    }
    return '<span class="xm-figure xm-' + kind + (extra ? " " + extra : "") + '">' +
      '<svg viewBox="0 -8 40 100" width="36" height="90" aria-hidden="true">' + gown + head + top + hands + '</svg></span>';
  }

  // A reindeer's head and neck, rising from the bottom edge.
  var REINDEER =
    '<svg class="xm-deer" viewBox="0 0 80 96" width="76" height="91" aria-hidden="true">' +
      '<g class="xm-antlers"><path class="xm-antler" d="M30 30 Q24 18 26 6 M26 16 Q19 14 16 7 M27 10 Q31 6 31 1"/>' +
        '<path class="xm-antler" d="M50 30 Q56 18 54 6 M54 16 Q61 14 64 7 M53 10 Q49 6 49 1"/></g>' +
      '<path class="xm-fur" d="M28 96 Q26 70 30 58 L50 58 Q54 70 52 96 Z"/>' +
      '<g class="xm-ear xm-ear-l"><path class="xm-fur" d="M28 34 Q16 30 14 38 Q22 42 30 39 Z"/></g>' +
      '<g class="xm-ear xm-ear-r"><path class="xm-fur" d="M52 34 Q64 30 66 38 Q58 42 50 39 Z"/></g>' +
      '<path class="xm-fur" d="M27 40 Q27 26 40 26 Q53 26 53 40 Q53 52 47 62 Q40 68 33 62 Q27 52 27 40 Z"/>' +
      '<path class="xm-muzzle" d="M32 56 Q32 50 40 50 Q48 50 48 56 Q48 64 40 65 Q32 64 32 56 Z"/>' +
      '<ellipse class="xm-deer-nose" cx="40" cy="54.5" rx="4" ry="3"/>' +
      '<g class="xm-blink"><ellipse class="xm-eye" cx="34" cy="41" rx="1.9" ry="2.3"/><ellipse class="xm-eye" cx="46" cy="41" rx="1.9" ry="2.3"/></g>' +
      '<path class="xm-collar" d="M30 72 Q40 77 50 72"/>' +
      '<circle class="xm-gold-fill" cx="40" cy="76" r="2.4"/>' +
    '</svg>';

  // A marzipan pig, the mandelgave, with a red bow.
  var PIG =
    '<span class="xm-pig"><svg viewBox="0 0 46 32" width="46" height="32" aria-hidden="true">' +
      '<path class="xm-tail" d="M6 14 q-4 -2 -3 -5 q2 -2 3 1"/>' +
      '<g class="xm-pig-leg xm-pig-leg-a"><rect class="xm-pink-dark" x="11" y="22" width="4" height="8" rx="1.5"/><rect class="xm-pink-dark" x="27" y="22" width="4" height="8" rx="1.5"/></g>' +
      '<g class="xm-pig-leg xm-pig-leg-b"><rect class="xm-pink-dark" x="15" y="22" width="4" height="8" rx="1.5"/><rect class="xm-pink-dark" x="31" y="22" width="4" height="8" rx="1.5"/></g>' +
      '<ellipse class="xm-pink" cx="21" cy="17" rx="15" ry="9"/>' +
      '<circle class="xm-pink" cx="35" cy="13" r="7.5"/>' +
      '<path class="xm-pink-dark" d="M31 7 L33 1.5 L36 6.5 Z M36.5 7 L40 3 L40.5 8.5 Z"/>' +
      '<ellipse class="xm-pink-dark" cx="41.5" cy="15" rx="3.3" ry="2.8"/>' +
      '<circle class="xm-eye" cx="40.6" cy="14.6" r="0.6"/><circle class="xm-eye" cx="42.5" cy="14.6" r="0.6"/>' +
      '<circle class="xm-eye" cx="36.5" cy="11" r="1"/>' +
      '<path class="xm-red" d="M27 13 L29.5 10.5 L29.5 15.5 Z M29.5 13 L32 10.5 L32 15.5 Z"/>' +
    '</svg></span>';

  // A bowl of risalamande with cherry sauce, the spoon stuck in.
  var BOWL =
    '<svg class="xm-bowl" viewBox="0 0 34 22" width="30" height="19" aria-hidden="true">' +
      '<path class="xm-spoon" d="M22 1 L18 11"/>' +
      '<path class="xm-rice" d="M5 10 Q8 2 17 3 Q27 2 29 10 Z"/>' +
      '<path class="xm-cherry" d="M9 7 Q15 3 22 6 Q24 9 21 9 Q20 12 18 9 Q14 10 13 8 Q11 10 9 7 Z"/>' +
      '<path class="xm-porcelain" d="M3 10 H31 Q30 20 17 21 Q4 20 3 10 Z"/>' +
      '<path class="xm-bowl-band" d="M5 13 H29"/>' +
    '</svg>';

  // A woven (flettet) julehjerte: a 4 x 4 red/white weave with a red lobe
  // and a white lobe, turned 45° so the point hangs down, and its handle.
  var HEART = (function () {
    var cells = "";
    for (var i = 0; i < 4; i++) {
      for (var j = 0; j < 4; j++) {
        cells += '<rect class="' + ((i + j) % 2 ? "xm-heart-white" : "xm-heart-red") + '" x="' + i * 6 + '" y="' + j * 6 + '" width="6" height="6"/>';
      }
    }
    return '<svg class="xm-heart" viewBox="-27 -38 54 58" width="54" height="58" aria-hidden="true">' +
      '<path class="xm-heart-handle" d="M-6 -21 Q0 -36 6 -21"/>' +
      '<g transform="rotate(45) translate(-12 -12)">' +
        '<path class="xm-heart-red" d="M0 0 A12 12 0 0 1 24 0 Z"/>' +
        '<path class="xm-heart-white" d="M0 24 A12 12 0 0 1 0 0 Z"/>' +
        cells +
        '<rect class="xm-heart-edge" x="0" y="0" width="24" height="24"/>' +
      '</g></svg>';
  })();

  // Santa's sleigh with two reindeer, flying left to right.
  function flyingDeer(x) {
    return '<g class="xm-flyer" transform="translate(' + x + ' 0)">' +
      '<g class="xm-gallop-a"><path class="xm-deer-leg" d="M8 40 L4 50 M22 40 L27 49"/></g>' +
      '<g class="xm-gallop-b"><path class="xm-deer-leg" d="M11 40 L9 51 M25 40 L31 47"/></g>' +
      '<ellipse class="xm-fur-fill" cx="16" cy="35" rx="13" ry="7"/>' +
      '<path class="xm-fur-fill" d="M25 33 L31 22 L37 23 L33 33 Z"/>' +
      '<ellipse class="xm-fur-fill" cx="37" cy="22" rx="6" ry="4"/>' +
      '<path class="xm-antler" d="M34 18 Q32 12 35 8 M33 13 L30 11 M37 18 Q39 12 43 10 M39 14 L42 15"/>' +
      '<circle class="xm-eye" cx="38" cy="21" r="0.9"/>' +
      '<circle class="xm-deer-nose-fill" cx="42.5" cy="23" r="1.5"/>' +
      '<path class="xm-tail-white" d="M3 33 Q0 31 2 29"/>' +
    '</g>';
  }
  var SLEIGH =
    '<svg class="xm-sleigh" viewBox="0 0 190 64" width="190" height="64" aria-hidden="true">' +
      '<path class="xm-rein" d="M62 34 Q90 30 104 34 Q126 32 146 34"/>' +
      flyingDeer(96) + flyingDeer(136) +
      '<path class="xm-sack" d="M8 30 Q4 14 16 12 Q22 8 26 14 Q34 18 30 30 Z"/>' +
      '<g class="xm-santa">' +
        '<path class="xm-red" d="M27 34 Q27 18 39 17 Q50 18 49 34 Z"/>' +
        '<circle class="xm-skin" cx="39" cy="14" r="6"/>' +
        '<path class="xm-white" d="M33 15 Q33 25 39 26 Q45 25 45 15 Q42 18 39 18 Q36 18 33 15 Z"/>' +
        '<path class="xm-red" d="M33 11 Q35 2 42 3 Q48 4 50 10 L45 9 Q45 11 45 12 Z"/>' +
        '<circle class="xm-white" cx="50" cy="10" r="2.2"/>' +
        '<rect class="xm-white" x="32" y="10" width="14" height="3.4" rx="1.7"/>' +
        '<circle class="xm-eye" cx="37" cy="13.6" r="0.8"/><circle class="xm-eye" cx="41.4" cy="13.6" r="0.8"/>' +
      '</g>' +
      '<path class="xm-sleigh-body" d="M6 28 H58 Q66 28 64 38 Q62 46 50 46 H18 Q6 46 6 36 Z"/>' +
      '<path class="xm-gold-line" d="M10 33 H58"/>' +
      '<path class="xm-runner" d="M10 46 L12 52 H62 Q70 52 70 45"/>' +
    '</svg>';

  // Each scene builds its actor and returns: cls (classes on the actor),
  // ms (run time), html, lines ([text, show at ms, hide at ms, speaker
  // selector inside the actor, "r" to anchor the bubble to the right]),
  // optional left/top, vars (CSS custom properties), cues ([ms, fn]) and
  // end (cleanup). A scene may return null when it cannot play right now
  // (e.g. no card in view to tug); play() then falls back to nisseCheer.
  var SKITS = {
    // A nisse walks across with a greeting sign.
    nisseCheer: function () {
      return {
        cls: "xm-walk xm-ground", ms: 16000,
        html: nisse() + '<span class="xm-sign">GOD JUL, IT!</span>',
        lines: [[pick([
          "God jul! Husk at slukke kaffemaskinen inden ferien.",
          "Nissen har talt: alle har været søde i år. Næsten.",
          "Glædelig jul fra lageret … og fra printeren.",
          "Har I gemt? Nissen spørger bare.",
        ]), 5500, 9500]],
      };
    },
    // A nisse stops mid-screen and throws a handful of glitter.
    nisseGlitter: function () {
      var bits = "";
      var colours = ["#e9b949", "#c8302b", "#dfe7ef", "#e9b949", "#5fa777"];
      for (var i = 0; i < 16; i++) {
        bits += '<i style="--dx:' + Math.round(rand(-70, 70)) + 'px;--dy:' + Math.round(rand(-90, -30)) +
                'px;--r:' + Math.round(rand(90, 540)) + 'deg;--c:' + colours[i % colours.length] +
                ';animation-delay:' + Math.round(6300 + rand(0, 400)) + 'ms"></i>';
      }
      return {
        cls: "xm-walk xm-pause xm-ground", ms: 15000,
        html: nisse("xm-toss") + '<span class="xm-glitter">' + bits + '</span>',
        lines: [[pick(["Lidt glimmer på jeres KPI'er!", "Så er der julestemning i dashboardet."]), 6600, 9600]],
      };
    },
    // Teasing: a nisse pops up at the corner of a card, tugs it, giggles
    // and scampers off. Needs a card fully in view, away from the edges.
    nisseTug: function () {
      var cards = document.querySelectorAll("main .card");
      var fits = [];
      for (var i = 0; i < cards.length && fits.length < 12; i++) {
        var r = cards[i].getBoundingClientRect();
        if (r.width > 180 && r.top > 90 && r.bottom < window.innerHeight - 12 &&
            r.bottom > 160 && r.right < window.innerWidth - 70) fits.push(cards[i]);
      }
      if (!fits.length) return null;
      var card = pick(fits);
      var rect = card.getBoundingClientRect();
      return {
        cls: "xm-perch", ms: 7500,
        left: Math.round(rect.right - 24) + "px", top: Math.round(rect.bottom - 82) + "px",
        html: nisse("xm-reach"),
        lines: [[pick(["Hihi!", "Hov, den sad løst!", "Bare et lille juletræk …"]), 2700, 5200]],
        cues: [
          [2300, function () { card.classList.add("xm-tugged"); }],
          [3900, function () { card.classList.remove("xm-tugged"); }],
        ],
        end: function () { card.classList.remove("xm-tugged"); },
      };
    },
    // Teasing: a nisse walks in, stops, and a tiny nisse hat lands on a
    // heading in view. The hat stays a while, then floats off.
    nisseHat: function () {
      if (document.querySelector(".xm-hat-perch")) return null;
      var heads = document.querySelectorAll("main h1, main h2");
      var target = null;
      for (var i = 0; i < heads.length && !target; i++) {
        var r = heads[i].getBoundingClientRect();
        if (r.width > 40 && r.top > 70 && r.bottom < window.innerHeight * 0.8) target = heads[i];
      }
      if (!target) return null;
      return {
        cls: "xm-walk xm-pause xm-ground", ms: 15000,
        html: nisse("xm-point"),
        lines: [[pick(["Sådan! Nu er overskriften også klar til jul.", "Den hue klæder den overskrift."]), 6800, 10000]],
        cues: [[6300, function () { hatOn(target); }]],
      };
    },
    // Two children in a snowball fight along the bottom of the screen.
    snowballFight: function () {
      var inset = Math.round(Math.min(70, window.innerWidth * 0.05));
      var dist = Math.max(160, window.innerWidth - 2 * inset - 70);
      function throwCue(at, side) {
        return [at, function (actor) {
          var k = actor.querySelector(".xm-kid-" + side);
          if (!k) return;
          k.classList.add("is-throwing");
          setTimeout(function () { k.classList.remove("is-throwing"); }, 450);
        }];
      }
      return {
        cls: "xm-strip", ms: 14000,
        vars: { "--xm-inset": inset + "px", "--xm-dist": dist + "px" },
        html: kid("l") + kid("r") +
              '<span class="xm-ball xm-ball-1"><i></i></span>' +
              '<span class="xm-ball xm-ball-2"><i></i></span>' +
              '<span class="xm-ball xm-ball-3"><i></i></span>' +
              '<span class="xm-puff xm-puff-1"></span><span class="xm-puff xm-puff-2"></span>',
        lines: [
          ["Ram plet!", 3200, 5000, ".xm-kid-l"],
          ["Vent bare …", 5000, 6500, ".xm-kid-r", "r"],
          ["Ha, forbi!", 7500, 9200, ".xm-kid-l"],
          ["Ikke huen! Mormor har strikket den!", 10900, 13300, ".xm-kid-r", "r"],
        ],
        cues: [throwCue(1700, "l"), throwCue(5900, "r"), throwCue(9300, "l")],
      };
    },
    // The Lucia procession: a stjernedreng, three attendants with candles
    // and Lucia with her candle crown in front, walking slowly across.
    lucia: function () {
      return {
        cls: "xm-procession xm-ground", ms: 30000,
        html: '<span class="xm-row">' +
                luciaFigure("dreng") + luciaFigure("pige", "xm-pige-1") + luciaFigure("pige", "xm-pige-2") +
                luciaFigure("pige", "xm-pige-3") + luciaFigure("lucia") +
              '</span>',
        lines: [
          ["♪ Sankta Lu-ci-aaa … ♪", 8000, 13000, ".xm-lucia"],
          [pick(["♪ … og et vers til rådighedsvagten ♪", "Psst, dit lys drypper på kablerne."]), 15500, 19500, ".xm-pige-2"],
        ],
      };
    },
    // A reindeer peeks up from the bottom edge, blinks, ducks back down.
    reindeerPeek: function () {
      return {
        cls: "xm-peek", ms: 10000, left: Math.round(rand(10, 72)) + "vw",
        html: '<span class="xm-peek-inner">' + REINDEER + '</span>',
        lines: [[pick([
          "Psst … har nogen set en slæde? Den stod ved helpdesk.",
          "Jeg kigger bare. Fortsæt med jeres tickets.",
          "Er slæden nu blevet et cloud-abonnement?",
        ]), 2200, 7200, ".xm-peek-inner"]],
      };
    },
    // A nisse brings risalamande; the marzipan pig trots behind.
    risalamande: function () {
      return {
        cls: "xm-walk xm-pause xm-ground", ms: 17000,
        html: '<span class="xm-row">' + PIG + '<span class="xm-carrier">' + nisse("xm-carry") + BOWL + '</span></span>',
        lines: [
          ["Hvem fik mandlen?", 6800, 9600, ".xm-carrier"],
          ["Øf! Jeg er mandelgaven.", 9800, 12200, ".xm-pig"],
        ],
      };
    },
    // A woven julehjerte floats down from the top, swaying.
    julehjerte: function () {
      return {
        cls: "xm-float", ms: 15000, left: Math.round(rand(8, 82)) + "vw",
        html: '<span class="xm-sway">' + HEART + '</span>',
        lines: [],
      };
    },
    // The sleigh crosses the sky below the toolbar.
    sleigh: function () {
      return {
        cls: "xm-top", ms: 13000,
        html: SLEIGH,
        lines: [[pick([
          "Ho ho ho! Er alle gaverne virusscannet?",
          "Ho ho! Hvem har skiftet wifi-koden på Nordpolen?",
          "Ho ho ho! Husk backup af ønskesedlerne!",
        ]), 4200, 8200]],
      };
    },
  };

  // How often each scene comes up relative to the others: the Lucia
  // procession is a treat (and guaranteed on 13 December, see luciaDue).
  var WEIGHTS = {
    nisseCheer: 1, nisseGlitter: 1, nisseTug: 1, nisseHat: 0.8, snowballFight: 1,
    lucia: 0.35, reindeerPeek: 1, risalamande: 0.9, julehjerte: 0.8, sleigh: 0.8,
  };

  var names = Object.keys(SKITS);
  var last = null;
  var playing = false;

  function pickSkit() {
    var pool = names.filter(function (n) { return n !== last; });
    var total = pool.reduce(function (sum, n) { return sum + (WEIGHTS[n] || 1); }, 0);
    var x = Math.random() * total;
    for (var i = 0; i < pool.length; i++) {
      x -= WEIGHTS[pool[i]] || 1;
      if (x <= 0) return pool[i];
    }
    return pool[pool.length - 1];
  }

  // Lucia is guaranteed once a year on her day (see luciaDueOn). The
  // guarantee is remembered per browser in localStorage (per page load
  // without it), and only marked as served when the scheduler played Lucia
  // *because* she was due: a random pick, a preview (?christmas-parade=lucia)
  // or chronicleChristmas.play("lucia") never counts.
  var LUCIA_KEY = "chronicleLuciaServed";
  var luciaServed = false;

  function luciaDue() {
    if (luciaServed) return false;
    var served = null;
    try { served = localStorage.getItem(LUCIA_KEY); } catch (e) { /* private mode */ }
    return luciaDueOn(new Date(), served);
  }

  function markLuciaServed() {
    luciaServed = true;
    try { localStorage.setItem(LUCIA_KEY, String(new Date().getFullYear())); } catch (e) { /* private mode */ }
  }

  // Hang the tiny nisse hat on a heading's first letter; it floats off
  // again after HAT_STAYS (or disappears with the heading on an htmx swap).
  function hatOn(heading) {
    if (!heading.isConnected || document.querySelector(".xm-hat-perch")) return;
    var hat = document.createElement("span");
    hat.className = "xm-hat-perch";
    hat.setAttribute("aria-hidden", "true");
    hat.innerHTML = TINY_HAT;
    var madeRelative = window.getComputedStyle(heading).position === "static";
    if (madeRelative) heading.classList.add("xm-hatted");
    heading.insertBefore(hat, heading.firstChild);
    setTimeout(function () {
      hat.classList.add("is-leaving");
      setTimeout(function () {
        hat.remove();
        if (madeRelative) heading.classList.remove("xm-hatted");
      }, 900);
    }, HAT_STAYS);
  }

  /**
   * Play scene `name` (or a random one). `due` is true only when the
   * scheduler asks for Lucia because her guaranteed day has come; that is
   * the one case that marks the guarantee as served.
   */
  function play(name, due) {
    if (playing || !document.body || document.querySelector(".xm-actor")) return;
    if (!SKITS[name]) name = pickSkit();
    var skit = SKITS[name]();
    if (!skit) {
      name = "nisseCheer";
      skit = SKITS.nisseCheer();
    }
    if (due && name === "lucia") markLuciaServed();
    last = name;
    playing = true;

    var actor = document.createElement("div");
    actor.className = "xm-actor " + skit.cls;
    actor.setAttribute("aria-hidden", "true");
    actor.style.setProperty("--xm-ms", skit.ms + "ms");
    if (skit.left) actor.style.left = skit.left;
    if (skit.top) actor.style.top = skit.top;
    Object.keys(skit.vars || {}).forEach(function (k) { actor.style.setProperty(k, skit.vars[k]); });
    actor.innerHTML = skit.html;

    var timers = [];
    (skit.lines || []).forEach(function (line) {
      var bubble = document.createElement("span");
      bubble.className = "xm-bubble" + (line[4] === "r" ? " xm-bubble-r" : "");
      bubble.textContent = line[0];
      (line[3] && actor.querySelector(line[3]) || actor).appendChild(bubble);
      timers.push(setTimeout(function () { bubble.classList.add("is-on"); }, line[1]));
      timers.push(setTimeout(function () { bubble.classList.remove("is-on"); }, line[2]));
    });
    (skit.cues || []).forEach(function (cue) {
      timers.push(setTimeout(function () { cue[1](actor); }, cue[0]));
    });
    document.body.appendChild(actor);

    setTimeout(function () {
      timers.forEach(clearTimeout);
      actor.remove();
      if (skit.end) skit.end();
      playing = false;
    }, skit.ms + 200);
  }

  function schedule(range) {
    setTimeout(function tick() {
      if (themeOn() && !document.hidden) {
        var due = luciaDue();
        play(due ? "lucia" : null, due);
      }
      schedule(NEXT_DELAY);
    }, rand(range[0], range[1]) * 1000);
  }

  // Public preview hook: play(name) only, so it never marks Lucia as served.
  window.chronicleChristmas = {
    play: function (name) { play(name, false); }, skits: names, candleState: candleState,
  };

  function start() {
    refreshCandles();
    setInterval(refreshCandles, CANDLE_EVERY);
    document.addEventListener("visibilitychange", function () {
      if (!document.hidden) refreshCandles();
    });
    document.body.addEventListener("htmx:afterSettle", refreshCandles);
    watchSidebarCandle();

    if (reduceMotion) return;
    var asked = new URLSearchParams(window.location.search).get("christmas-parade");
    if (asked) {
      // Preview: wait for Alpine to set data-event, then play once.
      setTimeout(function () { if (themeOn()) play(asked, false); }, 600);
    }
    schedule(FIRST_DELAY);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
