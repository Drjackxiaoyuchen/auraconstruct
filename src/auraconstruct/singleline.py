"""One continuous, sequence-scaled DNA backbone with collision-free label tiers."""
from __future__ import annotations

import math

from .brand import INK, MUTED, FAINT, PURPLE
from .scene import W, glyph, color_for, _header, _feature_notes, _path


def _label_width(label, size):
    # Conservative Arial widths. Full labels are retained in the feature notes.
    units = sum(.3 if ch in " ilI.,'" else .9 if ch in "MW@" else .59 for ch in label)
    return max(38, units * size + 12)


def _short_label(text,size,limit=204,chars=28):
    clean=' '.join(text.split())
    shown=clean if len(clean)<=chars else clean[:chars-1]+'…'
    while _label_width(shown,size)>limit:
        shown=shown[:-2]+'…'
    return shown,_label_width(shown,size)


def _labels(features, scale, left, right):
    size = 15 if len(features) <= 35 else 13
    labels = []
    for f in features:
        a,b=max(f.segments,key=lambda s:s[1]-s[0])
        name,width = _short_label(f.label,size)
        labels.append(dict(feature=f, text=name, width=width,
                           anchor=left+(a+b)/2*scale))
    labels.sort(key=lambda x:(x['anchor'], x['feature'].id))
    # Keep leaders vertical whenever the local label density allows it.
    natural=[]
    for l in labels:
        x=max(left,min(right-l['width'],l['anchor']-l['width']/2))
        row=next((i for i,end in enumerate(natural) if end+12<=x),len(natural))
        if row==len(natural):natural.append(left-12)
        natural[row]=x+l['width'];l['x']=x;l['row']=row
    if len(natural)<=6:
        return labels,max(1,len(natural)),size
    # Dense source records use bounded tiers rather than wrapping the DNA.
    rows = max(1, math.ceil(sum(l['width']+12 for l in labels)/(right-left)))
    while True:
        tiers = [labels[i::rows] for i in range(rows)]
        if all(sum(l['width']+12 for l in tier)-12 <= right-left for tier in tiers): break
        rows += 1
    if rows > 18:
        raise ValueError("Too many labels for a readable single line. Hide secondary features or shorten labels; the backbone will not wrap.")
    for row,tier in enumerate(tiers):
        edge=left
        for l in tier:
            l['x']=max(edge, min(right-l['width'], l['anchor']-l['width']/2))
            edge=l['x']+l['width']+12
        edge=right
        for l in reversed(tier):
            l['x']=min(l['x'],edge-l['width']);edge=l['x']-12
        edge=left
        for l in tier:
            l['x']=max(edge,l['x']);edge=l['x']+l['width']+12
            l['row']=row
    return labels,rows,size


def _compact_glyph(page,f,a,b,y,color,container=False,strand=None):
    strand=f.strand if strand is None else strand
    width=max(4,b-a)
    mid=(a+b)/2
    if f.role in ('region','engineered_region'):
        h=13 if container else 8
        r=min(5,width/3)
        commands=[("M",a+r,y-h),("L",b,y-h),("L",b,y+h),("L",a+r,y+h),
                  ("C",a-r/3,y+h,a-r/3,y-h,a+r,y-h),("Z",)]
        if strand==-1:
            commands=[(cmd[0],*[a+b-v if j%2==0 else v for j,v in enumerate(cmd[1:])]) for cmd in commands]
        _path(page,commands,
              "#FFFFFF" if not container else "none",color,1.5,f.id,"Region")
        return
    start=len(page.items)
    factor=.46
    horizontal=factor
    if f.role!='cds':
        nominal={'promoter':43,'rbs':44,'terminator':44,'origin':48,'operator':36,
                 'primer':48,'scar':42,'recombination':40,'polya':56,'ncrna':76,
                 'spacer':48,'nuclease_site':26}.get(f.role,52)
        desired=max(7,min(22,width*.85))
        if f.role=='origin':desired=max(14,desired)
        if f.role=='ncrna':desired=max(12,desired)
        horizontal=desired/nominal
        if f.role in ('origin','ncrna','generic','recombination','spacer'):
            factor=horizontal
        if f.role=='ncrna':factor=max(.24,factor)
    # Existing SBOL paths are scaled consistently; CDS width tracks its DNA span.
    glyph(page,f.role,0,0,max(5,width)/factor,color,strand,f.id)
    for item in page.items[start:]:
        item.x=mid+item.x*horizontal;item.y=y+item.y*factor
        item.w*=horizontal;item.h*=factor;item.size*=min(horizontal,factor);item.sw*=min(horizontal,factor)
        item.sw=max(.8,item.sw)
        item.commands=[(cmd[0],*[mid+v*horizontal if j%2==0 else y+v*factor for j,v in enumerate(cmd[1:])]) for cmd in item.commands]
        if container and item.kind=='path' and f.role=='cds':
            item.fill='none'
            # A parent outline encloses its overlapping subregions on this same backbone.
            item.y=y+(item.y-y)*1.5;item.h*=1.5
            item.commands=[(cmd[0],*[v if j%2==0 else y+(v-y)*1.5 for j,v in enumerate(cmd[1:])]) for cmd in item.commands]


def single_line_pages(c,features,palette,title=None):
    left,right=82,W-82
    scale=(right-left)/c.length
    labels,rows,size=_labels(features,scale,left,right)
    pitch=25 if len(features)>35 else 31
    y=max(390,190+rows*pitch)
    p=_header(c,1,1,'singleline',len(features))
    if title:p.items[0].text=title[:100]
    footer=next(i for i in p.items if i.kind=='text' and i.y==765 and i.x==76)
    footer.text='SINGLE LINE  /  SEQUENCE-SCALED BACKBONE'
    # All features stay on this one backbone, including joined and reverse-strand parts.
    p.line(left,y,right,y,INK,1.8);p.items[-1].name='Continuous DNA backbone'
    for x in (left,right):
        p.line(x,y-5,x,y+5,MUTED,1)
        p.items[-1].name='Backbone end'
    segments=[(f,a,b,f.segment_strands[j] if f.segment_strands else f.strand)
              for f in features for j,(a,b) in enumerate(f.segments)]
    for f,a,b,strand in sorted(segments,key=lambda s:-(s[2]-s[1])):
        container=any(other.id!=f.id and a<=u<v<=b and (u,v)!=(a,b) for other,u,v,_ in segments)
        _compact_glyph(p,f,left+a*scale,left+b*scale,y,color_for(f,palette),container,strand)
    # Leaders and labels remain part of their editable feature group.
    for l in labels:
        f=l['feature'];ly=y-63-l['row']*pitch
        cx=l['x']+l['width']/2
        p.line(l['anchor'],y-30,l['anchor'],ly+size+9,FAINT,1,f.id)
        if abs(cx-l['anchor'])>2:
            p.line(l['anchor'],ly+size+9,cx,ly+size+3,FAINT,1,f.id)
        p.text(l['text'],l['x'],ly,l['width'],size,INK,f.role=='cds','center',f.id)
    if not features:p.text('Unannotated DNA',left,y-57,right-left,18,MUTED,align='center')
    axis=y+43
    p.line(left,axis,right,axis,'#B4B8C0',1);p.items[-1].name='Base-pair axis'
    raw=c.length/6
    power=10**math.floor(math.log10(max(1,raw)))
    step=min((1,2,5,10),key=lambda k:abs(k*power-raw))*power
    ticks=list(range(0,c.length+1,max(1,int(step))))
    if c.length-ticks[-1]>c.length*.08:ticks.append(c.length)
    for pos in ticks:
        x=left+pos*scale
        p.line(x,axis,x,axis+5,'#B4B8C0',1);p.items[-1].name='Axis tick'
        p.text(f'{pos:,}',x-30,axis+9,60,11,MUTED,align='center')
    p.text('bp',right-16,axis+27,32,10,MUTED,align='right')
    # Module assignments are explicit metadata; brackets encode their source spans.
    modules=[]
    for f,a,b,_ in sorted(segments,key=lambda s:(s[1],s[2])):
        if not f.module:continue
        if modules and modules[-1][0]==f.module:
            modules[-1][2]=max(modules[-1][2],b)
        else:modules.append([f.module,a,b])
    occupied=[]
    for name,a,b in modules:
        x1,x2=left+a*scale,left+b*scale
        label,width=_short_label(name,14,limit=300,chars=35)
        width=max(42,width)
        x=max(left,min(right-width,(x1+x2-width)/2))
        row=next((i for i,spans in enumerate(occupied) if all(x+width+10<u or x>v+10 for u,v in spans)),len(occupied))
        if row==len(occupied):occupied.append([])
        occupied[row].append((x,x+width))
        yy=axis+49+row*33
        if yy+27>725:
            raise ValueError('Too many overlapping module brackets for one line. Combine module names or hide secondary features.')
        p.line(x1,yy-5,x1,yy,PURPLE,1);p.line(x1,yy,x2,yy,PURPLE,1);p.line(x2,yy,x2,yy-5,PURPLE,1)
        p.text(label,x,yy+5,width,14,PURPLE,True,'center')
    _feature_notes(p,features)
    p.notes += ('\nSingle-line view: exactly one continuous DNA backbone per construct. Glyph centers and CDS spans use the imported sequence coordinates. '
                'Small symbols have a minimum readable size. Parent feature outlines and overlapping subregions share the same backbone. '
                'Labels are arranged in tiers above the backbone; long display labels may shorten, with complete labels retained here. '
                'Axis values are sequence-boundary coordinates (0 to sequence length); feature intervals in notes/table are 1-based inclusive. '
                'Module brackets use explicit module assignments, not inferred regulatory interactions. Compact labels keep full callouts in the review table and these notes.')
    return [p]
