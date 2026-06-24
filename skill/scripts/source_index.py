"""source_index.py — human-readable source titles + the hierarchical source index (spec 006).

Deterministic, from corpus structure only (no reasoning). Two products:
  * `build_title_map` — locator -> a human title + artifact kind + repo, so citations render as
    "Authentication System — Contract (backend)" rather than "spec-001 · auth-contract.md" (FR-010);
  * `build_tree` / `render_index_tree` — a navigable tree repo -> feature(human title) -> artifacts,
    replacing the edge-list graph map (FR-011) — added for US3.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pydantic import BaseModel  # noqa: E402
from schema import FragmentCorpus  # noqa: E402

_H1 = re.compile(r"^\s{0,3}#\s+(.+?)\s*#*\s*$", re.MULTILINE)
_FRONTMATTER_TITLE = re.compile(r"^\s*title:\s*[\"']?(.+?)[\"']?\s*$", re.MULTILINE)
# A spec-fragment kind that most authoritatively carries the feature's title.
_TITLE_KINDS = ("spec", "design-doc", "adr", "plan")


class SourceTitle(BaseModel):
    model_config = {"extra": "forbid"}
    title: str
    artifact_kind: str
    repo: str
    is_fallback: bool = False


def _humanize(feature_key: str | None, locator: str) -> str:
    """A readable fallback when no heading is found: title-case the feature slug (sans number)."""
    stem = feature_key or locator.split("::", 1)[-1].split("/", 1)[0]
    stem = re.sub(r"^\d+[-_]?", "", stem)              # drop a leading NNN-
    words = re.split(r"[-_\s]+", stem.strip())
    return " ".join(w.capitalize() for w in words if w) or (feature_key or "Untitled")


def _extract_title(text: str) -> str | None:
    m = _FRONTMATTER_TITLE.search(text[:400]) if text.lstrip().startswith("---") else None
    if m:
        return m.group(1).strip()
    m = _H1.search(text)
    return m.group(1).strip() if m else None


def build_title_map(corpora: dict[str, FragmentCorpus]) -> dict[str, SourceTitle]:
    """locator -> SourceTitle. A feature's title is taken from its most authoritative fragment's
    heading and applied to every fragment of that feature; absent any heading, a humanized slug
    fallback is used (marked)."""
    # per (origin, feature_key): the best human title found
    feat_title: dict[tuple[str, str | None], str] = {}
    for origin in sorted(corpora):
        # prefer title-bearing kinds, in order, then any fragment
        frags = corpora[origin].fragments
        ordered = sorted(
            frags,
            key=lambda f: (_TITLE_KINDS.index(f.kind) if f.kind in _TITLE_KINDS else len(_TITLE_KINDS),
                           f.id),
        )
        for f in ordered:
            key = (origin, f.feature_key)
            if key in feat_title:
                continue
            t = _extract_title(f.text)
            if t:
                feat_title[key] = t

    out: dict[str, SourceTitle] = {}
    for origin in sorted(corpora):
        for f in corpora[origin].fragments:
            key = (origin, f.feature_key)
            title = feat_title.get(key)
            fallback = title is None
            if fallback:
                title = _humanize(f.feature_key, f.id)
            out[f.id] = SourceTitle(title=title, artifact_kind=f.kind, repo=origin, is_fallback=fallback)
    return out


# ───────────────────────── hierarchical source index (US3) ──────────────────

class SourceIndexNode(BaseModel):
    model_config = {"extra": "forbid"}
    kind: str                                  # "repo" | "feature" | "artifact"
    label: str
    href: str | None = None                    # drill-to-source link (artifact nodes)
    children: list["SourceIndexNode"] = []


def build_tree(corpora: dict[str, FragmentCorpus]) -> SourceIndexNode:
    """A deterministic tree: root → repo → feature(human title) → artifact(file), each artifact
    linking to its drill-to-source page. From corpus structure only (no reasoning) — replaces the
    edge-list map (FR-011)."""
    from render_sources import source_page_name  # local import avoids a module cycle at import time

    titles = build_title_map(corpora)
    repos: list[SourceIndexNode] = []
    for origin in sorted(corpora):
        # feature_key -> ordered {file: (kind, representative locator)}
        feats: dict[str | None, dict[str, tuple[str, str]]] = {}
        order: list[str | None] = []
        for f in corpora[origin].fragments:
            fk = f.feature_key
            file = f.id.split("::", 1)[-1].split("#", 1)[0]
            if fk not in feats:
                feats[fk] = {}
                order.append(fk)
            feats[fk].setdefault(file, (f.kind, f.id))
        feat_nodes: list[SourceIndexNode] = []
        for fk in order:
            files = feats[fk]
            ftitle = next((titles[loc].title for (_, loc) in files.values() if loc in titles),
                          _humanize(fk, origin))
            arts = [SourceIndexNode(kind="artifact", label=kind,
                                    href=f"sources/{origin}/{source_page_name(loc)}")
                    for file, (kind, loc) in files.items()]
            feat_nodes.append(SourceIndexNode(kind="feature", label=ftitle, children=arts))
        repos.append(SourceIndexNode(kind="repo", label=origin, children=feat_nodes))
    return SourceIndexNode(kind="repo", label="Workspace", children=repos)


def _tree_ul(node: SourceIndexNode) -> str:
    from render import esc  # local import avoids a cycle
    if node.kind == "artifact":
        link = f'<a href="{esc(node.href)}">view &rarr;</a>' if node.href else ""
        return f'<li class="ix-art"><span class="ix-kind">{esc(node.label)}</span> {link}</li>'
    cls = "ix-repo" if node.kind == "repo" else "ix-feat"
    kids = "".join(_tree_ul(c) for c in node.children)
    return f'<li class="{cls}"><span class="ix-label">{esc(node.label)}</span><ul>{kids}</ul></li>'


def render_index_tree(tree: SourceIndexNode, theme: dict | None = None, story_href: str = "index.html") -> str:
    """A standalone, design-system-styled hierarchical index page."""
    from render import DEFAULT_THEME, GLYPH, REPO_URL, build_css, esc
    merged = {**DEFAULT_THEME, **(theme or {})}
    css = build_css(merged) + _INDEX_TREE_CSS
    body = "".join(_tree_ul(r) for r in tree.children)
    return (
        '<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        '<meta name="color-scheme" content="light only">\n'
        f"<title>Source index</title>\n<style>{css}</style>\n</head>\n<body>\n"
        '<div class="grain"></div>\n<div class="wrap">\n'
        '<header class="mast">'
        f'<a href="{esc(story_href)}" class="brand-logo">{GLYPH}<span class="brand-word">Source index</span></a>'
        '<div class="kicker"><span>Source Index</span><span>repo &rsaquo; feature &rsaquo; artifacts</span></div>'
        '<h1 class="title">Source index</h1>'
        '<p class="dek">Every repository, feature, and artifact behind the story — each a click from '
        f'its rendered source. <a href="{esc(story_href)}">&larr; back to the story</a></p>'
        "</header>\n"
        f'<ul class="ixtree">{body}</ul>\n'
        '<footer id="refs"><div class="genline"><span class="gm">&#9679;</span> Generated by '
        f'<a href="{REPO_URL}" target="_blank" rel="noopener noreferrer">spec-kit-atlas</a>.</div></footer>\n'
        "</div>\n</body>\n</html>\n"
    )


_INDEX_TREE_CSS = """
  ul.ixtree{ list-style:none; margin:32px 0; padding:0; }
  ul.ixtree ul{ list-style:none; margin:0 0 0 18px; padding:0; border-left:1px solid var(--line); }
  .ixtree li{ margin:4px 0; padding:2px 0 2px 14px; }
  .ixtree .ix-repo > .ix-label{ font-family:var(--font-display); font-weight:700; font-size:1.25rem; }
  .ixtree .ix-feat > .ix-label{ font-family:var(--font-body); font-weight:600; font-size:1.02rem; }
  .ixtree .ix-kind{ font-family:var(--font-mono); font-size:11px; letter-spacing:.06em; text-transform:uppercase;
    color:#6e5413; background:#efe3c4; border-radius:9px; padding:1px 7px; }
  .ixtree .ix-art a{ font-family:var(--font-mono); font-size:12px; color:var(--gold); text-decoration:none; margin-left:8px; }
"""


__all__ = ["SourceTitle", "build_title_map", "SourceIndexNode", "build_tree", "render_index_tree"]
