# Annotation engines

## Existing annotations

Biopython reads the sequence and feature tables. AuraConstruct keeps feature types, qualifiers, ordered location segments, strands and source names. `source` features are omitted from the drawing. Label preference is `label`, `gene`, `standard_name`, `product`, `note`, then feature type.

Glyph-role priority is explicit saved-project role, feature type, regulatory class, Sequence Ontology qualifier, label heuristic, then Unspecified. Label heuristics are illustration hints and remain visibly labeled. No novel CDSs or interactions are inferred.

## Exact reference matching

Choose **Match reference parts** and provide a local FASTA, GenBank, SnapGene or EMBL library. FASTA records act as individual parts. For annotated reference files, individual annotated features act as reference parts. Both strands are searched. Circular queries also search across the sequence origin.

Only unambiguous A/C/G/T reference sequences of at least 12 bases are matched. Matches require 100% sequence identity across the entire reference feature. Repeated matches remain separate. This method is intentionally incomplete for diverged sequences. It is useful for trusted local construct-part libraries, not a general functional annotation engine.

Matches append with source `exact-reference:<filename>` and never overwrite imported features. A sequence match supports identity to the supplied reference; it does not verify function in the current construct.

## pLannotate

The supported integration uses **pLannotate 2.0.0**, BLAST, DIAMOND, Infernal and database bundle v2. Install it in a separate managed environment using mamba/micromamba/conda and curl:

```bash
.venv/bin/python scripts/setup_plannotate.py
.venv/bin/auraconstruct serve
```

The setup script creates `~/.local/share/auraconstruct/plannotate-env` (override the root with `AURACONSTRUCT_DATA_DIR`), downloads the official 256 MB release archive, verifies its published SHA-256, and lets pLannotate validate the individual database files. It leaves the app virtual environment and other Python installations unchanged. It does not run or download databases merely because a sequence is uploaded. Follow the [official installation documentation](https://github.com/mmcguffi/pLannotate) for alternatives. `AURACONSTRUCT_PLANNOTATE` can point to an existing executable.

Open the studio, upload a GenBank/FASTA file containing DNA, set **Circular** or **Linear**, and choose **Run pLannotate**. Uploading alone does not start annotation. The button is enabled only after the executable, external search tools, database manifest and required database files pass readiness checks. A truly empty file has no sequence to annotate.

Run `auraconstruct doctor --verify-databases` after installation, a database change, or suspected corruption. It prints JSON, reads every database file and compares its SHA-256 with the manifest; `database_integrity: "verified"` means all listed files passed. Missing files, malformed manifests and checksum mismatches make the check fail with exit status 1. The reported manifest fingerprint identifies the bundle metadata; it is not a fresh content-integrity check. Normal studio/API readiness and `auraconstruct doctor` check the reported database directory, manifest and file availability, with `database_integrity: "unchecked"`, so page loads and annotations do not repeatedly hash the full bundle. Verification checks local files against the manifest, not the biological correctness of its entries.

The adapter writes one temporary FASTA, invokes `plannotate batch -i INPUT -o OUTPUT -f annotated --cores 2`, adds `--linear` for linear DNA, and reads its annotated GenBank output. It requires explicit linear/circular topology. Temporary files are deleted after the operation. The default timeout is 600 seconds. The child process prepends its own search-tool directory and disables unrelated Python user-site packages; processing stays on the machine running the app.

The input and output sequence must match exactly before features are merged. Predictions append with source `pLannotate-prediction`; imported features remain. Engine version, database version/fingerprint, query sequence hash and run timestamp are recorded in project provenance. Generated GenBank features retain engine/database identifiers and the search evidence supplied by pLannotate. Single-line editable PPTX export works on the resulting model.

## Live validation, 2026-11-14

The actual engine and full default database search were run locally, with original feature annotations withheld:

| Sequence-only input | Length | Predicted features | Observation |
| --- | ---: | ---: | --- |
| pYTK001, circular | 2,676 bp | 7 | GFP, cat resistance CDS/promoter, origin and terminators detected |
| pMYT095, circular | 12,866 bp | 18 | Cas9, reporters, selection, origins, gRNA scaffold and tRNAs detected; some calls are marked fragments |
| pYTK001 rotated through the cat CDS | 2,676 bp | 7 | cat retained as a joined feature across the circular origin |
| pYTK001 treated as linear | 2,676 bp | 7 | Linear mode completed without changing the sequence |

Every output retained the exact input DNA and exported as one editable PowerPoint slide. These counts describe predictions, not annotation accuracy or complete recovery of deposited features. The database bundle manifest is v2, built 2026-07-05; its sources have their own dates and versions. Missed features, fragments and conflicting labels need review. Runtime measurements and raw outputs stay in the local validation directory rather than the public repository.

## Repeatable annotation-withheld validation

```bash
auraconstruct validate-annotation deposited.gb -o /private/path/validation-run --topology circular
```

This local command requires exactly one input record and runs pLannotate on its DNA with zero input features and no imported annotation provenance. It retains the raw source, feature-free query FASTA, predicted GenBank/project JSON, Aureka single-line SVG/native PPTX, artifact checksums, engine/database identifiers and UTC timestamps. A failed run records its error instead of a completed result. Use a new output directory each time; these artifacts contain DNA and should remain private.

After annotation, `report.json` compares the original and predicted features of one GenBank type (`--feature-type CDS` by default). Candidates require the same known strand and at least 90% coverage of **both** interval unions (`--minimum-overlap 0.9`). Joined/circular-origin intervals retain their original ordered segments; union coverage prevents counting overlapping segments twice. Names are not matching criteria. Exact interval coverage does not establish identical coding interpretation or function. No rotation or realignment is performed, and DNA or topology changes reject the comparison.

The report keeps reference and prediction denominators separate, lists unmatched features, and exposes multiple candidates. An unambiguous pair requires exactly one candidate in each direction; duplicate annotations are not silently assigned to a preferred match. Fuzzy boundaries and unknown/mixed strands remain listed but are excluded from agreement counts. Zero eligible source features means no agreement assessment is available. Deposited annotations may be incomplete or wrong, so unmatched predictions are not established false positives and the output is not a measured accuracy, precision or recall score.

The report also records source/prediction feature-type counts. Some deposited files encode every feature as `misc_feature`; those have zero CDS reference features even when the illustration assigns CDS glyphs from labels. The report explicitly marks a CDS assessment unavailable in that case. Illustration heuristics do not rewrite the deposited feature types for evaluation.

## Private library foundation

`auraconstruct library seed-demos` ingests the six already bundled source files into the local SQLite library; it is not a new Addgene download. `library stats`, `library ingest ... --source-url ... --license ...`, and `library export -o references.gb` support provenance-preserving reference management. Raw files, the database, aliases and source observations stay under the local data directory. The library currently provides exact reference matching, distinct from pLannotate's similarity search; broader acquisition is queued while pLannotate is prioritized.

Ingestion retains predictions, reference matches, manual/unknown-tool annotations and historical sequence annotations as separate evidence classes. They remain in the raw files and observation table, but cannot supply reference labels, provenance or glyph roles for subsequent matches. Reference export and `matchable_parts` require an unambiguous, non-fuzzy source annotation of at least 12 bp; `old_sequence`, `misc_difference`, `variation` and `unsure` entries are excluded. Legacy rows are rechecked from their saved source/engine metadata without deleting or rewriting observations. Reimporting an AuraConstruct library export does not turn it into an independent source. Counts can therefore decrease after an eligibility change while all observations remain intact. Imported source evidence is still unverified and may contain errors; this filter cannot identify predictions whose provenance was stripped before import.

Reference export revisions in v0.6.4 hash the exact exported GenBank bytes with the version prefix `auraconstruct-reference-v2` followed by a newline. The export records its eligibility-policy identifier, also retained in matched-project provenance. Changes to exported aliases, roles, source URLs or license notices therefore change the revision even when no new observations are added. Identical export content remains stable; excluded prediction-only sources do not affect it. This replaces the earlier observation-ID-only hash, so existing libraries receive a new revision without changing their DNA or deleting observations. It identifies the exported reference snapshot, not every field in SQLite: private retrieval notes and timestamps remain stored separately and are not included unless exported.

## Interpretation

Imported annotations may themselves be wrong. Exact matches and pLannotate calls produce sequence-based assignments. User edits are manual decisions. None is an experimentally validated function, expression result, or binding measurement merely because a figure displays it.
