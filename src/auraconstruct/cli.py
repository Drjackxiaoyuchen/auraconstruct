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
    doctor=sub.add_parser('doctor',help='Check local pLannotate tools and databases')
    doctor.add_argument('--verify-databases',action='store_true',help='Read and SHA-256 verify every database file')
    validation=sub.add_parser('validate-annotation',help='Withhold source features, run pLannotate and report coordinate agreement')
    validation.add_argument('input',type=Path)
    validation.add_argument('-o','--output',type=Path,required=True,help='New private output directory; existing directories are not overwritten')
    validation.add_argument('--topology',choices=['linear','circular'])
    validation.add_argument('--feature-type',default='CDS')
    validation.add_argument('--minimum-overlap',type=float,default=.9)
    export=sub.add_parser("export",help="Export one or more sequence files")
    export.add_argument("inputs",nargs="+",type=Path)
    export.add_argument("-o","--output",type=Path,required=True)
    export.add_argument("--layout",choices=["singleline","schematic","proportional"],default="singleline")
    export.add_argument("--palette",choices=["aureka","paper","colorblind","mono"],default="aureka")
    export.add_argument("--coordinates",action="store_true")
    export.add_argument("--detail",choices=["overview","detailed"],default="detailed")
    export.add_argument("--annotate",choices=["plannotate"])
    export.add_argument("--reference",type=Path)
    export.add_argument("--topology",choices=["linear","circular"])
    lib=sub.add_parser('library',help='Manage the private local DNA reference library')
    libsub=lib.add_subparsers(dest='library_command',required=True)
    for name in ('stats','seed-demos'):
        p=libsub.add_parser(name);p.add_argument('--db',type=Path)
    ingest=libsub.add_parser('ingest');ingest.add_argument('inputs',nargs='+',type=Path)
    ingest.add_argument('--source-url',required=True);ingest.add_argument('--license',required=True,dest='license_notice')
    ingest.add_argument('--access-note',default='');ingest.add_argument('--db',type=Path)
    ref=libsub.add_parser('export');ref.add_argument('-o','--output',required=True,type=Path);ref.add_argument('--db',type=Path)
    index=libsub.add_parser('build-index',help='Build a private standalone pLannotate BLAST database')
    index.add_argument('-o','--output',required=True,type=Path);index.add_argument('--db',type=Path)
    index.add_argument('--timeout',type=int,default=180)
    check_index=libsub.add_parser('index-status',help='Verify private index files and provenance')
    check_index.add_argument('directory',type=Path)
    args=parser.parse_args()
    if args.command=='validate-annotation':
        from .validation import validate_annotation
        try:
            report=validate_annotation(args.input,args.output,topology=args.topology,
                                       feature_type=args.feature_type,minimum_overlap=args.minimum_overlap)
        except (OSError,ValueError) as exc:parser.exit(2,f'Error: {exc}\n')
        print(json.dumps({'status':report['status'],'report':str(args.output/'report.json'),
                          'predictions':report['predictions'],'assessment_available':report['comparison']['assessment_available'],
                          'assessment_note':report['comparison']['assessment_note'],'comparison':report['comparison']['summary']},indent=2))
        return
    if args.command=='doctor':
        from .engine import status
        result=status(verify_databases=args.verify_databases)
        print(json.dumps(result,indent=2))
        if not result['ready']:parser.exit(1)
        return
    if args.command=='library':
        from . import library
        if args.library_command in ('build-index','index-status'):
            from .library_index import build_index,index_status
            try:
                result=(build_index(args.output,args.db,args.timeout) if args.library_command=='build-index'
                        else index_status(args.directory))
            except (OSError,ValueError) as exc:parser.exit(2,f'Error: {exc}\n')
            print(json.dumps(result,indent=2))
            if not result['ready']:parser.exit(1)
            return
        if args.library_command=='stats':result=library.stats(args.db)
        elif args.library_command=='seed-demos':result=library.seed_demos(args.db)
        elif args.library_command=='export':
            raw,revision=library.reference_genbank(args.db);args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_bytes(raw)
            result={'output':str(args.output),'revision':revision}
        else:
            result=[library.ingest(p.read_bytes(),p.name,source_url=args.source_url,license_notice=args.license_notice,
                                   access_note=args.access_note,path=args.db) for p in args.inputs]
        print(json.dumps(result,indent=2));return
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
        pages=[p for c in constructs for p in build_pages(c,args.layout,args.palette,args.coordinates,detail=args.detail)]
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
