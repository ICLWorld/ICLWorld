"""Frozen GUI tools plus an invisible, pre-action context checkpoint."""
import argparse
import json
from pathlib import Path
import os
from vic_sdk.computer_mcp import Computer, make_server

class CheckpointComputer(Computer):
    def act(self, *args, **kwargs):
        # The model's next operation cannot race ahead of its recorded request.
        # This does not add a model-visible rule-report or diagnostic tool.
        root=Path(self.config.get('capture_root',str(self.output)))
        source = root/'candidate-context.json'
        target = root/'video-checkpoint.json'
        if not target.exists() and source.exists():
            try:os.link(source, target)
            except FileExistsError:pass
        return super().act(*args, **kwargs)

def main():
    p=argparse.ArgumentParser();p.add_argument('--config',type=Path,required=True)
    p.add_argument('--capture-root',required=True)
    args=p.parse_args();cfg=json.loads(args.config.read_text());cfg['capture_root']=args.capture_root
    if cfg.get('rule_diagnostic'):
        raise ValueError('Open-ended rule diagnosis is disabled in matrix v2')
    c=CheckpointComputer(cfg)
    try:make_server(c).run(transport='stdio')
    finally:c.http.close()

if __name__=='__main__':main()
