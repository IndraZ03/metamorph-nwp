"""No scientific coefficients or category boundaries are assumed."""
from engine.landslide import config as shared

OUTPUT_DIR = shared.OUTPUT_DIR.parent / "flood"
RUNS_DIR = OUTPUT_DIR / "runs"
LATEST_PATH = OUTPUT_DIR / "latest.json"
STATUS_PATH = OUTPUT_DIR / "status.json"
TP_DIR = shared.TP_DIR
SOURCES_DIR = OUTPUT_DIR / "sources"
HISTORY_DIR = OUTPUT_DIR / "history"
BBOX = shared.BBOX
MINZOOM, MAXZOOM = 3, 6
METHOD_VERSION = "flood_indicators_v1"
SOURCES = {
    "hazard": "https://gis.bnpb.go.id/server/rest/services/inarisk/INDEKS_BAHAYA_BANJIR/ImageServer",
    "vulnerability": "https://gis.bnpb.go.id/server/rest/services/inarisk/layer_kerentanan_banjir/ImageServer",
}
DISCLAIMER = ("Produk ini merupakan indikasi potensi banjir berdasarkan prakiraan curah hujan ECMWF "
    "dan informasi spasial InaRISK BNPB. Produk belum menggantikan peringatan dini resmi dan tidak "
    "merepresentasikan prediksi pasti lokasi, waktu, atau kedalaman genangan.")
