"""Portable native PowerPoint exporter, using ECMA-376 DrawingML.

No screenshots, embedded SVGs, proprietary runtime, or python-pptx dependency.
Every feature is a named group of editable paths and editable text boxes.
"""
from __future__ import annotations

from collections import OrderedDict
from datetime import datetime, timezone
from html import escape
import io
from itertools import count
from zipfile import ZipFile, ZIP_DEFLATED

from .scene import W, H
from .brand import LOGO

EMU = 9525  # CSS pixel at 96 dpi
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
P = "http://schemas.openxmlformats.org/presentationml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS = f'xmlns:a="{A}" xmlns:p="{P}" xmlns:r="{R}"'


def xml(text):
    return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'+text


def rels(entries):
    return xml('<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'+
               ''.join(f'<Relationship Id="{rid}" Type="{R}/{kind}" Target="{escape(target,quote=True)}"/>'
                       for rid,kind,target in entries)+'</Relationships>')


def fill(color):
    return '<a:noFill/>' if color == "none" else f'<a:solidFill><a:srgbClr val="{color.lstrip(chr(35))}"/></a:solidFill>'


def xfrm(x, y, w, h, group=False):
    child = f'<a:chOff x="{round(x*EMU)}" y="{round(y*EMU)}"/><a:chExt cx="{max(1,round(w*EMU))}" cy="{max(1,round(h*EMU))}"/>' if group else ''
    return (f'<a:xfrm><a:off x="{round(x*EMU)}" y="{round(y*EMU)}"/>'
            f'<a:ext cx="{max(1,round(w*EMU))}" cy="{max(1,round(h*EMU))}"/>{child}</a:xfrm>')


def shape(item, sid):
    name = escape(item.name or item.kind, quote=True)
    if item.kind == "image":
        return (f'<p:pic><p:nvPicPr><p:cNvPr id="{sid}" name="{name}"/>'
                '<p:cNvPicPr><a:picLocks noChangeAspect="1"/></p:cNvPicPr><p:nvPr/></p:nvPicPr>'
                '<p:blipFill><a:blip r:embed="rIdLogo"/><a:stretch><a:fillRect/></a:stretch></p:blipFill>'
                f'<p:spPr>{xfrm(item.x,item.y,item.w,item.h)}<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr></p:pic>')
    nv = f'<p:nvSpPr><p:cNvPr id="{sid}" name="{name}"/><p:cNvSpPr'+(' txBox="1"' if item.kind=="text" else '')+'/>'+ '<p:nvPr/></p:nvSpPr>'
    pos = xfrm(item.x,item.y,item.w,item.h)
    if item.kind == "text":
        color = fill(item.fill)
        alignment = {"left":"l","center":"ctr","right":"r"}[item.align]
        props = f'<a:rPr lang="en-US" sz="{round(item.size*75)}" b="{1 if item.bold else 0}">{color}<a:latin typeface="Arial"/><a:ea typeface="Arial"/><a:cs typeface="Arial"/></a:rPr>'
        text = (f'<p:txBody><a:bodyPr wrap="none" lIns="0" tIns="0" rIns="0" bIns="0" anchor="t"/><a:lstStyle/>'
                f'<a:p><a:pPr algn="{alignment}"/><a:r>{props}<a:t xml:space="preserve">{escape(item.text)}</a:t></a:r>'
                f'<a:endParaRPr lang="en-US" sz="{round(item.size*75)}"/></a:p></p:txBody>')
        return f'<p:sp>{nv}<p:spPr>{pos}<a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/><a:ln><a:noFill/></a:ln></p:spPr>{text}</p:sp>'
    commands = []
    for cmd in item.commands:
        pts = [f'<a:pt x="{round((cmd[i]-item.x)*EMU)}" y="{round((cmd[i+1]-item.y)*EMU)}"/>' for i in range(1,len(cmd),2)]
        tag = {"M":"moveTo","L":"lnTo","C":"cubicBezTo","Z":"close"}[cmd[0]]
        commands.append(f'<a:{tag}>'+''.join(pts)+f'</a:{tag}>')
    path = f'<a:custGeom><a:avLst/><a:gdLst/><a:ahLst/><a:cxnLst/><a:rect l="0" t="0" r="r" b="b"/><a:pathLst><a:path w="{max(1,round(item.w*EMU))}" h="{max(1,round(item.h*EMU))}">'+''.join(commands)+'</a:path></a:pathLst></a:custGeom>'
    line = f'<a:ln w="{round(item.sw*EMU)}" cap="rnd">{fill(item.stroke)}'+ ('<a:prstDash val="dash"/>' if item.dashed else '')+'<a:round/></a:ln>'
    return f'<p:sp>{nv}<p:spPr>{pos}{path}{fill(item.fill)}{line}</p:spPr></p:sp>'


def sp_tree(items):
    ids = count(2)
    parts = ['<p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr>'+xfrm(0,0,W,H,True)+'</p:grpSpPr>']
    grouped = OrderedDict()
    # Glyphs, labels and interval tracks form one selectable feature group.
    for i, item in enumerate(items):
        grouped.setdefault(item.group or f"_ungrouped_{i}", []).append(item)
    for group, group_items in grouped.items():
        if group.startswith("_ungrouped_"):
            parts.append(shape(group_items[0], next(ids)))
            continue
        x, y = min(i.x for i in group_items), min(i.y for i in group_items)
        w, h = max(i.x+i.w for i in group_items)-x, max(i.y+i.h for i in group_items)-y
        label = next((i.text for i in group_items if i.kind=="text" and i.size>=14), group)
        name = escape(f"{group} / {label}",quote=True)
        parts.append(f'<p:grpSp><p:nvGrpSpPr><p:cNvPr id="{next(ids)}" name="{name}"/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr>{xfrm(x,y,w,h,True)}</p:grpSpPr>')
        parts.extend(shape(i,next(ids)) for i in group_items)
        parts.append('</p:grpSp>')
    return ''.join(parts)+'</p:spTree>'


THEME = f'''<a:theme xmlns:a="{A}" name="Aureka 2026"><a:themeElements><a:clrScheme name="Aureka">
<a:dk1><a:srgbClr val="333333"/></a:dk1><a:lt1><a:srgbClr val="FFFFFF"/></a:lt1><a:dk2><a:srgbClr val="707684"/></a:dk2><a:lt2><a:srgbClr val="F0EAFF"/></a:lt2>
<a:accent1><a:srgbClr val="6500FF"/></a:accent1><a:accent2><a:srgbClr val="FF6D8E"/></a:accent2><a:accent3><a:srgbClr val="4200AC"/></a:accent3><a:accent4><a:srgbClr val="F9AC2F"/></a:accent4><a:accent5><a:srgbClr val="6FC0A9"/></a:accent5><a:accent6><a:srgbClr val="FFBFDF"/></a:accent6><a:hlink><a:srgbClr val="6500FF"/></a:hlink><a:folHlink><a:srgbClr val="4200AC"/></a:folHlink></a:clrScheme>
<a:fontScheme name="Arial"><a:majorFont><a:latin typeface="Arial"/><a:ea typeface=""/><a:cs typeface=""/></a:majorFont><a:minorFont><a:latin typeface="Arial"/><a:ea typeface=""/><a:cs typeface=""/></a:minorFont></a:fontScheme>
<a:fmtScheme name="Standard"><a:fillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:fillStyleLst><a:lnStyleLst>
{''.join('<a:ln w="9525"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln>' for _ in range(3))}</a:lnStyleLst><a:effectStyleLst>{'<a:effectStyle><a:effectLst/></a:effectStyle>'*3}</a:effectStyleLst><a:bgFillStyleLst>{'<a:solidFill><a:schemeClr val="phClr"/></a:solidFill>'*3}</a:bgFillStyleLst></a:fmtScheme></a:themeElements></a:theme>'''


def to_pptx(pages) -> bytes:
    if not pages:
        raise ValueError("A presentation needs at least one slide.")
    out = io.BytesIO()
    with ZipFile(out,"w",ZIP_DEFLATED) as z:
        def put(path,content):
            z.writestr(path,xml(content))
        overrides = [("/ppt/presentation.xml","presentationml.presentation.main"),
                     ("/ppt/slideMasters/slideMaster1.xml","presentationml.slideMaster"),
                     ("/ppt/slideLayouts/slideLayout1.xml","presentationml.slideLayout"),
                     ("/ppt/notesMasters/notesMaster1.xml","presentationml.notesMaster"),
                     ("/ppt/theme/theme1.xml","theme")]
        for i in range(1,len(pages)+1):
            overrides += [(f"/ppt/slides/slide{i}.xml","presentationml.slide"),(f"/ppt/notesSlides/notesSlide{i}.xml","presentationml.notesSlide")]
        types = ''.join(f'<Override PartName="{p}" ContentType="application/vnd.openxmlformats-officedocument.{t}+xml"/>' for p,t in overrides)
        put("[Content_Types].xml",'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Default Extension="png" ContentType="image/png"/>'+types+'</Types>')
        z.writestr("ppt/media/aureka-logo.png", LOGO.read_bytes())
        z.writestr("_rels/.rels",rels([("rId1","officeDocument","ppt/presentation.xml")]))
        slideids = ''.join(f'<p:sldId id="{255+i}" r:id="rId{i+2}"/>' for i in range(1,len(pages)+1))
        put("ppt/presentation.xml",f'<p:presentation {NS}><p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/></p:sldMasterIdLst><p:notesMasterIdLst><p:notesMasterId r:id="rId2"/></p:notesMasterIdLst><p:sldIdLst>{slideids}</p:sldIdLst><p:sldSz cx="{W*EMU}" cy="{H*EMU}" type="screen16x9"/><p:notesSz cx="6858000" cy="9144000"/></p:presentation>')
        z.writestr("ppt/_rels/presentation.xml.rels",rels([("rId1","slideMaster","slideMasters/slideMaster1.xml"),("rId2","notesMaster","notesMasters/notesMaster1.xml")]+[(f"rId{i+2}","slide",f"slides/slide{i}.xml") for i in range(1,len(pages)+1)]))
        mapping = '<p:clrMap accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" bg1="lt1" bg2="lt2" folHlink="folHlink" hlink="hlink" tx1="dk1" tx2="dk2"/>'
        put("ppt/slideMasters/slideMaster1.xml",f'<p:sldMaster {NS}><p:cSld>{sp_tree([])}</p:cSld>{mapping}<p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst><p:txStyles><p:titleStyle/><p:bodyStyle/><p:otherStyle/></p:txStyles></p:sldMaster>')
        z.writestr("ppt/slideMasters/_rels/slideMaster1.xml.rels",rels([("rId1","slideLayout","../slideLayouts/slideLayout1.xml"),("rId2","theme","../theme/theme1.xml")]))
        put("ppt/slideLayouts/slideLayout1.xml",f'<p:sldLayout {NS} type="blank" preserve="1"><p:cSld name="Blank">{sp_tree([])}</p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sldLayout>')
        z.writestr("ppt/slideLayouts/_rels/slideLayout1.xml.rels",rels([("rId1","slideMaster","../slideMasters/slideMaster1.xml")]))
        put("ppt/theme/theme1.xml",THEME)
        put("ppt/notesMasters/notesMaster1.xml",f'<p:notesMaster {NS}><p:cSld>{sp_tree([])}</p:cSld>{mapping}<p:notesStyle/></p:notesMaster>')
        z.writestr("ppt/notesMasters/_rels/notesMaster1.xml.rels",rels([("rId1","theme","../theme/theme1.xml")]))
        for i,p in enumerate(pages,1):
            put(f"ppt/slides/slide{i}.xml",f'<p:sld {NS}><p:cSld name="{escape(p.title,quote=True)}"><p:bg><p:bgPr><a:solidFill><a:srgbClr val="FFFFFF"/></a:solidFill><a:effectLst/></p:bgPr></p:bg>{sp_tree(p.items)}</p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>')
            z.writestr(f"ppt/slides/_rels/slide{i}.xml.rels",rels([("rId1","slideLayout","../slideLayouts/slideLayout1.xml"),("rId2","notesSlide",f"../notesSlides/notesSlide{i}.xml"),("rIdLogo","image","../media/aureka-logo.png")]))
            paragraphs = ''.join(f'<a:p><a:r><a:rPr lang="en-US"/><a:t>{escape(line)}</a:t></a:r></a:p>' for line in p.notes.splitlines())
            put(f"ppt/notesSlides/notesSlide{i}.xml",f'<p:notes {NS}><p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/><p:sp><p:nvSpPr><p:cNvPr id="2" name="Notes"/><p:cNvSpPr/><p:nvPr><p:ph type="body" idx="1"/></p:nvPr></p:nvSpPr><p:spPr/><p:txBody><a:bodyPr/><a:lstStyle/>{paragraphs}</p:txBody></p:sp></p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:notes>')
            z.writestr(f"ppt/notesSlides/_rels/notesSlide{i}.xml.rels",rels([("rId1","slide",f"../slides/slide{i}.xml"),("rId2","notesMaster","../notesMasters/notesMaster1.xml")]))
    return out.getvalue()
