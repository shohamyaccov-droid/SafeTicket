#!/usr/bin/env python3
"""
Option A — IL vs global ticket pipeline QA runner.

Prints a clear PASS banner and exits with the same code as Django's test runner.

Usage (from repo root or backend):
  python il_global_ticket_approval_qa.py
"""
from __future__ import annotations

import os
import subprocess
import sys


def main() -> int:
    here = os.path.dirname(os.path.abspath(__file__))
    manage = os.path.join(here, 'manage.py')
    cmd = [
        sys.executable,
        manage,
        'test',
        'users.tests.test_il_global_approval_qa',
        '-v',
        '2',
    ]
    print('=' * 72)
    print('TradeTix Option A QA - IL pending_approval + global active')
    print('Running:', ' '.join(cmd))
    print('=' * 72)
    r = subprocess.run(cmd, cwd=here)
    if r.returncode == 0:
        print('\n>>> PASS - Test Case A (IL) and Test Case B (Global) completed OK <<<\n')
    else:
        print('\n>>> FAIL - see django test output above <<<\n')
    return r.returncode


if __name__ == '__main__':
    raise SystemExit(main())
