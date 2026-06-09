"""synthesize_atlas.py — the portal front door (spec 002, Phase C).

Generalizes synthesize.py from "one repo's sources → one storybook" to
"a workspace of repos → a folder of storybooks + an index" (the book-of-books).
It drives the DETERMINISTIC stages and makes the in-session reasoning boundary
explicit, exactly like synthesize.py — the per-scope reasoning (extract →
reconcile → compose) stays the in-session agent's work, run UNCHANGED per member.

    stage 0  adapt    each member's source → origin-stamped corpus.json   [code, here]
    ----- agent reasons each member: corpus → architecture_model + document_model -----
    finish            each document_model → <origin>.html + index.html    [code, here]

The reading principle holds per page (DESIGN §11.2 #8): each member's storybook
is the plain-English read of that source, simpler than the markdown, with every
claim's source one click away. The atlas/graph (Phases D–E) is subordinate to it.

Usage:
    # Stage 0 — adapt every member, print the per-member hand-off brief:
    uv run python skill/scripts/synthesize_atlas.py synthesis.workspace.json --work .synthesis-portal

    # Finish — once the agent has written each member's IR into the work dir,
    # render every page + the index into a site directory:
    uv run python skill/scripts/synthesize_atlas.py synthesis.workspace.json \
        --work .synthesis-portal --out site/ [--theme theme.json]

Re-runnable: it always re-adapts, and finishes only when every member's
document_model.json exists (and --out is given); otherwise it stops with the brief.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# scripts dir is importable both as a module and as a script.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import adapter_code  # noqa: E402
import adapter_doc  # noqa: E402
import adapter_speckit  # noqa: E402
import discover_links  # noqa: E402
import render as render_mod  # noqa: E402
import verify_links  # noqa: E402
from render import GLYPH, build_css, esc  # noqa: E402
from schema import DocumentModel, FragmentCorpus, LinkGraph, WorkspaceManifest  # noqa: E402

_ADAPTERS = {
    "speckit": adapter_speckit,
    "code": adapter_code,
    "doc": adapter_doc,
}

ATLAS_HAND_OFF = """\
─────────────────────────────────────────────────────────────────────────────
 STAGE 0 COMPLETE — adapted {n} workspace member(s); origin-stamped corpora in {work}
{members}
 NEXT: for EACH member, the in-session agent reasons the three phases (SKILL.md)
 into that member's work dir, using ONLY that member's locators (locators.txt):

   {work}/<origin>/architecture_model.json   (reconcile)
   {work}/<origin>/document_model.json        (compose)

 Write for a GENERAL READER (invariant #8): each page is the plain-English read of
 its source — simpler than the markdown, every claim's source one click away.

 THEN re-run this command with --out <dir> to verify + render every page + the index.
─────────────────────────────────────────────────────────────────────────────
"""


def _slug(origin: str) -> str:
    """Filesystem/URL-safe stem for a member origin."""
    return re.sub(r"[^A-Za-z0-9._-]+", "-", origin).strip("-") or "member"


def _page_filename(origin: str) -> str:
    return f"{_slug(origin)}.html"


def load_manifest(path) -> WorkspaceManifest:
    """Load a workspace manifest (.json or .toml) into the validated contract."""
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if p.suffix.lower() == ".toml":
        import tomllib  # py3.11+ stdlib
        data = tomllib.loads(text)
    else:
        data = json.loads(text)
    return WorkspaceManifest.model_validate(data)


def build_member_corpus(member, base, work) -> FragmentCorpus:
    """Adapt one member's source, then origin-stamp it (Phase A `with_origin`) so its
    locators are globally unique across the workspace — no cross-member collisions."""
    adapter = _ADAPTERS.get(member.adapter)
    if adapter is None:
        raise ValueError(f"unknown adapter {member.adapter!r} for member {member.origin!r}")
    src = (Path(base) / member.path).resolve()
    raw = Path(work) / f"corpus-{_slug(member.origin)}-raw.json"
    rc = adapter.main([str(src), "--out", str(raw), "--project-name", member.origin])
    if rc != 0:
        raise RuntimeError(f"{member.adapter} adapter failed for member {member.origin!r} ({src})")
    corpus = FragmentCorpus.model_validate_json(raw.read_text(encoding="utf-8"))
    return corpus.with_origin(member.origin)


# ─────────────────────────────── the index page ─────────────────────────────
# A lean, on-brand book-of-books index, built from the SAME design-system CSS as the
# pages (no second visual system). Phase E replaces this with the verified atlas graph.

_INDEX_CSS = """
  .idx-grid{ display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 18px; margin: 36px 0; }
  a.idx-card{ display: block; border: 1px solid var(--line-dk); border-radius: 8px; padding: 20px 22px; background: #fbf9f2;
    text-decoration: none; color: var(--ink); box-shadow: 0 4px 20px var(--shadow); transition: transform .18s, box-shadow .18s; }
  a.idx-card:hover{ transform: translateY(-3px); box-shadow: 0 10px 28px var(--shadow); }
  .idx-card .role{ font-family: var(--font-mono); font-size: 9.5px; letter-spacing: .1em; text-transform: uppercase; padding: 2px 7px; border-radius: 10px; font-weight: 600; }
  .role.docs{ background: #d9e2ea; color: #274056; } .role.spec{ background: #efe3c4; color: #6e5413; }
  .role.code{ background: #dce8d6; color: #37502f; } .role.intent{ background: #f0dccb; color: #7a4316; }
  .idx-card .idx-title{ display: block; font-family: var(--font-display); font-weight: 600; font-size: 1.3rem; margin: 12px 0 6px; letter-spacing: -.01em; }
  .idx-card .idx-desc{ font-size: .95rem; color: #42392a; margin: 0 0 12px; max-width: none; }
  .idx-card .idx-go{ font-family: var(--font-mono); font-size: 12px; color: var(--gold); letter-spacing: .04em; }
  .idx-atlas{ margin-top: 14px; }
  .idx-atlas a{ font-family: var(--font-mono); font-size: 13px; color: var(--blue); text-decoration: none; border-bottom: 1px solid rgba(44,74,99,.3); }
"""

_ATLAS_CSS = """
  .atlas-edges{ display: flex; flex-direction: column; gap: 10px; margin: 28px 0; }
  .atlas-edge{ display: flex; flex-wrap: wrap; align-items: baseline; gap: 10px 14px; padding: 12px 16px;
    border: 1px solid var(--line); border-radius: 6px; background: #fbf9f2; font-size: .95rem; }
  .atlas-edge a{ color: var(--blue); text-decoration: none; border-bottom: 1px solid rgba(44,74,99,.3); font-weight: 600; }
  .atlas-edge .rel{ font-family: var(--font-mono); font-size: 11px; letter-spacing: .08em; text-transform: uppercase; color: var(--gold); }
  .atlas-edge .ev{ font-family: var(--font-mono); font-size: 10.5px; color: #7d705a; margin-left: auto; }
  .atlas-empty{ color: #7d705a; font-style: italic; margin: 28px 0; }
"""


def render_index(manifest: WorkspaceManifest, theme: dict | None = None, has_atlas: bool = False) -> str:
    """Pure: a WorkspaceManifest → the book-of-books index HTML (one card per member)."""
    merged = {**render_mod.DEFAULT_THEME, **(manifest.theme or {}), **(theme or {})}
    css = build_css(merged) + _INDEX_CSS
    title = manifest.title or manifest.project_name or "Documentation Portal"
    project = manifest.project_name or title
    atlas_link = ('<p class="idx-atlas"><a href="atlas.html">&rarr; Traceability atlas</a></p>'
                  if has_atlas else "")
    cards = "".join(
        f'<a class="idx-card" href="{esc(_page_filename(m.origin))}">'
        f'<span class="role {esc(m.role)}">{esc(m.role)}</span>'
        f'<span class="idx-title">{esc(m.title or m.origin)}</span>'
        f'<p class="idx-desc">{esc(m.description or "")}</p>'
        f'<span class="idx-go">Read &rarr;</span></a>'
        for m in manifest.members
    )
    return (
        "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        '<meta name="color-scheme" content="light only">\n'
        '<meta name="theme-color" content="#f4f0e6">\n'
        f"<title>{esc(title)}</title>\n<style>{css}</style>\n</head>\n<body>\n"
        '<div class="grain"></div>\n'
        '<div class="wrap">\n'
        '<header class="mast">'
        f'<a href="#" class="brand-logo" aria-label="{esc(project)}">{GLYPH}<span class="brand-word">{esc(project)}</span></a>'
        '<div class="kicker"><span>Documentation Portal</span><span>Book of books</span></div>'
        f'<h1 class="title">{esc(title)}</h1>'
        '<p class="dek">One readable storybook per repository — each the plain-English read of its '
        'source, with every claim a click from the exact spec or code.</p>'
        f"{atlas_link}"
        "</header>\n"
        f'<div class="idx-grid">{cards}</div>\n'
        '<footer id="refs"><div class="genline"><span class="gm">&#9679;</span> Generated by '
        f'<a href="{render_mod.REPO_URL}" target="_blank" rel="noopener noreferrer">spec-kit-synthesis</a> '
        "— a portal of faithful, plain-English storybooks. Every claim is traceable to its source.</div></footer>\n"
        "</div>\n</body>\n</html>\n"
    )


def render_atlas(manifest: WorkspaceManifest, link_graph: LinkGraph, theme: dict | None = None) -> str:
    """Pure: a verified LinkGraph → the traceability atlas page (coverage-honest)."""
    merged = {**render_mod.DEFAULT_THEME, **(manifest.theme or {}), **(theme or {})}
    css = build_css(merged) + _ATLAS_CSS
    base_title = manifest.title or manifest.project_name or "Documentation Portal"
    project = manifest.project_name or base_title
    members = {m.origin: m for m in manifest.members}
    roles = {m.role for m in manifest.members}
    edges = link_graph.edges
    have = " · ".join(sorted(roles)) or "—"
    complete = {"docs", "spec", "code"} <= roles
    caveat = ("" if complete else
              " The intent&rarr;docs&rarr;specs&rarr;code chain is partial here — links are shown only "
              "where real evidence exists, never inferred.")
    note = (f'<div class="note flag-ok"><span class="tag">Coverage</span>'
            f'Roles present: {esc(have)}. {len(edges)} verified cross-repo link(s).{caveat}</div>')
    if edges:
        rows = []
        for e in edges:
            so, do = members.get(e.src.origin), members.get(e.dst.origin)
            sname = so.title if (so and so.title) else e.src.origin
            dname = do.title if (do and do.title) else e.dst.origin
            rows.append(
                '<div class="atlas-edge">'
                f'<a href="{esc(_page_filename(e.src.origin))}">{esc(sname)}</a>'
                f'<span class="rel">{esc(e.rel.value)}</span>'
                f'<a href="{esc(_page_filename(e.dst.origin))}">{esc(dname)}</a>'
                f'<span class="ev">{esc(e.evidence_kind.value)}: {esc(e.evidence[:48])}</span>'
                "</div>")
        body = '<div class="atlas-edges">' + "".join(rows) + "</div>"
    else:
        body = ('<p class="atlas-empty">No cross-repo links discovered yet — add declared links, '
                "shared qualified identifiers (FR-NNN / feature slugs), or agent-discovered prose references.</p>")
    return (
        "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        '<meta name="color-scheme" content="light only">\n'
        '<meta name="theme-color" content="#f4f0e6">\n'
        f"<title>{esc(base_title)} — Traceability</title>\n<style>{css}</style>\n</head>\n<body>\n"
        '<div class="grain"></div>\n<div class="wrap">\n'
        '<header class="mast">'
        f'<a href="index.html" class="brand-logo" aria-label="{esc(project)}">{GLYPH}<span class="brand-word">{esc(project)}</span></a>'
        '<div class="kicker"><span>Traceability Atlas</span><span>intent &rarr; docs &rarr; specs &rarr; code</span></div>'
        '<h1 class="title">Traceability</h1>'
        '<p class="dek">How the readable storybooks connect — every link verified, fail-closed; '
        'a fabricated cross-repo link cannot ship.</p>'
        "</header>\n"
        f"{note}\n{body}\n"
        '<footer id="refs"><div class="genline"><span class="gm">&#9679;</span> '
        '<a href="index.html">&larr; Back to the portal</a> &nbsp;&middot;&nbsp; Generated by '
        f'<a href="{render_mod.REPO_URL}" target="_blank" rel="noopener noreferrer">spec-kit-synthesis</a>.</div></footer>\n'
        "</div>\n</body>\n</html>\n"
    )


def build_site(manifest: WorkspaceManifest, doc_models: dict, link_graph: LinkGraph | None = None,
               theme: dict | None = None) -> dict:
    """Pure: manifest + per-origin DocumentModels (+ optional verified LinkGraph) → {filename: html}.

    With a LinkGraph, citation chips drill ACROSS pages (a chip whose locator is an edge source
    links to the target member's page) and an atlas.html renders the verified graph. Members
    without a DocumentModel are omitted — a half-built portal renders honestly."""
    merged_theme = {**(manifest.theme or {}), **(theme or {})}
    src_to_page: dict[str, str] = {}
    if link_graph:
        for e in link_graph.edges:
            src_to_page.setdefault(e.src.locator, _page_filename(e.dst.origin))
    resolve = (lambda ref: src_to_page.get(ref.locator)) if src_to_page else None
    site: dict[str, str] = {}
    for m in manifest.members:
        dm = doc_models.get(m.origin)
        if dm is not None:
            site[_page_filename(m.origin)] = render_mod.render(dm, merged_theme, resolve=resolve)
    if link_graph is not None:
        site["atlas.html"] = render_atlas(manifest, link_graph, theme)
    site["index.html"] = render_index(manifest, theme, has_atlas=link_graph is not None)
    return site


# ────────────────────────────────── CLI ─────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Build a documentation portal from a workspace manifest (spec 002).")
    p.add_argument("manifest", help="Path to synthesis.workspace.{json,toml}.")
    p.add_argument("--work", default=".synthesis-portal", help="Working dir for per-member IR (default: .synthesis-portal).")
    p.add_argument("--out", default=None, help="Site output directory. Requires every member's document_model.json.")
    p.add_argument("--theme", default=None, help="Optional theme-token JSON applied to the whole portal.")
    args = p.parse_args(argv)

    manifest = load_manifest(args.manifest)
    base = Path(args.manifest).resolve().parent
    work = Path(args.work)
    work.mkdir(parents=True, exist_ok=True)
    theme: dict[str, str] = {}
    if args.theme:
        loaded = json.loads(Path(args.theme).read_text(encoding="utf-8"))
        theme = {str(k): str(v) for k, v in loaded.items()}

    # ── stage 0: adapt every member (origin-stamped) ───────────────────────
    ready: dict[str, DocumentModel] = {}
    corpora: dict[str, FragmentCorpus] = {}
    lines: list[str] = []
    for m in manifest.members:
        mw = work / _slug(m.origin)
        mw.mkdir(parents=True, exist_ok=True)
        corpus = build_member_corpus(m, base, mw)
        corpora[m.origin] = corpus
        (mw / "corpus.json").write_text(corpus.model_dump_json(indent=2), encoding="utf-8")
        (mw / "locators.txt").write_text(
            "\n".join(f"{f.kind:12} {f.id}" for f in corpus.fragments) + "\n", encoding="utf-8")
        dmp = mw / "document_model.json"
        have = dmp.exists()
        if have:
            ready[m.origin] = DocumentModel.model_validate_json(dmp.read_text(encoding="utf-8"))
        lines.append(f"   [{ '✓' if have else ' ' }] {m.origin:14} ({m.role:5} · {len(corpus.fragments)} fragments) → {mw}")

    # cross-repo traceability graph (declared + deterministic shared-identifier edges); the
    # in-session agent may add evidence-gated prose edges before the finish step (spec 002 Phase D).
    link_graph = discover_links.build_link_graph(manifest, corpora)
    (work / "link_graph.json").write_text(link_graph.model_dump_json(indent=2), encoding="utf-8")
    print(f"synthesize_atlas: link_graph.json — {len(link_graph.edges)} cross-repo edge(s) "
          "(declared + shared-identifier; prose edges added by the agent).")

    missing = [m.origin for m in manifest.members if m.origin not in ready]

    # ── scaffold path: some member still needs its IR ──────────────────────
    if missing or not args.out:
        print(ATLAS_HAND_OFF.format(n=len(manifest.members), work=work, members="\n".join(lines) + "\n"))
        if args.out and missing:
            print(f"synthesize_atlas: --out given but {len(missing)} member(s) lack document_model.json: "
                  f"{', '.join(missing)} — produce them (brief above), then re-run.", file=sys.stderr)
        return 0

    # ── finish path: fail-closed link gate, then render pages + atlas + index ──
    corpus_paths = [str(work / _slug(m.origin) / "corpus.json") for m in manifest.members]
    vrc = verify_links.main([str(work / "link_graph.json"), *corpus_paths])
    if vrc != 0:
        print("synthesize_atlas: LINK VERIFY FAILED (fail-closed) — fix the flagged edges, do not bypass.",
              file=sys.stderr)
        return vrc
    site = build_site(manifest, ready, link_graph, theme)
    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    for fn, html_out in site.items():
        (outdir / fn).write_text(html_out, encoding="utf-8")
    print(f"synthesize_atlas: ✓ portal written to {outdir} ({len(site)} pages incl. index.html)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
