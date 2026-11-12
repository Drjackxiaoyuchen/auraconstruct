"""A small, explicit intermediate model. Coordinates are 0-based, half-open."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import re

ROLES = {
    "promoter": "SO:0000167", "rbs": "SO:0000139", "cds": "SO:0000316",
    "terminator": "SO:0000141", "origin": "SO:0000296", "operator": "SO:0000057",
    "primer": "SO:0005850", "scar": "SO:0001953", "ncrna": "SO:0000655",
    "recombination": "SO:0000299", "polya": "SO:0000553", "generic": None,
}


@dataclass
class Feature:
    id: str
    label: str
    type: str
    role: str
    segments: list[list[int]]
    strand: int = 0
    source: str = "imported"
    role_source: str = "feature-type"
    qualifiers: dict = field(default_factory=dict)
    color: str | None = None
    visible: bool = True
    module: str = ""
    fuzzy: bool = False
    segment_strands: list[int] = field(default_factory=list)

    @property
    def start(self):
        return min(s[0] for s in self.segments)

    @property
    def end(self):
        return max(s[1] for s in self.segments)

    @property
    def length(self):
        return sum(b - a for a, b in self.segments)


@dataclass
class Construct:
    id: str
    name: str
    sequence: str
    topology: str
    features: list[Feature]
    source_name: str
    source_format: str
    warnings: list[str] = field(default_factory=list)
    provenance: dict = field(default_factory=dict)

    @property
    def length(self):
        return len(self.sequence)

    def to_dict(self):
        d = asdict(self)
        d["length"] = self.length
        d["sha256"] = hashlib.sha256(self.sequence.encode()).hexdigest()
        d["coordinate_system"] = "0-based half-open; segments preserve joins"
        d["schema_version"] = 1
        return d


def infer_role(kind: str, qualifiers: dict, label: str) -> tuple[str, str]:
    """Prefer semantics over label guesses. Every guess is recorded separately."""
    direct = {"CDS": "cds", "promoter": "promoter", "RBS": "rbs",
              "terminator": "terminator", "rep_origin": "origin", "oriT": "generic",
              "protein_bind": "generic", "operator": "operator", "primer_bind": "primer",
              "ncRNA": "ncrna", "tRNA": "ncrna", "rRNA": "ncrna",
              "misc_recomb": "recombination", "polyA_signal": "polya", "polyA_site": "polya"}
    if kind in direct:
        return direct[kind], "feature-type"
    reg = " ".join(qualifiers.get("regulatory_class", [])).lower()
    classes = {"promoter": "promoter", "ribosome_binding_site": "rbs",
               "terminator": "terminator", "operator": "operator",
               "polyA_signal_sequence": "polya"}
    if reg in classes:
        return classes[reg], "regulatory-class"
    terms = " ".join(qualifiers.get("SO", []) + qualifiers.get("SO_terms", [])
                     + qualifiers.get("db_xref", []))
    for role, so in ROLES.items():
        if so and so in terms:
            return role, "sequence-ontology"
    # Label-only assignments affect illustration, never sequence annotation.
    hints = [(r"\bpromoter\b|^p(?:GAL\d|TEF\d|ADH\d|T7|BAD|Lac|Tac)", "promoter"),
             (r"\bterminator\b|\b(?:rrnB|T7Te)\b", "terminator"),
             (r"\b(?:RBS|ribosome binding|ribosome entry)\b", "rbs"),
             (r"\b(?:origin|ColE1|pUC ori|2 micron)\b", "origin"),
             (r"\boperator\b", "operator"), (r"\bprimer\b", "primer"),
             (r"\b(?:assembly scar|scar)\b", "scar")]
    for pattern, role in hints:
        if re.search(pattern, label, re.I):
            return role, "label-heuristic"
    return "generic", "unspecified"


def validate(c: Construct):
    if not c.sequence or not re.fullmatch(r"[ACGTRYSWKMBDHVN]+", c.sequence):
        raise ValueError("Expected a non-empty DNA sequence using IUPAC DNA letters.")
    if c.topology not in ("linear", "circular", "unknown"):
        raise ValueError("Topology must be linear, circular, or unknown.")
    ids = set()
    for f in c.features:
        if f.id in ids:
            raise ValueError("Feature IDs must be unique within a construct.")
        ids.add(f.id)
        if not f.segments or any(not (0 <= a < b <= c.length) for a, b in f.segments):
            raise ValueError(f"Feature {f.label!r} has invalid or out-of-range coordinates.")
        if f.strand not in (-1, 0, 1) or f.role not in ROLES:
            raise ValueError(f"Invalid strand or glyph role for {f.label!r}.")
        if f.segment_strands and (len(f.segment_strands) != len(f.segments) or any(s not in (-1,0,1) for s in f.segment_strands)):
            raise ValueError("Segment strands must match the number of joined segments.")
        if len(f.label) > 240 or len(f.module) > 100:
            raise ValueError("Shorten the feature label (240 characters) or module (100).")
        if f.color and not re.fullmatch(r"#[0-9a-fA-F]{6}", f.color):
            raise ValueError("Colors must be six-digit hex values, for example #377EB8.")
    return c
