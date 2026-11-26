/* No external scripts, analytics, sequence storage, or remote annotation calls. */
const $=id=>document.getElementById(id);
const state={records:[],index:0,pages:[],page:0,options:{layout:'singleline',palette:'aureka',coordinates:false,detail:'detailed'}};
const roles={promoter:'Promoter',rbs:'Ribosome entry site',cds:'Coding sequence',terminator:'Terminator',origin:'Replication origin',operator:'Operator',primer:'Primer binding site',scar:'Assembly scar',ncrna:'Non-coding RNA',recombination:'Recombination site',polya:'PolyA site',generic:'Unspecified'};
Object.assign(roles,{region:'Unspecified region',engineered_region:'Engineered region',spacer:'Inert DNA spacer',nuclease_site:'Nuclease cleavage site'});
let palettes={aureka:['#4200AC','#F9AC2F','#6500FF','#FF6D8E','#6FC0A9','#8882BE','#555656']};
let roleColorIndices={promoter:0,rbs:1,cds:2,terminator:3,origin:4,operator:5,generic:6};
let annotationModes={default:{available:false},detailed:{available:false}},annotationRunning=false;
function syncAnnotationControls(){
  const mode=$('annotationMode').value;
  $('annotationMode').querySelector('[value="detailed"]').disabled=!annotationModes.detailed?.available;
  $('annotationMode').disabled=annotationRunning||!annotationModes.default?.available;
  $('plannotate').disabled=annotationRunning||!annotationModes[mode]?.available;
  $('annotationModeNote').textContent=annotationModes[mode]?.reason||'Checking search modes…';
}
function defaultColor(role){return (palettes[state.options.palette]||palettes.aureka)[roleColorIndices[role]??6];}
const headers={'X-AuraConstruct':'1'};
let renderTimer,renderVersion=0,reviewVersion=0;
const current=()=>state.records[state.index];

function notice(text,error=false){const n=$('notification');n.textContent=text;n.className=error?'error':'';n.hidden=!text;}
async function api(path,body,json=true){
  const response=await fetch(path,{method:'POST',headers:json?{...headers,'Content-Type':'application/json'}:headers,body:json?JSON.stringify(body):body});
  if(!response.ok){const e=await response.json();throw Error(e.error||'Request failed.');}
  return response;
}
function guarded(fn){return async (...args)=>{try{await fn(...args);}catch(e){notice(e.message,true);}};}
function optionsFor(record){return {record,options:state.options};}
function showAnnotationSummary(summary){
  const panel=$('annotationSummary');
  if(!summary||typeof summary!=='object'){panel.hidden=true;return;}
  const run=summary.last_run;panel.hidden=false;
  panel.classList.toggle('changed',run?.query_status==='changed');
  $('appliedMode').hidden=!run;$('appliedMode').textContent=run?.mode_label||'';
  $('runDetails').textContent=run?[run.engine_version||'Engine version not recorded',`Database ${run.database_version||'not recorded'}`,run.time_utc||'Time not recorded',run.features_added===null?null:`${run.features_added} predictions added by this run`].filter(Boolean).join(' / '):'No pLannotate run history is recorded. Feature annotations may still be present in the imported file.';
  $('queryStatus').textContent=run?.query_message||'';
  $('historyNote').textContent=run?`${summary.note} The search selector controls the next run.`:'Importing a file does not establish how its existing annotations were produced.';
}
function selectRecord(index){
  reviewVersion++;
  $('reviewDialog').close();
  state.index=index;state.page=0;
  const c=current();if(!c)return;
  $('annotationSummary').hidden=true;
  $('figureTitle').textContent=c.name;
  $('meta').textContent=`${c.length.toLocaleString()} bp / ${c.topology} / ${c.source_format} / ${c.source_name}`;
  $('topology').value=c.topology;
  const source=$('sequenceSource');source.replaceChildren();source.hidden=!c.provenance?.source_url;
  if(!source.hidden){const link=document.createElement('a');link.textContent=c.provenance.display_citation||'Public sequence source';if(/^https:\/\//.test(c.provenance.source_url))link.href=c.provenance.source_url;link.target='_blank';link.rel='noreferrer';source.append(link);}
  $('featureSearch').value='';updateTable();scheduleRender();
  $('warnings').replaceChildren(...c.warnings.map(w=>{const p=document.createElement('p');p.textContent=w;return p;}));
}
function setRecords(records){
  state.records=records;
  $('recordSelect').replaceChildren(...records.map((c,i)=>{const o=new Option(`${c.name} · ${c.length.toLocaleString()} bp`,String(i));return o;}));
  $('recordSelect').disabled=false;selectRecord(0);
}
function scheduleRender(){clearTimeout(renderTimer);renderTimer=setTimeout(guarded(render),150);}
async function render(){
  if(!current())return;
  const version=++renderVersion;
    const record=current(),snapshot=JSON.stringify(record);
    const res=await api('/api/render',optionsFor(record));
    const data=await res.json();if(version!==renderVersion||current()!==record||JSON.stringify(record)!==snapshot)return;
    showAnnotationSummary(data.annotation_summary);
  state.pages=data.pages;state.page=Math.min(state.page,data.pages.length-1);showPage();
}
function showPage(){
  // SVG is generated by the local server from escaped model text, never file-supplied markup.
  $('canvas').innerHTML=state.pages[state.page]||'';
  $('pageInfo').textContent=`${state.page+1} / ${state.pages.length||1}`;
  $('prevPage').disabled=state.page<=0;$('nextPage').disabled=state.page>=state.pages.length-1;
  $('viewLabel').textContent=state.options.layout==='singleline'?'Single line':state.options.layout==='schematic'?'Wrapped schematic':'Sequence coordinates';
  $('figureCaption').textContent=state.options.layout==='singleline'?'One continuous DNA backbone. Labels above, source bp axis and module brackets below. Full callouts remain in the table and PowerPoint notes.':state.options.layout==='schematic'?(state.options.detail==='detailed'?'Not to scale. Imported positions, lengths, notes and short sequences accompany editable SBOL glyphs.':'Not to scale. Every glyph and label remains editable in PowerPoint.'):'Colored interval tracks show exact spans. Glyph widths adjust for readability.';
}
function syncLayoutControls(){
  for(const b of document.querySelectorAll('[data-layout]'))b.classList.toggle('active',b.dataset.layout===state.options.layout);
  const single=state.options.layout==='singleline';$('detail').disabled=single;$('coordinates').disabled=single;
  $('singleLineNote').hidden=!single;
}
function td(child){const el=document.createElement('td');el.append(child);return el;}
function input(value,change,placeholder=''){
  const el=document.createElement('input');el.type='text';el.value=value;el.placeholder=placeholder;
  el.addEventListener('input',()=>change(el.value));el.addEventListener('change',()=>change(el.value));return el;
}
function updateTable(){
  const c=current();if(!c)return;
  updateVisibilityCount();
  const search=$('featureSearch').value.toLowerCase();
  const rows=c.features.filter(f=>`${f.label} ${f.role} ${f.module} ${f.source}`.toLowerCase().includes(search)).map(f=>{
    const row=document.createElement('tr');
    const shown=document.createElement('input');shown.type='checkbox';shown.checked=f.visible;shown.setAttribute('aria-label',`Show ${f.label}`);shown.addEventListener('change',()=>{f.visible=shown.checked;updateVisibilityCount();scheduleRender();});row.append(td(shown));
    const label=input(f.label,v=>{f.label=v;scheduleRender();});label.maxLength=240;label.setAttribute('aria-label','Feature label');row.append(td(label));
    const glyph=document.createElement('select');glyph.setAttribute('aria-label','Glyph role');
    for(const [role,name] of Object.entries(roles)){glyph.add(new Option(name,role));}glyph.value=f.role;
    glyph.addEventListener('change',()=>{f.role=glyph.value;f.role_source='user-assigned';scheduleRender();updateTable();});row.append(td(glyph));
    const pos=document.createElement('span');pos.className='position';pos.textContent=f.segments.map(([a,b])=>`${a+1}..${b}`).join(', ')+` / ${f.strand===1?'+':f.strand===-1?'−':'?'}`+(f.fuzzy?' ≈':'');row.append(td(pos));
    const color=document.createElement('input');color.type='color';color.value=f.color||defaultColor(f.role);color.setAttribute('aria-label',`Color for ${f.label}`);color.addEventListener('input',()=>{f.color=color.value;scheduleRender();});row.append(td(color));
    const module=input(f.module,v=>{f.module=v;scheduleRender();},'No module');module.maxLength=100;module.setAttribute('aria-label','Module name');row.append(td(module));
    const caption=input(f.caption||'',v=>{f.caption=v;f.caption_source='user-caption';scheduleRender();},'Use source note');caption.maxLength=400;caption.setAttribute('aria-label','Annotation callout');row.append(td(caption));
    const evidence=document.createElement('div');evidence.className='evidence'+(f.role_source==='label-heuristic'?' heuristic':'');
    const origin=document.createElement('span');origin.textContent=`${f.source} / ${f.role_source}`;evidence.append(origin);
    const review=document.createElement('button');review.className='review-button';review.textContent='Review evidence';review.setAttribute('aria-label',`Review evidence for ${f.label}`);
    review.addEventListener('click',guarded(()=>reviewFeature(f.id)));evidence.append(review);row.append(td(evidence));return row;
  });
  $('featureTable').replaceChildren(...rows);
}
async function reviewFeature(id){
  const version=++reviewVersion,record=current(),snapshot=JSON.stringify(record);
  const res=await api('/api/feature-review',{record,feature_id:id}),data=await res.json();
  if(version!==reviewVersion)return;
  if(current()!==record||JSON.stringify(record)!==snapshot)throw Error('The construct changed. Open the feature review again.');
  $('reviewTitle').textContent=data.label;
  $('reviewOrigin').textContent=`${data.type} / ${data.source} / glyph: ${data.role} (${data.role_source})`;
  $('reviewFragment').textContent=data.fragment_status;
  $('reviewNote').textContent=data.note;
  $('reviewQualifiers').textContent=JSON.stringify(data.qualifiers,null,2);
  $('reviewOverlapCount').textContent=`Overlapping annotations (${data.overlaps.length})`;
  $('reviewOverlaps').replaceChildren(...data.overlaps.map(o=>{const li=document.createElement('li');li.textContent=`${o.relation}: ${o.label} / ${o.type} / ${o.shared_bp} shared bp / ${o.source}${o.visible?'':' / hidden in figure'}`;return li;}));
  $('reviewDialog').showModal();
}
$('closeReview').addEventListener('click',()=>{reviewVersion++;$('reviewDialog').close();});
function updateVisibilityCount(){
  const c=current();if(!c)return;
  $('featureCount').textContent=`${c.features.filter(f=>f.visible).length} / ${c.features.length}`;
  $('selectAll').checked=c.features.every(f=>f.visible);
  $('selectAll').indeterminate=c.features.some(f=>f.visible)&&!$('selectAll').checked;
}
async function importFiles(files){
  if(!files.length)return;notice('Reading sequence files…');
  const form=new FormData();for(const f of files)form.append('files',f);
  const res=await api('/api/import',form,false);const data=await res.json();setRecords(data.records);
  notice(`Loaded ${data.records.length} construct${data.records.length===1?'':'s'}. Review annotation roles before exporting.`);
}
async function exportFile(fmt){
  if(!current())throw Error('Import a sequence or load the example first.');
  notice('Preparing export…');
  const records=(fmt==='json'||$('allRecords').checked)?state.records:[current()];
  const response=await api(`/api/export/${fmt}`,{records,options:state.options});
  const blob=await response.blob();const url=URL.createObjectURL(blob);
  const name=response.headers.get('Content-Disposition')?.match(/filename="?([^";]+)/)?.[1]||`auraconstruct.${fmt}`;
  const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  notice(fmt==='pptx'?'PowerPoint exported. Select a part group, then Ungroup to edit its individual strokes and label.':'Export ready.');
}
async function loadPublicDemo(id){
  const res=await fetch(`/api/demo?id=${encodeURIComponent(id)}`);if(!res.ok)throw Error((await res.json()).error);
  const data=await res.json();setRecords(data.records);notice('Public toolkit plasmid loaded. Review the source annotation and display choices before exporting.');
}
$('loadDemo').addEventListener('click',guarded(() => loadPublicDemo($('demoSelect').value)));
$('fileInput').addEventListener('change',guarded(e=>importFiles([...e.target.files])));
const drop=$('dropzone');for(const name of ['dragenter','dragover'])drop.addEventListener(name,e=>{e.preventDefault();drop.classList.add('drag');});
for(const name of ['dragleave','drop'])drop.addEventListener(name,e=>{e.preventDefault();drop.classList.remove('drag');});
drop.addEventListener('drop',guarded(e=>importFiles([...e.dataTransfer.files])));
$('recordSelect').addEventListener('change',e=>selectRecord(Number(e.target.value)));
$('topology').addEventListener('change',()=>{if(current()){current().topology=$('topology').value;selectRecord(state.index);}});
for(const button of document.querySelectorAll('[data-layout]'))button.addEventListener('click',()=>{state.options.layout=button.dataset.layout;state.page=0;syncLayoutControls();scheduleRender();});
$('palette').addEventListener('change',()=>{state.options.palette=$('palette').value;updateTable();scheduleRender();});
$('coordinates').addEventListener('change',()=>{state.options.coordinates=$('coordinates').checked;scheduleRender();});
$('detail').addEventListener('change',()=>{state.options.detail=$('detail').value;state.page=0;scheduleRender();});
$('prevPage').addEventListener('click',()=>{if(state.page>0){state.page--;showPage();}});
$('nextPage').addEventListener('click',()=>{if(state.page<state.pages.length-1){state.page++;showPage();}});
$('featureSearch').addEventListener('input',updateTable);
$('selectAll').addEventListener('change',()=>{if(current()){current().features.forEach(f=>f.visible=$('selectAll').checked);updateTable();scheduleRender();}});
for(const [id,fmt] of [['exportSvg','svg'],['exportPptx','pptx'],['exportGb','gb'],['saveProject','json']])$(id).addEventListener('click',guarded(()=>exportFile(fmt)));
$('referenceInput').addEventListener('change',guarded(async e=>{
  if(!current())throw Error('Load a construct before adding reference matches.');
  if(!e.target.files[0])return;
  notice('Matching exact reference sequences on both strands…');const form=new FormData();form.append('record',JSON.stringify(current()));form.append('reference',e.target.files[0]);
  const res=await api('/api/annotate',form,false);state.records[state.index]=(await res.json()).record;selectRecord(state.index);notice('Exact reference matches added. Review the new annotations.');e.target.value='';
}));
$('annotationMode').addEventListener('change',syncAnnotationControls);
$('plannotate').addEventListener('click',guarded(async()=>{
  if(!current())throw Error('Load a construct first.');
  const mode=$('annotationMode').value;
  if(!annotationModes[mode]?.available)throw Error('The selected annotation mode is unavailable.');
  notice('Running pLannotate locally. Large databases may take several minutes…');
  annotationRunning=true;syncAnnotationControls();
  try{
    const records=state.records,index=state.index,record=current(),snapshot=JSON.stringify(record),before=record.features.length;
    const res=await api('/api/annotate',{record,engine:'plannotate',annotation_mode:mode});const annotated=(await res.json()).record;
    if(state.records!==records||records[index]!==record||JSON.stringify(record)!==snapshot){
      throw Error('The input changed while pLannotate was running. Your edits were preserved; run annotation again on the current input.');
    }
    state.records[index]=annotated;if(state.index===index)selectRecord(index);
    notice(`${record.name}: ${mode==='detailed'?'Overlapping-feature':'Default'} search finished with ${annotated.features.length-before} new predictions. Review boundaries, fragments and roles before exporting.`);
  }finally{annotationRunning=false;syncAnnotationControls();}
}));
$('projectInput').addEventListener('change',guarded(async e=>{
  const file=e.target.files[0];if(!file)return;
  const raw=JSON.parse(await file.text());const res=await api('/api/project',raw);const data=await res.json();
  state.options={...state.options,...data.options};$('palette').value=state.options.palette;$('coordinates').checked=state.options.coordinates;$('detail').value=state.options.detail;
  syncLayoutControls();
  setRecords(data.records);notice('Project restored.');e.target.value='';
}));
for(const [role,name] of Object.entries(roles))$('newRole').add(new Option(name,role));
$('addFeature').addEventListener('click',guarded(()=>{if(!current())throw Error('Load a construct first.');$('addDialog').showModal();}));
$('closeDialog').addEventListener('click',()=>$('addDialog').close());
$('featureForm').addEventListener('submit',guarded(async e=>{
  e.preventDefault();const v=Object.fromEntries(new FormData(e.target));const a=Number(v.start)-1,b=Number(v.end);
  if(a<0||a>=b||b>current().length)throw Error(`Choose a valid interval within 1..${current().length}.`);
  current().features.push({id:`user-${crypto.randomUUID()}`,label:v.label,type:'misc_feature',role:v.role,segments:[[a,b]],strand:Number(v.strand),source:'user-added',role_source:'user-assigned',qualifiers:{},color:null,visible:true,module:'',fuzzy:false});
  updateTable();scheduleRender();$('addDialog').close();e.target.reset();
}));
guarded(async()=>{
  const res=await fetch('/api/status');const s=await res.json();palettes=s.palettes||palettes;roleColorIndices=s.role_color_indices||roleColorIndices;
  $('version').textContent=`v${s.version}`;
  annotationModes=s.annotation_modes||{default:{available:!!s.plannotate,reason:'Uses the installed engine’s default search.'},detailed:{available:false,reason:'Detailed search could not be verified. Use Default search.'}};
  syncAnnotationControls();
  $('annotationStatus').textContent=s.plannotate?`${s.annotation_engine?.version||'pLannotate'} ready / database bundle ${s.annotation_engine?.database_version||'verified'}.`:(s.annotation_engine?.reason||'pLannotate is not ready. Exact reference matching is available.');
  const params=new URLSearchParams(location.search),demo=params.get('demo');
  if(['singleline','schematic','proportional'].includes(params.get('layout')))state.options.layout=params.get('layout');
  syncLayoutControls();
  if(demo&&[...$('demoSelect').options].some(o=>o.value===demo)){
    $('demoSelect').value=demo;
    if(['overview','detailed'].includes(params.get('detail'))){state.options.detail=params.get('detail');$('detail').value=state.options.detail;}
    await loadPublicDemo(demo);
  }
})();
