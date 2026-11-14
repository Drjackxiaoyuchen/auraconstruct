# Roadmap

The current deliverable is a working local v0.6 illustration tool. These items are future work, not completed capabilities.

## Figure composition

- Circular plasmid maps with editable arcs and collision-aware labels.
- Aligned construct variants for figures comparing a library or design series.
- Region selection, coordinate-preserving rotation around a chosen origin and collapsed backbone regions.
- Drag/reorder visual modules without changing the biological source order.
- Optional feature legend, scale bar and journal column sizing.

## Semantics and annotation

- Full SBOL Visual conformance review, expanded role vocabulary and snapshot fixtures.
- Optional SBOL3 data exchange with validation separate from illustration settings.
- Curated reference-library review UI and authorized incremental acquisition; the local SQLite/CLI foundation preserves source observations, aliases and licenses.
- Live pLannotate integration CI using a controlled database snapshot.
- Preservation of fuzzy-location classes in re-exported GenBank locations.

## Delivery and interoperability

- Packaged desktop launcher and installation checks.
- Visual regression tests in native PowerPoint and LibreOffice.
- Drag-and-drop library browser and editable feature coordinate dialog.

Contributions should preserve annotation provenance, biological coordinate order and native PowerPoint editability. A rendering change must not silently relabel evidence or imply functional validation.
