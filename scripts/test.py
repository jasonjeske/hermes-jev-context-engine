#!/usr/bin/env python3
"""Run all distribution tests offline in a fresh synthetic Hermes home."""
import argparse
import os
from pathlib import Path
import platform
import sys
import tempfile
import unittest


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--native-source', type=Path, required=True)
    args = ap.parse_args()
    root = Path(__file__).resolve().parents[1]
    work = root/'.test-work'
    work.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=work) as temp:
        home = Path(temp).resolve()
        for key in list(os.environ):
            if key.startswith('HERMES_') or key.endswith(('_API_KEY', '_AUTH_TOKEN', '_PROXY')):
                os.environ.pop(key, None)
        os.environ.update(HOME=str(home), HERMES_HOME=str(home/'hermes'), TMPDIR=str(home),
                          PYTHONDONTWRITEBYTECODE='1',
                          PYTHONPATH=os.pathsep.join([str(args.native_source.resolve()), str(root)]))
        tempfile.tempdir = str(home)
        sys.dont_write_bytecode = True
        sys.path[:0] = [str(root), str(root/'tests'), str(args.native_source.resolve())]
        platform.platform()  # Warm stdlib probes before offline guard.
        def audit(event, arguments):
            if event in ('socket.connect', 'socket.getaddrinfo', 'socket.sendto'):
                raise RuntimeError('offline tests prohibit network')
        sys.addaudithook(audit)
        result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.discover(str(root/'tests')))
        return 0 if result.wasSuccessful() else 1


if __name__ == '__main__': raise SystemExit(main())
