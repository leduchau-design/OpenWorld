"""Local Docker parity runner guard checks; never launch real containers in CI."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'run_w5_pg_local.sh'


@unittest.skipUnless(shutil.which('bash'), 'bash required for guard-only runner tests')
class LocalPostgresRunnerGuardTests(unittest.TestCase):
    def invoke(self, *, args=(), confirm=None):
        env = dict(os.environ)
        env.pop('OPENWORLD_PG_LOCAL_CONFIRM', None)
        if confirm is not None:
            env['OPENWORLD_PG_LOCAL_CONFIRM'] = confirm
        return subprocess.run(
            ['bash', str(SCRIPT), *args],
            check=False, capture_output=True, text=True, timeout=10,
            env=env,
        )

    def test_script_has_valid_bash_syntax(self):
        result = subprocess.run(['bash', '-n', str(SCRIPT)], check=False,
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_refuses_execution_by_default(self):
        result = self.invoke()
        self.assertEqual(result.returncode, 2)
        self.assertIn('REFUSED', result.stderr)
        self.assertIn('OPENWORLD_PG_LOCAL_CONFIRM', result.stderr)

    def test_refuses_improper_acknowledgement(self):
        result = self.invoke(confirm='YES')
        self.assertEqual(result.returncode, 2)
        self.assertIn('REFUSED', result.stderr)

    def test_refuses_arguments_even_with_acknowledgement(self):
        # This must abort before Docker/driver probes and before any mutation.
        result = self.invoke(confirm='YES_EPHEMERAL_CONTAINER', args=['--dsn', 'production'])
        self.assertEqual(result.returncode, 2)
        self.assertIn('Usage', result.stderr)

    def test_binds_ephemeral_localhost_only_and_disables_image_pull(self):
        source = SCRIPT.read_text(encoding='utf-8')
        self.assertIn("--publish '127.0.0.1::5432'", source)
        self.assertIn('--pull=never', source)
        self.assertIn('OPENWORLD_PG_TEST_ISOLATED=YES_EPHEMERAL_DB', source)
        self.assertIn('verify_w5_pg_report.py', source)
        self.assertIn('trap cleanup EXIT', source)
        self.assertNotIn('docker system prune', source)
        self.assertNotIn('workflow_dispatch', source)


if __name__ == '__main__':
    unittest.main()