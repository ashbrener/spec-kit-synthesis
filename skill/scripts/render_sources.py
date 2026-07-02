"""render_sources.py — the drill-to-source read surface (spec 003).

Reconstructs each cited source file from its corpus fragments and renders it as a beautified,
in-design-system HTML page (`sources/<file>.html`), so a citation chip can open the actual
source at the exact cited section. Pure + deterministic (stdlib only): the markdown is rendered
CLIENT-SIDE via CDN markdown-it + Mermaid (Python stays pydantic-only; consistent with the
CDN-fonts decision), and degrades to readable raw text with no JS.

This is a Layer-2 READ surface (DESIGN §1.7): a function of the corpus the run already reasoned
over. It changes nothing about extraction, reconciliation, compose, or the fail-closed verify
gate — it just makes the cited source readable instead of merely named (strengthens invariant I;
generated-never-authored, invariant V).
"""

from __future__ import annotations

import base64
import re
from collections import OrderedDict
from pathlib import Path

from render import DEFAULT_THEME, GLYPH, REPO_URL, build_css, esc
from schema import FragmentCorpus, SourceRef

_MD_CDN = "https://cdn.jsdelivr.net/npm/markdown-it@14/dist/markdown-it.min.js"
_MERMAID_CDN = "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"


def _loc_parts(locator: str) -> tuple[str, str]:
    """(file, section-anchor) from a fragment locator, dropping any `origin::` namespace."""
    bare = locator.split("::", 1)[-1]
    file, _, anchor = bare.partition("#")
    return file, anchor


def _safe(file: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", file).strip("-") or "source"


# Source-type taxonomy for the drilled source page (spec 011): the fragment `kind` → one of six
# categories (+ neutral 'source' default). Drives the header band/label/left-rule. Total.
_PAGE_CAT_LABEL = {"spec": "Spec", "plan": "Plan", "adr": "ADR", "research": "Research",
                   "code": "Code", "narrative": "Narrative", "source": "Source"}


def _page_category(kind: str) -> str:
    k = (kind or "").lower()
    if k in ("spec", "tasks", "data-model", "contract"):
        return "spec"
    if k == "plan":
        return "plan"
    if k == "research":
        return "research"
    if k == "adr":
        return "adr"
    if k in ("code", "code-symbol"):
        return "code"
    if k == "design-doc":
        return "narrative"
    return "source"


def source_page_name(locator: str) -> str:
    """Filename of the source page that a locator's file renders to."""
    return f"{_safe(_loc_parts(locator)[0])}.html"


def _group_by_file(corpus: FragmentCorpus) -> "OrderedDict[str, list]":
    """file -> [fragments], first-appearance order preserved (deterministic)."""
    groups: "OrderedDict[str, list]" = OrderedDict()
    for f in corpus.fragments:
        file, _ = _loc_parts(f.id)
        groups.setdefault(file, []).append(f)
    return groups


_SOURCE_CSS = """
  .srcwrap{ max-width: 860px; }
  .srchead{ padding: 40px 0 8px 18px; border-bottom: 1px solid var(--line); border-left: 4px solid var(--line-dk); margin-bottom: 28px; }
  /* source-type identity (spec 011): a tinted band + explicit label + a category-tinted left rule.
     Colour is paired with the label, never the sole signal. */
  .srchead.spec{ border-left-color: var(--gold); } .srchead.code{ border-left-color: var(--green); }
  .srchead.adr{ border-left-color: var(--red); } .srchead.narrative{ border-left-color: var(--blue); }
  .srchead.plan{ border-left-color: var(--acc-plan); } .srchead.research{ border-left-color: var(--acc-research); }
  .srchead.source{ border-left-color: var(--line-dk); }
  .srctype{ display: inline-block; font-family: var(--font-mono); font-size: 10px; font-weight: 600; letter-spacing: .08em; text-transform: uppercase; color: #fff; padding: 2px 9px; border-radius: 4px; margin: 10px 0 0; }
  .srctype.spec{ background: var(--gold); } .srctype.code{ background: var(--green); } .srctype.adr{ background: var(--red); }
  .srctype.narrative{ background: var(--blue); } .srctype.plan{ background: var(--acc-plan); } .srctype.research{ background: var(--acc-research); } .srctype.source{ background: var(--line-dk); }
  a.srcback{ font-family: var(--font-mono); font-size: 12px; letter-spacing: .04em; color: var(--gold); text-decoration: none; }
  a.srcback:hover{ text-decoration: underline; }
  h1.srctitle{ font-family: var(--font-mono); font-size: clamp(1.1rem,2.4vw,1.5rem); font-weight: 600; color: var(--ink); margin: 12px 0 0; word-break: break-all; }
  .md{ font-family: var(--font-body); color: var(--ink); }
  .md h1,.md h2,.md h3,.md h4{ font-family: var(--font-display); font-weight: 700; letter-spacing: -.01em; line-height: 1.2; margin: 1.6em 0 .5em; }
  .md h1{ font-size: 1.9rem; } .md h2{ font-size: 1.5rem; } .md h3{ font-size: 1.22rem; } .md h4{ font-size: 1.05rem; }
  .md p,.md li{ font-size: 1.04rem; line-height: 1.62; }
  .md a{ color: var(--blue); }
  .md code{ font-family: var(--font-mono); font-size: .88em; background: var(--paper-2); border: 1px solid var(--line); border-radius: 4px; padding: .08em .35em; }
  .md pre{ background: #fbf9f2; border: 1px solid var(--line-dk); border-radius: 8px; padding: 14px 16px; overflow-x: auto; box-shadow: inset 0 1px 6px var(--shadow); }
  .md pre code{ background: none; border: none; padding: 0; font-size: .85rem; line-height: 1.5; }
  .md pre.mermaid{ background: #fbf9f2; text-align: center; }
  .md table{ border-collapse: collapse; width: 100%; margin: 1em 0; font-size: .95rem; }
  .md th,.md td{ border: 1px solid var(--line-dk); padding: 7px 11px; text-align: left; }
  .md th{ background: var(--paper-2); font-family: var(--font-mono); font-size: 11px; letter-spacing: .06em; text-transform: uppercase; }
  .md blockquote{ border-left: 3px solid var(--gold); margin: 1em 0; padding: .2em 0 .2em 16px; color: #5b513c; }
  .md .srcanchor{ display: block; position: relative; top: -70px; visibility: hidden; }
  .md hr{ border: none; border-top: 1px solid var(--line); margin: 2em 0; }
  pre.rawmd{ white-space: pre-wrap; font-family: var(--font-mono); font-size: .82rem; color: var(--ink); }
"""

_BOOTSTRAP = """
(function(){
  var el=document.getElementById('src-md'), body=document.getElementById('srcbody');
  if(!el||!body||!window.markdownit){return;}
  var md=window.markdownit({html:true,linkify:true,typographer:true});
  var text=new TextDecoder('utf-8').decode(Uint8Array.from(atob(el.getAttribute('data-md')),function(c){return c.charCodeAt(0);}));
  body.innerHTML=md.render(text);
  body.querySelectorAll('code.language-mermaid').forEach(function(c){
    var d=document.createElement('pre'); d.className='mermaid'; d.textContent=c.textContent;
    (c.parentElement||c).replaceWith(d);
  });
  if(window.mermaid){ try{ mermaid.initialize({startOnLoad:false,theme:'neutral'}); mermaid.run({querySelector:'.mermaid'}); }catch(e){} }
  if(location.hash){ var t=document.getElementById(decodeURIComponent(location.hash.slice(1))); if(t){t.scrollIntoView();} }
})();
"""


def _page_html(file: str, fragments: list, theme: dict, back_href: str, back_label: str, project: str) -> str:
    # Reconstruct the file: each section's markdown, preceded by an anchor matching its locator.
    blob_parts = []
    for fr in fragments:
        _, anchor = _loc_parts(fr.id)
        blob_parts.append(f'<a id="{anchor}" class="srcanchor"></a>\n\n{fr.text or ""}')
    blob = "\n\n".join(blob_parts).strip() + "\n"
    b64 = base64.b64encode(blob.encode("utf-8")).decode("ascii")
    css = build_css(theme) + _SOURCE_CSS
    kind = fragments[0].kind if fragments else "document"
    cat = _page_category(kind)
    cat_label = _PAGE_CAT_LABEL[cat]
    return (
        '<!DOCTYPE html>\n<html lang="en">\n<head>\n'
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        '<meta name="color-scheme" content="light only">\n'
        '<meta name="theme-color" content="#f4f0e6">\n'
        f"<title>{esc(file)} — {esc(project)}</title>\n<style>{css}</style>\n</head>\n<body>\n"
        '<div class="grain"></div>\n<div class="wrap srcwrap">\n'
        f'<header class="srchead {cat}">'
        f'<a class="srcback" href="{esc(back_href)}">&larr; {esc(back_label)}</a>'
        f'<div class="kicker"><span>Source</span><span>{esc(kind)}</span></div>'
        f'<div class="srctype {cat}">{esc(cat_label)}</div>'
        f'<h1 class="srctitle">{esc(file)}</h1>'
        "</header>\n"
        '<article id="srcbody" class="md"></article>\n'
        f'<noscript><pre class="rawmd">{esc(blob)}</pre></noscript>\n'
        '<footer id="refs"><div class="genline"><span class="gm">&#9679;</span> Source view generated by '
        f'<a href="{REPO_URL}" target="_blank" rel="noopener noreferrer">spec-kit-atlas</a> '
        "— a faithful render of the cited source. Edit the source and regenerate; never this file.</div></footer>\n"
        "</div>\n"
        f'<div id="src-md" data-md="{b64}" hidden></div>\n'
        f'<script src="{_MD_CDN}"></script>\n'
        f'<script src="{_MERMAID_CDN}"></script>\n'
        f"<script>{_BOOTSTRAP}</script>\n"
        "</body>\n</html>\n"
    )


def render_source_pages(corpus: FragmentCorpus, theme: dict | None = None,
                        back_href: str = "../architecture.html",
                        back_label: str = "Back to the storybook",
                        project: str | None = None) -> dict[str, str]:
    """Pure: a FragmentCorpus → {"<safe-file>.html": html} — one beautified page per source file.
    Caller writes these under a `sources/` (or `sources/<origin>/`) directory."""
    merged = {**DEFAULT_THEME, **(theme or {})}
    proj = project or corpus.project_name
    out: dict[str, str] = {}
    for file, frags in _group_by_file(corpus).items():
        out[f"{_safe(file)}.html"] = _page_html(file, frags, merged, back_href, back_label, proj)
    return out


def build_source_resolver(corpus: FragmentCorpus, base: str = "sources/"):
    """Return a `resolve(ref)` for render.py: maps a citation's locator to its source-view
    section (`<base><safe-file>.html#<anchor>`) when that file was emitted, else None so the
    chip falls back to the References appendix. Composes under a portal's cross-repo resolver."""
    known = {_safe(_loc_parts(f.id)[0]) for f in corpus.fragments}

    def resolve(ref: SourceRef):
        file, anchor = _loc_parts(ref.locator)
        safe = _safe(file)
        if safe not in known:
            return None
        return f"{base}{safe}.html#{anchor}" if anchor else f"{base}{safe}.html"

    return resolve


def _ref_origin(ref: SourceRef) -> str | None:
    """The member a citation belongs to: the locator's `origin::` prefix, else ref.origin."""
    if "::" in ref.locator:
        return ref.locator.split("::", 1)[0]
    return ref.origin


def build_workspace_source_resolver(corpora_by_origin: dict[str, FragmentCorpus]):
    """Portal-wide drill-to-source (FR-005): a citation to ANY member's spec/ADR resolves to that
    member's bundled source view (`sources/<origin>/<file>.html#<section>`) — so from any page you
    can read the real source of any related repo. Determines the owning member from the ref's
    origin. Returns None for unknown members/files so a higher-priority resolver (or the
    References appendix) can take over."""
    known: dict[str, set[str]] = {
        origin: {_safe(_loc_parts(f.id)[0]) for f in corpus.fragments}
        for origin, corpus in corpora_by_origin.items()
    }

    def resolve(ref: SourceRef):
        origin = _ref_origin(ref)
        if not origin or origin not in known:
            return None
        file, anchor = _loc_parts(ref.locator)
        safe = _safe(file)
        if safe not in known[origin]:
            return None
        base = f"sources/{origin}/"
        return f"{base}{safe}.html#{anchor}" if anchor else f"{base}{safe}.html"

    return resolve


def compose_resolvers(*resolvers):
    """Chain resolvers: first non-None href wins. Lets a portal try cross-repo PAGE links first,
    then fall back to drill-to-source (or vice-versa). None-safe."""
    fns = [r for r in resolvers if r is not None]

    def resolve(ref: SourceRef):
        for fn in fns:
            href = fn(ref)
            if href:
                return href
        return None

    return resolve


def write_source_views(corpus: FragmentCorpus, out_dir, theme: dict | None = None, *,
                       subdir: str = "sources", back_href: str = "../architecture.html",
                       back_label: str = "Back to the storybook", project: str | None = None) -> int:
    """Write per-file source pages under <out_dir>/<subdir>/ (single-repo storybook). Returns the
    count. The bundled, self-contained read surface a chip resolver drills into."""
    pages = render_source_pages(corpus, theme, back_href=back_href, back_label=back_label, project=project)
    d = Path(out_dir) / subdir
    d.mkdir(parents=True, exist_ok=True)
    for name, html in pages.items():
        (d / name).write_text(html, encoding="utf-8")
    return len(pages)
