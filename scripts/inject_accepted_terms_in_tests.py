"""One-shot: inject accepted_terms into order POST payloads in backend tests."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1] / 'backend'
ORDER_MARKERS = (
    '/api/users/orders/',
    'ORDERS_URL',
    "'/orders/'",
    '"/orders/"',
    'create_order',
    'orders/guest',
)

changed = []
for path in ROOT.rglob('test*.py'):
    text = path.read_text(encoding='utf-8')
    if not any(m in text for m in ORDER_MARKERS):
        continue
    lines = text.splitlines(True)
    out = []
    i = 0
    modified = False
    while i < len(lines):
        line = lines[i]
        out.append(line)
        if re.search(r'''['"]total_amount['"]\s*:''', line):
            lookahead = ''.join(lines[i : i + 8])
            if 'accepted_terms' not in lookahead:
                window = ''.join(lines[max(0, i - 50) : i + 1])
                if any(m in window for m in ORDER_MARKERS):
                    indent = re.match(r'^(\s*)', line).group(1)
                    quote = "'" if "'total_amount'" in line else '"'
                    out.append(f'{indent}{quote}accepted_terms{quote}: True,\n')
                    modified = True
        i += 1
    if modified:
        path.write_text(''.join(out), encoding='utf-8')
        changed.append(str(path.relative_to(ROOT)))

print(f'updated {len(changed)} files')
for c in changed:
    print(c)
