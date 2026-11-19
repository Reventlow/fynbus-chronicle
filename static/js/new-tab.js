/*
 * Links marked data-new-tab open in a new browser tab.
 *
 * They also carry target="_blank", but some browser extensions strip that
 * attribute from every link when a page loads (seen on the ServiceDesk
 * page, 1.21.2), so a plain click opened the ticket in the same tab. This
 * listener does the same job from the click itself, which survives that.
 *
 * Only a plain left click is handled; Ctrl/Cmd/Shift/Alt-clicks and the
 * middle button keep the browser's own behaviour. rel="noreferrer" on the
 * link is honoured.
 */
(function () {
  "use strict";

  document.addEventListener("click", function (event) {
    if (event.defaultPrevented || event.button !== 0) return;
    if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    var link = event.target.closest && event.target.closest("a[data-new-tab][href]");
    if (!link) return;
    event.preventDefault();
    var rel = (link.getAttribute("rel") || "").split(/\s+/);
    var features = rel.indexOf("noreferrer") !== -1 ? "noopener,noreferrer" : "noopener";
    window.open(link.href, "_blank", features);
  });
})();
