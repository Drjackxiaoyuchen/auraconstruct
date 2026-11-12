# Public toolkit demos

The studio includes three real published plasmid sequence files. Each is an unmodified member of a publicly downloadable archive. `src/auraconstruct/data/demos/manifest.json` records the source URL, publication DOI, retrieval date, archive member, raw-file SHA-256, normalized-sequence SHA-256 and illustration overrides.

| Demo | Depositor / source | File source |
| --- | --- | --- |
| [pYTK001, Addgene #65108](https://www.addgene.org/65108/) | John Dueber lab; Lee et al., 2015; [10.1021/sb500366v](https://doi.org/10.1021/sb500366v) | Public [MoClo-YTK kit](https://www.addgene.org/kits/moclo-ytk/) GenBank ZIP |
| [pMYT001, Addgene #180654](https://www.addgene.org/180654/) | Tom Ellis lab; Shaw, Khalil and Ellis, 2023; [10.1021/acssynbio.3c00423](https://doi.org/10.1021/acssynbio.3c00423) | Publication supplementary archive, [Figshare record](https://acs.figshare.com/articles/journal_contribution/24512457) / [API metadata](https://api.figshare.com/v2/articles/24512457) |
| [pYSD891, Addgene #253017](https://www.addgene.org/253017/) | Paul Young lab; Juric et al., 2026; [10.1021/acssynbio.6c00085](https://doi.org/10.1021/acssynbio.6c00085) | Publication supplementary archive, [Figshare record](https://acs.figshare.com/articles/journal_contribution/32087000) / [API metadata](https://api.figshare.com/v2/articles/32087000) |

The demos cover a YTK entry vector with a GFP dropout cassette, the MYT pZ3 regulatory insert, and a YSD 2.0 surface-display scaffold. The pYSD891 GFP region is a cloning dropout cassette; its presence does not demonstrate functional yeast display or completed assembly of a protein of interest.

## Display choices

The stored GenBank files preserve the deposited annotations. Demo presets shorten some labels, name modules, and hide cloning-site detail. All features remain in the model and review table. Hidden features can be shown again. MYT `CamR` and `Z3BS` illustration roles are manually curated as CDS and operator respectively, with `demo-curated` role provenance. This changes the illustration metadata only.

The source citation appears beside the canvas and on exported slides. Full source metadata goes into project JSON and PowerPoint speaker notes. The application loads bundled files and makes no remote sequence requests when a demo is selected.

## Data licenses

These scientific data files are separate from the MIT-licensed application code. The MYT and YSD 2.0 supplementary archives are labeled **CC BY-NC 4.0** in their Figshare metadata. Attribution and the license link are retained in the manifest. The public YTK ZIP does not state a separate data license inside its archive; its source terms apply. Bundling a demonstration file does not relicense it or grant rights to obtain or use the corresponding biological material.

The random-DNA illustration fixture remains available for unit tests. It is no longer the interactive studio demo.
