"""Read common sequence formats without dropping location or qualifier data."""
from __future__ import annotations

import gzip
import io
from pathlib import Path
import warnings

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqFeature import CompoundLocation, ExactPosition, SeqFeature, SimpleLocation
from Bio.SeqRecord import SeqRecord

from .model import Construct, Feature, ROLES, infer_role, validate

FORMATS = {".gb": "genbank", ".gbk": "genbank", ".genbank": "genbank",
           ".dna": "snapgene", ".fa": "fasta", ".fas": "fasta", ".fasta": "fasta",
           ".fna": "fasta", ".embl": "embl", ".txt": "raw", ".seq": "raw"}


def read_bytes(data: bytes, filename: str, fmt: str | None = None) -> list[Construct]:
    if filename.lower().endswith(".gz"):
        # Limit decompression as well as uploaded bytes.
        with gzip.GzipFile(fileobj=io.BytesIO(data)) as handle:
            data = handle.read(20_000_001)
        filename = filename[:-3]
    if len(data) > 20_000_000:
        raise ValueError("Input exceeds 20 MB after decompression. Split it into smaller files.")
    if not data:
        raise ValueError("The sequence file is empty.")
    fmt = fmt or FORMATS.get(Path(filename).suffix.lower())
    if data[1:9] == b"SnapGene":
        fmt = "snapgene"
    elif data.lstrip().startswith(b"LOCUS"):
        fmt = "genbank"
    elif data.lstrip().startswith(b">"):
        fmt = "fasta"
    elif data.startswith(b"ID "):
        fmt = "embl"
    fmt = fmt or "raw"
    if fmt == "raw":
        text = "".join(data.decode("utf-8-sig").split()).upper()
        records = [SeqRecord(Seq(text), id=Path(filename).stem, name=Path(filename).stem)]
        parse_warnings = []
    else:
        handle = io.BytesIO(data) if fmt == "snapgene" else io.StringIO(data.decode("utf-8-sig"))
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            records = list(SeqIO.parse(handle, fmt))
        parse_warnings = list(dict.fromkeys(str(w.message) for w in caught))
    if not records:
        raise ValueError(f"No sequence records found in {filename}.")
    return [from_record(r, filename, fmt, parse_warnings, i) for i, r in enumerate(records)]


def from_record(record, filename, fmt, parse_warnings=None, index=0):
    fs, notices = [], list(parse_warnings or [])
    for i, f in enumerate(record.features):
        if f.type == "source":
            continue
        if f.location is None:
            notices.append(f"Skipped feature {i + 1}: no usable location.")
            continue
        q = {str(k): [str(vv) for vv in (v if isinstance(v, list) else [v])]
             for k, v in f.qualifiers.items()}
        label = next((q[k][0] for k in ("label", "gene", "standard_name", "product", "note")
                      if q.get(k)), f.type)
        role, role_source = infer_role(f.type, q, label)
        if q.get("auraconstruct_role", [None])[0] in ROLES:
            role, role_source = q["auraconstruct_role"][0], "saved-project"
        parts = list(f.location.parts)
        fuzzy = any(not isinstance(p.start, ExactPosition) or not isinstance(p.end, ExactPosition)
                    for p in parts)
        fs.append(Feature(f"f{i + 1}", label[:240], f.type, role,
                          [[int(p.start), int(p.end)] for p in parts],
                          f.location.strand or 0, qualifiers=q, role_source=role_source, fuzzy=fuzzy,
                          source=q.get("auraconstruct_source", ["imported"])[0],
                          module=q.get("auraconstruct_module", [""])[0],
                          segment_strands=[p.strand or 0 for p in parts],
                          caption=q.get("ac_caption", [""])[0],
                          caption_source=q.get("ac_caption_source", ["user-caption"])[0]))
    if not fs:
        notices.append("No annotations found. Use a reference library, pLannotate, or add features manually.")
    if any(f.role_source == "label-heuristic" for f in fs):
        notices.append("Some glyph roles come from label heuristics. Review them in the feature table.")
    if any(f.fuzzy for f in fs):
        notices.append("Fuzzy feature boundaries use their integer bounds for drawing. Original locations remain in qualifiers/export metadata.")
    for f, original in zip(fs, [x for x in record.features if x.type != "source" and x.location is not None]):
        f.qualifiers.setdefault("ac_original_location", [str(original.location)])
    name = next((s for s in [record.name, record.id] if s and not s.startswith("<unknown")), Path(filename).stem)
    c = Construct(f"record-{index + 1}", name,
                  str(record.seq).upper(), record.annotations.get("topology", "unknown"),
                  fs, Path(filename).name, fmt, notices)
    description=record.description if record.description not in (".","<unknown description>",name) else ""
    if not description:
        import re
        match=re.search(r"Description:\s*(.*?)(?:YTK Part Type:|Antibiotic Resistance:|$)",str(record.annotations.get("comment","")),re.S)
        description=" ".join(match.group(1).split()) if match else ""
    c.description=description[:300]
    return validate(c)


def to_genbank(c: Construct) -> bytes:
    validate(c)
    r = SeqRecord(Seq(c.sequence), id=c.name.replace(" ", "_")[:64],
                  name=c.name.replace(" ", "_")[:64], description=c.description or "AuraConstruct annotated sequence")
    r.annotations = {"molecule_type": "DNA"}
    if c.topology != "unknown":
        r.annotations["topology"] = c.topology
    for f in c.features:
        strands = f.segment_strands or [f.strand]*len(f.segments)
        locations = [SimpleLocation(a, b, strand=s or None) for (a,b),s in zip(f.segments,strands)]
        loc = locations[0] if len(locations) == 1 else CompoundLocation(locations)
        q = dict(f.qualifiers)
        q.update(label=[f.label], auraconstruct_role=[f.role], auraconstruct_source=[f.source],
                 auraconstruct_module=[f.module], ac_caption=[f.caption],
                 ac_caption_source=[f.caption_source])
        r.features.append(SeqFeature(loc, type=f.type, qualifiers=q))
    output = io.StringIO()
    SeqIO.write(r, output, "genbank")
    return output.getvalue().encode()


def from_dict(d: dict) -> Construct:
    if not isinstance(d, dict):
        raise ValueError("A construct must be a JSON object.")
    fs = [Feature(**{k: v for k, v in f.items() if k in Feature.__dataclass_fields__})
          for f in d.get("features", [])]
    c = Construct(**{k: d[k] for k in Construct.__dataclass_fields__ if k in d and k != "features"}, features=fs)
    return validate(c)
