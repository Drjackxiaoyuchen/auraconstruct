"""Shared geometry for SVG preview and native, editable DrawingML.

This implements a documented subset of SBOL Visual sequence-feature glyphs.
It does not serialize an SBOL RDF design or infer regulatory interactions.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from html import escape
import base64
import math
import textwrap

from .model import ROLES, validate
from .brand import AUREKA_COLORS, PURPLE, DEEP_PURPLE, YELLOW, INK, MUTED, FAINT, FONT, LOGO
from .details import category, summary, position_text, short_sequence

W, H = 1440, 810
PALETTES = {
    "aureka": AUREKA_COLORS,
    "paper": ["#247C80", "#D9A83A", "#4678B2", "#C66358", "#8A79A8", "#63856C", "#758394"],
    "colorblind": ["#009E73", "#E69F00", "#0072B2", "#D55E00", "#CC79A7", "#56B4E9", "#777777"],
    "mono": ["#333333"] * 7,
}
COLORS = dict(zip(["promoter", "rbs", "cds", "terminator", "origin", "operator", "generic"], range(7)))
LABELS = {"promoter": "Promoter", "rbs": "Ribosome entry site", "cds": "Coding sequence",
          "terminator": "Terminator", "origin": "Replication origin", "operator": "Operator",
          "primer": "Primer binding site", "scar": "Assembly scar", "ncrna": "Non-coding RNA",
          "recombination": "Recombination site", "polya": "PolyA site", "generic": "Unspecified"}
LABELS.update(region="Unspecified region", engineered_region="Engineered region",
              spacer="Inert DNA spacer", nuclease_site="Nuclease cleavage site")


@dataclass
class Primitive:
    kind: str
    x: float
    y: float
    w: float = 0
    h: float = 0
    fill: str = "none"
    stroke: str = "none"
    sw: float = 2.2
    commands: list = field(default_factory=list)
    text: str = ""
    size: float = 18
    bold: bool = False
    align: str = "left"
    name: str = ""
    group: str = ""
    dashed: bool = False


@dataclass
class Page:
    title: str
    items: list[Primitive] = field(default_factory=list)
    notes: str = ""

    def text(self, text, x, y, w, size=18, color=INK, bold=False, align="left", group="", h=None):
        self.items.append(Primitive("text", x, y, w, h or size * 1.45, fill=color,
                                    text=str(text), size=size, bold=bold, align=align, group=group, name=str(text)))

    def line(self, x, y, x2, y2, color=INK, sw=2.2, group="", dashed=False):
        self.items.append(Primitive("path", min(x, x2), min(y, y2), max(abs(x2-x), 1), max(abs(y2-y), 1),
                                    stroke=color, sw=sw, commands=[("M", x, y), ("L", x2, y2)],
                                    group=group, dashed=dashed, name="DNA backbone" if not group else "glyph stroke"))


def color_for(f, palette):
    return f.color or PALETTES[palette][COLORS.get(f.role, 6)]


def _path(page, points, fill="none", stroke=INK, sw=2.2, group="", name="glyph"):
    coords = []
    for p in points:
        coords.extend(zip(p[1::2], p[2::2]))
    xs, ys = zip(*coords) if coords else ([0, 1], [0, 1])
    page.items.append(Primitive("path", min(xs), min(ys), max(max(xs)-min(xs), 1), max(max(ys)-min(ys), 1),
                                fill, stroke, sw, points, group=group, name=name))


def glyph(page, role, x, y, width=90, color=INK, strand=1, group=""):
    """Draw native paths centered on the DNA backbone. Reverse strand rotates glyphs."""
    flip = -1 if strand == -1 else 1
    def path(cmds, fill="none", stroke=color, sw=2.8):
        transformed = []
        for cmd in cmds:
            vals = list(cmd[1:])
            for i in range(0, len(vals), 2):
                vals[i] = x + flip * vals[i]
                vals[i + 1] = y + flip * vals[i + 1]
            transformed.append((cmd[0], *vals))
        _path(page, transformed, fill, stroke, sw, group, LABELS.get(role, "Unspecified"))
    half = width / 2
    if role == "promoter":
        path([("M", -19, 0), ("L", -19, -42), ("L", 24, -42),
              ("M", 10, -54), ("L", 24, -42), ("L", 10, -30)])
    elif role == "rbs":
        path([("M", -22, 0), ("L", -22, -7), ("C", -22, -36, 22, -36, 22, -7),
              ("L", 22, 0), ("Z",)], "#FFFFFF")
    elif role == "cds":
        head = min(22, width * .32)
        path([("M", -half, -19), ("L", half-head, -19), ("L", half, 0),
              ("L", half-head, 19), ("L", -half, 19), ("Z",)], color, INK, 1.6)
    elif role == "terminator":
        path([("M", 0, 0), ("L", 0, -44), ("M", -22, -44), ("L", 22, -44)])
    elif role == "origin":
        k, r = .55228475 * 24, 24
        path([("M", -r, 0), ("C", -r, -k, -k, -r, 0, -r),
              ("C", k, -r, r, -k, r, 0), ("C", r, k, k, r, 0, r),
              ("C", -k, r, -r, k, -r, 0), ("Z",)], "#FFFFFF")
    elif role == "region":
        path([("M", -half+18, -19), ("L", half, -19), ("L", half, 19),
              ("L", -half+18, 19), ("C", -half-8, 19, -half-8, -19, -half+18, -19), ("Z",)], "#FFFFFF")
    elif role == "engineered_region":
        path([("M", -half, -19), ("L", half, -19), ("L", half, 19), ("L", -half, 19), ("Z",)], "#FFFFFF")
    elif role == "spacer":
        glyph(page,"origin",x,y,48,color,strand,group)
        path([("M", -14, -14), ("L", 14, 14), ("M", -14, 14), ("L", 14, -14)])
    elif role == "nuclease_site":
        path([("M", 0, 0), ("L", 0, -34), ("M", -13, -47), ("L", 13, -21),
              ("M", -13, -21), ("L", 13, -47)])
    elif role == "operator":
        path([("M", -18, -27), ("L", -18, 0), ("L", 18, 0), ("L", 18, -27)])
    elif role == "primer":
        path([("M", -24, -15), ("L", 24, -15), ("M", 12, -25), ("L", 24, -15), ("L", 12, -5)])
    elif role == "scar":
        path([("M", -21, -6), ("L", 21, -6), ("M", -21, 6), ("L", 21, 6)])
    elif role == "recombination":
        path([("M", -20, -23), ("L", 20, 0), ("L", -20, 23), ("Z",)], "#FFFFFF")
    elif role == "polya":
        path([("M", -28, -16), ("L", 28, -16), ("L", 28, 16), ("L", -28, 16), ("Z",)], "#FFFFFF", "none", 0)
        page.text("AAA", x-28, y-17, 56, 23, color, True, "center", group)
    elif role == "ncrna":
        path([("M", -38, 0), ("L", -38, -15),
              ("C", -32, -35, -26, -5, -19, -21),
              ("C", -12, -38, -7, -5, 0, -21),
              ("C", 7, -38, 12, -5, 19, -21),
              ("C", 26, -38, 32, -5, 38, -15),
              ("L", 38, 0), ("Z",)], "#FFFFFF")
    else:
        # Preferred SBOL Visual Unspecified glyph: a diamond with a question mark.
        path([("M", 0, -26), ("L", 26, 0), ("L", 0, 26), ("L", -26, 0), ("Z",)], "#FFFFFF")
        page.text("?", x-10, y-16, 20, 23, color, True, "center", group)
    if strand == 0 and role in ("promoter","rbs","cds","terminator","primer","ncrna","recombination"):
        page.text("?", x + half + 3, y-10, 16, 14, MUTED, group=group)


def _header(c, page_number, page_count, layout, selected):
    title = c.name if len(c.name) <= 70 else c.name[:67] + "..."
    p = Page(title)
    p.text(title, 74, 43, 1288, 33, bold=True, h=48)
    p.text(f"{c.length:,} bp   /   {c.topology} DNA   /   {selected} of {len(c.features)} features shown", 76, 98, 1280, 17, MUTED)
    if c.description:
        p.text(textwrap.shorten(c.description,width=160,placeholder="…"),76,120,1288,12,MUTED)
    p.line(76, 141, 1364, 141, FAINT, 1)
    p.line(76, 141, 150, 141, PURPLE, 4)
    p.line(150, 141, 183, 141, YELLOW, 4)
    p.text("SCHEMATIC  /  NOT TO SCALE" if layout == "schematic" else "SEQUENCE COORDINATES  /  1-BASED INCLUSIVE",
           76, 765, 490, 12, MUTED)
    p.items.append(Primitive("image", 629, 756, 182, 36, name="Aureka wordmark"))
    p.text(f"{page_number} / {page_count}", 1264, 765, 100, 14, MUTED, align="right")
    if c.provenance:
        label = c.provenance.get("display_citation", "Public sequence example")
        p.text(label[:150], 76, 735, 1288, 11, MUTED)
    p.notes = ("Generated by AuraConstruct. Glyphs implement a subset of SBOL Visual. "
               "https://sbolstandard.org/visual-specification/\nVisual reference: "
               "https://github.com/VoigtLab/dnaplotlib and Der et al., DOI:10.1021/acssynbio.6b00252.\n"
               f"Input: {c.source_name}; {c.source_format}; sequence length: {c.length} bp.\n"
               "No regulatory interactions or biological function were inferred from feature order.\n")
    if c.provenance:
        import json
        p.notes += "\nPublic demo provenance: " + json.dumps(c.provenance, ensure_ascii=False) + "\n"
    p.notes += "\nBranding follows the owner-supplied Aureka 2026 presentation template. Original Aureka wordmark retained.\n"
    return p


def _coordinate(f):
    coords = ", ".join(f"{a+1:,}..{b:,}" for a, b in f.segments)
    return ("complement " if f.strand == -1 else "") + coords + (" (fuzzy)" if f.fuzzy else "")


def _feature_notes(p, features):
    for f in features:
        p.notes += f"\n{f.id}: {f.label}; {_coordinate(f)}; role={f.role}; role source={f.role_source}; annotation source={f.source}"
        original=f.qualifiers.get("label",[])
        if isinstance(original,str):original=[original]
        if original and " / ".join(original)!=f.label:
            p.notes += "; original label: " + " / ".join(original)
        caption, caption_source=summary(f)
        if caption:p.notes += f"; caption ({caption_source}): {caption}"


def build_pages(c, layout="schematic", palette="aureka", coordinates=False, title=None, detail="overview"):
    validate(c)
    if layout not in ("schematic", "proportional") or palette not in PALETTES or detail not in ("overview","detailed"):
        raise ValueError("Unknown layout or palette.")
    features = sorted([f for f in c.features if f.visible], key=lambda f: (f.start, f.end, f.id))
    if len(features) > 5000:
        raise ValueError("Choose at most 5,000 illustrated features.")
    if layout == "proportional":
        return proportional_pages(c, features, palette, title, detail)
    if detail == "detailed":
        return detailed_pages(c, features, palette, title)
    # Eight parts per row and two rows per page keep every part editable/readable.
    count = max(1, math.ceil(len(features) / 16))
    pages = []
    for pg in range(count):
        chunk = features[pg*16:(pg+1)*16]
        p = _header(c, pg+1, count, layout, len(features))
        if title:
            p.items[0].text = title[:100]
        if not chunk:
            p.line(140, 365, 1300, 365, INK, 2)
            p.text("Unannotated DNA", 470, 395, 500, 22, MUTED, align="center")
        rows = math.ceil(len(chunk) / 8)
        for row in range(rows):
            subset = chunk[row*8:(row+1)*8]
            step = min(195, 1220 / len(subset))
            left = (W - step*len(subset)) / 2
            y = 300 + row * 245 if rows > 1 else 370
            p.line(left-12, y, left+step*len(subset)+12, y, INK, 2)
            if row or pg:
                p.line(left-27, y-7, left-20, y+7, MUTED, 1.5)
                p.line(left-20, y-7, left-13, y+7, MUTED, 1.5)
            if row < rows-1 or pg < count-1:
                end = left+step*len(subset)
                p.line(end+15, y-7, end+22, y+7, MUTED, 1.5)
                p.line(end+22, y-7, end+29, y+7, MUTED, 1.5)
            for i, f in enumerate(subset):
                x, g = left+(i+.5)*step, f.id
                glyph(p, f.role, x, y, min(106, step*.7), color_for(f, palette), f.strand, g)
                lines = textwrap.wrap(f.label, width=max(12, int(step/9)), break_long_words=True)[:3]
                if len(textwrap.wrap(f.label, width=max(12, int(step/9)))) > 3:
                    lines[-1] = lines[-1][:-1] + "…"
                for j, line in enumerate(lines):
                    p.text(line, x-step/2+5, y+64+j*21, step-10, 17, bold=f.role=="cds", align="center", group=g)
                if coordinates:
                    coord = _coordinate(f)
                    if len(coord) > 28:
                        coord = f"{f.length:,} bp / {len(f.segments)} segments"
                    p.text(coord, x-step/2, y+64+len(lines)*21, step, 11, MUTED, align="center", group=g)
            # Modules are explicit user assignments, never guessed from proximity.
            i = 0
            while i < len(subset):
                f = subset[i]
                if not f.module:
                    i += 1
                    continue
                j = i+1
                while j < len(subset) and subset[j].module == f.module:
                    j += 1
                a, b, yy = left+i*step+8, left+j*step-8, y-92
                p.line(a, yy+6, a, yy, FAINT, 1.5)
                p.line(a, yy, b, yy, FAINT, 1.5)
                p.line(b, yy, b, yy+6, FAINT, 1.5)
                max_chars = max(8, int((b-a)/7.5))
                module_label = f.module if len(f.module) <= max_chars else f.module[:max_chars-1] + "…"
                p.text(module_label, a, yy-29, b-a, 14, MUTED, align="center")
                i = j
        _feature_notes(p, chunk)
        pages.append(p)
    return pages


def detailed_pages(c,features,palette,title=None):
    """Four parts per row, with room for sequence-grounded teaching annotations."""
    chunks=[features[i:i+8] for i in range(0,len(features),8)] or [[]]
    # Avoid leaving one or two isolated parts on an otherwise empty final slide.
    if len(chunks)>1 and len(chunks[-1])<4:
        tail=chunks[-2]+chunks[-1];split=math.ceil(len(tail)/2)
        chunks[-2:]=[tail[:split],tail[split:]]
    count=len(chunks)
    pages=[]
    for pg in range(count):
        chunk=chunks[pg]
        p=_header(c,pg+1,count,"schematic",len(features))
        if title:p.items[0].text=title[:100]
        if not chunk:
            p.line(140,365,1300,365,INK,2)
            p.text("Unannotated DNA",470,395,500,22,MUTED,align="center")
        rows=math.ceil(len(chunk)/4)
        columns=math.ceil(len(chunk)/rows) if rows else 4
        for row in range(rows):
            subset=chunk[row*columns:(row+1)*columns]
            step=min(310,1220/len(subset));left=(W-step*len(subset))/2
            y=250+row*275 if rows>1 else 350
            p.line(left-12,y,left+step*len(subset)+12,y,INK,2)
            if row or pg:
                p.line(left-27,y-7,left-20,y+7,MUTED,1.5);p.line(left-20,y-7,left-13,y+7,MUTED,1.5)
            if row<rows-1 or pg<count-1:
                end=left+step*len(subset)
                p.line(end+15,y-7,end+22,y+7,MUTED,1.5);p.line(end+22,y-7,end+29,y+7,MUTED,1.5)
            for i,f in enumerate(subset):
                x=left+(i+.5)*step;g=f.id;col=x-step/2+9;width=step-18
                glyph(p,f.role,x,y,112,color_for(f,palette),f.strand,g)
                lines=textwrap.wrap(f.label,width=int(width/10),break_long_words=True)
                shown=lines[:2]
                if len(lines)>2:shown[-1]=shown[-1][:-1]+"…"
                for j,line in enumerate(shown):
                    p.text(line,col,y+61+j*22,width,18,bold=f.role=="cds",align="center",group=g)
                p.text(position_text(f),col,y+113,width,12,MUTED,align="center",group=g)
                cat=category(f)
                if f.module:cat += " / "+f.module
                p.text(textwrap.shorten(cat,width=46,placeholder="…"),col,y+131,width,12,DEEP_PURPLE,align="center",group=g)
                caption,source=summary(f)
                if caption:
                    notes=textwrap.wrap(caption,width=int(width/6.8),break_long_words=True)
                    for j,line in enumerate(notes[:2]):
                        if j==1 and len(notes)>2:line=line[:-1]+"…"
                        p.text(line,col,y+152+j*16,width,12,MUTED,align="center",group=g)
                seq=short_sequence(c,f)
                if seq:p.text(seq,col,y+189,width,12,INK,align="center",group=g)
        _feature_notes(p,chunk)
        p.notes += "\nDetailed schematic: coordinates, lengths and short sequences come from the imported record. Source feature notes and user captions remain distinct. Sequence-order layout separates overlapping features for readability; it does not assert that they are disjoint. Label-derived categories do not establish biological function or exact cut positions."
        pages.append(p)
    return pages


def proportional_pages(c, features, palette, title=None, detail="overview"):
    # Reserve each label's horizontal footprint when packing lanes.
    x0, span, scale = 110, 1220, 1220 / c.length
    lanes = []
    placements = []
    for f in features:
        left = max(x0, x0+f.start*scale-70)
        right = min(x0+span, x0+f.end*scale+70)
        lane = next((i for i, occupied in enumerate(lanes) if all(right < a-18 or left > b+18 for a,b in occupied)), len(lanes))
        if lane == len(lanes):
            lanes.append([])
        lanes[lane].append((left,right))
        placements.append((f,lane))
    per_page=2 if detail=="detailed" else 3
    count = max(1, math.ceil(len(lanes)/per_page))
    pages = []
    for pg in range(count):
        p = _header(c, pg+1, count, "proportional", len(features))
        if title:
            p.items[0].text = title[:100]
        # A second, fine track below each glyph encodes the exact segment interval.
        for lane in range(pg*per_page, min((pg+1)*per_page, max(1,len(lanes)))):
            y = 255+(lane % per_page)*(220 if detail=="detailed" else 155)
            p.line(x0, y, x0+span, y, FAINT, 1.5)
            for f, assigned in placements:
                if assigned != lane:
                    continue
                for si, (a,b) in enumerate(f.segments):
                    mid = x0+(a+b)/2*scale
                    width = max(14, min(260, (b-a)*scale))
                    strand = f.segment_strands[si] if f.segment_strands else f.strand
                    glyph(p, f.role, mid, y, width if f.role in ("cds","generic","ncrna") else 60,
                          color_for(f,palette), strand, f.id)
                    p.line(x0+a*scale, y+65, x0+b*scale, y+65, color_for(f,palette), 4, f.id)
                    lx = max(76, min(mid-110, W-296))
                    label = f.label if si == 0 else f"{f.label} (join {si+1})"
                    p.text(textwrap.shorten(label,width=30,placeholder="…"), lx,y+76,220,14,align="center",group=f.id)
                    if detail=="detailed":
                        p.text(f"{a+1:,}..{b:,} / {b-a:,} bp",lx,y+97,220,11,MUTED,align="center",group=f.id)
                        p.text(textwrap.shorten(category(f),width=34,placeholder="…"),lx,y+115,220,11,DEEP_PURPLE,align="center",group=f.id)
            if not features:
                p.text("Unannotated DNA", 470, y+55, 500, 22, MUTED, align="center")
        p.line(x0, 707, x0+span, 707, MUTED, 1)
        for i in range(6):
            x=x0+i*span/5
            pos = 1 if i == 0 else round(c.length*i/5)
            p.line(x,707,x,713,MUTED,1)
            p.text(f"{pos:,}",x-60,717,120,12,MUTED,align="center")
        _feature_notes(p,[f for f,l in placements if pg*per_page<=l<(pg+1)*per_page])
        p.notes += "\nProportional view: colored interval tracks carry exact segment coordinates; glyphs have minimum/maximum widths for readability. Separate lanes do not imply separate DNA molecules."
        pages.append(p)
    return pages


def to_svg(page):
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img">',
             f"<title>{escape(page.title)}</title>", '<rect width="100%" height="100%" fill="white"/>']
    for item in page.items:
        if item.kind == "text":
            anchor = {"left":"start", "center":"middle", "right":"end"}[item.align]
            xx = item.x + (item.w/2 if item.align=="center" else item.w if item.align=="right" else 0)
            parts.append(f'<text x="{xx:g}" y="{item.y+item.size:g}" fill="{item.fill}" font-family="Arial, sans-serif" '
                         f'font-size="{item.size}" font-weight="{700 if item.bold else 400}" text-anchor="{anchor}">{escape(item.text)}</text>')
        elif item.kind == "image":
            encoded = base64.b64encode(LOGO.read_bytes()).decode()
            parts.append(f'<image x="{item.x:g}" y="{item.y:g}" width="{item.w:g}" height="{item.h:g}" href="data:image/png;base64,{encoded}"/>')
        elif item.kind == "path":
            d = " ".join(cmd[0]+" "+" ".join(f"{v:g}" for v in cmd[1:]) for cmd in item.commands)
            parts.append(f'<path d="{d}" fill="{item.fill}" stroke="{item.stroke}" stroke-width="{item.sw}" '
                         f'stroke-linejoin="round" stroke-linecap="round"'+ (' stroke-dasharray="5 5"' if item.dashed else '') + '/>')
    return "\n".join(parts+["</svg>"])
