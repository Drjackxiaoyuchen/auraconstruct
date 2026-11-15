# Daily AuraConstruct development

The daily task runs in this chat at 09:00 Asia/Shanghai. Start by reading the newest report under the local data directory `~/.local/share/auraconstruct/reports/`. Do not repeat completed downloads or overwrite unrelated user changes.

## Priorities

1. Make real pLannotate annotation reliable for sequence-only GenBank/FASTA: isolated engine, search tools, databases, readiness and sequence-preserving output. Withhold original annotations during validation and report recovered/missed features without claiming functional verification.
2. Build a private, versioned common DNA part library with source observations, aliases, conflicting labels/types, coordinates, raw files, retrieval dates, licenses and checksums. Deduplicate feature sequences, including reverse complements, without discarding source evidence.
3. Research primary literature/software and acquire at most five eligible new plasmid sequence records per day. Start with common promoters, terminators, selection markers, replication origins, reporters and modular yeast parts. Keep additional candidates in a queue.
4. Improve the illustration workflow while preserving one continuous DNA backbone, Aureka colors, documented SBOL Visual semantics and native editable PowerPoint objects.

## Source access

Use Addgene's approved sequence API/bulk route for programmatic acquisition when the user has the relevant access and license. The current access process requires approval and a data license. Do not replace it with slower website scraping. Respect login, affinity-reagent acknowledgements, access controls, source licenses and rate limits. Do not accept agreements, message providers, purchase access or order biological materials.

Without approved access, record candidate Addgene pages and the access requirement. Independently published/depositor sequence downloads can be evaluated under their own terms. Record unknown or restricted license scope; public availability does not establish unrestricted commercial use or redistribution rights. Sources: [Addgene programmatic access](https://developers.addgene.org/access-options/), [sequence access requirements](https://help.addgene.org/hc/en-us/articles/44210206209549-Are-there-any-requirements-for-viewing-plasmid-sequence-data-on-the-Addgene-website), [terms](https://www.addgene.org/terms-of-use/).

Collected data, engine databases, raw sequence files and credentials stay local, outside the public code repository. Public repository changes contain implementation, documentation, permitted test fixtures and summaries only. The existing bundled demos have their own source notices; they do not license future acquisitions.

## Daily record

Record UTC retrieval times and local report dates, source URL/DOI, raw/sequence SHA-256, license/access status, new and duplicate record counts, unique parts versus source observations, annotation validation, code/test results and next work. Keep download attempts bounded with backoff. Record a blocked source rather than retrying it every day. Make one useful prioritized improvement when feasible; review and test changes before pushing authorized code/docs.

The initial seed uses already bundled source files; seed counts must not be reported as newly downloaded Addgene records.

Use `auraconstruct doctor --verify-databases` once per run to record file counts, bytes checked, manifest fingerprint and content-integrity status. Reuse that result in the report; do not repeat a full read for every annotation. Keep the quick readiness result distinct from full checksum verification. Continue real sequence-only regression tests separately from mocked unit tests.
