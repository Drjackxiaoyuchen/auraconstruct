# SBOL Visual conventions

[SBOL Visual specification](https://sbolstandard.org/visual-specification/) · [official glyph gallery](https://sbolstandard.org/visual-glyphs/)

This release independently implements a subset of sequence-feature glyphs as native paths. It follows the semantics below, with styling and dimensions chosen for presentation readability. It does not implement every rule or glyph in the standard and has not undergone a full conformance audit.

| Illustration role | Visual convention | Imported feature examples |
| --- | --- | --- |
| promoter | Raised, bent directional arrow | `promoter`, `regulatory_class=promoter` |
| rbs | Arch with a flat baseline | `RBS`, `ribosome_binding_site` |
| cds | Directional pentagonal arrow | `CDS` |
| terminator | Raised T | `terminator` |
| origin | Circle centered on backbone | `rep_origin` |
| operator | Open-top U on backbone | `operator`, `regulatory_class=operator` |
| primer | Short directional arrow above backbone | `primer_bind` |
| scar | Two short parallel strokes | Label heuristic or manual assignment |
| recombination | Directional triangle | `misc_recomb` |
| ncrna | Box with a wavy top | `ncRNA`, `tRNA`, `rRNA` |
| polya | `AAA` at the site | `polyA_site`, `polyA_signal` |
| generic | Diamond with question mark | Other or unknown feature types |
| region | Unspecified halfround rectangle | Annotated homology arms, barcodes, tags, linkers and assembly connectors |
| engineered_region | Plain rectangle | Explicit engineered region, SO:0000804 |
| spacer | Circle with X | Explicit inert DNA spacer, SO:0002223 |
| nuclease_site | X atop a DNA stem | Explicit nuclease site annotation |

Reverse-strand directional glyphs rotate 180 degrees about the DNA backbone. Labels remain upright. Strand-unknown directional features carry a small question mark. Joined features appear once in the schematic and as separate interval segments in coordinate mode. Per-segment strands remain in project JSON and GenBank output.

Module brackets encode only user-supplied module names. They are a presentation annotation. They do not assert transcriptional units, functional insulation or regulatory interaction. Likewise, role colors are a styling choice rather than an SBOL semantic requirement.

Internal coordinates use 0-based half-open intervals. Displayed coordinates are 1-based inclusive. Coordinate-view tracks encode exact intervals, while glyphs have minimum/maximum display widths. The schematic is explicitly labeled not to scale.

SBOL Visual graphics and SBOL data exchange are separate concerns. The exported project JSON is an AuraConstruct schema and is not SBOL RDF or JSON-LD.
