from pathlib import Path
from auraconstruct.demos import load_demo
from auraconstruct.scene import build_pages,to_svg
from auraconstruct.pptx import to_pptx
out=Path(__file__).resolve().parents[1] / 'examples'
out.mkdir(exist_ok=True)
all_pages=[]
for name in ['ytk001','myt001','myt075','myt095','ysd891']:
 c=load_demo(name)
 pages=build_pages(c,layout='schematic')
 all_pages+=pages
 (out/f'{c.name}_Aureka.pptx').write_bytes(to_pptx(pages))
 for i,p in enumerate(pages):
  (out/f'{c.name}_{i+1}.svg').write_text(to_svg(p))
 if name=='ytk001':
  (out/'demo.pptx').write_bytes(to_pptx(pages))
  (out/'demo.svg').write_text(to_svg(pages[0]))
(out/'AuraConstruct_Aureka_Public_Demos.pptx').write_bytes(to_pptx(all_pages))
print(f'{len(all_pages)} public demo slides')

(out/'AuraConstruct_Editable_Demo.pptx').write_bytes((out/'demo.pptx').read_bytes())

# Detailed teaching examples preserve source coordinates and annotation callouts.
detailed=[]
for demo_id in ('myt075','myt095'):
 c=load_demo(demo_id)
 pages=build_pages(c,layout='schematic',detail='detailed')
 detailed.extend(pages)
 (out/f'{c.name}_Detailed.pptx').write_bytes(to_pptx(pages))
 for i,p in enumerate(pages,1):
  (out/f'{c.name}_Detailed_{i}.svg').write_text(to_svg(p))
(out/'AuraConstruct_Detailed_MYT_Annotations.pptx').write_bytes(to_pptx(detailed))

# Dense real-world source: one readable architecture slide, then every annotation.
core=load_demo('ysd328')
overview=build_pages(core,layout='schematic',coordinates=True)
full=load_demo('ysd328-all')
annotations=build_pages(full,layout='schematic',detail='detailed')
(out/'AuraConstruct_Complex_YSD328.pptx').write_bytes(to_pptx(overview+annotations))
(out/'pYSD328_Overview.svg').write_text(to_svg(overview[0]))
(out/'pYSD328_All_Annotations.pptx').write_bytes(to_pptx(annotations))
for i,p in enumerate(annotations,1):
 (out/f'pYSD328_Detailed_{i}.svg').write_text(to_svg(p))
print(f'Complex construct: {len(overview)} overview + {len(annotations)} detailed slides; {len(full.features)} source annotations')

single_line=[]
for demo_id,name in [('myt095','pMYT095'),('ysd328','pYSD328'),('ysd328-all','pYSD328_All_70')]:
 pages=build_pages(load_demo(demo_id),layout='singleline')
 single_line.extend(pages)
 (out/f'{name}_Single_Line.pptx').write_bytes(to_pptx(pages))
 (out/f'{name}_Single_Line.svg').write_text(to_svg(pages[0]))
(out/'AuraConstruct_Single_Line_Demos.pptx').write_bytes(to_pptx(single_line))
print(f'{len(single_line)} single-line constructs; one backbone per slide')
