# Tool review and figure direction

Reviewed 12 November 2026. This comparison uses project documentation and primary publications, rather than a claim that every possible existing tool was tested.

| Project | What its documentation establishes | Use in AuraConstruct |
| --- | --- | --- |
| [pLannotate](https://github.com/barricklab/pLannotate) | Engineered-plasmid annotation, local CLI, GenBank output, interactive maps, custom databases | Optional local annotation subprocess; merge predictions with imported features |
| [DNAplotlib, VoigtLab](https://github.com/VoigtLab/dnaplotlib) | Programmable genetic designs, SBOL Visual diagrams, sequence-position views, vector output, design-variant galleries | Main reference for visual grammar and publication figure layout |
| [DNA Features Viewer](https://github.com/Edinburgh-Genome-Foundry/DnaFeaturesViewer) | GenBank/Biopython/GFF visualization, overlapping labels, linear/circular views, PNG/SVG/PDF and optional Bokeh | Reference for readable annotations and location-aware views |
| [gbdraw](https://github.com/satoshikawato/gbdraw) | GenBank/GFF genome maps, linear/circular SVG and other vector formats, browser and CLI workflows | Reference for future larger sequence maps |
| [SBOL Visual](https://sbolstandard.org/visual-glyphs/) | Standard genetic-design glyph vocabulary and associated semantics | Source of glyph meanings and preferred variants |

Native editable PowerPoint modules are the project's focus. This is a feature comparison of the documented outputs reviewed, not proof that no other project has a PPTX exporter.

## What the Voigt references actually show

- [DNAplotlib repository](https://github.com/VoigtLab/dnaplotlib) and [SBOL Visual example gallery](https://github.com/VoigtLab/dnaplotlib/tree/master/gallery/sbol_visual). The latter includes an example gene cassette and the source program that renders it.
- Der BS et al. *DNAplotlib: Programmable Visualization of Genetic Designs and Associated Data*. [DOI: 10.1021/acssynbio.6b00252](https://doi.org/10.1021/acssynbio.6b00252). This is the direct software-paper connection.
- Nielsen AAK et al. *Genetic circuit design automation*. Science (2016). [Primary institutional publication record](https://www.nist.gov/publications/genetic-circuit-design-automation), [DOI: 10.1126/science.aac7341](https://doi.org/10.1126/science.aac7341). Cello separates logic, gate assignment and DNA sequence design.
- Brophy JAN and Voigt CA. *Principles of genetic circuit design*. Nature Methods (2014). [DOI: 10.1038/nmeth.2926](https://doi.org/10.1038/nmeth.2926). A broader reference for visually separating regulator mechanisms, tuning and host context.
- Jones TS et al. *Genetic circuit design automation with Cello 2.0*. Nature Protocols (2022). [Primary paper](https://www.nature.com/articles/s41596-021-00675-2).

The software gallery was directly inspected. Some publisher figure pages were inaccessible during this review. No claim is made that AuraConstruct reproduces the exact figure-production pipeline of any specific paper beyond the documented DNAplotlib examples.

## Applied design decisions

1. Keep sequence-feature diagrams distinct from inferred regulatory networks. Adjacent parts do not justify drawing activation or repression links.
2. Use the preferred, recognizable glyph vocabulary. Label semantics take priority over decoration.
3. Use a single thin backbone and consistent stroke weights. Avoid bevels, shadows and decorative gradients in the scientific figure.
4. Give labels enough room. Paginate dense constructs before making labels too small.
5. Limit palette variation. Colors reinforce part roles, with a colorblind-friendly option and manual overrides.
6. Keep imported, predicted and user-assigned information traceable. Figure styling never establishes experimental evidence.
7. Export every feature as a native named PowerPoint group. Labels remain text boxes; glyphs remain editable paths.

Potential future comparisons include pySBOL3, SBOLCanvas, VisBOL and BioRender workflows. These were not evaluated for feature parity in this first implementation.
