/*
 * Halloween parade — now and then a ghost, a jack-o'-lantern, a squadron
 * of bats, a skeleton, a zombie, a vampire or a werewolf crosses the screen
 * and does something silly, or a spider drops in from the top on its thread.
 *
 * Loaded by templates/components/halloween_banner.html on every page, but
 * it only plays while <html data-event="halloween"> (the schedule, a user
 * pick in the tweaks panel, or ?force-theme=halloween). It is decoration
 * only: actors are aria-hidden, ignore the pointer (pointer-events: none in
 * CSS), never run with prefers-reduced-motion, and pause while the tab is
 * hidden. Styles live in static/src/input.css under "Halloween".
 *
 * Preview: add ?halloween-parade=now (or =<skit name>) to any URL to play
 * one at once, or call window.chronicleHalloween.play("ghostWifi").
 */
(function () {
  "use strict";

  var FIRST_DELAY = [12, 25];   // seconds before the first skit
  var NEXT_DELAY = [70, 160];   // seconds between skits

  var reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function themeOn() {
    return document.documentElement.getAttribute("data-event") === "halloween";
  }

  function rand(min, max) {
    return min + Math.random() * (max - min);
  }

  function pick(list) {
    return list[Math.floor(Math.random() * list.length)];
  }

  // A stick-figure skeleton. Head, arms and legs are separate groups so
  // CSS can swing the limbs (walk) and pop the head off.
  var SKELETON =
    '<svg class="hw-skel" viewBox="0 0 64 128" width="64" height="128" aria-hidden="true">' +
      '<g class="hw-leg hw-leg-l"><path d="M29 80 L25 101 L23 123 L17 125"/></g>' +
      '<g class="hw-leg hw-leg-r"><path d="M35 80 L39 101 L41 123 L47 125"/></g>' +
      '<path class="hw-bone" d="M32 29 L32 76"/>' +
      '<path class="hw-bone" d="M21 37 Q32 33 43 37 M22 45 Q32 41 42 45 M23 53 Q32 49 41 53 M25 61 Q32 58 39 61"/>' +
      '<path class="hw-bone" d="M23 76 Q32 84 41 76 Z"/>' +
      '<g class="hw-arm hw-arm-l"><path d="M31 33 L21 50 L19 66"/></g>' +
      '<g class="hw-arm hw-arm-r"><path d="M33 33 L43 50 L45 66"/></g>' +
      '<g class="hw-head">' +
        '<path class="hw-skull" d="M20 15 A12 12 0 1 1 44 15 L42 24 Q32 29 22 24 Z"/>' +
        '<ellipse class="hw-eye" cx="27" cy="15" rx="3.4" ry="4"/>' +
        '<ellipse class="hw-eye" cx="37" cy="15" rx="3.4" ry="4"/>' +
        '<path class="hw-eye" d="M32 19 L30.5 22 L33.5 22 Z"/>' +
        '<path class="hw-teeth" d="M26 25 L38 25 M29 23.5 L29 26.5 M32 23.5 L32 26.5 M35 23.5 L35 26.5"/>' +
      '</g>' +
    '</svg>';

  // Each skit builds its actor, says when its speech bubble shows (ms from
  // start) and how long the whole thing runs. Optional: `left` places an
  // actor that doesn't cross (the spiders drop in at a random spot), and
  // `speaker` is the part the bubble hangs on (default: the whole actor).
  var SKITS = {
    // The skeleton's head pops off, rolls ahead, and the body chases it.
    skeletonHead: function () {
      return {
        cls: "hw-walk hw-ground hw-skit-head", ms: 15000,
        html: SKELETON, bubble: "Hov! Mit hoved!", say: [6200, 9000],
      };
    },
    // Coffee goes straight through the rib cage.
    skeletonCoffee: function () {
      return {
        cls: "hw-walk hw-ground hw-skit-coffee", ms: 16000,
        html: SKELETON + '<span class="hw-cup" aria-hidden="true">☕</span>' +
              '<span class="hw-drip"></span><span class="hw-drip hw-drip-2"></span>',
        bubble: "Kaffen løber lige igennem…", say: [5500, 9500],
      };
    },
    // Moonwalks right-to-left while facing right.
    skeletonMoonwalk: function () {
      return {
        cls: "hw-moonwalk hw-ground hw-rtl", ms: 14000,
        html: SKELETON, bubble: "Hii-hii! 🕺", say: [4500, 8000],
      };
    },
    // A ghost stops mid-screen to ask for the wifi code.
    ghostWifi: function () {
      return {
        cls: "hw-ghost hw-pause hw-mid", ms: 15000,
        html: '<span class="hw-emoji hw-bob">👻</span>',
        bubble: "Bøh! … hvad er wifi-koden?", say: [6500, 9500],
      };
    },
    // A ghost carrying a ServiceDesk ticket.
    ghostTicket: function () {
      return {
        cls: "hw-ghost hw-low", ms: 17000,
        html: '<span class="hw-emoji hw-bob">👻</span><span class="hw-sign">Ticket #666<br>Det spøger i printeren</span>',
        bubble: "Er det her helpdesk?", say: [7000, 10000],
      };
    },
    // A jack-o'-lantern rolls in, gets dizzy, wobbles, rolls on.
    pumpkinRoll: function () {
      return {
        cls: "hw-roll hw-ground hw-pause", ms: 13000,
        html: '<span class="hw-emoji hw-spin">🎃</span>',
        bubble: "Puha … jeg er svimmel.", say: [5800, 8000],
      };
    },
    // Three bats; the last one flies the wrong way first.
    bats: function () {
      return {
        cls: "hw-bats hw-top", ms: 11000,
        html: '<span class="hw-emoji hw-flap">🦇</span><span class="hw-emoji hw-flap hw-bat-2">🦇</span>' +
              '<span class="hw-emoji hw-flap hw-bat-3">🦇</span>',
        bubble: "Forkert vej, Bent!", say: [3500, 6500],
      };
    },
    // A zombie shuffles across, very slowly, lurching.
    zombieShuffle: function () {
      return {
        cls: "hw-ground", ms: 22000,
        html: '<span class="hw-emoji hw-lurch">🧟</span>',
        bubble: pick(["Hjeeerner… nej vent: kaaaffe.", "Er det … stadig mandag?", "Jeg har ikke sovet siden go-live."]),
        say: [8000, 12500],
      };
    },
    // A zombie process: stops mid-screen with its sign, refuses to die.
    zombieProcess: function () {
      return {
        cls: "hw-pause hw-low", ms: 18000,
        html: '<span class="hw-emoji hw-lurch">🧟‍♂️</span><span class="hw-sign">PID 666 &lt;defunct&gt;<br>kill -9 virker ikke</span>',
        bubble: "Jeg er en zombie-proces. Jeg går ingen steder.", say: [7800, 11000],
      };
    },
    // A vampire glides in, makes its demand, goes poof and leaves as a bat.
    vampire: function () {
      return {
        cls: "hw-pause hw-mid", ms: 15000,
        html: '<span class="hw-vamp-wrap">' +
                '<span class="hw-emoji hw-vamp">🧛</span>' +
                '<span class="hw-emoji hw-poof">💨</span>' +
                '<span class="hw-vamp-bat"><span class="hw-emoji hw-flap">🦇</span></span>' +
              '</span>',
        bubble: pick(["Jeg vil kun suge … jeres båndbredde.", "Må jeg komme ind? Jeg har ikke noget adgangskort."]),
        say: [5600, 8400],
      };
    },
    // A colleague walks in, the full moon rises, and a werewolf runs off.
    werewolf: function () {
      return {
        cls: "hw-pause hw-ground", ms: 16000,
        html: '<span class="hw-morph">' +
                '<span class="hw-emoji hw-moon">🌕</span>' +
                '<span class="hw-emoji hw-human">🧑‍💼</span>' +
                '<span class="hw-emoji hw-wolf">🐺</span>' +
              '</span>',
        bubble: pick(["Auuuu! Fuldmåne OG fredagsdeploy!", "Auuuu! Hvem har rørt min firewall?"]),
        say: [8300, 11000],
      };
    },
    // A spider drops in on its thread, dangles, says hello, climbs back up.
    spiderDrop: function () {
      return {
        cls: "hw-drop-actor", ms: 12000, left: rand(8, 60) + "vw", speaker: ".hw-spider",
        html: '<span class="hw-spider" style="--hw-depth: ' + Math.round(rand(26, 48)) + 'vh">' +
                '<span class="hw-emoji hw-dangle">🕷️</span></span>',
        bubble: pick(["Hej! Jeg er bare en lille bug.", "Det er ikke en bug. Det er en feature.", "Har I prøvet at slukke og tænde for mig?"]),
        say: [3200, 8000],
      };
    },
    // Three spiders, one after the other; the last one explains.
    spiderTrio: function () {
      var spider = function (depth, extra) {
        return '<span class="hw-spider ' + extra + '" style="--hw-depth: ' + depth + 'vh">' +
               '<span class="hw-emoji hw-dangle">🕷️</span></span>';
      };
      return {
        cls: "hw-drop-actor hw-spiders", ms: 13000, left: rand(8, 45) + "vw", speaker: ".hw-spider-3",
        html: spider(22, "hw-spider-1") + spider(34, "hw-spider-2") + spider(28, "hw-spider-3"),
        bubble: "Vi er tre bugs. Det står i release notes.", say: [4800, 9000],
      };
    },
  };

  var names = Object.keys(SKITS);
  var last = null;
  var playing = false;

  function play(name) {
    if (playing || !document.body) return;
    if (!SKITS[name]) {
      var pool = names.filter(function (n) { return n !== last; });
      name = pool[Math.floor(Math.random() * pool.length)];
    }
    last = name;
    playing = true;
    var skit = SKITS[name]();

    var actor = document.createElement("div");
    actor.className = "hw-actor " + skit.cls;
    actor.setAttribute("aria-hidden", "true");
    actor.style.setProperty("--hw-ms", skit.ms + "ms");
    if (skit.left) actor.style.left = skit.left;
    actor.innerHTML = skit.html;
    var bubble = document.createElement("span");
    bubble.className = "hw-bubble";
    bubble.textContent = skit.bubble;
    (skit.speaker && actor.querySelector(skit.speaker) || actor).appendChild(bubble);
    document.body.appendChild(actor);

    setTimeout(function () { bubble.classList.add("is-on"); }, skit.say[0]);
    setTimeout(function () { bubble.classList.remove("is-on"); }, skit.say[1]);
    setTimeout(function () {
      actor.remove();
      playing = false;
    }, skit.ms + 200);
  }

  function schedule(range) {
    setTimeout(function tick() {
      if (themeOn() && !document.hidden) play();
      schedule(NEXT_DELAY);
    }, rand(range[0], range[1]) * 1000);
  }

  window.chronicleHalloween = { play: play, skits: names };

  if (reduceMotion) return;

  function start() {
    var asked = new URLSearchParams(window.location.search).get("halloween-parade");
    if (asked) {
      // Preview: wait for Alpine to set data-event, then play once.
      setTimeout(function () { if (themeOn()) play(asked); }, 600);
    }
    schedule(FIRST_DELAY);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
