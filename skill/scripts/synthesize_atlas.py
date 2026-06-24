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
    uv run python skill/scripts/synthesize_atlas.py atlas.workspace.json --work .atlas-portal

    # Finish — once the agent has written each member's IR into the work dir,
    # render every page + the index into a site directory:
    uv run python skill/scripts/synthesize_atlas.py atlas.workspace.json \
        --work .atlas-portal --out site/ [--theme theme.json]

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
import build_status as build_status_mod  # noqa: E402
import cluster  # noqa: E402
import discover_links  # noqa: E402
import gov_config  # noqa: E402
import render as render_mod  # noqa: E402
import render_sources  # noqa: E402
import scaffold  # noqa: E402
import source_index  # noqa: E402
import verify  # noqa: E402
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
# (atlas.workspace.json) supplies PRESENTATION (title/description/theme/order) always, and
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

MAP_HAND_OFF = """\
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


def _adapt_one(adapter_name, src, raw, project, *, adr_dir=None, include=None, exclude=None) -> FragmentCorpus:
    """Run one adapter over one source path → a (not-yet-origin-stamped) FragmentCorpus."""
    adapter = _ADAPTERS.get(adapter_name)
    if adapter is None:
        raise ValueError(f"unknown adapter {adapter_name!r}")
    argv = [str(src), "--out", str(raw), "--project-name", project]
    if adr_dir and adapter_name == "doc":
        argv += ["--adr-dir", str(adr_dir)]
    if include and adapter_name in ("doc", "code"):
        argv += ["--include", str(include)]
    if exclude and adapter_name in ("doc", "code"):
        argv += ["--exclude", ",".join(exclude)]
    rc = adapter.main(argv)
    if rc != 0:
        raise RuntimeError(f"{adapter_name} adapter failed over {src}")
    return FragmentCorpus.model_validate_json(raw.read_text(encoding="utf-8"))


def build_member_corpus(member, base, work) -> FragmentCorpus:
    """Adapt one member's source(s), then origin-stamp the result (Phase A `with_origin`) so its
    locators are globally unique across the workspace — no cross-member collisions.

    Merged multi-source ingestion (spec 005): when `member.sources` is set, each `IngestionSource`
    is adapted over its own path and all fragments are MERGED into one corpus before stamping — so a
    single member can carry, e.g., structure-aware specs (speckit) + decision records (doc). When
    `sources` is None, the legacy single `adapter`/`path` path is used unchanged."""
    base = Path(base)
    work = Path(work)
    if member.sources:
        merged: list = []
        for i, s in enumerate(member.sources):
            src = (base / s.path).resolve()
            if not src.exists():
                continue  # a declared sub-source the repo doesn't actually have — ingest what exists
            raw = work / f"corpus-{_slug(member.origin)}-{i}-{s.adapter}-raw.json"
            sub = _adapt_one(s.adapter, src, raw, member.origin, adr_dir=s.adr_dir,
                             include=s.include, exclude=s.exclude)
            merged.extend(sub.fragments)
        # de-dupe by fragment id (a doc free-form pass and an adr pass may both touch the adr dir)
        seen: set[str] = set()
        unique = []
        for f in merged:
            if f.id in seen:
                continue
            seen.add(f.id)
            unique.append(f)
        corpus = FragmentCorpus(project_name=member.origin, fragments=unique)
        return corpus.with_origin(member.origin)
    src = (base / member.path).resolve()
    raw = work / f"corpus-{_slug(member.origin)}-raw.json"
    corpus = _adapt_one(member.adapter, src, raw, member.origin)
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
  .idx-map{ margin-top: 14px; }
  .idx-map a{ font-family: var(--font-mono); font-size: 13px; color: var(--blue); text-decoration: none; border-bottom: 1px solid rgba(44,74,99,.3); }
"""

_MAP_CSS = """
  .map-edges{ display: flex; flex-direction: column; gap: 10px; margin: 28px 0; }
  .map-edge{ display: flex; flex-wrap: wrap; align-items: baseline; gap: 10px 14px; padding: 12px 16px;
    border: 1px solid var(--line); border-radius: 6px; background: #fbf9f2; font-size: .95rem; }
  .map-edge a{ color: var(--blue); text-decoration: none; border-bottom: 1px solid rgba(44,74,99,.3); font-weight: 600; }
  .map-edge .rel{ font-family: var(--font-mono); font-size: 11px; letter-spacing: .08em; text-transform: uppercase; color: var(--gold); }
  .map-edge .ev{ font-family: var(--font-mono); font-size: 10.5px; color: #7d705a; margin-left: auto; }
  .map-empty{ color: #7d705a; font-style: italic; margin: 28px 0; }
"""


def render_index(manifest: WorkspaceManifest, theme: dict | None = None, has_map: bool = False) -> str:
    """Pure: a WorkspaceManifest → the book-of-books index HTML (one card per member)."""
    merged = {**render_mod.DEFAULT_THEME, **(manifest.theme or {}), **(theme or {})}
    css = build_css(merged) + _INDEX_CSS
    title = manifest.title or manifest.project_name or "Documentation Portal"
    project = manifest.project_name or title
    map_link = ('<p class="idx-map"><a href="map.html">&rarr; Traceability map</a></p>'
                  if has_map else "")
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
        f"{map_link}"
        "</header>\n"
        f'<div class="idx-grid">{cards}</div>\n'
        '<footer id="refs"><div class="genline"><span class="gm">&#9679;</span> Generated by '
        f'<a href="{render_mod.REPO_URL}" target="_blank" rel="noopener noreferrer">spec-kit-atlas</a> '
        "— a portal of faithful, plain-English storybooks. Every claim is traceable to its source.</div></footer>\n"
        "</div>\n</body>\n</html>\n"
    )


def render_map(manifest: WorkspaceManifest, link_graph: LinkGraph, theme: dict | None = None) -> str:
    """Pure: a verified LinkGraph → the traceability atlas page (coverage-honest)."""
    merged = {**render_mod.DEFAULT_THEME, **(manifest.theme or {}), **(theme or {})}
    css = build_css(merged) + _MAP_CSS
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
                '<div class="map-edge">'
                f'<a href="{esc(_page_filename(e.src.origin))}">{esc(sname)}</a>'
                f'<span class="rel">{esc(e.rel.value)}</span>'
                f'<a href="{esc(_page_filename(e.dst.origin))}">{esc(dname)}</a>'
                f'<span class="ev">{esc(e.evidence_kind.value)}: {esc(e.evidence[:48])}</span>'
                "</div>")
        body = '<div class="map-edges">' + "".join(rows) + "</div>"
    else:
        body = ('<p class="map-empty">No cross-repo links discovered yet — add declared links, '
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
        '<div class="kicker"><span>Traceability Map</span><span>intent &rarr; docs &rarr; specs &rarr; code</span></div>'
        '<h1 class="title">Traceability</h1>'
        '<p class="dek">How the readable storybooks connect — every link verified, fail-closed; '
        'a fabricated cross-repo link cannot ship.</p>'
        "</header>\n"
        f"{note}\n{body}\n"
        '<footer id="refs"><div class="genline"><span class="gm">&#9679;</span> '
        '<a href="index.html">&larr; Back to the portal</a> &nbsp;&middot;&nbsp; Generated by '
        f'<a href="{render_mod.REPO_URL}" target="_blank" rel="noopener noreferrer">spec-kit-atlas</a>.</div></footer>\n'
        "</div>\n</body>\n</html>\n"
    )


def build_site(manifest: WorkspaceManifest, doc_models: dict, corpora: dict | None = None,
               link_graph: LinkGraph | None = None, theme: dict | None = None) -> dict:
    """Pure: manifest + per-origin DocumentModels (+ corpora, + optional verified LinkGraph) →
    {filename: html}.

    Drill-to-source (spec 003): every member's cited source files are rendered as bundled,
    beautified pages under `sources/<origin>/`, and citation chips drill into the OWNING repo's
    source content across the whole workspace (`build_workspace_source_resolver`). A LinkGraph
    still adds the verified map.html and acts as a cross-repo PAGE-link fallback. Members
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
        site["map.html"] = render_map(manifest, link_graph, theme)
    site["index.html"] = render_index(manifest, theme, has_map=link_graph is not None)
    return site


# ───────────────────────── melded SITE layer (spec 006) ─────────────────────
# The portal is ONE capability-organized story (not a book-of-books). The agent reasons ONE melded
# pair (architecture_model + document_model) over the MERGED workspace corpus, organized by the
# deterministic capability clusters; the page engine renders it with per-tier disclosures, build-status
# fading, human-titled source tables, and drill-to-source. The old build_site/render_map/render_index
# remain as (unit-tested) library functions but are no longer the portal's output.

MELD_HAND_OFF = """\
─────────────────────────────────────────────────────────────────────────────
 STAGE 0 COMPLETE — adapted the workspace; merged corpus + {n} capability cluster(s) in {work}
{members}
 NEXT: reason ONE MELDED story over the MERGED corpus, organized by capability (NOT per repo):
   {work}/architecture_model.json   (reconcile, across repos)
   {work}/document_model.json        (compose: one Section per capability)

 Use the clusters in {work}/clusters.json as the section spine. Per capability: a plain-English
 FUNCTIONAL narrative (tier unset) from the source layer, then per-tier TECHNICAL blocks tagged
 `tier` (e.g. "backend"/"frontend") + `build_status` (built/partial/planned); be diagram-forward.
 Cite the merged corpus (verify.py gate); every claim drills to its owning repo.

 THEN re-run this command with --out <dir> to verify + render the single melded page + sources.
─────────────────────────────────────────────────────────────────────────────
"""


def build_meld_site(meld_doc: DocumentModel, corpora: dict, title_map: dict,
                    theme: dict | None = None) -> dict:
    """Pure: the melded DocumentModel + per-origin corpora + human-title map → {filename: html}.

    One `index.html` (the melded story) + bundled drill-to-source pages under `sources/<origin>/`.
    Citations drill into the owning repo's source content (any related repo); the title map renders
    human-titled source tables. No per-member storybooks, no edge-list map."""
    merged_theme = theme or {}
    source_resolver = render_sources.build_workspace_source_resolver(corpora) if corpora else None
    site: dict[str, str] = {}
    site["index.html"] = render_mod.render(meld_doc, merged_theme, resolve=source_resolver,
                                           titles=title_map, catalog_href="catalog.html")
    # the hierarchical source index (tree) replaces the edge-list map (spec 006)
    tree = source_index.build_tree(corpora)
    site["catalog.html"] = source_index.render_index_tree(tree, merged_theme, story_href="index.html")
    for origin, corpus in corpora.items():
        pages = render_sources.render_source_pages(
            corpus, merged_theme, back_href="../../index.html", project=origin)
        for name, html_out in pages.items():
            site[f"sources/{origin}/{name}"] = html_out
    return site


# ────────────────────────────────── CLI ─────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Build a documentation portal from a workspace manifest (spec 002), "
                                "or auto-scaffold one from governance contracts on a governed workspace (spec 005).")
    p.add_argument("manifest", nargs="?", default=None,
                   help="Path to atlas.workspace.{json,toml}. Optional on a governed workspace "
                        "(the manifest is derived); when given, it overlays the derived manifest.")
    p.add_argument("--from", dest="from_dir", default=".",
                   help="Where to start authority discovery on a governed workspace (default: cwd).")
    p.add_argument("--authority", default=None,
                   help="Authority repo that owns .spec-arch-domain.yml (overrides discovery).")
    p.add_argument("--work", default=".atlas-portal", help="Working dir for per-member IR (default: .atlas-portal).")
    p.add_argument("--out", default=None, help="Site output directory. Requires every member's document_model.json.")
    p.add_argument("--theme", default=None, help="Optional theme-token JSON applied to the whole portal.")
    args = p.parse_args(argv)

    # ── resolve the manifest: hand-authored, auto-scaffolded, or overlaid (spec 005) ──
    operator = load_manifest(args.manifest) if args.manifest else None
    authority = scaffold.discover_authority(args.authority or args.from_dir)
    if authority is None and operator is not None:
        # a hand-authored manifest may sit at the workspace root — try discovery from there too
        authority = scaffold.discover_authority(Path(args.manifest).resolve().parent)

    derived = None
    if authority is not None:
        domain = gov_config.read_domain_manifest(authority)
        if isinstance(domain, gov_config.ManifestError):
            print(f"synthesize_atlas: domain manifest invalid ({domain.message}) — not scaffolding; "
                  "falling back to the hand-authored manifest.", file=sys.stderr)
            authority = None
        elif domain is None:
            authority = None
        else:
            derived, report = scaffold.derive_manifest(authority, domain)
            print(scaffold.format_report(report))

    manifest = scaffold.overlay_manifest(derived, operator)
    if manifest is None:
        print("synthesize_atlas: ungoverned workspace and no manifest given — nothing to build. "
              "Provide a atlas.workspace.json, or run inside a governed workspace "
              "(a repo reachable to a .spec-arch-domain.yml).", file=sys.stderr)
        return 2

    # base anchors member-path resolution + the declared-topology read: the authority dir when
    # scaffolded (FR-008 — decoupled from any manifest-file location), else the manifest's parent.
    base = authority if authority is not None else Path(args.manifest).resolve().parent
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
    citation_keys: dict[str, dict[str, str]] = {}   # spec 008: per-member slot key overrides
    for m in manifest.members:
        if m.origin in skipped:
            continue
        cfg = gov_config.find_repo_config((Path(base) / m.path), ceiling=base)
        namespaces[m.origin] = declared_ns.get(m.origin) or (cfg.namespace if cfg else None)
        if cfg and cfg.citation_keys:
            citation_keys[m.origin] = cfg.citation_keys

    # cross-repo traceability graph: declared slots (spec 008) + manifest + shared-identifier + cites;
    # the in-session agent may add evidence-gated prose edges before the finish step (spec 002 Phase D).
    link_graph = discover_links.build_link_graph(manifest, corpora, namespaces=namespaces,
                                                 citation_keys=citation_keys)
    (work / "link_graph.json").write_text(link_graph.model_dump_json(indent=2), encoding="utf-8")
    print(f"synthesize_atlas: link_graph.json — {len(link_graph.edges)} cross-repo edge(s) "
          "(declared + shared-identifier; prose edges added by the agent).")

    active = [m for m in manifest.members if m.origin not in skipped]
    active_origins = [m.origin for m in active]
    active_corpora = {o: corpora[o] for o in active_origins}

    # ── meld stage 0: merge corpora, cluster into capabilities, human titles, briefs (spec 006) ──
    merged = FragmentCorpus(
        project_name=(manifest.project_name or manifest.title or "Workspace"),
        fragments=[f for o in active_origins for f in active_corpora[o].fragments],
    )
    (work / "merged_corpus.json").write_text(merged.model_dump_json(indent=2), encoding="utf-8")
    source_origins = {rm.origin for rm in topology.members if rm.domain_role == "source"}
    source_origins |= {m.origin for m in active if m.role == "docs"}
    clusters = cluster.build_clusters(active_corpora, link_graph, source_origins)
    (work / "clusters.json").write_text(clusters.model_dump_json(indent=2), encoding="utf-8")
    title_map = source_index.build_title_map(active_corpora)
    (work / "title_map.json").write_text(
        json.dumps({k: v.model_dump() for k, v in title_map.items()}, indent=2), encoding="utf-8")
    # deterministic per-capability build status (coverage + lifecycle) for the agent's briefs (spec 006 US2)
    statuses = [build_status_mod.grade(c, active_corpora) for c in clusters.clusters]
    (work / "build_status.json").write_text(
        json.dumps([s.model_dump() for s in statuses], indent=2), encoding="utf-8")
    print(f"synthesize_atlas: merged corpus ({len(merged.fragments)} fragments); "
          f"{len(clusters.clusters)} capability cluster(s), {len(clusters.unclustered)} unclustered.")

    # The agent writes ONE melded pair over the merged corpus (verify.py gates it).
    arch_path = work / "architecture_model.json"
    meld_path = work / "document_model.json"
    have_meld = arch_path.exists() and meld_path.exists()

    # ── hand-off path: the melded IR isn't ready (or no --out) ──────────────
    if not have_meld or not args.out:
        print(MELD_HAND_OFF.format(n=len(clusters.clusters), work=work, members="\n".join(lines) + "\n"))
        if args.out and not have_meld:
            print("synthesize_atlas: --out given but the melded architecture_model.json + "
                  "document_model.json are not in the work dir yet — reason them (brief above), then re-run.",
                  file=sys.stderr)
        return 0

    # ── finish path: fail-closed gates (links + meld), then render ONE story + sources ──
    corpus_paths = [str(work / _slug(o) / "corpus.json") for o in active_origins]
    vrc = verify_links.main([str(work / "link_graph.json"), *corpus_paths])
    if vrc != 0:
        print("synthesize_atlas: LINK VERIFY FAILED (fail-closed) — fix the flagged edges, do not bypass.",
              file=sys.stderr)
        return vrc
    vrc = verify.main([str(meld_path), str(arch_path), str(work / "merged_corpus.json")])
    if vrc != 0:
        print("synthesize_atlas: MELD VERIFY FAILED (fail-closed) — fix the melded model, do not bypass.",
              file=sys.stderr)
        return vrc

    meld_doc = DocumentModel.model_validate_json(meld_path.read_text(encoding="utf-8"))
    merged_theme = {**(manifest.theme or {}), **(theme or {})}
    site = build_meld_site(meld_doc, active_corpora, title_map, merged_theme)
    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    for fn, html_out in site.items():
        dest = outdir / fn
        dest.parent.mkdir(parents=True, exist_ok=True)   # nested sources/<origin>/ dirs
        dest.write_text(html_out, encoding="utf-8")
    n_src = sum(1 for fn in site if fn.startswith("sources/"))
    print(f"synthesize_atlas: ✓ melded story written to {outdir} "
          f"({len(site) - n_src} page(s) + {n_src} source page(s); every claim drills to its source).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
