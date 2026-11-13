"""Small public sequence examples with byte-level provenance and display curation."""
import hashlib
import json
from pathlib import Path

from .sequence_io import read_bytes

ROOT = Path(__file__).parent / "data" / "demos"


def manifest():
    return json.loads((ROOT / "manifest.json").read_text())


def catalog():
    return [{"id":d["id"], "title":d["title"], "citation":d["display_citation"]} for d in manifest()]


def load_demo(demo_id):
    entry = next((d for d in manifest() if d["id"] == demo_id), None)
    if entry is None:
        raise ValueError("Choose an available public demo.")
    data = (ROOT / entry["file"]).read_bytes()
    if hashlib.sha256(data).hexdigest() != entry["file_sha256"]:
        raise ValueError("The bundled demo file does not match its recorded checksum.")
    c = read_bytes(data, entry["file"])[0]
    c.name = entry["plasmid"]
    if entry.get("description"):
        c.description = entry["description"]
    c.provenance = {k:v for k,v in entry.items() if k not in ("display_overrides", "file")}
    for f in c.features:
        override = entry.get("display_overrides", {}).get(f.id, {})
        for k in ("visible", "label", "module", "role", "caption", "color"):
            if k in override:
                setattr(f,k,override[k])
        if "role" in override:
            f.role_source = "demo-curated"
        if "caption" in override:
            f.caption_source = "demo-curated"
    c.warnings.append("Public sequence example. Original features are preserved; display curation and hidden details are recorded in the demo manifest.")
    return c
