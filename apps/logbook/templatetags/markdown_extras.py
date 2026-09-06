"""Template filters for rendering Markdown and splitting strings.

Two renderers over one pipeline:

``render_markdown``
    For the web UI. Code blocks carry Pygments *classes*, styled by
    static/src/input.css so they follow the light/dark theme.

``render_markdown_inline``
    For PDF, HTML and email exports, where no stylesheet is guaranteed to
    travel with the markup — email clients strip ``<style>`` and Outlook
    drops most CSS on paste. Highlight colours and block chrome are
    inlined as ``style`` attributes instead.

Both run the result through nh3 (Ammonia). These fields are written by
colleagues rather than the public, but they are still user input and
nothing in them needs to reach a browser as live markup. Markdown's own
output survives the allowlist untouched; raw ``<script>`` and event
handlers do not. Note that the export renderer has to allow ``style``
attributes — that is what it exists for — so raw HTML there could in
principle carry odd styling into a PDF. It cannot carry script.
"""

import re

import markdown
import nh3
from django import template
from django.utils.safestring import mark_safe
from markdown.treeprocessors import Treeprocessor

register = template.Library()

MARKDOWN_EXTENSIONS = ["fenced_code", "tables", "nl2br", "sane_lists", "codehilite"]

# Everything Markdown (plus Pygments) can emit. Anything else is dropped.
ALLOWED_TAGS = {
    "p", "br", "hr", "strong", "em", "del", "sup", "sub",
    "a", "img",
    "ul", "ol", "li",
    "blockquote",
    "h1", "h2", "h3", "h4", "h5", "h6",
    "code", "pre", "span", "div",
    "table", "thead", "tbody", "tr", "th", "td",
}

# class carries the Pygments token colours; href/src are URL-checked by nh3.
#
# The rest are attributes Markdown itself emits and that carry meaning:
#   ol start   — a list interrupted by a code fence continues at its own
#                number instead of restarting at 1
#   th/td style — column alignment from |:---|---:| syntax
# Leaving them out of the allowlist silently discarded both.
ALLOWED_ATTRIBUTES = {
    "*": {"class"},
    "a": {"href", "title"},
    "img": {"src", "alt", "title"},
    "ol": {"class", "start", "type", "reversed"},
    "li": {"class", "value"},
    "th": {"class", "style", "colspan", "rowspan"},
    "td": {"class", "style", "colspan", "rowspan"},
}
ALLOWED_ATTRIBUTES_INLINE = {**ALLOWED_ATTRIBUTES, "*": {"class", "style"}}
ALLOWED_URL_SCHEMES = {"http", "https", "mailto"}

# Inline styling for the export renderer, in the report palette.
EXPORT_STYLES = {
    "p": "margin: 0 0 6px;",
    "ul": "margin: 0 0 6px; padding-left: 18px;",
    "ol": "margin: 0 0 6px; padding-left: 18px;",
    "li": "margin: 2px 0;",
    "h1": "margin: 10px 0 4px; font-size: 1.25em; font-weight: 600; color: #4A4540;",
    "h2": "margin: 10px 0 4px; font-size: 1.15em; font-weight: 600; color: #4A4540;",
    "h3": "margin: 9px 0 4px; font-size: 1.05em; font-weight: 600; color: #4A4540;",
    "h4": "margin: 8px 0 4px; font-size: 1em; font-weight: 600; color: #4A4540;",
    "blockquote": (
        "margin: 6px 0; padding: 2px 0 2px 10px; "
        "border-left: 3px solid #D4CCC0; color: #6B635B;"
    ),
    "table": "border-collapse: collapse; margin: 6px 0; width: 100%;",
    "th": (
        "border: 1px solid #E5E0D8; padding: 4px 8px; text-align: left; "
        "background-color: #F0EDE8; color: #4A4540;"
    ),
    "td": "border: 1px solid #E5E0D8; padding: 4px 8px; text-align: left;",
    "hr": "border: 0; border-top: 1px solid #E5E0D8; margin: 8px 0;",
    "code": (
        "font-family: 'JetBrains Mono', Consolas, monospace; font-size: 0.9em; "
        "background-color: #F0EDE8; border-radius: 4px; padding: 1px 4px;"
    ),
}

# Code blocks. Pygments already puts its own style on the <pre> when
# noclasses is on, so these are applied on top by _style_code_blocks.
EXPORT_PRE_STYLE = (
    "margin: 6px 0; padding: 10px 12px; background-color: #FAF9F7; "
    "border: 1px solid #E5E0D8; border-radius: 8px; "
    "font-family: 'JetBrains Mono', Consolas, monospace; font-size: 0.88em; "
    "line-height: 1.5; "
    # A PDF page cannot scroll sideways, so wrap instead of overflowing.
    "white-space: pre-wrap; word-break: break-word;"
)
# Inside a <pre> the chrome belongs to the block, not to the <code>.
EXPORT_CODE_IN_PRE_STYLE = (
    "font-family: inherit; font-size: inherit; background: none; "
    "padding: 0; border-radius: 0;"
)

# Bare URLs, so a pasted link keeps working the way it did before these
# fields rendered Markdown. Skipped when the URL is already part of
# Markdown link syntax — preceded by "(", "<" or "]".
_BARE_URL = re.compile(r"(?<![(<\]\"'=])\bhttps?://[^\s<>\"'()]+[^\s<>\"'().,;:!?]")
_FENCE = re.compile(r"^\s*(```|~~~)")

# codehilite emits its markup as stashed raw HTML, so it never reaches the
# element tree — these two are styled with a search-and-replace instead.
_PRE_TAG = re.compile(r"<pre(?![^>]*\bstyle=)")
_PRE_TAG_STYLED = re.compile(r'<pre style="([^"]*)"')
_CODE_IN_PRE = re.compile(r"(<pre[^>]*>(?:<span></span>)?)<code>")


def _autolink(source: str) -> str:
    """Wrap bare URLs in Markdown autolink brackets, outside code fences.

    Markdown itself only linkifies ``<https://…>``; these fields used to go
    through Django's ``urlize``, so a plain pasted URL has always been
    clickable and should stay that way.
    """
    out, in_fence = [], False
    for line in source.splitlines():
        if _FENCE.match(line):
            in_fence = not in_fence
            out.append(line)
            continue
        out.append(line if in_fence else _BARE_URL.sub(lambda m: f"<{m.group(0)}>", line))
    return "\n".join(out)


class InlineStyleTreeprocessor(Treeprocessor):
    """Give each rendered element an inline style, for export targets."""

    def run(self, root):
        for parent in root.iter():
            for child in parent:
                style = EXPORT_STYLES.get(child.tag)
                if child.tag == "code" and parent.tag == "pre":
                    style = EXPORT_CODE_IN_PRE_STYLE
                if not style:
                    continue
                existing = child.get("style")
                child.set("style", f"{existing} {style}".strip() if existing else style)
        return root


def _style_code_blocks(html: str) -> str:
    """Inline the code-block chrome that the tree processor cannot reach."""
    html = _PRE_TAG_STYLED.sub(lambda m: f'<pre style="{m.group(1)} {EXPORT_PRE_STYLE}"', html)
    html = _PRE_TAG.sub(f'<pre style="{EXPORT_PRE_STYLE}"', html)
    return _CODE_IN_PRE.sub(rf'\1<code style="{EXPORT_CODE_IN_PRE_STYLE}">', html)


def _render(value: str, *, inline_styles: bool) -> str:
    """Render Markdown to sanitised HTML."""
    md = markdown.Markdown(
        extensions=MARKDOWN_EXTENSIONS,
        extension_configs={
            "codehilite": {
                # guess_lang would colour every unlabelled block, usually
                # wrongly; an unlabelled fence stays plain.
                "guess_lang": False,
                "noclasses": inline_styles,
                "pygments_style": "gruvbox-light",
            }
        },
    )
    if inline_styles:
        md.treeprocessors.register(InlineStyleTreeprocessor(md), "chronicle_inline_styles", 1)

    html = md.convert(_autolink(value))
    if inline_styles:
        html = _style_code_blocks(html)

    return nh3.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES_INLINE if inline_styles else ALLOWED_ATTRIBUTES,
        url_schemes=ALLOWED_URL_SCHEMES,
    )


@register.filter(name="render_markdown")
def render_markdown(value: str) -> str:
    """Render Markdown for the web UI (themeable Pygments classes)."""
    if not value:
        return ""
    return mark_safe(_render(value, inline_styles=False))


@register.filter(name="render_markdown_inline")
def render_markdown_inline(value: str) -> str:
    """Render Markdown for exports (colours and chrome inlined)."""
    if not value:
        return ""
    return mark_safe(_render(value, inline_styles=True))


@register.filter(name="split_commas")
def split_commas(value: str) -> list[str]:
    """Split a comma-separated string into a list of trimmed strings."""
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]
