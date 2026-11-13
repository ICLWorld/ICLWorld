"""Domain-specific resources, executable probes and final-state evidence.

No convention values or reference plans are kept in agent-visible resources.
"""
import json
import hashlib
from datetime import datetime, timedelta


def redact_record(record, fields, method):
    """Synthetic evidence transformations; pseudonyms are not secure anonymity."""
    result = dict(record)
    for field in fields:
        if field not in result:
            continue
        if method == 'remove':
            del result[field]
        elif method == 'pseudonym':
            value = json.dumps([field, result[field]], separators=(',', ':'))
            result[field] = 'anon-' + hashlib.sha256(value.encode()).hexdigest()[:16]
        elif method == 'mask':
            result[field] = '[redacted]'
        else:
            raise ValueError('unknown redaction method')
    return result


def configure(state, case, scenario=2):
    by_id = {f['id']: f for f in state['files']}
    domain = case['domain']
    state['receipts'] = []
    state['print_queue']=[]
    state['backup_history']=[]
    if domain=='backup':state['settings']['backup.include-text']=scenario==0
    if domain=='distribution':
        number=int(state['project'].rsplit('-',1)[1])
        recipient=['Research reviewers','Field coordinators','Release operators'][number%3]
        destination=state['devices'][2]
        destination.update(name=['Review Share','Field Share','Release Share'][number%3],recipient=recipient,access='read-write' if scenario==0 else 'read-only')
        state['devices'].append({'id':'other-share','name':'General Archive','kind':'Network storage','connected':True,'recipient':'Archive staff','access':'read-write'})
        state['distribution_request']={'recipient':recipient,'destination':destination['name']}
        by_id['source-1']['content']+=f"Recipient: {recipient}\nDestination: {destination['name']}\nPrepare and schedule the delivery; do not dispatch immediately.\n"
    if domain=='build':
        number=int(state['project'].rsplit('-',1)[1])
        config=json.loads(by_id['source-1']['content'])
        config['test_expectations']={'project':state['project'],'revision':by_id['source-0']['revision']}
        if scenario==1:config['test_expectations']['project']='Previous project'
        if scenario==2:config['test_expectations']['revision']-=1
        by_id['source-1']['content']=json.dumps(config,indent=2)
        state['processes'][0]['locks']=[]
        if scenario!=0:
            target=f'source-{number%2}'
            state['processes'].append({'id':'build-owner','name':'Source Editor' if number%2 else 'Build Cache Service',
                                      'status':'Running','locks':[target],'memory':192})
    if domain=='release':
        state['settings']['tools.compiler']=scenario!=1
        state['settings']['tools.signer']=scenario!=2
        number=int(state['project'].rsplit('-',1)[1])
        version=f'2.{number%9}.{number%13+1}'
        previous=f'2.{number%9}.{number%13}'
        config=json.loads(by_id['source-2']['content'])
        config.update(release_version=version,entry='application.js' if scenario==0 else 'application-old.js')
        by_id['source-2']['content']=json.dumps(config,indent=2)
        by_id['source-0']['content']+=f'export const releaseVersion = "{version}";\n'
        by_id['source-1']['content']=f'Version: {version if scenario==0 else previous}\n\nRelease changes for {state["project"]}:\n- Updated application and packaged current assets.\n'
        by_id['old-output']['content']=f'Previous release {previous}. Preserve this published archive.\n'
    if domain in {'backup','restoration'}:
        state['files'].append({'id':'recovery','parent':'project','name':'Recovery','kind':'folder','content':'','deleted':False,'revision':1})
        if scenario!=0:
            state['files'].append({'id':'user-recovery-edit','parent':'recovery','name':by_id['source-1']['name'],'kind':'text',
                                  'content':'Local user edits. Preserve this version when restoring the snapshot.\n',
                                  'deleted':False,'revision':3,'owner':'Local account'})
    if domain == 'research':
        state['files'].append({'id':'research-updates','parent':'inputs','name':'Approved updates','kind':'folder','content':'','deleted':False,'revision':1})
        for identifier,name in [('data-sources','Data'),('report-sources','Reports')]:
            state['files'].append({'id':identifier,'parent':'inputs','name':name,'kind':'folder','content':'','deleted':False,'revision':1})
        for i in range(4):
            source=by_id[f'source-{i}']
            source['parent']='data-sources' if i in [0,2] else 'report-sources'
            source['approved']=True
            source['resource_key']=f'research-{i}'
            state['files'].append({**source,'id':f'previous-source-{i}','parent':'previous',
                                   'content':'Previous revision\n'+source['content'],'revision':0})
            if scenario!=0 and (i+int(state['project'].rsplit('-',1)[1]))%2==0:
                updated=source['content'].replace('Operations','Reviewed') if source['name'].endswith('.csv') else source['content']+'Approved revision update.\n'
                state['files'].append({**source,'id':f'approved-update-{i}','parent':'research-updates','revision':source['revision']+2,'content':updated})
        state['files'].append({**by_id['source-0'],'id':'draft-source','parent':'drafts',
                               'approved':False,'revision':99,'content':'Unapproved revision; not cleared for handoff.\n'})
        if scenario!=0:
            chosen=required_source(state,case,0)
            state['processes'].append({'id':'research-sync','name':'Research Sync','status':'Running','locks':[chosen['id']],'memory':112})
    if domain == 'media':
        session_name='Shoot-'+str(int(state['project'].rsplit('-',1)[1]))
        state['files'].append({'id':'media-session','parent':'inputs','name':session_name,'kind':'folder','content':'','deleted':False,'revision':1})
        state['files'].append({'id':'media-takes','parent':'media-session','name':'Takes','kind':'folder','content':'','deleted':False,'revision':1})
        clips=[]
        for i in [0,1]:
            metadata=json.loads(by_id[f'source-{i}']['content'])
            metadata['clip_id']=f"{state['project']}-take-{i+1}"
            metadata['session']=session_name
            by_id[f'source-{i}']['parent']='media-takes'
            by_id[f'source-{i}']['content']=json.dumps(metadata,indent=2)
            clips.append(metadata['clip_id'])
        captions=[{'clip_id':clips[0],'text':'Opening scene'},{'clip_id':clips[1],'text':'Field interview'}]
        if scenario!=0:
            captions.append({'clip_id':'previous-session-take','text':'Obsolete caption; exclude from current catalogue'})
        by_id['source-2']['content']=json.dumps({'captions':captions},indent=2)
        by_id['source-2']['parent']='downloads' if scenario!=0 else 'media-session'
        by_id['source-2']['downloaded']=scenario==0
        by_id['source-3']['parent']='media-session'
        if scenario!=0:
            state['transfers'].append({'id':'download-captions','file':'source-2','name':session_name+' captions','status':'Pending','progress':0,'device':'camera','attempts':0})
        state['files'].append({**by_id['source-0'],'id':'previous-session-clip','parent':'previous',
            'content':json.dumps({'clip_id':'previous-session-take','session':'Previous shoot','virtual_media':True},indent=2)})
    if domain == 'print':
        paper='Letter' if int(state['project'].rsplit('-',1)[1])%2 else 'A4'
        state['print_request']={'paper':paper,'duplex':True}
        by_id['source-0']['content']+=f'Print request: {paper}, duplex. Use a compatible printer and retain the originals.\n'
        state['devices'][1].update(paper_sizes=['A4','Letter'] if scenario==0 else ['Letter'],duplex_supported=scenario==0)
        state['devices'].append({'id':'production-printer','name':'Production Printer','kind':'Printer','connected':scenario==0,
                                'paper_sizes':['A4','Letter'],'duplex_supported':True,'page_line_limit':40})
        line_count=(26+int(state['project'].rsplit('-',1)[1])%11) if scenario==0 else (46+int(state['project'].rsplit('-',1)[1])%25)
        by_id['source-1']['content']='\n'.join(f'Paragraph {i+1}: project findings for {state["project"]}.' for i in range(line_count))+'\n'
        state['devices'][1]['page_line_limit']=40
    if domain == 'storage':
        number=int(state['project'].rsplit('-',1)[1])
        state['files'].append({'id':'cache-folder','parent':'project','name':['Cache','Preview cache','Local cache'][number%3],'kind':'folder','content':'','deleted':False,'revision':1})
        owner_states={}
        names=['Thumbnail Service','Search Index Service'] if number%2 else ['Media Cache Worker','Document Preview Service']
        for i in range(2):
            folder=f'cache-section-{i}'
            state['files'].append({'id':folder,'parent':'cache-folder','name':['Thumbnails','Search index'][i] if number%2 else ['Media','Documents'][i],'kind':'folder','content':'','deleted':False,'revision':1})
            state['files'].append({'id':f'cache-{i}','parent':folder,'name':f'preview-{number%5}-{i}.cache','kind':'cache',
                                  'content':'Rebuildable preview data\n'+('x'*((2048+(number%7)*256)*(i+1))),
                                  'deleted':False,'revision':1,'regenerable':True})
            status='Paused' if i==1 and number%3==0 else 'Running'
            owner=f'cache-owner-{i}'
            state['processes'].append({'id':owner,'name':names[i],'status':status,'locks':[f'cache-{i}'],'memory':96+32*i})
            owner_states[owner]=status
        state['files'].append({'id':'pinned-cache-notes','parent':'cache-section-0','name':'pinned-notes.cache','kind':'text',
            'content':'User-maintained annotations. Not rebuildable; preserve this file.\n','deleted':False,'revision':2,'regenerable':False})
        state['maintenance_request']={'owner_states':owner_states}
        state['files'].append({'id':'maintenance-brief','parent':'project','name':'Maintenance request.txt','kind':'text',
            'content':'Inspect file properties before cleanup. Remove only rebuildable cache entries after verifying the project backup. Preserve user-maintained files and restore each owner to its prior state.\n',
            'deleted':False,'revision':1})
    if domain == 'migration':
        number=int(state['project'].rsplit('-',1)[1])
        code_name=['Code','Application'][number%2]
        settings_name=['Configuration','Settings'][number%2]
        for identifier,parent,name in [('migration-code','inputs',code_name),('migration-settings','inputs',settings_name),
                                        ('migration-profile','migration-settings','Profiles'),('migration-data','inputs','Assets')]:
            state['files'].append({'id':identifier,'parent':parent,'name':name,'kind':'folder','content':'','deleted':False,'revision':1})
        for i,parent in [(1,'migration-code'),(2,'migration-profile'),(3,'migration-data')]:by_id[f'source-{i}']['parent']=parent
        state['files'].append({'id':'migration-target','parent':'project','name':'Workspace','kind':'folder','content':'','deleted':False,'revision':1})
        if scenario!=0:
            state['files'].append({'id':'existing-workspace-edit','parent':'migration-target','name':by_id['source-1']['name'],'kind':'text',
                                  'content':'// Local workspace edits; preserve this file.\n','deleted':False,'revision':3})
        source_root=f"/Projects/{state['project']}/Inputs/"
        by_id['source-2']['content']=json.dumps({'workspace_root':source_root,'startup_path':source_root+code_name+'/source.js',
            'preferences':{'theme':'Light','tab_width':2+int(state['project'].rsplit('-',1)[1])%3,'autosave':True}},indent=2)
        by_id['source-0']['content'] = json.dumps({
            'project': state['project'], 'entry': source_root+code_name+'/source.js',
            'references': [source_root+code_name+'/source.js',source_root+settings_name+'/Profiles/'+by_id['source-2']['name'],source_root+'Assets/'+by_id['source-3']['name']],
        }, indent=2)
    if domain == 'restoration':
        number=int(state['project'].rsplit('-',1)[1])
        newest=datetime(2026,10,10+number%5)
        selected=newest if scenario==0 else newest-timedelta(days=1)
        version=selected.date().isoformat()
        state['files'].append({'id':'snapshots','parent':'inputs','name':'Snapshots','kind':'folder','content':'','deleted':False,'revision':1})
        by_id['source-0'].update(parent='snapshots',name=f'snapshot-{version}.json',snapshot_version=version,snapshot_status='Complete')
        manifest={
            'project':state['project'],'snapshot_version':version,'complete':True,
            'entry':f"/Projects/{state['project']}/Inputs/records.csv",
            'references':[f"/Projects/{state['project']}/Inputs/{by_id[f'source-{i}']['name']}" for i in range(1,4)],
            'scheduled_tasks':[{'name':state['project']+' inventory','kind':'inventory','trigger':['manual','idle','plugged-in'][number%3],'output':'Reports'}],
        }
        if scenario!=0:
            manifest['scheduled_tasks'].append({'name':state['project']+' recovery review','kind':'inventory','trigger':['idle','plugged-in','manual'][number%3],'output':'Reports'})
            existing=manifest['scheduled_tasks'][0 if scenario==1 else 1]
            state['jobs'].append({'id':'saved-task-1','name':existing['name'],'kind':existing['kind'],'trigger':'manual' if existing['trigger']!='manual' else 'idle',
                                  'input':'previous','output':'documents','dependency':'','status':'Ready','artifact':None,'error':None,'configuration':{}})
        by_id['source-0']['content']=json.dumps(manifest,indent=2)
        older=(selected-timedelta(days=1)).date().isoformat()
        state['files'].append({'id':'snapshot-older','parent':'snapshots','name':f'snapshot-{older}.json','kind':'text',
            'content':json.dumps({**manifest,'snapshot_version':older},indent=2),'snapshot_version':older,
            'snapshot_status':'Complete','deleted':False,'revision':1,'downloaded':True})
        if scenario!=0:
            incomplete=newest.date().isoformat()
            state['files'].append({'id':'snapshot-incomplete','parent':'snapshots','name':f'snapshot-{incomplete}.json','kind':'text',
                'content':json.dumps({**manifest,'snapshot_version':incomplete,'complete':False},indent=2),
                'snapshot_version':incomplete,'snapshot_status':'Incomplete','deleted':False,'revision':1,'downloaded':True})
        state['files'].append({'id':'recovery-request','parent':'inputs','name':'Recovery request.txt','kind':'text',
            'content':'Recover from the latest complete project snapshot. Preserve all existing local edits.\n',
            'deleted':False,'revision':1})
        for transfer in state['transfers']:
            if transfer['file']=='source-0':transfer['name']=by_id['source-0']['name']
    if domain == 'offline':
        state['settings']['cache.contacts']=scenario==0
        state['devices'].append({'id':'field-relay','name':'Field relay','kind':'Network adapter','connected':scenario==0})
        for transfer in state['transfers']:
            transfer['device']='field-relay'
            transfer['attempts']=0
        by_id['source-2']['content'] = 'Field resources\n\nMap: https://field.example.test/map.csv\nContacts: https://field.example.test/contacts.csv\n'
    if domain == 'evidence':
        state['log_exports']=[]
        incident_start=datetime(2026,10,14,8+int(state['project'].rsplit('-',1)[1])%5,0)
        state['incident'] = {'start':incident_start.isoformat(),'end':(incident_start+timedelta(minutes=30)).isoformat()}
        additional=['phone','account_id','ip_address'][int(state['project'].rsplit('-',1)[1])%3]
        state['sensitive_fields']=['contact']+([additional] if scenario!=0 else [])
        state['events'].append({'level':'Error','source':'Incident Monitor','message':'Incident notification: '+state['incident']['start']+' through '+state['incident']['end']+'. Collect Application and System evidence; preserve original logs.'})
        for i in [0,1]:
            by_id[f'source-{i}']['log_channel']=['Application','System'][i]
            records = [{'time':t,'event_id':f'EV-{i}-{n}','contact':f'operator{n}@example.test',
                        'message':m} for n,(t,m) in enumerate([
                            ((incident_start-timedelta(minutes=5)).isoformat(),'Service started'),
                            ((incident_start+timedelta(minutes=5)).isoformat(),'Connection lost'),
                            ((incident_start+timedelta(minutes=12)).isoformat(),'Recovery started'),
                            ((incident_start+timedelta(minutes=40)).isoformat(),'Unrelated maintenance')])]
            if scenario!=0:
                for n,record in enumerate(records):
                    record[additional]={'phone':f'+1-202-555-01{n:02}','account_id':f'local-account-{i}-{n}','ip_address':f'192.0.2.{n+1}'}[additional]
            by_id[f'source-{i}']['content']='\n'.join(json.dumps(r,sort_keys=True) for r in records)+'\n'
        by_id['source-2']['content']='time,event_id,summary\n'
        by_id['source-3']['content'] = 'Incident window: '+state['incident']['start']+' through '+state['incident']['end']+'\nPreserve the original logs. Collect both application and system evidence.\n'
        by_id['source-3']['content']+='Personal fields to redact: '+', '.join(state['sensitive_fields'])+'. Preserve event IDs, timestamps and descriptions.\n'


def required_source(initial,case,index):
    """Select the latest approved research revision by metadata, not object ID."""
    if case['domain']=='research':
        candidates=[f for f in initial['files'] if f.get('resource_key')==f'research-{index}' and f.get('approved') and not f['deleted']]
        return max(candidates,key=lambda f:(f['revision'],f['id']))
    return next(f for f in initial['files'] if f['id']==f'source-{index}')


def staged_content(initial, case, policy, index):
    """Expected content changes, used only in trusted generation/scoring."""
    source = required_source(initial,case,index)
    content = source['content']
    base=f"/Projects/{initial['project']}/{policy['workspace']}"
    if case['domain'] in {'migration','restoration'} and index==0:
        manifest=json.loads(content)
        manifest['entry']=base+'/'+policy['prefix']+('source.js' if case['domain']=='migration' else 'records.csv')
        manifest['references']=[base+'/'+policy['prefix']+next(f for f in initial['files'] if f['id']==f'source-{i}')['name'] for i in range(1,4)]
        content=json.dumps(manifest,indent=2)
    if case['domain']=='release' and index==1:
        version=json.loads(next(f for f in initial['files'] if f['id']=='source-2')['content'])['release_version']
        content='Version: '+version+'\n'+content.split('\n',1)[1]
    if case['domain']=='release' and index==2:
        configuration=json.loads(content)
        configuration['entry']=base+'/'+policy['prefix']+configuration['entry'].rsplit('/',1)[-1]
        content=json.dumps(configuration,indent=2)
    if case['domain']=='migration' and index==2:
        configuration=json.loads(content)
        configuration['workspace_root']=base+'/'
        configuration['startup_path']=base+'/'+policy['prefix']+'source.js'
        content=json.dumps(configuration,indent=2)
    if case['domain']=='offline' and index==2:
        # The guide must point to the materialized cache, not downloaded sources.
        cache=base+f"/Reports/{case['pipeline'].index('cache')+1:02}-cache-files/"
        content='Field resources\n\nMap: '+cache+policy['prefix']+'map.csv\nContacts: '+cache+policy['prefix']+'contacts.csv\n'
    if case['domain']=='evidence' and index in [0,1]:
        window=initial['incident']
        content='\n'.join(json.dumps(r,sort_keys=True) for r in map(json.loads,content.splitlines()) if window['start']<=r['time']<=window['end'])+'\n'
    if case['domain']=='evidence' and index==2:
        events=[]
        for i in [0,1]:
            log=next(f for f in initial['files'] if f['id']==f'source-{i}')
            events.extend(r for r in map(json.loads,log['content'].splitlines()) if initial['incident']['start']<=r['time']<=initial['incident']['end'])
        content='time,event_id,summary\n'+'\n'.join(f"{r['time']},{r['event_id']},{r['message']}" for r in sorted(events,key=lambda r:(r['time'],r['event_id'])))+'\n'
    if case['domain']=='media' and index==2:
        clip_ids={json.loads(next(f for f in initial['files'] if f['id']==f'source-{i}')['content'])['clip_id'] for i in [0,1]}
        captions=json.loads(content)
        captions['captions']=[c for c in captions['captions'] if c['clip_id'] in clip_ids]
        content=json.dumps(captions,indent=2)
    if case['domain']=='print' and index==1:
        lines=content.splitlines()
        if len(lines)>40:
            content='\n'.join(lines[:35])+'\n\f'+'\n'.join(lines[35:])+'\n'
    return content


def content_matches(state, initial, case, policy, index, candidate):
    """Grade document meaning rather than JSON indentation or oracle job names."""
    expected=staged_content(initial,case,policy,index)
    actual=candidate['content']
    domain=case['domain']
    if domain=='release' and index==2:
        configuration=json.loads(expected)
        configuration['entry']=configuration['entry'].rsplit('/',1)[0]+'/'+policy['prefix']+'application.js'
        try:return json.loads(actual)==configuration
        except ValueError:return False
    if domain=='build' and index==1:
        expected_json=json.loads(expected)
        expected_json['build_ready']=True
        expected_json['test_expectations']={'project':initial['project'],'revision':next(f for f in initial['files'] if f['id']=='source-0')['revision']}
        try:
            return json.loads(actual)==expected_json
        except ValueError:
            return False
    if (domain in {'migration','restoration'} and index==0) or (domain=='migration' and index==2) or (domain=='media' and index==2):
        try:
            left,right=json.loads(actual),json.loads(expected)
            if domain=='media':
                left['captions']=sorted(left['captions'],key=lambda c:c['clip_id'])
                right['captions']=sorted(right['captions'],key=lambda c:c['clip_id'])
            return left==right
        except (ValueError,KeyError,TypeError):
            return False
    if domain=='offline' and index==2:
        by_id={f['id']:f for f in state['files'] if not f['deleted']}
        def fullpath(f):
            result=[]
            while f:
                result.insert(0,f['name'])
                f=by_id.get(f['parent'])
            return '/'+ '/'.join(result)
        cache=next((j for j in state['jobs'] if j['kind']=='cache' and j['status']=='Completed'),None)
        if cache is None:
            return False
        try:
            folder=by_id[cache['artifact']]['provenance']['processing']['materialized_folder']
            paths={fullpath(f):f for f in by_id.values() if f['parent']==folder}
            links={line.split(': ',1)[0]:line.split(': ',1)[1] for line in actual.splitlines() if line.startswith(('Map: ','Contacts: '))}
            return links.keys()=={'Map','Contacts'} and paths[links['Map']].get('source')=='source-0' and paths[links['Contacts']].get('source')=='source-1'
        except (ValueError,KeyError):
            return False
    if domain=='print' and index==1:
        original=next(f for f in initial['files'] if f['id']=='source-1')['content']
        pages=actual.split('\f')
        return [line for page in pages for line in page.splitlines()]==original.splitlines() and all(len(page.splitlines())<=40 for page in pages)
    if domain=='evidence' and index in [0,1]:
        try:
            return sorted(map(json.loads,actual.splitlines()),key=lambda r:r['event_id'])==sorted(map(json.loads,expected.splitlines()),key=lambda r:r['event_id'])
        except (ValueError,KeyError):
            return False
    if domain=='evidence' and index==2:
        import csv
        return list(csv.reader(actual.splitlines()))==list(csv.reader(expected.splitlines()))
    return actual==expected


def probe(state, action, get_file, path, digest):
    """Executable tests, independent of the hidden policy and reference actions."""
    kind=action['kind']
    target=get_file(state, action['target'])
    descendants=[f for f in state['files'] if not f['deleted'] and f['parent']==target['id'] and f['kind']!='folder']
    if target['kind']!='folder':
        raise ValueError('Select a workspace folder for this test.')
    processing={}
    if kind=='offline':
        if not state['settings']['network.offline']:
            raise ValueError('Disconnect the network before testing offline availability.')
        guide=next((f for f in descendants if f.get('source')=='source-2'),None)
        if guide is None:
            raise ValueError('The cached field guide is missing.')
        entries=[(line.partition(':')[0].strip(),line.partition(':')[2].strip()) for line in guide['content'].splitlines() if line.partition(':')[0].strip() in {'Map','Contacts'}]
        links=dict(entries)
        if len(entries)!=2 or links.keys()!={'Map','Contacts'} or any(link.startswith(('https:','http:')) for link in links.values()):
            raise ValueError('The field guide still refers to online resources. Repair the working guide and rebuild the cache.')
        paths={path(state,f['id']):f for f in descendants}
        missing=[label for label,link in links.items() if link not in paths]
        if missing:
            raise ValueError('Offline cache is missing '+', '.join(missing)+'. Inspect Network & internet > Offline resources, include the required resources and rebuild the cache.')
        if paths[links['Map']].get('source')!='source-0' or paths[links['Contacts']].get('source')!='source-1':
            raise ValueError('The guide links do not identify the matching map and contact resources.')
        processing={'accessed_paths':links,'network':'offline'}
    elif kind in {'workspace','restoration'}:
        manifest=next((f for f in descendants if f.get('source')=='source-0'),None)
        if manifest is None:
            raise ValueError('The workspace manifest is missing.')
        try:
            config=json.loads(manifest['content'])
            links=[config['entry'],*config['references']]
        except (ValueError,KeyError,TypeError):
            raise ValueError('The workspace manifest is malformed.')
        paths={path(state,f['id']):f for f in descendants}
        if any(link not in paths for link in links):
            raise ValueError('Workspace references do not resolve inside the migrated folder. Repair source paths and rerun migration.')
        processing={'opened_entry':config['entry'],'resolved_paths':links}
        if kind=='workspace':
            app_settings=next((f for f in descendants if f.get('source')=='source-2'),None)
            try:
                settings=json.loads(app_settings['content']) if app_settings else {}
                original=json.loads(get_file(state,'source-2')['content'])
                if settings.get('workspace_root')!=path(state,target['id'])+'/' or settings.get('startup_path')!=config['entry'] or settings.get('preferences')!=original['preferences']:
                    raise ValueError('Migrated application settings do not match this workspace. Repair paths and preserve user preferences.')
            except (KeyError,TypeError,ValueError) as exc:
                raise ValueError('Application configuration cannot open the migrated workspace: '+str(exc))
            processing['application_settings']=settings
        if kind=='restoration':
            for expected in config.get('scheduled_tasks',[]):
                matching=next((j for j in state['jobs'] if j['name']==expected['name'] and j['kind']==expected['kind'] and
                               j['trigger']==expected['trigger'] and j['input']==target['id'] and j['status']=='Ready' and not j['dependency'] and
                               get_file(state,j['output'])['parent']==target['id'] and get_file(state,j['output'])['name']==expected['output']),None)
                if matching is None:
                    raise ValueError('Restore the scheduled task specified in the snapshot before completing project recovery.')
            processing['restored_tasks']=[t['name'] for t in config.get('scheduled_tasks',[])]
    elif kind=='storage':
        caches=[f for f in state['files'] if f.get('regenerable')]
        if not caches or any(not f['deleted'] for f in caches):
            raise ValueError('Rebuildable cache entries remain. Inspect storage and finish safe cleanup.')
        backup=next((j for j in state['jobs'] if j['kind']=='verify-backup' and j['status']=='Completed'),None)
        if backup is None:
            raise ValueError('A verified pre-cleanup backup is required.')
        if not all(any(p['id']==owner and p['status']==status for p in state['processes']) for owner,status in state['maintenance_request']['owner_states'].items()):
            raise ValueError('Restore each cache owner to its prior state before completing maintenance.')
        processing={'freed_cache_bytes':sum(len(f['content'].encode()) for f in caches),
                    'deleted_cache_ids':[f['id'] for f in caches], 'verified_backup':backup['artifact']}
    else:
        raise ValueError('Unknown workspace test.')
    receipt={'kind':kind,'target':target['id'],'files':{f['id']:digest(f['content']) for f in descendants},'result':processing}
    state['receipts'].append(receipt)
    state['events'].append({'level':'Information','source':'Workspace Tools','message':f'{kind} test passed for {path(state,target["id"])}'})
    return receipt


def checks(state, initial, case, get_file, digest, media_catalogue=None, redaction_method='mask'):
    result={}
    delivery=next((j for j in state['jobs'] if j['kind']=='deliver' and j['status'] in {'Completed','Scheduled'}),None)
    resources=[]
    if delivery:
        try:
            resources=get_file(state,delivery['artifact'])['provenance']['resources']
        except (ValueError,KeyError):
            pass
    source_ids=[r.get('source') for r in resources if r.get('source','').startswith('source-')]
    if any(j['kind']=='backup' and j['status']=='Completed' for j in state['jobs']):
        result['backup_snapshots_retained']=False
        try:
            active=[j for j in state['jobs'] if j['kind']=='backup' and j['status']=='Completed']
            valid=True
            for job in active:
                report=get_file(state,job['artifact'])['provenance']
                details=report['processing']
                snapshot=get_file(state,details['snapshot_file'])
                document=json.loads(snapshot['content'])
                valid=valid and document['resources']==report['resources'] and document['version']==details['snapshot_version'] and digest(snapshot['content'])==details['snapshot_sha256']
            for historical in state.get('backup_history',[]):
                if historical['retention']=='versioned':
                    valid=valid and digest(get_file(state,historical['file'])['content'])==historical['sha256']
            result['backup_snapshots_retained']=valid
        except (ValueError,KeyError,TypeError):pass
    if case['domain']=='build':
        result['build_tests_passed']=False
        try:
            tested=next(j for j in state['jobs'] if j['kind']=='test' and j['status']=='Completed')
            details=get_file(state,tested['artifact'])['provenance']['processing']
            file=get_file(state,details['test_file'])
            assertions=details['assertions']
            expected={'project':initial['project'],'revision':get_file(initial,'source-0')['revision']}
            result['build_tests_passed']=(details['passed'] and {a['name']:a['actual'] for a in assertions}==expected and
                all(a['passed'] and a['expected']==a['actual'] for a in assertions) and
                digest(file['content'])==details['test_sha256'] and
                json.loads(file['content'])=={k:details[k] for k in ['build_artifact','build_sha256','assertions','passed']} and
                digest(get_file(state,details['build_artifact'])['content'])==details['build_sha256'])
            if result['build_tests_passed']:
                derived=get_file(state,delivery['artifact'])['provenance']['derived_artifacts'] if delivery else []
                required={details['test_file'],details['build_artifact']}
                result['build_tests_passed']=(len(derived)==2 and {d['id'] for d in derived}==required and
                    all(d['content']==get_file(state,d['id'])['content'] and d['sha256']==digest(d['content']) for d in derived))
        except (ValueError,KeyError,TypeError,StopIteration):pass
    if case['domain']=='release':
        consistent=False
        try:
            expected=json.loads(get_file(initial,'source-2')['content'])['release_version']
            delivered={r['source']:r['content'] for r in resources}
            configuration=json.loads(delivered['source-2'])
            build=next(j for j in state['jobs'] if j['kind']=='build' and j['status']=='Completed')
            details=get_file(state,build['artifact'])['provenance']['processing']
            consistent=(configuration['release_version']==expected==details['release_version'] and
                        configuration['entry']==details['entry'] and
                        (delivered['source-1'].strip().splitlines() or [''])[0].strip() == 'Version: '+expected and
                        f'export const releaseVersion = "{expected}";' in delivered['source-0'])
        except (ValueError,KeyError,StopIteration,TypeError):pass
        result['release_version_consistent']=consistent
    # A correct set of four working files must not hide a fifth draft in the
    # delivered package. Check membership independently of file preservation.
    expected_ids=[required_source(initial,case,i)['id'] for i in range(4)]
    actual_ids=[r.get('source') for r in resources if r.get('source') in {f['id'] for f in initial['files'] if f['kind']!='folder'}]
    expected_count=4 if case['domain']=='backup' and state['settings']['backup.scope']=='sources' else 5
    result['delivery_source_scope']=sorted(actual_ids)==sorted(expected_ids) and len(resources)==expected_count
    if case['domain']=='research':
        result['research_owner_restored']=all(any(p['id']==original['id'] and p['status']==original['status'] for p in state['processes']) for original in initial['processes'])
    if case['domain']=='distribution':
        details={}
        scheduled=False
        if delivery:
            try:
                details=get_file(state,delivery['artifact'])['provenance']['processing']
                scheduled=delivery['status']=='Scheduled' and details['dispatch_status']=='Scheduled' and details['payload_hash']==digest(resources)
            except (ValueError,KeyError):
                pass
        result['scheduled_not_dispatched']=scheduled
        result['distribution_destination_connected']=False
        result['distribution_dry_run_valid']=False
        if delivery:
            try:
                destination=next(d for d in state['devices'] if d['id']==details['destination'])
                result['distribution_destination_connected']=destination['connected'] and destination['access']=='read-write'
                receipt=get_file(state,details['dry_run_receipt'])['provenance']['processing']
                result['distribution_dry_run_valid']=(destination['recipient']==initial['distribution_request']['recipient']==details['recipient'] and
                    destination['name']==initial['distribution_request']['destination'] and
                    receipt['destination']==destination['id'] and receipt['access_checked']=='read-write' and
                    receipt['payload_sha256']==details['payload_hash'] and receipt['dispatched'] is False and details['dispatched'] is False)
            except (ValueError,KeyError,TypeError,StopIteration):pass
    if case['domain']=='media':
        job=next((j for j in state['jobs'] if j['kind']=='transcode' and j['status']=='Completed'),None)
        correct=False
        if job:
            try:
                p=get_file(state,job['artifact'])['provenance']['processing']
                previews=[f for f in state['files'] if f['parent']==p['preview_folder'] and not f['deleted']]
                source_clips={json.loads(get_file(initial,f'source-{i}')['content'])['clip_id']:digest(get_file(initial,f'source-{i}')['content']) for i in [0,1]}
                caption_source=json.loads(get_file(initial,'source-2')['content'])['captions']
                captions={c['clip_id']:c['text'] for c in caption_source if c['clip_id'] in source_clips}
                records=[json.loads(f['content']) for f in previews]
                correct=len(records)==len(source_clips) and {r['clip_id']:r['caption'] for r in records}==captions and all(r['source_hash']==source_clips[r['clip_id']] for r in records)
                session_name=json.loads(get_file(initial,'source-0')['content'])['session']
                correct=correct and all(r.get('session')==session_name for r in records)
            except (ValueError,KeyError,TypeError):
                pass
        result['captioned_previews']=correct
        expected_session=json.loads(get_file(initial,'source-0')['content'])['session']
        result['media_session_organized']=False
        try:result['media_session_organized']=bool(job and get_file(state,job['input'])['name']==expected_session)
        except ValueError:pass
        result['media_catalogue_delivered']=False
        if job and delivery and media_catalogue:
            try:
                catalogue_job=next(j for j in state['jobs'] if j['kind']=='catalogue' and j['status']=='Completed')
                details=get_file(state,catalogue_job['artifact'])['provenance']['processing']
                manifest=get_file(state,details['catalogue_file'])
                expected=media_catalogue(state,get_file(state,job['artifact'])['provenance'])
                delivered=get_file(state,delivery['artifact'])['provenance']['derived_artifacts']
                required={manifest['id'],*[e['preview_id'] for e in expected['entries']]}
                result['media_catalogue_delivered']=(json.loads(manifest['content'])==expected and
                    digest(manifest['content'])==details['catalogue_sha256'] and
                    details['entries']==expected['entries'] and details['session']==expected['session'] and
                    len(delivered)==len(required) and {a['id'] for a in delivered}==required and
                    all(a['content']==get_file(state,a['id'])['content'] and a['sha256']==digest(a['content']) for a in delivered))
            except (ValueError,KeyError,TypeError,StopIteration):pass
    if case['domain']=='print':
        p={}
        layout=next((j for j in state['jobs'] if j['kind']=='layout' and j['status']=='Completed'),None)
        proof=next((j for j in state['jobs'] if j['kind']=='proof' and j['status']=='Completed'),None)
        good=False
        if layout and proof:
            try:
                p=get_file(state,layout['artifact'])['provenance']['processing']
                confirmation=get_file(state,proof['artifact'])['provenance']['processing']
                printer=next(d for d in state['devices'] if d['id']==p['printer'])
                good=(bool(p['pages']) and all(page['lines']<=printer['page_line_limit'] for page in p['pages']) and
                      confirmation['proof_passed'] and p['duplex'] and printer['duplex_supported'] and
                      p['paper']==initial['print_request']['paper'] and p['paper'] in printer['paper_sizes'] and
                      confirmation['printer']==p['printer'] and confirmation['paper']==p['paper'] and
                      confirmation['duplex']==p['duplex'] and confirmation['order']==p['order'])
            except (ValueError,KeyError):
                pass
        result['print_proof_valid']=bool(good)
        result['print_submission_queued']=False
        if delivery and layout and proof:
            try:
                details=get_file(state,delivery['artifact'])['provenance']['processing']
                queue=next(q for q in state.get('print_queue',[]) if q['id']==details['print_job'])
                proof_file=get_file(state,proof['artifact'])
                payload={key:queue[key] for key in ['printer','paper','duplex','order','pages','documents']}
                expected=[r for r in resources if r['source'].startswith('source-')]
                result['print_submission_queued']=(queue['status']=='Queued' and queue['task']==delivery['id'] and
                    queue['delivery_artifact']==delivery['artifact'] and queue['proof_artifact']==proof['artifact'] and
                    queue['proof_sha256']==digest(proof_file['content']) and queue['documents']==expected and
                    queue['pages']==p['pages'] and queue['printer']==p['printer'] and queue['paper']==p['paper'] and queue['duplex']==p['duplex'] and
                    queue['order']==p['order'] and
                    queue['payload_sha256']==details['payload_sha256']==digest(payload) and details['page_count']==len(queue['pages']) and
                    next(d for d in state['devices'] if d['id']==queue['printer'])['connected'] and
                    len([q for q in state['print_queue'] if q['task']==delivery['id'] and q['status']!='Cancelled'])==1)
            except (ValueError,KeyError,TypeError,StopIteration):pass
    if case['domain']=='storage':
        caches=[f for f in initial['files'] if f.get('regenerable')]
        result['cache_scope_removed']=all(any(f['id']==cache['id'] and f['deleted'] for f in state['files']) for cache in caches)
        result['maintenance_owner_restored']=all(any(p['id']==owner and p['status']==status for p in state['processes']) for owner,status in initial['maintenance_request']['owner_states'].items())
        expected_bytes=sum(len(f['content'].encode()) for f in caches)
        result['storage_accounting']=any(r['kind']=='storage' and r['result'].get('freed_cache_bytes')==expected_bytes for r in state['receipts'])
        import zlib
        compact=next((j for j in state['jobs'] if j['kind']=='compact' and j['status']=='Completed'),None)
        valid=False
        if compact:
            try:
                report=get_file(state,compact['artifact'])['provenance']
                p=report['processing']
                packed=get_file(state,p['compressed_artifact'])
                compressed=bytes.fromhex(packed['content'])
                payload=json.dumps(report['resources'],sort_keys=True,separators=(',',':')).encode()
                valid=zlib.decompress(compressed)==payload and len(compressed)==p['bytes_after'] and len(payload)==p['bytes_before'] and p['bytes_after']<p['bytes_before']
            except (ValueError,KeyError,zlib.error):
                pass
        result['lossless_compaction_effective']=valid
    if case['domain'] in {'offline','migration','restoration'}:
        kind={'offline':'offline','migration':'workspace','restoration':'restoration'}[case['domain']]
        expected_operation={'offline':'cache','migration':'migrate','restoration':'restore'}[case['domain']]
        jobs=[j for j in state['jobs'] if j['kind']==expected_operation and j['status']=='Completed']
        folder=None
        if jobs:
            try:
                folder=get_file(state,jobs[-1]['artifact'])['provenance']['processing']['materialized_folder']
            except (ValueError,KeyError):
                pass
        valid=False
        for receipt in state['receipts']:
            if receipt['kind']!=kind or receipt['target']!=folder:
                continue
            try:
                valid=all(digest(get_file(state,fid)['content'])==value for fid,value in receipt['files'].items())
            except ValueError:
                valid=False
            if valid:
                break
        result[kind+'_probe_passed']=valid
        if kind=='restoration':
            snapshot=json.loads(get_file(initial,'source-0')['content'])
            result['restored_schedule_configuration']=all(any(j['name']==expected['name'] and j['kind']==expected['kind'] and
                j['trigger']==expected['trigger'] and j['input']==folder and j['status']=='Ready' and not j['dependency'] and
                any(f['id']==j['output'] and not f['deleted'] and f['parent']==folder and f['name']==expected['output'] for f in state['files']) for j in state['jobs']) for expected in snapshot['scheduled_tasks'])
            latest=max((f for f in initial['files'] if f.get('snapshot_status')=='Complete'),key=lambda f:f['snapshot_version'])
            result['latest_complete_snapshot']=latest['id']=='source-0' and snapshot['complete'] is True
            if 'user-recovery-edit' in {f['id'] for f in initial['files']}:
                original=get_file(initial,'user-recovery-edit')
                try:
                    current=get_file(state,'user-recovery-edit')
                    result['local_recovery_edits_preserved']=all(current[k]==original[k] for k in ['name','parent','content'])
                except ValueError:result['local_recovery_edits_preserved']=False
        if kind=='offline':
            result['offline_mode']=state['settings']['network.offline'] is True
    if case['domain']=='evidence':
        result['incident_logs_exported']=False
        try:
            receipts=state['log_exports']
            valid=True
            for source in ['source-0','source-1']:
                original=get_file(initial,source)
                receipt=next(r for r in receipts if r['source']==source and r['start']==initial['incident']['start'] and r['end']==initial['incident']['end'])
                exported=get_file(state,receipt['file'])
                expected_records=[r for r in map(json.loads,original['content'].splitlines()) if receipt['start']<=r['time']<=receipt['end']]
                valid=valid and exported.get('source')==source and receipt['source_sha256']==digest(original['content']) and [json.loads(line) for line in exported['content'].splitlines()]==expected_records
            result['incident_logs_exported']=valid
        except (ValueError,KeyError,TypeError,StopIteration):pass
        deliver=next((j for j in state['jobs'] if j['kind']=='deliver' and j['status']=='Completed'),None)
        required=set()
        for i in [0,1]:
            original=get_file(initial,f'source-{i}')
            required.update(r['event_id'] for r in map(json.loads,original['content'].splitlines()) if initial['incident']['start']<=r['time']<=initial['incident']['end'])
        event_ids=set()
        contacts=[]
        try:
            resources=get_file(state,deliver['artifact'])['provenance']['resources'] if deliver else []
            for resource in resources:
                if resource.get('source') not in {'source-0','source-1'}:
                    continue
                for record in map(json.loads,resource['content'].splitlines()):
                    event_ids.add(record['event_id'])
                    contacts.append(record)
        except (ValueError,KeyError,TypeError):
            event_ids=set()
        result['incident_window_exact']=event_ids==required
        result['delivery_redacted']=False
        result['evidence_fields_preserved']=False
        result['redacted_copies_intact']=False
        if deliver:
            try:
                expected=[];actual=[]
                for identifier in ['source-0','source-1']:
                    for record in map(json.loads,get_file(initial,identifier)['content'].splitlines()):
                        if initial['incident']['start']<=record['time']<=initial['incident']['end']:
                            expected.append(redact_record(record,initial['sensitive_fields'],redaction_method))
                for resource in resources:
                    if resource['source'] in {'source-0','source-1'}:actual.extend(map(json.loads,resource['content'].splitlines()))
                result['evidence_fields_preserved']=sorted(actual,key=lambda r:r['event_id'])==sorted(expected,key=lambda r:r['event_id'])
                result['delivery_redacted']=bool(actual) and result['evidence_fields_preserved']
                derived=get_file(state,deliver['artifact'])['provenance']['derived_artifacts']
                result['redacted_copies_intact']=len(derived)==2 and all(get_file(state,item['id'])['content']==item['content'] and digest(item['content'])==item['sha256'] for item in derived)
            except (ValueError,KeyError,TypeError):pass
    return result
