"""Unit tests for the GFS tile engine (no network, synthetic data)."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from engine.gfs import config, render  # noqa: E402


def _synthetic_grids():
    lat = np.arange(-11.0, 6.01, 0.25)   # ascending
    lon = np.arange(95.0, 141.01, 0.25)
    lon2d, lat2d = np.meshgrid(lon, lat)
    grids = {
        "temperature": 28.0 + 3.0 * np.sin(np.radians(lon2d)) - 0.1 * lat2d,
        "dew_point": 22.0 + 2.0 * np.cos(np.radians(lat2d)),
        "rh": 60.0 + 20.0 * np.sin(np.radians(lon2d * 2)),
        "pressure": 1010.0 + 3.0 * np.sin(np.radians(lat2d * 3)),
        "rain": np.clip(5.0 * np.sin(np.radians(lon2d * 3)) ** 2 - 2.0, 0, None),
        "cape": np.clip(1500.0 + 800.0 * np.sin(np.radians(lat2d * 4)), 0, None),
        "clouds": np.clip(50.0 + 40.0 * np.sin(np.radians(lon2d)), 0, 100),
        "u10": -4.0 + 2.0 * np.sin(np.radians(lat2d)),
        "v10": 3.0 + 1.5 * np.cos(np.radians(lon2d)),
        "wind": 5.0 + 2.0 * np.sin(np.radians(lon2d)),
        "_lat": lat,
        "_lon": lon,
    }
    return grids


class TestRender(unittest.TestCase):
    def test_tiles_created_webp(self):
        orig_max = config.ZOOM_MAX
        config.ZOOM_MAX = 3  # keep the test fast
        try:
            with tempfile.TemporaryDirectory() as tmp:
                counts = render.render_timestep(_synthetic_grids(), tmp)
                self.assertEqual(set(counts), set(config.VARIABLES))
                for key, n in counts.items():
                    self.assertGreater(n, 0, f"{key} produced no tiles")
                # at least one real .webp file exists and starts with RIFF
                found = []
                for root, _d, files in os.walk(tmp):
                    for f in files:
                        if f.endswith(".webp"):
                            found.append(os.path.join(root, f))
                self.assertTrue(found)
                with open(found[0], "rb") as fh:
                    self.assertEqual(fh.read(4), b"RIFF")
        finally:
            config.ZOOM_MAX = orig_max

    def test_clouds_alpha_is_coverage(self):
        var = config.VARIABLES["clouds"]
        vals = np.array([[0.0, 50.0, 100.0]])
        rgba = render.colorize(var, vals)
        self.assertEqual(tuple(rgba[0, 0]), (255, 255, 255, 0))
        self.assertEqual(rgba[0, 1, 3], 127)
        self.assertEqual(rgba[0, 2, 3], 255)

    def test_rain_transparent_below_threshold(self):
        var = config.VARIABLES["rain"]
        vals = np.array([[0.0, 0.05, 5.0]])
        rgba = render.colorize(var, vals)
        self.assertEqual(rgba[0, 0, 3], 0)
        self.assertEqual(rgba[0, 1, 3], 0)
        self.assertEqual(rgba[0, 2, 3], 255)

    def test_nan_transparent(self):
        var = config.VARIABLES["temperature"]
        vals = np.array([[np.nan, 25.0]])
        rgba = render.colorize(var, vals)
        self.assertEqual(rgba[0, 0, 3], 0)
        self.assertEqual(rgba[0, 1, 3], 255)


class TestPublish(unittest.TestCase):
    def test_partial_chunk_publishes_and_older_run_does_not_overwrite(self):
        from datetime import datetime, timezone
        from unittest.mock import patch
        from engine.gfs import pipeline

        new = datetime(2026, 10, 21, tzinfo=timezone.utc)
        old = datetime(2026, 10, 17, 12, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as tmp:
            latest = os.path.join(tmp, "latest.json")
            with patch.object(config, "LATEST_FILE", latest), \
                 patch.object(config, "TILE_DIR", os.path.join(tmp, "tiles")), \
                 patch.object(config, "CHUNK_TIMESTEPS", 1), \
                 patch.object(pipeline, "_cleanup_old_runs", return_value=[]), \
                 patch.object(pipeline.source, "download_timestep", return_value={"bytes": 1}), \
                 patch.object(pipeline.decode, "decode_timestep", return_value={}), \
                 patch.object(pipeline.render, "render_timestep", return_value={"temperature": 1}), \
                 patch.object(pipeline.source, "valid_dir_name", return_value="2026102100"), \
                 patch.object(pipeline.source, "valid_time", return_value=new):
                pipeline.process_run(new, forecast_list=[0])
                written = json.loads(Path(latest).read_text(encoding="utf-8"))
                self.assertEqual(written["run"], "2026-10-21T00:00:00Z")
                self.assertTrue(any("error" not in row and row.get("valid") for row in written["timesteps"]))
                pipeline.process_run(old, forecast_list=[0])
                self.assertEqual(json.loads(Path(latest).read_text(encoding="utf-8"))["run"], "2026-10-21T00:00:00Z")

    def test_empty_manifest_does_not_publish(self):
        from datetime import datetime, timezone
        from engine.gfs import pipeline

        with tempfile.TemporaryDirectory() as tmp:
            latest = os.path.join(tmp, "latest.json")
            with patch.object(config, "LATEST_FILE", latest):
                self.assertFalse(pipeline._update_latest(
                    datetime(2026, 10, 21, tzinfo=timezone.utc),
                    {"timesteps": [{"forecast_hour": 0, "error": "boom"}]},
                ))
                self.assertFalse(os.path.exists(latest))


class TestConfig(unittest.TestCase):
    def test_forecast_hours_maximal(self):
        hours = config.forecast_hours()
        self.assertEqual(len(hours), 209)  # 121 hourly + 88 3-hourly
        self.assertEqual(hours[0], 0)
        self.assertEqual(hours[120], 120)
        self.assertEqual(hours[-1], 384)

    def test_manifest_variable_meta_serializable(self):
        from engine.gfs.pipeline import _variable_meta
        json.dumps(_variable_meta())  # must not raise


if __name__ == "__main__":
    unittest.main()
