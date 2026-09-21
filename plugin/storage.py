"""Local-only archival originals and non-content JSONL telemetry."""
import hashlib
import json
import os
from pathlib import Path
import uuid

class Archive:
    def __init__(self,path): self.path=str(path)
    def save(self,messages):
        p=Path(self.path); p.mkdir(parents=True,exist_ok=True,mode=0o700)
        data=json.dumps(messages,ensure_ascii=False,allow_nan=False).encode()
        name=hashlib.sha256(data).hexdigest()+'-'+uuid.uuid4().hex+'.json'
        target=p/name
        fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'wb') as f:
            f.write(data); f.flush(); os.fsync(f.fileno())
        return name

class Metrics:
    FIELDS={'schema','mode','outcome','reason','groups_pruned','candidate_groups','candidate_bytes_saved','cost_usd','input_tokens','output_tokens','elapsed_ms','shadow'}
    def __init__(self,path): self.path=str(path)
    def __call__(self,record):
        if set(record)-self.FIELDS: raise ValueError('unapproved metrics')
        p=Path(self.path); p.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_APPEND|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'a') as f: f.write(json.dumps(record,allow_nan=False)+'\n')
