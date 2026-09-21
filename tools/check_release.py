"""Offline distribution checks. Not a replacement for a secret scanner or review."""
import re
from pathlib import Path

root = Path(__file__).resolve().parents[1]
errors = []
count = 0
for path in sorted(root.rglob('*')):
    rel = path.relative_to(root)
    if '.git' in rel.parts:
        continue
    if path.is_symlink():
        errors.append(f"symlink: {rel}")
        continue
    if not path.is_file():
        continue
    count += 1
    if (path.name == '.env' or path.name.startswith('.env.') or
        path.suffix in {'.sqlite', '.sqlite3', '.db', '.jsonl', '.pyc'} or
        any(p in {'__pycache__', '.venv', 'venv', 'state', 'archives', 'backups', 'node_modules'} for p in rel.parts)):
        errors.append(f"runtime/private artifact: {rel}")
    if path.suffix in {'.png', '.jpg', '.jpeg', '.webp'}:
        continue
    try:
        text = path.read_text()
    except UnicodeDecodeError:
        errors.append(f"unexpected binary: {rel}")
        continue
    if re.search(r'/Users/[a-zA-Z][a-zA-Z0-9_-]*/|/home/[a-zA-Z][a-zA-Z0-9_-]*/', text):
        errors.append(f"absolute user-home path requires review: {rel}")
    if path.suffix == '.md':
        if chr(0x2014) in text:
            errors.append(f"em dash in prose: {rel}")
        for link in re.findall(r'!?\[[^\]]*\]\(([^)]+)\)', text):
            if link.startswith(('https://', 'http://', 'mailto:', '#')):
                continue
            target = link.split('#', 1)[0].split(' "', 1)[0]
            if target and not (path.parent / target).exists():
                errors.append(f"broken local link: {rel} -> {target}")
if errors:
    print('\n'.join(errors))
    raise SystemExit(1)
print(f"PASS: {count} distribution files; no forbidden runtime artifacts, absolute user-home paths or broken local Markdown links")
