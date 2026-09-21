#!/usr/bin/env python3
"""Separate stronger native rollback diagnostic. Exit 1 means invariant fails."""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
import time


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--native-source', type=Path, required=True)
    args = ap.parse_args()
    root = Path(__file__).resolve().parents[1]
    work = root/'.test-work'; work.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=work) as temp:
        home = Path(temp).resolve()
        os.environ.update(HOME=str(home), HERMES_HOME=str(home), PYTHONDONTWRITEBYTECODE='1')
        sys.dont_write_bytecode = True
        sys.path[:0] = [str(root), str(root/'tests'), str(args.native_source.resolve())]
        def audit(event, arguments):
            if event in ('socket.connect', 'socket.getaddrinfo', 'socket.sendto'):
                raise RuntimeError('network forbidden')
        sys.addaudithook(audit)
        from agent.context_compressor import ContextCompressor
        from agent import conversation_compression as host
        from plugin.engine import JevContextEngine, Settings
        from plugin.storage import Archive
        from test_plugin import fixture, Scorer
        stock = ContextCompressor(model='', config_context_length=200000, quiet_mode=True)
        jev = JevContextEngine(settings=Settings(mode='active', protect_first_n=1, protect_last_n=1,
            egress_authorized=True, session_scope='public_synthetic', authorized_task='public synthetic task'),
            scorer=Scorer(), archive=Archive(home/'archive'))
        results = {}
        for name, engine, messages in [('stock', stock, [{'role':'user','content':'Synthetic short request'}]), ('jev', jev, fixture())]:
            engine._last_feasibility_skip = True
            engine._last_compress_refused_would_grow = True
            engine._structural_no_op_backoff_until = time.monotonic()+100
            fields = ('_last_feasibility_skip', '_last_compress_refused_would_grow', '_structural_no_op_backoff_until')
            before = {key:getattr(engine,key) for key in fields}
            saved = host._snapshot_compressor_attempt_state(engine)
            engine.compress(messages, force=True)
            host._restore_compressor_attempt_state(engine, saved)
            results[name] = {'full_restoration': all(getattr(engine,k)==v for k,v in before.items()),
                             'snapshot_restored': host._snapshot_compressor_attempt_state(engine)==saved,
                             'changed_fields': [k for k,v in before.items() if getattr(engine,k)!=v]}
        print(json.dumps(results, indent=2))
        return 0 if all(v['full_restoration'] for v in results.values()) else 1


if __name__ == '__main__': raise SystemExit(main())
