"""Tile + manifest HTTP server (Python stdlib only, no dependencies).

Routes:
  GET /                      -> service info
  GET /api/gfs/latest        -> latest run manifest summary
  GET /api/gfs/runs          -> list of processed runs
  GET /api/gfs/runs/<run>/manifest.json
  GET /tiles/gfs/...webp     -> tile file (Cache-Control: 1h)

CORS is open so the web frontend (any origin) can consume the tiles.
Run:  python -m engine.gfs.run serve --port 8080
"""
from __future__ import annotations

import json
import mimetypes
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse

from . import config, pipeline, source


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # keep stdout clean
        pass

    def _send_json(self, obj, status=200):
        body = json.dumps(obj, indent=1).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: str, content_type: str):
        with open(path, "rb") as fh:
            body = fh.read()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "public, max-age=3600")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        parsed = urlparse(self.path)
        path = unquote(parsed.path)

        if path == "/":
            self._send_json({"service": "metamorph-nwp GFS tile engine",
                             "model": "GFS 0.25deg",
                             "endpoints": ["/api/gfs/latest", "/api/gfs/runs",
                                           "/api/gfs/runs/<run>/manifest.json",
                                           "/tiles/gfs/<run>/<valid>/<variable>/<z>/<x>/<y>.webp"]})
            return
        if path == "/api/gfs/latest":
            if not os.path.exists(config.LATEST_FILE):
                self._send_json({"error": "no processed run yet"}, 404)
                return
            with open(config.LATEST_FILE) as fh:
                self._send_json(json.load(fh))
            return
        if path == "/api/gfs/runs":
            self._send_json({"runs": pipeline.list_runs()})
            return
        if path.startswith("/api/gfs/runs/") and path.endswith("/manifest.json"):
            run_dir = path.split("/")[4]
            mpath = os.path.join(config.TILE_DIR, "gfs", run_dir, "manifest.json")
            if not os.path.exists(mpath):
                self._send_json({"error": "manifest not found"}, 404)
                return
            with open(mpath) as fh:
                self._send_json(json.load(fh))
            return
        if path.startswith("/tiles/gfs/") and path.endswith(".webp"):
            rel = path[len("/tiles/gfs/"):]
            # guard against path traversal
            full = os.path.normpath(os.path.join(config.TILE_DIR, "gfs", rel))
            if not full.startswith(os.path.normpath(os.path.join(config.TILE_DIR, "gfs"))):
                self._send_json({"error": "forbidden"}, 403)
                return
            if not os.path.exists(full):
                self._send_json({"error": "tile not found"}, 404)
                return
            self._send_file(full, "image/webp")
            return
        self._send_json({"error": "not found"}, 404)

    def do_OPTIONS(self):  # noqa: N802
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()


def serve(port: int = 8080, host: str = "0.0.0.0") -> None:
    mimetypes.add_type("image/webp", ".webp")
    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"GFS tile server on http://{host}:{port}  (data: {config.DATA_DIR})")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopping")
        httpd.shutdown()


if __name__ == "__main__":
    serve()
