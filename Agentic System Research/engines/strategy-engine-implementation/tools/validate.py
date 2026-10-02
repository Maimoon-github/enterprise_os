#!/usr/bin/env python3
"""Run all tests; --require-live fails if production fixtures are unavailable."""
import argparse
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'backend'), str(ROOT)]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--require-live',action='store_true')
    args=parser.parse_args()
    suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'),top_level_dir=str(ROOT))
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    if args.require_live and (result.skipped or not os.environ.get('STRATEGY_LIVE_FACTORY')):
        print('PRODUCTION ACCEPTANCE BLOCKED: live runtime/ledger checks did not run.',file=sys.stderr)
        return 2
    return 0 if result.wasSuccessful() else 1


if __name__=='__main__':
    raise SystemExit(main())
