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

From v0.7.3, CLI validation/export can request `--annotation-mode detailed`. This probes the installed engine's isolated `batch --help` and adds the legacy `--detailed` flag only when it is advertised as an option. Engines without that flag produce an explicit error; absence does not establish what their default nested-feature policy does. `--annotation-mode default` adds no mode flag and keeps existing studio/default behavior. The requested mode and flags are recorded in run provenance, and new GenBank predictions retain `ac_annotation_mode`. Illustration `--detail` controls figure callouts separately from engine annotation mode.

```bash
auraconstruct validate-annotation source.gb -o PRIVATE_NEW_DIRECTORY --annotation-mode detailed
auraconstruct export source.gb --annotate plannotate --annotation-mode detailed -o map.pptx
```

Legacy detailed mode can retain overlapping annotations of different source types, including additional fragments that need review. More calls do not establish better biological accuracy. Compare runs with original annotations withheld and preserve imported features rather than replacing them.

From v0.7.4, the studio's **pLannotate search** selector offers **Default search** and **Include overlapping features**. Default remains selected initially. `/api/status` reports base readiness and per-mode availability separately, using the installed capability gate; inability to verify detailed mode leaves default search usable. The selector and run button are disabled during a run, and the chosen mode is sent explicitly to `/api/annotate`. That endpoint defaults older requests to `default`, rejects unknown modes and rechecks support before search. Mode selection affects the next requested annotation, while the applied mode remains in the resulting project/GenBank provenance. Figure detail continues to control callouts independently.

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

From v0.7.1, policy `source-semantics-v2` resolves generic context using explicit source feature types, regulatory classes or Sequence Ontology terms. For example, a `gene` context and a `CDS` covering the same part can supply a CDS role. This is not a majority vote: repeated generic observations cannot outweigh explicit semantics. Different functional roles, or saved glyph roles contradicting explicit source semantics, remain unresolved. Export qualifiers retain the role/type alternatives, conflict flags and resolution method; no raw observation is rewritten. This resolves representation differences, not biological function. [NCBI feature-table guidance](https://www.ncbi.nlm.nih.gov/genbank/feature_table/) distinguishes gene context from CDS annotations.

## Private custom search index

```bash
auraconstruct library build-index -o ~/.local/share/auraconstruct/indexes/source-v1
auraconstruct library index-status ~/.local/share/auraconstruct/indexes/source-v1
# Optional independent experiment; keep both snapshots for comparison:
auraconstruct library build-index --profile parts -o ~/.local/share/auraconstruct/indexes/parts-v1
```

`build-index` reads the eligible source-reference export, converts each reference to its biological strand, and invokes the isolated engine's `plannotate makedb` with nucleotide FASTA/description CSV, BLAST and `--no-builtins`. It requires pLannotate and `makeblastdb`. The 180-second build timeout is configurable with `--timeout`; failed builds retain a failed manifest and diagnostics. Existing output directories are never overwritten.

Unresolved role conflicts and all strand conflicts are omitted from the search index and listed in the manifest, while their raw observations remain in SQLite and the retained reference GenBank. Context resolved by explicit source semantics can be included; entries keep the resolution method and alternative roles/types alongside aliases, source URLs, license notices, part hashes and the reference revision/policy. Input and compiled-index hashes form a versioned bundle fingerprint. Everything in this directory contains private reference data and should stay outside public GitHub. Existing index snapshots remain immutable and verifiable; adopting a new policy requires a build in a new directory.

The default `--profile source` retains eligible context entries. Optional `--profile parts` omits roles `generic`, `region` and `engineered_region` before searching. This can reduce competition from broad contextual intervals over nested feature calls; it also removes potentially useful annotations. All exclusions remain in the manifest with their reasons and source metadata, and the full reference export remains byte-identical between profiles built from the same library snapshot. Other roles may still come from illustration label heuristics; this profile does not establish function, rewrite source types, or guarantee that pLannotate will report a particular hit. Both profiles exclude unresolved role/strand conflicts. Compare both runs and review omissions before adopting the smaller index.

From v0.7.2, index manifest schema 2 records the profile in its integrity fingerprint. `index-status` still verifies schema 1 snapshots using their original hash contract and reports their full-source profile. Neither a new profile nor a successful integrity check activates a custom index in the studio.

Single-line SVG/PPTX display labels retain an explicit trailing `(fragment)` qualifier when shortening long names. Full source labels remain in the project and slide notes; this display rule adds no biological interpretation.

`index-status` checks every manifest-listed file and the manifest fingerprint; it reports integrity readiness, not biological accuracy, search coverage, or agreement with the newest library revision. Later acquisitions require a build in a new directory. The saved `databases.yml` can be passed with `-y` to a separate, isolated pLannotate batch run. Its output remains similarity predictions and must not be ingested as independent source evidence. The studio's **Run pLannotate** button continues using the default builtin bundle.

This standalone index is intended for evaluation. Deposited labels can be incomplete or contextual, and the conflict filter can omit useful markers. It is not a replacement for the builtin database. Compare source/prediction denominators and review missing/fragment calls before using a custom configuration for presentation annotation. Custom search was tested separately from the default engine; index verification alone does not establish a successful query.

## Interpretation

Imported annotations may themselves be wrong. Exact matches and pLannotate calls produce sequence-based assignments. User edits are manual decisions. None is an experimentally validated function, expression result, or binding measurement merely because a figure displays it.
