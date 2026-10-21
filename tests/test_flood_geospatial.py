"""Geospatial tests: coordinate alignment, half-cell tie-breaking, NoData masking."""
from pathlib import Path
import tempfile
import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
from engine.landslide.tiles import nearest_sample
from engine.flood.tiles import write_tiles
from engine.flood.bnpb import ingest_layer


def test_flood_tiles_half_cell_sampling():
    lats = np.array([10.0, 0.0])
    lons = np.array([100.0, 110.0])
    values = np.array([[10.0, 20.0], [30.0, 40.0]], dtype=np.float32)

    # Sample exactly at tie point (lat=5.0, lon=105.0)
    qlat = np.array([5.0])
    qlon = np.array([105.0])
    sampled = nearest_sample(values, lats, lons, qlat, qlon, nodata_val=np.nan)
    # Tie-breaking convention chooses top-right (index [0, 1] = 20.0)
    assert sampled[0] == pytest.approx(20.0)

    # Outside bounds gives NoData (NaN)
    qlat_out = np.array([50.0])
    qlon_out = np.array([105.0])
    sampled_out = nearest_sample(values, lats, lons, qlat_out, qlon_out, nodata_val=np.nan)
    assert np.isnan(sampled_out[0])


def test_write_tiles_generates_valid_webp():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        lats = np.linspace(6.5, -11.5, 73)
        lons = np.linspace(94.0, 141.5, 191)
        rain = np.full((73, 191), 50.0, dtype=np.float32)

        write_tiles(root, 24, "rainfall", rain, lats, lons)
        # Check at least one tile was generated
        tiles = list(root.glob("tiles/rainfall/24/*/*/*.webp"))
        assert len(tiles) > 0
        header = tiles[0].read_bytes()[:12]
        assert header.startswith(b"RIFF")
        assert b"WEBP" in header


def test_ingest_layer_chunk_size_validation():
    with pytest.raises(ValueError, match="Chunk size must be positive"):
        ingest_layer("http://dummy", "dummy.tif", "dummy.json", [0, 0, 1, 1], chunk_size=0)


@pytest.mark.parametrize("bad_dtype", [False, True])
def test_raw_export_validates_numeric_payload_and_nodata(tmp_path, bad_dtype):
    from rasterio.io import MemoryFile
    from engine.landslide.hazard import export_chunk
    values = np.array([[0, 1], [-3.4028235e38, 0.5]], dtype=np.float32)
    dtype = "uint8" if bad_dtype else "float32"
    with MemoryFile() as memory:
        with memory.open(driver="GTiff", width=2, height=2, count=1, dtype=dtype,
                         crs="EPSG:4326", transform=from_origin(100, 2, 1, 1)) as dst:
            dst.write(np.zeros((2, 2), dtype=np.uint8) if bad_dtype else values, 1)
        payload = memory.read()
    class Response:
        closed = False
        def raise_for_status(self):
            pass
        def iter_content(self, chunk_size):
            yield payload
        def close(self):
            self.closed = True
    response = Response()
    class Client:
        def get(self, url, **kwargs):
            assert kwargs["stream"] is True
            assert kwargs["params"]["renderingRule"] == '{"rasterFunction": "None"}'
            return response
    if bad_dtype:
        with pytest.raises(ValueError, match="raw Float32"):
            export_chunk(Client(), (100, 0, 102, 2), 2, 2, 4326, tmp_path)
    else:
        result = export_chunk(Client(), (100, 0, 102, 2), 2, 2, 4326, tmp_path)
        assert result[0, 0] == 0
        assert result[0, 1] == 1
        assert np.isnan(result[1, 0])
        assert result[1, 1] == 0.5
    assert response.closed


def test_export_payload_bound_closes_response(tmp_path):
    from engine.landslide.hazard import export_chunk
    class Response:
        closed = False
        def raise_for_status(self):
            pass
        def iter_content(self, chunk_size):
            yield b"x" * (2 * 1024 * 1024)
        def close(self):
            self.closed = True
    response = Response()
    class Client:
        def get(self, *args, **kwargs):
            return response
    with pytest.raises(ValueError, match="bounded raster payload"):
        export_chunk(Client(), (100, 0, 102, 2), 2, 2, 4326, tmp_path)
    assert response.closed


def test_ingest_lock_preserves_active_writer(tmp_path):
    lock = tmp_path / "ingest.lock"
    lock.write_text("active", encoding="utf-8")
    with pytest.raises(FileExistsError):
        ingest_layer("https://example.invalid", tmp_path / "raw.tif",
                     tmp_path / "latest.json", [0, 0, 1, 1])
    assert lock.read_text(encoding="utf-8") == "active"
