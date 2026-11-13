# Architecture

```text
GenBank / SnapGene / FASTA / EMBL / raw DNA
                 |
         Biopython parser
                 |
       Construct + Feature model
            /            \
  exact reference     pLannotate (optional)
            \            /
     annotation review + illustration settings
                 |
     shared deterministic scene geometry
            /                 \
    SVG browser preview    ECMA-376 DrawingML
                            editable PPTX
```

## Modules

- `sequence_io.py`: format detection, import/export and conversion to the model.
- `model.py`: coordinate, strand, role and color validation. JSON retains the normalized sequence SHA-256.
- `annotate.py`: exact reference search and bounded local pLannotate subprocess.
- `brand.py`: Aureka palette and original wordmark.
- `demos.py`: checked public examples and display presets.
- `details.py`: annotation categories, source summaries and short stored feature sequences.
- `scene.py`: shared primitives, glyphs, layout, pagination and SVG.
- `singleline.py`: one sequence-scaled backbone, collision-free label tiers and explicit module brackets; no construct wrapping or pagination.
- `pptx.py`: native paths, text boxes, named feature groups, notes and PowerPoint package relationships.
- `server.py`: loopback-only Flask interface; uploaded files are not persisted.
- `web/`: browser UI without a JavaScript build step or external CDN.
- `cli.py`: batch export and app launcher.

The product has no dependency on the development environment's presentation-authoring runtime. PPTX export uses Python's XML/ZIP facilities and interoperable DrawingML. Render checks imported generated presentations into an independent presentation runtime during development; they do not prove native PowerPoint application behavior on every version.

## Local API

Run `auraconstruct serve --no-browser`. Bind address is always `127.0.0.1`. POST requests require `X-AuraConstruct: 1`. These endpoints are for the local app, not an authenticated public service. Do not expose the development server to a network.

| Method and route | Input | Result |
| --- | --- | --- |
| GET `/api/status` | None | App version, roles, whether pLannotate is on PATH |
| GET `/api/demo?id=ytk001` | Demo ID: `ytk001`, `myt001`, `myt075`, `myt095`, or `ysd891` | Public toolkit sequence demo with provenance |
| POST `/api/import` | Multipart `files` | `records` array |
| POST `/api/render` | JSON `record`, `options` | Array of SVG `pages` |
| POST `/api/annotate` | JSON `record`, `engine: plannotate`; or multipart JSON `record` and file `reference` | Updated `record` |
| POST `/api/export/pptx` | JSON `records` or `record`, `options` | Native PPTX |
| POST `/api/export/svg` | Same | SVG or ZIP |
| POST `/api/export/json` | Same | Project JSON including DNA |
| POST `/api/export/gb` | Same | Annotated GenBank including DNA |
| POST `/api/project` | Project JSON | Validated records and options |

Options: `layout` (`singleline`, `schematic` or `proportional`; default `singleline`), `palette` (`aureka`, `paper`, `colorblind`, `mono`), `coordinates` (boolean), `detail` (`overview` or `detailed`), and optional `title`. Single-line maps keep compact labels; `detail` and `coordinates` apply to wrapped/coordinate views. Full callouts remain in the single-line PowerPoint notes and project data.

Project JSON stores `schema_version: 1`, `records`, and `options`. Each construct stores sequence, topology, source name/format, warnings and features. Features store ordered segments, strand and optional per-segment strands, qualifiers, annotation source, role-source, display color, visibility, module and fuzzy-boundary flag. Sequence data is not reconstructed from the drawing.
