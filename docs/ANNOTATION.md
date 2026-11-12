# Annotation engines

## Existing annotations

Biopython reads the sequence and feature tables. AuraConstruct keeps feature types, qualifiers, ordered location segments, strands and source names. `source` features are omitted from the drawing. Label preference is `label`, `gene`, `standard_name`, `product`, `note`, then feature type.

Glyph-role priority is explicit saved-project role, feature type, regulatory class, Sequence Ontology qualifier, label heuristic, then Unspecified. Label heuristics are illustration hints and remain visibly labeled. No novel CDSs or interactions are inferred.

## Exact reference matching

Choose **Match reference parts** and provide a local FASTA, GenBank, SnapGene or EMBL library. FASTA records act as individual parts. For annotated reference files, individual annotated features act as reference parts. Both strands are searched. Circular queries also search across the sequence origin.

Only unambiguous A/C/G/T reference sequences of at least 12 bases are matched. Matches require 100% sequence identity across the entire reference feature. Repeated matches remain separate. This method is intentionally incomplete for diverged sequences. It is useful for trusted local construct-part libraries, not a general functional annotation engine.

Matches append with source `exact-reference:<filename>` and never overwrite imported features. A sequence match supports identity to the supplied reference; it does not verify function in the current construct.

## pLannotate

Follow the [official installation instructions](https://github.com/barricklab/pLannotate). A typical setup using one conda environment is:

```bash
conda create -n auraconstruct -c conda-forge -c bioconda python=3.11 plannotate
conda activate auraconstruct
plannotate setupdb
pip install -e /path/to/auraconstruct
auraconstruct serve
```

Check `plannotate batch --help` and database readiness in that environment. Dependencies and database downloads belong to pLannotate. AuraConstruct does not install or silently download those databases.

The adapter writes one temporary FASTA, invokes `plannotate batch -i INPUT -o OUTPUT -f annotated`, adds `--linear` for linear DNA, and reads its annotated GenBank output. It requires explicit linear/circular topology. Temporary files are deleted after the operation. The default timeout is 300 seconds. All processing occurs on the machine running the app.

The input and output sequence must match exactly before features are merged. Predictions append with source `pLannotate-prediction`. Imported features remain. Output naming and invocation follow the documented pLannotate CLI. A unit test simulates the executable's output and checks the merge. A live database run has not been verified in this release's development environment.

## Interpretation

Imported annotations may themselves be wrong. Exact matches and pLannotate calls produce sequence-based assignments. User edits are manual decisions. None is an experimentally validated function, expression result, or binding measurement merely because a figure displays it.
