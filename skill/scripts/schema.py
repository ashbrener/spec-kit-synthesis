"""IR schemas for spec-kit-atlas — the contracts between phases.

These Pydantic models are the *only* coupling between the in-session agent
(which performs the reasoning of phases A–C) and the deterministic scripts
(adapter, verify, render). Each phase reads one artifact and writes the next:

    spec folders ──adapter──▶ FragmentCorpus
    FragmentCorpus ──agent: extract──▶ [SpecDigest]
    [SpecDigest]   ──agent: reconcile──▶ ArchitectureModel
    ArchitectureModel ──agent: compose──▶ DocumentModel
    DocumentModel  ──verify (fail-closed)──▶ DocumentModel (validated)
    DocumentModel + theme ──render──▶ interactive SVG HTML

Design anchors (DESIGN.md):
  §11.2 #2  provenance is source-TYPED from the first commit
  §1.7      altitude-tagged blocks (functional / technical / provenance)
  §3        ArchitectureModel carries history[] (supersessions) + open_questions[]
  §5        every claim carries source_refs; a claim with no source cannot exist
  §6        diagrams are a declarative graph, rendered deterministically to SVG
  §11.2 #4  stateless: these artifacts are a per-run build IR, never a product model
"""

from __future__ import annotations

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator

SCHEMA_VERSION = "0.1.0"


# ───────────────────────────── provenance ──────────────────────────────────

class SourceType(str, Enum):
    """What KIND of source a reference points at (DESIGN §11.2 #2).

    Only `spec` is produced in Phase 1; `design_doc` and `code` are the
    sequenced Phase 2/3 adapters (DESIGN §11.4). Listing them now means the
    provenance model never needs a redesign to admit them.
    """

    SPEC = "spec"
    DESIGN_DOC = "design_doc"
    ADR = "adr"            # an architecture decision record (so a chip renders as an ADR, not a doc)
    CODE = "code"


class SourceRef(BaseModel):
    """A single, named, typed pointer back to a real source location.

    Rendered as a Layer-2 citation chip, e.g. `spec-004 · data-model.md`.
    `locator` is the machine key the verify gate resolves against the corpus.
    """

    model_config = {"extra": "forbid"}

    type: SourceType
    name: str = Field(..., description="Human label for the citation chip, e.g. 'spec-004 · data-model.md'.")
    locator: str = Field(..., description="Stable key resolvable into the FragmentCorpus, e.g. a fragment id.")
    anchor: Optional[str] = Field(None, description="Optional finer pointer (heading, line range, symbol).")
    origin: Optional[str] = Field(None, description="Workspace-member id when federating repos (portal — spec 002); namespaces the locator. None = single-repo.")


# ───────────────────────────── adapter output ──────────────────────────────

class Fragment(BaseModel):
    """One source-neutral unit of input text + its origin.

    The adapter flattens spec folders into these; the core never sees a
    'spec' — only fragments. This is the source-agnostic seam (DESIGN §11.1).
    """

    model_config = {"extra": "forbid"}

    id: str = Field(..., description="Stable fragment id; the locator a SourceRef resolves to.")
    source: SourceRef = Field(..., description="Where this fragment came from (self-referential locator == id).")
    kind: str = Field(..., description="Adapter-assigned role, e.g. 'spec', 'plan', 'data-model', 'research', 'contract'.")
    feature_key: Optional[str] = Field(None, description="Grouping key (e.g. the feature folder), source-internal; never shown in the narrative.")
    lifecycle: Optional[str] = Field(None, description="Lifecycle/state token when the source carries one (workstate overlay or inferred).")
    text: str = Field(..., description="The raw prose/structured text of this fragment.")


class FragmentCorpus(BaseModel):
    """The complete, source-typed input the core reasons over (adapter output)."""

    model_config = {"extra": "forbid"}

    schema_version: str = SCHEMA_VERSION
    project_name: str = Field(..., description="Display name for the system being documented.")
    fragments: list[Fragment] = Field(default_factory=list)

    def locators(self) -> set[str]:
        return {f.id for f in self.fragments}

    def with_origin(self, origin: str) -> "FragmentCorpus":
        """Return a copy with every fragment id + self-referential locator namespaced by
        ``origin`` (workspace federation — spec 002), the SourceRef.origin stamped, and the
        locator==id invariant preserved. Idempotent. Single-repo runs never call this, so their
        bare locators and unchanged golden files are unaffected (origin stays None)."""
        pref = f"{origin}::"

        def ns(s: str) -> str:
            return s if s.startswith(pref) else pref + s

        frags = [
            f.model_copy(update={
                "id": ns(f.id),
                "source": f.source.model_copy(update={"locator": ns(f.source.locator), "origin": origin}),
            })
            for f in self.fragments
        ]
        return self.model_copy(update={"fragments": frags})


# ───────────────────────── extract output (per source) ─────────────────────

class Altitude(str, Enum):
    """Reading depth a claim belongs to (DESIGN §1.7 progressive disclosure)."""

    FUNCTIONAL = "functional"   # Layer 0 — plain-English, exec-readable
    TECHNICAL = "technical"     # Layer 1 — drill-down detail
    PROVENANCE = "provenance"   # Layer 2 — citations (carried by source_refs)


class Claim(BaseModel):
    """A single asserted fact about the system, with mandatory provenance.

    DESIGN §5.1: a claim with no source_refs cannot exist; therefore a
    sentence resting only on an unsourced claim cannot be written. The verify
    gate enforces this mechanically.
    """

    model_config = {"extra": "forbid"}

    id: str
    text: str
    altitude: Altitude = Altitude.FUNCTIONAL
    source_refs: list[SourceRef] = Field(..., min_length=1, description="≥1 required — faithfulness invariant.")

    @model_validator(mode="after")
    def _require_provenance(self) -> "Claim":
        if not self.source_refs:
            raise ValueError(f"Claim {self.id!r} has no source_refs (faithfulness invariant, DESIGN §5.1).")
        return self


class Decision(BaseModel):
    """A design decision with its rationale and the roads not taken (DESIGN §1.5)."""

    model_config = {"extra": "forbid"}

    id: str
    decision: str
    rationale: Optional[str] = None
    alternatives: list[str] = Field(default_factory=list)
    source_refs: list[SourceRef] = Field(..., min_length=1)


class SpecDigest(BaseModel):
    """Structured extraction from ONE source fragment-group (Phase A output)."""

    model_config = {"extra": "forbid"}

    feature_key: str
    claims: list[Claim] = Field(default_factory=list)
    decisions: list[Decision] = Field(default_factory=list)
    open_questions: list[Claim] = Field(default_factory=list, description="[NEEDS CLARIFICATION]/deferred items → 'Unspecified' material.")


# ───────────────────────── reconcile output (the model) ────────────────────

class EvolutionNote(BaseModel):
    """A resolved supersession: old behaviour demoted to history (DESIGN §3, §1.2).

    Evidence-gated (DESIGN §5.4): superseded_by is set only on real evidence
    (workstate relation, explicit prose, or unambiguous same-concern recency).
    """

    model_config = {"extra": "forbid"}

    id: str
    title: str
    old_state: str = Field(..., description="What the system used to do.")
    new_state: str = Field(..., description="What it does now (also a current claim).")
    evidence: str = Field(..., description="Why we believe this is a supersession, not a contradiction.")
    source_refs: list[SourceRef] = Field(..., min_length=1)


class CoverageStatus(str, Enum):
    """How well an area of the system is backed by spec AND by code (DESIGN §5.8).

    The coverage view's whole point is honesty about a half-specced system:
    naming what is specified-but-unbuilt and built-but-unspecified, rather than
    letting a specs-only doc read as complete.
    """

    SPEC_BACKED = "spec_backed"        # specified AND present in code
    SPECCED_ONLY = "specced_only"      # specified but no code found — specced-but-unbuilt
    IMPLEMENTED_ONLY = "implemented_only"  # code exists but no spec — built-but-unspecced
    UNKNOWN = "unknown"                # cannot determine from the sources at hand


class CoverageItem(BaseModel):
    """One area of the system, classified by intent-vs-reality (DESIGN §5.8 'better').

    Produced only when a code source is present (Phase 2). spec_refs cite the
    specifying fragments; code_refs cite the implementing fragments. The verify
    gate resolves both against the corpus, so a coverage claim is as grounded as
    any other.
    """

    model_config = {"extra": "forbid"}

    area: str = Field(..., description="The component/feature this row is about (display name).")
    status: CoverageStatus
    note: Optional[str] = Field(None, description="One-line justification; required for implemented_only/unknown.")
    spec_refs: list[SourceRef] = Field(default_factory=list, description="Specifying sources (type=spec/design_doc).")
    code_refs: list[SourceRef] = Field(default_factory=list, description="Implementing sources (type=code).")

    @model_validator(mode="after")
    def _refs_match_status(self) -> "CoverageItem":
        if self.status is CoverageStatus.SPEC_BACKED and not (self.spec_refs and self.code_refs):
            raise ValueError(f"CoverageItem {self.area!r} is spec_backed but lacks both spec_refs and code_refs.")
        if self.status is CoverageStatus.SPECCED_ONLY and not self.spec_refs:
            raise ValueError(f"CoverageItem {self.area!r} is specced_only but has no spec_refs.")
        if self.status is CoverageStatus.IMPLEMENTED_ONLY and not self.code_refs:
            raise ValueError(f"CoverageItem {self.area!r} is implemented_only but has no code_refs.")
        return self


class ArchitectureModel(BaseModel):
    """The reconciled, current-state model — the core's reduce output (Phase B).

    This is the 'persisted, diffable build artifact' of DESIGN §3: written to
    disk for review/incrementality, regenerated every run, NEVER authoritative
    and NEVER hand-edited (DESIGN §11.2 #4). It is a compiler IR, not a product
    model.
    """

    model_config = {"extra": "forbid"}

    schema_version: str = SCHEMA_VERSION
    project_name: str
    claims: list[Claim] = Field(default_factory=list, description="Merged, current-state claims (overlaps collapsed).")
    decisions: list[Decision] = Field(default_factory=list)
    history: list[EvolutionNote] = Field(default_factory=list, description="Superseded behaviour, demoted (DESIGN §3).")
    open_questions: list[Claim] = Field(default_factory=list, description="Unresolved/contradictory → 'Unspecified' (DESIGN §5.2/§5.3).")
    section_plan: list[str] = Field(default_factory=list, description="Ordered section ids assigned by reconcile (DESIGN §2 spine + inferred slots).")
    coverage_note: Optional[str] = Field(None, description="Mandatory scope framing (DESIGN §5.8 coverage honesty).")
    coverage: list[CoverageItem] = Field(default_factory=list, description="Intent-vs-reality coverage rows; empty in specs-only (Phase 1) runs, populated when a code source is present (Phase 2).")


# ───────────────────────── compose output (the document) ───────────────────

class BlockType(str, Enum):
    PROSE = "prose"
    TABLE = "table"
    CALLOUT = "callout"
    DIAGRAM = "diagram"
    COVERAGE = "coverage"   # intent-vs-reality matrix (Phase 2; carries CoverageItem rows)


class CalloutKind(str, Enum):
    """The three callout types that map to what atlas must surface (DESIGN §1.6)."""

    DECISION = "decision"      # a choice
    UNSPECIFIED = "unspecified"  # a gap (fail-closed)
    EVOLUTION = "evolution"    # a change over time


class DiagramNode(BaseModel):
    model_config = {"extra": "forbid"}
    id: str
    label: str
    caption: Optional[str] = Field(None, description="Hover-to-explain text.")
    target: Optional[str] = Field(None, description="Optional section id to jump to on click.")
    source_refs: list[SourceRef] = Field(default_factory=list, description="A node exists only if a claim backs it (DESIGN §6).")


class DiagramEdge(BaseModel):
    model_config = {"extra": "forbid"}
    src: str
    dst: str
    label: Optional[str] = None
    emphasis: bool = False


class DiagramGraph(BaseModel):
    """Declarative diagram intent; the renderer lays it out to interactive SVG (DESIGN §6)."""

    model_config = {"extra": "forbid"}
    layout: Literal["pipeline", "mapping", "ladder", "flow", "panel", "hub", "stack", "timeline", "sequence", "erd"] = "pipeline"
    title: Optional[str] = Field(None, description="Optional diagram title, rendered in the display face above the figure (renderer v2).")
    nodes: list[DiagramNode] = Field(default_factory=list)
    edges: list[DiagramEdge] = Field(default_factory=list)


class Block(BaseModel):
    """One rendered unit, tagged with its reading altitude (DESIGN §1.7, §3 compose)."""

    model_config = {"extra": "forbid"}

    type: BlockType
    altitude: Altitude = Altitude.FUNCTIONAL
    # Melded SITE layer (spec 006): which tier/member this block draws from (e.g. "backend",
    # "frontend"); None = the functional/source layer (always visible). The renderer groups
    # TECHNICAL blocks by `tier` into per-tier disclosures.
    tier: Optional[str] = Field(default=None, description="Contributing tier/member origin; None = functional/source layer.")
    build_status: Optional[Literal["built", "partial", "planned"]] = Field(default=None, description="Per-block build grade; 'planned' renders faded. None inherits the tier/section grade.")
    # Exactly one payload is set, matching `type`:
    prose: Optional[str] = None
    prose_style: Optional[Literal["lead", "pull"]] = Field(default=None, description="PROSE-only: render as a lead paragraph ('lead') or a pull-quote ('pull').")
    table: Optional[list[list[str]]] = None
    callout_kind: Optional[CalloutKind] = None
    callout_tag: Optional[str] = None
    diagram: Optional[DiagramGraph] = None
    coverage: Optional[list["CoverageItem"]] = Field(default=None, description="Coverage rows for a COVERAGE block (Phase 2).")
    claim_ids: list[str] = Field(default_factory=list, description="Claims this block rests on; the verify gate resolves them.")
    source_refs: list[SourceRef] = Field(default_factory=list, description="Resolved citations for the Layer-2 drill-down.")

    @model_validator(mode="after")
    def _payload_matches_type(self) -> "Block":
        present = {
            BlockType.PROSE: self.prose is not None,
            BlockType.TABLE: self.table is not None,
            BlockType.CALLOUT: self.callout_kind is not None,
            BlockType.DIAGRAM: self.diagram is not None,
            BlockType.COVERAGE: bool(self.coverage),
        }
        if not present[self.type]:
            raise ValueError(f"Block of type {self.type} is missing its payload.")
        if self.prose_style is not None and self.type is not BlockType.PROSE:
            raise ValueError(f"prose_style is only valid on PROSE blocks (got {self.type}).")
        return self


class Section(BaseModel):
    """A spine section; every section is two-tiered via its blocks' altitudes (DESIGN §2)."""

    model_config = {"extra": "forbid"}
    id: str
    number: int
    title: str
    strap: Optional[str] = Field(None, description="Short eyebrow shown beside the section number ('NN — strap'). Renderer v2.")
    subtitle: Optional[str] = None
    build_status: Optional[Literal["built", "partial", "planned"]] = Field(default=None, description="Capability-level build grade (spec 006); shown as a badge by the heading.")
    blocks: list[Block] = Field(default_factory=list)


class MetaPair(BaseModel):
    """One label/value pair for the masthead metadata row (renderer v2, spec 001)."""

    model_config = {"extra": "forbid"}

    label: str
    value: str


class DocumentModel(BaseModel):
    """The full storybook content, pre-render (Phase C output).

    Renderer v2 (spec 001) adds masthead fields — project_name, title_accent,
    kicker, meta — to populate the editorial design-system shell. All are
    optional with graceful fallbacks (project_name falls back to title).
    """

    model_config = {"extra": "forbid"}

    schema_version: str = SCHEMA_VERSION
    title: str
    title_accent: Optional[str] = Field(None, description="Substring of `title` rendered in the masthead accent <em>; cosmetic, optional.")
    lede: Optional[str] = Field(None, description="One-line deck under the title (the masthead dek).")
    project_name: Optional[str] = Field(None, description="Brand wordmark + colophon label; falls back to `title` when unset.")
    kicker: Optional[list[str]] = Field(None, description="Masthead eyebrow spans (≤2): first renders left, second right.")
    meta: list[MetaPair] = Field(default_factory=list, description="Masthead metadata row (label/value pairs).")
    sections: list[Section] = Field(default_factory=list)


# ───────────────────────── workspace (portal — spec 002) ───────────────────

class LinkRel(str, Enum):
    """The typed, directional relationship a cross-repo edge asserts.

    Reconciled to the shared governance vocabulary (vocabulary.json @0.2.0, spec 004): the
    values here MUST equal the contract's `relations` keys (drift-guarded by
    test_contract_conformance.py). The docs↔spec edge has no typed relation in the contract,
    so it maps to the untyped `references` fallback rather than a local dialect."""

    DERIVED_FROM = "derived_from"      # a spec is derived from an upstream spec
    CITES = "cites"                    # a spec/plan cites (is bound by) a decision
    IMPLEMENTS = "implements"          # code implements a spec
    SUPERSEDES = "supersedes"          # one decision supersedes an earlier one
    REFERENCES = "references"          # untyped fallback (incl. docs↔spec)


class LinkEvidenceKind(str, Enum):
    """How a cross-repo edge was established (the §5.4 evidence ladder)."""

    DECLARED = "declared"      # written in the manifest — trusted
    IDENTIFIER = "identifier"  # a shared QUALIFIED identifier (FR-NNN, feature slug) — deterministic
    PROSE = "prose"            # a literal prose reference found in a source fragment — agent-discovered


class LinkEndpoint(BaseModel):
    """One end of a cross-repo edge: a member origin + a locator that resolves in it."""

    model_config = {"extra": "forbid"}

    origin: str
    locator: str = Field(..., description="A fragment locator (origin-namespaced) resolvable in the workspace.")


class DeclaredLink(BaseModel):
    """An operator-authored cross-repo edge in the manifest (trusted; member-relative locators)."""

    model_config = {"extra": "forbid"}

    src_origin: str
    src_locator: str = Field(..., description="Member-relative locator in src_origin (the builder namespaces it).")
    dst_origin: str
    dst_locator: str = Field(..., description="Member-relative locator in dst_origin (the builder namespaces it).")
    rel: LinkRel = LinkRel.REFERENCES


class IngestionSource(BaseModel):
    """One source of fragments contributing to a single member's merged corpus (spec 005).

    A governed member is derived with several of these — e.g. its specs (speckit) and its
    decision records (doc, with `adr_dir` set) — all merged under one member `origin`. When a
    member declares no `sources`, ingestion falls back to its single `adapter`/`path`.
    """

    model_config = {"extra": "forbid"}

    adapter: Literal["speckit", "code", "doc"]
    path: str = Field(..., description="Source path, relative to the workspace base (or absolute).")
    adr_dir: Optional[str] = Field(None, description="For the doc adapter: force ADR classification at/below this dir.")
    include: Optional[str] = Field(None, description="Optional extension override passed to the doc/code adapter.")
    exclude: list[str] = Field(default_factory=list, description="Path-prefixes (with '/') or bare dir names this source skips, beyond the always-skipped hidden/tooling dirs (spec 007).")


class WorkspaceMember(BaseModel):
    """One repo/source federated into a portal workspace (spec 002).

    Each member yields ONE faithful storybook page via the unchanged engine; its
    `origin` namespaces its locators (Phase A) and names its page in the site.
    """

    model_config = {"extra": "forbid"}

    origin: str = Field(..., description="Stable member id; namespaces this member's locators and names its page.")
    path: str = Field(..., description="Path to the member's source, relative to the manifest dir (or absolute).")
    adapter: Literal["speckit", "code", "doc"] = "speckit"
    role: Literal["docs", "spec", "code", "intent"] = "spec"
    title: Optional[str] = Field(None, description="Display title for the index card (defaults to origin).")
    description: Optional[str] = Field(None, description="One-line description for the index card.")
    pin: Optional[str] = Field(None, description="Commit to pin for a reproducible build (recorded; checkout is the operator's job).")
    url: Optional[str] = Field(None, description="Git URL to fetch this member at `pin` when it isn't checked out locally (Phase F).")
    optional: bool = Field(default=False, description="If true, skip this member (with a warning) when its source path is missing, instead of failing the build.")
    base_url: Optional[str] = Field(None, description="Optional published host base for 'view source' links (else self-contained).")
    sources: Optional[list["IngestionSource"]] = Field(
        default=None,
        description="Merged multi-source ingestion (spec 005): when set, each source is adapted and "
        "merged into one origin-stamped corpus, overriding the single `adapter`/`path`. Empty → None.")

    @model_validator(mode="after")
    def _empty_sources_is_none(self) -> "WorkspaceMember":
        # A member can never ingest nothing; an empty list means "use the single-adapter path".
        if self.sources is not None and len(self.sources) == 0:
            object.__setattr__(self, "sources", None)
        return self


class WorkspaceManifest(BaseModel):
    """A portal workspace: the members to federate + presentation (spec 002)."""

    model_config = {"extra": "forbid"}

    schema_version: str = SCHEMA_VERSION
    title: Optional[str] = Field(None, description="Portal / index title.")
    project_name: Optional[str] = Field(None, description="Brand wordmark for the index.")
    members: list[WorkspaceMember] = Field(default_factory=list)
    links: list[DeclaredLink] = Field(default_factory=list, description="Operator-declared cross-repo edges (trusted).")
    theme: dict[str, str] = Field(default_factory=dict, description="Optional theme-token overrides for the whole portal.")


class LinkEdge(BaseModel):
    """A verified-or-candidate cross-repo edge: typed, directional, evidence-bearing (spec 002)."""

    model_config = {"extra": "forbid"}

    src: LinkEndpoint
    dst: LinkEndpoint
    rel: LinkRel
    evidence_kind: LinkEvidenceKind
    evidence: str = Field(..., description="The declaration, the shared identifier, or the literal prose quote.")


class LinkGraph(BaseModel):
    """The cross-repo traceability graph — a per-run, diffable build IR (sibling to ArchitectureModel)."""

    model_config = {"extra": "forbid"}

    schema_version: str = SCHEMA_VERSION
    edges: list[LinkEdge] = Field(default_factory=list)


__all__ = [
    "SCHEMA_VERSION",
    "SourceType", "SourceRef",
    "Fragment", "FragmentCorpus",
    "Altitude", "Claim", "Decision", "SpecDigest",
    "EvolutionNote", "CoverageStatus", "CoverageItem", "ArchitectureModel",
    "BlockType", "CalloutKind",
    "DiagramNode", "DiagramEdge", "DiagramGraph",
    "Block", "Section", "MetaPair", "DocumentModel",
    "IngestionSource", "WorkspaceMember", "WorkspaceManifest",
    "LinkRel", "LinkEvidenceKind", "LinkEndpoint", "DeclaredLink", "LinkEdge", "LinkGraph",
]
