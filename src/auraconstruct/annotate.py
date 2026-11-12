"""Two explicit annotation routes: exact local references and optional pLannotate."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import shutil
import subprocess
import tempfile

from Bio.Seq import Seq
from Bio import SeqIO

from .model import Feature, infer_role, validate
from .sequence_io import read_bytes


def exact_annotate(construct, reference_bytes: bytes, reference_name: str):
    """Exact DNA matches only. A library is user supplied, never a hidden catalog."""
    c = deepcopy(construct)
    refs = read_bytes(reference_bytes, reference_name)
    n = c.length
    target = c.sequence + (c.sequence if c.topology == "circular" else "")
    existing = {(tuple(map(tuple, f.segments)), f.strand, f.label) for f in c.features}
    for ref in refs:
        candidates = [(ref.name, ref.sequence, "misc_feature", {})] if not ref.features else []
        for f in ref.features:
            # Biopython extraction respects the biological order of join segments.
            strands = f.segment_strands or [f.strand]*len(f.segments)
            seq = "".join(ref.sequence[a:b] if strand != -1 else str(Seq(ref.sequence[a:b]).reverse_complement())
                          for (a, b),strand in zip(f.segments,strands))
            candidates.append((f.label, seq, f.type, f.qualifiers))
        for label, seq, kind, q in candidates:
            if len(seq) < 12 or len(seq) > n or any(x not in "ACGT" for x in seq):
                continue
            reverse = str(Seq(seq).reverse_complement())
            variants = [(1, seq)] if reverse == seq else [(1, seq), (-1, reverse)]
            for strand, query in variants:
                start = target.find(query)
                while 0 <= start < n:
                    end = start + len(query)
                    segments = [[start, end]] if end <= n else [[start, n], [0, end - n]]
                    if strand == -1 and len(segments) > 1:
                        segments.reverse()
                    key = (tuple(map(tuple, segments)), strand, label)
                    if key not in existing:
                        role, role_source = infer_role(kind, q, label)
                        f = Feature(f"exact-{len(c.features) + 1}", label, kind, role, segments, strand,
                                    source=f"exact-reference:{Path(reference_name).name}", role_source=role_source,
                                    qualifiers={**q, "note": ["Exact sequence match to user reference; function unverified."]})
                        c.features.append(f)
                        existing.add(key)
                    if len(c.features) > 5000:
                        raise ValueError("Reference produced more than 5,000 features. Use a more specific library.")
                    start = target.find(query, start + 1)
    c.warnings = [w for w in c.warnings if not w.startswith("No annotations found")]
    c.warnings.append("Reference annotations are exact sequence matches, not experimentally verified functions.")
    return validate(c)


def plannotate_available():
    return shutil.which("plannotate") is not None


def plannotate(construct, timeout=300):
    executable = shutil.which("plannotate")
    if not executable:
        raise ValueError("pLannotate is not installed. See docs/ANNOTATION.md for its separate environment and database setup.")
    c = deepcopy(construct)
    if c.topology == "unknown":
        raise ValueError("Set linear or circular topology before running pLannotate.")
    with tempfile.TemporaryDirectory(prefix="auraconstruct-") as tmp:
        source = Path(tmp) / "input.fa"
        source.write_text(f">construct\n{c.sequence}\n")
        args = [executable, "batch", "-i", str(source), "-o", tmp, "-f", "annotated"]
        if c.topology == "linear":
            args.append("--linear")
        try:
            result = subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)
        except subprocess.TimeoutExpired as exc:
            raise ValueError(f"pLannotate exceeded {timeout} seconds.") from exc
        if result.returncode:
            raise ValueError(f"pLannotate failed: {(result.stderr or result.stdout)[-2000:]}")
        outputs = list(Path(tmp).glob("annotated*.gb*"))
        if len(outputs) != 1:
            raise ValueError("pLannotate did not produce exactly one annotated GenBank file.")
        predicted = read_bytes(outputs[0].read_bytes(), outputs[0].name)[0]
        if predicted.sequence != c.sequence:
            raise ValueError("pLannotate changed the sequence. Results were not merged.")
        existing = {(f.label, tuple(map(tuple, f.segments)), f.strand) for f in c.features}
        for f in predicted.features:
            if (f.label, tuple(map(tuple, f.segments)), f.strand) in existing:
                continue
            f.id = f"plann-{len(c.features) + 1}"
            f.source = "pLannotate-prediction"
            c.features.append(f)
        c.warnings.append("pLannotate annotations are sequence-similarity predictions. Review boundaries and function.")
    return validate(c)
