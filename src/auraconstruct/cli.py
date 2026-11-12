from __future__ import annotations

import argparse
import json
from pathlib import Path
import webbrowser

from .sequence_io import read_bytes
from .annotate import exact_annotate, plannotate
from .scene import build_pages, to_svg
from .pptx import to_pptx


def main():
    parser=argparse.ArgumentParser(description="DNA sequence files to editable genetic construct illustrations")
    sub=parser.add_subparsers(dest="command",required=True)
    serve=sub.add_parser("serve",help="Launch the local browser app")
    serve.add_argument("--port",type=int,default=8741)
    serve.add_argument("--no-browser",action="store_true")
    export=sub.add_parser("export",help="Export one or more sequence files")
    export.add_argument("inputs",nargs="+",type=Path)
    export.add_argument("-o","--output",type=Path,required=True)
    export.add_argument("--layout",choices=["schematic","proportional"],default="schematic")
    export.add_argument("--palette",choices=["aureka","paper","colorblind","mono"],default="aureka")
    export.add_argument("--coordinates",action="store_true")
    export.add_argument("--annotate",choices=["plannotate"])
    export.add_argument("--reference",type=Path)
    export.add_argument("--topology",choices=["linear","circular"])
    args=parser.parse_args()
    if args.command=="serve":
        from .server import create_app
        if not args.no_browser:
            webbrowser.open(f"http://127.0.0.1:{args.port}")
        create_app().run(host="127.0.0.1",port=args.port,debug=False)
        return
    constructs=[]
    try:
        for path in args.inputs:
            for c in read_bytes(path.read_bytes(),path.name):
                if args.topology:
                    c.topology=args.topology
                if args.reference:
                    c=exact_annotate(c,args.reference.read_bytes(),args.reference.name)
                if args.annotate:
                    c=plannotate(c)
                constructs.append(c)
        pages=[p for c in constructs for p in build_pages(c,args.layout,args.palette,args.coordinates)]
        out=args.output
        out.parent.mkdir(parents=True,exist_ok=True)
        if out.suffix.lower()==".pptx":
            out.write_bytes(to_pptx(pages))
        elif out.suffix.lower()==".json":
            out.write_text(json.dumps({"schema_version":1,"records":[c.to_dict() for c in constructs]},indent=2))
        elif out.suffix.lower()==".svg":
            if len(pages)==1:
                out.write_text(to_svg(pages[0]))
            else:
                for i,p in enumerate(pages,1):
                    out.with_name(f"{out.stem}-{i:03}.svg").write_text(to_svg(p))
        else:
            raise ValueError("Output extension must be .pptx, .svg or .json")
        print(f"Exported {len(constructs)} constructs / {len(pages)} figure pages to {out}")
    except (ValueError,OSError) as exc:
        parser.exit(2,f"Error: {exc}\n")


if __name__=="__main__":
    main()
