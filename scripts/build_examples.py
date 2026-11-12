from pathlib import Path
from auraconstruct.demos import load_demo
from auraconstruct.scene import build_pages,to_svg
from auraconstruct.pptx import to_pptx
out=Path(__file__).resolve().parents[1] / 'examples'
out.mkdir(exist_ok=True)
all_pages=[]
for name in ['ytk001','myt001','ysd891']:
 c=load_demo(name)
 pages=build_pages(c)
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
