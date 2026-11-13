const root = document.querySelector('#app');
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const api = async (url, body) => {
  if (location.pathname==='/studio36' && url==='/api/v2/cases') url+='?catalogue=36';
  const r = await fetch(url, body === undefined ? {} : {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
  const data = await r.json(); if (!r.ok) throw Error(data.error || `HTTP ${r.status}`); return data;
};
const APPS = [
  ['files','File Explorer','folder'], ['editor','Notepad','document'], ['settings','Settings','settings'],
  ['scheduler','Task Scheduler','calendar'], ['transfers','Transfer Manager','download'],
  ['monitor','Task Manager','monitor'], ['devices','Device Manager','device'], ['events','Event Viewer','list'],
  ['terminal','Terminal','document'],
];
const shapes = {folder:'M3 7h7l2-3h9v16H3Z',document:'M6 3h9l4 4v14H6ZM9 11h7M9 15h7',settings:'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8M12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M5 19l2-2M17 7l2-2',calendar:'M4 5h16v16H4ZM4 10h16M8 2v6M16 2v6M8 14h2M14 14h2',download:'M12 2v13M7 10l5 5 5-5M4 17v4h16v-4',monitor:'M3 4h18v13H3ZM8 21h8M12 17v4M6 12l3-4 4 6 4-5',device:'M7 2h10v20H7ZM10 18h4',list:'M5 5h14M5 10h14M5 15h14M5 20h14'};
const icon = (kind, size=24) => `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="${shapes[kind]||shapes.document}"/></svg>`;
const app = id => APPS.find(a => a[0]===id);
let session, windows=[], nextWindow=1, z=1, start=false, clipboard=null, dialog=null, contextMenu=null, notice='', replay=false, traceEnabled=false;
let copiedPath="";
let busy=Promise.resolve();
const scrollPositions=new Map();
let lastScrollDialog=null;
let terminalLines=['Workspace Terminal','Type help to list available commands.'];
const data = () => session.state;
const file = id => data().files.find(f => f.id===id && !f.deleted);
const children = id => data().files.filter(f => f.parent===id && !f.deleted);
const folders = () => data().files.filter(f => f.kind==='folder' && !f.deleted);
const fullpath = id => {let f=file(id), result=[];while(f){result.unshift(f.name);f=file(f.parent)}return '/'+result.join('/')};
const options = (items, selected) => items.map(([v,label]) => `<option value="${esc(v)}" ${v===selected?'selected':''}>${esc(label)}</option>`).join('');
const folderOptions = selected => options(folders().map(f=>[f.id,fullpath(f.id)]),selected);
const btn = (action,label,attrs='') => `<button type="button" data-command="${action}" ${attrs}>${label}</button>`;

function open(id, route) {
  const w={id:`w${nextWindow++}`, app:id, x:130+(windows.length%4)*34, y:40+(windows.length%4)*26,
    width:Math.min(innerWidth-160,1010), height:Math.min(innerHeight-110,590), z:++z,
    route:route||'project', section:'', selected:[], history:[], minimized:false, maximized:false, query:'', sort:'name'};
  w.x=Math.max(0,Math.min(w.x,innerWidth-w.width));
  w.y=Math.max(0,Math.min(w.y,innerHeight-48-w.height));
  if(id==='editor') w.fileId=route||null;
  windows.push(w); start=false; render(); return w;
}
async function mutate(a) {
  const updated=await api(`/api/v2/sessions/${session.id}/action`,a);
  session=updated;
  if(!updated.last_event.accepted) notice=updated.last_event.error;
  else if(updated.last_event.outcome?.status==='Failed') notice=updated.last_event.outcome.error;
  else notice='';
  render(); return updated.last_event.outcome;
}
function breadcrumbs(id) {let f=file(id),items=[];while(f){items.unshift(f);f=file(f.parent)}return items.map(f=>btn('folder',esc(f.name),`data-target="${f.id}"`)).join('<span>›</span>')}
function nav(items,current,command) {return `<aside class="navigation">${items.map(([id,label])=>btn(command,esc(label),`data-target="${id}" class="${current===id?'selected':''}"`)).join('')}</aside>`}

function explorer(w) {
  const sort=(a,b)=>w.sort==='kind'?a.kind.localeCompare(b.kind):a.name.localeCompare(b.name);
  const list=children(w.route).filter(f=>f.name.toLowerCase().includes(w.query.toLowerCase())).sort(sort);
  return `<div class="app-layout">${nav([['project',data().project],['projects','Projects'],['documents','Documents'],['downloads','Downloads'],['desktop','Desktop']],w.route,'folder')}<main class="file-main">
    <div class="toolbar">${btn('back','←','title="Back"')}${btn('up','↑','title="Up"')}<div class="breadcrumbs">${breadcrumbs(w.route)}</div><input data-field="search" placeholder="Search this folder" value="${esc(w.query)}" aria-label="Search files"></div>
    <div class="toolbar file-tools">${btn('new-folder',icon('folder',16)+' New folder')}${btn('new-document','New document')}${btn('copy','Copy')}${btn('copy-path','Copy path','title="Copy selected item path, or current folder when nothing is selected"')}${btn('cut','Cut')}${btn('paste','Paste',clipboard?'':'disabled')}${btn('rename','Rename')}${btn('delete','Delete')}${btn('properties','Properties')}<select data-field="sort" aria-label="Sort by">${options([['name','Name'],['kind','Type']],w.sort)}</select></div>
    <div class="file-head"><span>Name</span><span>Type</span><span>Size</span><span>Revision</span></div>
    <div class="file-list" data-scroll="files">${list.map(f=>`<button class="file-row ${w.selected.includes(f.id)?'selected':''}" data-command="select-file" data-target="${f.id}"><span>${icon(f.kind==='folder'?'folder':'document',20)}${esc(f.name)}</span><span>${esc(f.kind)}${typeof f.approved==='boolean'?(f.approved?' · Approved':' · Not approved'):''}</span><span>${f.kind==='folder'?'—':(f.storage_bytes??new TextEncoder().encode(f.content).length)+' B'}</span><span>${f.revision}</span></button>`).join('')||'<p class="empty">This folder is empty.</p>'}</div>
    <footer>${list.length} items · ${w.selected.length} selected <span>${clipboard?esc(clipboard.mode+' '+clipboard.ids.length+' items'):'Ready'}</span></footer></main></div>`;
}
function editor(w) {
  const f=file(w.fileId);
  const content=w.draft??f?.content??'Open a text document from File Explorer.';
  const breakLines=[...content.matchAll(/\f/g)].map(match=>content.slice(0,match.index).split('\n').length);
  return `<form data-form="editor" class="editor"><div class="toolbar">${btn('choose-document','Open…')}${btn('copy-path','Copy path',f?'':'disabled')}<button type="submit">Save</button>${btn('page-break','Insert page break',f?'':'disabled')}<label>Line <input type="number" min="1" value="${w.lineNumber||1}" data-field="go-line" aria-label="Go to line number"></label>${btn('go-line','Go')}<span>${esc(f?fullpath(f.id):'No document open')}${f&&content!==f.content?' · Unsaved changes':''}</span></div><textarea data-field="content" data-scroll="editor" spellcheck="false" aria-label="Document content" ${f?'':'disabled'}>${esc(content)}</textarea><footer>UTF-8 · ${content.split('\f').length} page(s)${breakLines.length?' · Page breaks before lines '+breakLines.join(', '):''}<span>${f?'Revision '+f.revision:'Notepad'}</span></footer></form>`;
}
const SETTING_GROUPS = {
  system:[['Power & scheduling',['scheduler.trigger']],['Storage & backup',['backup.retention','backup.scope','backup.include-text']]],
  network:[['Connection',['network.offline']],['Offline resources',['cache.contacts']],['Distribution',['distribution.destination']]],
  apps:[['Processing',['tools.enabled','tools.compiler','tools.signer']],['Media previews',['media.preview']],['Archives',['archive.format']],['Verification',['verification.mode']]],
  devices:[['Printing',['printer.selected','printer.paper','printer.duplex','printer.order']]],
  privacy:[['Evidence filtering',['privacy.redaction','privacy.scope','privacy.method']]],
};
const labels={'scheduler.trigger':'Default job trigger','backup.retention':'Retention policy','network.offline':'Offline mode','tools.enabled':'Processing tools','archive.format':'Archive format','verification.mode':'Verification depth','printer.duplex':'Duplex printing','privacy.redaction':'Filter personal information'};
labels['cache.contacts']='Include contacts in offline cache';
labels['printer.selected']='Printer';labels['printer.paper']='Paper size';
labels['distribution.destination']='Distribution destination';
labels['backup.scope']='Backup scope';labels['backup.include-text']='Include text documents (.txt)';
labels['privacy.scope']='Redaction scope';
labels['privacy.method']='Personal field treatment';
labels['media.preview']='Preview output size';
labels['printer.order']='Output page order';
labels['tools.compiler']='Compiler component';labels['tools.signer']='Signing provider';
const choices={'scheduler.trigger':[['manual','Manual'],['idle','When idle'],['plugged-in','When plugged in']], 'backup.retention':[['keep','Keep originals'],['versioned','Versioned copies']], 'archive.format':[['zip','ZIP'],['tar','TAR']], 'verification.mode':[['checksum','Checksums'],['full','Full content comparison']]};
function settings(w) {
  choices['printer.selected']=data().devices.filter(d=>d.kind==='Printer').map(d=>[d.id,d.name]);
  choices['printer.paper']=[['A4','A4'],['Letter','Letter']];
  choices['distribution.destination']=data().devices.filter(d=>d.kind==='Network storage').map(d=>[d.id,d.name]);
  choices['backup.scope']=[['all','All input files'],['sources','Copied sources only']];
  choices['privacy.scope']=[['contact','Contact only'],['personal','All personal fields']];
  choices['privacy.method']=[['mask','Mask values'],['remove','Remove fields'],['pseudonym','Stable pseudonyms']];
  choices['media.preview']=[['compact','Compact · 640 × 360'],['review','Review · 1280 × 720'],['detail','Detailed · 1920 × 1080']];
  choices['printer.order']=[['forward','First page to last'],['reverse','Last page to first']];
  const section=w.section||'system', pages=SETTING_GROUPS[section], page=pages.find(p=>p[0]===w.page)||pages[0];
  return `<div class="app-layout">${nav([['system','System'],['network','Network & internet'],['apps','Apps'],['devices','Bluetooth & devices'],['privacy','Privacy']],section,'settings-section')}<main class="settings-main"><h1>${esc(section[0].toUpperCase()+section.slice(1))}</h1><div class="tabs">${pages.map(p=>btn('settings-page',esc(p[0]),`data-target="${esc(p[0])}" class="${p===page?'selected':''}"`)).join('')}</div><h2>${esc(page[0])}</h2>${page[1].map(key=>`<label class="setting-card"><span>${esc(labels[key])}<small>Changes apply to new operations and jobs.</small></span><select data-field="setting" data-key="${key}" aria-label="${esc(labels[key])}">${choices[key]?options(choices[key],data().settings[key]):options([['true','On'],['false','Off']],String(data().settings[key]))}</select></label>`).join('')}</main></div>`;
}
function scheduler(w) {
  const selected=w.section||'all', list=data().jobs.filter(j=>selected==='all'||j.status.toLowerCase()===selected);
  const j=data().jobs.find(j=>w.selected.includes(j.id));
  return `<div class="app-layout">${nav([['all','Task Scheduler Library'],['ready','Ready'],['completed','Completed'],['failed','Failed']],selected,'section')}<main class="scheduler-main"><div class="toolbar"><h2>Task Scheduler</h2><span class="spacer"></span>${btn('new-job','Create task…')}${btn('run-job','Run / retry',j?'':'disabled')}${btn('job-properties','Properties',j?'':'disabled')}</div><div class="job-head"><span>Name</span><span>Operation</span><span>Trigger</span><span>Status</span></div><div class="job-list" data-scroll="jobs">${list.map(j=>`<button class="job-row ${w.selected.includes(j.id)?'selected':''}" data-command="select-job" data-target="${j.id}"><span>${esc(j.name)}</span><span>${esc(j.kind)}</span><span>${esc(j.trigger)}</span><span class="${j.status==='Failed'?'error-text':''}">${esc(j.status)}</span></button>`).join('')||'<p class="empty">No tasks in this view. Create a task to begin.</p>'}</div><div class="detail-pane">${j?`<h3>${esc(j.name)}</h3><dl><dt>Input</dt><dd>${esc(fullpath(j.input))}</dd><dt>Output</dt><dd>${esc(fullpath(j.output))}</dd><dt>Dependency</dt><dd>${esc(j.dependency||'None')}</dd><dt>Last result</dt><dd>${esc(j.error||j.status)}</dd></dl>${j.artifact?btn('open-artifact','Open output',`data-target="${j.artifact}"`):''}`:'Select a task to inspect its configuration and last result.'}</div></main></div>`;
}
function devices(w) {
  if(w.section==='print-queue')return printQueue();
return `<div class="app-layout">${nav([['all','All devices'],['Camera','Cameras'],['Printer','Printers'],['Network storage','Network storage'],['print-queue','Print queue']],w.section||'all','section')}<main class="settings-main"><h1>Devices</h1><p>Manage the resources available to desktop applications.</p>${data().devices.filter(d=>!w.section||w.section==='all'||d.kind===w.section).map(d=>`<div class="setting-card"><span>${icon('device')} ${esc(d.name)}<small>${esc(d.kind)} · ${d.connected?'Connected':'Disconnected'}${d.kind==='Printer'?' · Paper: '+esc((d.paper_sizes||['A4','Letter']).join(', '))+' · Duplex: '+(d.duplex_supported===false?'Unavailable':'Available'):''}</small></span>${d.kind==='Network storage'?`<label>Access<select data-field="device-access" data-target="${d.id}" aria-label="${esc(d.name)} access">${options([['read-only','Read only'],['read-write','Read and write']],d.access||'read-write')}</select><small>Recipient: ${esc(d.recipient||'Local team')}</small></label>`:''}${btn('device',d.connected?'Disconnect':'Connect',`data-target="${d.id}"`)}</div>`).join('')}</main></div>`;
}
function printQueue() {
return `<div class="app-layout">${nav([['all','All devices'],['print-queue','Print queue']],'print-queue','section')}<main class="settings-main"><h1>Print queue</h1><p>Virtual submissions only. No documents are sent to a host printer.</p>${(data().print_queue||[]).map(p=>`<div class="setting-card print-job"><span>${esc(p.name)}<small>${esc(p.status)} · ${p.pages.length} pages · ${esc(p.paper)} · ${p.duplex?'Duplex':'Simplex'} · ${esc(data().devices.find(d=>d.id===p.printer)?.name)}</small><small>${p.order==='reverse'?'Last page to first':'First page to last'}</small><small>${p.pages.map(page=>esc(page.name)+' · page '+page.page).join(' → ')}</small></span><div class="print-actions">${p.status==='Cancelled'?'':btn('print-control',p.status==='Paused'?'Resume':'Pause',`data-target="${p.id}" data-status="${p.status==='Paused'?'Queued':'Paused'}"`)+btn('print-control','Cancel',`data-target="${p.id}" data-status="Cancelled"`)}</div></div>`).join('')||'<p class="empty">No print jobs.</p>'}</main></div>`;
}
function monitor(w) {
  const storage=storageUsage();
  const performance=`<h2>Workspace storage</h2><p>Virtual file sizes, not host disk usage. Generated reports and backup copies are included.</p><div class="performance"><div>Files<strong>${storage.count}</strong></div><div>Used<strong>${storage.used.toLocaleString()} B</strong></div><div>Rebuildable cache<strong>${storage.cache.toLocaleString()} B</strong></div><div>Released cache<strong>${storage.released.toLocaleString()} B</strong></div></div><h2>Compressed artifacts</h2>${data().files.filter(f=>!f.deleted&&f.encoding==='hex/zlib').map(f=>`<div class="setting-card"><span>${esc(fullpath(f.id))}<small>${f.storage_bytes.toLocaleString()} B · Lossless DEFLATE</small></span></div>`).join('')||'<p>No compressed artifacts.</p>'}`;
  return `<div class="app-layout">${nav([['processes','Processes'],['performance','Performance'],['services','Services']],w.section||'processes','section')}<main class="settings-main"><h1>Task Manager</h1>${w.section==='performance'?performance:data().processes.map(p=>`<div class="setting-card"><span>${esc(p.name)}<small>${esc(p.status)} · ${p.memory} MB${p.locks.length?' · Open files: '+p.locks.map(fullpath).join(', '):''}</small></span>${btn('process',p.status==='Running'?'Pause':'Resume',`data-target="${p.id}"`)}</div>`).join('')}</main></div>`;
}
function storageUsage() {
  const stats={count:0,used:0,cache:0,released:0};
  for(const f of data().files) {
    if(f.kind==='folder') continue;
    const bytes=f.storage_bytes??new TextEncoder().encode(f.content).length;
    if(f.deleted) {if(f.regenerable) stats.released+=bytes;continue;}
    stats.count++;stats.used+=bytes;
    if(f.regenerable) stats.cache+=bytes;
  }
  return stats;
}
function transfers(w) {
  return `<div class="app-layout">${nav([['all','All transfers'],['Pending','Pending'],['Failed','Failed'],['Completed','Completed']],w.section||'all','section')}<main class="settings-main"><h1>Transfers</h1>${data().transfers.filter(t=>!w.section||w.section==='all'||w.section===t.status).map(t=>`<div class="setting-card"><span>${esc(t.name)}<small>${esc(t.status)} · ${t.progress}%${t.attempts?' · Attempts: '+t.attempts:''}</small>${t.error?`<small class="error-text">${esc(t.error)}</small>`:''}</span>${btn('download',t.status==='Completed'?'Completed':t.status==='Failed'?'Retry':'Download',`data-target="${t.id}" ${t.status==='Completed'?'disabled':''}`)}</div>`).join('')||'<p class="empty">No transfers.</p>'}</main></div>`;
}
function events(w) {
  const logs=data().files.filter(f=>f.log_channel&&!f.deleted), selected=file(w.section);
  const records=selected?.log_channel?selected.content.split('\n').filter(Boolean).map(line=>{try{const record=JSON.parse(line);if(!record||typeof record!=='object'||Array.isArray(record)||!record.event_id||!record.time)throw Error('Invalid record');return record}catch{return {event_id:'Invalid record',time:'',message:line}}}):null;
  return `<div class="app-layout">${nav([['all','Application logs'],['Error','Errors'],['Information','Information'],...logs.map(f=>[f.id,f.log_channel+' log'])],w.section||'all','section')}<main class="settings-main"><h1>Event Viewer</h1>${selected?.log_channel?`<h2>${esc(selected.log_channel)} · ${esc(selected.name)}</h2>${records?.find(r=>r.message==='Incident anchor')?`<p><strong>Incident anchor:</strong> ${esc(records.find(r=>r.message==='Incident anchor').time)}</p>`:''}${btn('export-log','Export interval…',`data-target="${selected.id}"`)}`:''}<input data-field="search" placeholder="Filter events" value="${esc(w.query)}" aria-label="Filter events"><div class="events" data-scroll="events">${records?records.filter(r=>JSON.stringify(r).toLowerCase().includes(w.query.toLowerCase())).map(r=>`<article><small>${esc(r.time)} · ${esc(r.event_id)}</small><p>${esc(JSON.stringify(r))}</p></article>`).join(''):data().events.filter(e=>(!w.section||w.section==='all'||w.section===e.level)&&JSON.stringify(e).toLowerCase().includes(w.query.toLowerCase())).map(e=>`<article><small>${esc(e.level)} · ${esc(e.source)}</small><p>${esc(e.message)}</p></article>`).join('')}</div></main></div>`;
}
function terminal(w) {
  return `<div class="terminal"><div class="terminal-lines" data-scroll="terminal">${terminalLines.map(line=>`<pre>${esc(line)}</pre>`).join('')}<form data-form="terminal"><label>PS C:\\Workspace&gt; <input name="command" data-field="terminal-command" aria-label="Terminal command" autocomplete="off"></label>${btn("paste-path","Paste path",copiedPath?"":"disabled")}</form></div></div>`;
}
async function terminalCommand(command) {
  terminalLines.push('PS C:\\Workspace> '+command);
  if(command==='help'){terminalLines.push('offline-test "/folder/path" — test cached resources with network disconnected\nworkspace-open "/folder/path" — resolve and open a migrated workspace\nstorage-audit "/folder/path" — verify cache cleanup, backup and restored services\nrestore-check "/folder/path" — validate recovered resources and restored schedules\npwd — show the current project\nclear — clear terminal output');render();return}
  if(command==='clear'){terminalLines=[];render();return}
  if(command==='pwd'){terminalLines.push(fullpath('project'));render();return}
  const match=command.match(/^(offline-test|workspace-open|storage-audit|restore-check)\s+"(.+)"$/);
  if(!match){terminalLines.push('Unknown command. Type help for syntax.');render();return}
  const target=folders().find(f=>fullpath(f.id)===match[2]);
  if(!target){terminalLines.push('Folder not found: '+match[2]);render();return}
  const outcome=await mutate({op:'probe',kind:{'offline-test':'offline','workspace-open':'workspace','storage-audit':'storage','restore-check':'restoration'}[match[1]],target:target.id});
  terminalLines.push(outcome?'PASS\n'+JSON.stringify(outcome.result,null,2):'FAILED: '+notice);
  render();
}
const renderApp={files:explorer,editor,settings,scheduler,devices,monitor,transfers,events,terminal};

function renderDialog() {
  if(!dialog) return '';
  let fields='', title=dialog.title||'';
  if(dialog.type==='name') fields=`<label>Name<input name="name" required value="${esc(dialog.value||'')}" autofocus></label>`;
  if(dialog.type==='copy-path') fields=`<label>Absolute path<input aria-label="Absolute path" value="${esc(dialog.value)}" readonly></label><p>Select the path and copy it with Ctrl+C or Command+C.</p>`;
  if(dialog.type==='open') fields=`<label>Document<select name="target">${options(data().files.filter(f=>f.kind!=='folder'&&!f.deleted).map(f=>[f.id,fullpath(f.id)]),dialog.target)}</select></label>`;
if(dialog.type==='job') {const j=dialog.job;fields=`<div class="form-grid"><label>Task name<input name="name" required placeholder="e.g. 01-inventory" value="${esc(j?.name||'')}" ${j?'readonly':''}></label><label>Operation<select name="kind" ${j?'disabled':''}>${options([...new Set(['inventory','validate','dry-run','index','build','test','sign','backup','restore','compare','transcode','catalogue','layout','proof','cache','migrate','redact','replicate','compact','package','verify','audit','verify-backup','deliver'])].map(k=>[k,k]),j?.kind||'inventory')}</select></label><label class="wide">Input folder<select name="input">${folderOptions(j?.input||dialog.folder)}</select></label><label class="wide">Output folder<select name="output">${folderOptions(j?.output||dialog.folder)}</select></label><label>Depends on<select name="dependency">${options([['','None'],...data().jobs.filter(x=>x.id!==j?.id).map(x=>[x.name,x.name])],j?.dependency||'')}</select></label><label>Trigger<select name="trigger">${options(choices['scheduler.trigger'],j?.trigger||data().settings['scheduler.trigger'])}</select></label></div>`;}
  if(dialog.type==='info') fields=`<pre>${esc(dialog.content)}</pre>`;
  if(dialog.type==='log-export')fields=`<label>Destination folder<select name="parent">${folderOptions('project')}</select></label><label>File name<input name="name" required value="${esc(file(dialog.target).name)}"></label><label>Start time (ISO 8601)<input name="start" required placeholder="2026-10-14T09:00:00"></label><label>End time (ISO 8601)<input name="end" required placeholder="2026-10-14T09:30:00"></label>`;
  if(dialog.type==='unsaved')return `<div class="modal-shade"><div class="dialog"><h2>Save changes?</h2><p>${esc(dialog.name)} has unsaved changes.</p><footer>${btn('cancel','Cancel')}${btn('discard-changes','Discard')}${btn('save-changes','Save','class="primary"')}</footer></div></div>`;
  return `<div class="modal-shade"><form class="dialog" data-form="dialog"><h2>${esc(title)}</h2>${fields}<footer>${btn('cancel','Cancel')}<button type="submit" class="primary">${dialog.type==='info'?'Close':'OK'}</button></footer></form></div>`;
}
function render() {
  root.querySelectorAll('[data-scroll-view]').forEach(el=>scrollPositions.set(el.dataset.scrollView,{top:el.scrollTop,left:el.scrollLeft}));
  if(dialog!==lastScrollDialog){scrollPositions.delete('desktop:dialog');lastScrollDialog=dialog}
  const active=document.activeElement, focus=active?.dataset.tid, value=active?.value, sel=active?.selectionStart;
  const workHeight=innerHeight-48;
  root.innerHTML=`<div class="desktop"><div class="wallpaper"></div><div class="desktop-icons">${APPS.filter(a=>['files','editor','settings','scheduler'].includes(a[0])).map(a=>`<button data-open="${a[0]}">${icon(a[2],34)}<span>${a[1]}</span></button>`).join('')}</div><div class="window-layer">${windows.filter(w=>!w.minimized).sort((a,b)=>a.z-b.z).map(w=>`<section class="window ${w.z===z?'active':''}" data-window="${w.id}" style="left:${w.maximized?0:w.x}px;top:${w.maximized?0:w.y}px;width:${w.maximized?innerWidth:w.width}px;height:${w.maximized?workHeight:w.height}px;z-index:${w.z}"><header class="titlebar" data-drag="${w.id}">${icon(app(w.app)[2],16)}<strong>${app(w.app)[1]}${w.app==='editor'&&file(w.fileId)?' — '+esc(file(w.fileId).name):''}</strong><span class="spacer"></span>${btn('minimize','─','aria-label="Minimize"')}${btn('maximize','□','aria-label="Maximize"')}${btn('close','×','class="close" aria-label="Close"')}</header><div class="window-content">${renderApp[w.app](w)}</div><div class="resize-handle" data-resize="${w.id}"></div></section>`).join('')}</div>${start?`<div class="start-menu"><input data-field="start-search" placeholder="Search applications" aria-label="Search applications"><h3>Applications</h3><div class="start-grid">${APPS.map(a=>`<button data-open="${a[0]}">${icon(a[2],28)}<span>${a[1]}</span></button>`).join('')}</div><footer><span>Local account</span>${btn('task-info','Task instructions')}${session.mode==='practice'?'':btn('finish',session.mode==='demo'?'Finish recording':'End session')}</footer></div>`:''}<div class="taskbar">${btn('start','<span class="start-symbol">⊞</span>','aria-label="Start"')}<span class="task-divider"></span>${APPS.map(a=>`<button data-open="${a[0]}" class="task-icon ${windows.some(w=>w.app===a[0])?'running':''}" title="${a[1]}">${icon(a[2],21)}</button>`).join('')}<div class="task-windows">${windows.map(w=>`<button data-command="task-window" data-target="${w.id}" class="${w.z===z&&!w.minimized?'selected':''}">${esc(app(w.app)[1])}</button>`).join('')}</div><span class="spacer"></span><span class="tray">ENG&nbsp;&nbsp; ◌&nbsp;&nbsp; 100%<small>10:24 AM<br>10/14/2026</small></span></div>${notice?`<div class="notification"><strong>Operation result</strong><p>${esc(notice)}</p>${btn('dismiss-notice','Dismiss')}</div>`:''}${renderDialog()}<div id="replay-pointer" ${replay?'':'hidden'}></div></div>`;
  if(contextMenu){const el=document.createElement('div');el.className='context-menu';el.dataset.window=contextMenu.window;el.style.left=contextMenu.x+'px';el.style.top=contextMenu.y+'px';el.innerHTML=['copy','copy-path','cut','rename','delete','properties'].map(c=>btn(c,c==='copy-path'?'Copy path':c[0].toUpperCase()+c.slice(1))).join('');root.querySelector('.desktop').append(el)}
  installVisibleSelects();
  assignTraceIds();
  if(focus){const next=root.querySelector(`[data-tid="${CSS.escape(focus)}"]`);if(next){next.focus();if(next.tagName==='INPUT'&&value!==undefined&&next.dataset.field==='search'){next.value=value;try{next.setSelectionRange(sel,sel)}catch{}}}}
  root.querySelectorAll('[data-scroll-view]').forEach(el=>{const position=scrollPositions.get(el.dataset.scrollView);if(position){el.scrollTop=position.top;el.scrollLeft=position.left}});
}
function assignTraceIds() {
  // Panels scroll independently of their controls. Include wheel/keyboard
  // scrolling even when no resource mutation follows (e.g. reading a report).
  root.querySelectorAll('.settings-main,.detail-pane,.dialog,.navigation,.breadcrumbs,.task-windows,.tabs').forEach(el=>{
    if(!el.hasAttribute('data-scroll'))el.dataset.scroll='panel-'+el.classList[0];
  });
  root.querySelectorAll('[data-scroll]').forEach(el=>{
    const scope=el.closest('[data-window]')?.dataset.window||'desktop';
    const w=windows.find(item=>item.id===scope);
    // Identity belongs to the rendered view, not the subsequently changed
    // window state. New folders/pages/documents must not inherit old offsets.
    const view=w?[w.app,w.route,w.section,w.page,w.fileId,w.query,w.sort,el.classList.contains('detail-pane')?w.selected:[]]:[];
    el.dataset.scrollView=el.classList.contains('dialog')?'desktop:dialog':JSON.stringify([scope,el.dataset.scroll,...view]);
  });
  const counts={};
  root.querySelectorAll('button,input,select,textarea,form,[data-scroll],[data-drag],[data-resize]').forEach(el=>{
    const scope=el.closest('[data-window]')?.dataset.window||'desktop';
    const attrs=[...el.attributes].filter(a=>(a.name.startsWith('data-')&&a.name!=='data-tid')||a.name==='name').map(a=>a.name+'='+a.value).sort().join('|');
    const base=`${scope}:${el.tagName}:${attrs}`; counts[base]=(counts[base]||0)+1;
    el.dataset.tid=base+':'+counts[base];
  });
}
const winFor = el => windows.find(w=>w.id===el.closest('[data-window]')?.dataset.window);
async function handle(event) {
  const el=event.target.closest('button,input,select,textarea,form'), w=el&&winFor(el);
  if(event.type==='change') {
    if(el.dataset.field==='device-access'){await mutate({op:'device-access',target:el.dataset.target,access:event.value??el.value});return}
    if(el.dataset.field==='setting'){const raw=event.value??el.value;await mutate({op:'setting',key:el.dataset.key,value:raw==='true'?true:raw==='false'?false:raw})}
    if(el.dataset.field==='sort'){w.sort=event.value??el.value;render()}
    return;
  }
  if(event.type==='input') {
    if(el.dataset.field==='go-line'&&w)w.lineNumber=Number(event.value??el.value)||1;
    if(el.dataset.field==='content'&&w&&replay)w.draft=event.value??el.value;
    if(el.dataset.field==='search'&&w){w.query=event.value??el.value;render()}
    if(el.dataset.field==='start-search'){root.querySelectorAll('.start-grid button').forEach(b=>b.hidden=!b.textContent.toLowerCase().includes(el.value.toLowerCase()))}
    return;
  }
  if(event.type==='submit') {
    event.preventDefault();const form=event.target, values=event.formValues??Object.fromEntries(new FormData(form));
    if(form.dataset.form==='editor'&&w?.fileId) await mutate({op:'write',target:w.fileId,content:event.formContent??form.querySelector('textarea').value});
    if(form.dataset.form==='terminal') await terminalCommand(values.command.trim());
    if(form.dataset.form==='dialog') {
      const d=dialog; dialog=null;
      if(d.type==='log-export')await mutate({op:'export-log',target:d.target,parent:values.parent,name:values.name,start:values.start,end:values.end});
      if(d.type==='name') {
        if(d.op==='rename') await mutate({op:'rename',target:d.target,name:values.name});
        else {const id=await mutate({op:d.op,parent:d.parent,name:values.name});if(d.op==='create-document'&&typeof id==='string')open('editor',id)}
      }else if(d.type==='job') await mutate(d.job?{op:'update-job',target:d.job.id,...values}:{op:'create-job',...values});
      else if(d.type==='open'){
        const ew=windows.find(x=>x.id===d.window), current=file(ew.fileId);
        if(values.target!==ew.fileId){
          if(current&&ew.draft!==undefined&&ew.draft!==current.content)dialog={type:'unsaved',window:ew.id,name:current.name,nextFile:values.target};
          else {ew.fileId=values.target;ew.draft=undefined}
        }
        render();
      }
      else render();
    }
    return;
  }
  if(event.type==='dblclick'&&el?.dataset.command==='select-file') {
    const f=file(el.dataset.target);if(f.kind==='folder'){w.history.push(w.route);w.route=f.id;w.selected=[];render()}else open('editor',f.id);
    return;
  }
  if(event.type==='contextmenu'&&el?.dataset.command==='select-file') {
    event.preventDefault();w.selected=[el.dataset.target];contextMenu={window:w.id,x:Math.min(event.clientX,innerWidth-180),y:Math.min(event.clientY,innerHeight-245)};render();return;
  }
  if(event.type==='keydown') {
    if(event.key==='Escape'&&(dialog||contextMenu||start)){event.preventDefault();dialog=null;contextMenu=null;start=false;render();return}
    if(el?.dataset.field==='go-line'&&event.key==='Enter'){event.preventDefault();await command({dataset:{command:'go-line'}},w,event);return}
    if(['INPUT','TEXTAREA','SELECT'].includes(event.target.tagName)) {
      if(event.ctrlKey&&event.key.toLowerCase()==='s'&&w?.app==='editor'){event.preventDefault();await mutate({op:'write',target:w.fileId,content:root.querySelector(`[data-window="${w.id}"] textarea`).value})}
      return;
    }
    if(w?.app==='files'&&event.ctrlKey&&['c','x','v'].includes(event.key.toLowerCase())) {
      event.preventDefault();await command({dataset:{command:{c:'copy',x:'cut',v:'paste'}[event.key.toLowerCase()]}},w,event);
    }
    return;
  }
  if(event.type!=='click'||!el) return;
  if(el.dataset.open){const existing=windows.filter(x=>x.app===el.dataset.open).at(-1);if(existing){existing.minimized=false;existing.z=++z;start=false;render()}else open(el.dataset.open);return}
  if(el.dataset.command) await command(el,w,event);
}
async function command(el,w,event) {
  const c=el.dataset.command, target=el.dataset.target;
  contextMenu=null;
  if(c==='start')start=!start;
  else if(c==='close'){const document=file(w.fileId);if(w.app==='editor'&&document&&w.draft!==undefined&&w.draft!==document.content)dialog={type:'unsaved',window:w.id,name:document.name};else windows=windows.filter(x=>x!==w)}
  else if(c==='minimize')w.minimized=true;
  else if(c==='maximize')w.maximized=!w.maximized;
  else if(c==='task-window'){const item=windows.find(x=>x.id===target);item.minimized=false;item.z=++z}
  else if(c==='folder'){w.history.push(w.route);w.route=target;w.selected=[]}
  else if(c==='back'){w.route=w.history.pop()||w.route;w.selected=[]}
  else if(c==='up'){w.history.push(w.route);w.route=file(w.route)?.parent||w.route;w.selected=[]}
  else if(c==='select-file'){w.selected=event.ctrlKey?(w.selected.includes(target)?w.selected.filter(x=>x!==target):[...w.selected,target]):[target];w.z=++z}
  else if(c==='select-job')w.selected=[target];
  else if(c==='section'){w.section=target;w.selected=[]}
  else if(c==='settings-section'){w.section=target;w.page=null}
  else if(c==='settings-page')w.page=target;
  else if(c==='copy'||c==='cut') {if(!w.selected.length){notice='Select at least one file.'}else clipboard={ids:[...w.selected],mode:c}}
  else if(c==='paste'&&clipboard){for(const id of clipboard.ids)await mutate({op:clipboard.mode==='cut'?'move':'copy',target:id,parent:w.route});if(clipboard.mode==='cut')clipboard=null}
  else if(c==='new-folder'||c==='new-document')dialog={type:'name',title:c==='new-folder'?'New folder':'New document',op:c==='new-folder'?'mkdir':'create-document',parent:w.route};
  else if(c==='rename'){if(w.selected.length!==1)notice='Select one item to rename.';else dialog={type:'name',title:'Rename',op:'rename',target:w.selected[0],value:file(w.selected[0]).name}}
  else if(c==='delete'){for(const id of w.selected)await mutate({op:'delete',target:id});w.selected=[]}
  else if(c==='copy-path'){
    if(w.app==='files'&&w.selected.length>1){notice='Select one file or folder to copy its path.'}
    else {
      const id=w.app==='editor'?w.fileId:(w.selected[0]||w.route);
      if(id){const value=fullpath(id);copiedPath=value;try{await navigator.clipboard.writeText(value);notice='Path copied: '+value}catch{dialog={type:'copy-path',title:'Copy path',value}}}
    }
  }
  else if(c==='paste-path'&&copiedPath){
    const input=root.querySelector(`[data-window="${w.id}"] input[name="command"]`);
    input.setRangeText(copiedPath,input.selectionStart,input.selectionEnd,'end');input.focus();return;
  }
  else if(c==='properties'){if(w.selected.length===1){const f=file(w.selected[0]);const info=await mutate({op:'properties',target:f.id});dialog={type:'info',title:f.name,content:formatFileProperties(info)}}else notice='Select one item.'}
  else if(c==='choose-document')dialog={type:'open',title:'Open document',window:w.id,target:w.fileId};
  else if(c==='go-line'){const textarea=root.querySelector(`[data-window="${w.id}"] textarea`);const lines=textarea.value.split('\n');const line=Math.max(1,Math.min(lines.length,w.lineNumber||1));const offset=lines.slice(0,line-1).reduce((n,text)=>n+text.length+1,0);textarea.focus();textarea.setSelectionRange(offset,offset);textarea.scrollTop=Math.max(0,(line-1)*22-120);return}
  else if(c==='page-break'){const textarea=root.querySelector(`[data-window="${w.id}"] textarea`);const at=textarea.selectionStart;w.draft=textarea.value.slice(0,at)+'\f'+textarea.value.slice(textarea.selectionEnd);const scroll=textarea.scrollTop;render();const next=root.querySelector(`[data-window="${w.id}"] textarea`);next.focus();next.setSelectionRange(at+1,at+1);next.scrollTop=scroll;return}
  else if(c==='new-job')dialog={type:'job',title:'Create task',folder:'project'};
  else if(c==='run-job')await mutate({op:'run-job',target:w.selected[0]});
  else if(c==='job-properties')dialog={type:'job',title:'Edit / reset task',job:data().jobs.find(j=>j.id===w.selected[0])};
  else if(c==='open-artifact')open('editor',target);
  else if(c==='export-log')dialog={type:'log-export',title:'Export log interval',target};
  else if(c==='device')await mutate({op:'device',target,connected:!data().devices.find(d=>d.id===target).connected});
  else if(c==='print-control')await mutate({op:'print-control',target,status:el.dataset.status});
  else if(c==='process')await mutate({op:'process',target,status:data().processes.find(p=>p.id===target).status==='Running'?'Paused':'Running'});
  else if(c==='download')await mutate({op:'download',target});
  else if(c==='cancel')dialog=null;
  else if(c==='discard-changes')completeEditorNavigation(dialog);
  else if(c==='save-changes'){const pending=dialog, edited=windows.find(x=>x.id===pending.window);const outcome=await mutate({op:'write',target:edited.fileId,content:edited.draft});if(outcome)completeEditorNavigation(pending)}
  else if(c==='dismiss-notice')notice='';
  else if(c==='task-info'){start=false;dialog={type:'info',title:session.case.title,content:session.case.task+'\n\nCurrent project: '+data().project}}
  else if(c==='finish'){session=await api(`/api/v2/sessions/${session.id}/finish`,{});traceEnabled=false;start=false;notice=session.mode==='demo'?(session.result.success?'Demonstration accepted. Video rendering queued.':'Demonstration incomplete. Inspect the authoring result in Studio.'):'Session ended. Results are available to the external runner.';window.parent.postMessage({source:'os-icl',type:'OS_ICL_FINISHED',episodeId:session.id},location.origin)}
  render();
}

function completeEditorNavigation(pending) {
  const edited=windows.find(x=>x.id===pending.window);
  if(pending.nextFile){edited.fileId=pending.nextFile;edited.draft=undefined}
  else windows=windows.filter(x=>x!==edited);
  dialog=null;
}

async function record(event) {
  if(!traceEnabled||replay)return;
  const target=event.target.closest('[data-tid]');if(!target)return;
  if(event.type==='keydown'&&event.key!=='Escape'&&!(event.ctrlKey&&['s','c','x','v'].includes(event.key.toLowerCase())))return;
  await api(`/api/v2/sessions/${session.id}/ui-event`,{type:event.type,selector:target.dataset.tid,
    value:'value' in target?target.value:undefined, key:event.key,ctrlKey:event.ctrlKey||false,
    x:event.clientX,y:event.clientY,scrollTop:event.type==='scroll'?target.scrollTop:undefined});
}
for(const type of ['click','dblclick','contextmenu','change','input','submit','keydown']) {
  root.addEventListener(type,event=>{
    if(type==='submit'||type==='contextmenu')event.preventDefault();
    if(type==='keydown'&&event.key==='Enter'&&event.target.dataset.field==='go-line')event.preventDefault();
    if(type==='keydown'&&event.ctrlKey&&['s','c','x','v'].includes(event.key.toLowerCase())&&!['INPUT','TEXTAREA'].includes(event.target.tagName))event.preventDefault();
    if(type==='keydown'&&event.ctrlKey&&event.key.toLowerCase()==='s')event.preventDefault();
    // Snapshot before asynchronous handling: later typing must not change an
    // earlier recorded event's input value.
    const target=event.target, snapshot={type,target,key:event.key,ctrlKey:event.ctrlKey,clientX:event.clientX,clientY:event.clientY,preventDefault:()=>event.preventDefault()};
    const value='value' in target?target.value:undefined;
    snapshot.value=value;
    if(type==='input'&&target.dataset.field==='content'){const editorWindow=winFor(target);if(editorWindow)editorWindow.draft=value}
    if(type==='submit'){snapshot.formValues=Object.fromEntries(new FormData(target));snapshot.formContent=target.querySelector('textarea')?.value}
    const selector=target.closest('[data-tid]')?.dataset.tid;
    busy=busy.then(async()=>{
      if(traceEnabled&&!replay&&selector&&target.dataset.command!=='finish')await api(`/api/v2/sessions/${session.id}/ui-event`,{type,selector,value,key:event.key,ctrlKey:event.ctrlKey||false,x:event.clientX,y:event.clientY});
      await handle(snapshot);
    }).catch(e=>{notice=e.message;render()});
    window.__OS_PENDING__=busy;
  });
}
root.addEventListener('scroll',e=>{if(e.target.matches('[data-scroll]')){const el=e.target;if(traceEnabled&&!replay){const event={type:'scroll',selector:el.dataset.tid,scrollTop:el.scrollTop,scrollLeft:el.scrollLeft};busy=busy.then(()=>api(`/api/v2/sessions/${session.id}/ui-event`,event))}}},true);
let dragging;
root.addEventListener('pointerdown',e=>{
  const title=e.target.closest('[data-drag]'),resize=e.target.closest('[data-resize]');
  if((!title&&!resize)||e.target.closest('button'))return;
  const w=windows.find(w=>w.id===(title?.dataset.drag||resize?.dataset.resize));if(w.maximized)return;
  w.z=++z;dragging={w,x:e.clientX,y:e.clientY,original:{x:w.x,y:w.y,width:w.width,height:w.height},resize:!!resize};
  e.preventDefault();
});
window.addEventListener('pointermove',e=>{if(!dragging)return;const {w,x,y,original,resize}=dragging;
  if(resize){w.width=Math.max(680,Math.min(innerWidth-w.x,original.width+e.clientX-x));w.height=Math.max(390,Math.min(innerHeight-48-w.y,original.height+e.clientY-y))}
  else{w.x=Math.max(0,Math.min(innerWidth-120,original.x+e.clientX-x));w.y=Math.max(0,Math.min(innerHeight-100,original.y+e.clientY-y))}
  const el=root.querySelector(`[data-window="${w.id}"]`);Object.assign(el.style,{left:w.x+'px',top:w.y+'px',width:w.width+'px',height:w.height+'px',zIndex:w.z});
});
window.addEventListener('pointerup',()=>{if(!dragging)return;const {w}=dragging;if(traceEnabled&&!replay)busy=busy.then(()=>api(`/api/v2/sessions/${session.id}/ui-event`,{type:'drag',window:w.id,geometry:{x:w.x,y:w.y,width:w.width,height:w.height},z:w.z}));dragging=null;render()});
window.addEventListener('resize',render);
window.__OS_WAIT_IDLE__=()=>busy;

async function runReplay(sid) {
  const replayData=await api(`/api/v2/sessions/${sid}/replay`,{});session=replayData.session;render();
  let previousEventTime=null;
  for(const ev of replayData.trace) {
    const presentationFast=new URLSearchParams(location.search).get('audit_speed')==='fast';
    if(!presentationFast&&previousEventTime!==null&&ev.at-previousEventTime>=900)await new Promise(r=>setTimeout(r,Math.min(8000,ev.at-previousEventTime)));
    previousEventTime=ev.at??previousEventTime;
    if(ev.type==='drag'){const w=windows.find(w=>w.id===ev.window);if(!w)throw Error('Replay window missing');Object.assign(w,ev.geometry,{z:ev.z});z=Math.max(z,ev.z);render();continue}
    let el=root.querySelector(`[data-tid="${CSS.escape(ev.selector)}"]`);
    if(!el)throw Error(`Replay target missing: ${ev.selector}`);
    const rect=el.getBoundingClientRect(),pointer=root.querySelector('#replay-pointer');pointer.style.left=(ev.x??rect.left+rect.width/2)+'px';pointer.style.top=(ev.y??rect.top+rect.height/2)+'px';
    const fast=new URLSearchParams(location.search).get('audit_speed')==='fast';
    // Chromium can emit several identical input notifications for one
    // multiline replacement. Keep the authentic trace, but do not turn
    // unchanged text into repeated artificial reading pauses.
    const changedText=ev.type==='input'&&el.tagName==='TEXTAREA'&&ev.value!==undefined&&el.value!==ev.value;
    if(!fast&&changedText)await new Promise(r=>setTimeout(r,700));
    if(ev.value!==undefined)el.value=ev.value;
    if(ev.type==='scroll'){el.scrollTop=ev.scrollTop;el.scrollLeft=ev.scrollLeft??0;continue}
    if(['click','dblclick','contextmenu'].includes(ev.type))await new Promise(r=>setTimeout(r,fast?0:350));
    const openedDocument=ev.type==='submit'&&dialog?.type==='open';
    await handle({type:ev.type,target:el,value:ev.value,key:ev.key,ctrlKey:ev.ctrlKey,clientX:ev.x,clientY:ev.y,preventDefault:()=>{}});
    if(!fast&&openedDocument)await new Promise(r=>setTimeout(r,2000));
    // Presentation dwell makes visible diagnostics readable. It does not
    // create an action or contribute to the meaningful-mutation threshold.
    if(!fast&&notice&&el.dataset.command!=='dismiss-notice')await new Promise(r=>setTimeout(r,2000));
    if(!fast&&ev.type==='click'&&el.dataset.command==='properties'&&dialog?.type==='info')await new Promise(r=>setTimeout(r,2500));
    if(!fast&&ev.type==='change'&&el.dataset.field==='setting')await new Promise(r=>setTimeout(r,1200));
    if(!fast&&ev.type==='click'&&el.dataset.command==='open-artifact')await new Promise(r=>setTimeout(r,2000));
    if(!fast&&ev.type==='dblclick'&&el.dataset.command==='select-file'&&file(el.dataset.target)?.kind!=='folder')await new Promise(r=>setTimeout(r,2000));
    if(!fast&&changedText)await new Promise(r=>setTimeout(r,700));
    if(!fast&&ev.type==='submit')await new Promise(r=>setTimeout(r,450));
    if(!fast&&ev.type==='submit'&&el.dataset.form==='terminal')await new Promise(r=>setTimeout(r,2000));
  }
  const current=await api(`/api/v2/sessions/${session.id}`);
  if(current.state_hash!==replayData.expected_hash)throw Error(`Replay state mismatch: ${current.state_hash} != ${replayData.expected_hash}`);
  await new Promise(r=>setTimeout(r,1000));window.__REPLAY_DONE__=true;
}
async function studio() {
  const catalogue=await api('/api/v2/cases');
  root.innerHTML=`<main class="studio"><header><h1>OS-ICL Studio</h1><a href="/">Open desktop</a></header><p>36-task catalogue · 12 Easy / 12 Medium / 12 Hard · development</p><form id="create-session"><label>Workflow<select name="case_id">${options(catalogue.cases.map(c=>[c.id,c.id+' — '+c.title]),catalogue.cases[0].id)}</select></label><label>Mode<select name="mode">${options([['demo','Record demonstration'],['evaluation','External evaluation session'],['practice','Practice']],'demo')}</select></label><label>Convention<select name="convention">${options([['0','Convention A'],['1','Convention B'],['2','Convention C']],'0')}</select></label><label>Seed<input name="seed" type="number" value="1001"></label><button class="primary">Create session</button></form><p>Authoring instructions are shown before recording. The demonstration itself uses the ordinary desktop. Evaluation rules are inferred from independently supplied videos.</p></main>`;
  root.querySelector('#create-session button').insertAdjacentHTML('beforebegin',`<label>Demonstration plan<select name="plan_variant">${options([['standard','Standard preparation'],['configure-first','Configure tools first'],['reverse-sources','Process sources in reverse order']],'standard')}</select></label>`);
  document.querySelector('#create-session').addEventListener('submit',async e=>{e.preventDefault();try{const result=await api('/api/v2/sessions',Object.fromEntries(new FormData(e.target)));location.href=result.launch_url}catch(err){alert(err.message)}});
}
async function boot() {
  const q=new URLSearchParams(location.search),sid=q.get('session');
  if(['/studio','/studio36'].includes(location.pathname)){await studio();return}
  if(sid){session=await api(`/api/v2/sessions/${sid}`);replay=q.get('replay')==='1';if(replay){await runReplay(sid);return}}
  else session=await api('/api/v2/sessions',{mode:'practice',case_id:'OS-E-01',seed:42,convention:0});
  if(session.compatible===false){
    root.innerHTML=`<main class="brief"><h1>Session update required</h1><p>This session was created with a different desktop implementation. It cannot continue safely with the current code.</p><p>Resetting clears this session's actions, recording and result, while keeping its workflow, seed and demonstrated procedure. Previously exported artifacts are not deleted.</p><button id="reset-session" class="primary">Reset session</button> <a href="/studio">Create a separate session</a><p id="reset-error" role="alert"></p></main>`;
    document.querySelector('#reset-session').onclick=async()=>{const button=document.querySelector('#reset-session');button.disabled=true;try{await api(`/api/v2/sessions/${session.id}/reset`,{});location.reload()}catch(error){document.querySelector('#reset-error').textContent=error.message;button.disabled=false}};
    return;
  }
  document.title='Desktop — OS-ICL';
  if(session.mode==='demo'&&session.status==='active'&&session.recorder_brief?.method) {
    root.innerHTML=`<main class="brief"><h1>${esc(session.case.title)}</h1><h2>Recorder instructions</h2><p>${esc(session.recorder_brief.instruction)}</p><p>${esc(session.recorder_brief.method)}</p><p>Demonstrate only the local method. Use the ordinary desktop. Finish through Start.</p><button id="begin-demo" class="primary">Start demonstration</button></main>`;
    document.querySelector('#begin-demo').onclick=()=>{render();traceEnabled=true};
  }else if(session.mode==='demo'&&session.status==='active') {
    root.innerHTML=`<main class="brief"><h1>${esc(session.case.title)}</h1><p>${esc(session.case.task)}</p><h2>Recorder instructions</h2><pre>${esc(JSON.stringify(session.recorder_brief.convention,null,2))}</pre><p>Preserve all originals. Stage four source files under the working folder, rename the copies, create and save handoff-index.txt, configure settings, and run the dependent workflow below. Output reports go in a Reports subfolder; the final delivery goes in the delivery folder.</p><p>${esc(session.case.pipeline.join(' → '))}</p><details><summary>Detailed authoring operations</summary><pre>${esc(JSON.stringify(session.recorder_brief.reference,null,2))}</pre></details><button id="begin-demo" class="primary">Start demonstration</button></main>`;
    document.querySelector('#begin-demo').onclick=()=>{render();traceEnabled=true};
  }else {render();traceEnabled=session.status==='active'}
  window.parent.postMessage({source:'os-icl',type:'OS_ICL_READY',episodeId:session.id},location.origin);
}
boot().catch(e=>{root.innerHTML=`<main class="brief"><h1>Could not open desktop</h1><p>${esc(e.message)}</p></main>`;window.__REPLAY_ERROR__=e.message});


function formatFileProperties(info) {
  const labels={path:'Location',revision:'Revision',bytes:'Size (bytes)',approved:'Approved',
    resource_key:'Resource key',snapshot_version:'Snapshot version',snapshot_status:'Snapshot status',
    regenerable:'Regenerable',owners:'Owners',sha256:'SHA-256'};
  return Object.entries(labels).filter(([key])=>info[key]!==null&&info[key]!==undefined)
    .map(([key,label])=>label+': '+(typeof info[key]==='boolean'?(info[key]?'Yes':'No'):Array.isArray(info[key])?(info[key].join(', ')||'None'):info[key])).join('\n');
}

// Render choices inside the page so tab capture includes the entire selection.
// Native selects remain the form values and change-event targets.
let visiblePicker = null;
function closeVisiblePicker(focus = false) {
  if (!visiblePicker) return;
  const {menu, trigger} = visiblePicker;
  menu.remove();
  trigger.setAttribute('aria-expanded', 'false');
  if (focus && trigger.isConnected) trigger.focus();
  visiblePicker = null;
}
document.addEventListener('pointerdown', event => {
  if (visiblePicker && !visiblePicker.menu.contains(event.target) && !visiblePicker.trigger.contains(event.target))
    closeVisiblePicker();
}, true);
window.addEventListener('resize', () => closeVisiblePicker());

function installVisibleSelects() {
  closeVisiblePicker();
  root.querySelectorAll('select').forEach((select, index) => {
    if (select.dataset.visiblePicker) return;
    select.dataset.visiblePicker = 'true';
    const label = select.getAttribute('aria-label') ||
      select.closest('label')?.childNodes[0]?.textContent?.trim() || select.name || 'Choose';
    const trigger = document.createElement('button');
    trigger.type = 'button';
    trigger.className = 'visible-select';
    trigger.setAttribute('role', 'combobox');
    trigger.setAttribute('aria-label', label);
    trigger.setAttribute('aria-haspopup', 'listbox');
    trigger.setAttribute('aria-expanded', 'false');
    trigger.setAttribute('aria-controls', 'visible-options-' + index);
    trigger.disabled = select.disabled;
    trigger.textContent = select.selectedOptions[0]?.textContent || 'Choose…';
    select.hidden = true;
    select.after(trigger);

    function show() {
      if (visiblePicker?.trigger === trigger) { closeVisiblePicker(true); return; }
      closeVisiblePicker();
      const menu = document.createElement('div');
      menu.id = 'visible-options-' + index;
      menu.className = 'visible-options';
      menu.setAttribute('role', 'listbox');
      menu.setAttribute('aria-label', label);
      const buttons = [];
      function choose(option) {
        select.value = option.value;
        trigger.textContent = option.textContent;
        closeVisiblePicker(true);
        select.dispatchEvent(new Event('change', {bubbles: true}));
      }
      for (const option of select.options) {
        const button = document.createElement('button');
        button.type = 'button';
        button.setAttribute('role', 'option');
        button.setAttribute('aria-selected', String(option.selected));
        button.textContent = option.textContent;
        button.disabled = option.disabled;
        button.addEventListener('click', event => {event.stopPropagation(); choose(option);});
        menu.append(button);
        if (!option.disabled) buttons.push(button);
      }
      menu.addEventListener('keydown', event => {
        const position = buttons.indexOf(document.activeElement);
        if (['ArrowDown','ArrowUp','Home','End'].includes(event.key)) {
          event.preventDefault(); event.stopPropagation();
          const next = event.key === 'Home' ? 0 : event.key === 'End' ? buttons.length - 1 :
            (position + (event.key === 'ArrowDown' ? 1 : -1) + buttons.length) % buttons.length;
          buttons[next]?.focus();
        } else if (event.key === 'Escape') {
          event.preventDefault(); event.stopPropagation(); closeVisiblePicker(true);
        } else if (event.key === 'Tab') closeVisiblePicker(true);
      });
      document.body.append(menu);
      const box = trigger.getBoundingClientRect();
      const width = Math.min(Math.max(box.width, 320), innerWidth - 24);
      menu.style.width = width + 'px';
      menu.style.left = Math.max(12, Math.min(box.left, innerWidth - width - 12)) + 'px';
      const below = innerHeight - box.bottom - 12, above = box.top - 12;
      menu.style.maxHeight = Math.min(320, Math.max(below, above)) + 'px';
      if (below >= Math.min(menu.scrollHeight, 320) || below >= above) menu.style.top = box.bottom + 4 + 'px';
      else menu.style.bottom = innerHeight - box.top + 4 + 'px';
      visiblePicker = {menu, trigger};
      trigger.setAttribute('aria-expanded', 'true');
      (buttons.find(button => button.getAttribute('aria-selected') === 'true') || buttons[0])?.focus();
    }
    trigger.addEventListener('click', event => {event.stopPropagation(); show();});
    trigger.addEventListener('keydown', event => {
      if (['ArrowDown','ArrowUp','Enter',' '].includes(event.key)) {
        event.preventDefault(); event.stopPropagation(); show();
      }
    });
  });
}
