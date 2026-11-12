import gzip
import io
import json
from pathlib import Path
import struct
from zipfile import ZipFile
import xml.etree.ElementTree as ET

import pytest
from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord
from Bio.SeqFeature import SeqFeature, SimpleLocation, CompoundLocation

from auraconstruct.model import Feature, Construct, infer_role
from auraconstruct.sequence_io import read_bytes, from_dict, to_genbank
from auraconstruct.annotate import exact_annotate, plannotate
from auraconstruct.scene import build_pages, to_svg, W, H
from auraconstruct.pptx import to_pptx, P, A
from auraconstruct.server import create_app

DEMO = Path(__file__).parents[1]/"src/auraconstruct/data/illustration_demo.gb"


def record_bytes(r, fmt="genbank"):
    out=io.StringIO();SeqIO.write(r,out,fmt);return out.getvalue().encode()


def sample():
    return read_bytes(DEMO.read_bytes(),DEMO.name)[0]


def test_compound_reverse_and_origin_roundtrip():
    r=SeqRecord(Seq("ATGC"*50),id="test",name="test",annotations={"molecule_type":"DNA","topology":"circular"})
    loc=CompoundLocation([SimpleLocation(0,10,strand=-1),SimpleLocation(180,200,strand=-1)])
    r.features=[SeqFeature(loc,type="CDS",qualifiers={"label":["joined CDS"]})]
    c=read_bytes(record_bytes(r),"test.gbk")[0]
    assert c.features[0].segments==[[0,10],[180,200]]
    assert c.features[0].strand==-1
    c.features[0].module="Module A"
    restored=read_bytes(to_genbank(c),"roundtrip.gb")[0]
    assert restored.features[0].segments==c.features[0].segments
    assert restored.features[0].module=="Module A"
    assert restored.sequence==c.sequence


def test_mixed_strand_join_roundtrip():
    r=SeqRecord(Seq("ATGC"*50),id="mixed",name="mixed",annotations={"molecule_type":"DNA"})
    loc=CompoundLocation([SimpleLocation(20,40,strand=1),SimpleLocation(80,100,strand=-1)])
    r.features=[SeqFeature(loc,type="misc_feature",qualifiers={"label":["mixed"]})]
    c=read_bytes(record_bytes(r),"mixed.gb")[0]
    assert c.features[0].strand==0
    assert c.features[0].segment_strands==[1,-1]
    restored=read_bytes(to_genbank(c),"roundtrip.gb")[0]
    assert restored.features[0].segment_strands==[1,-1]


@pytest.mark.parametrize("ext,raw",[("x.txt",b"ATGC RYSW\nKMBDHVN"),("x.fa",b">a\nATGC\n>b\nNNNN\n"),("x.fa.gz",gzip.compress(b">a\nATGC"))])
def test_raw_fasta_and_gzip(ext,raw):
    records=read_bytes(raw,ext)
    assert records[0].length>0
    assert not records[0].features
    assert records[0].topology=="unknown"


def test_embl():
    r=SeqRecord(Seq("ATGC"*10),id="x",name="x",annotations={"molecule_type":"DNA"})
    assert read_bytes(record_bytes(r,"embl"),"x.embl")[0].sequence==str(r.seq)


def packet(tag,data):
    return bytes([tag])+struct.pack(">I",len(data))+data


def test_snapgene_binary_and_reverse_feature():
    # Native SnapGene cookie, DNA packet and Features XML, not a renamed GenBank.
    cookie=packet(9,b"SnapGene"+struct.pack(">HHH",1,1,1))
    dna=packet(0,b"\x01"+b"ATGC"*20)
    features=packet(10,b'<Features><Feature name="demo" type="CDS" directionality="2"><Segment range="5-20"/></Feature></Features>')
    c=read_bytes(cookie+dna+features,"native.dna")[0]
    assert c.source_format=="snapgene"
    assert c.topology=="circular"
    assert c.features[0].segments==[[4,20]]
    assert c.features[0].strand==-1


@pytest.mark.parametrize("raw",[b"",b"ATGC<svg>",b"hello",b"ATGU",b"1234"])
def test_invalid_sequences_rejected(raw):
    with pytest.raises((ValueError,UnicodeError)):
        read_bytes(raw,"x.txt")


def test_role_priority_and_heuristic_disclosure():
    assert infer_role("CDS",{},"promoter")==("cds","feature-type")
    assert infer_role("regulatory",{"regulatory_class":["promoter"]},"x")==("promoter","regulatory-class")
    assert infer_role("misc_feature",{},"GAL1 Promoter")==("promoter","label-heuristic")
    assert infer_role("misc_feature",{},"mystery")==("generic","unspecified")
    assert infer_role("primer",{},"AmpR_primer_F_inside")==("primer","feature-type")
    assert infer_role("protein_bind",{"db_xref":["SO:0000057"]},"site")==("operator","sequence-ontology")


def test_exact_match_both_strands_and_circular_origin():
    query="AAGCTAGGCTAGTC"
    c=Construct("x","x",query[7:]+"C"*20+str(Seq(query).reverse_complement())+"G"*20+query[:7],"circular",[],"x.fa","fasta")
    out=exact_annotate(c,f">part\n{query}\n".encode(),"parts.fa")
    assert any(f.strand==-1 for f in out.features)
    assert any(len(f.segments)==2 for f in out.features)
    assert not c.features
    assert all(f.source=="exact-reference:parts.fa" for f in out.features)
    assert len(exact_annotate(out,f">part\n{query}\n".encode(),"parts.fa").features)==len(out.features)


def test_project_roundtrip_and_validation():
    c=sample();c.features[0].color="#123456";c.features[0].visible=False
    assert from_dict(json.loads(json.dumps(c.to_dict()))).to_dict()==c.to_dict()
    d=c.to_dict();d["features"][0]["segments"]=[[0,999999]]
    with pytest.raises(ValueError):from_dict(d)


def test_native_groups_editable_text_no_raster_and_notes():
    c=sample();c.features[0].label='Label {x} & <editable>'
    data=to_pptx(build_pages(c))
    with ZipFile(io.BytesIO(data)) as z:
        # Only the original brand wordmark is an image. Construct glyphs remain native.
        assert [n for n in z.namelist() if n.startswith("ppt/media/")] == ["ppt/media/aureka-logo.png"]
        for name in z.namelist():
            if name.endswith((".xml",".rels")):ET.fromstring(z.read(name))
        root=ET.fromstring(z.read("ppt/slides/slide1.xml"))
        assert len(root.findall(f".//{{{P}}}grpSp"))==8
        assert len(root.findall(f".//{{{A}}}custGeom"))>=8
        assert 'Label {x} & <editable>' in ' '.join(e.text or '' for e in root.findall(f".//{{{A}}}t"))
        assert b"sbolstandard.org" in z.read("ppt/notesSlides/notesSlide1.xml")
        # All relationship targets point to existing package members.
        import posixpath
        for name in [n for n in z.namelist() if n.endswith('.rels')]:
            base=posixpath.dirname(posixpath.dirname(name))
            for rel in ET.fromstring(z.read(name)):
                target=posixpath.normpath(posixpath.join(base,rel.attrib['Target']))
                assert target in z.namelist(), (name,target)


def test_dense_maps_paginate_and_stay_on_canvas():
    c=sample()
    c.features=[Feature(str(i),"A longer annotation label for a feature",'CDS','cds',[[i*30,i*30+20]],-1 if i%2 else 1,module='Module label' if i%3 else '') for i in range(65)]
    for layout in ("schematic","proportional"):
        pages=build_pages(c,layout,coordinates=True)
        assert len(pages)>1
        for p in pages:
            for s in p.items:
                assert s.x>=0 and s.y>=0
                assert s.x+s.w<=W+1 and s.y+s.h<=H+1, (s,layout)
    c.features=[]
    assert "Unannotated DNA" in to_svg(build_pages(c)[0])


def test_web_import_render_export_and_project():
    client=create_app().test_client();h={"X-AuraConstruct":"1"}
    response=client.post('/api/import',data={'files':(io.BytesIO(DEMO.read_bytes()),'demo.gb')},headers=h)
    assert response.status_code==200
    data=response.json;assert len(data['records'])==1
    payload={'record':data['records'][0],'options':{'palette':'paper'}}
    assert '<svg' in client.post('/api/render',json=payload,headers=h).json['pages'][0]
    assert client.post('/api/export/pptx',json=payload,headers=h).data[:2]==b'PK'
    for fmt in ('json','gb','svg'):
        assert client.post(f'/api/export/{fmt}',json=payload,headers=h).status_code==200
    assert client.post('/api/project',json=data,headers=h).json['records']==data['records']
    assert client.post('/api/render',json=payload).status_code==403
    assert client.post('/api/render',json=payload,headers={**h,'Host':'hostile.example'}).status_code==403


def test_plannotate_missing_and_sequence_change_protection(monkeypatch):
    monkeypatch.setattr('auraconstruct.annotate.shutil.which',lambda _:None)
    with pytest.raises(ValueError,match='not installed'):plannotate(sample())


def test_plannotate_adapter_merges_and_preserves_imports(monkeypatch):
    from types import SimpleNamespace
    c=sample()
    monkeypatch.setattr('auraconstruct.annotate.shutil.which',lambda _:'/bin/plannotate')
    def fake_run(args,**kwargs):
        out=Path(args[args.index('-o')+1])/'annotated_pLann.gbk'
        predicted=sample();predicted.features=[Feature('p1','Predicted ori','rep_origin','origin',[[3000,3200]],1)]
        out.write_bytes(to_genbank(predicted))
        return SimpleNamespace(returncode=0,stderr='',stdout='')
    monkeypatch.setattr('auraconstruct.annotate.subprocess.run',fake_run)
    result=plannotate(c)
    assert len(result.features)==len(c.features)+1
    assert result.features[-1].source=='pLannotate-prediction'
    assert result.sequence==c.sequence


@pytest.mark.parametrize("demo_id",["ytk001","myt001","myt075","myt095","ysd891"])
def test_public_demo_provenance_and_export(demo_id):
    import hashlib
    from auraconstruct.demos import load_demo
    c=load_demo(demo_id)
    assert hashlib.sha256(c.sequence.encode()).hexdigest()==c.provenance["sequence_sha256"]
    assert c.length==c.provenance["length"]
    assert c.provenance["source_url"].startswith("https://www.addgene.org/")
    assert from_dict(c.to_dict()).provenance==c.provenance
    for layout in ("schematic","proportional"):
        pages=build_pages(c,layout=layout)
        with ZipFile(io.BytesIO(to_pptx(pages))) as z:
            for i in range(len(pages)):
                notes=z.read(f"ppt/notesSlides/notesSlide{i+1}.xml").decode()
                assert c.provenance["doi"] in notes
            assert b'6500FF' in z.read('ppt/theme/theme1.xml')
    response=create_app().test_client().get(f'/api/demo?id={demo_id}')
    assert response.status_code==200
    assert response.json['records'][0]['sha256']==c.to_dict()['sha256']


def test_detailed_captions_and_short_sequences_keep_their_sources():
    from auraconstruct.details import category,summary,short_sequence
    c=Construct('x','x','ATGCCGTAGCTAACCGGTTAA','linear',[], 'x.gb','genbank')
    f=Feature('primer','ConE RP','misc_feature','primer',[[2,14]],-1,
              qualifiers={'note':['Source note about a primer site.']})
    assert short_sequence(c,f)==f"5′ {str(Seq(c.sequence[2:14]).reverse_complement())} 3′"
    assert summary(f)==('Source note about a primer site.','qualifier:note')
    f.caption='Manually reviewed callout';assert summary(f)==(f.caption,'user-caption')
    c.features=[f]
    restored=read_bytes(to_genbank(c),'roundtrip.gb')[0].features[0]
    assert restored.caption==f.caption and restored.caption_source=='user-caption'
    site=Feature('site','BsaI','protein_bind','generic',[[0,4]],1)
    assert category(site)=='Restriction-related annotation'
    assert short_sequence(c,site)=='5′ ATGC 3′'
    # A label alone does not establish an exact cleavage coordinate or overhang.
    assert infer_role('protein_bind',{},'BsaI')==('generic','feature-type')


def test_detailed_mode_has_coordinates_notes_and_native_objects():
    from auraconstruct.demos import load_demo
    c=load_demo('myt075')
    c.features[0].caption='Reviewed homology arm caption'
    c.features[0].caption_source='user-caption'
    pages=build_pages(c,detail='detailed')
    assert len(pages)==3
    svg=to_svg(pages[0])
    assert '519 bp' in svg and 'Homology arm' in svg and 'Reviewed homology arm caption' in svg
    assert 'Genomic' not in svg  # Donor coordinates are not silently promoted to genomic coordinates.
    with ZipFile(io.BytesIO(to_pptx(pages))) as z:
        notes=z.read('ppt/notesSlides/notesSlide1.xml').decode()
        assert 'caption (user-caption): Reviewed homology arm caption' in notes
        root=ET.fromstring(z.read('ppt/slides/slide1.xml'))
        assert len(root.findall(f'.//{{{P}}}grpSp'))==8
        assert any('519 bp' in (e.text or '') for e in root.findall(f'.//{{{A}}}t'))
    for layout in ('schematic','proportional'):
        for p in build_pages(c,layout=layout,detail='detailed'):
            assert all(s.x>=0 and s.y>=0 and s.x+s.w<=W+1 and s.y+s.h<=H+1 for s in p.items)
