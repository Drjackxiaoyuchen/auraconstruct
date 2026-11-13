# Public toolkit demos

The studio includes six real published plasmid sequence files and seven display presets. Each file is an unmodified member of a publicly downloadable archive. `src/auraconstruct/data/demos/manifest.json` records the source URL, publication DOI, retrieval date, archive member, raw-file SHA-256, normalized-sequence SHA-256 and illustration overrides.

| Demo | Depositor / source | File source |
| --- | --- | --- |
| [pYTK001, Addgene #65108](https://www.addgene.org/65108/) | John Dueber lab; Lee et al., 2015; [10.1021/sb500366v](https://doi.org/10.1021/sb500366v) | Public [MoClo-YTK kit](https://www.addgene.org/kits/moclo-ytk/) GenBank ZIP |
| [pMYT001, Addgene #180654](https://www.addgene.org/180654/) | Tom Ellis lab; Shaw, Khalil and Ellis, 2023; [10.1021/acssynbio.3c00423](https://doi.org/10.1021/acssynbio.3c00423) | Publication supplementary archive, [Figshare record](https://acs.figshare.com/articles/journal_contribution/24512457) / [API metadata](https://api.figshare.com/v2/articles/24512457) |
| [pYSD891, Addgene #253017](https://www.addgene.org/253017/) | Paul Young lab; Juric et al., 2026; [10.1021/acssynbio.6c00085](https://doi.org/10.1021/acssynbio.6c00085) | Publication supplementary archive, [Figshare record](https://acs.figshare.com/articles/journal_contribution/32087000) / [API metadata](https://api.figshare.com/v2/articles/32087000) |
| [pMYT075, Addgene #180728](https://www.addgene.org/180728/) | Shaw, Khalil and Ellis, 2023; Int.1 donor | Same MYT supplementary archive |
| [pMYT095, Addgene #198866](https://www.addgene.org/198866/) | Shaw, Khalil and Ellis, 2023; Cas9/gRNA-processing vector | Same MYT supplementary archive |
| [pYSD328, Addgene #253040](https://www.addgene.org/253040/) | Juric et al., 2026; assembled anti-ALFA-tag nanobody display vector | Same YSD 2.0 supplementary archive |

The demos cover a YTK entry vector with a GFP dropout cassette, the MYT pZ3 regulatory insert, and a YSD 2.0 surface-display scaffold. The pYSD891 GFP region is a cloning dropout cassette; its presence does not demonstrate functional yeast display or completed assembly of a protein of interest.

## Display choices

The stored GenBank files preserve the deposited annotations. Demo presets shorten some labels, name modules, and hide cloning-site detail. All features remain in the model and review table. Hidden features can be shown again. MYT `CamR` and `Z3BS` illustration roles are manually curated as CDS and operator respectively, with `demo-curated` role provenance. This changes the illustration metadata only.

The source citation appears beside the canvas and on exported slides. Full source metadata goes into project JSON and PowerPoint speaker notes. The application loads bundled files and makes no remote sequence requests when a demo is selected.

## Data licenses

These scientific data files are separate from the MIT-licensed application code. The MYT and YSD 2.0 supplementary archives are labeled **CC BY-NC 4.0** in their Figshare metadata. Attribution and the license link are retained in the manifest. The public YTK ZIP does not state a separate data license inside its archive; its source terms apply. Bundling a demonstration file does not relicense it or grant rights to obtain or use the corresponding biological material.

The random-DNA illustration fixture remains available for unit tests. It is no longer the interactive studio demo.

Additional detailed examples: [pMYT075](https://www.addgene.org/180728/) and [pMYT095](https://www.addgene.org/198866/) come from the same MYT supplementary archive, with matching source metadata and checksums. See [detailed annotations](DETAILED_ANNOTATIONS.md).

## Complex construct demo

**pYSD328 is 8,197 bp with 70 imported annotations.** It has an Aga2 signal peptide, anti-ALFA-tag nanobody, linker/HA/TEV regions, 649 stalk, GPI-anchor region, yeast selection and maintenance sequences, and a reverse-strand bacterial selection cassette. The 70 annotations include overlapping CDS subregions, tags, primer binding spans and restriction-related labels; they are not 70 independent genes or transcription units.

Choose **pYSD328 · presentation selection** for 16 selected parts. Both presets stay on one continuous backbone in the default **Single line** view. In **Wrapped → Overview** with coordinates enabled, the selected presentation also fits on one 16:9 slide. Choose **pYSD328 · all 70 annotations** for the full source record; **Wrapped → Detailed** generates nine slides and **Wrapped → Overview** generates five. The same unmodified sequence file backs both presets. Hidden features remain in the table and saved project. The header and table counter show visible versus total features.

The anti-ALFA nanobody illustration role is manually curated as CDS. CEN6 uses an unspecified-region glyph because the source calls it `rep_origin` despite its centromere identity. Tags, source coverage spans, and parent regions containing other features also use unspecified-region glyphs. These choices are recorded as `demo-curated`; original types and coordinates are retained. The parent fusion CDS (905–3487) overlaps its protein subregions. Approximate source coverage annotations are kept as such, not interpreted as 800 bp primer oligonucleotides. BsaI-related four-base labels are not automatically reclassified as DNA cleavage sites.

[Complex editable demonstration](../examples/AuraConstruct_Complex_YSD328.pptx) contains one selected overview and all nine detailed slides. [Overview SVG](../examples/pYSD328_Overview.svg) is a vector preview. The full source labels, coordinates, source citation and curation metadata are retained in the speaker notes/project, even when a display label is shortened.

[Single-line examples](../examples/AuraConstruct_Single_Line_Demos.pptx) include pMYT095 (25 features), selected pYSD328 (16 of 70), and all 70 pYSD328 annotations, each on one backbone. MYT promoter/terminator display labels are shortened and coding regions use Aureka accent colors; original source labels remain in qualifiers and speaker notes.
