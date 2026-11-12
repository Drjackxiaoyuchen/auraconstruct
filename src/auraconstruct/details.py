"""Source-backed annotation text, separate from SBOL glyph meaning.

Subtypes inferred from labels describe those labels and do not establish function,
cleavage coordinates, assembly compatibility, or targeting activity.
"""
import re
from Bio.Seq import Seq


def category(f):
    text=f.label
    if re.search(r"homology|\b[35]['′’]?\s*HA\b",text,re.I):
        return "Homology arm"
    if re.search(r"barcode",text,re.I):return "Barcode"
    if re.fullmatch(r"Con[SLRE]\d*",text,re.I):return "Assembly connector"
    if re.search(r"overhang",text,re.I):return "Annotated overhang"
    if re.search(r"gRNA.*(?:target|spacer)|CRISPR.*target",text,re.I):return "Annotated guide target"
    if re.search(r"gRNA.*scaffold",text,re.I):return "gRNA scaffold"
    if re.search(r"\btRNA\b|^t(?:GCC|CCC)$",text,re.I):return "tRNA annotation"
    if re.search(r"\bNLS\b",text,re.I):return "Nuclear localization tag"
    if re.search(r"(?:BsaI|BsmBI|BbsI|NotI|EcoRI|XhoI|BamHI|HindIII)",text):
        return "Restriction-related annotation"
    if re.search(r"linker",text,re.I):return "Linker region"
    if re.search(r"\btag\b|FLAG|His6|HA.tag",text,re.I):return "Tag annotation"
    if f.role=="generic":return "Unspecified sequence feature"
    return {"promoter":"Promoter", "cds":"Coding sequence", "rbs":"Ribosome entry site",
            "terminator":"Terminator", "origin":"Replication origin", "operator":"Operator",
            "primer":"Primer binding site", "scar":"Assembly scar", "ncrna":"Non-coding RNA",
            "recombination":"Recombination site", "polya":"PolyA site", "region":"Unspecified region",
            "engineered_region":"Engineered region", "spacer":"Inert DNA spacer",
            "nuclease_site":"Nuclease cleavage site"}.get(f.role,f.type)


def summary(f):
    if f.caption:return f.caption,f.caption_source
    for key in ("product","function","note","regulatory_class"):
        values=f.qualifiers.get(key,[])
        for value in values:
            text=" ".join(str(value).split())
            if text and text not in (f.label,f.type,"."):
                return text,f"qualifier:{key}"
    return "",""


def position_text(f):
    strand={1:"+",-1:"−",0:"?"}[f.strand]
    if len(f.segments)==1:
        a,b=f.segments[0];loc=f"{a+1:,}..{b:,}"
    else:loc=f"{len(f.segments)} joined segments"
    return f"{loc} / {f.length:,} bp / strand {strand}" + (" / fuzzy" if f.fuzzy else "")


def short_sequence(c,f):
    if f.length>32:return ""
    if f.segment_strands and len(set(f.segment_strands))>1:return ""
    if f.role!="primer" and not re.search(r"primer|overhang|barcode|target|BsaI|BsmBI|BbsI|NotI|EcoRI|XhoI|BamHI|HindIII",f.label,re.I):
        return ""
    strands=f.segment_strands or [f.strand]*len(f.segments)
    sequence="".join(str(Seq(c.sequence[a:b]).reverse_complement()) if strand==-1 else c.sequence[a:b]
                     for (a,b),strand in zip(f.segments,strands))
    return f"5′ {sequence} 3′" if f.strand else sequence+" (reference strand)"
