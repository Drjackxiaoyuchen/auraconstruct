# Detailed schematics

Choose **Wrapped → Annotation detail → Detailed** to add sequence-grounded annotation to each SBOL feature group. New sessions and CLI exports default to **Single line**, which keeps one continuous backbone with compact labels and retains complete callouts in the table and PowerPoint notes. **Wrapped → Overview** keeps compact modules across rows.

The detailed view includes:

- Full part labels, with up to two display lines.
- Source positions using 1-based inclusive coordinates, length in bp, strand, and fuzzy-boundary flags.
- Context labels for homology arms, barcodes, assembly connectors, NLSs, linkers/tags, tRNAs, guide RNA scaffolds, and restriction-related annotations.
- Imported `product`, `function`, `note` or `regulatory_class` information when available.
- Editable annotation callouts. A user caption replaces the displayed source note while retaining the original qualifier.
- Short source sequences for annotated primer regions, barcodes, overhangs, targets and restriction-related sites, up to 32 bp. Reverse-strand sequences follow the stored feature orientation. Mixed-strand joins omit this short sequence line.

Detailed schematics use four parts per row and eight per slide. Each part's glyph, label, metadata, note and short sequence remain a single named PowerPoint group of editable objects. Full labels and notes remain in the project, source qualifiers and speaker notes when display text shortens.

## SBOL meaning and extra context

The context label is separate from the glyph's meaning. A homology arm, barcode or NLS does not acquire an invented SBOL icon: it can use the standard **Unspecified halfround rectangle** variant with its biological label. Explicit engineered regions, inert DNA spacers and nuclease sites have their defined SBOL Visual glyphs. A guide RNA scaffold or tRNA uses the non-coding RNA glyph. Label-based role hints remain marked `label-heuristic`.

Source glyph references: [SBOL Visual glyph gallery](https://sbolstandard.org/visual-glyphs/), [SBOL Visual 3.0 specification](https://sbolstandard.org/docs/SBOL-Visual-3.0.pdf), [SBOL Visual ontology](https://synbiodex.github.io/sbol-visual-ontology/sbol-vo.html).

The source type and qualifiers remain available. Short protein-like regions such as NLSs use an unspecified region instead of automatically becoming independent CDSs. Only named source features, explicit ontology terms, or user edits determine the labels and roles.

## Coordinate limits

Positions refer to the loaded sequence record. A donor plasmid's homology-arm coordinates are plasmid coordinates. They do not establish the genomic coordinate, neighboring gene, target alignment, exact cut position, or homology identity. Import an annotated genomic region or provide verified reference context for those claims.

Sequence-order schematics separate overlapping features for readability. They do not imply non-overlapping intervals or independent translation units. Use **Coordinates** to inspect exact segment spans.

A feature named `BsaI` does not by itself identify whether its annotated span is a recognition motif, cut, or assembly overhang. The detailed view reports it as a **restriction-related annotation** and shows only its stored span and short sequence. It does not infer a cleavage offset or design a primer or guide.

## New MYT teaching examples

- **pMYT075**, [Addgene #180728](https://www.addgene.org/180728/): Int.1 integration donor, homology arms, barcodes, annotated assembly primer sites, reporter dropout regions, and bacterial backbone.
- **pMYT095**, [Addgene #198866](https://www.addgene.org/198866/): Cas9 expression region with NLS annotations, gRNA scaffold/tRNA processing region, fluorescent dropout annotations, yeast selection/maintenance and bacterial backbone.

Both are unmodified files from the publicly downloadable [MYT supplementary archive](https://api.figshare.com/v2/articles/24512457). Their illustration presets add explanatory captions with `demo-curated` provenance.

```bash
auraconstruct export plasmid.gb -o detailed.pptx --detail detailed
auraconstruct export plasmid.gb -o overview.pptx --detail overview
python scripts/build_examples.py
```

New project records preserve `caption`, `caption_source` and the construct description. GenBank exports retain captions in `ac_caption` and `ac_caption_source` qualifiers. These are annotation fields, not evidence of experimental validation.
