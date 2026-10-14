/*
 * Images in description fields (tasks, feature requests).
 *
 * Any <textarea data-paste-images> gets:
 *
 *   Paste / drop   An image pasted (Ctrl+V) or dropped into the field is
 *                  uploaded to /images/ at once; a placeholder at the cursor
 *                  is replaced by its Markdown reference,
 *                  ![billede](/images/<key>/).
 *
 *   Live preview   A box under the field renders the description through the
 *                  server's own Markdown renderer (POST /images/preview/), so
 *                  it shows exactly what the saved page will. It only appears
 *                  while the text contains an image.
 *
 *   Resizing       Each image in the preview has size buttons (S/M/L/Fuld), a
 *                  drag handle on its lower-right corner, and a remove button.
 *                  The size is stored in the text as an alt suffix,
 *                  ![billede|480](/images/<key>/), which the renderer turns
 *                  into a width attribute.
 *
 * Configuration comes from the <script> tag's data attributes (base.html):
 * data-upload-url, data-preview-url, data-csrf. Everything is delegated on
 * the document, so textareas that arrive with an htmx swap work too.
 */
(function () {
  "use strict";

  var script = document.currentScript;
  var UPLOAD_URL = script.dataset.uploadUrl;
  var PREVIEW_URL = script.dataset.previewUrl;
  var CSRF = script.dataset.csrf;

  var SIZES = [
    { label: "S", title: "Lille (240 px)", width: 240 },
    { label: "M", title: "Mellem (480 px)", width: 480 },
    { label: "L", title: "Stor (800 px)", width: 800 },
    { label: "Fuld", title: "Fuld bredde", width: null },
  ];
  var MIN_WIDTH = 40;
  var MAX_WIDTH = 2000;
  var PREVIEW_DELAY = 300;  // ms of typing quiet before the preview refreshes

  var counter = 0;

  /* ---------------------------------------------------------------- text */

  function escapeRegExp(s) {
    return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  }

  // Matches every reference to one image URL, with or without a size.
  function referencePattern(url) {
    return new RegExp("!\\[([^\\]|]*)(?:\\|\\d+)?\\]\\(" + escapeRegExp(url) + "\\)", "g");
  }

  function hasImage(text) {
    return /!\[[^\]]*\]\([^)\s]+\)/.test(text);
  }

  // Replace the textarea's value, keep the caret where it was relative to
  // the text around it, and let listeners (preview, Alpine) know.
  function setValue(textarea, value) {
    var caret = textarea.selectionStart + (value.length - textarea.value.length);
    textarea.value = value;
    textarea.selectionStart = textarea.selectionEnd = Math.max(0, Math.min(caret, value.length));
    textarea.dispatchEvent(new Event("input", { bubbles: true }));
  }

  function setImageWidth(textarea, url, width) {
    setValue(textarea, textarea.value.replace(referencePattern(url), function (_, alt) {
      return "![" + alt + (width ? "|" + width : "") + "](" + url + ")";
    }));
  }

  function removeImage(textarea, url) {
    // Take a line the reference had to itself along with it.
    var value = textarea.value.replace(referencePattern(url), "");
    setValue(textarea, value.replace(/\n{3,}/g, "\n\n").replace(/^\n+/, ""));
  }

  /* -------------------------------------------------------------- upload */

  function insertAtCursor(textarea, text) {
    var start = textarea.selectionStart, end = textarea.selectionEnd;
    var before = textarea.value.slice(0, start), after = textarea.value.slice(end);
    // Images are blocks: give them their own line.
    if (before && !/\n$/.test(before)) text = "\n" + text;
    if (after && !/^\n/.test(after)) text = text + "\n";
    textarea.value = before + text + after;
    textarea.selectionStart = textarea.selectionEnd = before.length + text.length;
    textarea.dispatchEvent(new Event("input", { bubbles: true }));
  }

  function replaceText(textarea, from, to) {
    var pos = textarea.value.indexOf(from);
    if (pos === -1) return;
    var caret = textarea.selectionStart;
    textarea.value = textarea.value.slice(0, pos) + to + textarea.value.slice(pos + from.length);
    if (caret > pos) caret += to.length - from.length;
    textarea.selectionStart = textarea.selectionEnd = caret;
    textarea.dispatchEvent(new Event("input", { bubbles: true }));
  }

  function upload(textarea, file) {
    var placeholder = "![Uploader billede " + (++counter) + "…]()";
    insertAtCursor(textarea, placeholder);

    var body = new FormData();
    body.append("image", file, file.name || "pasted.png");
    fetch(UPLOAD_URL, {
      method: "POST",
      body: body,
      headers: { "X-CSRFToken": CSRF },
      credentials: "same-origin",
    })
      .then(function (r) {
        return r.json().catch(function () { return {}; }).then(function (data) {
          if (!r.ok) throw new Error(data.error || "HTTP " + r.status);
          return data;
        });
      })
      .then(function (data) { replaceText(textarea, placeholder, data.markdown); })
      .catch(function (err) {
        replaceText(textarea, placeholder, "");
        window.alert("Billedet kunne ikke uploades: " + err.message);
      });
  }

  // Files from a paste or drop. Some sources fill only `items`, not
  // `files`, so read both and drop duplicates.
  function imageFiles(dataTransfer) {
    if (!dataTransfer) return [];
    var found = [];
    Array.prototype.forEach.call(dataTransfer.items || [], function (item) {
      if (item.kind === "file" && item.type.indexOf("image/") === 0) {
        var f = item.getAsFile();
        if (f) found.push(f);
      }
    });
    if (!found.length) {
      found = Array.prototype.filter.call(dataTransfer.files || [], function (f) {
        return f.type.indexOf("image/") === 0;
      });
    }
    return found;
  }

  function handleTransfer(event, dataTransfer) {
    var textarea = event.target;
    if (!(textarea instanceof HTMLTextAreaElement) || !textarea.hasAttribute("data-paste-images")) return;
    var files = imageFiles(dataTransfer);
    if (!files.length) return;  // ordinary text paste/drop
    event.preventDefault();
    files.forEach(function (f) { upload(textarea, f); });
  }

  /* ------------------------------------------------------------- preview */

  function previewFor(textarea) {
    if (textarea._pastePreview) return textarea._pastePreview;
    var box = document.createElement("div");
    box.className = "paste-preview";
    box.hidden = true;
    box.innerHTML =
      '<div class="paste-preview-label">Forhåndsvisning</div>' +
      '<div class="paste-preview-body md"></div>';
    textarea.insertAdjacentElement("afterend", box);
    textarea._pastePreview = box;
    return box;
  }

  function refreshPreview(textarea) {
    var box = previewFor(textarea);
    var text = textarea.value;
    if (!hasImage(text)) {
      box.hidden = true;
      return;
    }
    var seq = (textarea._previewSeq || 0) + 1;
    textarea._previewSeq = seq;
    var body = new FormData();
    body.append("text", text);
    fetch(PREVIEW_URL, {
      method: "POST",
      body: body,
      headers: { "X-CSRFToken": CSRF },
      credentials: "same-origin",
    })
      .then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.text(); })
      .then(function (html) {
        if (seq !== textarea._previewSeq) return;  // a newer render is on its way
        // Sanitised by the server's Markdown pipeline (nh3), same as the detail page.
        box.querySelector(".paste-preview-body").innerHTML = html;
        decorateImages(textarea, box);
        box.hidden = false;
      })
      .catch(function () { /* the preview is a convenience; the field still works */ });
  }

  function schedulePreview(textarea) {
    clearTimeout(textarea._previewTimer);
    textarea._previewTimer = setTimeout(function () { refreshPreview(textarea); }, PREVIEW_DELAY);
  }

  /* ------------------------------------------------------------- resizing */

  function button(label, title, onClick, active) {
    var b = document.createElement("button");
    b.type = "button";
    b.className = "paste-size-btn" + (active ? " is-active" : "");
    b.textContent = label;
    b.title = title;
    b.addEventListener("click", onClick);
    return b;
  }

  function decorateImages(textarea, box) {
    box.querySelectorAll(".paste-preview-body img").forEach(function (img) {
      var url = img.getAttribute("src");
      if (!/^\/images\/[0-9a-f]+\/$/.test(url)) return;  // only our own uploads
      var current = img.getAttribute("width") ? parseInt(img.getAttribute("width"), 10) : null;

      var figure = document.createElement("span");
      figure.className = "paste-figure";
      img.parentNode.insertBefore(figure, img);
      figure.appendChild(img);

      var bar = document.createElement("span");
      bar.className = "paste-size-bar";
      SIZES.forEach(function (size) {
        bar.appendChild(button(size.label, size.title, function () {
          setImageWidth(textarea, url, size.width);
        }, size.width === current));
      });
      var remove = button("✕", "Fjern billedet fra beskrivelsen", function () {
        removeImage(textarea, url);
      }, false);
      remove.classList.add("is-remove");
      bar.appendChild(remove);
      figure.appendChild(bar);

      var handle = document.createElement("span");
      handle.className = "paste-resize-handle";
      handle.title = "Træk for at ændre størrelsen";
      figure.appendChild(handle);
      attachDrag(textarea, url, img, handle);
    });
  }

  // Drag the corner handle: the image follows the pointer live, and the
  // width (rounded to 10 px) is written to the text on release.
  function attachDrag(textarea, url, img, handle) {
    handle.addEventListener("pointerdown", function (down) {
      down.preventDefault();
      handle.setPointerCapture(down.pointerId);
      var startX = down.clientX;
      var startWidth = img.getBoundingClientRect().width;
      var width = startWidth;

      function move(e) {
        width = Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, startWidth + e.clientX - startX));
        img.setAttribute("width", Math.round(width));
      }
      function up() {
        handle.removeEventListener("pointermove", move);
        handle.removeEventListener("pointerup", up);
        handle.removeEventListener("pointercancel", up);
        if (Math.abs(width - startWidth) >= 2) {
          setImageWidth(textarea, url, Math.round(width / 10) * 10);
        }
      }
      handle.addEventListener("pointermove", move);
      handle.addEventListener("pointerup", up);
      handle.addEventListener("pointercancel", up);
    });
  }

  /* ---------------------------------------------------------------- wiring */

  function initAll(root) {
    (root || document).querySelectorAll("textarea[data-paste-images]").forEach(function (ta) {
      if (ta._pasteInit) return;
      ta._pasteInit = true;
      if (hasImage(ta.value)) refreshPreview(ta);  // edit form with images already in it
    });
  }

  document.addEventListener("paste", function (e) { handleTransfer(e, e.clipboardData); });
  document.addEventListener("drop", function (e) { handleTransfer(e, e.dataTransfer); });
  document.addEventListener("input", function (e) {
    var t = e.target;
    if (t instanceof HTMLTextAreaElement && t.hasAttribute("data-paste-images")) schedulePreview(t);
  });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () { initAll(); });
  } else {
    initAll();
  }
  document.addEventListener("htmx:afterSwap", function (e) { initAll(e.target); });
})();
