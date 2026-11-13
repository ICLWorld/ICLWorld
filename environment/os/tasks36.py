"""35 independent tasks on the existing desktop, with separate local demos.

Only fixtures, trusted target derivation and scoring contracts are added. All
actions are existing workflows.mutate operations; no solver operation exists.
"""
import copy
import csv
import io
import json
import random
from collections import Counter
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime,timedelta
from pathlib import Path

from judge36 import evaluate

SPEC=json.loads((Path(__file__).parent/'docs/TASK_CATALOGUE_36.json').read_text())['tasks']
TITLES=[
 'Batch file naming','Batch metadata filing','Select approved revisions','Preserve both conflict versions',
 'Filter contact fields in log copies','Set device connection scope',
 'Export event time slices','Set existing task triggers','Format document paragraphs','Control print queue states','Insert document page breaks',
 'Research handoff collection','Release documentation alignment','Field action guide','Migration configuration alignment',
 'Meeting print master','Incident timeline and response report','Working-directory differential sync','Repair a failed task dependency graph',
 'Create and test a rollback point','Personnel change verification','Inventory lot reconciliation','Three-way field merge',
 'Restore historical processing settings','Recover a signed software release','Restart a project from historical snapshots',
 'Camera ingest and caption correction','Proof and first print submission','Repair an offline resource cache',
 'Migrate and open a nested workspace','Recover build and test failures','Redact and archive incident evidence',
 'Repair scheduled share distribution','Storage cleanup and service restoration','Withdraw and replace a submitted print revision']
CASES=[{'id':s['id'],'title':TITLES[i],'difficulty':s['level'],'family':'task36','task':'Complete the requested business outcome using the method shown in the demonstrations.'} for i,s in enumerate(SPEC)]
CASE_BY_ID={x['id']:x for x in CASES}
SPEC_BY_ID={x['id']:x for x in SPEC}


def dump(value,indent=2):return json.dumps(value,indent=indent,ensure_ascii=False)
def csv_text(rows):
    stream=io.StringIO(newline='');writer=csv.writer(stream,lineterminator='\n');writer.writerows(rows);return stream.getvalue()


def byte_display(value,convention):
    if convention==0:return f'{value} B'
    scale,places,unit=(1024,3,'KiB') if convention==1 else (1048576,6,'MiB')
    number=(Decimal(value)/Decimal(scale)).quantize(Decimal(1).scaleb(-places),rounding=ROUND_HALF_UP)
    return f'{number:.{places}f} {unit}'


class Build:
    def __init__(self,cid,c,seed,scope,base=None):
        import workflows as w
        self.w=w; self.cid=cid;self.c=c;self.seed=seed;self.scope=scope
        self.rng=random.Random(seed);self.actions=[];self.goals=[];self.writable={};self.shadow=None
        self.case=copy.deepcopy(CASE_BY_ID[cid]);self.case.update(domain='task36',pipeline=[])
        if base is None:
            source=w._generate_fixture('OS-LH-01',0,seed)
            self.s=copy.deepcopy(source['initial'])
            self.s.update(files=[w.node('desktop',None,'Desktop'),w.node('documents',None,'Documents'),w.node('downloads',None,'Downloads'),
                w.node('projects',None,'Projects'),w.node('project','projects',f'Project-{seed}'),w.node('recycle',None,'Recycle Bin')],
                jobs=[],processes=[],transfers=[],events=[],print_queue=[],receipts=[],backup_history=[],log_exports=[])
            self.s['settings'].update({'tools.enabled':True,'tools.compiler':True,'tools.signer':True,'network.offline':False,'backup.include-text':True,'cache.contacts':True})
        else:
            self.s=copy.deepcopy(base['initial']);self.case.update(domain=base['case']['domain'],pipeline=base['case']['pipeline'],recovery=base['case'].get('recovery'))
        self.s['case_id']=cid;self.s['project']=f'Project-{seed}' if base is None else self.s['project']
        self.root=self.folder('Workspace','project') if base is None else 'inputs'
        self.output=self.folder('Output','project') if base is None else 'project'
        self.file('Unrelated note.txt','Protected unrelated business note. Do not modify.',parent='documents')

        self.request='Use the supplied business records. Preserve source documents and unrelated objects.'
        self.rule='';self.subject='the demonstrated local method'
    def file(self,name,content='',parent=None,**kw):
        assert self.shadow is None,'All initial fixtures must be installed before planning'
        identifier=kw.pop('identifier',f'n{len(self.s["files"])}')
        self.s['files'].append(self.w.node(identifier,parent or self.root,name,kw.pop('kind','text'),content,**kw));return identifier
    def folder(self,name,parent=None):return self.file(name,parent=parent or 'project',kind='folder')
    def allow(self,collection,identifier,*fields):
        if collection=='settings':
            self.writable.setdefault('settings',[]).append(identifier)
        else:self.writable.setdefault(collection,{}).setdefault(identifier,[]).extend(fields)
    def act(self,**action):
        if self.shadow is None:self.shadow=copy.deepcopy(self.s)
        self.actions.append(action)
        return self.w.mutate(self.shadow,action,self.case)
    def goal(self,predicate_type,**params):self.goals.append({'type':predicate_type,**params})
    def write(self,identifier,value,mode=None):
        mode=output_mode(self.cid,self.c,self.scope,mode)
        self.allow('files',identifier,'content','revision');self.act(op='write',target=identifier,content=value)
        self.goal('content',id=identifier,value=value,mode=mode)
    def field(self,collection,identifier,field,value):
        self.allow(collection,identifier,field);self.goal('field',collection=collection,id=identifier,field=field,value=value)
    def run(self,kind,input,output,dependency='',name=None,trigger='manual'):
        name=name or f'{len((self.shadow or self.s)["jobs"])+1:02}-{kind}'
        jid=self.act(op='create-job',name=name,kind=kind,input=input,output=output,dependency=dependency,trigger=trigger)
        outcome=self.act(op='run-job',target=jid)
        if isinstance(outcome,dict) and outcome.get('status')=='Failed':raise ValueError(f'{self.cid}: {name}: {outcome}')
        return name,jid
    def complete(self):
        # Source request is public business data, not the hidden rule or plan.
        if self.shadow is None:self.shadow=copy.deepcopy(self.s)
        selectors={}
        initial_ids={f['id'] for f in self.s['files']}
        for f in self.shadow['files']:
            if f['id'] not in initial_ids and not f.get('deleted'):
                selectors[f['id']]={'path':self.w.path(self.shadow,f['id'])}
        for j in self.shadow['jobs']:
            if j['id'] not in {x['id'] for x in self.s['jobs']}:
                selectors[j['id']]={'job_kind':j['kind'],'job_name':j['name']}
        case=copy.deepcopy(self.case);case['task']=self.request+' Use the '+VIDEOICL_RELATIONS[self.cid]+' demonstrated in the video.'+(VIDEOICL_OUTPUTS.get(self.cid,'')+' For JSON outputs, use the declared field names and value types; indentation and object key order are unrestricted.' if self.scope=='query' else '')
        return {'benchmark_version':self.w.VERSION,'schema_version':self.w.SCHEMA_VERSION,'implementation':copy.deepcopy(self.w.IMPLEMENTATION),
            'case':case,'seed':self.seed,'convention':self.c,'plan_variant':'module-demo' if self.scope=='demo' else 'standard',
            'initial':copy.deepcopy(self.s),'state':copy.deepcopy(self.s),'events':[], 'reference':self.actions,
            'task36_scope':self.scope,'task36':True,'_judge36':{'goals':self.goals,'writable':self.writable,'selectors':selectors,
                'delivery_destinations':[[j['input'],j['output']] for j in self.shadow['jobs'] if j['kind']=='deliver'], 'copy_sources':dict(Counter(f['source'] for f in self.shadow['files'] if not f.get('deleted') and f['id'] not in initial_ids and f.get('source') and not f.get('generated_by'))),
                'active_deliveries':sum(j['kind']=='deliver' and j['status'] in {'Completed','Scheduled'} for j in self.shadow['jobs'])},
            '_brief36':{'method':self.rule,'scope':'local-method-only' if self.scope=='demo' else 'full-query','instruction':self.request}}


def _easy(b,num):
    c=b.c;n=3 if b.scope=='demo' else 6
    if num==1:
        topics=b.rng.sample(['annual','Quarterly','field','FINAL','regional','technical','monthly','Planning','Service','Research'],n)
        ids=[b.file(f'{x}  report {b.rng.randrange(10,99)}.txt',f'Protected body {b.seed}/{i}') for i,x in enumerate(topics)]
        b.request=f'Rename all {n} text documents in Workspace; preserve extensions, content and all other files.'
        b.rule=['Replace word spaces with hyphens.','Replace word spaces with underscores.','Title-case each word, single spaces.'][c]
        for fid in ids:
            f=b.w.get_file(b.s,fid);stem=f['name'][:-4];new=(('-' if c==0 else '_').join(stem.split()) if c<2 else ' '.join(x.capitalize() for x in stem.split()))+'.txt'
            b.allow('files',fid,'name');b.act(op='rename',target=fid,name=new);b.goal('file',id=fid,fields={'name':new})
    elif num==2:
        sources=[b.folder(f'Project-{i}',b.root) for i in range(2)]
        targets={};ids=[]
        attributes=[('csv',0,0),('csv',1,1),('txt',0,1),('txt',1,0),('json',0,0),('json',1,1)]
        b.rng.shuffle(attributes)
        for i,(ext,p,resource) in enumerate(attributes):
            key=f'resource-{resource}'
            fid=b.file(f'asset-{i}.{ext}',f'Body {i}/{b.seed}',parent=sources[p],resource_key=key)
            ids.append((fid,ext,key,p))
        for scheme in range(3):
            root=b.folder(['By type','By project','By key'][scheme],b.output)
            for fid,ext,key,p in ids:
                path=[ext] if scheme==0 else [f'Project-{p}',ext] if scheme==1 else [key]
                parent=root
                for name in path:
                    marker=(parent,name)
                    if marker not in targets:targets[marker]=b.folder(name,parent)
                    parent=targets[marker]
                targets[(scheme,fid)]=parent
        b.request='Move all asset files from the two source projects into the supplied filing tree; preserve their contents and unrelated files.'
        b.rule=['File by extension.','File by source project, then extension.','File by resource_key.'][c]
        for fid,*_ in ids:
            parent=targets[(c,fid)];b.allow('files',fid,'parent');b.act(op='move',target=fid,parent=parent);b.goal('file',id=fid,fields={'parent':parent})
    elif num==3:
        groups=[]
        for i in range(3 if b.scope=='demo' else 4):
            root=b.folder(f'Document-{i}',b.root);target=b.folder('Selected',root);versions=[]
            tokens=b.rng.sample(range(100,999),4);small=b.rng.randrange(75,125);middle=small+b.rng.randrange(40,90);large=middle+b.rng.randrange(40,90);revision=b.rng.randrange(5,15)
            for j,(revision,size,approved) in enumerate([(revision,middle,True),(revision-1,small,True),(revision-2,large,True),(revision+20,large+50,False)]):
                fid=b.file(f'edition-r{revision}.txt',chr(65+i)*size,parent=root,revision=revision,approved=approved,resource_key=f'doc-{i}');versions.append(fid)
            groups.append((target,versions))
        b.request='For each document group, copy exactly one approved version into its Selected folder. Preserve all originals.'
        b.rule=['Choose the highest approved revision.','Choose the smallest approved byte size.','Choose the largest approved byte size.'][c]
        for parent,versions in groups:
            source=versions[c];f=b.w.get_file(b.s,source);b.act(op='copy',target=source,parent=parent)
            b.goal('copy',parent=parent,name=f['name'],source=source);b.goal('members',parent=parent,names=[f['name']])
    elif num==4:
        pairs=[]
        for i in range(3 if b.scope=='demo' else 4):
            src=b.folder(f'Incoming-{i}',b.root);dst=b.folder(f'Target-{i}',b.output)
            stem=f'record-{b.rng.randrange(100,999)}';oldrev=b.rng.randrange(1,5);newrev=b.rng.randrange(6,12)
            old=b.file(stem+'.txt',f'Existing {i}/{b.seed}',parent=dst,revision=oldrev);new=b.file(stem+'.txt',f'Incoming {i}/{b.seed}',parent=src,revision=newrev);pairs.append((old,new,dst,stem,oldrev,newrev))
        b.request='Resolve the supplied name conflicts while preserving both contents. Leave non-conflicting files unchanged.'
        b.rule=['Existing keeps its name; incoming gets -incoming.','Incoming keeps its name; existing gets -previous.','Both get their own -r{revision} suffix.'][c]
        for old,new,dst,stem,oldrev,newrev in pairs:
            oldname=[stem+'.txt',stem+'-previous.txt',f'{stem}-r{oldrev}.txt'][c];newname=[stem+'-incoming.txt',stem+'.txt',f'{stem}-r{newrev}.txt'][c]
            for fid,name in [(old,oldname),(new,newname)]:
                b.allow('files',fid,'name');b.act(op='rename',target=fid,name=name);b.goal('file',id=fid,fields={'name':name})
            b.allow('files',new,'parent');b.act(op='move',target=new,parent=dst);b.goal('file',id=new,fields={'parent':dst})
    elif num==6:
        ids=[]
        for i in range(n):
            rows=[{'event_id':f'EV-{b.seed}-{i}-{j}','time':f'2026-10-15T09:0{j}:00','operator_id':f'{1000+b.seed%997+i*2+j}','contact':f'op{1000+b.seed%997+i*2+j}@example.test','message':'Connection checked'} for j in range(2)]
            b.file(f'original-{i}.jsonl','\n'.join(json.dumps(x) for x in rows));target=b.file(f'copy-{i}.jsonl','\n'.join(json.dumps(x) for x in rows),parent=b.output);ids.append((target,rows))
        b.request='Filter contact fields in every copy-*.jsonl document in Output. Preserve originals, event identifiers, timestamps and all other fields.'
        b.rule=['Mask contact values as [REDACTED].','Remove contact fields.','Replace contact with Contact-{operator_id}.'][c]
        for fid,rows in ids:
            result=copy.deepcopy(rows)
            for row in result:
                if c==1:del row['contact']
                else:row['contact']='[REDACTED]' if c==0 else 'Contact-'+row['operator_id']
            b.write(fid,'\n'.join(json.dumps(x) for x in result),mode='jsonl')
    elif num==7:
        kinds=['Camera','Printer','Network storage']*2;b.rng.shuffle(kinds)
        b.s['devices']=[{'id':f'd{i}','name':f'{kind} unit {i}','kind':kind,'connected':bool(i%2)} for i,kind in enumerate(kinds)]
        b.request='Set connection states for the six unit devices using the demonstrated device-category policy; preserve other device properties.'
        if b.scope=='demo':b.s['devices'].append({'id':'scope-control-device','name':'Protected office printer','kind':'Printer','connected':True})
        selected=['Camera','Printer','Network storage'][c];b.rule=f'Connect only {selected} devices; disconnect other target categories.'
        for d in b.s['devices']:
            if ' unit ' not in d['name']:continue
            value=d['kind']==selected;b.field('devices',d['id'],'connected',value);b.act(op='device',target=d['id'],connected=value)
    elif num==8:
        anchors=[];start=datetime(2026,10,15,7+b.seed%5,b.seed%31)
        for i in range(3 if b.scope=='demo' else 4):
            t=start+timedelta(hours=i);rows=[{'time':(t+timedelta(seconds=s)).isoformat(),'event_id':f'EV{i}-{j}','message':'Incident anchor' if s==0 else f'Event record {j}'} for j,s in enumerate([-121,-120,-90,-60,0,60,90,120,121])]
            fid=b.file(f'channel-{i}.jsonl','\n'.join(json.dumps(x) for x in rows),log_channel=f'Channel {i}');anchors.append((fid,t))
        b.request='Export one independent file for each channel anchor: '+', '.join(f'Channel {i}: {t.isoformat()}' for i,(_,t) in enumerate(anchors))+'. Intervals are closed; all times use the same local timezone.'
        b.rule=['Export from two minutes before the anchor through the anchor.','Export from the anchor through two minutes after it.','Export one minute before through one minute after.'][c]
        for i,(source,t) in enumerate(anchors):
            begin=t-timedelta(minutes=[2,0,1][c]);end=t+timedelta(minutes=[0,2,1][c]);name=f'window-{i}.jsonl'
            b.act(op='export-log',target=source,parent=b.output,name=name,start=begin.isoformat(),end=end.isoformat())
            b.goal('export',source=source,parent=b.output,name=name,start=begin.isoformat(),end=end.isoformat())
    elif num==9:
        for i in range(n):b.s['jobs'].append({'id':f'job-{i+1}','name':f'Existing task {i}','kind':'inventory','input':b.root,'output':b.output,'dependency':'','trigger':['idle','manual','plugged-in'][i%3],'status':'Ready','error':None,'artifact':None})
        trigger=['manual','idle','plugged-in'][c];b.request='Update only Trigger on all Existing task entries. Do not run them or change paths/dependencies.';b.rule=f'Set target triggers to {trigger}.'
        for j in b.s['jobs']:b.field('jobs',j['id'],'trigger',trigger);b.act(op='update-job',target=j['id'],trigger=trigger)
    elif num==10:
        docs=[]
        for i in range(n):
            first=f'{b.rng.choice(["Inventory","Transport","Planning","Inspection"])} record {b.seed+i}\ncontains {b.rng.randrange(11,99)} entries.'
            second=f'{b.rng.choice(["Regional","Annual","Field","Research"])} summary\nwas checked by team {b.rng.randrange(2,20)}.'
            before=f'# Report {i}\n\n{first}\n\n{second}\n\n```\nKeep  code\nexactly.\n```\n'
            docs.append((b.file(f'working-{i}.txt',before,parent=b.output),before,first,second))
        b.request='Format only the two body paragraphs in each working document. Preserve headings and fenced code.'
        b.rule=['Join each paragraph into one line; one blank line between paragraphs.','Add two spaces at each paragraph start; keep internal line breaks.','Join each paragraph into one bullet line beginning - .'][c]
        for fid,before,first,second in docs:
            transform=lambda text:' '.join(text.splitlines()) if c==0 else '  '+text if c==1 else '- '+' '.join(text.splitlines())
            b.write(fid,before.replace(first,transform(first)).replace(second,transform(second)))
    elif num==11:
        for d in b.s['devices']:d['connected']=True
        page_counts=[3,4,5,6,7,8,9,10] if b.scope=='demo' else [3,4,5,6,8,9];b.rng.shuffle(page_counts)
        for i,pages in enumerate(page_counts):b.s['print_queue'].append({'id':f'print-{i+1}','name':f'Packet {i}','status':'Queued','printer':'printer','paper':'A4','duplex':True,'order':'forward','pages':[{'name':'report.txt','page':j+1} for j in range(pages)],'documents':[]})
        if b.scope=='demo':b.s['print_queue'].append({'id':'scope-control-queue','name':'Unrelated draft','status':'Queued','printer':'printer','paper':'A4','duplex':True,'order':'forward','pages':[{'name':'unrelated.txt','page':j+1} for j in range(10)],'documents':[]})
        limit=[4,6,8][c];b.request='Set the Packet queue states in the supplied batch using the demonstrated page-count condition. Never cancel a packet.';b.rule=f'Pause packets with more than {limit} pages; leave other target packets queued.'
        for q in b.s['print_queue']:
            if q['name'].startswith('Packet ') and len(q['pages'])>limit:b.field('print_queue',q['id'],'status','Paused');b.act(op='print-control',target=q['id'],status='Paused')
    elif num==12:
        docs=[]
        for i in range(n):
            text=f'# Document {b.seed}-{i}\nBody records: {b.rng.randrange(10,99)}.\nAppendix\nDetails for site {b.rng.randrange(10,99)}.\nReferences\nSources {b.seed+i}.\nSignature\nTeam {i+1}.\n';docs.append((b.file(f'pages-{i}.txt',text,parent=b.output),text))
        heading=['Appendix','References','Signature'][c];b.request='Insert exactly one page break in each pages-*.txt document using the demonstrated heading boundary. Preserve every text character.';b.rule=f'Insert a page break immediately before {heading}.'
        for fid,text in docs:b.write(fid,text.replace(heading,'\f'+heading,1))


def _medium(b,num):
    c=b.c;demo=b.scope=='demo';r=b.rng
    if num==1:
        categories=['Data','Notes','Protocol'];sources=[];targets={}
        projects=[b.folder(f'Source-{i}',b.root) for i in range(2)]
        for i,category in enumerate(categories):
            project=projects[i%2]
            for revision in [1,3]:
                fid=b.file(f'{category.lower()}-r{revision}.txt',f'{category} content revision {revision} for {b.seed}',parent=project,approved=True,revision=revision,resource_key=f'K{i}')
                if revision==3:sources.append((fid,category,i%2,f'K{i}'))
            b.file(f'{category.lower()}-draft.txt','Do not deliver',parent=project,approved=False,revision=99,resource_key=f'K{i}')
        for scheme in range(3):
            top=b.folder(['By category','By source','By key'][scheme],b.output)
            for fid,category,project,key in sources:
                name=[category,f'Source-{project}',key][scheme]
                existing=next((x['id'] for x in b.s['files'] if x['parent']==top and x['name']==name),None)
                targets[(scheme,fid)]=existing or b.folder(name,top)
        b.request='Deliver K0 with its required K1 and K2 attachments, using each latest approved revision. Preserve all source versions and local edits. Create the collection in Output.' if not demo else 'The three revision-3 resources are already selected and approved. Demonstrate only their grouping in Output; preserve all sources.'
        b.rule=['Group by resource category.','Group by source project.','Group by resource_key.'][c]
        for fid,*_ in sources:
            f=b.w.get_file(b.s,fid);parent=targets[(c,fid)];b.act(op='copy',target=fid,parent=parent);b.goal('copy',parent=parent,name=f['name'],source=fid)
        for parent in set(targets[(c,fid)] for fid,*_ in sources):b.goal('members',parent=parent,names=[b.w.get_file(b.s,fid)['name'] for fid,*_ in sources if targets[(c,fid)]==parent])
    elif num==2:
        version=f'2.{b.seed%9}.7';changes=[{'change_id':f'CH{i}','summary':summary,'approved':i!=2} for i,summary in enumerate(['Fix import','Update assets','Withdrawn feature'])]
        b.file('Request-r1.json',dump({'revision':1,'version':'1.0.0','changes':['CH2']}));b.file('Request-r2.json',dump({'revision':2,'valid':True,'version':version,'changes':['CH0','CH1']}))
        b.file('source.js',f'export const releaseVersion = "{version}";\n');b.file('changes.json',dump(changes))
        config=b.file('config.json',dump({'release_version':'1.0.0'}),parent=b.output);notes=b.file('release-notes.txt','Version: 1.0.0\n',parent=b.output);index=b.file('delivery-index.json','{}',parent=b.output)
        b.request='Prepare current release documentation from the highest valid request. Align working config, release notes and delivery index with the source version; exclude withdrawn changes.'
        b.rule=['Write change_id: summary.','Write summary [change_id].','Write [change_id] summary.'][c]
        lines=[f"{x['change_id']}: {x['summary']}" if c==0 else f"{x['summary']} [{x['change_id']}]" if c==1 else f"[{x['change_id']}] {x['summary']}" for x in changes if x['approved']]
        b.write(config,dump({'release_version':version}),mode='json');b.write(notes,'Version: '+version+'\n'+'\n'.join(lines)+'\n');b.write(index,dump({'version':version,'notes':'release-notes.txt','config':'config.json','changes':['CH0','CH1']}),mode='json')
    elif num==3:
        people=[{'person_id':'P1','name':'Alex','phone':'555-0101'},{'person_id':'P2','name':'Alex','phone':'555-0102'}]
        plans=[{'slot_id':f'S{i}','person_id':f'P{i+1}','site':f'Site-{i}','time':f'{9+i}:00','resources':[f'MAP-{i}'],'active':True} for i in range(2)]
        b.file('people.json',dump(people));b.file('arrangements.json',dump(plans+[{'slot_id':'S9','active':False}]));b.file('resources.json',dump({'MAP-0':'map-east.csv','MAP-1':'map-west.csv'}));out=b.file('field-guide.json','[]',parent=b.output)
        b.request='Prepare one guide entry per active slot, linking the exact person, site, time and resources by IDs. Exclude withdrawn slots; save field-guide.json.'
        b.rule=['Display Name <phone>.','Display Name (phone).','Display phone — Name.'][c]
        result=[]
        for p,slot in zip(people,plans):
            contact=f"{p['name']} <{p['phone']}>" if c==0 else f"{p['name']} ({p['phone']})" if c==1 else f"{p['phone']} — {p['name']}"
            result.append({**slot,'contact':contact})
        b.write(out,dump(result),mode='json')
    elif num==4:
        newroot=f'/Projects/Project-{b.seed}/Workspace/New/'
        resources=[{'number':3,'category':'Code','name':'z-source.js'},{'number':1,'category':'Config','name':'b-settings.json'},{'number':2,'category':'Data','name':'a-data.csv'},{'number':6,'category':'Code','name':'c-tool.js'},{'number':5,'category':'Config','name':'e-flags.json'},{'number':4,'category':'Data','name':'d-report.csv'}]
        b.file('migration-request.json',dump({'new_root':newroot,'resources':resources,'preferences':{'theme':'Light','tab_width':4}}))
        manifest=b.file('workspace.json',dump({'entry':'/old/z-source.js','references':['/old/'+x['name'] for x in resources]}),parent=b.output)
        settings=b.file('app-settings.json',dump({'workspace_root':'/old/','startup_path':'/old/z-source.js','preferences':{'theme':'Light','tab_width':4}}),parent=b.output)
        b.request='Repair the already-copied workspace configuration using migration-request.json. Preserve preferences and all references, with absolute paths to the new root.'
        b.rule=['Order references by target path.','Order references by logical number.','Order Code, Config, Data, then by path.'][c]
        order=sorted(resources,key=(lambda x:x['name']) if c==0 else (lambda x:x['number']) if c==1 else (lambda x:({'Code':0,'Config':1,'Data':2}[x['category']],x['name'])))
        b.write(manifest,dump({'entry':newroot+'z-source.js','references':[newroot+x['name'] for x in order]}),mode='json')
        b.write(settings,dump({'workspace_root':newroot,'startup_path':newroot+'z-source.js','preferences':{'theme':'Light','tab_width':4}}),mode='json')
    elif num==5:
        chapters=[{'id':'A','title':'Opening','revision':2,'body':'Welcome.\nAgenda.'},{'id':'B','title':'Findings','revision':4,'body':'Finding one.\nFinding two.'},{'id':'C','title':'Actions','revision':3,'body':'Next action.\nOwner.'}]
        b.file('agenda.json',dump({'order':['A','B','C'],'page_line_limit':5,'approved':chapters}));master=b.file('print-master.txt','',parent=b.output);toc=b.file('contents.json','[]',parent=b.output)
        b.request='Assemble the approved chapters in agenda order. Number chapter headings using the demonstrated format, start each chapter on a new page, and save an accurate contents table. Five lines maximum per page.'
        b.rule=['Use Arabic chapter numbers: 1., 2., 3.','Use Roman chapter numbers: I., II., III.','Use letter chapter numbers: A., B., C.'][c]
        prefixes=[['1.','2.','3.'],['I.','II.','III.'],['A.','B.','C.']][c]
        b.write(master,'\f'.join(f'{p} {ch["title"]}\n{ch["body"]}\n' for p,ch in zip(prefixes,chapters)))
        b.write(toc,dump([{'chapter_id':ch['id'],'heading':p+' '+ch['title'],'page':i+1} for i,(p,ch) in enumerate(zip(prefixes,chapters))]),mode='json')
    elif num==6:
        rows=[{'event_id':'EV1','time':'2026-10-15T09:00:00','message':'Connection lost'},{'event_id':'EV2','time':'2026-10-15T09:05:00','message':'Repair applied'},{'event_id':'EV3','time':'2026-10-15T09:07:00','message':'Recovery verified'}]
        b.file('application-export.json',dump(rows[:2]));b.file('system-export.json',dump(rows[1:]));b.file('response.json',dump({'incident':'INC1','events':['EV1','EV2','EV3'],'verified_by':'EV3'}));out=b.file('timeline.json','{}',parent=b.output)
        b.request='Produce an incident timeline from both exports, deduplicating event IDs and retaining channel provenance. Base the response conclusion on the actual verification record.'
        b.rule=['Use YYYY-MM-DD HH:MM:SS.','Use YYYY/MM/DD HH:MM:SS.','Use YYYY-MM-DDTHH:MM:SS.'][c]
        result=[]
        for i,row in enumerate(rows):
            time=row['time'].replace('T',' ') if c<2 else row['time']
            if c==1:time=time.replace('-','/')
            result.append({**row,'time':time,'channels':['Application'] if i==0 else ['Application','System'] if i==1 else ['System']})
        b.write(out,dump({'incident':'INC1','events':result,'recovered':True,'verification_event':'EV3'}),mode='json')
    elif num==7:
        previous=b.folder('Previous',b.output);snapshot=b.folder('Snapshot',b.output);src=b.folder('Source',b.root);target=b.folder('Active',b.output)
        old=b.file('records.csv','id,value\nR1,10\n',parent=target,resource_key='records',revision=1)
        new=b.file('records.csv','id,value\nR1,20\n',parent=src,resource_key='records',revision=2)
        retired=b.file('retired.txt','Retired but recoverable',parent=target);fresh=b.file('added.txt','New approved data',parent=src)
        b.file('local-edit.txt','Preserve this local annotation',parent=target)
        b.request='Synchronize Active: replace records.csv with Source revision 2, add added.txt, and remove retired.txt from the active set. Preserve local-edit.txt and every replaced/retired content.'
        b.rule=['Move prior content into Previous.','Keep prior content in place with -previous suffix.','Copy prior content into Snapshot before removing the active original.'][c]
        for fid in [old,retired]:
            f=b.w.get_file(b.s,fid)
            if c==0:b.allow('files',fid,'parent');b.act(op='move',target=fid,parent=previous);b.goal('file',id=fid,fields={'parent':previous})
            elif c==1:
                name=f['name'].rsplit('.',1);name=name[0]+'-previous.'+name[1];b.allow('files',fid,'name');b.act(op='rename',target=fid,name=name);b.goal('file',id=fid,fields={'name':name})
            else:
                b.act(op='copy',target=fid,parent=snapshot);b.goal('copy',parent=snapshot,name=f['name'],source=fid);b.allow('files',fid,'deleted');b.act(op='delete',target=fid);b.goal('file',id=fid,fields={'deleted':True})
        for fid in [new,fresh]:
            f=b.w.get_file(b.s,fid);b.act(op='copy',target=fid,parent=target);b.goal('copy',parent=target,name=f['name'],source=fid)
    elif num==8:
        b.file('records.csv','id,value\nR1,7\n',parent=b.root)
        b.s['jobs'].append({'id':'old-task','name':'Broken validation','kind':'validate','input':b.root,'output':b.output,'dependency':'Missing inventory','trigger':'manual','status':'Failed','error':'Dependency has not completed.','artifact':None})
        b.request='Replace the affected failed pipeline using the supplied business stages: inventory, validate, index, package, verify, deliver. All stages consume Workspace and write Output. Preserve the unrelated existing task record.' if not demo else 'Demonstrate names for two example stages, inventory then validate, using Workspace as input and Output as output. Do not repair the unrelated existing task.'
        b.rule=['Name stages NN-operation.','Name stages operation-NN.','Name stages stepNN_operation.'][c]
        previous=''
        kinds=['inventory','validate'] if demo else ['inventory','validate','index','package','verify','deliver']
        for i,kind in enumerate(kinds):
            name=f'{i+1:02}-{kind}' if c==0 else f'{kind}-{i+1:02}' if c==1 else f'step{i+1:02}_{kind}'
            previous,jid=b.run(kind,b.root,b.output,previous,name)
            b.goal('job',name=name,fields={'kind':kind,'input':b.root,'output':b.output,'dependency':'' if i==0 else prior,'status':'Completed'});prior=name
        b.goal('pipeline',final=kinds[-1],input=b.root,kinds=kinds)
    elif num==9:
        b.case['domain']='backup';b.s['settings']['backup.scope']='all';b.s['settings']['backup.include-text']=True
        for i,name in enumerate(['records.csv','preferences.json','notes.txt','inventory.csv']):b.file(name,'{"enabled":true}' if name.endswith('.json') else 'id,value\nR1,7\n' if name.endswith('.csv') else 'Protected notes',identifier=f'source-{i}')
        stage={}
        for scheme in range(3):
            for kind in ['inventory','backup','restore','compare','verify']:
                label=kind.title() if scheme==0 else 'Recovery' if kind=='restore' else 'Snapshots' if scheme==2 and kind=='backup' else 'Reports'
                marker=(scheme,label)
                if marker not in stage:
                    rootname=['Stage outputs','Central outputs','Snapshot outputs'][scheme]
                    root=next((f['id'] for f in b.s['files'] if f['parent']==b.output and f['name']==rootname),None) or b.folder(rootname,b.output)
                    stage[marker]=b.folder(label,root)
                stage[(scheme,kind)]=stage[marker]
        b.request='Create a rollback snapshot from all four Workspace resources, restore it to an empty supplied destination and compare actual content. Preserve all source resources.' if not demo else 'Demonstrate output organization for inventory, backup and restore stages only, using the four prepared resources. Do not perform the full restore exercise.'
        b.rule=['Use separate stage output folders.','Use central Reports; restore into Recovery.','Use Snapshots for backup, Reports for other reports, and Recovery for restored files.'][c]
        prev=''
        for kind in (['inventory','backup','restore'] if demo else ['inventory','backup','restore','compare','verify']):
            dest=stage[(c,kind)];prev,jid=b.run(kind,b.root,dest,prev)
            b.goal('job',name=prev,fields={'output':dest,'status':'Completed'})
        b.goal('pipeline',final='restore' if demo else 'verify',input=b.root,kinds=['inventory','backup','restore'] if demo else ['inventory','backup','restore','compare','verify'])
    elif num==10:
        records=[{'request_id':'R1','person_id':'P1','revision':2,'new_phone':'555-0199','evidence_matches':True,'withdrawn':False},{'request_id':'R2','person_id':'P2','revision':1,'new_phone':'555-0188','evidence_matches':False,'withdrawn':False},{'request_id':'R3','person_id':'P3','revision':1,'new_phone':'555-0177','evidence_matches':True,'withdrawn':True}]
        people=[{'person_id':f'P{i+1}','name':'Alex' if i<2 else 'Sam','phone':f'555-010{i}'} for i in range(3)]
        b.file('change-requests.json',dump(records));b.file('verification-policy.txt','Accept active latest requests only when evidence_matches is true. Match by person_id.');master=b.file('people-working.json',dump(people),parent=b.output);ack=b.file('acknowledgements.json','[]',parent=b.output)
        b.request='Verify personnel phone changes against the supplied evidence and policy. Update only approved fields, and produce an acknowledgement for every active request. Preserve withdrawn and rejected people.'
        b.rule=['Use Approved or Rejected.','Use accepted=true or false.','Use status=ok or error.'][c]
        result=copy.deepcopy(people);result[0]['phone']=records[0]['new_phone'];responses=[]
        for rec in records[:2]:
            ok=rec['evidence_matches'];response={'request_id':rec['request_id'],'person_id':rec['person_id']}
            response.update({'decision':'Approved' if ok else 'Rejected'} if c==0 else {'accepted':ok} if c==1 else {'status':'ok' if ok else 'error'});responses.append(response)
        b.write(master,dump(result),mode='json');b.write(ack,dump(responses),mode='json')
    elif num==11:
        rows=[{'record_id':'T1','lot_id':'L1','kind':'receipt','quantity':12,'active':True},{'record_id':'T2','lot_id':'L1','kind':'issue','quantity':3,'active':True},{'record_id':'T3','lot_id':'L2','kind':'return','quantity':4,'active':True},{'record_id':'T4','lot_id':'L1','kind':'receipt','quantity':99,'active':False}]
        products=[{'lot_id':'L1','opening':20,'box':12,'pack':5},{'lot_id':'L2','opening':17,'box':6,'pack':4}]
        b.file('transactions.json',dump(rows+[rows[0]]));b.file('lot-baselines.json',dump(products));stock=b.file('stock-working.json',dump([{'lot_id':'L1','quantity':'20 pcs'},{'lot_id':'L2','quantity':'17 pcs'}]),parent=b.output);diff=b.file('differences.json','[]',parent=b.output)
        b.request='Reconcile each inventory lot: opening + active receipts - active returns - active issues. Deduplicate record_id, exclude withdrawn transactions, and save corrected stock plus lot differences. Unit capacities are in lot-baselines.json.'
        b.rule=['Display N pcs.','Display C box + R pcs using the product box capacity.','Display P pack + R pcs using the product pack capacity.'][c]
        quantities=[29,13];result=[];changes=[]
        for item,total in zip(products,quantities):
            value=f'{total} pcs' if c==0 else f'{total//item["box"]} box + {total%item["box"]} pcs' if c==1 else f'{total//item["pack"]} pack + {total%item["pack"]} pcs'
            result.append({'lot_id':item['lot_id'],'quantity':value});changes.append({'lot_id':item['lot_id'],'before_pcs':item['opening'],'after_pcs':total,'difference_pcs':total-item['opening']})
        b.write(stock,dump(result),mode='json');b.write(diff,dump(changes),mode='json')
    elif num==12:
        x=b.rng.randrange(2,15);y=b.rng.randrange(20,50);newer=b.rng.choice([True,False])
        baseline={'project':f'P{b.seed}','timeout':x,'retries':y};main={'project':baseline['project'],'timeout':x+10,'retries':y+10,'main_only':'retain'};review={'project':baseline['project'],'timeout':x+11,'retries':y+11,'review_only':'retain'}
        times={'main':{'timeout':30 if newer else 10,'retries':10 if newer else 30},'review':{'timeout':10 if newer else 30,'retries':30 if newer else 10}}
        b.file('baseline.json',dump(baseline));b.file('main.json',dump(main));b.file('review.json',dump(review));b.file('field-times.json',dump(times));out=b.file('merged.json','{}',parent=b.output);report=b.file('merge-diff.json','{}',parent=b.output)
        b.request='Merge main and review against baseline by field. Preserve unique changes from both sides. Resolve conflicting fields using the demonstrated method and save merged content plus an accurate conflict record.'
        b.rule=['Conflicts use main values.','Conflicts use review values.','Conflicts use the newer field timestamp; ties use main.'][c]
        result={**main,'review_only':'retain'}
        if c==1:result.update(timeout=x+11,retries=y+11)
        elif c==2:result.update(timeout=x+10 if newer else x+11,retries=y+11 if newer else y+10)
        b.write(out,dump(result),mode='json');b.write(report,dump({'conflict_fields':['timeout','retries'],'values':{k:result[k] for k in ['timeout','retries']},'preserved_unique':['main_only','review_only']}),mode='json')


def _apply_old_plan(b,base,policy,adapt=None):
    plan=b.w.reference(base['case'],copy.deepcopy(b.shadow or b.s),policy)
    for action in plan:
        action=copy.deepcopy(action)
        if adapt:action=adapt(action)
        if action is None:continue
        if action['op']=='setting':b.allow('settings',action['key'])
        elif action['op']=='device':b.allow('devices',action['target'],'connected')
        elif action['op']=='device-access':b.allow('devices',action['target'],'access')
        elif action['op']=='download':b.allow('transfers',action['target'],'status','progress','attempts','error');b.allow('files',next(t['file'] for t in b.s['transfers'] if t['id']==action['target']),'downloaded')
        elif action['op']=='delete' and any(f['id']==action['target'] for f in b.s['files']):b.allow('files',action['target'],'deleted')
        elif action['op']=='update-job' and any(j['id']==action['target'] for j in b.s['jobs']):b.allow('jobs',action['target'],'input','output','dependency','trigger','status','error','artifact','snapshot','configuration')
        try:b.act(**action)
        except (ValueError,KeyError,TypeError):
            # Expected visible diagnostic attempts from the existing recovery
            # authoring plans are retained, never counted as success evidence.
            pass
    return b.shadow


def _pipeline_goal(b,kinds=None,final='deliver'):
    job=next(j for j in reversed(b.shadow['jobs']) if j['kind']==final and j['status'] in {'Completed','Scheduled'})
    b.goal('pipeline',input=job['input'],final=final,kinds=kinds or b.case['pipeline'])
    return job


def _hard(b,num,base):
    c=b.c;w=b.w;policy=copy.deepcopy(w.CONVENTIONS[0])
    if num==1:
        settings={'archive.format':'tar','verification.mode':'full','media.preview':'compact','scheduler.trigger':'idle'}
        b.file('history-wrong.json',dump({'run_id':'old-run','settings':{'archive.format':'zip'}}))
        b.file('history-selected.json',dump({'run_id':f'RUN-{b.seed}','settings':settings}))
        b.file('data.csv','id,value\nR1,42\n',parent=b.root);report=b.file('configuration-diff.txt','',parent=b.output)
        b.request=f'Restore only archive.format, verification.mode, media.preview and scheduler.trigger from RUN-{b.seed}. Run fresh validation/package/verification jobs and record before/after settings. Preserve history and unrelated settings.'
        b.rule=['Record key: before -> after per line.','Record CSV columns key,before,after.','Record a JSON array with key,before,after.'][c]
        diffs=[{'key':k,'before':b.s['settings'][k],'after':v} for k,v in settings.items()]
        for k,v in settings.items():b.allow('settings',k);b.act(op='setting',key=k,value=v);b.goal('field',collection='settings',id=k,field='',value=v)
        prev=''
        for kind in ['validate','package','verify']:prev,jid=b.run(kind,b.root,b.output,prev,trigger='idle')
        b.goal('pipeline',input=b.root,final='verify',kinds=['inventory','validate','index','package','verify']);b.goal('domain',name='configuration',settings=settings)
        text='\n'.join(f"{x['key']}: {x['before']} -> {x['after']}" for x in diffs) if c==0 else csv_text([['key','before','after']]+[[x['key'],x['before'],x['after']] for x in diffs]) if c==1 else dump(diffs)
        b.write(report,text,mode='json' if c==2 else None);return
    extra=None
    if num in {2,8,11,12}:extra=b.file({2:'release-changes.txt',8:'test-summary.txt',11:'maintenance-report.txt',12:'revision-request.txt'}[num],'',parent='project')
    if num==2:
        b.w.get_file(b.s,extra)['content']='Approved changes: CH1 Fix import; CH2 Update assets. Preserve release version.'
        b.rule=['change_id: summary','summary [change_id]','[change_id] summary'][c]
        b.request='Recover the current signed release: repair tool availability and staged entry/version alignment. Include CH1 Fix import and CH2 Update assets using the demonstrated notes format; preserve sources and previous release.'
        def adapt(action):
            if action['op']=='create-job' and action['kind']=='inventory':
                notes=next(f for f in (b.shadow or b.s)['files'] if not f.get('deleted') and f.get('source')=='source-1')
                version=json.loads(w.get_file(b.s,'source-2')['content'])['release_version']
                lines=[f'{cid}: {summary}' if c==0 else f'{summary} [{cid}]' if c==1 else f'[{cid}] {summary}' for cid,summary in [('CH1','Fix import'),('CH2','Update assets')]]
                b.act(op='write',target=notes['id'],content='Version: '+version+'\n'+'\n'.join(lines)+'\n')
            if action['op']=='write' and action['target'] in {f['id'] for f in (b.shadow or b.s)['files'] if f.get('source')=='source-1'}:
                version=json.loads(w.get_file(b.s,'source-2')['content'])['release_version']
                lines=[f'{cid}: {summary}' if c==0 else f'{summary} [{cid}]' if c==1 else f'[{cid}] {summary}' for cid,summary in [('CH1','Fix import'),('CH2','Update assets')]]
                action['content']='Version: '+version+'\n'+'\n'.join(lines)+'\n'
            return action
        _apply_old_plan(b,base,policy,adapt);_pipeline_goal(b)
        b.goal('domain',name='checks',keys=['release_version_consistent','delivery_source_scope'])
        notes=next(f for f in b.shadow['files'] if not f['deleted'] and f.get('source')=='source-1');b.goal('domain',name='resource_content',source='source-1',value=notes['content'],mode='trim-lines')
        signed=next(j for j in b.shadow['jobs'] if j['kind']=='sign' and j['status']=='Completed');b.goal('domain',name='signature',job=signed['id']);return
    if num==3:
        first=next(f['id'] for f in b.s['files'] if f['parent']=='project' and f['name']=='Recovery')
        second=b.folder('Restored',first);rb=b.folder('Restored','project');wb=b.folder('Workspace',rb);rc=b.folder('Recovered','project')
        desired=[second,wb,rc][c]
        b.rule=['Recovery/Restored, with Reports inside.','Restored/Workspace, with Reports inside.','Recovered, with Reports inside.'][c]
        b.request='Recover from the latest complete project snapshot, preserve all local edits, restore every scheduled task recorded in the snapshot, and pass restore-check. Use the demonstrated recovery layout.'
        plan=w.reference(base['case'],copy.deepcopy(b.s),policy)
        sim=copy.deepcopy(b.s)
        for a in plan:
            try:w.mutate(sim,a,base['case'])
            except (ValueError,KeyError,TypeError):pass
        old=next(j['output'] for j in sim['jobs'] if j['kind']=='restore');oldpath=w.path(sim,old);newpath=w.path(b.s,desired)
        def adapt(a):
            for k,v in list(a.items()):
                if isinstance(v,str):a[k]=desired if v==old else v.replace(oldpath,newpath)
            return a
        _apply_old_plan(b,base,policy,adapt);_pipeline_goal(b)
        b.goal('domain',name='checks',keys=['restored_schedule_configuration','latest_complete_snapshot','delivery_source_scope'])
        b.goal('probe',kind='restoration',target=desired);return
    if num==4:
        policy['preview']=['compact','review','detail'][c]
        b.rule=['Compact 640 x 360.','Review 1280 x 720.','Detailed 1920 x 1080.'][c]
        b.request='Import the approved current shoot, recover its caption download, correct clip_id associations, and deliver a verified catalogue and previews. Preserve all source media; use the demonstrated preview size.'
        _apply_old_plan(b,base,policy);_pipeline_goal(b)
        b.goal('domain',name='preview',preset=policy['preview']);b.goal('domain',name='checks',keys=['captioned_previews','media_catalogue_delivered','delivery_source_scope']);return
    if num==5:
        # Fixed public paper/duplex answers from the old fixture are removed.
        b.s['print_request']={}
        for f in b.s['files']:
            if f['id']=='source-0':f['content']='Approved meeting cover.\n'
        profile=[{'paper':'A4','duplex':True,'order':'forward'},{'paper':'Letter','duplex':True,'order':'forward'},{'paper':'A4','duplex':False,'order':'reverse'}][c]
        b.rule=['A4, duplex, forward.','Letter, duplex, forward.','A4, simplex, reverse.'][c]
        b.request='Prepare approved working documents, repair pagination, select a capable connected printer and submit exactly one proof-matching packet with the demonstrated printing profile.'
        # Plan with a condition-independent legacy request; it is not exposed.
        planning=copy.deepcopy(b.s);planning['print_request']={'paper':'A4','duplex':True}
        plan=w.reference(base['case'],planning,policy)
        for a in plan:
            a=copy.deepcopy(a)
            if a['op']=='setting':
                key=a['key'].removeprefix('printer.')
                if key in profile:a['value']=profile[key]
                b.allow('settings',a['key'])
            if a['op']=='device':b.allow('devices',a['target'],'connected')
            try:b.act(**a)
            except (ValueError,KeyError,TypeError):pass
        final=_pipeline_goal(b);b.goal('domain',name='print_profile',profile=profile);b.goal('domain',name='print_submission',input=final['input'],profile=profile);return
    if num==6:
        original={f'source-{i}':w.get_file(b.s,f'source-{i}')['name'] for i in range(4)}
        names={sid:name if c==0 else b.s['project']+'-'+name if c==1 else f'R{i}.'+name.rsplit('.',1)[-1] for i,(sid,name) in enumerate(original.items())}
        replacements={'reviewed-'+original[sid]:name for sid,name in names.items()}
        b.rule=['Keep original resource names.','Prefix each name with project_id-.','Use R0/R1/R2/R3 resource IDs as stems, preserving extensions.'][c]
        b.request='Repair the relay/downloads and missing contact cache, prepare local guide references, rebuild the cache, disconnect the network and pass offline-test. Preserve downloaded originals and use the demonstrated naming.'
        def adapt(a):
            for k,v in a.items():
                if isinstance(v,str):
                    for old,new in replacements.items():v=v.replace(old,new)
                    a[k]=v
            return a
        _apply_old_plan(b,base,policy,adapt);_pipeline_goal(b)
        job=next(j for j in reversed(b.shadow['jobs']) if j['kind']=='cache' and j['status']=='Completed');target=w.get_file(b.shadow,job['artifact'])['provenance']['processing']['materialized_folder']
        b.goal('probe',kind='offline',target=target)
        for sid,name in names.items():
            current=next(f for f in b.shadow['files'] if f.get('source')==sid and f['parent']==target and not f['deleted']);b.goal('file',id=current['id'],fields={'name':name})
        return
    if num==7:
        preserve=b.folder('Local-preserved','project')
        b.rule=['Use a fresh sibling workspace; leave the original destination untouched.','Rename local conflicting files with -local, then migrate into the original destination.','Copy local conflicts to Local-preserved before removing them, then migrate into the original destination.'][c]
        b.request='Migrate the nested workspace, preserve original sources and local destination edits, retain preferences, and pass workspace-open. Use the demonstrated collision-preservation method.'
        local=next((f for f in b.s['files'] if f['id']=='existing-workspace-edit'),None)
        if local and c==1:
            name=local['name'].replace('.js','-local.js');b.allow('files',local['id'],'name');b.act(op='rename',target=local['id'],name=name);b.goal('file',id=local['id'],fields={'name':name})
        elif local and c==2:
            b.act(op='copy',target=local['id'],parent=preserve);b.goal('copy',parent=preserve,name=local['name'],source=local['id']);b.allow('files',local['id'],'deleted');b.act(op='delete',target=local['id']);b.goal('file',id=local['id'],fields={'deleted':True})
        _apply_old_plan(b,base,policy);_pipeline_goal(b)
        job=next(j for j in reversed(b.shadow['jobs']) if j['kind']=='migrate' and j['status']=='Completed');target=w.get_file(b.shadow,job['artifact'])['provenance']['processing']['materialized_folder'];b.goal('probe',kind='workspace',target=target)
        if local:b.goal('domain',name='old_content',id=local['id'],content=local['content'])
        return
    if num==8:
        b.rule=['Write each key: value on a separate line.','Write a JSON object.','Write headers build_artifact,passed,assertions, then one row of comma-separated JSON values; preserve string quotes and the assertions array without CSV escaping.'][c]
        b.request='Recover the locked build and its independent configuration/test errors. Preserve the old output, pass real tests against public source specifications, save a faithful test summary and restore owner process states.'
        _apply_old_plan(b,base,policy);_pipeline_goal(b)
        b.goal('domain',name='checks',keys=['build_tests_passed','delivery_source_scope'])
        job=next(j for j in b.shadow['jobs'] if j['kind']=='test' and j['status']=='Completed');result=w.get_file(b.shadow,job['artifact'])['provenance']['processing'];summary={k:result[k] for k in ['build_artifact','passed','assertions']}
        text='\n'.join(k+': '+json.dumps(v) for k,v in summary.items()) if c==0 else dump(summary) if c==1 else summary_values(summary)
        b.write(extra,text,mode='json' if c==1 else None);return
    if num==9:
        policy['redaction']=['mask','remove','pseudonym'][c]
        base=copy.deepcopy(base);base['case']['pipeline'].insert(-1,'audit');b.case['pipeline']=base['case']['pipeline']
        b.rule=['Mask personal values, retaining fields.','Remove personal fields.','Use the existing stable pseudonym treatment.'][c]
        b.request='Export both log channels for the incident window, preserve originals, collect a traceable timeline and redact every field listed in the incident brief. Deliver verified evidence with an audit trail using the demonstrated treatment.'
        _apply_old_plan(b,base,policy);_pipeline_goal(b)
        b.goal('domain',name='checks',keys=['incident_logs_exported','incident_window_exact','delivery_redacted','evidence_fields_preserved','redacted_copies_intact'],redaction=policy['redaction']);return
    if num==10:
        trigger=['manual','idle','plugged-in'][c]
        b.rule=f'Use {trigger} for the final delivery task only.';b.request='Repair the correct recipient share connection/access, validate the exact payload with a fresh dry-run and save a verified distribution plan without dispatching it. Use the demonstrated final trigger.'
        def adapt(a):
            if a['op']=='create-job' and a['kind']=='deliver':a['trigger']=trigger
            return a
        _apply_old_plan(b,base,policy,adapt);job=_pipeline_goal(b)
        b.goal('field',collection='jobs',id=job['id'],field='trigger',value=trigger);b.goal('domain',name='checks',keys=['scheduled_not_dispatched','distribution_destination_connected','distribution_dry_run_valid','delivery_source_scope']);return
    if num==11:
        b.rule=['Display integer B.','Display KiB to three decimals.','Display MiB to six decimals.'][c]
        b.request='Verify a protective backup before deleting only regenerable cache, compact losslessly, restore each owner to its original state and pass storage-audit. Report actual released cache bytes using the demonstrated unit; preserve user annotations.'
        _apply_old_plan(b,base,policy);_pipeline_goal(b)
        keys=['backup_snapshots_retained','cache_scope_removed','maintenance_owner_restored','storage_accounting','lossless_compaction_effective'];b.goal('domain',name='checks',keys=keys)
        freed=sum(len(f['content'].encode()) for f in b.s['files'] if f.get('regenerable'))
        value=byte_display(freed,c)
        b.write(extra,f'released_bytes: {freed}\nreleased_display: {value}\n');return
    if num==12:
        b.s['print_queue'].append({'id':'print-unrelated','name':'Unrelated packet','task':'unrelated-producer','status':'Queued','printer':b.s['print_queue'][0]['printer'],'paper':'A4','duplex':False,'order':'forward','pages':[{'name':'unrelated.txt','page':1,'lines':1}],'documents':[{'name':'unrelated.txt','content':'Unrelated protected content.','source':'unrelated-source'}]})
        b.rule=['[r8] Title','Title [r8]','r8 - Title'][c]
        b.request='Withdraw only the previously submitted project packet, rebuild its producer chain for approved revision 8, reproof and submit exactly one active replacement. Preserve unrelated queue entries and old source documents; mark the title using the demonstrated format.'
        queue=b.s['print_queue'][0];b.allow('print_queue',queue['id'],'status');b.act(op='print-control',target=queue['id'],status='Cancelled');b.goal('field',collection='print_queue',id=queue['id'],field='status',value='Cancelled')
        for f in b.s['files']:
            if f.get('generated_by'):b.allow('files',f['id'],'deleted')
        jobs=copy.deepcopy(b.s['jobs'])
        for job in reversed(jobs):
            b.allow('jobs',job['id'],'status','error','artifact','snapshot','configuration');b.act(op='update-job',target=job['id'])
        root=jobs[0]['input'];cover=next(f for f in b.shadow['files'] if not f['deleted'] and f['parent']==root and f.get('source')=='source-0')
        title=['[r8] Meeting packet','Meeting packet [r8]','r8 - Meeting packet'][c]
        b.write(cover['id'],title+'\nApproved revision 8.\n')
        for job in jobs:b.act(op='run-job',target=job['id'])
        _pipeline_goal(b);b.goal('domain',name='print_submission',input=root,exclude=[q['id'] for q in b.s['print_queue']]);return


def _text_demo(cid,c,seed,num,hard=False):
    b=Build(cid,c,seed,'demo');b.subject='the local record transformation';mode=None
    if not hard and num==2 or hard and num==2:
        source=[{'change_id':f'CH{seed%97+7}','summary':['Repair search','Improve export','Fix preview'][seed%3]},{'change_id':f'CH{seed%89+107}','summary':['Refresh cache','Update parser','Add validation'][seed%3]}]
        result='\n'.join(f"{x['change_id']}: {x['summary']}" if c==0 else f"{x['summary']} [{x['change_id']}]" if c==1 else f"[{x['change_id']}] {x['summary']}" for x in source)
        b.rule=['change_id: summary','summary [change_id]','[change_id] summary'][c]
    elif not hard and num==3:
        names=b.rng.sample(['Morgan','Taylor','Jordan','Casey','Riley','Avery'],2);source=[{'name':name,'phone':f'555-{seed%9000+i:04}'} for i,name in enumerate(names)]
        result='\n'.join(f"{x['name']} <{x['phone']}>" if c==0 else f"{x['name']} ({x['phone']})" if c==1 else f"{x['phone']} — {x['name']}" for x in source);b.rule=['Name <phone>','Name (phone)','phone — Name'][c]
    elif not hard and num==4:
        fixtures=[([('zipper.js',3,'Code'),('beta.json',6,'Config'),('atlas.csv',2,'Data'),('engine.js',5,'Code'),('orbit.json',1,'Config'),('delta.csv',4,'Data')]),
                  [('solar.js',8,'Code'),('alpha.json',3,'Config'),('lagoon.csv',7,'Data'),('beacon.js',2,'Code'),('zephyr.json',6,'Config'),('meridian.csv',5,'Data')],
                  [('maple.js',2,'Code'),('quartz.json',9,'Config'),('apricot.csv',4,'Data'),('willow.js',7,'Code'),('cedar.json',3,'Config'),('harbor.csv',6,'Data')]]
        entries=fixtures[{1001:0,1012:1,1026:2}.get(seed,seed%3)]
        source=[{'path':f'/project-{seed}/'+name,'number':number,'category':category} for name,number,category in entries]
        b.rng.shuffle(source)
        order=sorted(source,key=(lambda x:x['path']) if c==0 else (lambda x:x['number']) if c==1 else (lambda x:({'Code':0,'Config':1,'Data':2}[x['category']],x['path'])))
        result=dump({'references':[x['path'] for x in order]});mode='json';b.rule=['Order paths alphabetically.','Order by logical number.','Order Code, Config, Data; within each category, order full paths alphabetically.'][c]
    elif not hard and num==5:
        source=b.rng.sample(['Overview','Scope','Results','Follow-up','Resources','Decisions'],3);prefix=[['1.','2.','3.'],['I.','II.','III.'],['A.','B.','C.']][c];result='\n'.join(p+' '+x for p,x in zip(prefix,source));b.rule=['Arabic numbering.','Roman numbering.','Letter numbering.'][c]
    elif not hard and num==6:
        source=[f'2026-10-{10+seed%15:02}T09:{seed%60:02}:03',f'2026-10-{10+seed%15:02}T10:{(seed+7)%60:02}:05'];result='\n'.join(x.replace('T',' ') if c==0 else x.replace('T',' ').replace('-','/') if c==1 else x for x in source);b.rule=['YYYY-MM-DD HH:MM:SS','YYYY/MM/DD HH:MM:SS','YYYY-MM-DDTHH:MM:SS'][c]
    elif not hard and num==10:
        source=[{'request_id':f'R{seed}-1','approved':True},{'request_id':f'R{seed}-2','approved':False}];out=[]
        for x in source:out.append({'request_id':x['request_id'],**({'decision':'Approved' if x['approved'] else 'Rejected'} if c==0 else {'accepted':x['approved']} if c==1 else {'status':'ok' if x['approved'] else 'error'})})
        result=dump(out);mode='json';b.rule=['Approved/Rejected','accepted=true/false','status=ok/error'][c]
    elif not hard and num==11:
        source=[{'quantity':17+seed%31,'box':12,'pack':5},{'quantity':11+seed%17,'box':6,'pack':4}];result='\n'.join(f"{x['quantity']} pcs" if c==0 else f"{x['quantity']//x['box']} box + {x['quantity']%x['box']} pcs" if c==1 else f"{x['quantity']//x['pack']} pack + {x['quantity']%x['pack']} pcs" for x in source);b.rule=['N pcs','C box + R pcs','P pack + R pcs'][c]
    elif not hard and num==12:
        source={'baseline':{'x':1,'y':2,'z':3},'main':{'x':10,'y':20,'z':30,'main_only':'retain'},'review':{'x':11,'y':21,'z':31,'review_only':'retain'},'times':{'main':{'x':20,'y':10,'z':15},'review':{'x':10,'y':20,'z':15}}}
        
        for branch in ('baseline','main','review'):
            for key in ('x','y','z'):source[branch][key]+=seed%97
        value={'x':[10,11,10][c],'y':[20,21,21][c],'z':[30,31,30][c],'main_only':'retain','review_only':'retain'}
        for key in ('x','y','z'):value[key]+=seed%97;result=dump(value);mode='json';b.rule=['Conflicts use main.','Conflicts use review.','Conflicts use newer field timestamp; ties main.'][c]
    elif hard and num==1:
        source=[[{'key':'archive.format','before':'zip','after':'tar'},{'key':'verification.mode','before':'checksum','after':'full'}],[{'key':'media.preview','before':'compact','after':'review'},{'key':'scheduler.trigger','before':'manual','after':'idle'}],[{'key':'archive.format','before':'tar','after':'zip'},{'key':'media.preview','before':'detail','after':'compact'}]][seed%3]
        result='\n'.join(f"{x['key']}: {x['before']} -> {x['after']}" for x in source) if c==0 else csv_text([['key','before','after']]+[[x['key'],x['before'],x['after']] for x in source]) if c==1 else dump(source)
        mode='json' if c==2 else None;b.rule=['key: before -> after','CSV key,before,after','JSON key/before/after array'][c]
    elif hard and num==8:
        source={'build_artifact':f'build-{seed%997}','passed':True,'assertions':[{'name':'project','expected':f'P{seed%87}','actual':f'P{seed%87}','passed':True},{'name':'revision','expected':seed%17+2,'actual':seed%17+2,'passed':True}]}
        result='\n'.join(k+': '+json.dumps(v) for k,v in source.items()) if c==0 else dump(source) if c==1 else summary_values(source)
        mode='json' if c==1 else None;b.rule=['key: value lines','JSON object','Header build_artifact,passed,assertions then comma-separated JSON values'][c]
    elif hard and num==11:
        source={'released_bytes':3587+seed%997};q=source['released_bytes'];result=byte_display(q,c);b.rule=['integer B','KiB, three decimals','MiB, six decimals'][c]
    elif hard and num==12:
        revision=2+seed%13;title=['Review packet','Field briefing','Technical report'][seed%3];source=[{'revision':revision,'title':title},{'revision':revision+3,'title':'Operations summary'}];result='\n'.join([f'[r{x["revision"]}] {x["title"]}',f'{x["title"]} [r{x["revision"]}]',f'r{x["revision"]} - {x["title"]}'][c] for x in source);b.rule=['[rN] Title','Title [rN]','rN - Title'][c]
    else:raise ValueError((cid,num))
    compact=('{'+'\n'+',\n'.join('  '+json.dumps(k)+': '+json.dumps(v,ensure_ascii=False) for k,v in source.items())+'\n}') if isinstance(source,dict) else ('[\n'+',\n'.join('  '+json.dumps(v,ensure_ascii=False) for v in source)+'\n]')
    inp=b.file('Example input.json',compact);target=b.file('Example result.txt','',parent=b.output)
    b.request='Read Example input.json and demonstrate the local transformation in Example result.txt. Preserve the input. This is a local-method demonstration, not the full query workflow.'
    b.write(target,result,mode);return b.complete()


def _collision_demo(cid,c,seed,hard=False):
    b=Build(cid,c,seed,'demo');dst=b.folder('Original target',b.output);prev=b.folder('Previous',b.output);snap=b.folder('Local-preserved' if hard else 'Snapshot',b.output);sibling=b.folder('New workspace',b.output)
    old=b.file('source.txt',f'Local edit {seed} must survive.',parent=dst);new=b.file('source.txt',f'Approved incoming content {seed}.',parent=b.root)
    b.request='Demonstrate only preservation of the existing source.txt when the incoming file has the same name. Keep both contents recoverable.'
    b.rule=(['Use a fresh sibling workspace; leave the original destination untouched.','Rename the conflicting local file with -local before copying incoming.','Copy the local file to Local-preserved, then clear the original conflict.'] if hard else ['Move the old file into Previous before replacing it.','Keep old content with a -previous suffix.','Copy the old file into Snapshot before removing the original conflict.'])[c]
    target=dst
    if hard and c==0:target=sibling
    elif c==0:b.allow('files',old,'parent');b.act(op='move',target=old,parent=prev);b.goal('file',id=old,fields={'parent':prev})
    elif c==1:
        name='source-local.txt' if hard else 'source-previous.txt';b.allow('files',old,'name');b.act(op='rename',target=old,name=name);b.goal('file',id=old,fields={'name':name})
    else:
        b.act(op='copy',target=old,parent=snap);b.goal('copy',parent=snap,name='source.txt',source=old);b.allow('files',old,'deleted');b.act(op='delete',target=old);b.goal('file',id=old,fields={'deleted':True})
    b.act(op='copy',target=new,parent=target);b.goal('copy',parent=target,name='source.txt',source=new)
    return b.complete()


def _hard_module(cid,c,seed,num):
    import workflows as w
    if num==3:
        b=Build(cid,c,seed,'demo');ra=b.folder('Recovery','project');a=b.folder('Restored',ra);rb=b.folder('Restored','project');bb=b.folder('Workspace',rb);cc=b.folder('Recovered','project')
        parents=[a,bb,cc];reports=[b.folder('Reports',p) for p in parents]
        data=b.file('example-data.csv','id,value\nR1,7\n');report=b.file('example-report.txt','Verified example recovery.\n')
        b.request='Demonstrate only the recovery workspace layout: copy example-data.csv to the selected workspace and example-report.txt to its Reports child. Preserve both inputs.'
        b.rule=['Recovery/Restored with Reports inside.','Restored/Workspace with Reports inside.','Recovered with Reports inside.'][c]
        for source,parent in [(data,parents[c]),(report,reports[c])]:
            name=w.get_file(b.s,source)['name'];b.act(op='copy',target=source,parent=parent);b.goal('copy',parent=parent,name=name,source=source)
        return b.complete()
    if num==7:return _collision_demo(cid,c,seed,True)
    oldid={4:4,5:5,6:6,9:9,10:10}[num]
    base=w._generate_fixture(f'OS-LH-{oldid:02}',0,seed)
    if num==5:
        w.get_file(base['initial'],'source-0')['content']='Approved example cover.\n'
        base['state']=copy.deepcopy(base['initial'])
    plan=w.reference(base['case'],copy.deepcopy(base['initial']),copy.deepcopy(w.CONVENTIONS[0]))
    state=copy.deepcopy(base['initial']);module_kind={4:'transcode',5:'layout',6:None,9:'redact',10:'deliver'}[num]
    selected=None
    for action in plan:
        if module_kind and action['op']=='create-job' and action['kind']==module_kind:
            if selected is None:selected=copy.deepcopy(action)
        try:w.mutate(state,action,base['case'])
        except (ValueError,KeyError,TypeError):pass
    if module_kind:
        if num==5:state['print_queue']=[]
        cut=next(i for i,j in enumerate(state['jobs']) if j['kind']==module_kind)
        for job in reversed(state['jobs'][cut:]):w.mutate(state,{'op':'update-job','target':job['id']},base['case'])
        state['jobs']=state['jobs'][:cut]
    base['initial']=state;b=Build(cid,c,seed,'demo',base)
    if num==4:
        value=['compact','review','detail'][c];b.rule=['Compact 640 x 360.','Review 1280 x 720.','Detailed 1920 x 1080.'][c]
        b.request='Demonstrate the preview-size relation using the already-prepared matching clips and captions. Set the preview profile and run the example transcode only.'
        b.allow('settings','media.preview');b.act(op='setting',key='media.preview',value=value)
        b.run('transcode',selected['input'],selected['output'],selected['dependency']);b.goal('domain',name='preview',preset=value)
    elif num==5:
        b.s['print_request']={};profile=[{'paper':'A4','duplex':True,'order':'forward'},{'paper':'Letter','duplex':True,'order':'forward'},{'paper':'A4','duplex':False,'order':'reverse'}][c]
        b.rule=['A4, duplex, forward.','Letter, duplex, forward.','A4, simplex, reverse.'][c];b.request='Demonstrate the printing profile on the prepared short documents: set paper, sides and order, then create layout and proof. Do not run the full query or submit a print packet.'
        # Local examples must be short; the full query retains pagination faults.
        for f in b.s['files']:
            if f['parent']==selected['input'] and f.get('source')=='source-1':f['content']='Example report.\nTwo short lines.\n'
        for job in reversed(b.s['jobs']):w.mutate(b.s,{'op':'update-job','target':job['id']},b.case)
        for job in b.s['jobs']:w.mutate(b.s,{'op':'run-job','target':job['id']},b.case)
        for k,v in profile.items():b.allow('settings','printer.'+k);b.act(op='setting',key='printer.'+k,value=v)
        name,jid=b.run('layout',selected['input'],selected['output'],selected['dependency']);b.run('proof',selected['input'],selected['output'],name)
        b.goal('domain',name='print_profile',profile=profile)
    elif num==6:
        b.request='Demonstrate only cached-resource names and matching guide references. Rename the example cached resources, update the guide absolute links, then run offline-test. Downloads and the cache are already prepared.'
        b.rule=['Keep original resource names.','Prefix names with project_id-.','Use R0/R1/R2/R3 stems and preserve extensions.'][c]
        cache=next(j for j in reversed(state['jobs']) if j['kind']=='cache' and j['status']=='Completed');folder=w.get_file(state,cache['artifact'])['provenance']['processing']['materialized_folder']
        b.s['receipts']=[];changes=[]
        for i in range(4):
            f=next(f for f in b.s['files'] if not f['deleted'] and f['parent']==folder and f.get('source')==f'source-{i}');original=w.get_file(b.s,f'source-{i}')['name'];new=original if c==0 else b.s['project']+'-'+original if c==1 else f'R{i}.'+original.rsplit('.',1)[-1];changes.append((f['id'],f['name'],new))
        guide=next(f for f in b.s['files'] if not f['deleted'] and f['parent']==folder and f.get('source')=='source-2');content=guide['content']
        for fid,old,new in changes:content=content.replace(old,new)
        for fid,old,new in changes:b.allow('files',fid,'name');b.act(op='rename',target=fid,name=new);b.goal('file',id=fid,fields={'name':new})
        b.write(guide['id'],content);b.act(op='probe',kind='offline',target=folder);b.goal('probe',kind='offline',target=folder)
    elif num==9:
        method=['mask','remove','pseudonym'][c];b.rule=['Mask personal values.','Remove personal fields.','Use stable pseudonyms.'][c]
        b.request='Demonstrate only the personal-field treatment on the prepared incident working copies. Keep the complete public sensitive-field scope, select the method and run the example redaction.'
        b.allow('settings','privacy.method');b.act(op='setting',key='privacy.method',value=method)
        name,jid=b.run('redact',selected['input'],selected['output'],selected['dependency']);b.goal('domain',name='local_redaction',job=jid,method=method)
    elif num==10:
        trigger=['manual','idle','plugged-in'][c];b.rule=f'Final delivery trigger: {trigger}.'
        b.request='Demonstrate the final delivery trigger using the already-verified distribution payload and prerequisites. Create and run only the final delivery task; it must remain Scheduled, not dispatched.'
        name,jid=b.run('deliver',selected['input'],selected['output'],selected['dependency'],trigger=trigger)
        b.goal('job',name=name,fields={'trigger':trigger,'status':'Scheduled'});b.goal('domain',name='checks',keys=['scheduled_not_dispatched','distribution_dry_run_valid'])
    return b.complete()


def generate(case_id,convention=0,seed=42,plan_variant='standard'):
    import workflows as w
    if case_id not in CASE_BY_ID or convention not in range(3):raise ValueError('Unknown task36 case or convention')
    if plan_variant not in {'standard','module-demo'}:raise ValueError('Unknown task36 plan variant')
    scope='demo' if plan_variant=='module-demo' else 'query';level=case_id.split('-')[1];num=int(case_id[-2:])
    if scope=='demo' and (level=='M' and num in {2,3,4,5,6,10,11,12} or level=='H' and num in {1,2,8,11,12}):return _text_demo(case_id,convention,seed,num,level=='H')
    if scope=='demo' and level=='M' and num==7:return _collision_demo(case_id,convention,seed)
    if scope=='demo' and level=='H':return _hard_module(case_id,convention,seed,num)
    if level=='H' and num!=1:
        mapping={2:2,3:12,4:4,5:5,6:6,7:7,8:8,9:9,10:10,11:11,12:5}
        base=w._generate_fixture(f'OS-LH-{mapping[num]:02}',0,seed*3+1 if num==7 else seed)
        if num==12:
            clone=copy.deepcopy(base)
            for action in clone['reference']:w.transition(clone,action)
            base['initial']=copy.deepcopy(clone['state'])
        b=Build(case_id,convention,seed,scope,base)
        _hard(b,num,base)
    else:
        b=Build(case_id,convention,seed,scope)
        if level=='E':_easy(b,num)
        elif level=='M':_medium(b,num)
        else:_hard(b,num,None)
    if level=='H' and scope=='query' and num in {2,4,5,6,8,9,10,11}:
        b.request+=' Stage fresh copies under Working (under its current-shoot child for camera material), stage reports in its Reports child, and final artifacts in Deliverables.'
    ep=b.complete()
    return ep


def public(episode,mode='evaluation'):
    import workflows as w
    case={k:v for k,v in episode['case'].items() if k not in {'pipeline','recovery'}}
    payload={'benchmark_version':w.VERSION,'catalogue_version':'36.1-dev','case':case,'seed':episode['seed'],
             'state':copy.deepcopy(episode['state']),'state_hash':w.digest(episode['state']),'task_scope':episode['task36_scope']}
    if mode=='demo':payload['recorder_brief']=copy.deepcopy(episode['_brief36'])
    return payload

VIDEOICL_RELATIONS = {'OS-E-01': 'file-title word formatting while preserving extensions', 'OS-E-02': 'destination grouping by file metadata', 'OS-E-03': 'approved-version selection criterion', 'OS-E-04': 'existing-versus-incoming conflict naming convention', 'OS-E-06': 'contact-field transformation', 'OS-E-07': 'device-category connection policy', 'OS-E-08': 'anchor-relative time window with inclusive endpoints', 'OS-E-09': 'task trigger setting', 'OS-E-10': 'body-paragraph formatting', 'OS-E-11': 'page-count threshold and strict comparison', 'OS-E-12': 'section-heading page-break boundary', 'OS-M-01': 'handoff folder grouping', 'OS-M-02': 'change-entry text format', 'OS-M-03': 'person-name and phone display format', 'OS-M-04': 'reference ordering and tie-breaking', 'OS-M-05': 'chapter heading numbering', 'OS-M-06': 'timestamp representation', 'OS-M-07': 'preservation of replaced file contents', 'OS-M-08': 'stage task-name format', 'OS-M-09': 'stage output-folder organization', 'OS-M-10': 'approval-result encoding', 'OS-M-11': 'quantity units, quotient and remainder representation', 'OS-M-12': 'conflicting-field precedence', 'OS-H-01': 'configuration difference record format', 'OS-H-02': 'release change-entry format', 'OS-H-03': 'recovery folder layout', 'OS-H-04': 'preview size profile', 'OS-H-05': 'paper, duplex and page-order profile', 'OS-H-06': 'cached resource naming and corresponding links', 'OS-H-07': 'local file conflict preservation', 'OS-H-08': 'test-result summary representation', 'OS-H-09': 'sensitive-field treatment', 'OS-H-10': 'final delivery trigger setting', 'OS-H-11': 'byte-unit conversion and rounding', 'OS-H-12': 'revision marker placement in a title'}

VIDEOICL_OUTPUTS = {'OS-E-08': ' Save each channel i export as window-i.jsonl in Output.', 'OS-M-02': ' Deliver Output/config.json (release_version), release-notes.txt (Version: header followed by change entries), and delivery-index.json with version, notes, config and changes (change IDs).', 'OS-M-03': ' Save an array in Output/field-guide.json. Each entry retains slot_id, person_id, site, time, resources (resource IDs), active, and adds contact in the demonstrated display format.', 'OS-M-05': ' Save print-master.txt and contents.json in Output. Each contents entry has chapter_id, heading and one-based page.', 'OS-M-06': ' Save Output/timeline.json with incident, events, recovered and verification_event. Each event retains event_id, time and message and adds channels: Application and/or System, based on the corresponding exports.', 'OS-M-10': ' Save people-working.json and acknowledgements.json as JSON arrays in Output. Keep all unchanged person fields; every active request acknowledgement contains request_id, person_id and the demonstrated decision field.', 'OS-M-11': ' Save two JSON arrays in Output: stock-working.json entries contain lot_id (string) and quantity (string in the demonstrated units); differences.json entries contain lot_id (string), before_pcs, after_pcs and difference_pcs (integer counts). Preserve lot order from lot-baselines.json.', 'OS-M-12': ' Save Output/merged.json as a JSON object of merged fields and merge-diff.json as a JSON object. The conflict record contains conflict_fields (names), values (resolved conflicting fields) and preserved_unique (names of both sides unique fields).', 'OS-H-01': ' Save Output/configuration-diff.txt with one record per restored setting, using key, before and after from the actual old and restored values. Use the record representation demonstrated in the video.', 'OS-H-02': ' The staged release notes start with Version: followed by the preserved release_version, then one line per approved change in the demonstrated format; the changes request is input, not an output to overwrite.', 'OS-H-06': ' In the cached guide retain the title and the two lines Map: <absolute cached map path> and Contacts: <absolute cached contacts path>. Keep other guide text and original downloaded resources.', 'OS-H-08': ' Save test-summary.txt with build_artifact, passed and assertions, in that field order when order matters. Assertions retain name, expected, actual and passed from the actual test result.', 'OS-H-11': ' Save maintenance-report.txt as two text lines: released_bytes: <integer> and released_display: <unit representation learned from the video>. The demo itself shows only the unit representation. Use base 1024 and decimal HALF_UP rounding.', 'OS-H-12': ' Edit the working cover, not revision-request.txt: line 1 is the marked title, line 2 is the approved body. The replacement cover title is Meeting packet, revision 8; its body is Approved revision 8. Retain the same paper, duplex and order settings as the supplied valid print configuration.'}

from os_content_formats import output_mode, summary_values

_original_generate=generate
def generate(*args, **kwargs):
    from os_outcome_scoring import contract
    return contract(_original_generate(*args, **kwargs))
