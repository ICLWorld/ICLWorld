"""Immutable dataset media and R initial states for the self-hosted backend."""
import os,json,hashlib
from pathlib import Path
ROOT=Path(os.environ["ICLWORLD_DATASET"])
def read(name): return json.loads((ROOT/"metadata"/name).read_text())
def media():
 return [dict(x, video=x["video"], run_id=x["id"], approved=True,historical=False,recording_actor="human_browser",created_at=0,visual_review="passed") for x in read("os-demonstrations.json")], ""
def video(entry):
 p=(ROOT/entry["video"]).resolve()
 if not p.is_relative_to(ROOT.resolve()) or hashlib.sha256(p.read_bytes()).hexdigest()!=entry["sha256"]: raise ValueError("Dataset media checksum mismatch")
 return p
def replay(body):
 rows=[x for x in read("web-replays.json") if str(x["task_id"])==str(body.task_id) and x["variant"]==body.variant and (not body.replay_run_id or x["run_id"]==body.replay_run_id) and x["epoch"]==body.replay_epoch and x["example"]==body.replay_example]
 if len(rows)!=1: raise ValueError("No unique frozen replay")
 r=rows[0];initial=json.loads((ROOT/r["initial"]).read_text())
 if hashlib.sha256(json.dumps(initial,sort_keys=True).encode()).hexdigest()!=r["initial_sha256"]:raise ValueError("Replay checksum mismatch")
 return initial,{k:r[k] for k in ("run_id","epoch","example","seed","initial_sha256","video_sha256")}
