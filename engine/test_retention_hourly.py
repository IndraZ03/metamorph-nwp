import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from engine import retention as r
from engine import hourly


class RetentionTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 20, 12, tzinfo=timezone.utc)

    def test_boundary_and_future(self):
        self.assertFalse(r.expired(self.now - timedelta(hours=15), self.now))
        self.assertTrue(r.expired(self.now - timedelta(hours=16), self.now))
        self.assertTrue(r.keep_step(self.now - timedelta(days=5), 144, self.now))
        self.assertFalse(r.expired('unknown', self.now))

    def test_all_roots_manifest_latest_and_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            roots = [base / name for name in ('visual', 'numeric', 'grids', 'cache')]
            latest = base / 'latest.json'
            old = self.now - timedelta(hours=16)
            run = old.strftime('%Y%m%d%H')
            manifest = {'run_id': run, 'timesteps': [
                {'step': 0, 'valid_time': old.isoformat()},
                {'step': 24, 'valid_time': (old + timedelta(hours=24)).isoformat()}]}
            for root in roots:
                for step in ('000', '024'):
                    path = root / run / 't2m' / step
                    path.mkdir(parents=True)
                    (path / 'tile').write_text('x')
                r.atomic_write_json(root / run / 'manifest.json', manifest)
            r.atomic_write_json(latest, manifest)
            with patch.object(r, 'layouts', return_value=(roots, [latest], base / 'lock')):
                report = r.cleanup('icon', self.now, dry_run=True)
                self.assertEqual(len(report['removed']), 4)
                self.assertEqual(len(json.loads(latest.read_text())['timesteps']), 2)
                r.cleanup('icon', self.now)
                self.assertEqual(len(json.loads(latest.read_text())['timesteps']), 1)
                for root in roots:
                    self.assertFalse((root / run / 't2m' / '000').exists())
                    self.assertTrue((root / run / 't2m' / '024').exists())

    def test_gfs_and_cache_naming(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / 'tiles'
            stale = root / '2026101900' / '2026101920'
            future = root / '2026101900' / '2026102100'
            stale.mkdir(parents=True)
            future.mkdir(parents=True)
            with patch.object(r, 'layouts', return_value=([root], [], base / 'lock')):
                r.cleanup('gfs', self.now)
            self.assertFalse(stale.exists())
            self.assertTrue(future.exists())
            cache = base / 'cache'
            path = cache / '20261019T00' / '0.grib2'
            path.parent.mkdir(parents=True)
            path.write_bytes(b'x')
            static = cache / 'static.npz'
            static.write_bytes(b'x')
            with patch.object(r, 'layouts', return_value=([cache], [], base / 'lock')):
                r.cleanup('ecmwf', self.now)
            self.assertFalse(path.exists())
            self.assertTrue(static.exists())

    def test_gfs_latest_retargets_to_newest_ready_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / 'tiles'
            old = root / '2026101712'
            new = root / '2026102100'
            old.mkdir(parents=True)
            new.mkdir(parents=True)
            latest = base / 'latest.json'
            r.atomic_write_json(old / 'manifest.json', {
                'run': '2026-10-17T12:00:00Z',
                'timesteps': [{'forecast_hour': 0, 'valid': '2026-10-17T12:00:00Z'}]})
            r.atomic_write_json(new / 'manifest.json', {
                'run': '2026-10-21T00:00:00Z', 'status': 'partial',
                'timesteps': [{'forecast_hour': 0, 'valid': '2026-10-21T00:00:00Z'}]})
            r.atomic_write_json(latest, {'model': 'GFS', 'run': '2026-10-17T12:00:00Z', 'timesteps': []})
            with patch.object(r, 'layouts', return_value=([root], [latest], base / 'lock')):
                dry = r.cleanup('gfs', self.now, dry_run=True)
                self.assertEqual(dry['retargeted'], '2026102100')
                self.assertEqual(json.loads(latest.read_text())['timesteps'], [])
                live = r.cleanup('gfs', self.now)
                self.assertEqual(live['retargeted'], '2026102100')
                written = json.loads(latest.read_text())
                self.assertEqual(written['run'], '2026-10-21T00:00:00Z')
                self.assertEqual(written['manifest'], '/api/gfs/runs/2026102100/manifest.json')
                self.assertEqual(len(written['timesteps']), 1)
                again = r.cleanup('gfs', self.now)
                self.assertIsNone(again['retargeted'])

    def test_corrupt_manifest_preserves_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run = root / '2026101900'
            run.mkdir()
            (run / 'manifest.json').write_text('{')
            with patch.object(r, 'layouts', return_value=([root], [], root / 'lock')):
                self.assertIn('error', r.cleanup('icon', self.now))
            self.assertTrue(run.exists())

    def test_os_lock_releases(self):
        with tempfile.TemporaryDirectory() as tmp:
            lock = Path(tmp) / 'lock'
            with r.model_lock(lock):
                with self.assertRaises(RuntimeError):
                    with r.model_lock(lock):
                        pass
            with r.model_lock(lock):
                pass


class RunnerTests(unittest.TestCase):
    def test_isolated_subprocess_results(self):
        commands = {'ok': ['-c', 'print("ok")'], 'bad': ['-c', 'raise SystemExit(3)'],
                    'slow': ['-c', 'import time; time.sleep(10)']}
        with patch.object(hourly, 'COMMANDS', commands):
            self.assertTrue(hourly.run_model('ok', 5, sys.executable))
            self.assertFalse(hourly.run_model('bad', 5, sys.executable))
            self.assertFalse(hourly.run_model('slow', .1, sys.executable))

    def test_cycle_cleanup_error_is_failure(self):
        with patch.object(hourly, 'cleanup', return_value={'error': 'bad'}), patch.object(hourly, 'run_model', return_value=True), patch.object(hourly, 'health_snapshot', return_value={'ecmwf': {'fresh': True, 'complete': True}}):
            self.assertFalse(hourly.cycle())

    def test_once_and_no_catchup(self):
        with patch.object(hourly, 'cycle', return_value=True):
            self.assertEqual(hourly.daemon(10, 5, once=True), 0)
            waits = []
            def wait(delay):
                waits.append(delay)
                raise InterruptedError
            with self.assertRaises(InterruptedError):
                hourly.daemon(10, 5, clock=iter([0, 30]).__next__, wait=wait)
            self.assertEqual(waits, [10])


if __name__ == '__main__':
    unittest.main()
