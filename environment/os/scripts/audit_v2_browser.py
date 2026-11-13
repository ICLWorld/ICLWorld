#!/usr/bin/env python3
"""Trusted UI reference audit. Uses DOM only in tests, not agent evaluation.

Every resource mutation is performed by clicking/filling the ordinary desktop.
The reference is read by this trusted harness; it is never injected into the UI.
"""
import argparse
import json
import hashlib
import subprocess
import shutil
import sys
import tempfile
import threading
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import server
import workflows
import artifact_provenance
from playwright.sync_api import sync_playwright


def request(base, path, body=None):
    raw = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base + path, data=raw, headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read())


class Desktop:
    def __init__(self, page):
        self.page = page

    def idle(self):
        self.page.evaluate("async () => { await window.__OS_WAIT_IDLE__(); }")

    def click(self, locator):
        locator.click()
        self.idle()

    def fill(self, locator, value):
        locator.fill(value)
        self.idle()

    def front(self, app):
        self.click(self.page.locator(f'.taskbar [data-open="{app}"]'))
        return self.page.locator('.window').last

    def folder(self, identifier):
        win = self.front("files")
        # Visible breadcrumbs and rows, never an API navigation shortcut.
        state = self.page.request.get(self.base + f"/api/v2/sessions/{self.sid}").json()["state"]
        by_id = {f["id"]:f for f in state["files"]}
        chain = []
        current = by_id[identifier]
        while current:
            chain.insert(0, current["id"])
            current = by_id.get(current["parent"])
        self.click(win.locator(f'.navigation [data-target="{chain[0]}"]'))
        for target in chain[1:]:
            win.locator(f'.file-row[data-target="{target}"]').dblclick()
            self.idle()
        return win

    def action(self, action):
        op = action["op"]
        if op in {"mkdir", "create-document"}:
            win = self.folder(action["parent"])
            self.click(win.locator('[data-command="new-folder"' + ']' if op == "mkdir" else '[data-command="new-document"]'))
            self.fill(self.page.locator('.dialog input[name="name"]'), action["name"])
            self.click(self.page.locator('.dialog button[type="submit"]'))
        elif op=='export-log':
            win=self.front('events')
            self.click(win.locator(f'[data-command="section"][data-target="{action["target"]}"]'))
            self.click(win.locator('[data-command="export-log"]'))
            self.page.locator('.dialog select[name="parent"]').select_option(action['parent'])
            self.idle()
            for field in ['name','start','end']:self.fill(self.page.locator(f'.dialog input[name="{field}"]'),action[field])
            self.click(self.page.locator('.dialog button[type="submit"]'))
        elif op == "copy":
            state = request(self.base, f"/api/v2/sessions/{self.sid}")["state"]
            source = next(f for f in state["files"] if f["id"] == action["target"])
            win = self.folder(source["parent"])
            self.click(win.locator(f'.file-row[data-target="{action["target"]}"]'))
            self.click(win.locator('[data-command="properties"]'))
            self.click(self.page.locator('.dialog button[type="submit"]'))
            win.locator(f'.file-row[data-target="{action["target"]}"]').dblclick()
            self.idle()
            self.click(self.page.locator('.window').last.locator('[data-command="close"]'))
            win=self.front('files')
            self.click(win.locator(f'.file-row[data-target="{action["target"]}"]'))
            self.click(win.locator('[data-command="copy"]'))
            win = self.folder(action["parent"])
            self.click(win.locator('[data-command="paste"]'))
        elif op == "properties":
            state=request(self.base,f"/api/v2/sessions/{self.sid}")["state"]
            target=next(f for f in state['files'] if f['id']==action['target'])
            win=self.folder(target['parent'])
            self.click(win.locator(f'.file-row[data-target="{target["id"]}"]'))
            self.click(win.locator('[data-command="properties"]'))
            self.click(self.page.locator('.dialog button[type="submit"]'))
        elif op == "rename":
            state = request(self.base, f"/api/v2/sessions/{self.sid}")["state"]
            target = next(f for f in state["files"] if f["id"] == action["target"])
            win = self.folder(target["parent"])
            self.click(win.locator(f'.file-row[data-target="{target["id"]}"]'))
            self.click(win.locator('[data-command="rename"]'))
            self.fill(self.page.locator('.dialog input[name="name"]'), action["name"])
            self.click(self.page.locator('.dialog button[type="submit"]'))
        elif op == "delete":
            state=request(self.base,f"/api/v2/sessions/{self.sid}")["state"]
            target=next(f for f in state['files'] if f['id']==action['target'])
            win=self.folder(target['parent'])
            self.click(win.locator(f'.file-row[data-target="{target["id"]}"]'))
            self.click(win.locator('[data-command="delete"]'))
        elif op == "write":
            win = self.front("editor")
            self.click(win.locator('[data-command="choose-document"]'))
            self.page.locator('.dialog select[name="target"]').select_option(action["target"])
            self.idle()
            self.click(self.page.locator('.dialog button[type="submit"]'))
            if '\f' in action['content']:
                # Insert page breaks through the same visible controls available
                # to people and pixel agents, never by injecting control bytes.
                plain=action['content'].replace('\f','')
                if win.locator('textarea').input_value()!=plain:
                    self.fill(win.locator('textarea'),plain)
                line=action['content'].split('\f',1)[0].count('\n')+1
                self.fill(win.locator('[data-field="go-line"]'),str(line))
                self.click(win.locator('[data-command="go-line"]'))
                self.click(win.locator('[data-command="page-break"]'))
                assert win.locator('textarea').input_value()==action['content']
                assert '2 page(s)' in win.locator('footer').inner_text()
            else:
                self.fill(win.locator('textarea'), action["content"])
            self.click(win.locator('button[type="submit"]'))
        elif op == "setting":
            section, page = {
                "archive.format":("apps","Archives"), "verification.mode":("apps","Verification"),
                "scheduler.trigger":("system","Power & scheduling"), "backup.retention":("system","Storage & backup"),
                "tools.enabled":("apps","Processing"), "privacy.redaction":("privacy","Evidence filtering"),
                "network.offline":("network","Connection"), "printer.duplex":("devices","Printing"),
                "cache.contacts":("network","Offline resources"),
                "printer.selected":("devices","Printing"),"printer.paper":("devices","Printing"),
                "distribution.destination":("network","Distribution"),
                "backup.scope":("system","Storage & backup"),"backup.include-text":("system","Storage & backup"),
                "privacy.scope":("privacy","Evidence filtering"),
                "privacy.method":("privacy","Evidence filtering"),
                "media.preview":("apps","Media previews"),
                "printer.order":("devices","Printing"),
                "tools.compiler":("apps","Processing"),"tools.signer":("apps","Processing"),
            }[action["key"]]
            win = self.front("settings")
            self.click(win.locator(f'[data-command="settings-section"][data-target="{section}"]'))
            self.click(win.locator(f'[data-command="settings-page"][data-target="{page}"]'))
            value = str(action["value"]).lower() if isinstance(action["value"], bool) else action["value"]
            win.locator(f'select[data-key="{action["key"]}"]').select_option(value)
            self.idle()
        elif op=='device-access':
            win=self.front('devices')
            win.locator(f'[data-field="device-access"][data-target="{action["target"]}"]').select_option(action['access'])
            self.idle()
        elif op in {"device", "process", "download"}:
            win = self.front({"device":"devices", "process":"monitor", "download":"transfers"}[op])
            self.click(win.locator(f'[data-command="{op}"][data-target="{action["target"]}"]'))
        elif op == "create-job":
            win = self.front("scheduler")
            self.click(win.locator('[data-command="new-job"]'))
            self.fill(self.page.locator('.dialog input[name="name"]'), action["name"])
            for key in ["kind", "input", "output", "dependency", "trigger"]:
                self.page.locator(f'.dialog select[name="{key}"]').select_option(action[key])
                self.idle()
            self.click(self.page.locator('.dialog button[type="submit"]'))
        elif op == "run-job":
            win = self.front("scheduler")
            self.click(win.locator(f'.job-row[data-target="{action["target"]}"]'))
            self.click(win.locator('[data-command="run-job"]'))
            state=request(self.base,f'/api/v2/sessions/{self.sid}')['state']
            task=next(j for j in state['jobs'] if j['id']==action['target'])
            if task['kind']=='redact' and task['status']=='Completed':
                artifact=next(f for f in state['files'] if f['id']==task['artifact'])
                files=artifact['provenance']['processing'].get('redacted_files',[])
                if files:
                    redacted=next(f for f in state['files'] if f['id']==files[0])
                    explorer=self.folder(redacted['parent'])
                    explorer.locator(f'.file-row[data-target="{redacted["id"]}"]').dblclick()
                    self.idle()
                    editor=self.page.locator('.window').last
                    visible=editor.locator('textarea').input_value()
                    assert visible==redacted['content']
                    records=[json.loads(line) for line in visible.splitlines()]
                    method=artifact['provenance']['processing']['method']
                    assert records and all(r.get('event_id') and r.get('time') and r.get('message') for r in records)
                    if method=='mask':assert all(r['contact']=='[redacted]' for r in records)
                    elif method=='remove':assert all('contact' not in r for r in records)
                    elif method=='pseudonym':assert all(r['contact'].startswith('anon-') and '@' not in r['contact'] for r in records)
                    else:raise AssertionError('Unknown visible redaction treatment: '+method)
                    self.click(editor.locator('[data-command="close"]'))
            if task['kind']=='backup' and task['status']=='Completed':
                artifact=next(f for f in state['files'] if f['id']==task['artifact'])
                snapshot_id=artifact['provenance']['processing']['snapshot_file']
                snapshot=next(f for f in state['files'] if f['id']==snapshot_id)
                explorer=self.folder(snapshot['parent'])
                explorer.locator(f'.file-row[data-target="{snapshot_id}"]').dblclick()
                self.idle()
                editor=self.page.locator('.window').last
                assert json.loads(editor.locator('textarea').input_value())['resources']
                self.click(editor.locator('[data-command="close"]'))
            if task['kind']=='test' and task['status']=='Completed':
                artifact=next(f for f in state['files'] if f['id']==task['artifact'])
                result_id=artifact['provenance']['processing']['test_file']
                result=next(f for f in state['files'] if f['id']==result_id)
                explorer=self.folder(result['parent'])
                explorer.locator(f'.file-row[data-target="{result_id}"]').dblclick()
                self.idle()
                editor=self.page.locator('.window').last
                assert json.loads(editor.locator('textarea').input_value())['passed']
                self.click(editor.locator('[data-command="close"]'))
            if task['kind']=='deliver' and task['status']=='Completed' and any(p['task']==task['id'] for p in state.get('print_queue',[])):
                device_window=self.front('devices')
                self.click(device_window.locator('[data-command="section"][data-target="print-queue"]'))
                assert 'Queued' in device_window.locator('.settings-main').inner_text()
            if task['kind']=='catalogue' and task['status']=='Completed':
                artifact=next(f for f in state['files'] if f['id']==task['artifact'])
                manifest_id=artifact['provenance']['processing'].get('catalogue_file')
                if manifest_id:
                    manifest=next(f for f in state['files'] if f['id']==manifest_id)
                    explorer=self.folder(manifest['parent'])
                    explorer.locator(f'.file-row[data-target="{manifest_id}"]').dblclick()
                    self.idle()
                    editor=self.page.locator('.window').last
                    text=editor.locator('textarea')
                    assert len(json.loads(text.input_value())['entries'])==2
                    text.click()
                    text.press('Control+End')
                    self.idle()
                    text.press('Control+Home')
                    self.idle()
                    self.click(editor.locator('[data-command="close"]'))
        elif op == "update-job":
            win = self.front("scheduler")
            self.click(win.locator(f'.job-row[data-target="{action["target"]}"]'))
            self.click(win.locator('[data-command="job-properties"]'))
            for key in ['input','output','dependency','trigger']:
                if key in action:
                    self.page.locator(f'.dialog select[name="{key}"]').select_option(action[key])
                    self.idle()
            self.click(self.page.locator('.dialog button[type="submit"]'))
        elif op == "probe":
            state=request(self.base,f"/api/v2/sessions/{self.sid}")["state"]
            by_id={f['id']:f for f in state['files']}
            current=by_id[action['target']]
            parts=[]
            while current:
                parts.insert(0,current['name'])
                current=by_id.get(current['parent'])
            command={'offline':'offline-test','workspace':'workspace-open','storage':'storage-audit','restoration':'restore-check'}[action['kind']]+' "/'+'/'.join(parts)+'"'
            win=self.front('terminal')
            self.fill(win.locator('[data-field="terminal-command"]'),command)
            win.locator('[data-field="terminal-command"]').press('Enter')
            self.idle()
        else:
            raise ValueError(f"unimplemented browser audit operation {op}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', default='OS-LH-01')
    parser.add_argument('--all', action='store_true')
    parser.add_argument('--convention', type=int, default=0)
    parser.add_argument('--seed', type=int, default=1001)
    parser.add_argument('--seeds',help='Comma-separated independent demonstration seeds')
    parser.add_argument('--plan',choices=['standard','configure-first','reverse-sources'],default='standard')
    parser.add_argument('--resume',action='store_true')
    parser.add_argument('--video', action='store_true')
    parser.add_argument('--usability', action='store_true')
    parser.add_argument('--output', type=Path, default=ROOT / 'data' / 'v2-audit')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    http = ThreadingHTTPServer(('127.0.0.1',0), server.Handler)
    thread = threading.Thread(target=http.serve_forever, daemon=True)
    thread.start()
    server.Handler.log_message = lambda *args: None
    base = f'http://127.0.0.1:{http.server_port}'
    # Explicit rendering below lets this audit inspect replay errors before
    # recording an acceptance result. Production finish still queues rendering.
    original_renderer = server.schedule_video_render
    def defer_render(sid,generation):
        session=server.SESSIONS[sid]
        session['video_status']='not-rendered-test'
        session['recording_actor']='oracle-assisted-browser-audit'
        server.persist(session)
    server.schedule_video_render = defer_render
    cases = workflows._FIXTURE_CASES if args.all else [workflows._FIXTURE_BY_ID[args.case]]
    seeds=[int(v) for v in args.seeds.split(',')] if args.seeds else [args.seed]
    results = json.loads((args.output/'results.json').read_text()) if args.resume and (args.output/'results.json').is_file() else []
    if any(row.get('plan_variant','standard')!=args.plan for row in results):
        raise ValueError('Cannot resume a directory containing another authoring plan variant.')
    fingerprint=workflows.IMPLEMENTATION['fingerprint']
    if any(row.get('implementation_fingerprint')!=fingerprint for row in results):
        raise ValueError('Output directory contains another implementation. Use a new versioned output directory.')
    completed={(r['case_id'],r['seed']) for r in results if r.get('implementation_fingerprint')==fingerprint and
        (not args.video or r.get('video_path') and Path(r['video_path']).is_file() and hashlib.sha256(Path(r['video_path']).read_bytes()).hexdigest()==r.get('video_sha256'))}
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path='/usr/bin/google-chrome',headless=True,args=['--no-sandbox'])
            for case,seed in [(case,seed) for seed in seeds for case in cases]:
                artifact_provenance.assert_unchanged(workflows.IMPLEMENTATION)
                if (case['id'],seed) in completed:
                    print(case['id'],args.convention,seed,'RESUMED',flush=True)
                    continue
                run_output=args.output/f'seed-{seed}' if args.seeds else args.output
                run_output.mkdir(parents=True,exist_ok=True)
                created = request(base, '/api/v2/sessions', {'case_id':case['id'], 'mode':'demo', 'convention':args.convention, 'seed':seed,'plan_variant':args.plan})
                sid = created['id']
                context = browser.new_context(viewport={'width':1280,'height':720},device_scale_factor=1,locale='en-US')
                page = context.new_page()
                errors = []
                page.on('pageerror',lambda e:errors.append(str(e)))
                page.goto(base+created['launch_url'])
                page.locator('#begin-demo').click()
                ui = Desktop(page); ui.base=base;ui.sid=sid
                for index, action in enumerate(created['recorder_brief']['reference']):
                    try:
                        ui.action(action)
                        # Error notifications are ordinary dismissible UI. Record
                        # that click before continuing, rather than force-clicking
                        # a control covered by the notification overlay.
                        dismiss=page.locator('[data-command="dismiss-notice"]')
                        if dismiss.count():
                            ui.click(dismiss)
                    except Exception:
                        page.screenshot(path=str(run_output/f'{case["id"]}-failure.png'))
                        print('FAILED ACTION',index,action,flush=True)
                        raise
                if args.usability:
                    state=request(base,f'/api/v2/sessions/{sid}')['state']
                    original=next(f for f in state['files'] if f['id']=='source-0')
                    explorer=ui.folder(original['parent'])
                    explorer.locator('.file-row[data-target="source-0"]').click(button='right')
                    ui.idle()
                    ui.click(page.locator('.context-menu [data-command="properties"]'))
                    assert page.locator('.dialog').is_visible()
                    ui.click(page.locator('.dialog button[type="submit"]'))
                    win=ui.front('editor')
                    saved=win.locator('textarea').input_value()
                    transient=saved+'\nUnsaved draft regression check'
                    ui.fill(win.locator('textarea'),transient)
                    ui.front('settings')
                    win=ui.front('editor')
                    assert win.locator('textarea').input_value()==transient,'switching apps lost the draft'
                    ui.click(win.locator('[data-command="close"]'))
                    assert page.locator('.dialog').get_by_text('Save changes?',exact=True).is_visible()
                    ui.click(page.locator('.dialog [data-command="cancel"]'))
                    win=ui.front('editor')
                    ui.fill(win.locator('textarea'),saved)
                    win.locator('textarea').press('Control+s')
                    ui.idle()
                ui.click(page.locator('[data-command="start"]'))
                ui.click(page.locator('[data-command="finish"]'))
                finished = request(base,f'/api/v2/sessions/{sid}')
                assert finished['result']['success'],finished['result']
                assert not errors,errors
                assert 'vibe' not in page.locator('body').inner_text().lower()
                page.screenshot(path=str(run_output/f'{case["id"]}-{args.convention}.png'))
                context.close()
                replay_context=browser.new_context(viewport={'width':1280,'height':720},locale='en-US')
                replay_page=replay_context.new_page()
                replay_page.goto(base+created['launch_url']+'&replay=1&audit_speed=fast')
                replay_page.wait_for_function('window.__REPLAY_DONE__ === true || !!window.__REPLAY_ERROR__',timeout=180000)
                error=replay_page.evaluate('window.__REPLAY_ERROR__ || null')
                if error:
                    replay_page.screenshot(path=str(run_output/f'{case["id"]}-replay-failure.png'))
                    raise AssertionError(error)
                replay_context.close()
                video_metadata={}
                if args.video:
                    artifact_provenance.assert_unchanged(workflows.IMPLEMENTATION)
                    video_path=run_output/f'{case["id"]}-{args.convention}.webm'
                    subprocess.run([sys.executable,str(ROOT/'render_video.py'),'--session',sid,
                        '--base-url',base,'--output',str(video_path)],check=True,timeout=600)
                    probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height,codec_name','-show_entries','format=duration,size','-of','json',str(video_path)]))
                    assert probe['streams'][0]['width']==1280 and probe['streams'][0]['height']==720
                    assert float(probe['format']['duration'])>=10
                    recording=server.SESSIONS[sid]
                    recording.update(video=f'{sid}.webm',video_status='ready',video_error=None)
                    recording['video_provenance']=artifact_provenance.video_metadata(recording)
                    shutil.copyfile(video_path,server.VIDEOS/recording['video'])
                    server.persist(recording)
                    video_metadata={'video_path':str(video_path.resolve()),'video_sha256':hashlib.sha256(video_path.read_bytes()).hexdigest(),
                                    'video_probe':probe,'video_provenance':recording['video_provenance']}
                results.append({'case_id':case['id'],'convention':args.convention,'seed':seed,'session_id':sid,'plan_variant':args.plan,
                                'result':finished['result'],'browser_errors':errors,'replay_hash_verified':True,
                                'usability_checks':args.usability,'implementation_fingerprint':fingerprint,
                                'scenario':server.SESSIONS[sid]['episode']['scenario'], **video_metadata})
                (args.output/'results.json').write_text(json.dumps(results,indent=2))
                print(case['id'],args.convention,seed,'PASS',flush=True)
            browser.close()
    finally:
        server.schedule_video_render=original_renderer
        http.shutdown();http.server_close()
    print(f'{len(results)} browser workflows verified.',flush=True)


if __name__=='__main__':
    main()
