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
from typing import Optional

# scripts dir is importable both as a module and as a script.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import adapter_code  # noqa: E402
import adapter_doc  # noqa: E402
import adapter_speckit  # noqa: E402
import discover_links  # noqa: E402
import gov_config  # noqa: E402
import render as render_mod  # noqa: E402
import render_sources  # noqa: E402
import verify_links  # noqa: E402
from render import GLYPH, build_css, esc  # noqa: E402
from schema import (DocumentModel, FragmentCorpus, LinkEvidenceKind, LinkGraph,  # noqa: E402
                    WorkspaceManifest)

from pydantic import BaseModel  # noqa: E402

_ADAPTERS = {
    "speckit": adapter_speckit,
    "code": adapter_code,
    "doc": adapter_doc,
}


# ───────────────────── topology resolution (spec 004 US2) ────────────────────
# When a project publishes a `.spec-arch-domain.yml`, it is the SOURCE OF TRUTH for structural
# topology (members / roles / namespaces / locators), graded `declared`. The workspace record
# (synthesis.workspace.json) supplies PRESENTATION (title/description/theme/order) always, and
# the full topology FALLBACK when no manifest is present. On overlap the manifest wins on
# structural fields; the manifest carries no presentation. An ungoverned project (no manifest)
# resolves to exactly its workspace record — unchanged behaviour.

class ResolvedMember(BaseModel):
    """One member of the resolved topology: structure (manifest-or-fallback) + presentation."""

    model_config = {"extra": "forbid"}

    origin: str
    # structural (manifest if present, else the workspace record):
    domain_role: Optional[str] = None      # source | build | standalone (manifest role), if declared
    namespace: Optional[str] = None        # the ADR prefix, if declared
    locator: Optional[str] = None          # where the member lives, if declared
    structure_evidence: str = "record"     # "declared" when from the manifest, else "record"
    # presentation (always from the workspace record):
    role: str = "spec"                     # the badge role (docs|spec|code|intent)
    title: Optional[str] = None
    description: Optional[str] = None


class ResolvedTopology(BaseModel):
    """The resolved member topology + whether a declared manifest backed it."""

    model_config = {"extra": "forbid"}

    members: list[ResolvedMember]
    declared: bool = False


def resolve_topology(manifest: WorkspaceManifest, domain_manifest=None) -> ResolvedTopology:
    """Combine the workspace record (presentation + fallback) with an optional declared
    `.spec-arch-domain.yml` (structural source of truth). Pure + deterministic.

    Matching: a domain member is bound to a workspace member when their identifiers agree
    (`name`/`namespace`/`locator-stem` vs `origin`, case-insensitive). The workspace member
    order is preserved (presentation owns ordering)."""
    dmembers = list(domain_manifest.members) if domain_manifest is not None else []

    def _match(origin: str):
        o = origin.lower()
        for dm in dmembers:
            stem = Path(dm.locator).name.lower() if dm.locator else ""
            if o in {dm.name.lower(), dm.namespace.lower(), stem}:
                return dm
        return None

    resolved: list[ResolvedMember] = []
    for m in manifest.members:
        dm = _match(m.origin)
        if dm is not None:
            resolved.append(ResolvedMember(
                origin=m.origin,
                domain_role=dm.role, namespace=dm.namespace, locator=dm.locator,
                structure_evidence=LinkEvidenceKind.DECLARED.value,
                role=m.role, title=m.title, description=m.description))
        else:
            resolved.append(ResolvedMember(
                origin=m.origin,
                structure_evidence="record",
                role=m.role, title=m.title, description=m.description))
    return ResolvedTopology(members=resolved, declared=bool(dmembers))

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


def build_site(manifest: WorkspaceManifest, doc_models: dict, corpora: dict | None = None,
               link_graph: LinkGraph | None = None, theme: dict | None = None) -> dict:
    """Pure: manifest + per-origin DocumentModels (+ corpora, + optional verified LinkGraph) →
    {filename: html}.

    Drill-to-source (spec 003): every member's cited source files are rendered as bundled,
    beautified pages under `sources/<origin>/`, and citation chips drill into the OWNING repo's
    source content across the whole workspace (`build_workspace_source_resolver`). A LinkGraph
    still adds the verified atlas.html and acts as a cross-repo PAGE-link fallback. Members
    without a DocumentModel are omitted — a half-built portal renders honestly."""
    merged_theme = {**(manifest.theme or {}), **(theme or {})}
    corpora = corpora or {}
    rendered = [m for m in manifest.members if doc_models.get(m.origin) is not None]

    # primary: a citation drills to the owning repo's bundled source content (any related repo)
    src_corpora = {m.origin: corpora[m.origin] for m in rendered if m.origin in corpora}
    source_resolver = render_sources.build_workspace_source_resolver(src_corpora) if src_corpora else None
    # fallback: a verified cross-repo edge → the target member's page (atlas navigation)
    src_to_page: dict[str, str] = {}
    if link_graph:
        for e in link_graph.edges:
            src_to_page.setdefault(e.src.locator, _page_filename(e.dst.origin))
    page_resolver = (lambda ref: src_to_page.get(ref.locator)) if src_to_page else None
    resolve = render_sources.compose_resolvers(source_resolver, page_resolver)

    site: dict[str, str] = {}
    for m in rendered:
        dm = doc_models[m.origin]
        site[_page_filename(m.origin)] = render_mod.render(dm, merged_theme, resolve=resolve)
        corpus = corpora.get(m.origin)
        if corpus is not None:
            pages = render_sources.render_source_pages(
                corpus, merged_theme, back_href="../../" + _page_filename(m.origin),
                project=dm.title or corpus.project_name)
            for name, html in pages.items():
                site[f"sources/{m.origin}/{name}"] = html
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
    skipped: list[str] = []
    for m in manifest.members:
        src = Path(base) / m.path
        if not src.exists():
            if m.optional:
                skipped.append(m.origin)
                lines.append(f"   [-] {m.origin:14} (optional · source not found) — skipped")
                continue
            raise SystemExit(f"synthesize_atlas: member {m.origin!r} source not found: {src} "
                             '(set "optional": true to skip a not-checked-out repo).')
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

    # Declared topology (spec 004 US2): when the workspace base publishes a `.spec-arch-domain.yml`
    # it is the structural source of truth (members/roles/namespaces/locators), validated against
    # the vendored schema and graded `declared`; a malformed manifest is reported and we fall back
    # to the workspace record. The workspace record is always the presentation overlay + the
    # topology fallback. An ungoverned project has no manifest → resolves to its record unchanged.
    domain = gov_config.read_domain_manifest(base)
    if isinstance(domain, gov_config.ManifestError):
        print(f"synthesize_atlas: declared topology invalid ({domain.message}) — falling back "
              "to the workspace record.", file=sys.stderr)
        domain = None
    topology = resolve_topology(manifest, domain)
    (work / "topology.json").write_text(topology.model_dump_json(indent=2), encoding="utf-8")
    if topology.declared:
        n_dec = sum(1 for rm in topology.members if rm.structure_evidence == "declared")
        print(f"synthesize_atlas: declared topology from .spec-arch-domain.yml — "
              f"{n_dec} member(s) graded `declared` (structural source of truth).")

    # Per-member ADR namespace (spec 004) — used to qualify bare ADR-NNN ids for citation
    # discovery. The DECLARED manifest namespace wins on this structural field; otherwise the
    # repo's own `.spec-arch-governance.yml` (searched from the member source path up to the
    # workspace base) supplies it. Absent → member read as ungoverned (bare ids stay repo-local;
    # no behaviour change for an ungoverned project).
    declared_ns = {rm.origin: rm.namespace for rm in topology.members if rm.structure_evidence == "declared"}
    namespaces: dict[str, str | None] = {}
    for m in manifest.members:
        if m.origin in skipped:
            continue
        if declared_ns.get(m.origin):
            namespaces[m.origin] = declared_ns[m.origin]
            continue
        cfg = gov_config.find_repo_config((Path(base) / m.path), ceiling=base)
        namespaces[m.origin] = cfg.namespace if cfg else None

    # cross-repo traceability graph (declared + deterministic shared-identifier + cites edges);
    # the in-session agent may add evidence-gated prose edges before the finish step (spec 002 Phase D).
    link_graph = discover_links.build_link_graph(manifest, corpora, namespaces=namespaces)
    (work / "link_graph.json").write_text(link_graph.model_dump_json(indent=2), encoding="utf-8")
    print(f"synthesize_atlas: link_graph.json — {len(link_graph.edges)} cross-repo edge(s) "
          "(declared + shared-identifier; prose edges added by the agent).")

    active = [m for m in manifest.members if m.origin not in skipped]
    missing = [m.origin for m in active if m.origin not in ready]

    # ── scaffold path: some member still needs its IR ──────────────────────
    if missing or not args.out:
        print(ATLAS_HAND_OFF.format(n=len(manifest.members), work=work, members="\n".join(lines) + "\n"))
        if args.out and missing:
            print(f"synthesize_atlas: --out given but {len(missing)} member(s) lack document_model.json: "
                  f"{', '.join(missing)} — produce them (brief above), then re-run.", file=sys.stderr)
        return 0

    # ── finish path: fail-closed link gate, then render pages + atlas + index ──
    corpus_paths = [str(work / _slug(m.origin) / "corpus.json") for m in active]
    vrc = verify_links.main([str(work / "link_graph.json"), *corpus_paths])
    if vrc != 0:
        print("synthesize_atlas: LINK VERIFY FAILED (fail-closed) — fix the flagged edges, do not bypass.",
              file=sys.stderr)
        return vrc
    active_manifest = manifest.model_copy(update={"members": active})
    site = build_site(active_manifest, ready, corpora, link_graph, theme)
    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    for fn, html_out in site.items():
        dest = outdir / fn
        dest.parent.mkdir(parents=True, exist_ok=True)   # nested sources/<origin>/ dirs
        dest.write_text(html_out, encoding="utf-8")
    n_src = sum(1 for fn in site if fn.startswith("sources/"))
    print(f"synthesize_atlas: ✓ portal written to {outdir} ({len(site) - n_src} pages + {n_src} source page(s); "
          "every citation drills into sources/)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
