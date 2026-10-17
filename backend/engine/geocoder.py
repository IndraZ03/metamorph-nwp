import json
import sqlite3
import urllib.request
from pathlib import Path
from typing import Dict, Optional, Tuple

from .config import CACHE_DIR

DB_PATH = CACHE_DIR / "geocache.db"


class ReverseGeocoder:
    """
    Reverse geocoder for Indonesia domain with SQLite caching.
    Resolves: Kecamatan, Kabupaten/Kota, Provinsi.
    """

    def __init__(self):
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS geocache (
                    lat_key REAL,
                    lon_key REAL,
                    kecamatan TEXT,
                    kabupaten_kota TEXT,
                    provinsi TEXT,
                    negara TEXT,
                    display_name TEXT,
                    PRIMARY KEY (lat_key, lon_key)
                )
                """
            )
            conn.commit()

    @staticmethod
    def _round_key(lat: float, lon: float, precision: int = 2) -> Tuple[float, float]:
        """Snap coordinate to ~1 km grid to maximize cache hits."""
        return round(lat, precision), round(lon, precision)

    def resolve(self, lat: float, lon: float) -> Dict[str, str]:
        """
        Resolve lat, lon to location hierarchy:
        {
            "kecamatan": "...",
            "kabupaten_kota": "...",
            "provinsi": "...",
            "negara": "Indonesia"
        }
        """
        lat_k, lon_k = self._round_key(lat, lon)

        # 1. Check cache
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT kecamatan, kabupaten_kota, provinsi, negara, display_name FROM geocache WHERE lat_key=? AND lon_key=?",
                (lat_k, lon_k),
            )
            row = cursor.fetchone()
            if row:
                return {
                    "kecamatan": row[0],
                    "kabupaten_kota": row[1],
                    "provinsi": row[2],
                    "negara": row[3],
                    "display_name": row[4],
                }

        # 2. Query OSM Nominatim reverse geocode
        loc_data = {
            "kecamatan": "Perairan / Luar Wilayah",
            "kabupaten_kota": "-",
            "provinsi": "-",
            "negara": "Indonesia",
            "display_name": f"{lat:.4f}, {lon:.4f}",
        }

        url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat:.4f}&lon={lon:.4f}&zoom=14&addressdetails=1"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "metamorph-nwp/1.0 (metamorph-nwp-geocoder)"},
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.load(resp)

            addr = data.get("address", {})
            kecamatan = (
                addr.get("suburb")
                or addr.get("district")
                or addr.get("subdistrict")
                or addr.get("town")
                or addr.get("village")
                or "-"
            )
            kabupaten = (
                addr.get("city")
                or addr.get("county")
                or addr.get("municipality")
                or addr.get("regency")
                or "-"
            )
            provinsi = addr.get("state") or addr.get("province") or "-"
            negara = addr.get("country") or "Indonesia"
            display_name = data.get("display_name", f"{lat:.4f}, {lon:.4f}")

            loc_data = {
                "kecamatan": kecamatan,
                "kabupaten_kota": kabupaten,
                "provinsi": provinsi,
                "negara": negara,
                "display_name": display_name,
            }
        except Exception as e:
            # Fallback for offline/timeout or ocean
            pass

        # 3. Store into cache
        try:
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO geocache
                    (lat_key, lon_key, kecamatan, kabupaten_kota, provinsi, negara, display_name)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        lat_k,
                        lon_k,
                        loc_data["kecamatan"],
                        loc_data["kabupaten_kota"],
                        loc_data["provinsi"],
                        loc_data["negara"],
                        loc_data["display_name"],
                    ),
                )
                conn.commit()
        except Exception:
            pass

        return loc_data


_geocoder = None


def get_geocoder() -> ReverseGeocoder:
    global _geocoder
    if _geocoder is None:
        _geocoder = ReverseGeocoder()
    return _geocoder
