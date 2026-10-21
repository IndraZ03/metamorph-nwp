import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from engine import health


class HealthTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.path = self.root / "latest.json"
        self.run = "2026-10-20T00:00:00Z"
        self.upstream = {"status": "ok", "run": self.run}

    def manifest(self, model="ecmwf"):
        if model == "gfs":
            return {"run": self.run, "variables": {"t2m": {}},
                    "timesteps": [{"forecast_hour": 0, "tiles": {"t2m": 1}}]}
        if model == "icon":
            return {"run_id": "2026102000", "parameters": [{"id": "t2m"}],
                    "timesteps": [{"step": 0, "step_str": "000", "params": ["t2m"]}]}
        return {"run_time": self.run, "run_id": "20261020T00", "variables": [{"id": "t2m"}],
                "steps": [{"step": 0, "ready": True, "vars": ["t2m"]}]}

    def check(self, model="ecmwf", manifest=None, artifacts=True, upstream=None):
        manifest = self.manifest(model) if manifest is None else manifest
        self.path.write_text(json.dumps(manifest), encoding="utf-8")
        if artifacts:
            relative = {"ecmwf": "20261020T00/t2m/0", "icon": "2026102000/t2m/000",
                        "gfs": "2026102000/2026102000/t2m"}[model]
            for kind in ("tiles", "numeric"):
                tile = self.root / kind / relative / "3/0/0.webp"
                tile.parent.mkdir(parents=True, exist_ok=True)
                tile.write_bytes(b"tile")
        return health.check_model(model, self.path, self.root / "tiles", self.root / "numeric",
                                  self.upstream if upstream is None else upstream)

    def test_fresh_all_formats(self):
        for model in health.MODELS:
            with self.subTest(model=model):
                self.assertEqual(self.check(model)["status"], "healthy")

    def test_gfs_latest_pointer_loads_catalog(self):
        manifest = self.manifest("gfs")
        self.check("gfs")
        canonical = self.root / "tiles/2026102000/manifest.json"
        canonical.write_text(json.dumps(manifest), encoding="utf-8")
        self.path.write_text(json.dumps({"run": self.run, "timesteps": manifest["timesteps"]}), encoding="utf-8")
        result = health.check_model("gfs", self.path, self.root / "tiles", self.root / "numeric", self.upstream)
        self.assertEqual(result["status"], "healthy")

    def test_check_all_shape(self):
        with patch.object(health, "probe_provider", return_value={"status": "unknown", "error": "offline"}):
            results = health.check_all(root=self.root, timeout=1)
        self.assertEqual(set(results), set(health.MODELS))
        self.assertTrue(all(r["fresh"] is None for r in results.values()))

    def test_stale_published_run(self):
        self.assertEqual(self.check(upstream={"status": "ok", "run": "2026-10-20T06:00:00Z"})["status"], "stale")

    def test_unknown_provider(self):
        result = self.check(upstream={"status": "unknown", "error": "TLS failure"})
        self.assertEqual(result["status"], "unknown")
        self.assertTrue(result["complete"])

    def test_empty(self):
        manifest = self.manifest()
        manifest["steps"] = []
        self.assertEqual(self.check(manifest=manifest)["status"], "incomplete")

    def test_missing_artifacts(self):
        result = self.check(artifacts=False)
        self.assertEqual(result["status"], "incomplete")
        self.assertTrue(any("missing artifact" in s for s in result["issues"]))

    def test_missing_variables(self):
        manifest = self.manifest()
        manifest["steps"][0]["vars"] = []
        self.assertFalse(self.check(manifest=manifest)["complete"])

    def test_missing_manifest_unknown(self):
        result = health.check_model("ecmwf", self.path, self.root, upstream=self.upstream)
        self.assertEqual(result["status"], "unknown")

    def test_probe_404_then_published(self):
        with patch.object(health, "_http", side_effect=[HTTPError("url", 404, "missing", {}, None), ""]) as http:
            result = health.probe_provider("gfs", now="2026-10-20T06:00:00Z")
        self.assertEqual(result["run"], "2026-10-20T00:00:00+00:00")
        self.assertEqual(http.call_count, 2)

    def test_probe_network_failure_not_stale_guess(self):
        with patch.object(health, "_http", side_effect=URLError("TLS failure")) as http:
            self.assertEqual(health.probe_provider("ecmwf")["status"], "unknown")
        self.assertEqual(http.call_count, 1)

    def test_probe_bound(self):
        with patch.object(health, "_http", side_effect=HTTPError("url", 404, "missing", {}, None)) as http:
            self.assertEqual(health.probe_provider("gfs")["status"], "unknown")
        self.assertEqual(http.call_count, 9)

    def test_icon_newest_listing(self):
        listing = "icon_global_icosahedral_single-level_2026102006_000_T_2M.grib2.bz2"
        with patch.object(health, "_http", return_value=listing):
            self.assertEqual(health.probe_provider("icon")["run"], "2026-10-20T06:00:00+00:00")

    def test_check_read_only(self):
        self.check()
        before = {str(p): (p.stat().st_mtime_ns, p.read_bytes()) for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(health.check_model("ecmwf", self.path, self.root / "tiles", self.root / "numeric", self.upstream)["status"], "healthy")
        after = {str(p): (p.stat().st_mtime_ns, p.read_bytes()) for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
