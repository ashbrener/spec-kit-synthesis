"""IR schemas for spec-kit-synthesis — the contracts between phases.

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


# ───────────────────────── compose output (the document) ───────────────────

class BlockType(str, Enum):
    PROSE = "prose"
    TABLE = "table"
    CALLOUT = "callout"
    DIAGRAM = "diagram"


class CalloutKind(str, Enum):
    """The three callout types that map to what synthesis must surface (DESIGN §1.6)."""

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
    layout: Literal["pipeline", "mapping", "ladder", "flow", "panel"] = "pipeline"
    nodes: list[DiagramNode] = Field(default_factory=list)
    edges: list[DiagramEdge] = Field(default_factory=list)


class Block(BaseModel):
    """One rendered unit, tagged with its reading altitude (DESIGN §1.7, §3 compose)."""

    model_config = {"extra": "forbid"}

    type: BlockType
    altitude: Altitude = Altitude.FUNCTIONAL
    # Exactly one payload is set, matching `type`:
    prose: Optional[str] = None
    table: Optional[list[list[str]]] = None
    callout_kind: Optional[CalloutKind] = None
    callout_tag: Optional[str] = None
    diagram: Optional[DiagramGraph] = None
    claim_ids: list[str] = Field(default_factory=list, description="Claims this block rests on; the verify gate resolves them.")
    source_refs: list[SourceRef] = Field(default_factory=list, description="Resolved citations for the Layer-2 drill-down.")

    @model_validator(mode="after")
    def _payload_matches_type(self) -> "Block":
        present = {
            BlockType.PROSE: self.prose is not None,
            BlockType.TABLE: self.table is not None,
            BlockType.CALLOUT: self.callout_kind is not None,
            BlockType.DIAGRAM: self.diagram is not None,
        }
        if not present[self.type]:
            raise ValueError(f"Block of type {self.type} is missing its payload.")
        return self


class Section(BaseModel):
    """A spine section; every section is two-tiered via its blocks' altitudes (DESIGN §2)."""

    model_config = {"extra": "forbid"}
    id: str
    number: int
    title: str
    subtitle: Optional[str] = None
    blocks: list[Block] = Field(default_factory=list)


class DocumentModel(BaseModel):
    """The full storybook content, pre-render (Phase C output)."""

    model_config = {"extra": "forbid"}

    schema_version: str = SCHEMA_VERSION
    title: str
    lede: Optional[str] = None
    sections: list[Section] = Field(default_factory=list)


__all__ = [
    "SCHEMA_VERSION",
    "SourceType", "SourceRef",
    "Fragment", "FragmentCorpus",
    "Altitude", "Claim", "Decision", "SpecDigest",
    "EvolutionNote", "ArchitectureModel",
    "BlockType", "CalloutKind",
    "DiagramNode", "DiagramEdge", "DiagramGraph",
    "Block", "Section", "DocumentModel",
]
