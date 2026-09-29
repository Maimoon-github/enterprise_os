"""Unit-process protocol checks. A subprocess is NOT a sandbox isolation test."""
import os
import subprocess
import sys
import unittest
from app.schemas.strategy import SolverOutput, canonical
from tests.support import ROOT, mandate, solver


class RuntimeCLITests(unittest.TestCase):
    def invoke(self, raw):
        env={'PATH':os.environ.get('PATH',''), 'PYTHONPATH':str(ROOT/'backend'), 'PYTHONDONTWRITEBYTECODE':'1'}
        return subprocess.run([sys.executable,str(ROOT/'sandbox/docker/hardened/skills/s-alloc/scripts/run.py')],
                              input=raw,capture_output=True,timeout=5,env=env)

    def test_cli_returns_exact_typed_solution(self):
        m=mandate()
        result=self.invoke(canonical(m))
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(SolverOutput.model_validate_json(result.stdout),solver.solve(m))
        self.assertEqual(result.stderr,b'')

    def test_invalid_payload_has_no_reflected_secret(self):
        result=self.invoke(b'{"secret":"never-echo-this"}')
        self.assertEqual(result.returncode,2)
        self.assertEqual(result.stdout,b'')
        self.assertNotIn(b'never-echo-this',result.stderr)

    def test_input_size_limit(self):
        result=self.invoke(b'x'*524289)
        self.assertEqual(result.returncode,2)
        self.assertEqual(result.stdout,b'')
