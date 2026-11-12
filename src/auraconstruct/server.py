"""Local browser app. No remote sequence services or persistent upload storage."""
from __future__ import annotations

import io
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

from flask import Flask, jsonify, request, send_file
from werkzeug.exceptions import HTTPException

from . import __version__
from .annotate import exact_annotate, plannotate, plannotate_available
from .model import ROLES
from .sequence_io import read_bytes, from_dict, to_genbank
from .scene import build_pages, to_svg, PALETTES, COLORS
from .pptx import to_pptx

ROOT = Path(__file__).parent


def create_app():
    app = Flask(__name__, static_folder=str(ROOT / "web"), static_url_path="/static")
    app.config["MAX_CONTENT_LENGTH"] = 22_000_000

    @app.before_request
    def local_only():
        # Prevent cross-site requests against a user's local sequence app.
        if request.host.split(":")[0] not in ("127.0.0.1", "localhost", "[::1]"):
            return jsonify(error="Use localhost or 127.0.0.1."), 403
        if request.method == "POST" and request.headers.get("X-AuraConstruct") != "1":
            return jsonify(error="Missing local app request header."), 403

    @app.after_request
    def headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = "default-src 'self'; img-src 'self' blob: data:; style-src 'self'; script-src 'self'; frame-ancestors 'none'; object-src 'none'"
        return response

    @app.errorhandler(Exception)
    def error(exc):
        status = exc.code if isinstance(exc, HTTPException) else 400
        if not isinstance(exc, (ValueError, HTTPException, UnicodeError, OSError, KeyError, TypeError)):
            app.logger.exception("Request failed")
            status = 500
        return jsonify(error=str(exc) if status != 500 else "The operation failed. Check the local server log."), status

    @app.get("/")
    def index():
        return app.send_static_file("index.html")

    @app.get("/api/status")
    def status():
        from .demos import catalog
        return jsonify(version=__version__, plannotate=plannotate_available(), roles=ROLES,
                       palettes=PALETTES, role_color_indices=COLORS, demos=catalog())

    @app.get("/api/demo")
    def demo():
        from .demos import load_demo
        return jsonify(records=[load_demo(request.args.get("id", "ytk001")).to_dict()])

    @app.post("/api/import")
    def import_sequence():
        records = []
        files = request.files.getlist("files")
        if not files:
            raise ValueError("Choose at least one sequence file.")
        for file in files:
            for c in read_bytes(file.read(), file.filename or "sequence.txt"):
                c.id = f"record-{len(records)+1}"
                records.append(c.to_dict())
        return jsonify(records=records)

    @app.post("/api/render")
    def render():
        data = request.get_json()
        c = from_dict(data["record"])
        pages = build_pages(c, **options(data))
        return jsonify(pages=[to_svg(p) for p in pages])

    @app.post("/api/annotate")
    def annotate():
        if request.is_json:
            data=request.get_json()
            if data.get("engine") != "plannotate":
                raise ValueError("Choose the pLannotate engine.")
            c = plannotate(from_dict(data["record"]))
        else:
            c = from_dict(json.loads(request.form["record"]))
            ref=request.files["reference"]
            c = exact_annotate(c,ref.read(),ref.filename or "reference.fa")
        return jsonify(record=c.to_dict())

    @app.post("/api/export/<fmt>")
    def export(fmt):
        data = request.get_json()
        records = [from_dict(d) for d in data.get("records", [data.get("record")])]
        if not records or any(c is None for c in records):
            raise ValueError("Select a construct first.")
        if fmt == "json":
            content = json.dumps({"schema_version":1, "records":[c.to_dict() for c in records], "options":options(data)}, indent=2).encode()
            return download(content,"auraconstruct-project.json","application/json")
        if fmt == "gb":
            return download(b"".join(to_genbank(c) for c in records), "annotated-constructs.gb", "text/plain")
        pages=[p for c in records for p in build_pages(c,**options(data))]
        if fmt == "pptx":
            return download(to_pptx(pages),"auraconstruct-editable.pptx","application/vnd.openxmlformats-officedocument.presentationml.presentation")
        if fmt == "svg":
            if len(pages)==1:
                return download(to_svg(pages[0]).encode(),"construct.svg","image/svg+xml")
            buf=io.BytesIO()
            with ZipFile(buf,"w",ZIP_DEFLATED) as z:
                for i,p in enumerate(pages,1):
                    z.writestr(f"construct-{i:03}.svg",to_svg(p))
            return download(buf.getvalue(),"construct-figures.zip","application/zip")
        raise ValueError("Export format must be pptx, svg, json or gb.")

    @app.post("/api/project")
    def project():
        data=request.get_json()
        return jsonify(records=[from_dict(d).to_dict() for d in data["records"]], options=options(data))

    return app


def options(data):
    raw = data.get("options",{})
    return {k:v for k,v in raw.items() if k in ("layout","palette","coordinates","title","detail")}


def download(content, name, mimetype):
    return send_file(io.BytesIO(content), download_name=name, mimetype=mimetype, as_attachment=True)
