"""OS-ICL v2 resource graph. Policy/oracles remain in trusted Python only."""
from __future__ import annotations

import copy
import hashlib
import hmac
import zlib
import json
import random
import domain_checks
import protocols
import artifact_provenance

VERSION = "2.0.0-dev.5"
SCHEMA_VERSION = 5
IMPLEMENTATION = artifact_provenance.capture()
CONVENTIONS = (
    {"workspace": "Working", "delivery": "Deliverables", "prefix": "reviewed-",
     "format": "zip", "verify": "checksum", "schedule": "manual", "retention": "keep",'preview':'review','print_order':'forward','redaction':'mask'},
    {"workspace": "Preparation", "delivery": "Handoff", "prefix": "ready-",
     "format": "tar", "verify": "full", "schedule": "idle", "retention": "versioned",'preview':'compact','print_order':'reverse','redaction':'remove'},
    {"workspace": "Staging", "delivery": "Exports", "prefix": "final-",
     "format": "zip", "verify": "full", "schedule": "plugged-in", "retention": "keep",'preview':'detail','print_order':'forward','redaction':'pseudonym'},
)

# Job pipelines differ in purpose and dependencies, rather than hiding arbitrary
# symbol mappings. Operation parameters are learned from demonstrated practice.
_FIXTURE_TEMPLATES = [
    ("Research handoff", "Prepare and deliver the current research project with an edited handoff index and verified archive.",
     ["inventory", "validate", "index", "package", "verify", "deliver"], "research", "lock"),
    ("Release preparation", "Prepare a verified release bundle from the current project, including release notes and a signed build report.",
     ["inventory", "validate", "build", "sign", "package", "verify", "deliver"], "release", "dependency"),
    ("Backup and recovery", "Back up the project, restore a test copy, compare it with the source, and deliver the recovery report.",
     ["inventory", "backup", "restore", "compare", "verify", "deliver"], "backup", None),
    ("Media ingest", "Import the camera material, prepare preview copies, and deliver a verified media collection.",
     ["inventory", "validate", "transcode", "catalogue", "verify", "deliver"], "media", "device"),
    ("Print production", "Prepare the document set, configure the printer, proof the output and submit the verified print packet.",
     ["inventory", "validate", "layout", "proof", "verify", "deliver"], "print", "printer"),
    ("Offline field kit", "Download the field resources, prepare the offline workspace and deliver a verified field kit.",
     ["inventory", "validate", "cache", "package", "verify", "deliver"], "offline", "download"),
    ("Workspace migration", "Migrate the project into a fresh workspace, update its manifest and deliver the verified migration result.",
     ["inventory", "validate", "migrate", "compare", "verify", "deliver"], "migration", None),
    ("Failed build recovery", "Recover the project build, preserve the previous output and deliver a verified replacement.",
     ["inventory", "validate", "build", "test", "package", "verify", "deliver"], "build", "lock"),
    ("Evidence archive", "Collect the incident evidence, redact the working copies and deliver a verified evidence archive.",
     ["inventory", "validate", "redact", "package", "verify", "deliver"], "evidence", None),
    ("Scheduled distribution", "Prepare the project distribution, configure the destination and schedule its verified delivery.",
     ["inventory", "validate", "dry-run", "replicate", "package", "verify", "deliver"], "distribution", "destination"),
    ("Storage maintenance", "Preserve the project, compact its working data and deliver a verified maintenance report.",
     ["inventory", "backup", "verify-backup", "compact", "compare", "verify", "deliver"], "storage", None),
    ("Project restoration", "Retrieve the project snapshot, restore its working files and deliver a verified restoration report.",
     ["inventory", "validate", "restore", "compare", "verify", "deliver"], "restoration", "download"),
]

_FIXTURE_CASES = [{"id": f"OS-LH-{i+1:02}", "title": t[0], "task": t[1],
          "family": "long_horizon", "difficulty": "L4", "pipeline": t[2],
          "domain": t[3], "recovery": t[4], "app": "Desktop"}
         for i, t in enumerate(_FIXTURE_TEMPLATES)]
_FIXTURE_BY_ID = {c["id"]: c for c in _FIXTURE_CASES}
TOOL_DEPENDENCIES = protocols.dependencies(_FIXTURE_CASES)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def node(identifier, parent, name, kind="folder", content="", **extra):
    return {"id": identifier, "parent": parent, "name": name, "kind": kind,
            "content": content, "deleted": False, "revision": 1, **extra}


def _generate_fixture(case_id="OS-LH-01", convention=0, seed=42, plan_variant='standard'):
    """Private resource construction templates; not an exposed task catalogue."""
    if case_id not in _FIXTURE_BY_ID or convention not in range(3):
        raise ValueError("unknown task or convention")
    rng = random.Random(seed)
    scenario=seed % 3
    case = copy.deepcopy(_FIXTURE_BY_ID[case_id])
    case["pipeline"] = protocols.pipeline_for(case, convention)
    project = rng.choice(["Northbridge", "Lakeside", "Cedar", "Summit", "Harbour"])
    project += f"-{rng.randrange(100, 999)}"
    domain = case["domain"]
    names = {
        "research": ["observations.csv", "protocol.txt", "results.csv", "summary.txt"],
        "release": ["application.js", "release-notes.txt", "config.json", "assets.csv"],
        "backup": ["records.csv", "preferences.json", "notes.txt", "inventory.csv"],
        "media": ["scene-01.mov", "scene-02.mov", "captions.txt", "shot-list.csv"],
        "print": ["cover.txt", "report.txt", "appendix.txt", "figures.csv"],
        "offline": ["map.csv", "contacts.csv", "field-guide.txt", "checklist.txt"],
        "migration": ["workspace.json", "source.js", "app-settings.json", "resources.csv"],
        "build": ["main.js", "modules.json", "build-notes.txt", "resources.csv"],
        "evidence": ["access.log", "system.log", "timeline.csv", "incident.txt"],
        "distribution": ["package.json", "instructions.txt", "catalogue.csv", "release.txt"],
        "storage": ["records.csv", "cache.csv", "notes.txt", "inventory.csv"],
        "restoration": ["snapshot.json", "records.csv", "notes.txt", "inventory.csv"],
    }[domain]
    files = [node("desktop", None, "Desktop"), node("documents", None, "Documents"),
             node("downloads", None, "Downloads"), node("projects", None, "Projects"),
             node("recycle", None, "Recycle Bin"), node("project", "projects", project),
             node("inputs", "project", "Inputs"), node("previous", "project", "Previous"),
             node("old-output", "previous", "previous-release.zip", "archive", "Preserve this previous release."),
             node("reference", "documents", "Read me.txt", "text", "Use Start to open applications. Files and jobs share the same workspace. Job dependencies refer to job names; outputs are written into the selected output folder."),
             node("scratch", "desktop", "Notes.txt", "text", "")]
    for i, name in enumerate(names):
        revision = rng.randrange(2, 9)
        content = f"Project: {project}\nResource: {name}\nRevision: {revision}\nOwner: Operations\n"
        if name.endswith(".csv"):
            content = "record,value,owner\n" + "\n".join(f"{project}-{n+1},{rng.randrange(10,900)},Operations" for n in range(8)) + "\n"
        elif name.endswith(".json"):
            content = json.dumps({"project":project,"revision":revision,"resources":names,"enabled":True},indent=2)
            if domain == "build" and name == "modules.json":
                content = json.dumps({"project":project,"revision":revision,"resources":names,"enabled":True,"build_ready":scenario==0},indent=2)
        elif name.endswith(".js"):
            content = f"export const project = {json.dumps(project)};\nexport const revision = {revision};\nexport function status() {{ return {{project, revision}}; }}\n"
        elif name.endswith(".mov"):
            content = json.dumps({"virtual_media":True,"project":project,"duration_seconds":rng.randrange(30,240),"frames":rng.randrange(900,7200),"codec":"virtual-source"},indent=2)
        if domain == "evidence":
            content += "Contact: private@example.test\nEvent: service interrupted\n"
        files.append(node(f"source-{i}", "inputs", name, "text", content,
                          revision=revision,
                          downloaded=case["recovery"] != "download" or scenario==0,
                          device_source=domain == "media"))
    # Realistic irrelevant files and deeper folders make navigation necessary.
    files += [node("old-project", "projects", "Previous quarter"),
              node("unrelated", "old-project", "Budget.txt", "text", "Unrelated project; preserve."),
              node("drafts", "project", "Drafts"),
              node("draft", "drafts", "unapproved-draft.txt", "text", "Draft; excluded from handoff.")]
    state = {"files": files, "settings": {"archive.format": "zip", "verification.mode": "checksum",
             "scheduler.trigger": "manual", "backup.retention": "keep", 'backup.scope':'all','backup.include-text':True, "tools.enabled": scenario==0,
             'tools.compiler':True,'tools.signer':True,
             "network.offline": False, "cache.contacts":True, "printer.duplex": False, 'printer.selected':'printer','printer.paper':'A4','printer.order':'forward',
             'distribution.destination':'destination', "privacy.redaction": False,'privacy.scope':'contact','privacy.method':'mask','media.preview':'review'},
             "jobs": [], "devices": [
                 {"id": "camera", "name": "Field Camera", "kind": "Camera", "connected": scenario==0},
                 {"id": "printer", "name": "Office Printer", "kind": "Printer", "connected": scenario==0},
                 {"id": "destination", "name": "Team Share", "kind": "Network storage", "connected": scenario==0}],
             "processes": [{"id": "indexer", "name": "Project Indexer", "status": "Running",
                            "locks": ["source-0"] if case["recovery"] == "lock" and scenario!=0 else [], "memory": 348},
                           {"id": "system", "name": "Desktop Manager", "status": "Running", "locks": [], "memory": 176}],
             "transfers": [{"id": f"download-{i}", "file": f"source-{i}", "name": name,
                            "status": "Completed" if scenario==0 else "Pending", "progress": 100 if scenario==0 else 0} for i, name in enumerate(names)]
                            if case["recovery"] == "download" else [],
             "events": [{"level": "Information", "source": "Workspace", "message": f"Project {project} is ready."}],
             "project": project, "case_id": case_id}
    domain_checks.configure(state, case, scenario)
    return {"benchmark_version": VERSION, "schema_version": SCHEMA_VERSION, "case": case,
            "seed": seed, "scenario":scenario, "implementation":copy.deepcopy(IMPLEMENTATION),
            "convention": convention, "initial": copy.deepcopy(state), "state": state,
            "events": [],'plan_variant':plan_variant, "reference": reference(case, state, CONVENTIONS[convention],plan_variant)}


def get_file(state, identifier):
    result = next((f for f in state["files"] if f["id"] == identifier and not f["deleted"]), None)
    if result is None:
        raise ValueError("file not found")
    return result


def path(state, identifier):
    names, seen = [], set()
    while identifier:
        if identifier in seen:
            raise ValueError("cyclic folder graph")
        seen.add(identifier)
        f = get_file(state, identifier)
        names.insert(0, f["name"])
        identifier = f["parent"]
    return "/" + "/".join(names)


def add_file(state, parent, name, kind, content="", **extra):
    if get_file(state, parent)["kind"] != "folder":
        raise ValueError("destination is not a folder")
    if not name.strip() or "/" in name or "\\" in name:
        raise ValueError("invalid file name")
    if any(f["parent"] == parent and f["name"] == name and not f["deleted"] for f in state["files"]):
        raise ValueError("a file with this name already exists")
    identifier = "f-" + str(len(state["files"]) + 1)
    f = node(identifier, parent, name, kind, content, **extra)
    state["files"].append(f)
    return f


def resolve_folder(state, name, parent="project"):
    f = next((f for f in state["files"] if f["parent"] == parent and f["name"] == name and not f["deleted"]), None)
    if f is None or f["kind"] != "folder":
        raise ValueError(f"folder {name} does not exist")
    return f["id"]


def transition(episode, action):
    """Atomic reducer; rejected operations add an error but never partial output."""
    before = digest(episode["state"])
    candidate = copy.deepcopy(episode["state"])
    try:
        outcome = mutate(candidate, action, episode["case"])
        episode["state"] = candidate
        accepted, error = True, None
    except (ValueError, KeyError, TypeError) as exc:
        outcome, accepted, error = None, False, str(exc)
        episode["state"]["events"].append({"level": "Error", "source": action.get("op", "Operation"), "message": error})
    event = {"action": copy.deepcopy(action), "accepted": accepted, "error": error,
             "outcome": outcome, "before": before, "after": digest(episode["state"])}
    episode["events"].append(event)
    return event


def mutate(state, action, case):
    op = action.get("op")
    if op == "probe":
        return domain_checks.probe(state, action, get_file, path, digest)
    if op == "mkdir":
        return add_file(state, action["parent"], action["name"], "folder")["id"]
    if op in {"copy", "rename", "move", "delete", "write", "properties"}:
        f = get_file(state, action["target"])
        if op == "properties":
            return {"path": path(state, f["id"]), "revision": f["revision"], "sha256": digest(f["content"]),
                    "bytes":f.get('storage_bytes',len(f["content"].encode())), "regenerable":f.get("regenerable",False),
                    "snapshot_version":f.get('snapshot_version'), "snapshot_status":f.get('snapshot_status'),
                    "approved":f.get("approved"), 'resource_key':f.get('resource_key'), "owners":[p["name"] for p in state["processes"] if f["id"] in p["locks"]]}
        if op in {"rename", "move", "delete", "write"} and any(f["id"] in p["locks"] and p["status"]=="Running" for p in state["processes"]):
            raise ValueError("Resource is in use. Pause its owner before modifying it.")
        if op == "copy":
            if f["kind"] == "folder":
                raise ValueError("select a file to copy")
            if not f.get("downloaded", True):
                raise ValueError("download this resource before copying")
            if f.get("device_source") and not state["devices"][0]["connected"]:
                raise ValueError("connect the camera before importing")
            owners=[p['name'] for p in state['processes'] if f['id'] in p['locks'] and p['status']=='Running']
            if owners:
                raise ValueError('Resource is locked by '+', '.join(owners))
            return add_file(state, action["parent"], action.get("name", f["name"]), f["kind"], f["content"],
                            source=f.get("source", f["id"]), source_hash=digest(f["content"]),
                            **({k:f[k] for k in ("revision","approved","resource_key") if k in f} if case.get("id")=="OS-E-03" else {}))["id"]
        if op == "rename":
            name = action["name"]
            if not name.strip() or "/" in name or "\\" in name:
                raise ValueError("invalid file name")
            if any(x["id"] != f["id"] and x["parent"] == f["parent"] and x["name"] == name and not x["deleted"] for x in state["files"]):
                raise ValueError("name conflict")
            f["name"] = name
        elif op == "move":
            parent = get_file(state, action["parent"])
            if parent["kind"] != "folder" or parent["id"] == f["id"] or path(state, parent["id"]).startswith(path(state, f["id"]) + "/"):
                raise ValueError("invalid destination")
            if any(x["parent"] == parent["id"] and x["name"] == f["name"] and not x["deleted"] for x in state["files"]):
                raise ValueError("name conflict")
            f["parent"] = parent["id"]
        elif op == "delete":
            targets=[f]
            identifiers={f['id']}
            # Resolve the whole subtree before changing anything. Checking only
            # the folder would bypass descendant locks and cache safety gates.
            while True:
                children=[x for x in state['files'] if not x['deleted'] and x['parent'] in identifiers and x['id'] not in identifiers]
                if not children:break
                targets.extend(children)
                identifiers.update(x['id'] for x in children)
            if any(p['status']=='Running' and identifiers.intersection(p['locks']) for p in state['processes']):
                raise ValueError('A file in this folder is in use. Pause its owner before deleting the folder.')
            if any(x.get('regenerable') for x in targets):
                verification=next((j for j in state["jobs"] if j["kind"]=="verify-backup" and j["status"]=="Completed"),None)
                if verification is None:
                    raise ValueError("Verify the project backup before cleaning rebuildable cache.")
                receipt=get_file(state,verification["artifact"])
                if receipt["content"]!=json.dumps(receipt.get("provenance",{}),indent=2):
                    raise ValueError("Backup verification receipt has been altered.")
            if identifiers.intersection({"desktop", "projects", "documents", "downloads", "project", "inputs", "recycle"}):
                raise ValueError("system folder cannot be deleted")
            for target in targets:target['deleted']=True
        elif op == "write":
            if f["kind"] == "folder":
                raise ValueError("cannot edit a folder")
            content=str(action['content'])
            if content!=f['content']:
                f['content']=content
                f['revision']+=1
        return f["id"]
    if op=='export-log':
        from datetime import datetime
        source=get_file(state,action['target'])
        if not source.get('log_channel'):raise ValueError('Select an Event Viewer log channel to export.')
        try:
            start,end=datetime.fromisoformat(action['start']),datetime.fromisoformat(action['end'])
            if start>end:raise ValueError('Start is after end.')
            records=[json.loads(line) for line in source['content'].splitlines()]
            selected=[record for record in records if start<=datetime.fromisoformat(record['time'])<=end]
        except (ValueError,KeyError,TypeError) as exc:raise ValueError('Invalid log export interval or log record: '+str(exc))
        if not selected:raise ValueError('No records occur in the selected export interval.')
        content='\n'.join(json.dumps(record,sort_keys=True) for record in selected)+'\n'
        exported=add_file(state,action['parent'],action.get('name',source['name']),'text',content,
                          source=source['id'],source_hash=digest(source['content']),export_channel=source['log_channel'])
        state.setdefault('log_exports',[]).append({'source':source['id'],'file':exported['id'],'channel':source['log_channel'],
            'start':action['start'],'end':action['end'],'source_sha256':digest(source['content']),'export_sha256':digest(content),'event_ids':[r['event_id'] for r in selected]})
        return exported['id']
    if op == "create-document":
        return add_file(state, action["parent"], action["name"], "text", str(action.get("content", "")))["id"]
    if op == "setting":
        key, value = action["key"], action["value"]
        allowed = {"archive.format": ["zip", "tar"], "verification.mode": ["checksum", "full"],
                   "scheduler.trigger": ["manual", "idle", "plugged-in"], "backup.retention": ["keep", "versioned"],
                   "tools.enabled": [True, False], "network.offline": [True, False], "cache.contacts": [True,False],
                   "printer.duplex": [True, False], 'printer.selected':[d['id'] for d in state['devices'] if d['kind']=='Printer'],
                   'printer.paper':['A4','Letter'], "privacy.redaction": [True, False]}
        allowed['distribution.destination']=[d['id'] for d in state['devices'] if d['kind']=='Network storage']
        allowed['backup.scope']=['all','sources'];allowed['backup.include-text']=[True,False]
        allowed['privacy.scope']=['contact','personal']
        allowed['privacy.method']=['mask','remove','pseudonym']
        allowed['media.preview']=['review','compact','detail']
        allowed['printer.order']=['forward','reverse']
        allowed['tools.compiler']=[True,False];allowed['tools.signer']=[True,False]
        if key not in allowed or value not in allowed[key]:
            raise ValueError("invalid setting")
        state["settings"][key] = value
        return key
    if op == "device":
        d = next((d for d in state["devices"] if d["id"] == action["target"]), None)
        if d is None:
            raise ValueError("device not found")
        d["connected"] = bool(action["connected"])
        return d["id"]
    if op == "process":
        p = next((p for p in state["processes"] if p["id"] == action["target"]), None)
        if p is None or action["status"] not in {"Running", "Paused", "Stopped"}:
            raise ValueError("invalid process operation")
        p["status"] = action["status"]
        return p["id"]
    if op=='device-access':
        device=next((d for d in state['devices'] if d['id']==action['target'] and d['kind']=='Network storage'),None)
        if device is None or action['access'] not in {'read-only','read-write'}:raise ValueError('Invalid destination access setting.')
        device['access']=action['access']
        return device['id']
    if op == "download":
        transfer = next((t for t in state["transfers"] if t["id"] == action["target"]), None)
        if transfer is None:
            raise ValueError("transfer not found")
        if state["settings"]["network.offline"]:
            raise ValueError("turn off offline mode before downloading")
        transfer['attempts']=transfer.get('attempts',0)+1
        endpoint=next((d for d in state['devices'] if d['id']==transfer.get('device')),None)
        if endpoint and not endpoint['connected']:
            error=f"Connection to {endpoint['name']} is unavailable. Reconnect the adapter in Device Manager and retry this transfer."
            transfer.update(status='Failed',progress=0,error=error)
            state['events'].append({'level':'Error','source':'Transfer Manager','message':transfer['name']+': '+error})
            return {'status':'Failed','error':error}
        transfer.update(status="Completed", progress=100,error='')
        get_file(state, transfer["file"])["downloaded"] = True
        return transfer["id"]
    if op=='print-control':
        item=next((p for p in state.get('print_queue',[]) if p['id']==action['target']),None)
        status=action['status']
        if item is None:raise ValueError('Print job not found.')
        allowed={'Queued':{'Paused','Cancelled'},'Paused':{'Queued','Cancelled'},'Cancelled':set()}
        if status not in allowed.get(item['status'],set()):raise ValueError('Invalid print queue transition.')
        if status=='Queued':
            printer=next(d for d in state['devices'] if d['id']==item['printer'])
            if not printer['connected']:raise ValueError('Reconnect the printer before resuming the print job.')
        item['status']=status
        state['events'].append({'level':'Information','source':'Print queue','message':item['name']+': '+status})
        return item['id']
    if op == "create-job":
        kind, name = action["kind"], str(action["name"])
        if kind not in TOOL_DEPENDENCIES:
            raise ValueError("unknown job type")
        if not name.strip() or any(j["name"] == name for j in state["jobs"]):
            raise ValueError("job name is empty or already exists")
        for key in ["input", "output"]:
            if get_file(state, action[key])["kind"] != "folder":
                raise ValueError("job paths must be folders")
        dependency = action.get("dependency", "")
        if dependency and not any(j["name"] == dependency for j in state["jobs"]):
            raise ValueError("dependency job does not exist")
        job = {"id": f"job-{len(state['jobs'])+1}", "name": name, "kind": kind,
               "input": action["input"], "output": action["output"], "dependency": dependency,
               "trigger": action.get("trigger", state["settings"]["scheduler.trigger"]),
               "status": "Ready", "error": None, "artifact": None}
        if job["trigger"] not in {"manual", "idle", "plugged-in"}:
            raise ValueError("invalid job trigger")
        state["jobs"].append(job)
        return job["id"]
    if op == "update-job":
        job = next((j for j in state["jobs"] if j["id"] == action["target"]), None)
        if job is None:
            raise ValueError("job not found")
        if any(p['task']==job['id'] and p['status'] in {'Queued','Paused'} for p in state.get('print_queue',[])):
            raise ValueError('Cancel the submitted print job before resetting its producer task.')
        if any(j["dependency"] == job["name"] and j["status"] == "Completed" for j in state["jobs"]):
            raise ValueError("completed dependent tasks must be reset before editing this task")
        for key in ["input", "output"]:
            if key in action and get_file(state, action[key])["kind"] != "folder":
                raise ValueError("job paths must be folders")
        dependency = action.get("dependency", job["dependency"])
        prior = next((j for j in state["jobs"] if j["name"] == dependency), None)
        if dependency and (prior is None or prior["id"] == job["id"]):
            raise ValueError("invalid dependency")
        seen = {job["name"]}
        while prior:
            if prior["name"] in seen:
                raise ValueError("cyclic task dependency")
            seen.add(prior["name"])
            prior = next((j for j in state["jobs"] if j["name"] == prior["dependency"]), None)
        if action.get("trigger", job["trigger"]) not in {"manual", "idle", "plugged-in"}:
            raise ValueError("invalid trigger")
        if job["artifact"]:
            get_file(state, job["artifact"])["deleted"] = True
        for generated in state["files"]:
            if generated.get("generated_by") == job["id"]:
                generated["deleted"] = True
        job.update({key: action[key] for key in ["input", "output", "dependency", "trigger"] if key in action})
        job.update(status="Ready", artifact=None, error=None)
        return job["id"]
    if op == "run-job":
        job = next((j for j in state["jobs"] if j["id"] == action["target"]), None)
        if job is None:
            raise ValueError("job not found")
        if job["status"] in {"Completed", "Scheduled"}:
            raise ValueError("job already completed or scheduled; edit/reset it before rerunning")
        error = job_error(state, job, case)
        if error:
            job.update(status="Failed", error=error)
            state["events"].append({"level": "Error", "source": job["name"], "message": error})
            return {"status": "Failed", "error": error}
        inputs = [f for f in state["files"] if f["parent"] == job["input"] and f["kind"] != "folder" and not f["deleted"]]
        parent_job = next((j for j in state["jobs"] if j["name"] == job["dependency"]), None)
        source_versions = {f["id"]: digest(f["content"]) for f in inputs}
        extension = state["settings"]["archive.format"] if job["kind"] in {"package", "backup"} else "json"
        output_name = f"{job['name']}.{extension}"
        resources = [{"name": f["name"], "content": f["content"], "source": f.get("source", f["id"])} for f in inputs]
        prior_artifact = get_file(state, parent_job["artifact"]) if parent_job else None
        prior_report = prior_artifact.get("provenance", {}) if prior_artifact else {}
        # Every stage carries the actual virtual bytes, not an acknowledgement
        # with an operation label. This makes restore/compare/redact observable.
        if prior_report.get("resources"):
            resources = copy.deepcopy(prior_report["resources"])
        kind = job["kind"]
        if kind=='backup':
            if state['settings']['backup.scope']=='sources':
                copied_sources={f['source'] for f in inputs if f.get('source')}
                resources=[r for r in resources if r['source'] in copied_sources]
            if not state['settings']['backup.include-text']:
                resources=[r for r in resources if not r['name'].endswith('.txt')]
            if not resources:
                error='Backup scope contains no files. Inspect the source-copy and text-document settings.'
                job.update(status='Failed',error=error)
                return {'status':'Failed','error':error}
        processing = {}
        if kind == "validate":
            processing = {"nonempty": all(r["content"].strip() for r in resources), "count": len(resources)}
            if not processing["nonempty"]:
                job.update(status="Failed", error="An input is empty; repair the document before retrying.")
                return {"status": "Failed", "error": job["error"]}
        elif kind == "index":
            processing = {"entries": [r["name"] for r in resources]}
        elif kind=='dry-run':
            destination=selected_destination(state)
            processing={'destination':destination['id'],'destination_name':destination['name'],'recipient':destination.get('recipient'),
                        'access_checked':destination.get('access','read-write'),'payload_sha256':digest(resources),'dispatched':False}
        elif kind == "build":
            processing = {"build_id": digest(resources)[:12], "modules": [r["name"] for r in resources if r["name"].endswith((".js", ".json"))]}
            if case['domain']=='release':
                config=json.loads(next(r['content'] for r in resources if r.get('source')=='source-2'))
                processing.update(release_version=config['release_version'],entry=config['entry'])
        elif kind=='test':
            assertions=build_assertions(resources)
            failed=next((a for a in assertions if not a['passed']),None)
            if failed:
                error=f"Test assertion failed: {failed['name']} expected {failed['expected']!r}, got {failed['actual']!r}. Repair test_expectations in the working modules.json, then reset and rerun upstream tasks."
                job.update(status='Failed',error=error)
                state['events'].append({'level':'Error','source':job['name'],'message':error})
                return {'status':'Failed','error':error}
            result={'build_artifact':prior_artifact['id'],'build_sha256':digest(prior_artifact['content']),
                    'assertions':assertions,'passed':True}
            test_file=add_file(state,job['output'],job['name']+'-results.json','text',json.dumps(result,indent=2),generated_by=job['id'])
            processing={**result,'test_file':test_file['id'],'test_sha256':digest(test_file['content'])}
        elif kind == "sign":
            processing={"identity":"Workspace Local CA", "signed_artifact":prior_artifact["id"],
                        "signature":hmac.new(b'OS-ICL virtual signing authority',prior_artifact["content"].encode(),hashlib.sha256).hexdigest()}
        elif kind == "redact":
            import re
            redacted=[]
            folder=add_file(state,job['output'],job['name']+'-files','folder',generated_by=job['id']) if case['domain']=='evidence' else None
            for r in resources:
                if case['domain']=='evidence' and r['source'] in {'source-0','source-1'}:
                    fields=state['sensitive_fields'] if state['settings']['privacy.scope']=='personal' else ['contact']
                    rows=[json.loads(line) for line in r['content'].splitlines()]
                    rows=[domain_checks.redact_record(row,fields,state['settings']['privacy.method']) for row in rows]
                    r['content']='\n'.join(json.dumps(row,sort_keys=True) for row in rows)+'\n'
                    redacted.append(add_file(state,folder['id'],r['name'],'text',r['content'],source=r['source'],generated_by=job['id']))
                else:r["content"] = re.sub(r"[\w.+-]+@[\w.-]+\.[\w-]+", "[redacted]", r["content"])
            processing = {"personal_information_filtered": True,'scope':state['settings']['privacy.scope'],'method':state['settings']['privacy.method']}
            if folder:processing.update(redacted_folder=folder['id'],redacted_files=[f['id'] for f in redacted])
        elif kind in {"restore", "migrate", "cache"}:
            direct_restore=(kind=='restore' and case['domain'] in {'backup','restoration'}) or (kind=='migrate' and case['domain']=='migration')
            restored=get_file(state,job['output']) if direct_restore else add_file(state, job["output"], f"{job['name']}-files", "folder", generated_by=job["id"])
            if direct_restore:
                migration_names=[(member['name'],get_file(state,member['source'])['name']) for member in resources] if kind=='migrate' else []
                for resource in resources:
                    original=get_file(state,resource['source'])
                    if kind=='migrate':
                        old_root=path(state,job['input'])+'/'
                        new_root=path(state,restored['id'])+'/'
                        for old_name,new_name in migration_names:
                            resource['content']=resource['content'].replace(old_root+old_name,new_root+new_name)
                        resource['content']=resource['content'].replace(old_root,new_root)
                    resource['name']=original['name']
            if kind == "migrate" or kind=="restore" and case["domain"]=="restoration":
                source_root = path(state, job["input"]) + "/"
                output_root = path(state, restored["id"]) + "/"
                for resource in resources:
                    if resource.get("source") == "source-0":
                        if direct_restore:
                            manifest=json.loads(resource['content'])
                            manifest['entry']=output_root+get_file(state,'source-1')['name']
                            manifest['references']=[output_root+get_file(state,f'source-{i}')['name'] for i in range(1,4)]
                            resource['content']=json.dumps(manifest,indent=2)
                        else:
                            resource["content"] = resource["content"].replace(source_root, output_root)
            materialized_resources=[r for r in resources if not (kind=='cache' and case['domain']=='offline' and r.get('source')=='source-1' and not state['settings'].get('cache.contacts',True))]
            for r in materialized_resources:
                add_file(state, restored["id"], r["name"], "text", r["content"], source=r["source"], generated_by=job["id"])
            processing = {"materialized_folder": restored["id"], "count": len(materialized_resources),
                          'omitted_sources':[r['source'] for r in resources if r not in materialized_resources]}
        elif kind == "transcode":
            width,height=preview_dimensions(state['settings']['media.preview'])
            previews = add_file(state, job["output"], f"{job['name']}-previews", "folder", generated_by=job["id"])
            captions=next((json.loads(r["content"])["captions"] for r in resources if r.get("source")=="source-2"),[])
            for r in resources:
                if r["name"].endswith(".mov"):
                    media=json.loads(r["content"])
                    caption=next(c["text"] for c in captions if c["clip_id"]==media["clip_id"])
                    add_file(state, previews["id"], r["name"].removesuffix(".mov") + "-preview.txt", "text",
                             json.dumps({"clip_id":media["clip_id"],"session":media['session'],"caption":caption,"source_hash":digest(r["content"]),"virtual_preview":True,'width':width,'height':height},indent=2), source=r["source"], generated_by=job["id"])
            processing = {"preview_folder": previews["id"], "codec": "virtual-preview",'width':width,'height':height,'preset':state['settings']['media.preview']}
        elif kind=='catalogue' and case['domain']=='media':
            catalogue=media_catalogue(state,prior_report)
            manifest=add_file(state,job['output'],job['name']+'-index.json','text',json.dumps(catalogue,indent=2),generated_by=job['id'])
            processing={'catalogue_file':manifest['id'],'catalogue_sha256':digest(manifest['content']),
                        'session':catalogue['session'],'entries':catalogue['entries']}
        elif kind == "layout":
            ordered=sorted(resources,key=lambda r:r['source']) if case['domain']=='print' else resources
            pages=[{"name": r["name"], "page":i+1, "lines": len(page.splitlines())} for r in ordered if case['domain']!='print' or r['source'].startswith('source-') for i,page in enumerate(r["content"].split("\f"))]
            if state['settings']['printer.order']=='reverse':pages.reverse()
            processing = {"pages":pages,'order':state['settings']['printer.order'],
                          "duplex": state["settings"]["printer.duplex"], 'printer':state['settings']['printer.selected'],
                          'paper':state['settings']['printer.paper'],'page_line_limit':selected_printer(state).get('page_line_limit',40)}
        elif kind == "proof":
            processing = {"proof_passed": bool(prior_report.get("processing", {}).get("pages")),
                          "printer": state['settings']['printer.selected'],'paper':state['settings']['printer.paper'],
                          'duplex':state['settings']['printer.duplex'],'order':state['settings']['printer.order']}
        elif kind == "compare":
            if parent_job and parent_job['kind'] in {'restore','migrate'}:
                folder=prior_report['processing']['materialized_folder']
                actual=[f for f in state['files'] if f['parent']==folder and not f['deleted']]
                if case['domain']=='backup':
                    missing=[get_file(state,f'source-{i}')['name'] for i in range(4) if not any(f.get('source')==f'source-{i}' for f in actual)]
                    if missing:
                        error='Recovery scope incomplete: '+', '.join(missing)+' missing. Include required text documents and rebuild the backup and recovery copy.'
                        job.update(status='Failed',error=error)
                        state['events'].append({'level':'Error','source':job['name'],'message':error})
                        return {'status':'Failed','error':error}
                matched=all(any(f['name']==r['name'] and f['content']==r['content'] for f in actual) for r in resources)
                processing={'matched':matched,'compared_folder':folder,'expected_resource_count':len(resources)}
            else:
                originals = {f["id"]: f["content"] for f in state["files"] if f["id"].startswith("source-")}
                processing = {"matched": all(r["content"] == originals[r["source"]] for r in resources if r["source"] in originals)}
            if not processing['matched']:
                job.update(status='Failed',error='Restored content differs from the verified snapshot. Repair the recovery copy and retry comparison.')
                return {'status':'Failed','error':job['error']}
        elif kind == "compact":
            payload=json.dumps(resources,sort_keys=True,separators=(',',':')).encode()
            packed=zlib.compress(payload,9)
            compressed=add_file(state,job['output'],job['name']+'.deflate','archive',packed.hex(),
                                encoding='hex/zlib',storage_bytes=len(packed),generated_by=job['id'])
            processing = {"bytes_before":len(payload), 'bytes_after':len(packed),
                          'compressed_artifact':compressed['id'],'codec':'zlib',
                          "content_hash": digest(resources), "lossless":zlib.decompress(packed)==payload}
        elif kind in {"verify", "verify-backup"}:
            processing = {"verified_artifact": prior_artifact["id"] if prior_artifact else None,
                          "sha256": digest(prior_artifact["content"]) if prior_artifact else None,
                          "mode": state["settings"]["verification.mode"],
                          "content_hash": digest(resources)}
        elif kind == "audit":
            trail=[]
            current=parent_job
            while current:
                record=get_file(state,current["artifact"])
                trail.append({"task":current["name"],"operation":current["kind"],
                              "artifact":record["id"],"sha256":digest(record["content"]),
                              "input_hashes":record["provenance"]["hashes"]})
                current=next((j for j in state["jobs"] if j["name"]==current["dependency"]),None)
            processing={"verification_receipt":prior_artifact["id"],"audit_trail":trail,
                        "resource_hash":digest(resources)}
        elif kind == "deliver":
            processing = {"verification_receipt": prior_artifact["id"] if prior_artifact else None,
                          "delivered_resource_count": len(resources)}
            if case["domain"] == "distribution":
                destination=selected_destination(state)
                check=ancestor_job(state,parent_job,'dry-run')
                processing.update(dispatch_status="Scheduled", destination=destination['id'],recipient=destination['recipient'],
                                  dry_run_receipt=check['artifact'],trigger=job["trigger"], payload_hash=digest(resources),dispatched=False)
            if case['domain']=='print':
                proof_job=ancestor_job(state,parent_job,'proof')
                proof=get_file(state,proof_job['artifact'])
                layout_job=ancestor_job(state,proof_job,'layout')
                pages=get_file(state,layout_job['artifact'])['provenance']['processing']['pages']
                documents=[copy.deepcopy(r) for r in resources if r['source'].startswith('source-')]
                queue={'id':f"print-{len(state['print_queue'])+1}",'name':state['project']+' print packet','task':job['id'],
                       'status':'Queued','printer':state['settings']['printer.selected'],'paper':state['settings']['printer.paper'],
                       'duplex':state['settings']['printer.duplex'],'pages':copy.deepcopy(pages),'documents':documents,
                       'order':state['settings']['printer.order'],
                       'proof_artifact':proof['id'],'proof_sha256':digest(proof['content'])}
                queue['payload_sha256']=digest({k:queue[k] for k in ['printer','paper','duplex','order','pages','documents']})
                state['print_queue'].append(queue)
                processing.update(print_job=queue['id'],submission_status='Queued',page_count=len(pages),payload_sha256=queue['payload_sha256'])
        elif kind in {"package", "backup", "replicate", "catalogue", "inventory"}:
            processing = {"entries": [{"name": r["name"], "sha256": digest(r["content"])} for r in resources],
                          "format": state["settings"]["archive.format"], "retention": state["settings"]["backup.retention"]}
            if kind=='backup':
                version=1+len([h for h in state['backup_history'] if h['job']==job['id']])
                versioned=state['settings']['backup.retention']=='versioned'
                name=job['name']+(f'-snapshot-v{version}.json' if versioned else '-snapshot.json')
                snapshot={'project':state['project'],'version':version,'resources':copy.deepcopy(resources)}
                extra={'backup_owner':job['id']} if versioned else {'generated_by':job['id']}
                retained=add_file(state,job['output'],name,'archive',json.dumps(snapshot,indent=2),**extra)
                state['backup_history'].append({'job':job['id'],'file':retained['id'],'version':version,'retention':state['settings']['backup.retention'],'sha256':digest(retained['content'])})
                processing.update(snapshot_file=retained['id'],snapshot_sha256=digest(retained['content']),snapshot_version=version)
        report = {"project": state["project"], "operation": job["kind"],
                  "inputs": [path(state, f["id"]) for f in inputs], "hashes": source_versions,
                  "settings": copy.deepcopy(state["settings"]),
                  "dependency_artifact": parent_job["artifact"] if parent_job else None,
                  "resources": resources, "processing": processing}
        if case['domain']=='media':
            report['derived_artifacts']=copy.deepcopy(prior_report.get('derived_artifacts',[]))
            if kind=='catalogue':
                report['derived_artifacts']=[{'id':manifest['id'],'name':manifest['name'],'content':manifest['content'],'sha256':digest(manifest['content'])}]
                for entry in catalogue['entries']:
                    preview=get_file(state,entry['preview_id'])
                    report['derived_artifacts'].append({'id':preview['id'],'name':preview['name'],'content':preview['content'],'sha256':digest(preview['content'])})
        if case['domain']=='build':
            report['derived_artifacts']=copy.deepcopy(prior_report.get('derived_artifacts',[]))
            if kind=='test':
                report['derived_artifacts']=[{'id':f['id'],'name':f['name'],'content':f['content'],'sha256':digest(f['content'])} for f in [prior_artifact,test_file]]
        if case['domain']=='evidence':
            report['derived_artifacts']=copy.deepcopy(prior_report.get('derived_artifacts',[]))
            if kind=='redact':report['derived_artifacts']=[{'id':f['id'],'name':f['name'],'content':f['content'],'sha256':digest(f['content'])} for f in redacted]
        artifact = add_file(state, job["output"], output_name,
                            "archive" if extension in {"zip", "tar"} else "report",
                            json.dumps(report, indent=2), provenance=report, generated_by=job["id"])
        if kind=='deliver' and case['domain']=='print':queue['delivery_artifact']=artifact['id']
        final_status="Scheduled" if kind=="deliver" and case["domain"]=="distribution" else "Completed"
        job.update(status=final_status, error=None, artifact=artifact["id"],
                   snapshot=digest(report), configuration=copy.deepcopy(state["settings"]))
        state["events"].append({"level": "Information", "source": job["name"], "message": f"{final_status}; wrote {path(state, artifact['id'])}"})
        return {"status": final_status, "artifact": artifact["id"]}
    raise ValueError("unknown operation")


def build_assertions(resources):
    import re
    code=next(r['content'] for r in resources if r['source']=='source-0')
    expected=json.loads(next(r['content'] for r in resources if r['source']=='source-1'))['test_expectations']
    project_match=re.search(r'export const project = (".*?");',code)
    revision_match=re.search(r'export const revision = (\d+);',code)
    actual={'project':json.loads(project_match.group(1)) if project_match else None,
            'revision':int(revision_match.group(1)) if revision_match else None}
    return [{'name':key,'expected':expected[key],'actual':actual[key],'passed':actual[key]==expected[key]} for key in ['project','revision']]


def ancestor_job(state,job,kind):
    seen=set()
    while job and job['id'] not in seen:
        if job['kind']==kind:return job
        seen.add(job['id'])
        job=next((j for j in state['jobs'] if j['name']==job['dependency']),None)
    raise ValueError('Required '+kind+' output is missing from the task chain.')


def selected_destination(state):
    device=next((d for d in state['devices'] if d['id']==state['settings']['distribution.destination'] and d['kind']=='Network storage'),None)
    if device is None:raise ValueError('Selected destination is unavailable.')
    return device


def selected_printer(state):
    printer=next((d for d in state['devices'] if d['id']==state['settings']['printer.selected'] and d['kind']=='Printer'),None)
    if printer is None:raise ValueError('Selected printer is unavailable.')
    return printer


def preview_dimensions(preset):
    return {'compact':(640,360),'review':(1280,720),'detail':(1920,1080)}[preset]


def media_catalogue(state,transcode_report):
    """Validate actual preview bytes before creating a source-to-preview index."""
    try:
        folder=get_file(state,transcode_report['processing']['preview_folder'])
        previews=[f for f in state['files'] if f['parent']==folder['id'] and f['kind']!='folder' and not f['deleted']]
        clips={r['source']:r for r in transcode_report['resources'] if r['name'].endswith('.mov')}
        captions={c['clip_id']:c['text'] for r in transcode_report['resources'] if r['source']=='source-2' for c in json.loads(r['content'])['captions']}
        if len(previews)!=len(clips):raise ValueError('A required preview is missing or an unexpected preview is present.')
        entries=[]
        seen=set()
        for preview in previews:
            resource=clips[preview['source']]
            source=json.loads(resource['content'])
            record=json.loads(preview['content'])
            expected={'clip_id':source['clip_id'],'session':source['session'],'caption':captions[source['clip_id']],
                      'source_hash':digest(resource['content']),'virtual_preview':True,
                      'width':transcode_report['processing']['width'],'height':transcode_report['processing']['height']}
            if record!=expected or preview['source'] in seen:raise ValueError('Preview metadata or source correspondence has changed.')
            seen.add(preview['source'])
            entries.append({'clip_id':source['clip_id'],'session':source['session'],'caption':record['caption'],
                'source_id':preview['source'],'source_name':resource['name'],'source_sha256':record['source_hash'],
                'preview_id':preview['id'],'preview_path':path(state,preview['id']),'preview_sha256':digest(preview['content']),
                'width':record['width'],'height':record['height']})
        sessions={e['session'] for e in entries}
        if len(sessions)!=1:raise ValueError('A catalogue must describe exactly one shoot session.')
        return {'session':sessions.pop(),'entries':sorted(entries,key=lambda e:e['clip_id'])}
    except (ValueError,KeyError,TypeError) as exc:
        raise ValueError('Media catalogue cannot be generated: '+str(exc))


def job_error(state, job, case):
    dependency = next((j for j in state["jobs"] if j["name"] == job["dependency"]), None)
    if job["dependency"] and (dependency is None or dependency["status"] != "Completed"):
        return "Dependency has not completed. Run the prerequisite job first."
    predecessors=TOOL_DEPENDENCIES.get(job["kind"],set())
    if case.get("id")=="OS-H-01":
        predecessors=set(predecessors)|({None} if job["kind"]=="validate" else {"validate"} if job["kind"]=="package" else set())
    prior_kind=dependency["kind"] if dependency else None
    if prior_kind not in predecessors:
        return "The dependency output is not compatible with this tool. Inspect the task configuration and prerequisite artifact."
    if dependency:
        try:
            artifact = get_file(state, dependency["artifact"])
        except ValueError:
            return "Dependency output is missing. Reset and rerun the prerequisite task."
        if digest(artifact.get("provenance", {})) != dependency.get("snapshot") or artifact["content"] != json.dumps(artifact.get("provenance", {}), indent=2):
            return "Dependency output has been changed. Reset and rerun the prerequisite task."
        if dependency['kind']=='backup':
            try:
                report=artifact['provenance']
                snapshot=get_file(state,report['processing']['snapshot_file'])
                if digest(snapshot['content'])!=report['processing']['snapshot_sha256'] or json.loads(snapshot['content'])['resources']!=report['resources']:
                    return 'Backup snapshot differs from its manifest. Repair or regenerate the backup before recovery.'
            except (ValueError,KeyError,TypeError):return 'Backup snapshot is missing or invalid. Regenerate the backup before recovery.'
    files = [f for f in state["files"] if f["parent"] == job["input"] and not f["deleted"] and f["kind"] != "folder"]
    if not files:
        return "Input folder has no files."
    if (job['kind']=='restore' and case['domain'] in {'backup','restoration'}) or (job['kind']=='migrate' and case['domain']=='migration'):
        if job['input']==job['output']:
            return 'Restore into a separate recovery folder to preserve the working input.'
        for f in files:
            name=get_file(state,f.get('source',f['id']))['name']
            if any(x['parent']==job['output'] and x['name']==name and not x['deleted'] for x in state['files']):
                return f"{job['kind'].capitalize()} name conflict: {name} already exists. Preserve the existing version and choose a separate destination folder."
    if job["kind"] == "validate":
        import csv
        try:
            for f in files:
                if f["name"].endswith(".json"):
                    json.loads(f["content"])
                elif f["name"].endswith(".csv"):
                    rows=list(csv.reader(f["content"].splitlines()))
                    if not rows or any(len(row)!=len(rows[0]) for row in rows[1:]):
                        return "CSV columns are inconsistent. Repair the working data before retrying validation."
        except ValueError:
            return "A JSON document is malformed. Repair the working data before retrying validation."
    if job["kind"] in {"build", "transcode", "migrate", "compact", "restore"} and not state["settings"]["tools.enabled"]:
        return "Processing tools are disabled. Enable tools in Settings > Apps > Processing."
    if job['kind']=='build' and not state['settings']['tools.compiler']:
        return 'Compiler component is unavailable. Enable the compiler in Settings > Apps > Processing, then retry the build.'
    if job['kind']=='sign' and not state['settings']['tools.signer']:
        return 'Signing provider is unavailable. Enable the signing provider in Settings > Apps > Processing, then retry signing.'
    if job["kind"] == "build" and case["domain"] == "build":
        configuration = next((f for f in files if f.get("source") == "source-1"), None)
        try:
            ready = configuration is not None and json.loads(configuration["content"]).get("build_ready") is True
        except (ValueError, TypeError):
            ready = False
        if not ready:
            return "Build configuration error: modules.json requires build_ready=true. Repair the working copy, then revalidate the input."
    if job['kind']=='test':
        try:build_assertions([{'source':f.get('source',f['id']),'content':f['content']} for f in files])
        except (ValueError,KeyError,TypeError,StopIteration):
            return 'Test configuration is incomplete. Provide staged source exports and modules.json test_expectations.'
    if case['domain']=='build' and job['kind'] in {'package','verify','audit','deliver'}:
        try:
            tested=ancestor_job(state,dependency,'test')
            result=get_file(state,tested['artifact'])['provenance']['processing']
            document=get_file(state,result['test_file'])
            if not result['passed'] or not all(a['passed'] for a in result['assertions']) or digest(document['content'])!=result['test_sha256']:
                raise ValueError('Test results are missing, failed or changed.')
            if digest(get_file(state,result['build_artifact'])['content'])!=result['build_sha256']:
                raise ValueError('The tested build has changed.')
        except (ValueError,KeyError,TypeError) as exc:return 'Build release gate failed: '+str(exc)
    if job['kind']=='build' and case['domain']=='release':
        try:
            config=json.loads(next(f['content'] for f in files if f.get('source')=='source-2'))
            source=next((f for f in files if path(state,f['id'])==config['entry'] and f.get('source')=='source-0'),None)
            if source is None:
                return 'Build entry not found: '+config['entry']+'. Repair config.json to point to the staged application, then reset and rerun validation.'
            notes=next(f['content'] for f in files if f.get('source')=='source-1')
            version=config['release_version']
            if (notes.strip().splitlines() or [''])[0].strip() != 'Version: '+version or f'export const releaseVersion = "{version}";' not in source['content']:
                return 'Release version mismatch: application, config.json and release notes must describe the same release.'
        except (ValueError,KeyError,StopIteration,TypeError):
            return 'Release configuration is incomplete. Inspect config.json and release notes.'
    if job['kind'] in {'layout','proof'}:
        printer=selected_printer(state)
        if not printer['connected']:return printer['name']+' is disconnected.'
        if state['settings']['printer.paper'] not in printer.get('paper_sizes',['A4','Letter']):
            return printer['name']+' does not support '+state['settings']['printer.paper']+'. Choose a compatible printer in Settings > Bluetooth & devices > Printing.'
        if state['settings']['printer.duplex'] and not printer.get('duplex_supported',True):
            return printer['name']+' does not support duplex printing. Choose a compatible printer in Settings > Bluetooth & devices > Printing.'
        if job['kind']=='proof':
            layout=get_file(state,dependency['artifact'])['provenance']['processing']
            if any(layout.get(key)!=state['settings']['printer.'+key] for key in ['paper','duplex','order']) or layout.get('printer')!=printer['id']:
                return 'Printer settings changed after layout. Reset and rerun the layout before proofing.'
    if job['kind']=='proof':
        layout=get_file(state,dependency['artifact'])['provenance']['processing']
        limit=layout.get('page_line_limit',40)
        overflow=next((page for page in layout.get('pages',[]) if page['lines']>limit),None)
        if overflow:
            return f"Proof page overflow: {overflow['name']}, page {overflow['page']} has {overflow['lines']} lines; capacity is {limit}. Insert a page break in the working document, then reset and rerun the upstream layout."
    if job['kind']=='deliver' and case['domain']=='print':
        try:
            proof_job=ancestor_job(state,dependency,'proof')
            proof=get_file(state,proof_job['artifact'])
            p=proof['provenance']
            if proof_job['status']!='Completed' or digest(p)!=proof_job['snapshot'] or proof['content']!=json.dumps(p,indent=2):
                raise ValueError('The proof receipt is missing or changed.')
            if any(digest(get_file(state,fid)['content'])!=value for fid,value in p['hashes'].items()):
                raise ValueError('Documents changed after proof. Regenerate the layout and proof before submission.')
            profile=p['processing']
            printer=selected_printer(state)
            if not printer['connected']:raise ValueError('Selected printer is disconnected.')
            if profile['printer']!=printer['id'] or any(profile[key]!=state['settings']['printer.'+key] for key in ['paper','duplex','order']):
                raise ValueError('Print settings changed after proof.')
        except (ValueError,KeyError,TypeError) as exc:return 'Print submission failed: '+str(exc)
    if job["kind"] == "transcode":
        if not any(f.get('source')=='source-2' for f in files):
            return 'Caption sidecar is missing. Download current-session captions in Transfer Manager, import them into the working folder, then reset and rerun validation.'
        try:
            media={json.loads(f["content"])["clip_id"] for f in files if f["name"].endswith(".mov")}
            caption_file=next(f for f in files if f.get("source")=="source-2")
            captions=json.loads(caption_file["content"])["captions"]
            if {c["clip_id"] for c in captions}!=media or len(captions)!=len(media):
                return "Caption IDs do not match the imported takes. Repair the caption sidecar before creating previews."
        except (ValueError,KeyError,StopIteration,TypeError):
            return "Media or caption sidecar is malformed."
    if job['kind']=='catalogue' and case['domain']=='media':
        try:media_catalogue(state,get_file(state,dependency['artifact'])['provenance'])
        except (ValueError,KeyError,TypeError) as exc:return str(exc)
    if job['kind'] in {'verify','audit','deliver'} and case['domain']=='media':
        try:
            derived=get_file(state,dependency['artifact'])['provenance']['derived_artifacts']
            if not derived:raise ValueError('No catalogue or preview snapshots are available.')
            for item in derived:
                actual=get_file(state,item['id'])
                if actual['content']!=item['content'] or digest(actual['content'])!=item['sha256']:
                    raise ValueError(actual['name']+' changed after catalogue generation.')
        except (ValueError,KeyError,TypeError) as exc:
            return 'Media verification failed: '+str(exc)+' Repair the derived files or regenerate the catalogue before retrying.'
    if case['domain']=='distribution' and job['kind'] in {'dry-run','replicate','deliver'}:
        destination=selected_destination(state)
        if not destination['connected']:return destination['name']+' is disconnected. Reconnect the share before retrying.'
        if destination.get('access','read-write')!='read-write':return 'Destination access denied: '+destination['name']+' is read-only. Configure write access in Device Manager and repeat the dry run.'
        if job['kind'] in {'replicate','deliver'}:
            try:
                check=ancestor_job(state,dependency,'dry-run')
                report=get_file(state,check['artifact'])['provenance']
                current=[{'name':f['name'],'content':f['content'],'source':f.get('source',f['id'])} for f in files]
                if report['processing']['destination']!=destination['id'] or report['processing']['payload_sha256']!=digest(report['resources']) or digest(current)!=digest(report['resources']):
                    return 'Destination or payload differs from the dry-run receipt. Repeat the dry check before staging or scheduling.'
            except (ValueError,KeyError,TypeError):return 'A valid destination dry-run receipt is required.'
    if job["kind"] == "redact" and not state["settings"]["privacy.redaction"]:
        return "Redaction is disabled. Enable privacy filtering before processing evidence."
    if case['domain']=='evidence' and job['kind'] in {'package','verify','audit','deliver'}:
        try:
            redaction=ancestor_job(state,dependency,'redact')
            report=get_file(state,redaction['artifact'])['provenance']
            method=report['processing']['method']
            for resource in report['resources']:
                if resource['source'] not in {'source-0','source-1'}:continue
                originals={r['event_id']:r for r in map(json.loads,get_file(state,resource['source'])['content'].splitlines())}
                for record in map(json.loads,resource['content'].splitlines()):
                    original=originals[record['event_id']]
                    expected=domain_checks.redact_record(original,state['sensitive_fields'],method)
                    remaining=[field for field in state['sensitive_fields'] if (field in record)!=(field in expected) or record.get(field)!=expected.get(field)]
                    if remaining:return 'Personal fields remain: '+', '.join(remaining)+'. Broaden the Privacy filtering scope and regenerate redacted copies.'
            for item in report['derived_artifacts']:
                if get_file(state,item['id'])['content']!=item['content']:return 'Redacted evidence copy changed. Regenerate redaction before packaging.'
        except (ValueError,KeyError,TypeError):return 'Redacted evidence copies are missing or invalid.'
    if job["kind"] in {"verify","audit"}:
        current=dependency
        while current:
            if current["kind"]=="sign":
                signed=get_file(state,current["artifact"])["provenance"]["processing"]
                original=get_file(state,signed["signed_artifact"])
                expected=hmac.new(b'OS-ICL virtual signing authority',original["content"].encode(),hashlib.sha256).hexdigest()
                if not hmac.compare_digest(signed["signature"],expected):
                    return "Build signature does not match its signed artifact. Rebuild and sign the corrected output."
            current=next((j for j in state["jobs"] if j["name"]==current["dependency"]),None)
    return None


def reference(case, state, policy, plan_variant='standard'):
    """Trusted authoring actions, never returned on an agent-facing route."""
    actions = []
    if plan_variant not in {'standard','configure-first','reverse-sources'}:raise ValueError('Unknown authoring plan variant.')
    attempts = []
    selected_sources=[domain_checks.required_source(state,case,i) for i in range(4)]
    selected_ids={f['id'] for f in selected_sources}
    owners=[p for p in state['processes'] if selected_ids.intersection(p['locks']) and p['status']=='Running'] if case['recovery']=='lock' else []
    selected_source=next((f for f in selected_sources if any(f['id'] in p['locks'] for p in owners)),selected_sources[0])
    owner_paused=bool(owners)
    if owner_paused:
        attempts.append({"op": "copy", "target": selected_source['id'], "parent": "documents"})
        for owner in owners:actions.append({"op": "process", "target": owner['id'], "status": "Paused"})
    if case['domain']=='research':
        actions=[{'op':'properties','target':f['id']} for f in state['files'] if f.get('resource_key')]+actions
    if case["recovery"] in {"device", "printer", "destination"}:
        target={"device": "camera", "printer": "printer", "destination": "destination"}[case["recovery"]]
        if not next(d for d in state["devices"] if d["id"]==target)["connected"]:
            if case["recovery"] == "device":
                attempts.append({"op": "copy", "target": "source-0", "parent": "documents"})
            actions.append({"op": "device", "target": target, "connected": True})
    if case["recovery"] == "download":
        if not get_file(state,"source-0").get("downloaded",True):
            attempts.append({"op": "copy", "target": "source-0", "parent": "documents"})
        endpoint=next((d for d in state['devices'] if d['id']=='field-relay'),None)
        if endpoint and not endpoint['connected']:
            actions.append({'op':'download','target':state['transfers'][0]['id']})
            actions.append({'op':'device','target':endpoint['id'],'connected':True})
        actions += [{"op": "download", "target": t["id"]} for t in state["transfers"] if t["status"]!="Completed"]
    if case['domain']=='restoration':
        actions=[{'op':'properties','target':f['id']} for f in state['files'] if f.get('snapshot_status')]+actions
    # Resolve IDs by applying the same reducer to a private planning graph.
    simulated = copy.deepcopy(state)
    for a in actions:
        mutate(simulated, a, case)
    def append(a):
        result = mutate(simulated, a, case)
        actions.append(a)
        return result
    working = append({"op": "mkdir", "parent": "project", "name": policy["workspace"]})
    if case['domain']=='media':
        working=append({'op':'mkdir','parent':working,'name':json.loads(get_file(state,'source-0')['content'])['session']})
    delivery = append({"op": "mkdir", "parent": "project", "name": policy["delivery"]})
    reports = append({"op": "mkdir", "parent": working, "name": "Reports"})
    copies = {}
    missing_sidecar=case['domain']=='media' and not get_file(state,'source-2').get('downloaded',True)
    source_order=range(3,-1,-1) if plan_variant=='reverse-sources' else range(4)
    for i in source_order:
        if missing_sidecar and i==2:continue
        original = domain_checks.required_source(state,case,i)
        if case['domain']=='evidence' and i in [0,1]:
            copied=append({'op':'export-log','target':original['id'],'parent':working,'name':original['name'],
                           'start':state['incident']['start'],'end':state['incident']['end']})
        else:copied = append({"op": "copy", "target": original["id"], "parent": working})
        copies[i] = copied
        append({"op": "rename", "target": copied, "name": policy["prefix"] + original["name"]})
    for i in range(4):
        if i not in copies:continue
        if case['domain']=='print' and i==1:continue
        new_content = domain_checks.staged_content(state, case, policy, i)
        if new_content != get_file(simulated, copies[i])["content"]:
            append({"op": "write", "target": copies[i], "content": new_content})
    index = append({"op": "create-document", "parent": working, "name": "handoff-index.txt"})
    # Individual edits are purposeful: header plus entries, mirroring actual
    # document editing. One save remains one mutation, not keystroke inflation.
    content = f"Project: {state['project']}\n" + "\n".join(policy["prefix"] + domain_checks.required_source(state,case,i)["name"] for i in range(4))
    if case['domain']=='research':
        content=f"Project: {state['project']}\n"+'\n'.join(policy['prefix']+source['name']+f" | revision={source['revision']}" for source in [domain_checks.required_source(state,case,i) for i in range(4)])
    append({"op": "write", "target": index, "content": content})
    for key, value in [("archive.format", policy["format"]), ("verification.mode", policy["verify"]),
                       ("scheduler.trigger", policy["schedule"]), ("backup.retention", policy["retention"])]:
        append({"op": "setting", "key": key, "value": value})
    if case["recovery"] != "dependency" and any(k in {"build", "transcode", "migrate", "compact", "restore"} for k in case["pipeline"]):
        append({"op": "setting", "key": "tools.enabled", "value": True})
    if case["domain"] == "evidence":
        append({"op": "setting", "key": "privacy.redaction", "value": True})
        append({'op':'setting','key':'privacy.method','value':policy['redaction']})
    if case["domain"] == "print":
        append({"op": "setting", "key": "printer.duplex", "value": True})
        append({'op':'setting','key':'printer.paper','value':state['print_request']['paper']})
        append({'op':'setting','key':'printer.order','value':policy['print_order']})
    if case['domain']=='distribution':
        append({'op':'setting','key':'distribution.destination','value':next(d['id'] for d in state['devices'] if d.get('recipient')==state['distribution_request']['recipient'])})
    if case['domain']=='backup':
        append({'op':'setting','key':'backup.scope','value':'sources' if policy['retention']=='versioned' else 'all'})
    if case['domain']=='media':append({'op':'setting','key':'media.preview','value':policy['preview']})
    previous = ""
    prior_jobs=[]
    for i, kind in enumerate(case["pipeline"]):
        name = f"{i+1:02}-{kind}"
        job = append({"op": "create-job", "name": name, "kind": kind, "input": working,
                      "output": 'migration-target' if kind=='migrate' and case['domain']=='migration' else 'recovery' if kind=='restore' and case['domain'] in {'backup','restoration'} else delivery if kind == "deliver" else reports,
                      "dependency": previous, "trigger": policy["schedule"]})
        if case["recovery"] == "dependency" and kind == "build" and not simulated["settings"]["tools.enabled"]:
            append({"op": "run-job", "target": job})
            append({"op": "setting", "key": "tools.enabled", "value": True})
        if case['domain']=='release' and kind in {'build','sign'}:
            component='tools.compiler' if kind=='build' else 'tools.signer'
            if not simulated['settings'][component]:
                append({'op':'run-job','target':job})
                append({'op':'setting','key':component,'value':True})
        if case["domain"] == "build" and kind == "build" and not json.loads(get_file(simulated,copies[1])["content"]).get("build_ready"):
            append({"op": "run-job", "target": job})
            corrected = json.loads(get_file(simulated, copies[1])["content"])
            corrected["build_ready"] = True
            append({"op": "write", "target": copies[1], "content": json.dumps(corrected, indent=2)})
            for prior in reversed(prior_jobs):
                append({"op": "update-job", "target": prior})
            for prior in prior_jobs:
                append({"op": "run-job", "target": prior})
        if case['domain']=='build' and kind=='test':
            config=json.loads(get_file(simulated,copies[1])['content'])
            expected={'project':state['project'],'revision':get_file(state,'source-0')['revision']}
            if config['test_expectations']!=expected:
                append({'op':'run-job','target':job})
                config['test_expectations']=expected
                append({'op':'write','target':copies[1],'content':json.dumps(config,indent=2)})
                for prior in reversed(prior_jobs):append({'op':'update-job','target':prior})
                for prior in prior_jobs:append({'op':'run-job','target':prior})
        if case['domain']=='release' and kind=='build' and json.loads(get_file(simulated,copies[2])['content'])['entry']!=path(simulated,copies[0]):
            append({'op':'run-job','target':job})
            corrected=json.loads(get_file(simulated,copies[2])['content'])
            corrected['entry']=path(simulated,copies[0])
            append({'op':'write','target':copies[2],'content':json.dumps(corrected,indent=2)})
            for prior in reversed(prior_jobs):append({'op':'update-job','target':prior})
            for prior in prior_jobs:append({'op':'run-job','target':prior})
        if missing_sidecar and kind=='transcode':
            append({'op':'run-job','target':job})
            append({'op':'download','target':'download-captions'})
            copied=append({'op':'copy','target':'source-2','parent':working})
            copies[2]=copied
            append({'op':'rename','target':copied,'name':policy['prefix']+get_file(state,'source-2')['name']})
            append({'op':'write','target':copied,'content':domain_checks.staged_content(state,case,policy,2)})
            for prior in reversed(prior_jobs):append({'op':'update-job','target':prior})
            for prior in prior_jobs:append({'op':'run-job','target':prior})
        if case['domain']=='print' and kind=='layout':
            printer=selected_printer(simulated)
            if not printer.get('duplex_supported',True) or simulated['settings']['printer.paper'] not in printer.get('paper_sizes',['A4','Letter']):
                append({'op':'run-job','target':job})
                append({'op':'device','target':'production-printer','connected':True})
                append({'op':'setting','key':'printer.selected','value':'production-printer'})
        if case['domain']=='print' and kind=='proof':
            layout_task=next(j for j in simulated['jobs'] if j['name']==previous)
            layout=get_file(simulated,layout_task['artifact'])['provenance']['processing']
            if any(page['lines']>layout['page_line_limit'] for page in layout['pages']):
                append({'op':'run-job','target':job})
                append({'op':'write','target':copies[1],'content':domain_checks.staged_content(state,case,policy,1)})
                for prior in reversed(prior_jobs):append({'op':'update-job','target':prior})
                for prior in prior_jobs:append({'op':'run-job','target':prior})
        if case['domain']=='distribution' and kind=='dry-run' and selected_destination(simulated).get('access')!='read-write':
            append({'op':'run-job','target':job})
            append({'op':'device-access','target':selected_destination(simulated)['id'],'access':'read-write'})
        if case['domain']=='backup' and kind=='compare' and not simulated['settings']['backup.include-text']:
            append({'op':'run-job','target':job})
            append({'op':'setting','key':'backup.include-text','value':True})
            for prior in reversed(prior_jobs):append({'op':'update-job','target':prior})
            for prior in prior_jobs:append({'op':'run-job','target':prior})
        if case['domain']=='evidence' and kind=='package' and len(state['sensitive_fields'])>1 and simulated['settings']['privacy.scope']=='contact':
            append({'op':'run-job','target':job})
            append({'op':'setting','key':'privacy.scope','value':'personal'})
            for prior in reversed(prior_jobs):append({'op':'update-job','target':prior})
            for prior in prior_jobs:append({'op':'run-job','target':prior})
        outcome=append({"op": "run-job", "target": job})
        if kind in {'restore','migrate'} and isinstance(outcome,dict) and outcome.get('status')=='Failed':
            destination=append({'op':'mkdir','parent':'project','name':policy['workspace']+(' Migration' if kind=='migrate' else ' Recovery')})
            append({'op':'update-job','target':job,'output':destination})
            append({'op':'run-job','target':job})
        if kind == "verify-backup":
            caches=[f for f in simulated['files'] if f.get('regenerable') and not f['deleted']]
            for candidate in caches+[get_file(simulated,'pinned-cache-notes')]:append({'op':'properties','target':candidate['id']})
            owners=[p for p in simulated['processes'] if set(p['locks']).intersection(f['id'] for f in caches)]
            prior_states={p['id']:p['status'] for p in owners}
            for owner in owners:
                if owner['status']=='Running':append({'op':'process','target':owner['id'],'status':'Paused'})
            for cache in caches:
                append({"op":"delete","target":cache["id"]})
            for owner in owners:
                if prior_states[owner['id']]=='Running':append({'op':'process','target':owner['id'],'status':'Running'})
            append({"op":"probe","kind":"storage","target":"project"})
        if kind in {"cache", "migrate"}:
            artifact = get_file(simulated, next(j for j in simulated["jobs"] if j["id"] == job)["artifact"])
            if kind=='cache':append({'op':'setting','key':'network.offline','value':True})
            if kind=='cache' and not simulated['settings'].get('cache.contacts',True):
                # The first offline test intentionally exercises the installed
                # incomplete scope. Failed probes make no filesystem changes.
                actions.append({'op':'probe','kind':'offline','target':artifact['provenance']['processing']['materialized_folder']})
                append({'op':'setting','key':'cache.contacts','value':True})
                append({'op':'update-job','target':job})
                append({'op':'run-job','target':job})
                artifact=get_file(simulated,next(j for j in simulated['jobs'] if j['id']==job)['artifact'])
            append({"op":"probe", "kind":"offline" if kind == "cache" else "workspace",
                    "target":artifact["provenance"]["processing"]["materialized_folder"]})
        if kind=="restore" and case["domain"]=="restoration":
            artifact=get_file(simulated,next(j for j in simulated["jobs"] if j["id"]==job)["artifact"])
            restored=artifact["provenance"]["processing"]["materialized_folder"]
            snapshot=json.loads(get_file(state,"source-0")["content"])
            for task in snapshot["scheduled_tasks"]:
                destination=next((f['id'] for f in simulated['files'] if f['parent']==restored and f['name']==task['output'] and f['kind']=='folder' and not f['deleted']),None)
                if destination is None:destination=append({'op':'mkdir','parent':restored,'name':task['output']})
                existing=next((j for j in simulated['jobs'] if j['name']==task['name']),None)
                if existing:
                    append({'op':'update-job','target':existing['id'],'input':restored,'output':destination,'dependency':'','trigger':task['trigger']})
                else:
                    append({"op":"create-job","name":task["name"],"kind":task["kind"],"input":restored,
                            "output":destination,"dependency":"","trigger":task["trigger"]})
            append({"op":"probe","kind":"restoration","target":restored})
        previous = name
        prior_jobs.append(job)
    if owner_paused:
        for owner in owners:append({"op": "process", "target": owner['id'], "status": "Running"})
    if plan_variant=='configure-first':
        common={'archive.format','verification.mode','scheduler.trigger','backup.retention'}
        configuration=[a for a in actions if a['op']=='setting' and a['key'] in common]
        remaining=[a for a in actions if not (a['op']=='setting' and a['key'] in common)]
        return attempts+configuration+remaining
    return attempts + actions


def evaluate(episode):
    if episode.get('task36'):
        import judge36
        return judge36.evaluate(episode)
    state, initial = episode["state"], episode["initial"]
    policy, case = CONVENTIONS[episode["convention"]], episode["case"]
    checks = {f"resource_{i}": False for i in range(4)}
    checks.update({"index": False, "delivery": False, "verification_receipt": False,
                   "archive.format": False, "verification.mode": False,
                   "scheduler.trigger": False, "backup.retention": False})
    for kind in case["pipeline"]:
        for prefix in ["job_", "provenance_", "output_location_"]:
            checks[prefix + kind] = False
        if kind in {"restore", "migrate", "cache"}:
            checks["materialized_" + kind] = False
    try:
        working = resolve_folder(state, policy["workspace"])
        if case['domain']=='media':
            working=resolve_folder(state,json.loads(get_file(initial,'source-0')['content'])['session'],working)
        delivery = resolve_folder(state, policy["delivery"])
        reports = resolve_folder(state, "Reports", working)
        working_files = [f for f in state["files"] if f["parent"] == working and not f["deleted"]]
        for i in range(4):
            src = domain_checks.required_source(initial,case,i)
            checks[f"resource_{i}"] = any(f["name"] == policy["prefix"] + src["name"] and
                f.get("source") == src["id"] and f.get("source_hash") == digest(src["content"]) and
                domain_checks.content_matches(state,initial,case,policy,i,f) for f in working_files)
        checks["index"] = any(f["name"] == "handoff-index.txt" and state["project"] in f["content"] and
            all(policy["prefix"] + domain_checks.required_source(initial,case,i)["name"] in f["content"] for i in range(4)) for f in working_files)
        if case['domain']=='research':
            checks['research_index_revisions']=any(f['name']=='handoff-index.txt' and all(any(policy['prefix']+src['name'] in line and f"revision={src['revision']}" in line for line in f['content'].splitlines()) for src in [domain_checks.required_source(initial,case,i) for i in range(4)]) for f in working_files)
        jobs = [j for j in state["jobs"] if j["status"] == "Completed" or
                case["domain"]=="distribution" and j["kind"]=="deliver" and j["status"]=="Scheduled"]
        chain = []
        for kind in case["pipeline"]:
            prior = chain[-1]["name"] if chain else ""
            match = next((j for j in jobs if j["kind"] == kind and j["input"] == working and
                          j["dependency"] == prior and j["trigger"] == policy["schedule"]), None)
            checks[f"job_{kind}"] = match is not None
            if match is None:
                break
            # Ensure the output existed when verified and remains intact now.
            artifact = get_file(state, match["artifact"])
            p = artifact.get("provenance", {})
            checks[f"provenance_{kind}"] = (digest(p) == match["snapshot"] and
                artifact["content"] == json.dumps(p, indent=2) and
                all(digest(get_file(state, identifier)["content"]) == value for identifier, value in p.get("hashes", {}).items()))
            expected_output=match['output'] if (kind=='restore' and case['domain'] in {'backup','restoration'}) or (kind=='migrate' and case['domain']=='migration') else delivery if kind == "deliver" else reports
            checks[f"output_location_{kind}"] = artifact["parent"] == expected_output
            if p.get("processing", {}).get("materialized_folder"):
                folder = p["processing"]["materialized_folder"]
                materialized = [f for f in state["files"] if f["parent"] == folder and not f["deleted"]]
                checks[f"materialized_{kind}"] = all(any(f["name"] == r["name"] and f["content"] == r["content"] for f in materialized) for r in p["resources"])
            if kind == "verify":
                previous_artifact = get_file(state, p["processing"]["verified_artifact"])
                checks["verification_receipt"] = p["processing"]["sha256"] == digest(previous_artifact["content"])
            if kind == "audit":
                records=p["processing"].get("audit_trail",[])
                checks["audit_trail_integrity"]=len(records)==len(chain) and all(
                    digest(get_file(state,r["artifact"])["content"])==r["sha256"] for r in records)
            if kind == "sign":
                signed=p["processing"]
                original=get_file(state,signed["signed_artifact"])
                signature=hmac.new(b'OS-ICL virtual signing authority',original["content"].encode(),hashlib.sha256).hexdigest()
                checks["build_signature_valid"]=hmac.compare_digest(signed["signature"],signature)
            chain.append(match)
        checks["delivery"] = len(chain) == len(case["pipeline"]) and get_file(state, chain[-1]["artifact"])["parent"] == delivery
        for key, value in [("archive.format", policy["format"]), ("verification.mode", policy["verify"]),
                           ("scheduler.trigger", policy["schedule"]), ("backup.retention", policy["retention"])]:
            checks[key] = state["settings"][key] == value and all(j.get("configuration", {}).get(key) == value for j in chain)
    except ValueError:
        checks["workspace"] = False
    protected = [f for f in initial["files"] if not f.get("regenerable")]
    checks["preserved_originals"] = all(any(f["id"] == src["id"] and not f["deleted"] and
        all(f[k] == src[k] for k in ["parent", "name", "content",'revision']) for f in state["files"]) for src in protected)
    checks["no_failed_jobs"] = all(j["status"] != "Failed" for j in state["jobs"])
    if case["recovery"] == "lock":
        checks['owner_restored']=all(any(p['id']==original['id'] and p['status']==original['status'] for p in state['processes']) for original in initial['processes'])
    checks.update(domain_checks.checks(state, initial, case, get_file, digest, media_catalogue, policy['redaction']))
    if case['domain']=='evidence':
        checks['redaction_method_learned']=state['settings']['privacy.method']==policy['redaction'] and all(j['configuration'].get('privacy.method')==policy['redaction'] for j in state['jobs'] if j['kind']=='redact' and j['status']=='Completed')
    if case['domain']=='backup':
        expected_scope='sources' if policy['retention']=='versioned' else 'all'
        checks['backup.scope']=state['settings']['backup.scope']==expected_scope and all(j['configuration'].get('backup.scope')==expected_scope for j in state['jobs'] if j['kind']=='backup' and j['status']=='Completed')
    if case['domain']=='media':
        checks['media.preview']=False
        try:
            task=next(j for j in state['jobs'] if j['kind']=='transcode' and j['status']=='Completed')
            info=get_file(state,task['artifact'])['provenance']['processing']
            checks['media.preview']=(info['width'],info['height'])==preview_dimensions(policy['preview']) and info['preset']==policy['preview']
        except (ValueError,KeyError,StopIteration):pass
    if case['domain']=='print':
        checks['printer.order']=False
        try:
            layout=next(j for j in state['jobs'] if j['kind']=='layout' and j['status']=='Completed')
            info=get_file(state,layout['artifact'])['provenance']['processing']
            checks['printer.order']=info['order']==policy['print_order']
        except (ValueError,KeyError,StopIteration):pass
    return {"success": all(checks.values()), "goal_success": all(checks.values()),
            "rule_compliance": all(checks.get(k, False) for k in ["index", "archive.format", "verification.mode", "scheduler.trigger", "backup.retention"]) and checks.get('backup.scope',True) and checks.get('media.preview',True) and checks.get('printer.order',True) and all(checks.get('job_'+kind,False) for kind in case['pipeline']),
            "side_effect_free": checks["preserved_originals"], "checks": checks,
            "partial_credit": round(sum(checks.values()) / max(1, len(checks)), 4),
            "agent_steps": len(episode["events"]), "reference_mutations": len(episode["reference"]),
            "state_hash": digest(state), "benchmark_version": VERSION}


def public(episode, mode="evaluation"):
    if episode.get('task36'):
        import tasks36
        return tasks36.public(episode, mode)
    public_case = {k: v for k, v in episode["case"].items() if k not in {"pipeline", "recovery"}}
    payload = {"benchmark_version": VERSION, "case": public_case,
               "seed": episode["seed"], "state": copy.deepcopy(episode["state"]),
               "state_hash": digest(episode["state"])}
    if mode == "demo":
        payload["case"]["pipeline"] = copy.deepcopy(episode["case"]["pipeline"])
        payload["recorder_brief"] = {"convention": copy.deepcopy(CONVENTIONS[episode["convention"]]),
                                    "reference": copy.deepcopy(episode["reference"])}
    return payload


def generate(case_id="OS-E-01", convention=0, seed=42, plan_variant="standard"):
    """Generate only tasks in the current 36-task catalogue."""
    import tasks36
    if case_id not in tasks36.CASE_BY_ID:
        raise ValueError("Retired or unknown task; use the current 36-task catalogue")
    return tasks36.generate(case_id, convention, seed, plan_variant)
